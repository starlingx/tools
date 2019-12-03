import yaml
import os
import sys, getopt, getpass
import subprocess
import hashlib
import tarfile
import re
import shutil
from urllib import request

SCHEMA_CHART_TEMPLATE = 'template/armada-chart.template'
SCHEMA_CHARTGROUP_TEMPLATE = 'template/armada-chartgroup.template'
SCHEMA_MANIFEST_TEMPLATE = 'template/armada-manifest.template'
BIN_FETCH_CHART_INFO = 'bin/fetch_chart_info.sh'
TEMP_USER_DIR = '/tmp/' + getpass.getuser() + '/'
# Temp app work dir to hold git repo and upstream tarball
# TEMP_APP_DIR = TEMP_USER_DIR/appName
TEMP_APP_DIR = ''
APP_GEN_PY_PATH = os.path.split(os.path.realpath(__file__))[0]

def to_camel_case(s):
    return s[0].lower() + s.title().replace('_','')[1:] if s else s

class ArmadaApplication:

    def __init__(self, app_data):
        # Initialize application config
        self._armada_app = {}
        # 'appName', 'namespace', 'version' are checked in check_manifest()
        self._armada_app['appName'] = app_data['appName']
        self._armada_app['namespace'] = app_data['namespace']
        self._armada_app['version'] = app_data['version']

        # Initialize manifest
        self._armada_manifest = app_data['manifest']

        # Initialize chartgroup
        self._armada_chartgroup = app_data['chartGroup']

        # Initialize chart
        self._armada_chart = app_data['chart']
        # add namespace and prefix to each chart
        # 'namespace', 'releasePrefix' are checked in check_manifest()
        for i in range(len(self._armada_chart)):
            self._armada_chart[i]['namespace'] = self._armada_app['namespace']
            self._armada_chart[i]['releasePrefix'] = self._armada_manifest['releasePrefix']

    # TODO: Validate values
    def _validate_app_values(self, app_data):
        return True

    # TODO: Validate values
    def _validate_manifest_values(self, manifest_data):
        return True

    # TODO: Validate values
    def _validate_chartgroup_values(self, chartgroup_data):
        return True

    # TODO: Validate values
    def _validate_chart_values(self, chart_data):
        return True

    def _validate_app_attributes(self):
        if not self._validate_app_values(self._armada_app):
            return False
        if not self._validate_manifest_values(self._armada_manifest):
            return False
        if not self._validate_chartgroup_values(self._armada_chartgroup):
            return False
        if not self._validate_chart_values(self._armada_chart):
            return False

        return True

    def get_app_name(self):
        return self._armada_app['appName']

    def _package_helm_chart(self, chart):
        path = chart['path']
        # lint helm chart
        cmd_lint = ['helm', 'lint', path]
        subproc = subprocess.run(cmd_lint, env=os.environ.copy(), \
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if subproc.returncode == 0:
            print(str(subproc.stdout, encoding = 'utf-8'))
        else:
            print(str(subproc.stderr, encoding = 'utf-8'))
            return False

        # package helm chart
        cmd_package = ['helm', 'package', path, '--save=false', \
                '--destination=' + self._armada_app['outputChartDir']]
        subproc = subprocess.run(cmd_package, env=os.environ.copy(), \
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if subproc.returncode == 0:
            output = str(subproc.stdout, encoding = 'utf-8')
            print(output)
            # capture tarball name
            for words in output.split('/'):
                if 'tgz' in words:
                    chart['tarballName'] = words.rstrip('\n')
        else:
            print(subproc.stderr)
            return False
        return True

    # pyyaml does not support writing yaml block with initial indent
    # add initial indent for yaml block substitution
    def _write_yaml_to_manifest(self, key, src, init_indent):
        target = {}
        # add heading key
        target[key] = src
        lines = yaml.safe_dump(target).split('\n')
        # remove ending space
        lines.pop()
        indents = ' ' * init_indent
        for i in range(len(lines)):
            lines[i] = indents + lines[i]
        # restore ending '\n'
        return '\n'.join(lines) + '\n'

    def _substitute_values(self, in_line, dicts):
        out_line = in_line
        pattern = re.compile('\$.+?\$')
        results = pattern.findall(out_line)
        if results:
            for result in results:
                result_word = result.strip('$').split('%')
                value_key = result_word[0]
                value_default = ''
                if len(result_word) > 1:
                    value_default = result_word[1]
                # underscore case to camel case
                value = to_camel_case(value_key)
                if value in dicts:
                    out_line = out_line.replace(result, str(dicts[value]))
                elif value_default:
                    out_line = out_line.replace(result, value_default)

        if out_line == in_line:
            return out_line, False
        else:
            return out_line, True

    def _substitute_blocks(self, in_line, dicts):
        out_line = in_line
        result = re.search('@\S+\|\d+@',out_line)
        if result:
            block_key = result.group().strip('@').split('|')
            key = block_key[0].lower()
            indent = int(block_key[1])
            if key in dicts:
                out_line = self._write_yaml_to_manifest(key, dicts[key], indent)
            else:
                out_line = ''

        return out_line

    # Fetch info from helm chart to fill
    # the values that needs to be substituted
    # Below info are needed:
    # - waitLabelKey
    # - chartArcname
    #
    def _fetch_info_from_chart(self, chart_idx):
        a_chart = self._armada_chart[chart_idx]
        bin_fetch_script = APP_GEN_PY_PATH + '/' + BIN_FETCH_CHART_INFO
        # waitLabelKey
        # search for the key of label which indicates '.Release.Name'
        # within deployment, statefulset, daemonset yaml file
        cmd = [bin_fetch_script, 'waitlabel', a_chart['path']]
        subproc = subprocess.run(cmd, env=os.environ.copy(), \
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if subproc.returncode == 0:
            output = str(subproc.stdout, encoding = 'utf-8')
            if output.strip():
                a_chart['waitLabelKey'] = output.strip()
        if 'waitLabelKey' not in a_chart:
            print("The label which indicates .Release.Name is not found in %s" % a_chart['name'])
            return False

        # chartArcname is the helm chart name in Chart.yaml
        # it is used as tarball arcname during helm package
        cmd = [bin_fetch_script, 'chartname', a_chart['path']]
        subproc = subprocess.run(cmd, env=os.environ.copy(), \
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if subproc.returncode == 0:
            output = str(subproc.stdout, encoding = 'utf-8')
            if output.strip():
                a_chart['chartArcname'] = output.strip()
        if 'chartArcname' not in a_chart:
            print("The name within Chart.yaml of chart %s folder is not found" % a_chart['name'])
            return False

        return True

    # Sub-process of app generation
    # lint and package helm chart
    # TODO: sub-chart dependency check
    #
    def _gen_helm_chart_tarball(self, chart):
        ret = False
        path = ''
        print('Processing chart %s...' % chart['name'])
        # check pathtype of the chart
        if chart['_pathType'] is 'git':
            gitname = ''
            # download git
            if not os.path.exists(TEMP_APP_DIR):
                os.makedirs(TEMP_APP_DIR)
            # if the git folder exists, check git name and use that folder
            # otherwise git clone from upstream
            if not os.path.exists(TEMP_APP_DIR + chart['_gitname']):
                saved_pwd = os.getcwd()
                os.chdir(TEMP_APP_DIR)
                cmd = ['git', 'clone', chart['path']]
                subproc = subprocess.run(cmd, env=os.environ.copy(), \
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if subproc.returncode != 0:
                    output = str(subproc.stderr, encoding = 'utf-8')
                    print(output)
                    print('Error: git clone %s failed' % chart['_gitname'])
                    os.chdir(saved_pwd)
                    return False
                os.chdir(saved_pwd)
            else:
                # git pull to ensure folder up-to-date
                saved_pwd = os.getcwd()
                os.chdir(TEMP_APP_DIR + chart['_gitname'])
                cmd = ['git', 'pull']
                subproc = subprocess.run(cmd, env=os.environ.copy(), \
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if subproc.returncode != 0:
                    output = str(subproc.stderr, encoding = 'utf-8')
                    print(output)
                    print('Error: git pull for %s failed' % chart['_gitname'])
                    os.chdir(saved_pwd)
                    return False
                os.chdir(saved_pwd)
            path = TEMP_APP_DIR + chart['_gitname'] + '/' + chart['subpath']
        elif chart['_pathType'] is 'tarball':
            if not os.path.exists(TEMP_APP_DIR):
                os.makedirs(TEMP_APP_DIR)
            try:
                # check whether it's a url or local tarball
                if not os.path.exists(chart['path']):
                    # download tarball
                    tarpath = TEMP_APP_DIR + chart['_tarname'] + '.tgz'
                    if not os.path.exists(tarpath):
                        res = request.urlopen(chart['path'])
                        with open(tarpath, 'wb') as f:
                            f.write(res.read())
                else:
                    tarpath = chart['path']
                # extract tarball
                chart_tar = tarfile.open(tarpath, 'r:gz')
                chart_files = chart_tar.getnames()
                # get tar arcname for packaging helm chart process
                # TODO: compatible with the case that there is no arcname
                chart['_tarArcname'] = chart_files[0].split('/')[0]
                if not os.path.exists(chart['_tarArcname']):
                    for chart_file in chart_files:
                        chart_tar.extract(chart_file, TEMP_APP_DIR)
                chart_tar.close()
            except Exception as e:
                print('Error: %s' % e)
                return False
            path = TEMP_APP_DIR + chart['_tarArcname'] + '/' + chart['subpath']
        elif chart['_pathType'] is 'dir':
            path = chart['path']

        # update chart path
        # remove ending '/'
        chart['path'] = path.rstrip('/')
        # lint and package
        ret = self._package_helm_chart(chart)

        return ret

    # Sub-process of app generation
    # generate application manifest file
    #
    def _gen_armada_manifest(self):
        # check manifest file existance
        manifest_file = self._armada_app['outputDir'] + '/' + self._armada_app['appName'] + '.yaml'
        if os.path.exists(manifest_file):
            os.remove(manifest_file)

        # update schema path to abspath
        chart_template = APP_GEN_PY_PATH + '/' + SCHEMA_CHART_TEMPLATE
        chartgroup_template = APP_GEN_PY_PATH + '/' + SCHEMA_CHARTGROUP_TEMPLATE
        manifest_template = APP_GEN_PY_PATH + '/' + SCHEMA_MANIFEST_TEMPLATE

        # generate chart schema
        try:
            with open(chart_template, 'r') as f:
                chart_schema = f.readlines()
        except IOError:
            print('File %s not found' % chart_template)
            return False
        with open(manifest_file, 'a') as f:
            # iterate each armada_chart
            for idx in range(len(self._armada_chart)):
                a_chart = self._armada_chart[idx]
                # fetch chart specific info
                if not self._fetch_info_from_chart(idx):
                    return False
                for line in chart_schema:
                    # substitute template values to chart values
                    out_line, substituted = self._substitute_values(line, a_chart)
                    if not substituted:
                        # substitute template blocks to chart blocks
                        out_line = self._substitute_blocks(line, a_chart)
                    f.write(out_line)

        # generate chartgroup schema
        try:
            with open(chartgroup_template, 'r') as f:
                chartgroup_schema = f.readlines()
        except IOError:
            print('File %s not found' % chartgroup_template)
            return False
        with open(manifest_file, 'a') as f:
            # iterate each chartgroup
            for chartgroup in self._armada_chartgroup:
                for line in chartgroup_schema:
                    # substitute template values to chartgroup values
                    out_line, substituted = self._substitute_values(line, chartgroup)
                    if not substituted:
                        # substitute template blocks to chartgroup blocks
                        out_line = self._substitute_blocks(line, chartgroup)
                    f.write(out_line)

        # generate manifest schema
        try:
            with open(manifest_template, 'r') as f:
                manifest_schema = f.readlines()
        except IOError:
            print('File %s not found' % manifest_template)
            return False
        with open(manifest_file, 'a') as f:
            # only one manifest in an application
            manifest = self._armada_manifest
            # substitute values
            for line in manifest_schema:
                # substitute template values to manifest values
                out_line, substituted = self._substitute_values(line, manifest)
                if not substituted:
                    # substitute template blocks to manifest blocks
                    out_line = self._substitute_blocks(line, manifest)
                f.write(out_line)

        return True

    # Sub-process of app generation
    # generate application metadata
    #
    def _gen_metadata(self):
        # check metadata file existance
        metadata_file = self._armada_app['outputDir'] + '/metadata.yaml'
        if os.path.exists(metadata_file):
            os.remove(metadata_file)
        with open(metadata_file, 'a') as f:
            f.write('app_name: ' + self._armada_app['appName'] + '\n')
            f.write('app_version: ' + self._armada_app['version'] + '\n')
        return True


    def _gen_md5(self, in_file):
        with open(in_file, 'rb') as f:
            out_md5 = hashlib.md5(f.read()).hexdigest()
        return out_md5

    # Sub-process of app generation
    # generate application checksum file and tarball
    #
    def _gen_checksum_and_app_tarball(self):
        store_cwd = os.getcwd()
        os.chdir(self._armada_app['outputDir'])
        # gen checksum
        # check checksum file existance
        checksum_file = 'checksum.md5'
        if os.path.exists(checksum_file):
            os.remove(checksum_file)
        app_files = []
        for parent, dirnames, filenames in os.walk('./'):
            for filename in filenames:
                app_files.append(os.path.join(parent, filename))
        with open(checksum_file, 'a') as f:
            for target_file in app_files:
                f.write(self._gen_md5(target_file) + ' ' + target_file + '\n')
        app_files.append('./' + checksum_file)

        # gen application tarball
        tarname = self._armada_app['appName'] + '-' + self._armada_app['version'] + '.tgz'
        t = tarfile.open(tarname, 'w:gz')
        for target_file in app_files:
            t.add(target_file)
        t.close()
        os.chdir(store_cwd)
        return tarname

    # Generate armada application, including:
    # 1. helm chart tarballs
    # 2. armada manifest
    # 3. metadata file
    # 4. checksum file
    # 5. application tarball
    #
    def gen_app(self, output_dir, overwrite):
        ret = False
        if not self._validate_app_attributes():
            print('Error: Some of the app attributes are not valid!')
            return ret
        self._armada_app['outputDir'] = output_dir
        self._armada_app['outputChartDir'] = output_dir + '/charts'
        if not os.path.exists(self._armada_app['outputDir']):
            os.makedirs(self._armada_app['outputDir'])
        elif overwrite:
            shutil.rmtree(self._armada_app['outputDir'])
        else:
            print('Output folder %s exists, please remove it or use --overwrite.' % self._armada_app['outputDir'])
            return ret
        if not os.path.exists(self._armada_app['outputChartDir']):
            os.makedirs(self._armada_app['outputChartDir'])
        # 1. Generating helm chart tarball
        for chart in self._armada_chart:
            ret = self._gen_helm_chart_tarball(chart)
            if ret:
                print('Helm chart %s tarball generated!' % chart['name'])
                print('')
            else:
                print('Generating tarball for helm chart: %s error!' % chart['name'])
                return ret

        # 2. Generating armada manifest
        ret = self._gen_armada_manifest()
        if ret:
            print('Armada manifest generated!')
        else:
            print('Armada manifest generation failed!')
            return ret

        # 3. Generating metadata file
        ret = self._gen_metadata()
        if ret:
            print('Metadata generated!')
        else:
            print('Metadata generation failed!')
            return ret

        # 4&5. Generating checksum file and tarball
        ret = self._gen_checksum_and_app_tarball()
        if ret:
            print('Checksum generated!')
            print('App tarball generated at %s/%s' % (self._armada_app['outputDir'], ret))
            print('')
        else:
            print('Checksum and App tarball generation failed!')
            return ret

        return ret

    # For debug
    def print_app_data(self):
        print(self._armada_app)
        print(self._armada_manifest)
        print(self._armada_chartgroup)
        print(self._armada_chart)

def parse_yaml(yaml_in):
    yaml_data=''
    try:
        with open(yaml_in) as f:
            yaml_data = yaml.safe_load(f)
    except IOError:
        print('Error: %s no found' % yaml_in )
    except Exception as e:
        print('Error: Invalid yaml file')
    return yaml_data

def check_manifest(manifest_data):
    # TODO: check more mandatory key/values in manifest yaml

    # check app values
    if 'appName' not in manifest_data:
        print('Error: \'appName\' is missing.')
        return False

    if 'namespace' not in manifest_data:
        print('Error: \'namespace\' is missing.')
        return False

    if 'version' not in manifest_data:
        print('Error: \'version\' is missing.')
        return False

    # check manifest values
    if 'manifest' not in manifest_data:
        print('Error: \'manifest\'is missing.')
        return False

    if 'releasePrefix' not in manifest_data['manifest']:
        print('Error: Manifest attribute \'releasePrefix\' is missing.')
        return False

    # check chartGroup values
    if 'chartGroup' not in manifest_data:
        print('Error: \'chartGroup\' is missing.')
        return False

    # check chart values
    if 'chart' not in manifest_data:
        print('Error: \'chart\' is missing.')
        return False

    for chart in manifest_data['chart']:
        # check chart name
        if 'name' not in chart:
            print('Error: Chart attribute \'name\' is missing.')
            return False

        # check chart path, supporting: dir, git, tarball
        if 'path' not in chart:
            print('Error: Chart attribute \'path\' is missing in chart %s.' % chart['name'])
            return False
        else:
            # TODO: To support branches/tags in git repo
            if chart['path'].endswith('.git'):
                if 'subpath' not in chart:
                    print('Error: Chart attribute \'subpath\' is missing in chart %s.' % chart['name'])
                    return False
                chart['_pathType'] = 'git'
                gitname = re.search('[^/]+(?=\.git$)',chart['path']).group()
                if gitname:
                    chart['_gitname'] = gitname
                else:
                    print('Error: Invalid \'path\' in chart %s.' % chart['name'])
                    print('       only \'local dir\', \'.git\', \'.tar.gz\', \'.tgz\' are supported')
                    return False
            elif chart['path'].endswith('.tar.gz') or chart['path'].endswith('.tgz'):
                if 'subpath' not in chart:
                    print('Error: Chart attribute \'subpath\' is missing in chart %s.' % chart['name'])
                    return False
                chart['_pathType'] = 'tarball'
                tarname = re.search('[^/]+(?=\.tgz)|[^/]+(?=\.tar\.gz)',chart['path']).group()
                if tarname:
                    chart['_tarname'] = tarname
                else:
                    print('Error: Invalid \'path\' in chart %s.' % chart['name'])
                    print('       only \'local dir\', \'.git\', \'.tar.gz\', \'.tgz\' are supported')
                    return False
            else:
                if not os.path.isdir(chart['path']):
                    print('Error: Invalid \'path\' in chart %s.' % chart['name'])
                    print('       only \'local dir\', \'.git\', \'.tar.gz\', \'.tgz\' are supported')
                    return False
                chart['_pathType'] = 'dir'

    return True

def generate_app(file_in, out_folder, overwrite):
    global TEMP_APP_DIR
    app_data = parse_yaml(file_in)
    if not app_data:
        print('Parse yaml error')
        return
    if not check_manifest(app_data):
        print('Application manifest is not valid')
        return
    armada_app = ArmadaApplication(app_data)
    TEMP_APP_DIR = TEMP_USER_DIR + armada_app.get_app_name() + '/'
    app_out = out_folder + '/' + armada_app.get_app_name()
    armada_app.gen_app(app_out, overwrite)

def main(argv):
    input_file = ''
    output_folder = '.'
    overwrite = False
    try:
        options, args = getopt.getopt(argv, 'hi:o:', \
                ['help', 'input==', 'output==', 'overwrite'])
    except getopt.GetoptError:
        sys.exit()
    for option, value in options:
        if option in ('-h', '--help'):
            print('StarlingX User Application Generator')
            print('')
            print('Usage:')
            print('    python app-gen.py [Option]')
            print('')
            print('Options:')
            print('    -i, --input yaml_file    generate app from yaml_file')
            print('    -o, --output folder      generate app to output folder')
            print('        --overwrite          overwrite the output dir')
            print('    -h, --help               this help')
        if option in ('--overwrite'):
            overwrite = True
        if option in ('-i', '--input'):
            input_file = value
        if option in ('-o', '--output'):
            output_folder = value

    if not os.path.isfile(os.path.abspath(input_file)):
        print('Error: input file not found')
        sys.exit()
    if input_file:
        generate_app(os.path.abspath(input_file), os.path.abspath(output_folder), overwrite)

if __name__ == '__main__':
    main(sys.argv[1:])
