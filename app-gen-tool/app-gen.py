import yaml
import os
import sys, getopt, getpass
import subprocess
import hashlib
import tarfile
import re
import shutil
from urllib import request

## Variables for armada packaging
ARMADA_CHART_TEMPLATE = 'template_armada/armada-chart.template'
ARMADA_CHARTGROUP_TEMPLATE = 'template_armada/armada-chartgroup.template'
ARMADA_MANIFEST_TEMPLATE = 'template_armada/armada-manifest.template'
BIN_FETCH_CHART_INFO = 'bin/fetch_chart_info.sh'

## Variables for FluxCD packaging
FLUX_KUSTOMIZATION_TEMPLATE = 'templates_flux/kustomization.template'
FLUX_BASE_TEMPLATES = 'templates_flux/base/'
FLUX_MANIFEST_TEMPLATE = 'templates_flux/fluxcd-manifest'
FLUX_COMMON_TEMPLATE = 'templates_plugins/common.template'
FLUX_HELM_TEMPLATE = 'templates_plugins/helm.template'
FLUX_KUSTOMIZE_TEMPLATE = 'templates_plugins/kustomize.template'
FLUX_LIFECYCLE_TEMPLATE = 'templates_plugins/lifecycle.template'


TEMP_USER_DIR = '/tmp/' + getpass.getuser() + '/'
# Temp app work dir to hold git repo and upstream tarball
# TEMP_APP_DIR = TEMP_USER_DIR/appName
TEMP_APP_DIR = ''
APP_GEN_PY_PATH = os.path.split(os.path.realpath(__file__))[0]

def to_camel_case(s):
    return s[0].lower() + s.title().replace('_','')[1:] if s else s

