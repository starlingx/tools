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
import fs
import os
import psutil
import schrootspool
import shutil
import signal
import subprocess
import utils

BUILD_ROOT = '/localdisk/loadbuild/'
STORE_ROOT = '/localdisk/pkgbuilder'
BUILD_ENGINE = 'sbuild'
STX_LOCALRC = '/usr/local/bin/stx/stx-localrc'
SBUILD_CONF = '/etc/sbuild/sbuild.conf'
ENVIRON_VARS = ['OSTREE_OSNAME', 'OS_MIRROR_URL', 'OS_MIRROR_DIST_PATH',
                'DEBIAN_DISTRIBUTION', 'DEBIAN_VERSION']
REPO_BUILD = 'deb-local-build'


def check_request(request_form, needed_form):
    response = {}
    if not all(t in request_form for t in needed_form):
        response['status'] = 'fail'
        msg = ','.join(needed_form)
        response['msg'] = 'All required parameters are: ' + msg
    return response


class Debbuilder(object):
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
        self.attrs['unique_id'] = None
        self.set_extra_repos()
        self.set_environ_vars()
        os.system('/opt/setup.sh')
        self.schroot_config_dir = '/etc/schroot/chroot.d'

    def get_parent_chroot_name(self, user):
        return '-'.join([self.attrs['dist'], self.attrs['arch'], user])

    def get_cloned_chroot_name(self, user, chroot_sequence):
        return '-'.join([self.get_parent_chroot_name(user), str(chroot_sequence)])

    def get_user_dir(self, user, project):
        return os.path.join(STORE_ROOT, user, project)

    def get_user_schroot_config_dir(self, user, project):
        user_dir = self.get_user_dir(user, project)
        return os.path.join(user_dir, 'chroots/chroot.d')

    def get_user_chroots_dir(self, user, project):
        user_dir = self.get_user_dir(user, project)
        return os.path.join(user_dir, 'chroots')

    def get_user_schroot_log_path(self, user, project):
        user_dir = self.get_user_dir(user, project)
        return os.path.join(user_dir, 'chroot.log')

    def get_parent_chroot_dir(self, user, project):
        user_chroots_dir = self.get_user_chroots_dir(user, project)
        parent_chroot_name = self.get_parent_chroot_name(user)
        return os.path.join(user_chroots_dir, parent_chroot_name)

    def get_cloned_chroot_dir(self, user, project, chroot_sequence):
        user_chroots_dir = self.get_user_chroots_dir(user, project)
        cloned_chroot_name = self.get_cloned_chroot_name(user, chroot_sequence)
        return os.path.join(user_chroots_dir, cloned_chroot_name)

    def get_user_stamp_dir(self, user, project, build_type):
        user_dir = self.get_user_dir(user, project)
        return os.path.join(user_dir, build_type, 'stamp')

    def compose_chroot_name(self, user, index=None):
        chroot_name = '-'.join([self.attrs['dist'], self.attrs['arch'], user])
        if index is not None:
            chroot_name = '-'.join([chroot_name, str(index)])
        return chroot_name

    def decompose_chroot_name(self, chroot_name, user):
        self.logger.debug("Starting decompose_chroot_name...")
        self.logger.debug("chroot_name: %s", chroot_name)
        components = {}
        # the username may contain '-' so we remove it before splitting
        value_to_remove = f'-{user}'
        parts = chroot_name.replace(value_to_remove, '').split('-')
        self.logger.debug("parts: %s", parts)
        if len(parts) < 2:
            self.logger.debug("components: %s", components)
            return components
        components['dist'] = parts[0]
        components['arch'] = parts[1]
        components['user'] = user
        if len(parts) >= 3:
            components['index'] = parts[2]
        self.logger.debug("components: %s", components)
        return components

    def index_from_chroot_name(self, chroot_name, user):
        components = self.decompose_chroot_name(chroot_name, user)
        if 'index' in components:
            return int(components['index'])
        return None

    def get_schroot_conf_path(self, user, index=None):
        parent_chroot_name = self.get_parent_chroot_name(user)
        conf_file_path = schrootspool.get_schroot_conf_path(parent_chroot_name)
        if conf_file_path is None:
            return None
        if index is not None:
            conf_file_path = '-'.join([conf_file_path, str(index)])
        return conf_file_path

    def compose_schroot_name(self, user, index=None):
        if self.attrs['unique_id'] is None:
            self.logger.error("compose_schroot_name: attribute 'unique_id' has noty been set.")
            return None
        schroot_name = '-'.join([self.attrs['dist'], self.attrs['arch'], self.attrs['unique_id'], user])
        if index is not None:
            schroot_name = '-'.join([schroot_name, str(index)])
        return schroot_name

    def decompose_schroot_config_name(self, schroot_config_name, user):
        self.logger.debug("Starting decompose_schroot_config_name...")
        self.logger.debug("schroot_config_name: %s", schroot_config_name)
        components = {}
        # the username may contain '-' so we remove it before splitting
        value_to_remove = f'-{user}'
        parts = schroot_config_name.replace(value_to_remove, '').split('-')
        self.logger.debug("parts: %s", parts)
        if len(parts) < 3:
            self.logger.debug("components: %s", components)
            return components
        components['dist'] = parts[0]
        components['arch'] = parts[1]
        components['user'] = user
        components['unique_id'] = parts[2]
        if len(parts) >= 4:
            components['index'] = parts[3]
        self.logger.debug("components: %s", components)
        return components

    def index_from_schroot_config_name(self, schroot_config_name, user):
        components = self.decompose_schroot_config_name(schroot_config_name, user)
        if 'index' in components:
            return int(components['index'])
        return None

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
        chroots = os.popen('schroot --list')
        target_line = "chroot:" + chroot
        for line in chroots:
            if line.strip() == target_line:
                self.logger.info("chroot %s exists" % chroot)
                return True
        return False

    def is_parent_config(self, schroot_config_name, user):
        index = self.index_from_schroot_config_name(schroot_config_name, user)
        if index is None:
            return True
        else:
            return False

    def get_parent_schroot_config(self, user):
        schroot_conf_list = os.listdir(self.schroot_config_dir)
        for schroot_conf_name in schroot_conf_list:
            if self.is_parent_config(schroot_conf_name, user):
                return schroot_conf_name
        return None

    def set_unique_id(self, user):
        parent_schroot_config_name = self.get_parent_schroot_config(user)
        self.logger.debug("parent_schroot_config_name: %s" % parent_schroot_config_name)
        parent_schroot_components = self.decompose_schroot_config_name(parent_schroot_config_name, user)
        if parent_schroot_components and 'unique_id' in parent_schroot_components:
            self.attrs['unique_id'] = parent_schroot_components['unique_id']
            self.logger.debug("unique_id: %s" % self.attrs['unique_id'])
        else:
            self.logger.error("failed to determine schroot unique_id from parent schroot name")

    def add_chroot(self, request_form):
        response = check_request(request_form, ['user', 'project'])
        if response:
            return response
        user = request_form['user']
        project = request_form['project']

        parent_chroot_name = self.get_parent_chroot_name(user)
        if self.has_chroot(parent_chroot_name):
            self.logger.warn("chroot %s already exists" % parent_chroot_name)
            self.set_unique_id(user)
            response['status'] = 'exists'
            response['msg'] = 'chroot exists'
            return response

        user_chroots_dir = self.get_user_chroots_dir(user, project)
        parent_chroot_dir = self.get_parent_chroot_dir(user, project)
        user_schroot_log_path = self.get_user_schroot_log_path(user, project)

        os.makedirs(user_chroots_dir, exist_ok=True)
        self.logger.debug("Directory of chroots: %s" % user_chroots_dir)

        if os.path.exists(parent_chroot_dir):
            self.logger.debug("Found disused chroot %s, remove it" % parent_chroot_dir)
            try:
                shutil.rmtree(parent_chroot_dir)
            except Exception as e:
                self.logger.error(str(e))
                # New chroot will be created below, we just reports this
                self.logger.warning("Failed to remove %s" % parent_chroot_dir)

        try:
            self.ctlog = open(user_schroot_log_path, 'w')
        except IOError as e:
            self.logger.error(str(e))
            response['status'] = 'fail'
            response['msg'] = 'fail to create log file'
        else:
            chroot_suffix = '--chroot-suffix=-' + user
            chroot_cmd = ' '.join(['nice', '-n', '15', 'ionice', '-c', '3',
                                   'sbuild-createchroot', chroot_suffix,
                                   '--include=apt-transport-https,ca-certificates,eatmydata',
                                   '--command-prefix=eatmydata',
                                   self.attrs['dist'], parent_chroot_dir])
            if 'mirror' in request_form:
                chroot_cmd = ' '.join([chroot_cmd, request_form['mirror']])
            self.logger.debug("Command to create chroot:%s" % chroot_cmd)

            p = subprocess.Popen(chroot_cmd, shell=True, stdout=self.ctlog,
                                 stderr=self.ctlog)
            self.chroot_processes.setdefault(user, []).append(p)

            response['status'] = 'creating'
            response['msg'] = 'Chroot created, please check logs at: %s' % user_schroot_log_path
        return response

    def save_chroots_config(self, user, project):
        self.logger.debug("Save the config file of chroot to persistent store")
        user_schroot_config_dir = self.get_user_schroot_config_dir(user, project)
        try:
            shutil.rmtree(user_schroot_config_dir)
            shutil.copytree(self.schroot_config_dir, user_schroot_config_dir)
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error("Failed to save the config file of chroot")
        else:
            self.logger.info("Successfully saved the config file of chroot")

    def delete_cloned_chroot(self, user, project, index):
        """
        Delete a clone chroot
        """
        rc = True
        delete_chroot_dir = self.get_cloned_chroot_dir(user, project, index)

        # Delete old chroot
        if delete_chroot_dir is not None and os.path.exists(delete_chroot_dir):
            self.logger.debug('Delete chroot at path: %s', delete_chroot_dir)
            try:
                if utils.is_tmpfs(delete_chroot_dir):
                    utils.unmount_tmpfs(delete_chroot_dir)
                shell_cmd = 'rm -rf --one-file-system %s' % delete_chroot_dir
                self.logger.debug('shell_cmd=%s', shell_cmd)
                subprocess.check_call(shell_cmd, shell=True)
            except Exception as e:
                self.logger.error(str(e))
                self.logger.error("Failed to delete unwanted chroot: %s", delete_chroot_dir)
                rc = False

        return rc

    def delete_cloned_schroot_config(self, user, project, index):
        """
        Delete a clone's schroot config
        """
        rc = True
        delete_conf_path = self.get_schroot_conf_path(user, index)

        if delete_conf_path is not None and os.path.exists(delete_conf_path):
            self.logger.debug('Delete schroot config at path: %s', delete_conf_path)
            try:
                shell_cmd = 'rm -f %s' % delete_conf_path
                self.logger.debug('shell_cmd=%s', shell_cmd)
                subprocess.check_call(shell_cmd, shell=True)
            except Exception as e:
                self.logger.error(str(e))
                self.logger.error("Failed to remove unwanted config file: %s", delete_conf_path)
                rc = False

        # self.chroots_pool.load()
        return rc

    def delete_clones_by_max_index(self, user, project, max_index):
        """
        Delete a clone's chroot dir and schroot config file if it's index exceeds the maximum.
        i.e. the number of parallel instances is being reduced
        """
        rc = True

        schroot_conf_list = os.listdir(self.schroot_config_dir)
        for schroot_conf_name in schroot_conf_list:
            index = self.index_from_schroot_config_name(schroot_conf_name, user)
            if index is None or index <= max_index:
                continue
            if not self.delete_cloned_schroot_config(user, project, index):
                rc = False

        user_chroots_dir = self.get_user_chroots_dir(user, project)
        chroot_list = os.listdir(user_chroots_dir)
        for chroot_name in chroot_list:
            if chroot_name == 'chroot.d':
                continue
            index = self.index_from_chroot_name(chroot_name, user)
            if index is None or index <= max_index:
                continue
            if not self.delete_cloned_chroot(user, project, index):
                rc = False

        # self.chroots_pool.load()
        return rc

    def delete_all_clone_chroots(self, user, project):
        rc = True

        user_chroots_dir = self.get_user_chroots_dir(user, project)
        chroot_list = os.listdir(user_chroots_dir)
        for chroot_name in chroot_list:
            if chroot_name == 'chroot.d':
                continue
            index = self.index_from_chroot_name(chroot_name, user)
            if index is None:
                continue
            if not self.delete_cloned_chroot(user, project, index):
                rc = False

        return rc

    def delete_tmpfs_clones(self, user, project):
        rc = True

        user_chroots_dir = self.get_user_chroots_dir(user, project)
        chroot_list = os.listdir(user_chroots_dir)
        for chroot_name in chroot_list:
            if chroot_name == 'chroot.d':
                continue
            if not utils.is_tmpfs(os.path.join(user_chroots_dir, chroot_name)):
                continue
            index = self.index_from_chroot_name(chroot_name, user)
            if index is None:
                continue
            if not self.delete_cloned_chroot(user, project, index):
                rc = False
            if not self.delete_cloned_schroot_config(user, project, index):
                rc = False

        return rc

    def free_tmpfs_chroots(self, request_form):
        response = check_request(request_form, ['user', 'project'])
        if response:
            return response

        user = request_form['user']
        project = request_form['project']
        if not self.delete_tmpfs_clones(user, project):
            msg = 'Failed to delete some tmpfs chroots.'
            self.logger.error(msg)
            response['status'] = 'fail'
            response['msg'] = msg
        else:
            response['status'] = 'success'
            response['msg'] = 'tmpfs chroots have been freed'
        self.chroots_pool.load()
        return response

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
        tmpfs_instances = 0
        if 'tmpfs_percentage' in request_form.keys():
            tmpfs_percentage = int(request_form['tmpfs_percentage'])
        else:
            tmpfs_percentage = 0
        chroot_sequence = 1

        # Try to find the parent chroot
        # e.g bullseye-amd64-user
        parent_chroot_name = self.get_parent_chroot_name(user)
        # e.g /localdisk/pkgbuilder/user/stx/chroots/bullseye-amd64-user
        parent_chroot_dir = self.get_parent_chroot_dir(user, project)

        if not os.path.exists(parent_chroot_dir):
            self.logger.error("Failed to find the parent chroot %s", parent_chroot_dir)
            response['status'] = 'fail'
            response['msg'] = 'The parent chroot %s does not exist' % parent_chroot_dir
            return response

        parent_conf_path = self.get_schroot_conf_path(user)
        if parent_conf_path is None or not os.path.exists(parent_conf_path):
            self.logger.error("Failed to find the parent schroot config file for %s", parent_chroot_name)
            response['status'] = 'fail'
            response['msg'] = 'The parent schroot config file for %s does not exist' % parent_chroot_name
            return response

        self.set_unique_id(user)

        if not self.delete_clones_by_max_index(user, project, required_instances):
            response['status'] = 'fail'
            response['msg'] = 'Failed to delete old schroot instances'
            return response

        if not self.delete_all_clone_chroots(user, project):
            response['status'] = 'fail'
            response['msg'] = 'Failed to delete old chroot instances'
            return response

        # tmpfs calculations
        mem_per_instance_gb = 0
        if required_instances > 1:
            GB = 1024 * 1024 * 1024
            min_tmpfs_size_gb = 10
            mem = psutil.virtual_memory()
            avail_mem_gb = int(mem.available * tmpfs_percentage / (100 * GB))
            for tmpfs_instances in range(required_instances - 1, -1, -1):
                if tmpfs_instances <= 0:
                    mem_per_instance_gb = 0
                    break
                mem_per_instance_gb = int(avail_mem_gb / tmpfs_instances)
                if mem_per_instance_gb >= min_tmpfs_size_gb:
                    break

        self.logger.debug("The parent chroot %s exists, start to clone chroot from it", parent_chroot_dir)
        self.logger.debug("Creating %s instances, including %s instances using %s gb of tmpfs", required_instances, tmpfs_instances, mem_per_instance_gb)
        for instance in range(required_instances):
            cloned_chroot_name = self.get_cloned_chroot_name(user, chroot_sequence)
            cloned_chroot_dir = self.get_cloned_chroot_dir(user, project, chroot_sequence)
            clone_conf_path = self.get_schroot_conf_path(user, chroot_sequence)

            if clone_conf_path is None:
                err_msg = "Failed to determine the schroot config file for %s" % cloned_chroot_name
                self.logger.error(err_msg)
                response['status'] = 'fail'
                response['msg'] = err_msg
                return response

            use_tmpfs = (instance >= (required_instances - tmpfs_instances))

            # Create new chroot
            self.logger.info("Cloning chroot %s from the parent %s", cloned_chroot_dir, parent_chroot_dir)
            try:
                if use_tmpfs:
                    os.makedirs(cloned_chroot_dir)
                    shell_cmd = 'mount -t tmpfs -o size=%sG tmpfs %s' % (mem_per_instance_gb, cloned_chroot_dir)
                    subprocess.check_call(shell_cmd, shell=True)
                    shell_cmd = 'cp -ar %s/. %s/' % (parent_chroot_dir, cloned_chroot_dir)
                    subprocess.check_call(shell_cmd, shell=True)
                else:
                    self.logger.info("Cloning chroot %s from the parent %s", cloned_chroot_dir, parent_chroot_dir)
                    shell_cmd = 'rm -rf %s.tmp' % cloned_chroot_dir
                    subprocess.check_call(shell_cmd, shell=True)
                    shell_cmd = 'cp -ar %s %s.tmp' % (parent_chroot_dir, cloned_chroot_dir)
                    subprocess.check_call(shell_cmd, shell=True)
                    shell_cmd = 'mv %s.tmp %s' % (cloned_chroot_dir, cloned_chroot_dir)
                    subprocess.check_call(shell_cmd, shell=True)
            except Exception as e:
                self.logger.error(str(e))
                response['status'] = 'fail'
                if not response['msg']:
                    response['msg'] = 'Failed to create chroot instances:'
                response['msg'].append(str(instance) + ' ')
                continue
            else:
                self.logger.info("Successfully cloned chroot %s", cloned_chroot_dir)

            self.logger.info("Target cloned chroot %s is ready, updating config", cloned_chroot_dir)

            # For the cloned chroot, the schroot config file also need to be created.
            # Start with the parent schroot as a template and modify it
            if os.path.exists(clone_conf_path):
                self.logger.debug("Cloned chroot config %s already exists", clone_conf_path)
                chroot_sequence = chroot_sequence + 1
                continue
            try:
                self.logger.debug("Creating config file %s from %s", clone_conf_path, parent_conf_path)
                shutil.copyfile(parent_conf_path, clone_conf_path)
                self.logger.debug("Successfully cloned chroot config, try to update %s", clone_conf_path)
                shell_cmd = 'sed -i \'s/%s/%s/g\' %s' % (parent_chroot_name, cloned_chroot_name, clone_conf_path)
                subprocess.check_call(shell_cmd, shell=True)
            except Exception as e:
                self.logger.error(str(e))
                self.logger.error("Failed to clone and update config file %s", clone_conf_path)
                continue
            else:
                self.logger.debug("Successfully cloned and updated chroot's config %s", clone_conf_path)
                chroot_sequence = chroot_sequence + 1
                continue

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

        user_schroot_config_dir = self.get_user_schroot_config_dir(user, project)
        if not os.path.exists(user_schroot_config_dir):
            self.logger.warn("Failed to find directory of chroots %s" % user_schroot_config_dir)
            response['status'] = 'success'
            response['msg'] = ' '.join(['External chroot', user_schroot_config_dir,
                                        'does not exist'])
        else:
            try:
                shutil.rmtree(self.schroot_config_dir)
                shutil.copytree(user_schroot_config_dir, self.schroot_config_dir)
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

        user_schroot_config_dir = self.get_user_schroot_config_dir(user, project)
        try:
            shutil.rmtree(user_schroot_config_dir)
        except Exception as e:
            self.logger.error(str(e))
            # Just report this but not quit
            self.logger.error("Failed to remove %s", user_schroot_config_dir)

        try:
            shutil.copytree(self.schroot_config_dir, user_schroot_config_dir)
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error("Failed to save %s with %s", self.schroot_config_dir, user_schroot_config_dir)
            response['status'] = 'fail'
            response['msg'] = 'Failed to save the config files of chroots to persistent storage'
        else:
            response['status'] = 'success'
            response['msg'] = 'Successfully saved the config files of chroots to persistent storage'
            self.logger.debug("Successfully saved the config files of chroots")
        return response

    def refresh_chroots(self, request_form):
        '''
        Refresh all chroots with the 'clean' parent chroot
        '''
        response = check_request(request_form, ['user', 'project'])
        if response:
            return response
        user = request_form['user']
        project = request_form['project']

        dst_chroots = self.chroots_pool.get_busy()
        if dst_chroots:
            self.logger.warning('Some chroots are busy')

        self.logger.warning('Force the termination of busy chroots prior to refresh')
        self.stop_task(request_form)
        self.chroots_pool.release_all()

        # Stop all schroot sessions
        subprocess.call('schroot --all --end-session', shell=True)

        dst_chroots = self.chroots_pool.get_idle()
        user_chroots_dir = self.get_user_chroots_dir(user, project)
        parent_chroot_name = self.get_parent_chroot_dir(user, project)
        if not os.path.exists(os.path.join(user_chroots_dir, parent_chroot_name)):
            self.logger.error("The parent chroot %s does not exist", parent_chroot_name)
            response['status'] = 'fail'
            response['msg'] = 'The parent chroot does not exist'
            return response
        for clone_chroot_name in dst_chroots:
            # e.g. the chroot name is 'chroot:bullseye-amd64-<user>-1'
            self.logger.debug('The current chroot is %s', clone_chroot_name)
            if parent_chroot_name == clone_chroot_name:
                continue

            parent_chroot_path = os.path.join(user_chroots_dir, parent_chroot_name)
            self.logger.debug('The parent chroot path: %s', parent_chroot_path)
            clone_chroot_path = os.path.join(user_chroots_dir, clone_chroot_name)
            self.logger.debug('The chroot path: %s', clone_chroot_path)
            is_tmpfs = self.chroots_pool.is_tmpfs(clone_chroot_name)
            self.logger.debug('is_tmpfs: %s', is_tmpfs)
            try:
                if is_tmpfs:
                    self.logger.debug('clean directory: %s', clone_chroot_path)
                    utils.clear_directory(clone_chroot_path)
                    shell_cmd = 'cp -ar %s/. %s/' % (parent_chroot_path, clone_chroot_path)
                    self.logger.debug('shell_cmd: %s', shell_cmd)
                    subprocess.check_call(shell_cmd, shell=True)
                    self.logger.debug('cmd exits: %s', shell_cmd)
                else:
                    cp_cmd = 'cp -ra %s %s' % (parent_chroot_path, clone_chroot_path + '.tmp')
                    subprocess.check_call(cp_cmd, shell=True)
                    rm_cmd = 'rm -rf --one-file-system ' + clone_chroot_path
                    subprocess.check_call(rm_cmd, shell=True)
                    mv_cmd = 'mv -f %s %s' % (clone_chroot_path + '.tmp', clone_chroot_path)
                    subprocess.check_call(mv_cmd, shell=True)
            except subprocess.CalledProcessError as e:
                self.logger.error(str(e))
                self.logger.error('Failed to refresh the chroot %s', clone_chroot_name)
                response['status'] = 'fail'
                response['msg'] = 'Error during refreshing the chroots'
                return response
            else:
                self.logger.info('Successfully refreshed the chroot %s', clone_chroot_name)

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
                                 ['user', 'project', 'type', 'dsc', 'snapshot_idx', 'layer', 'size', 'allow_tmpfs'])
        if response:
            return response
        user = request_form['user']
        snapshot_index = request_form['snapshot_idx']
        layer = request_form['layer']
        size = request_form['size']
        allow_tmpfs = request_form['allow_tmpfs']

        chroot_name = self.compose_chroot_name(user)
        if not self.has_chroot(chroot_name):
            self.logger.critical("The basic chroot %s does not exist" % chroot_name)
            response['status'] = 'fail'
            response['msg'] = ' '.join(['chroot', chroot_name, 'does not exist'])
            return response

        # for example: dsc = '/path/to/tsconfig_1.0-1.stx.3.dsc'
        dsc = request_form['dsc']
        if not os.path.isfile(dsc):
            self.logger.error("%s does not exist" % dsc)
            response['status'] = 'fail'
            response['msg'] = dsc + ' does not exist'
            return response

        bcommand = ' '.join(['nice', '-n', '15', 'ionice', '-c', '3',
                             BUILD_ENGINE, '-d', self.attrs['dist']])
        dsc_build_dir = os.path.dirname(dsc)
        chroot = self.chroots_pool.acquire(needed_size=size, allow_tmpfs=allow_tmpfs)
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
        stamp_dir = self.get_user_stamp_dir(user, project, build_type)
        try:
            shutil.rmtree(stamp_dir)
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
        chroot_name = self.compose_chroot_name(user)
        if not self.has_chroot(chroot_name):
            self.logger.critical("Can't find required chroot: %s" % chroot_name)

        req['user'] = user
        req['owner'] = 'all'
        self.kill_task(req)
        os.system('sbuild_abort')

        response['status'] = 'success'
        response['msg'] = 'Stop current build tasks'
        self.attrs['state'] = 'idle'
        return response
