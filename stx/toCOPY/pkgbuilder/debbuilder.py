# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Copyright (C) 2021-2022 Wind River Systems,Inc
#
import os
import schrootspool
import shutil
import signal
import subprocess

BUILD_ROOT = '/localdisk/loadbuild/'
STORE_ROOT = '/localdisk/pkgbuilder'
BUILD_ENGINE = 'sbuild'
STX_LOCALRC = '/usr/local/bin/stx/stx-localrc'
SBUILD_CONF = '/etc/sbuild/sbuild.conf'
ENVIRON_VARS = ['OSTREE_OSNAME', 'CENGNURL', 'DEBIAN_DISTRIBUTION', 'DEBIAN_VERSION']
REPO_BUILD = 'deb-local-build'


def check_request(request_form, needed_form):
    response = {}
    if not all(t in request_form for t in needed_form):
        response['status'] = 'fail'
        msg = ','.join(needed_form)
        response['msg'] = 'All required parameters are: ' + msg
    return response


class Debbuilder:
    """
    Debbuilder querys/creates/saves/restores the schroot for sbuild
    The default name of schroot is '<Debian DIST>-amd64-<USER>'
    it takes USER as suffix, per user per schroot and the multiple
    build instances launched on the same schroot will be queued.

    Debuilder starts/stops the build instances for USER, it also
    cleans the scene and handles the USER's abort/terminate commands
    to build instance. The whole build log will be displayed
    on front end console including the detailed build stats.
    For these key result status like success,fail or give-back,
    please refer to the document of Debian sbuild.
    Debbuiler allows to customize the build configuration for sbuild
    engine by updating debbuilder.conf

    Debuilder is created by python3 application 'app.py' which runs in
    python Flask server to provide Restful APIs to offload the build tasks.
    """
    def __init__(self, mode, dist, arch, logger):
        self.logger = logger
        self.chroots_pool = schrootspool.SchrootsPool(logger)
        self.chroots_state = {}
        self.chroot_processes = {}
        self.sbuild_processes = {}
        self.ctlog = None
        self.attrs = {}
        self.attrs['state'] = 'idle'
        self.attrs['mode'] = mode
        self.attrs['dist'] = dist
        self.attrs['arch'] = arch
        self.set_extra_repos()
        self.set_environ_vars()
        os.system('/opt/setup.sh')

    def get_state(self):
        response = {}
        response['status'] = 'success'
        response['msg'] = self.attrs['state']
        return response

    def set_environ_vars(self):
        if not os.path.exists(STX_LOCALRC):
            self.logger.error("%s does not exist", STX_LOCALRC)
            return
        self.logger.debug("%s does exist", STX_LOCALRC)

        for var in ENVIRON_VARS:
            self.logger.debug("Fetching %s from stx-localrc", var)
            cmd = "grep '^export *%s=.*' %s | cut -d \\= -f 2" % (var, STX_LOCALRC)
            self.logger.debug('The fetch command is %s', cmd)
            try:
                outs = subprocess.check_output(cmd, shell=True).decode()
            except Exception as e:
                self.logger.error(str(e))
                self.logger.error("Failed to fetch %s from %s", var, STX_LOCALRC)
                break
            else:
                if not outs:
                    self.logger.error("Got null when fetch %s from %s", var, STX_LOCALRC)
                    break
                value = outs.strip().split("\n")[0].strip('"')
                self.logger.debug("Got value %s for %s", value, var)
                replace_cmd = "sed -i -e 's#@%s@#%s#g' %s" % (var, value, SBUILD_CONF)
                self.logger.debug('The replacing command is %s', replace_cmd)
                ret = os.system(replace_cmd)
                self.logger.debug('The return value of macro replacing is %d', ret)

    def set_extra_repos(self):
        repomgr_url = None
        if not os.path.exists(STX_LOCALRC):
            self.logger.warning('stx-localrc does not exist')
            return

        env_list = []
        with open(STX_LOCALRC) as f:
            env_list = list(f)
        for item in env_list:
            if item.startswith('export '):
                envvar = item.replace('export ', '').split('=')
                if envvar and len(envvar) >= 2 and envvar[0].strip() == 'REPOMGR_DEPLOY_URL':
                    repomgr_url = envvar[1].strip()
                    break

        if repomgr_url:
            url_parts = repomgr_url.split(':')
            repo_origin = url_parts[1][2:]
            self.logger.debug('The origin of local repositories is %s', repo_origin)
            try:
                with open(SBUILD_CONF, '+r') as f:
                    sconf = f.read()
                    sconf = sconf.replace('http://stx-stx-repomgr:80/', repomgr_url)
                    sconf = sconf.replace('stx-stx-repomgr', repo_origin)
                    f.seek(0, 0)
                    f.write(sconf)
                    f.truncate()
            except IOError as e:
                self.logger.error(str(e))

    def has_chroot(self, chroot):
        chroots = os.popen('schroot -l')
        target_line = "chroot:" + chroot
        for line in chroots:
            if line.strip() == target_line:
                self.logger.info("chroot %s exists" % chroot)
                return True
        return False

    def add_chroot(self, request_form):
        response = check_request(request_form, ['user', 'project'])
        if response:
            return response
        user = request_form['user']
        project = request_form['project']

        chroot = '-'.join([self.attrs['dist'], self.attrs['arch'], user])
        if self.has_chroot(chroot):
            self.logger.warn("chroot %s already exists" % chroot)
            response['status'] = 'exists'
            response['msg'] = 'chroot exists'
            return response

        user_dir = os.path.join(STORE_ROOT, user, project)
        user_chroots_dir = os.path.join(user_dir, 'chroots')
        os.makedirs(user_chroots_dir, exist_ok=True)
        self.logger.debug("Directory of chroots: %s" % user_chroots_dir)

        user_chroot = os.path.join(user_chroots_dir, chroot)
        self.logger.debug("Found disused chroot %s, remove it" % user_chroot)
        try:
            shutil.rmtree(user_chroot, ignore_errors=True)
        except Exception as e:
            self.logger.error(str(e))
            # New chroot will be created below, we just reports this
            self.logger.warning("Failed to remove %s" % user_chroot)

        try:
            self.ctlog = open(os.path.join(user_dir, 'chroot.log'), 'w')
        except IOError as e:
            self.logger.error(str(e))
            response['status'] = 'fail'
            response['msg'] = 'fail to create log file'
        else:
            chroot_suffix = '--chroot-suffix=-' + user
            chroot_cmd = ' '.join(['sbuild-createchroot', chroot_suffix,
                                   '--include=apt-transport-https,ca-certificates,eatmydata',
                                   '--command-prefix=eatmydata',
                                   self.attrs['dist'], user_chroot])
            if 'mirror' in request_form:
                chroot_cmd = ' '.join([chroot_cmd, request_form['mirror']])
            self.logger.debug("Command to creat chroot:%s" % chroot_cmd)

            p = subprocess.Popen(chroot_cmd, shell=True, stdout=self.ctlog,
                                 stderr=self.ctlog)
            self.chroot_processes.setdefault(user, []).append(p)

            response['status'] = 'creating'
            response['msg'] = 'Chroot creating, please check %s/chroot.log' % user_dir
        return response

    def save_chroots_config(self, user, project):
        self.logger.debug("Save the config file of chroot to persistent store")
        user_conf_store_dir = os.path.join(STORE_ROOT, user, project, 'chroots/chroot.d')
        system_conf_dir = '/etc/schroot/chroot.d'
        try:
            shutil.rmtree(user_conf_store_dir, ignore_errors=True)
            shutil.copytree(system_conf_dir, user_conf_store_dir)
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error("Failed to save the config file of chroot")
        else:
            self.logger.info("Successfully saved the config file of chroot")

    def is_parent_config(self, parent_chroot_name, target_config):
        # The name of config file for the parent schroot has two parts:
        # chroot_name + '-' + random number
        # e.g. bullseye-amd64-user-yWJpyF
        # The name of config file for the cloned schroot has three parts:
        # chroot_name + '-' + random number + '-' + sequence
        # e.g. bullseye-amd64-user-yWJpyF-1
        conf_file_suffix = target_config.replace(parent_chroot_name + '-', '')
        if '-' not in conf_file_suffix:
            return True
        else:
            return False

    def clone_chroot(self, request_form):
        """
        Clone and configure multiple instances of chroots
        the cloned chroot takes the sequence as suffix
        The chroot index file in /etc/schroot/chroot.d also
        need to be cloned to make the chroot can be managed by schroot
        """
        response = check_request(request_form, ['user', 'project', 'instances'])
        if response:
            return response

        user = request_form['user']
        project = request_form['project']
        required_instances = int(request_form['instances'])
        chroot_sequence = 1

        # Try to find the parent chroot
        user_dir = os.path.join(STORE_ROOT, user, project)
        # e.g bullseye-amd64-user
        parent_chroot_name = '-'.join([self.attrs['dist'], self.attrs['arch'], user])
        # e.g /localdisk/pkgbuilder/user/stx/chroots/bullseye-amd64-user
        parent_chroot_path = os.path.join(user_dir, 'chroots', parent_chroot_name)
        if not os.path.exists(parent_chroot_path):
            self.logger.error("Failed to find the parent chroot %s", parent_chroot_path)
            response['status'] = 'fail'
            response['msg'] = 'The parent chroot %s does not exist' % parent_chroot_path
            return response

        self.logger.debug("The parent chroot %s exists, start to clone chroot with it", parent_chroot_path)
        for instance in range(required_instances):
            cloned_chroot_name = parent_chroot_name + '-' + str(chroot_sequence)
            cloned_chroot_path = parent_chroot_path + '-' + str(chroot_sequence)
            if not os.path.exists(cloned_chroot_path):
                try:
                    self.logger.info("Cloning chroot %s from the parent %s", cloned_chroot_path, parent_chroot_path)
                    shell_cmd = 'rm -rf %s.tmp' % cloned_chroot_path
                    subprocess.check_call(shell_cmd, shell=True)
                    shell_cmd = 'cp -ar %s %s.tmp' % (parent_chroot_path, cloned_chroot_path)
                    subprocess.check_call(shell_cmd, shell=True)
                    shell_cmd = 'mv %s.tmp %s' % (cloned_chroot_path, cloned_chroot_path)
                    subprocess.check_call(shell_cmd, shell=True)
                except Exception as e:
                    self.logger.error(str(e))
                    response['status'] = 'fail'
                    if not response['msg']:
                        response['msg'] = 'The failed chroot instances:'
                    response['msg'].append(str(instance) + ' ')
                    continue
                else:
                    self.logger.info("Successfully cloned chroot %s", cloned_chroot_path)

            self.logger.info("Target cloned chroot %s is ready, updated config", cloned_chroot_path)
            # For the cloned chroot, the schroot config file also need to be created
            # Try to find the config file of parent schroot and take it as template
            # e.g. it is /etc/chroots/chroot.d/bullseye-amd64-user-yWJpyF
            schroot_conf_dir = os.listdir(os.path.join('/etc/schroot/chroot.d'))
            for conf in schroot_conf_dir:
                if self.is_parent_config(parent_chroot_name, conf):
                    parent_conf_name = conf
                    parent_conf_path = os.path.join('/etc/schroot/chroot.d', parent_conf_name)
                    self.logger.info("Found the config of the parent chroot: %s", parent_conf_name)
                    new_conf_name = parent_conf_name + '-' + str(chroot_sequence)
                    new_conf_path = os.path.join('/etc/schroot/chroot.d', new_conf_name)
                    if os.path.exists(new_conf_path):
                        self.logger.debug("Cloned chroot config %s already exists", new_conf_path)
                        chroot_sequence = chroot_sequence + 1
                        continue
                    try:
                        self.logger.debug("Creating config file %s from %s", new_conf_name, parent_conf_name)
                        shutil.copyfile(parent_conf_path, new_conf_path)
                        self.logger.debug("Successfully cloned chroot config, try to update %s", new_conf_name)
                        shell_cmd = 'sed -i \'s/%s/%s/g\' %s' % (parent_chroot_name, cloned_chroot_name, new_conf_path)
                        subprocess.check_call(shell_cmd, shell=True)
                    except Exception as e:
                        self.logger.error(str(e))
                        self.logger.error("Failed to clone and update config file %s", new_conf_path)
                        break
                    else:
                        self.logger.debug("Successfully cloned and updated chroot's config %s", new_conf_path)
                        chroot_sequence = chroot_sequence + 1
                        break

        # Save the above chroot config files to the external persistent storage
        self.save_chroots_config(user, project)
        if chroot_sequence == required_instances + 1:
            self.logger.info("All required %s chroots are created", str(required_instances))
            response['status'] = 'success'
            response['msg'] = 'All required chroots are created'
        else:
            self.logger.info("Not all required %d chroots created, only %d created ok",
                             required_instances, chroot_sequence - 1)
            response['status'] = 'fail'
            response['msg'] = 'Available chroots=%d' % (chroot_sequence - 1)
        # Reload all chroots into the chroots pool
        self.chroots_pool.load()
        return response

    def load_chroot(self, request_form):
        response = check_request(request_form, ['user', 'project'])
        if response:
            return response
        user = request_form['user']
        project = request_form['project']

        user_dir = os.path.join(STORE_ROOT, user, project)
        user_chroots = os.path.join(user_dir, 'chroots/chroot.d')
        if not os.path.exists(user_chroots):
            self.logger.warn("Failed to find directory of chroots %s" % user_chroots)
            response['status'] = 'success'
            response['msg'] = ' '.join(['External chroot', user_chroots,
                                        'does not exist'])
        else:
            target_dir = '/etc/schroot/chroot.d'
            try:
                shutil.rmtree(target_dir, ignore_errors=True)
                shutil.copytree(user_chroots, target_dir)
            except Exception as e:
                self.logger.error(str(e))
                self.logger.error("Failed to load external config file of chroot")
                response['status'] = 'fail'
                response['msg'] = 'Failed to load external config file of chroot'
            else:
                response['status'] = 'success'
                response['msg'] = 'Load external chroot config ok'

        self.chroots_pool.load()
        return response

    def save_chroot(self, request_form):
        response = check_request(request_form, ['user', 'project'])
        if response:
            return response
        user = request_form['user']
        project = request_form['project']

        user_dir = os.path.join(STORE_ROOT, user, project)
        user_chroots = os.path.join(user_dir, 'chroots/chroot.d')
        try:
            shutil.rmtree(user_chroots, ignore_errors=True)
        except Exception as e:
            self.logger.error(str(e))
            # Just report this but not quit
            self.logger.error("Failed to remove %s", user_chroots)

        sys_schroots = '/etc/schroot/chroot.d'
        try:
            shutil.copytree(sys_schroots, user_chroots)
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error("Failed to save %s with %s", sys_schroots, user_chroots)
            response['status'] = 'fail'
            response['msg'] = 'Failed to save the config files of chroots to persistent storage'
        else:
            response['status'] = 'success'
            response['msg'] = 'Successfully saved the config files of chroots to persistent storage'
            self.logger.debug("Successfully saved the config files of chroots")
        return response

    def refresh_chroots(self, request_form):
        '''
        Refresh all chroots with the backup 'clean' chroot
        '''
        response = check_request(request_form, ['user', 'project'])
        if response:
            return response
        user = request_form['user']
        project = request_form['project']

        dst_chroots = self.chroots_pool.get_idle()
        if not dst_chroots:
            self.logger.warning('Some chroots are busy')
        self.logger.warning('Force to refresh chroots')
        self.stop_task(request_form)
        self.chroots_pool.release_all()

        # Stop all schroot sessions
        subprocess.call('schroot -a -e', shell=True)

        backup_chroot = None
        user_dir = os.path.join(STORE_ROOT, user, project)
        user_chroots_dir = os.path.join(user_dir, 'chroots')
        for chroot in dst_chroots:
            # e.g. the chroot name is 'chroot:bullseye-amd64-<user>-1'
            self.logger.debug('The current chroot is %s', chroot)
            chroot = chroot.split(':')[1]
            self.logger.debug('The name of chroot: %s', chroot)
            if not backup_chroot:
                backup_chroot = chroot[0:chroot.rindex('-')]
                self.logger.debug('The name of backup chroot: %s', backup_chroot)
                if not os.path.exists(os.path.join(user_chroots_dir, backup_chroot)):
                    self.logger.error("The backup chroot %s does not exist", backup_chroot)
                    response['status'] = 'fail'
                    response['msg'] = 'The backup chroot does not exist'
                    return response
            if backup_chroot == chroot:
                continue

            backup_chroot_path = os.path.join(user_chroots_dir, backup_chroot)
            chroot_path = os.path.join(user_chroots_dir, chroot)
            try:
                cp_cmd = 'cp -ra %s %s' % (backup_chroot_path, chroot_path + '.tmp')
                subprocess.check_call(cp_cmd, shell=True)
                rm_cmd = 'rm -rf ' + chroot_path
                subprocess.check_call(rm_cmd, shell=True)
                mv_cmd = 'mv -f %s %s' % (chroot_path + '.tmp', chroot_path)
                subprocess.check_call(mv_cmd, shell=True)
            except subprocess.CalledProcessError as e:
                self.logger.error(str(e))
                self.logger.error('Failed to refresh the chroot %s', chroot)
                response['status'] = 'fail'
                response['msg'] = 'Error during refreshing the chroots'
                return response
            else:
                self.logger.info('Successfully refreshed the chroot %s', chroot)

        self.logger.info('Successfully refreshed all idle chroots')
        response['status'] = 'success'
        response['msg'] = 'All idle chroots are refreshed'
        return response

    def assemble_extra_repo(self, snapshot_idx, repo=""):
        repomgr_url = None
        if not os.path.exists(STX_LOCALRC):
            self.logger.warning('stx-localrc does not exist')
            return None

        env_list = []
        with open(STX_LOCALRC) as f:
            env_list = list(f)
        for item in env_list:
            if item.startswith('export '):
                envvar = item.replace('export ', '').split('=')
                if envvar and len(envvar) >= 2 and envvar[0].strip() == 'REPOMGR_DEPLOY_URL':
                    repomgr_url = envvar[1].strip()
                    break

        if repomgr_url:
            if repo:
                repomgr_url = f"deb [trusted=yes] {repomgr_url}{repo} {self.attrs['dist']} main"
            else:
                repomgr_url = ' '.join(['deb [trusted=yes]', repomgr_url + REPO_BUILD + '-' + snapshot_idx, self.attrs['dist'], 'main'])
        self.logger.warning("The extra repository URL is %s", repomgr_url)
        return repomgr_url

    def add_task(self, request_form):
        response = check_request(request_form,
                                 ['user', 'project', 'type', 'dsc', 'snapshot_idx', 'layer'])
        if response:
            return response
        user = request_form['user']
        snapshot_index = request_form['snapshot_idx']
        layer = request_form['layer']

        chroot = '-'.join([self.attrs['dist'], self.attrs['arch'], user])
        if not self.has_chroot(chroot):
            self.logger.critical("The basic chroot %s does not exist" % chroot)
            response['status'] = 'fail'
            response['msg'] = ' '.join(['chroot', chroot, 'does not exist'])
            return response

        # for example: dsc = '/path/to/tsconfig_1.0-1.stx.3.dsc'
        dsc = request_form['dsc']
        if not os.path.isfile(dsc):
            self.logger.error("%s does not exist" % dsc)
            response['status'] = 'fail'
            response['msg'] = dsc + ' does not exist'
            return response

        bcommand = ' '.join([BUILD_ENGINE, '-d', self.attrs['dist']])
        dsc_build_dir = os.path.dirname(dsc)
        chroot = self.chroots_pool.apply()
        self.chroots_pool.show()
        if not chroot:
            self.logger.error("There is not idle chroot for %s", dsc)
            response['status'] = 'fail'
            response['msg'] = 'There is not idle chroot for ' + dsc
            return response
        self.chroots_state[dsc] = chroot
        self.logger.info("Chroot %s is ready for %s", chroot, dsc)

        if 'jobs' in request_form:
            jobs = '-j' + request_form['jobs']
        else:
            jobs = '-j4'

        repo_url = self.assemble_extra_repo(snapshot_index)
        extra_repo = '--extra-repository=\'%s\'' % (repo_url)

        layer_url = self.assemble_extra_repo(
            snapshot_index, repo=f"deb-local-binary-{layer}"
        )
        layer_repo = '--extra-repository=\'%s\'' % (layer_url)

        bcommand = ' '.join([bcommand, jobs, '-c', chroot, layer_repo, extra_repo,
                            '--build-dir', dsc_build_dir, dsc])
        self.logger.debug("Build command: %s" % (bcommand))
        self.attrs['state'] = 'works'

        # verify if tests need to be executed
        if request_form['run_tests'] == 'True':
            p = subprocess.Popen(bcommand, shell=True, preexec_fn=os.setsid)
        else:
            self.logger.debug("No tests needed, setting DEB_BUILD_OPTIONS=nocheck")
            p = subprocess.Popen(bcommand, shell=True, env={**os.environ, 'DEB_BUILD_OPTIONS': 'nocheck'}, preexec_fn=os.setsid)
        self.sbuild_processes.setdefault(user, {}).setdefault(dsc, p)

        response['status'] = 'success'
        response['msg'] = chroot
        return response

    def clean_stamp(self, request_form):
        response = check_request(request_form, ['user', 'project', 'type'])
        if response:
            return response

        user = request_form['user']
        project = request_form['project']
        build_type = request_form['type']
        stamp_dir = os.path.join(STORE_ROOT, user, project, build_type, 'stamp')
        try:
            shutil.rmtree(stamp_dir, ignore_errors=True)
        except Exception as e:
            self.logger.error(str(e))
            # New chroot will be created below, we just reports this
            self.logger.warning("Failed to remove %s" % stamp_dir)
            response['status'] = 'fail'
            response['msg'] = 'Failed to remove stamp directory'
        else:
            self.logger.info("The stamp directory %s has been cleaned", stamp_dir)
            response['status'] = 'success'
            response['msg'] = 'Successfully cleaned the stamp directory'
        return response

    def kill_task(self, request_form):
        response = check_request(request_form, ['user', 'owner'])
        if response:
            return response
        user = request_form['user']
        owner = request_form['owner']

        if 'dsc' in request_form:
            done_dsc = request_form['dsc']
            if done_dsc:
                self.chroots_pool.release(self.chroots_state[done_dsc])
                self.logger.debug('The chroot %s for %s is released', self.chroots_state[done_dsc], done_dsc)
                for dsckey in self.sbuild_processes[user].keys():
                    if dsckey == done_dsc:
                        self.logger.debug("Terminating package build process for %s", dsckey)
                        p = self.sbuild_processes[user][dsckey]
                        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                        self.logger.debug("Package build process terminated for %s", dsckey)
                        del self.sbuild_processes[user][dsckey]
                        break
        else:
            if owner in ['sbuild', 'all']:
                self.chroots_pool.show()
                if self.sbuild_processes and self.sbuild_processes[user]:
                    for dsckey in self.sbuild_processes[user].keys():
                        self.logger.debug("Terminating package build process for %s", dsckey)
                        p = self.sbuild_processes[user][dsckey]
                        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                        self.logger.debug("chroot:%s ---> %s", self.chroots_state[dsckey], dsckey)
                        self.chroots_pool.release(self.chroots_state[dsckey])
                        self.logger.debug("Package build process terminated")
                    del self.sbuild_processes[user]

        if owner in ['chroot', 'all']:
            if self.ctlog:
                self.ctlog.close()
            if self.chroot_processes and self.chroot_processes[user]:
                for p in self.chroot_processes[user]:
                    self.logger.debug("Terminating chroot process")
                    p.terminate()
                    p.wait()
                    self.logger.debug("Chroot process terminated")
                del self.chroot_processes[user]

        self.logger.info("Current status of chroots:")
        self.chroots_pool.show()

        response['status'] = 'success'
        response['msg'] = 'killed all build related tasks'
        return response

    def stop_task(self, request_form):
        req = {}
        response = check_request(request_form, ['user'])
        if response:
            return response
        user = request_form['user']

        # check whether the need schroot exists
        chroot = '-'.join([self.attrs['dist'], self.attrs['arch'], user])
        if not self.has_chroot(chroot):
            self.logger.critical("No required chroot %s" % chroot)

        req['user'] = user
        req['owner'] = 'all'
        self.kill_task(req)
        os.system('sbuild_abort')

        response['status'] = 'success'
        response['msg'] = 'Stop current build tasks'
        self.attrs['state'] = 'idle'
        return response