class Application:

    def __init__(self, app_data):
        # Initialize application config
        self._app = {}
        self._app = app_data['appManifestFile-config']

        self.APP_NAME = self._app['appName']
        self.APP_NAME_WITH_UNDERSCORE = self._app['appName'].replace('-', '_')
        self.APP_NAME_CAMEL_CASE = self._app['appName'].replace('-', ' ').title().replace(' ', '')

        # Initialize chartgroup
        self._chartgroup = app_data['appManifestFile-config']['chartGroup']
        for i in range(len(self._chartgroup)):
            self._chartgroup[i]['namespace'] = self._app['namespace']

        # Create empty list that will contain all the charts
        self._listcharts = {}
        self._listcharts['chart_names'] = []
        self._listcharts['namespace'] = self._app['namespace']

        # Initialize chart
        self._chart = app_data['appManifestFile-config']['chart']
        for i in range(len(self._chart)):
            self._chart[i]['namespace'] = self._app['namespace']
            self._chart[i]['releasePrefix'] = self._app['manifest']['releasePrefix']
            self._listcharts['chart_names'].append(self._chart[i]['name'])

        # Initialize Armada manifest
        self._manifest = app_data['appManifestFile-config']['manifest']
        self._manifest['chart_groups'] = []
        for i in range(len(self._chartgroup)):
            self._manifest['chart_groups'].append(self._chartgroup[i]['name'])

        # Initialize setup data
        self.plugin_setup = app_data['setupFile-config']


        # Initialize metadata
        self.metadata = app_data['metadataFile-config']



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
        if not self._validate_app_values(self._app):
            return False
        if not self._validate_manifest_values(self._manifest):
            return False
        if not self._validate_chartgroup_values(self._chartgroup):
            return False
        if not self._validate_chart_values(self._chart):
            return False

        return True


    # Subprocess that check charts informations
    def check_charts(self):
        charts = self._chart
        for chart in charts:
            manifest_data = dict()
            chart_file_data = dict()
            manifest_data['name'], manifest_data['version'] = chart['name'], chart['version']
            if chart['_pathType'] == 'dir':
                try:
                    chart_metadata_f = open(f'{chart["path"]}/Chart.yaml', 'r')
                except Exception as e:
                    print(f'ERROR: {e}')
                    sys.exit(1)
                chart_file_lines = chart_metadata_f.readlines()
                chart_file_lines = [l for l in chart_file_lines if len(l) > 0 and l[0] != '#']
                chart_metadata_f.close()
                for line in chart_file_lines:
                    line = line.rstrip('\n')
                    line_data = line.split()
                    if not line_data:
                        continue
                    if 'name:' in line_data[0]:
                        chart_file_data['name'] = line_data[-1]
                    elif 'version:' in line_data[0]:
                        chart_file_data['version'] = line_data[-1]
            # To-do chart type different from dir
            for key in manifest_data:
                err_str = ''
                if key not in chart_file_data:
                    err_str = f'"{key}" is present in app-manifest.yaml but not in {chart["path"]}/Chart.yaml'
                    raise KeyError(err_str)
                if manifest_data[key] != chart_file_data[key]:
                    err_str = f'"{key}" has different values in app-manifest.yaml and {chart["path"]}/Chart.yaml'
                    raise ValueError(err_str)


    def get_app_name(self):
        return self._app['appName']


    # Sub-process of app generation
    # generate application helm-charts tarball
    #
    def _package_helm_chart(self, chart, chart_dir):
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
        cmd_package = ['helm', 'package', path, \
                '--destination=' + chart_dir]
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
        # remove ending space and first line
        lines.pop()
        lines.pop(0)
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

    def _fetch_info_from_chart(self, chart_idx):
        a_chart = self._chart[chart_idx]
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
    def _gen_helm_chart_tarball(self, chart, chart_dir):
        ret = False
        path = ''
        print('Processing chart %s...' % chart['name'])
        # check pathtype of the chart
        if chart['_pathType'] == 'git':
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
        elif chart['_pathType'] == 'tarball':
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
        elif chart['_pathType'] == 'dir':
            path = chart['path']

        # update chart path
        # remove ending '/'
        chart['path'] = path.rstrip('/')
        # lint and package
        ret = self._package_helm_chart(chart, chart_dir)

        return ret


    # Sub-process of app generation
    # generate application manifest file
    #
    def _gen_armada_manifest(self):
        # check manifest file existance
        manifest_file = self._app['outputArmadaDir'] + '/' + self._app['appName'] + '.yaml'
        if os.path.exists(manifest_file):
            os.remove(manifest_file)

        # update schema path to abspath
        chart_template = APP_GEN_PY_PATH + '/' + ARMADA_CHART_TEMPLATE
        chartgroup_template = APP_GEN_PY_PATH + '/' + ARMADA_CHARTGROUP_TEMPLATE
        manifest_template = APP_GEN_PY_PATH + '/' + ARMADA_MANIFEST_TEMPLATE

        # generate chart schema
        try:
            with open(chart_template, 'r') as f:
                chart_schema = f.readlines()
        except FileNotFoundError:
            print('File %s not found' % chart_template)
            return False
        with open(manifest_file, 'a') as f:
            # iterate each armada_chart
            for idx in range(len(self._chart)):
                a_chart = self._chart[idx]
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
        except FileNotFoundError:
            print('File %s not found' % chartgroup_template)
            return False
        with open(manifest_file, 'a') as f:
            # iterate each chartgroup
            for chartgroup in self._chartgroup:
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
        except FileNotFoundError:
            print('File %s not found' % manifest_template)
            return False
        with open(manifest_file, 'a') as f:
            # only one manifest in an application
            manifest = self._manifest
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
    # generate application fluxcd manifest files
    #
    def _gen_fluxcd_manifest(self):
        # check manifest file existance
        flux_dir = self._app['outputManifestDir']

        # update schema path to abspath
        kustomization_template = APP_GEN_PY_PATH + '/' + FLUX_KUSTOMIZATION_TEMPLATE

        base_helmrepo_template = APP_GEN_PY_PATH + '/' + FLUX_BASE_TEMPLATES + '/helmrepository.template'
        base_kustom_template = APP_GEN_PY_PATH + '/' + FLUX_BASE_TEMPLATES + '/kustomization.template'
        base_namespace_template = APP_GEN_PY_PATH + '/' + FLUX_BASE_TEMPLATES + '/namespace.template'

        manifest_helmrelease_template = APP_GEN_PY_PATH + '/' + FLUX_MANIFEST_TEMPLATE + '/helmrelease.template'
        manifest_kustomization_template = APP_GEN_PY_PATH + '/' + FLUX_MANIFEST_TEMPLATE + '/kustomization.template'

        manifest = self._app
        chartgroup = self._listcharts
        chart = self._chart

        # generate kustomization file
        try:
            with open(kustomization_template, 'r') as f:
                kustomization_schema = f.readlines()
        except FileNotFoundError:
            print('File %s not found' % kustomization_template)
            return False
        kustom_file = flux_dir + 'kustomization.yaml'
        with open(kustom_file, 'a') as f:
            # substitute values
            for line in kustomization_schema:
                # substitute template values to manifest values
                out_line, substituted = self._substitute_values(line, chartgroup)
                if not substituted:
                    # substitute template blocks to manifest blocks
                    out_line = self._substitute_blocks(line, chartgroup)
                f.write(out_line)

        # generate base/namespace file
        try:
            with open(base_namespace_template, 'r') as f:
                base_namespace_schema = f.readlines()
        except FileNotFoundError:
            print('File %s not found' % base_namespace_template)
            return False
        base_namespace_file = flux_dir + 'base/namespace.yaml'
        with open(base_namespace_file, 'a') as f:
            # substitute values
            for line in base_namespace_schema:
                # substitute template values to manifest values
                out_line, substituted = self._substitute_values(line, manifest)
                if not substituted:
                    # substitute template blocks to manifest blocks
                    out_line = self._substitute_blocks(line, manifest)
                f.write(out_line)

        # generate base/kustomization file
        # generate base/helmrepository file
        # Both yaml files don't need to add informations from the input file
        try:
            with open(base_kustom_template, 'r') as f:
                base_kustom_schema = f.readlines()
        except FileNotFoundError:
            print('File %s not found' % base_kustom_template)
            return False
        base_kustom_file = flux_dir + 'base/kustomization.yaml'
        with open(base_kustom_file, 'a') as f:
            for line in base_kustom_schema:
                out_line = line
                f.write(out_line)

        try:
            with open(base_helmrepo_template, 'r') as f:
                base_helmrepo_schema = f.readlines()
        except FileNotFoundError:
            print('File %s not found' % base_helmrepo_template)
            return False
        base_helmrepo_file = flux_dir + 'base/helmrepository.yaml'
        with open(base_helmrepo_file, 'a') as f:
            for line in base_helmrepo_schema:
                out_line = line
                f.write(out_line)

        # iterate each fluxcd_chart for the generation of its fluxcd manifests
        for idx in range(len(chart)):
            a_chart = chart[idx]

            # generate manifest/helmrelease file
            try:
                with open(manifest_helmrelease_template, 'r') as f:
                    manifest_helmrelease_schema = f.readlines()
            except FileNotFoundError:
                print('File %s not found' % manifest_helmrelease_template)
                return False
            manifest_helmrelease_file = flux_dir + a_chart['name'] + '/helmrelease.yaml'
            with open(manifest_helmrelease_file, 'a') as f:
                # fetch chart specific info
                for line in manifest_helmrelease_schema:
                    # substitute template values to chart values
                    out_line, substituted = self._substitute_values(line, a_chart)
                    if not substituted:
                        # substitute template blocks to chart blocks
                        out_line = self._substitute_blocks(line, a_chart)
                    f.write(out_line)

            # generate manifest/kustomizaion file
            try:
                with open(manifest_kustomization_template, 'r') as f:
                    manifest_kustomization_schema = f.readlines()
            except FileNotFoundError:
                print('File %s not found' % manifest_kustomization_template)
                return False
            manifest_kustomization_file = flux_dir + a_chart['name'] + '/kustomization.yaml'
            with open(manifest_kustomization_file, 'a') as f:
                # fetch chart specific info
                for line in manifest_kustomization_schema:
                    # substitute template values to chart values
                    out_line, substituted = self._substitute_values(line, a_chart)
                    if not substituted:
                        # substitute template blocks to chart blocks
                        out_line = self._substitute_blocks(line, a_chart)
                    f.write(out_line)

            # generate an empty manifest/system-overrides file
            system_override_file = flux_dir + '/' + a_chart['name'] + '/' + a_chart['name'] + '-system-overrides.yaml'
            open(system_override_file, 'w').close()

            # generate a manifest/static-overrides file
            static_override_file = flux_dir + '/' + a_chart['name'] + '/' + a_chart['name'] + '-static-overrides.yaml'
            open(static_override_file, 'w').close()

        return True


    # Sub-process of app generation
    # generate application plugin files
    #
    def _gen_plugins(self):

        plugin_dir =  self._app['outputPluginDir']

        common_template = APP_GEN_PY_PATH + '/' + FLUX_COMMON_TEMPLATE
        helm_template = APP_GEN_PY_PATH + '/' + FLUX_HELM_TEMPLATE
        kustomize_template = APP_GEN_PY_PATH + '/' + FLUX_KUSTOMIZE_TEMPLATE
        lifecycle_template = APP_GEN_PY_PATH + '/' + FLUX_LIFECYCLE_TEMPLATE

        appname = 'k8sapp_' + self.APP_NAME_WITH_UNDERSCORE
        namespace = self._app['namespace']
        chart = self._chart
        name = self._chart[0]['name']

        # generate Common files
        try:
            with open(common_template, 'r') as f:
                common_schema = f.read()
        except FileNotFoundError:
            print('File %s not found' % common_template)
            return False
        common_file = plugin_dir + '/' + appname + '/common/constants.py'
        output = common_schema.format(appname=appname, name=name, namespace=namespace)

        with open(common_file, "w") as f:
            f.write(output)

        self.create_init_file(self._app['outputCommonDir'])

        # Generate Helm files
        try:
            with open(helm_template, 'r') as f:
                helm_schema = f.read()
        except FileNotFoundError:
            print('File %s not found' % helm_template)
            return False

        for idx in range(len(chart)):
            a_chart = chart[idx]

            helm_file = plugin_dir + '/' + appname + '/helm/' + a_chart['name'].replace(" ", "_").replace("-", "_") + '.py'

            name = a_chart['name'].replace('-', ' ').title().replace(' ','')
            namespace = a_chart['namespace']

            output = helm_schema.format(appname=appname, name=name)

            with open(helm_file, "w") as f:
                f.write(output)

        self.create_init_file(self._app['outputHelmDir'])

        # Generate Kustomize files
        try:
            with open(kustomize_template, 'r') as f:
                kustomize_schema = f.read()
        except FileNotFoundError:
            print('File %s not found' % kustomize_template)
            return False
        kustomize_file = plugin_dir + '/' + appname + '/kustomize/kustomize_' + self.APP_NAME_WITH_UNDERSCORE + '.py'
        output = kustomize_schema.format(appname=appname, appnameStriped=self.APP_NAME_CAMEL_CASE)

        with open(kustomize_file, "w") as f:
            f.write(output)

        self.create_init_file(self._app['outputKustomizeDir'])

        # Generate Lifecycle files
        try:
            with open(lifecycle_template, 'r') as f:
                lifecycle_schema = f.read()
        except FileNotFoundError:
            print('File %s not found' % lifecycle_template)
            return False
        lifecycle_file = plugin_dir + '/' + appname + '/lifecycle/lifecycle_' + self.APP_NAME_WITH_UNDERSCORE + '.py'
        output = lifecycle_schema.format(appnameStriped=self.APP_NAME_CAMEL_CASE)

        with open(lifecycle_file, "w") as f:
            f.write(output)

        self.create_init_file(self._app['outputLifecycleDir'])

        # Generate setup.py
        setupPy_file = plugin_dir + '/setup.py'
        file = f"""import setuptools\n\nsetuptools.setup(\n    setup_requires=['pbr>=2.0.0'],\n    pbr=True)"""

        with open(setupPy_file, 'w') as f:
            f.write(file)

        # Generate setup.cfg file
        self.write_app_setup()


        self.create_init_file(plugin_dir)

        dir = plugin_dir + '/' + appname
        self.create_init_file(dir)

        return True


    # Subprocess that creates __init__.py file
    def create_init_file(self, path):
        init_file = path + '/__init__.py'
        open(init_file, 'w').close()


    #Subprocess that writes the setup.cfg file
    def write_app_setup(self):
        def split_and_format_value(value) -> str:
            if type(value) == str:
                return ''.join([f'\t{lin}\n' for lin in value.split('\n')])
            else:
                return ''.join([f'\t{lin}\n' for lin in value])

        def expected_order(tup: tuple) -> int:
            if tup[0] == 'name':
                return 0
            elif tup[0] == 'summary':
                return 1
            return 2

        yml_data = self.plugin_setup
        yml_data['metadata']['name'] = f'k8sapp-{self.APP_NAME}'
        yml_data['metadata']['summary'] = f'StarlingX sysinv extensions for {self.APP_NAME}'
        yml_data['metadata'] = dict(sorted(yml_data['metadata'].items(), key=expected_order))
        out = ''
        for label in yml_data:
            out += f'[{label}]\n'
            for key, val in yml_data[label].items():
                if label == 'metadata' and val is None:
                    raise ValueError(f'You should\'ve written a value for: {key}')
                elif type(val) != list:
                    out += f'{key} = {val}\n'
                else:
                    out += f'{key} =\n'
                    out += split_and_format_value(val)
            out += '\n'
        charts_data = self._chart
        plugins_names = []
        for dic in charts_data:
            plugins_names.append(dic['name'])
        out += f'[files]\npackages =\n\tk8sapp_{self.APP_NAME_WITH_UNDERSCORE}\n\n'
        out += '[global]\nsetup-hooks =\n\tpbr.hooks.setup_hook\n\n'
        out += '[entry_points]\nsystemconfig.helm_applications =\n\t' \
               f'{self.APP_NAME} = systemconfig.helm_plugins.{self.APP_NAME_WITH_UNDERSCORE}\n\n' \
               f'systemconfig.helm_plugins.{self.APP_NAME_WITH_UNDERSCORE} =\n'
        for i, plug in enumerate(plugins_names):
            out += f'\t{i+1:03d}_{plug} = k8sapp_{self.APP_NAME_WITH_UNDERSCORE}.helm.{plug.replace("-","_")}'
            out += f':{plug.replace("-", " ").title().replace(" ", "")}Helm\n'
        out += '\n'
        out += 'systemconfig.fluxcd.kustomize_ops =\n' \
               f'\t{self.APP_NAME} = k8sapp_{self.APP_NAME_WITH_UNDERSCORE}.kustomize.kustomize_' \
               f'{self.APP_NAME_WITH_UNDERSCORE}:{self.APP_NAME_CAMEL_CASE}FluxCDKustomizeOperator\n\n' \
               'systemconfig.app_lifecycle =\n' \
               f'\t{self.APP_NAME} = k8sapp_{self.APP_NAME_WITH_UNDERSCORE}.lifecycle.lifecycle_' \
               f'{self.APP_NAME_WITH_UNDERSCORE}:{self.APP_NAME_CAMEL_CASE}AppLifecycleOperator\n\n'
        out += '[bdist_wheel]\nuniversal = 1'
        with open(f'{self._app["outputPluginDir"]}/setup.cfg', 'w+') as f:
            f.write(out)


    # Sub-process of app generation
    # generate application metadata
    #
    def _gen_metadata(self, package_type, output):
        """
        gets the keys and values defined in the input yaml and writes the metadata.yaml app file.
        """

        yml_data = self.metadata
        app_name, app_version = self._app['appName'], self._app['appVersion']
        file = output + '/metadata.yaml'
        try:
            with open(file, 'w') as f:
                f.write(f'app_name: {app_name}\napp_version: {app_version}')

            if package_type == 'flux':
                with open(file, 'a') as f:
                    f.write('\nhelm_repo: stx-platform\n')
                    if yml_data is not None:
                        yaml.safe_dump(yml_data, f)
        except:
            return False

        return True


    # Sub-process of app generation
    # generate application sha256 file
    #
    def _gen_sha256(self, in_file):
        with open(in_file, 'rb') as f:
            out_sha256 = hashlib.sha256(f.read()).hexdigest()
        return out_sha256


    # Sub-process of app generation
    # generate plugin wheels
    #
    def _gen_plugin_wheels(self):
        dirplugins = self._app['outputPluginDir']

        store_cwd = os.getcwd()
        os.makedirs(dirplugins, exist_ok=True)
        os.chdir(dirplugins)

        command = [
            "python3",
            "setup.py",
            "bdist_wheel",
            "--universal",
            "-d",
            dirplugins]

        try:
            subprocess.call(command, stderr=subprocess.STDOUT)
        except:
            return False

        files = [
            f'{dirplugins}/ChangeLog',
            f'{dirplugins}/AUTHORS']
        for file in files:
            if os.path.exists(file):
                os.remove(file)

        dirs = [
            f'{dirplugins}/build/',
            f'{dirplugins}/k8sapp_{self.APP_NAME_WITH_UNDERSCORE}.egg-info/']
        for dir in dirs:
            if os.path.exists(dir):
                shutil.rmtree(dir)

        os.chdir(store_cwd)

        return True


    # Sub-process of app generation
    # generate application checksum file and tarball
    #
    def _gen_checksum_and_app_tarball(self, output):
        store_cwd = os.getcwd()
        os.chdir(output)
        # gen checksum
        # check checksum file existance
        checksum_file = 'checksum.sha256'
        if os.path.exists(checksum_file):
            os.remove(checksum_file)
        app_files = []
        try:
            for parent, dirnames, filenames in os.walk('./'):
                for filename in filenames:
                    if filename[-3:] != '.py' and filename[-4:] != '.cfg':
                        app_files.append(os.path.join(parent, filename))
        except Exception as e:
            print('Error: %s' % e)
        try:
            with open(checksum_file, 'a') as f:
                for target_file in sorted(app_files):
                    f.write(self._gen_sha256(target_file) + ' *' + target_file + '\n')
        except Exception as e:
            print('Error: %s' % e)

        app_files.append('./' + checksum_file)

        # gen application tarball
        tarname = f"{self._app['appName']}-{self._app['appVersion']}.tgz"
        t = tarfile.open(tarname, 'w:gz')
        for target_file in app_files:
            t.add(target_file)
        t.close()
        os.chdir(store_cwd)
        return tarname


    def _create_flux_dir(self, output_dir):

        if not os.path.exists(self._app['outputFluxChartDir']):
            os.makedirs(self._app['outputFluxChartDir'])
        if not os.path.exists(self._app['outputManifestDir']):
            os.makedirs(self._app['outputFluxBaseDir'])
            for idx in range(len(self._chart)):
                chart = self._chart[idx]
                self._app['outputFluxManifestDir'] = output_dir + '/FluxCD/fluxcd-manifests/' + chart['name']
                os.makedirs(self._app['outputFluxManifestDir'])


    def _create_plugins_dir(self):

        if not os.path.exists(self._app['outputPluginDir']):
            os.makedirs(self._app['outputPluginDir'])
        if not os.path.exists(self._app['outputHelmDir']):
            os.makedirs(self._app['outputHelmDir'])
        if not os.path.exists(self._app['outputCommonDir']):
            os.makedirs(self._app['outputCommonDir'])
        if not os.path.exists(self._app['outputKustomizeDir']):
            os.makedirs(self._app['outputKustomizeDir'])
        if not os.path.exists(self._app['outputLifecycleDir']):
            os.makedirs(self._app['outputLifecycleDir'])


    def _create_armada_dir(self):

        if not os.path.exists(self._app['outputArmadaDir']):
            os.makedirs(self._app['outputArmadaDir'])
        if not os.path.exists(self._app['outputArmadaChartDir']):
            os.makedirs(self._app['outputArmadaChartDir'])


    # Generate armada application, including:
    # 1. Check chart values
    # 2. Create Armada directory
    # 3. Generate helm chart tarballs
    # 4. Generate armada manifest
    # 5. Generate metadata file
    # 6. Generage checksum file
    # 7. Package Armada application
    #
    def gen_armada_app(self, output_dir, no_package, package_only):
        ret = False
        if not self._validate_app_attributes():
            print('Error: Some of the app attributes are not valid!')
            return ret

        self._app['outputDir'] = output_dir
        self._app['outputArmadaDir'] = output_dir + '/Armada'
        self._app['outputArmadaChartDir'] = output_dir + '/Armada/charts'

        # 1 - Validate input file and helm chart data
        self.check_charts()

        if not package_only:
            # 2. Generate armada directories
            self._create_armada_dir()

            # 3. Generating helm chart tarball
            for chart in self._chart:
                ret = self._gen_helm_chart_tarball(
                                    chart, self._app['outputArmadaChartDir'])
                if ret:
                    print('Helm chart %s tarball generated!' % chart['name'])
                    print('')
                else:
                    print('Generating tarball for helm chart: %s error!' % chart['name'])
                    return ret

            # 4. Generating armada manifest
            ret = self._gen_armada_manifest()
            if ret:
                print('Armada manifest generated!')
            else:
                print('Armada manifest generation failed!')
                return ret

            # 5. Generating metadata file
            ret = self._gen_metadata('armada', self._app['outputArmadaDir'])
            if ret:
                print('Metadata generated!')
            else:
                print('Armada Metadata generation failed!')
                return ret

        if not no_package:
            # 6&7. Generating checksum file and tarball
            ret = self._gen_checksum_and_app_tarball(self._app['outputArmadaDir'])
            if ret:
                print('Checksum generated!')
                print('Armada App tarball generated at %s/%s' % (self._app['outputArmadaDir'], ret))
                print('')
            else:
                print('Checksum and App tarball generation failed!')
                return ret

            return ret


    # Function to call all process fot the creation of the FluxCd app tarball
    # 1 - Validate input file and helm chart data
    # 2 - Create application directories
    # 3 - Generate FluxCD Manifests
    # 4 - Generate application plugins
    # 5 - Generate application metadata
    # 6 - Package helm-charts
    # 7 - Package plugins in wheel format
    # 8 - Generate checksum
    # 9 - Package entire application
    def gen_flux_app(self, output_dir, no_package, package_only):

        self._app['outputDir'] = output_dir
        self._app['outputFluxCDDir'] = output_dir + '/FluxCD'
        self._app['outputFluxChartDir'] = output_dir + '/FluxCD/charts/'
        self._app['outputManifestDir'] = output_dir + '/FluxCD/fluxcd-manifests/'
        self._app['outputFluxBaseDir'] = output_dir + '/FluxCD/fluxcd-manifests/base/'

        self._app['outputPluginDir'] = output_dir + '/FluxCD/plugins'
        self._app['outputHelmDir'] = output_dir + '/FluxCD/plugins/k8sapp_' + self._app['appName'].replace(" ", "_").replace("-", "_") + '/helm/'
        self._app['outputCommonDir'] = output_dir + '/FluxCD/plugins/k8sapp_' + self._app['appName'].replace(" ", "_").replace("-", "_") + '/common/'
        self._app['outputKustomizeDir'] = output_dir + '/FluxCD/plugins/k8sapp_' + self._app['appName'].replace(" ", "_").replace("-", "_") + '/kustomize/'
        self._app['outputLifecycleDir'] = output_dir + '/FluxCD/plugins/k8sapp_' + self._app['appName'].replace(" ", "_").replace("-", "_") + '/lifecycle/'

        # 1 - Validate input file and helm chart data
        self.check_charts()

        if not package_only:

            # 2 - Create application directories
            self._create_flux_dir(output_dir)
            self._create_plugins_dir()

            # 3 - Generate FluxCD Manifests
            ret = self._gen_fluxcd_manifest()
            if ret:
                print('FluxCD manifest generated!')
            else:
                print('FluxCCD manifest generation failed!')
                return ret

            # 4 - Generate application plugins
            ret = self._gen_plugins()
            if ret:
                print('FluxCD Plugins generated!')
            else:
                print('FluxCD Plugins generation failed!')
                return ret

            # 5 - Generate application metadata
            ret = self._gen_metadata('flux', self._app['outputFluxCDDir'])
            if ret:
                print('FluxCD Metadata generated!')
            else:
                print('FluxCD Metadata generation failed!')
                return ret

        if not no_package:

            # 6 - Package helm-charts
            for chart in self._chart:
                ret = self._gen_helm_chart_tarball(
                                        chart, self._app['outputFluxChartDir'])
                if ret:
                    print('Helm chart %s tarball generated!' % chart['name'])
                    print('')
                else:
                    print('Generating tarball for helm chart: %s error!' % chart['name'])
                    return ret

            # 7 - Package plugins in wheel format
            ret = self._gen_plugin_wheels()
            if ret:
                print('Plugin wheels generated!')
            else:
                print('Plugin wheels generation failed!')
                return ret

            # 8 - Generate checksum &&
            # 9 - Package entire application
            ret = self._gen_checksum_and_app_tarball(self._app['outputFluxCDDir'])
            if ret:
                print('Checksum generated!')
                print('FluxCD App tarball generated at %s/%s' % (self._app['outputDir'], ret))
                print('')
            else:
                print('Checksum and App tarball generation failed!')
                return ret


    # For debug
    def print_app_data(self):
        print(self._app)
        print(self._manifest)
        print(self._chartgroup)
        print(self._chart)


