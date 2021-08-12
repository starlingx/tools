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
# Copyright (C) 2021 Wind River Systems,Inc
#
import os
import shutil
import subprocess

BUILD_ROOT = '/localdisk/loadbuild/'
BUILD_ENGINE = 'sbuild'
DEBDIST = 'bullseye'


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
    def __init__(self, mode, logger):
        self._state = 'idle'
        self._mode = mode
        self.logger = logger
        self.chroot_processes = {}
        self.sbuild_processes = {}
        self.ctlog = None

    @property
    def state(self):
        return self._state

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, mode):
        self._mode = mode

    def has_chroot(self, chroot):
        chroots = os.popen('schroot -l')
        for line in chroots:
            if chroot in line.strip():
                self.logger.info("chroot %s exists" % chroot)
                return True
        return False

    def add_chroot(self, user='builder', project='stx', mirror=None):
        response = {}
        if user == 'builder':
            self._mode = 'private'
        else:
            self._mode = 'public'
        self.logger.debug("Current chroot mode=%s" % self._mode)

        chroot = ''.join([DEBDIST, '-amd64-', user])
        if self.has_chroot(chroot):
            self.logger.warn("chroot %s has already exists" % chroot)
            response['status'] = 'exists'
            response['msg'] = 'chroot exists'
            return response

        user_dir = os.path.join(BUILD_ROOT, user, project)
        user_chroots_dir = os.path.join(user_dir, 'chroots')
        if not os.path.exists(user_chroots_dir):
            os.makedirs(user_chroots_dir)
        self.logger.debug("User's chroot dir=%s" % user_chroots_dir)

        user_chroot = os.path.join(user_chroots_dir, chroot)
        if os.path.exists(user_chroot):
            self.logger.debug("Invalid chroot %s, clean it" % user_chroot)
            shutil.rmtree(user_chroot)

        self.ctlog = open(os.path.join(user_chroots_dir, 'chroot.log'), 'w')
        chroot_suffix = '--chroot-suffix=-' + user
        chroot_cmd = ' '.join(['sbuild-createchroot', chroot_suffix,
                               '--include=eatmydata', DEBDIST, user_chroot])
        if mirror:
            chroot_cmd = ' '.join([chroot_cmd, mirror])
        self.logger.debug("Command to creat chroot:%s" % chroot_cmd)

        p = subprocess.Popen(chroot_cmd, shell=True, stdout=self.ctlog,
                             stderr=self.ctlog)
        self.chroot_processes.setdefault(user, []).append(p)

        response['status'] = 'creating'
        response['msg'] = ' '.join(['please check',
                                    user_chroots_dir + '/chroot.log'])
        return response

    def load_chroot(self, user, project):
        response = {}
        user_dir = os.path.join(BUILD_ROOT, user, project)
        user_chroots = os.path.join(user_dir, 'chroots/chroot.d')
        if not os.path.exists(user_chroots):
            self.logger.warn("Not find chroots %s" % user_chroots)
            response['status'] = 'success'
            response['msg'] = ' '.join(['External chroot', user_chroots,
                                        'does not exist'])
        else:
            target_dir = '/etc/schroot/chroot.d'
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            shutil.copytree(user_chroots, target_dir)
            response['status'] = 'success'
            response['msg'] = 'Load external chroot config ok'

        self.logger.debug("Load chroots %s" % response['status'])
        return response

    def save_chroot(self, user, project):
        response = {}
        user_dir = os.path.join(BUILD_ROOT, user, project)
        user_chroots = os.path.join(user_dir, 'chroots/chroot.d')
        if os.path.exists(user_chroots):
            shutil.rmtree(user_chroots)

        sys_schroots = '/etc/schroot/chroot.d'
        shutil.copytree(sys_schroots, user_chroots)

        response['status'] = 'success'
        response['msg'] = 'Save chroots config to external'
        self.logger.debug("Save chroots config %s" % response['status'])
        return response

    def add_task(self, user, proj, task_info):
        response = {}

        chroot = ''.join([DEBDIST, '-amd64-', user])
        if not self.has_chroot(chroot):
            self.logger.critical("The chroot %s does not exist" % chroot)
            response['status'] = 'fail'
            response['msg'] = ' '.join(['chroot', chroot, 'does not exist'])
            return response

        project = os.path.join(BUILD_ROOT, user, proj)
        build_dir = os.path.join(project, task_info['type'],
                                 task_info['package'])
        if not os.path.isdir(build_dir):
            self.logger.critical("%s does not exist" % build_dir)
            response['status'] = 'fail'
            response['msg'] = build_dir + ' does not exist'
            return response

        # make sure the dsc file exists
        dsc_target = os.path.join(build_dir, task_info['dsc'])
        if not os.path.isfile(dsc_target):
            self.logger.error("%s does not exist" % dsc_target)
            response['status'] = 'fail'
            response['msg'] = dsc_target + ' does not exist'
            return response

        bcommand = ' '.join([BUILD_ENGINE, '-d', DEBDIST, '-c', chroot,
                            '--build-dir', build_dir, dsc_target])
        self.logger.debug("Build command: %s" % bcommand)

        self._state = 'works'
        p = subprocess.Popen(bcommand, shell=True)
        self.sbuild_processes.setdefault(user, []).append(p)

        response['status'] = 'success'
        response['msg'] = 'sbuild package building task launched'
        return response

    def kill_task(self, user, owner):
        response = {}

        if owner in ['sbuild', 'all']:
            if self.sbuild_processes and self.sbuild_processes[user]:
                for p in self.sbuild_processes[user]:
                    self.logger.debug("Terminating package build process")
                    p.terminate()
                    p.wait()
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

        response['status'] = 'success'
        response['msg'] = 'killed all build related tasks'
        return response

    def stop_task(self, user):
        response = {}
        # check whether the need schroot exists
        chroot = ''.join([DEBDIST, '-amd64-', user])
        if 'public' in self.mode:
            self.logger.debug("Public mode, chroot:%s" % chroot)
        else:
            self.logger.debug("Private mode, chroot:%s" % chroot)

        if not self.has_chroot(chroot):
            self.logger.critical("No required chroot %s" % chroot)

        self.kill_task(user, 'all')
        os.system('sbuild_abort')

        response['status'] = 'success'
        response['msg'] = 'Stop current build tasks'
        return response
