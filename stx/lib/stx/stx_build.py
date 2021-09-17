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

import logging
import subprocess
import sys

from stx import command  # pylint: disable=E0611
from stx import utils  # pylint: disable=E0611


class HandleBuildTask:
    '''Handle the task for the build sub-command'''

    def __init__(self):
        self.logger = logging.getLogger('STX-Build')
        utils.set_logger(self.logger)

    def buildImageCMD(self, args, prefixcmd):

        if args.type:
            if (args.type != 'rt' and args.type != 'std'):
                self.logger.error('Option -t for generaing image only should \
be [ rt|std ]')
                self.logger.error('Please use "stx build -h" to show the help\
\n')
                sys.exit(1)

            cmd = prefixcmd + '"build-image -t ' + args.type + '"\''
        else:
            cmd = prefixcmd + '"build-image"\''

        return cmd

    def buildDistroCMD(self, prefixcmd):

        cmd = prefixcmd + '"build-pkgs"\''
        return cmd

    def buildPrepareCMD(self, prefixcmd):

        cmd = prefixcmd + '". /usr/local/bin/stx/stx-prepare-build"\''
        return cmd

    def buildCleanupCMD(self, prefixcmd):

        cmd = prefixcmd + '". /usr/local/bin/stx/stx-cleanup"\''
        return cmd

    def buildPackageCMD(self, args, prefixcmd):

        if args.force:
            cmd = prefixcmd + '"build-pkgs -c -p ' + args.build_task + '"\''
        else:
            cmd = prefixcmd + '"build-pkgs -p ' + args.build_task + '"\''
        return cmd

    def handleBuild(self, args):

        self.logger.setLevel(args.loglevel)

        podname = command.get_pod_name('builder')
        if not podname:
            self.logger.error('The builder container does not exist, \
so please use the control module to start.')
            sys.exit(1)

        if args.build_task != 'prepare' and args.build_task != 'cleanup':

            bashcmd = '\'find /home/${MYUNAME}/prepare-build.done \
&>/dev/null\''
            cmd = command.generatePrefixCommand(podname, bashcmd, 0)

            ret = subprocess.call(cmd, shell=True)
            if ret != 0:
                self.logger.warning('****************************************\
******************************')
                self.logger.warning('The building env not be initialized yet!\
')
                self.logger.warning('Execute \'stx build prepare\' to finish \
the setup step before building')
                self.logger.warning('****************************************\
******************************')
                sys.exit(1)

        prefix_cmd = command.generatePrefixCommand(podname, '', 1)

        if args.build_task == 'image':
            cmd = self.buildImageCMD(args, prefix_cmd)
            self.logger.debug('Execute the generation image command: [%s]',
                              cmd)

        elif args.build_task == 'distro':
            cmd = self.buildDistroCMD(prefix_cmd)
            self.logger.debug('Execute the distro compiling command: [%s].',
                              cmd)

        elif args.build_task == 'prepare':
            cmd = self.buildPrepareCMD(prefix_cmd)
            self.logger.debug('Execute the prepare command: [%s].', cmd)

        elif args.build_task == 'cleanup':
            cmd = self.buildCleanupCMD(prefix_cmd)
            self.logger.debug('Execute the cleanup command: [%s].', cmd)

        else:
            cmd = self.buildPackageCMD(args, prefix_cmd)
            self.logger.debug('Compile the package: [%s] with the command \
[%s]', args.build_task, cmd)

        try:
            subprocess.check_call(cmd, shell=True)
        except subprocess.CalledProcessError as exc:
            raise Exception('Failed to build with the command [%s].\n \
Returncode: %s' % (cmd, exc.returncode))