def parse_yaml(yaml_in):
    yaml_data=''
    try:
        with open(yaml_in) as f:
            yaml_data = yaml.safe_load(f)
    except FileNotFoundError:
        print('Error: %s no found' % yaml_in )
    except Exception as e:
        print('Error: Invalid yaml file')
    return yaml_data


def check_manifest(manifest_data):
    # TODO: check more mandatory key/values in manifest yaml

    # check app values
    if 'appName' not in manifest_data['appManifestFile-config']:
        print('Error: \'appName\' is missing.')
        return False

    if 'namespace' not in manifest_data['appManifestFile-config']:
        print('Error: \'namespace\' is missing.')
        return False

    if 'appVersion' not in manifest_data['appManifestFile-config']:
        print('Error: \'appVersion\' is missing.')
        return False

    # # check manifest values
    # if 'manifest' not in manifest_data['appManifestFile-config']:
    #     print('Error: \'manifest\'is missing.')
    #     return False

    # if 'releasePrefix' not in manifest_data['manifest']:
    #     print('Error: Manifest attribute \'releasePrefix\' is missing.')
    #     return False

    # check chartGroup values
    if 'chartGroup' not in manifest_data['appManifestFile-config']:
        print('Error: \'chartGroup\' is missing.')
        return False

    # check chart values
    if 'chart' not in manifest_data['appManifestFile-config']:
        print('Error: \'chart\' is missing.')
        return False

    for chart in manifest_data['appManifestFile-config']['chart']:
        # check chart name
        if 'name' not in chart:
            print('Error: Chart attribute \'name\' is missing.')
            return False

        # check chart version
        if 'version' not in chart:
            print('Error: Chart attribute \'version\' is missing.')
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


