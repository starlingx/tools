#!/usr/bin/env python3
#
# Copyright (c) 2021 Wind River Systems, Inc.
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

from stx import command  # pylint: disable=E0611
from stx import helper  # pylint: disable=E0611
from stx import stx_configparser  # pylint: disable=E0611
from stx import utils  # pylint: disable=E0611

helmchartdir = 'stx/stx-build-tools-chart/stx-builder'


class HandleControlTask:
    '''Handle the task for the control sub-command'''

    def __init__(self):
        self.stxconfig = stx_configparser.STXConfigParser()
        self.projectname = self.stxconfig.getConfig('project', 'name')
        self.helm_status = command.helm_release_exists(self.projectname)
        self.logger = logging.getLogger('STX-Control')
        utils.set_logger(self.logger)

    def configurePulp(self):
        '''Initial the password of the pulp service.'''

        # wait three times when the pulp service is not initialized yet.
        count = 3
        remote_cmd = ' -- bash /etc/pulp/changepasswd'
        pulpname = ' stx-pulp'
        while count:
            podname = command.get_pod_name(pulpname)
            if podname:
                cmd = 'minikube -p $MINIKUBENAME kubectl -- exec -ti '
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

        projectname = self.stxconfig.getConfig('project', 'name')
        builder_uid = self.stxconfig.getConfig('builder', 'uid')
        builder_myuname = self.stxconfig.getConfig('builder', 'myuname')
        builder_release = self.stxconfig.getConfig('builder', 'release')
        builder_dist = self.stxconfig.getConfig('builder', 'dist')
        builder_stx_dist = self.stxconfig.getConfig('builder', 'stx_dist')
        builder_debfullname = self.stxconfig.getConfig('builder',
                                                       'debfullname')
        builder_debemail = self.stxconfig.getConfig('builder', 'debemail')
        repomgr_type = self.stxconfig.getConfig('repomgr', 'type')
        gituser = self.stxconfig.getConfig('project', 'gituser')
        gitemail = self.stxconfig.getConfig('project', 'gitemail')
        proxy = self.stxconfig.getConfig('project', 'proxy')
        proxyserver = self.stxconfig.getConfig('project', 'proxyserver')
        proxyport = self.stxconfig.getConfig('project', 'proxyport')
        buildbranch = self.stxconfig.getConfig('project', 'buildbranch')
        manifest = self.stxconfig.getConfig('project', 'manifest')
        cengnurl = self.stxconfig.getConfig('repomgr', 'cengnurl')
        sourceslist = self.stxconfig.getConfig('repomgr', 'sourceslist')
        deblist = self.stxconfig.getConfig('repomgr', 'deblist')
        dsclist = self.stxconfig.getConfig('repomgr', 'dsclist')
        if sourceslist:
            if not (deblist or dsclist):
                self.logger.warning('*************************************\
*********************************')
                self.logger.warning('Either Deblist or Dsclist must exist \
when sourceslist is enabled!!!')
                self.logger.warning('*************************************\
*********************************')
                sys.exit(1)

        repomgr_type = self.stxconfig.getConfig('repomgr', 'type')
        if repomgr_type not in ('aptly', 'pulp'):
            self.logger.warning('Repomgr type only supports [aptly] or [pulp],\
 please modify the value with config command!!!')
            sys.exit(1)

        builder_chartfile = os.path.join(os.environ['PRJDIR'],
                                         helmchartdir, 'Chart.yaml')
        cmd = 'sed -i -e "s:aptly:%s:g" %s' % (repomgr_type, builder_chartfile)
        self.logger.debug('Write the repomgr type [%s] to the chart file \
with the command [%s]', repomgr_type, cmd)

        # Fix Me:
        # Now we always use aptly as the repomgr.
        # Don't switch to pulp, since it will trigger the sshd block issue.
        # Later if we find the root cause and fix it, we will enable the
        # following function.

        # os.system(cmd)

        builderhelmchartdir = os.path.join(os.environ['PRJDIR'], helmchartdir)
        configmap_dir = os.path.join(builderhelmchartdir, 'configmap/')
        self.logger.debug('builder localrc file is located at %s',
                          configmap_dir)
        pkgbuilder_configmap_dir = os.path.join(builderhelmchartdir,
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
                line = line.replace("@DIST@", builder_dist)
                line = line.replace("@STX_DIST@", builder_stx_dist)
                line = line.replace("@DEBFULLNAME@", builder_debfullname)
                line = line.replace("@DEBEMAIL@", builder_debemail)
                line = line.replace("@REPOMGR_TYPE@", repomgr_type)
                line = line.replace("@GITUSER@", gituser)
                line = line.replace("@GITEMAIL@", gitemail)
                line = line.replace("@PROXY@", proxy)
                line = line.replace("@PROXYSERVER@", proxyserver)
                line = line.replace("@PROXYPORT@", proxyport)
                line = line.replace("@BUILDBRANCH@", buildbranch)
                line = line.replace("@MANIFEST@", manifest)
                line = line.replace("@HOSTUSERNAME@", hostusername)
                line = line.replace("@CENGNURL@", cengnurl)
                if sourceslist:
                    line = line.replace("@fetch@", "true")
                    line = line.replace("@SOURCESLIST@", sourceslist)
                    line = line.replace("@DEBLIST@", deblist)
                    line = line.replace("@DSCLIST@", dsclist)
                message += line

        with open(localrc, "w") as wf:
            wf.write(message)

        # Copy stx-localrc file of builder container to pkgbuilder
        cmd = 'cp -f %s %s' % (localrc, pkgbuilder_configmap_dir)
        os.system(cmd)

        # Update the dependency charts
        cmd = 'helm dependency update ' + helmchartdir
        self.logger.debug('Dependency build command: %s', cmd)
        subprocess.call(cmd, shell=True)

        return repomgr_type

    def handleStartTask(self, helmstatus, projectname):
        cmd = 'helm install ' + projectname + ' ' + helmchartdir
        self.logger.debug('Execute the helm start command: %s', cmd)
        if helmstatus:
            self.logger.warning('The helm release %s already exists - nothing to do',
                                projectname)
        else:
            repomgr_type = self.finish_configure()
            subprocess.check_call(cmd, shell=True, cwd=os.environ['PRJDIR'])
            if repomgr_type == 'pulp':
                self.configurePulp()

    def handleStopTask(self, helmstatus, projectname):
        if helmstatus:
            cmd = 'helm uninstall ' + projectname
            self.logger.debug('Execute the helm stop command: %s', cmd)
            subprocess.check_call(cmd, shell=True)
        else:
            self.logger.warning('The helm release %s does not exist - nothing to do',
                                projectname)

    def handleUpgradeTask(self, helmstatus, projectname):
        command.check_prjdir_env()
        self.finish_configure()
        if helmstatus:
            cmd = 'helm upgrade ' + projectname + ' ' + helmchartdir
            self.logger.debug('Execute the upgrade command: %s', cmd)
            subprocess.call(cmd, shell=True, cwd=os.environ['PRJDIR'])
        else:
            self.logger.error('The helm release %s does not exist.',
                              projectname)
            sys.exit(1)

    def handleEnterTask(self, args):
        default_docker = 'builder'
        container_list = ['builder', 'pkgbuilder', 'repomgr', 'lat']
        prefix_exec_cmd = 'minikube -p $MINIKUBENAME kubectl -- exec -ti '

        if args.dockername:
            if args.dockername not in container_list:
                self.logger.error('Please input the correct docker name \
argument. eg: %s \n', container_list)
                sys.exit(1)
            default_docker = args.dockername

        podname = command.get_pod_name(default_docker)
        if podname:
            if default_docker == 'builder':
                cmd = prefix_exec_cmd + podname
                cmd = cmd + ' -- bash -l -c \'sudo -u ${MYUNAME} bash \
--rcfile /home/$MYUNAME/userenv\''
            else:
                cmd = prefix_exec_cmd + podname + ' -- bash'
            self.logger.debug('Execute the enter command: %s', cmd)
            # Return exit status to shell w/o raising an exception
            # in case the user did "echo COMMAND ARGS | stx control enter"
            ret = subprocess.call(cmd, shell=True)
            sys.exit(ret)
        else:
            self.logger.error('Please ensure the docker container you want to \
enter has been started!!!\n')
            sys.exit(1)

    def handleControl(self, args):

        self.logger.setLevel(args.loglevel)
        projectname = self.stxconfig.getConfig('project', 'name')
        if not projectname:
            projectname = 'stx'

        if args.ctl_task == 'start':
            self.handleStartTask(self.helm_status, projectname)

        elif args.ctl_task == 'stop':
            self.handleStopTask(self.helm_status, projectname)

        elif args.ctl_task == 'upgrade':
            self.handleUpgradeTask(self.helm_status, projectname)

        elif args.ctl_task == 'enter':
            self.handleEnterTask(args)

        elif args.ctl_task == 'status':
            command.get_helm_info()
            command.get_deployment_info()
            command.get_pods_info()

        else:
            self.logger.error('Control module doesn\'t support your \
subcommand: [%s].\n', args.ctl_task)
            print(helper.help_control())
