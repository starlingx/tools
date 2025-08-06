#!/usr/bin/env python3
#
# Copyright (c) 2024 Wind River Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import getpass
import logging
import os
import subprocess
import sys
import time

from stx.k8s import KubeHelper
from stx.minikube import MinikubeCtl
from stx.minikube import MinikubeProfileNotFoundError

from stx import helper  # pylint: disable=E0611
from stx import stx_shell
from stx import utils  # pylint: disable=E0611

helmchartdir = 'stx/stx-build-tools-chart/stx-builder'

tty_flag = ' -ti ' if os.isatty(1) else ' -i '


class HandleControlTask(object):
    '''Handle the task for the control sub-command'''

    def __init__(self, config):
        self.config = config
        self.k8s = KubeHelper(config)
        self.projectname = self.config.get('project', 'name')
        self.logger = logging.getLogger('STX-Control')
        self.abs_helmchartdir = os.path.join(os.environ['PRJDIR'],
                                             helmchartdir)
        self.shell = stx_shell.HandleShellTask(config)
        utils.set_logger(self.logger)
        if self.config.use_minikube:
            self.minikube_ctl = MinikubeCtl(profile_name=self.config.minikube_profile)

    def configurePulp(self):
        '''Initial the password of the pulp service.'''

        # wait three times when the pulp service is not initialized yet.
        count = 3
        remote_cmd = ' -- bash /etc/pulp/changepasswd'
        pulpname = ' stx-pulp'
        while count:
            podname = self.k8s.get_pod_name(pulpname)
            if podname:
                cmd = self.config.kubectl() + ' exec ' + tty_flag
                cmd = cmd + podname + remote_cmd
                subprocess.call(cmd, shell=True)
                count = 0
            else:
                self.logger.info('Waiting for pulp to finish the setup...')
                time.sleep(60)
                count = count - 1
                if count == 0:
                    self.logger.error('Pulp service initialization failed.\n')
                    sys.exit(1)

    def finish_configure(self):
        '''Before starting, we need to finish the setup'''

        max_cpus = os.environ['STX_BUILD_CPUS']

        projectname = self.config.get('project', 'name')
        builder_uid = self.config.get('builder', 'uid')
        builder_myuname = self.config.get('builder', 'myuname')
        builder_release = self.config.get('builder', 'release')
        builder_debfullname = self.config.get('builder', 'debfullname')
        builder_debemail = self.config.get('builder', 'debemail')
        repomgr_type = self.config.get('repomgr', 'type')
        repomgr_origin = self.config.get('repomgr', 'origin')
        gituser = self.config.get('project', 'gituser')
        gitemail = self.config.get('project', 'gitemail')
        proxy = self.config.get('project', 'proxy')
        proxyserver = self.config.get('project', 'proxyserver')
        proxyport = self.config.get('project', 'proxyport')
        buildbranch = self.config.get('project', 'buildbranch')
        manifest = self.config.get('project', 'manifest')

        # Adjust builder distribution variables to align with the build
        # container configuration
        #  Migrate:
        #    builder.dist -> builder.os_id            (= debian)
        #    builder.stx_dist -> builder.stx_pkg_ext  (= .stx  )
        #  Add:
        #    builder.os_codename                      (= bullseye)

        try:
            builder_os_codename = self.config.get('builder', 'os_codename')
            builder_os_id = self.config.get('builder', 'os_id')
        except Exception:
            builder_dist = self.config.get('builder', 'dist')
            builder_os_codename = builder_dist
            builder_os_id = 'debian'

        try:
            builder_stx_pkg_ext = self.config.get('builder', 'stx_pkg_ext')
        except Exception:
            builder_stx_dist = self.config.get('builder', 'stx_dist')
            builder_stx_pkg_ext = builder_stx_dist

        # The stx_mirror_url references below are obsolete, and are retained for
        # backward compatibility with preexisting build environmnets.
        # Please use {os,lat}_mirror versions instead.
        stx_mirror_url = None
        try:
            os_mirror_url = self.config.get('repomgr', 'os_mirror_url')
            if not os_mirror_url:
                # Assume that we want an upstream URL
                os_mirror_url = "http://"
        except Exception:
            # second chance using old stx_mirror_url
            try:
                stx_mirror_url = self.config.get('repomgr', 'stx_mirror_url')
                os_mirror_url = stx_mirror_url
            except Exception:
                # Fail on os_mirror_url without catching the error this time
                os_mirror_url = self.config.get('repomgr', 'os_mirror_url')
        os_mirror_dist_path = self.config.get('repomgr', 'os_mirror_dist_path')
        os_mirror_dl_path = self.config.get('repomgr', 'os_mirror_dl_path')
        stx_mirror_strategy = self.config.get('repomgr', 'stx_mirror_strategy')
        lat_mirror_url = self.config.get('repomgr', 'lat_mirror_url')
        lat_mirror_lat_path = self.config.get('repomgr', 'lat_mirror_lat_path')

        sourceslist = self.config.get('repomgr', 'sourceslist')
        deblist = self.config.get('repomgr', 'deblist')
        dsclist = self.config.get('repomgr', 'dsclist')
        ostree_osname = self.config.get('project', 'ostree_osname')
        debian_snapshot = ""
        if self.config.get('project', 'debian_snapshot_base'):
            debian_snapshot = \
                self.config.get('project', 'debian_snapshot_base') + \
                '/' + \
                self.config.get('project', 'debian_snapshot_timestamp')
        debian_security_snapshot = ""
        if self.config.get('project', 'debian_security_snapshot_base'):
            debian_security_snapshot = \
                self.config.get('project', 'debian_security_snapshot_base') + \
                '/' + \
                self.config.get('project', 'debian_snapshot_timestamp')
        debian_distribution = self.config.get('project', 'debian_distribution')
        debian_version = self.config.get('project', 'debian_version')
        if sourceslist:
            if not (deblist or dsclist):
                self.logger.warning('*************************************\
*********************************')
                self.logger.warning('Either Deblist or Dsclist must exist \
when sourceslist is enabled!!!')
                self.logger.warning('*************************************\
*********************************')
                sys.exit(1)

        repomgr_type = self.config.get('repomgr', 'type')
        if repomgr_type not in ('aptly', 'pulp'):
            self.logger.warning('Repomgr type only supports [aptly] or [pulp],\
 please modify the value with config command!!!')
            sys.exit(1)

        builder_chartfile = os.path.join(self.abs_helmchartdir, 'Chart.yaml')
        cmd = 'sed -i -e "s:aptly:%s:g" %s' % (repomgr_type, builder_chartfile)
        self.logger.debug('Write the repomgr type [%s] to the chart file \
with the command [%s]', repomgr_type, cmd)

        # Fix Me:
        # Now we always use aptly as the repomgr.
        # Don't switch to pulp, since it will trigger the sshd block issue.
        # Later if we find the root cause and fix it, we will enable the
        # following function.

        # os.system(cmd)

        configmap_dir = os.path.join(self.abs_helmchartdir, 'configmap/')
        self.logger.debug('builder localrc file is located at %s',
                          configmap_dir)
        pkgbuilder_configmap_dir = os.path.join(self.abs_helmchartdir,
                                                'dependency_chart/\
stx-pkgbuilder/configmap/')
        self.logger.debug('pkgbuilder localrc file is located at %s',
                          pkgbuilder_configmap_dir)
        if not os.path.exists(pkgbuilder_configmap_dir):
            os.mkdir(pkgbuilder_configmap_dir)

        localrcsample = os.path.join(configmap_dir, 'localrc.sample')
        localrc = os.path.join(configmap_dir, 'stx-localrc')
        if os.path.exists(localrc):
            os.remove(localrc)

        hostusername = getpass.getuser()

        with open(localrcsample, "r") as rf:
            message = ''
            for line in rf:
                line = line.replace("@PROJECT@", projectname)
                line = line.replace("@MYUID@", builder_uid)
                line = line.replace("@MYUNAME@", builder_myuname)
                line = line.replace("@MY_RELEASE@", builder_release)
                line = line.replace("@BUILDER_OS_ID@", builder_os_id)
                line = line.replace("@BUILDER_OS_CODENAME@", builder_os_codename)
                line = line.replace("@BUILDER_STX_PKG_EXTENSION@", builder_stx_pkg_ext)
                line = line.replace("@DEBFULLNAME@", builder_debfullname)
                line = line.replace("@DEBEMAIL@", builder_debemail)
                line = line.replace("@REPOMGR_TYPE@", repomgr_type)
                line = line.replace("@REPOMGR_ORIGIN@", repomgr_origin)
                line = line.replace("@GITUSER@", gituser)
                line = line.replace("@GITEMAIL@", gitemail)
                line = line.replace("@PROXY@", proxy)
                line = line.replace("@PROXYSERVER@", proxyserver)
                line = line.replace("@PROXYPORT@", proxyport)
                line = line.replace("@BUILDBRANCH@", buildbranch)
                line = line.replace("@MANIFEST@", manifest)
                line = line.replace("@HOSTUSERNAME@", hostusername)
                line = line.replace("@OS_MIRROR_URL@", os_mirror_url)
                line = line.replace("@OS_MIRROR_DIST_PATH@", os_mirror_dist_path)
                line = line.replace("@OS_MIRROR_DL_PATH@", os_mirror_dl_path)
                line = line.replace("@LAT_MIRROR_URL@", lat_mirror_url)
                line = line.replace("@LAT_MIRROR_LAT_PATH@", lat_mirror_lat_path)
                line = line.replace("@STX_MIRROR_STRATEGY@", stx_mirror_strategy)
                line = line.replace("@OSTREE_OSNAME@", ostree_osname)
                line = line.replace("@DEBIAN_SNAPSHOT@", debian_snapshot)
                line = line.replace("@DEBIAN_SECURITY_SNAPSHOT@", debian_security_snapshot)
                line = line.replace("@DEBIAN_DISTRIBUTION@", debian_distribution)
                line = line.replace("@DEBIAN_VERSION@", debian_version)
                line = line.replace("@MAX_CPUS@", max_cpus)
                if sourceslist:
                    line = line.replace("@fetch@", "true")
                    line = line.replace("@SOURCESLIST@", sourceslist)
                    line = line.replace("@DEBLIST@", deblist)
                    line = line.replace("@DSCLIST@", dsclist)
                message += line

        with open(localrc, "w") as wf:
            wf.write(message)

        # Update LAT configmap for patching
        lat_configmap_dir = os.path.join(self.abs_helmchartdir,
                                         'dependency_chart/stx-lat-tool/configmap/')
        patch_env_sample = os.path.join(lat_configmap_dir, 'patch.env.sample')
        patch_env = os.path.join(lat_configmap_dir, 'stx-patch-env.sh')

        with open(patch_env_sample, "r") as rf:
            message = rf.read()
            message = message.replace("@PROJECT@", projectname)
            message = message.replace("@MYUNAME@", builder_myuname)

        with open(patch_env, "w") as wf:
            wf.write(message)

        # Copy stx-localrc file of builder container to pkgbuilder
        cmd = 'cp -f %s %s' % (localrc, pkgbuilder_configmap_dir)
        os.system(cmd)

        # Update the dependency charts
        cmd = self.config.helm() + ' dependency update ' + self.abs_helmchartdir
        self.logger.debug('Dependency build command: %s', cmd)
        subprocess.call(cmd, shell=True)

        return repomgr_type

    def handleStartTask(self, projectname, wait, use_dockerhub_cred):
        if self.config.use_minikube:
            self.minikube_ctl.start()

        wait_arg = '--wait ' if wait else ''
        cmd = self.config.helm() + ' install ' + wait_arg + projectname + ' ' \
            + self.abs_helmchartdir \
            + ' --set global.image.tag=' + self.config.docker_tag + '-' + self.config.get('builder', 'os_codename')

        if not self.config.use_minikube:
            # Override hostDir for k8s local host mount
            # need to review this to support multi node (PV/PVCs)
            cmd += ' --set global.hostDir=' + self.config.build_home

        for reg_index, reg in enumerate(self.config.insecure_docker_reg_list):
            cmd += f' --set stx-docker.insecureRegistries[{reg_index}]={reg}'

        if self.config.container_mtu:
            cmd += f' --set stx-docker.mtu={self.config.container_mtu}'

        if use_dockerhub_cred:
            image_pull_secret = self.k8s.try_create_docker_cred_secret()
            if image_pull_secret:
                cmd += f' --set global.imagePullSecrets[0].name={image_pull_secret}'

        self.logger.debug('Execute the helm start command: %s', cmd)
        helm_status = self.k8s.helm_release_exists(self.projectname)
        if helm_status:
            self.logger.warning('The helm release %s already exists - nothing to do',
                                projectname)
        else:
            repomgr_type = self.finish_configure()
            subprocess.check_call(cmd, shell=True, cwd=os.environ['PRJDIR'])
            if repomgr_type == 'pulp':
                self.configurePulp()

    def handleStopTask(self, projectname, wait):
        # "helm uninstall --wait" requires version >= 3.7, and is broken
        # in some versions:
        #     https://github.com/helm/helm/issues/10586
        #     https://github.com/helm/helm/pull/11479
        #
        # Workaround: loop until there are no pods left, after "helm uninstall".

        # Use Helm's own default timeout of 5 minutes
        timeout = 5 * 60
        deadline = time.time() + timeout
        if self.config.use_minikube:
            self.minikube_ctl.require_started()

        helm_status = self.k8s.helm_release_exists(self.projectname)
        if helm_status:
            cmd = f'{self.config.helm()} uninstall {projectname}'
            self.logger.debug('Execute the helm stop command: %s', cmd)
            subprocess.check_call(cmd, shell=True)
        else:
            self.logger.warning('The helm release %s does not exist',
                                projectname)

        if wait:
            while True:
                pod_count = len(self.k8s.get_helm_pods())
                if pod_count == 0:
                    break
                if time.time() > deadline:
                    self.logger.warning("maximum wait time of %d second(s) exceeded", timeout)
                    self.logger.warning("gave up while pods are still running")
                    break
                self.logger.info("waiting for %d pod(s) to exit", pod_count)
                time.sleep(2)

        self.k8s.delete_docker_cred_secret()

    def handleIsStartedTask(self, projectname):
        if self.k8s.helm_release_exists(projectname):
            self.logger.info('Helm release %s is installed' % projectname)
            sys.exit(0)
        else:
            self.logger.info('Helm release %s is not installed' % projectname)
            sys.exit(1)

    def handleUpgradeTask(self, projectname):
        self.finish_configure()
        helm_status = self.k8s.helm_release_exists(self.projectname)
        if helm_status:
            cmd = self.config.helm() + ' upgrade ' + projectname + ' ' \
                + self.abs_helmchartdir
            self.logger.debug('Execute the upgrade command: %s', cmd)
            subprocess.call(cmd, shell=True, cwd=os.environ['PRJDIR'])
        else:
            self.logger.error('The helm release %s does not exist.',
                              projectname)
            sys.exit(1)

    def handleEnterTask(self, args):
        self.shell.cmd_control_enter(args)

    def handleStatusTask(self):
        if self.config.use_minikube:
            self.minikube_ctl.require_started()
        self.k8s.get_helm_info()
        self.k8s.get_deployment_info()
        self.k8s.get_pods_info()

    def run_pod_cmd(self, podname, maincmd, remotecmd):
        # Run command on pod in this format: kubectl+maincmd+podname+remotecmd
        cmd = self.config.kubectl() + maincmd + podname + remotecmd
        self.logger.info('run pod cmd: %s', cmd)
        subprocess.call(cmd, shell=True)

    def add_keys_for_signing_server(self, args):
        self.logger.info('Prepare keys for accessing signing server!')
        buildername = 'builder'
        latname = 'lat'
        username = getpass.getuser()
        if not args.key:
            args.key = '~/.ssh/id_rsa'
        if not os.path.exists(os.path.expanduser(args.key)):
            self.logger.error("The key file doesn't exist!")
            sys.exit(1)

        pod_name = self.k8s.get_pod_name(buildername)
        if pod_name:
            # Prepare and run commands:
            #  kubectl exec -i(or -it if is a TTY) [pod_name_builder] -- mkdir /home/[user_name]/.ssh
            #  kubectl exec -i(or -it if is a TTY) [pod_name_builder] -- mkdir /root/.ssh
            #  kubectl cp [key] [pod_name_builder]:/home/[user_name]/.ssh
            #  kubectl cp [key] [pod_name_builder]:/root/.ssh
            main_cmd = ' exec ' + tty_flag
            remote_cmd = ' -- mkdir /home/' + username + '/.ssh'
            self.run_pod_cmd(pod_name, main_cmd, remote_cmd)
            remote_cmd = ' -- mkdir /root/.ssh'
            self.run_pod_cmd(pod_name, main_cmd, remote_cmd)
            main_cmd = ' cp ' + args.key + ' '
            remote_cmd = ':/home/' + username + '/.ssh'
            self.run_pod_cmd(pod_name, main_cmd, remote_cmd)
            remote_cmd = ':/root/.ssh'
            self.run_pod_cmd(pod_name, main_cmd, remote_cmd)
        else:
            self.logger.error('Failed to prepare for signing builds because \
no builder container is available!')
            sys.exit(1)

        pod_name = self.k8s.get_pod_name(latname)
        if pod_name:
            # Prepare and run commands:
            #  kubectl exec -i(or -it if is a TTY) [pod_name_lat] -- mkdir /root/.ssh
            #  kubectl cp [key] [pod_name_lat]:/root/.ssh
            main_cmd = ' exec ' + tty_flag
            remote_cmd = ' -- mkdir /root/.ssh'
            self.run_pod_cmd(pod_name, main_cmd, remote_cmd)
            main_cmd = ' cp ' + args.key + ' '
            remote_cmd = ':/root/.ssh'
            self.run_pod_cmd(pod_name, main_cmd, remote_cmd)
        else:
            self.logger.error('Failed to prepare for signing builds because \
no lat container is available!')
            sys.exit(1)

    def handleKeysTask(self, args):
        if not args.key_type:
            args.key_type = 'signing-server'
        if args.key_type == 'signing-server':
            self.add_keys_for_signing_server(args)
        else:
            self.logger.error('Unsupported key-type!')
            sys.exit(1)

    def handleControl(self, args):
        try:
            self.logger.setLevel(args.loglevel)
            projectname = self.config.get('project', 'name')
            if not projectname:
                projectname = 'stx'

            if args.ctl_task == 'start':
                self.handleStartTask(projectname, args.wait,
                                     args.use_dockerhub_cred)

            elif args.ctl_task == 'stop':
                self.handleStopTask(projectname, args.wait)

            elif args.ctl_task == 'is-started':
                self.handleIsStartedTask(projectname)

            elif args.ctl_task == 'upgrade':
                self.handleUpgradeTask(projectname)

            elif args.ctl_task == 'enter':
                self.handleEnterTask(args)

            elif args.ctl_task == 'keys-add':
                self.handleKeysTask(args)

            elif args.ctl_task == 'status':
                self.handleStatusTask()

            else:
                self.logger.error(
                    'Control module does not support the subcommand: [%s].', args.ctl_task
                )
                self.logger.error(helper.help_control())
        except MinikubeProfileNotFoundError as e:
            self.logger.error(str(e), exc_info=True)
            sys.exit(1)
        except Exception as e:
            self.logger.error(
                'Error executing control task: %s', str(e), exc_info=True
            )
            sys.exit(1)