def generate_app(file_in, out_folder, package_type, overwrite, no_package, package_only):
    global TEMP_APP_DIR
    app_data = parse_yaml(file_in)
    if not app_data:
        print('Parse yaml error')
        return
    if not check_manifest(app_data):
        print('Application manifest is not valid')
        return
    app = Application(app_data)
    TEMP_APP_DIR = TEMP_USER_DIR + app.get_app_name() + '/'
    app_out = out_folder + '/' + app.get_app_name()

    if not os.path.exists(app_out):
        os.makedirs(app_out)
    elif overwrite:
        shutil.rmtree(app_out)
    elif package_only:
        pass
    else:
        print('Output folder %s exists, please remove it or use --overwrite.' % app_out)
        sys.exit()

    if package_type == 'armada' or package_type == 'both':
        app.gen_armada_app(app_out, no_package, package_only)

    if package_type == 'flux' or package_type == 'both':
        app.gen_flux_app(app_out, no_package, package_only)


def main(argv):
    input_file = ''
    output_folder = '.'
    package_type = ''
    overwrite = False
    package_only = False
    no_package = False
    try:
        options, args = getopt.getopt(argv, 'hi:o:t:', \
                ['help', 'input=', 'output=', 'type=', 'overwrite', 'no-package', 'package-only'])
    except getopt.GetoptError:
        print('Error: Invalid argument')
        sys.exit(1)
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
            print('    -t, --type package       select Armada,Flux or Both packaging')
            print('        --overwrite          overwrite the output dir')
            print('        --no-package         does not create app tarball')
            print('        --package-only       only creates tarball from dir')
            print('    -h, --help               this help')
        if option in ('--overwrite'):
            overwrite = True
        if option in ('-i', '--input'):
            input_file = value
        if option in ('-o', '--output'):
            output_folder = value
        if option in ('-t', '--type'):
            package_type = value.lower()
        if option in ('--no-package'):
            no_package = True
        if option in ('--package-only'):
            package_only = True

    if not package_type:
        print('Error: Select type of packaging (armada/flux/both)')
        sys.exit(1)
    if not os.path.isfile(os.path.abspath(input_file)):
        print('Error: input file not found')
        sys.exit(1)
    if input_file:
        generate_app(os.path.abspath(input_file), os.path.abspath(output_folder), package_type, overwrite, no_package, package_only)


if __name__ == '__main__':
    main(sys.argv[1:])