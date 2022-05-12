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

from stx.k8s import KubeHelper
from stx import utils  # pylint: disable=E0611

STX_BUILD_TYPES = ['rt', 'std']
STX_LAYERS = ['distro', 'flock']


class HandleBuildTask:
    '''Handle the task for the build sub-command'''

    def __init__(self, config):
        self.config = config
        self.k8s = KubeHelper(config)
        self.logger = logging.getLogger('STX-Build')
        utils.set_logger(self.logger)

    def buildImageCMD(self, args, prefixcmd):

        if args.buildtype:
            if args.buildtype not in STX_BUILD_TYPES:
                self.logger.error('Option "-t|--buildtype" for generating ' +
                                  'image only should be %s.', STX_BUILD_TYPES)
                self.logger.error('Please use "stx build -h" to show the help')
                sys.exit(1)

            if args.buildtype == 'std':
                build_type_opt = "--std"
            elif args.buildtype == 'rt':
                build_type_opt = "--rt"
            else:
                build_type_opt = ''

            cmd = prefixcmd + '"build-image ' + build_type_opt + '"\''
        else:
            cmd = prefixcmd + '"build-image"\''

        return cmd

    def buildLayerCMD(self, args, prefixcmd):

        cmd = prefixcmd + '"build-pkgs '
        if not args.layers:
            self.logger.error('Must use "-l|--layers" option for layer ' +
                              'building.')
            sys.exit(1)

        if args.layers not in STX_LAYERS:
            self.logger.error('Option "-l|--layers" for layer building ' +
                              'only should be %s.', STX_LAYERS)
            self.logger.error('Please use "stx build -h" to show the help')
            sys.exit(1)

        cmd = cmd + '--layers ' + args.layers + ' '

        if args.exit_on_fail:
            cmd = cmd + '--exit_on_fail '

        if args.force:
            cmd = cmd + '--clean '

        if args.enable_test:
            cmd = cmd + '--test '

        cmd = cmd + '"\''
        return cmd

    def buildPrepareCMD(self, prefixcmd):

        cmd = prefixcmd + '". /usr/local/bin/stx/stx-prepare-build"\''
        return cmd

    def buildCleanupCMD(self, prefixcmd):

        cmd = prefixcmd + '". /usr/local/bin/stx/stx-cleanup"\''
        return cmd

    def buildDownloadCMD(self, args, prefixcmd):

        cmd = prefixcmd + '"downloader '

        if args.download_binary:
            cmd = cmd + '--download_binary '
        elif args.download_source:
            cmd = cmd + '--download_source '
        else:
            cmd = cmd + '--download_binary --download_source '

        if args.force:
            cmd = cmd + '--clean_mirror '

        if args.buildtype:
            cmd = cmd + f'-B {args.buildtype} '

        cmd = cmd + '"\''
        return cmd

    def buildPackageCMD(self, args, prefixcmd, world):

        if world:
            cmd = prefixcmd + '"build-pkgs -a '
        else:
            cmd = prefixcmd + '"build-pkgs -p ' + args.build_task + ' '

        if args.exit_on_fail:
            cmd = cmd + '--exit_on_fail '

        if args.force:
            cmd = cmd + '--clean '

        if args.enable_test:
            cmd = cmd + '--test '

        if args.buildtype:
            cmd = cmd + f'-b {args.buildtype} '

        cmd = cmd + '"\''
        return cmd

    def handleBuild(self, args):

        self.logger.setLevel(args.loglevel)

        podname = self.k8s.get_pod_name('builder')
        if not podname:
            self.logger.error('The builder container does not exist, ' +
                              'so please use the control module to start.')
            sys.exit(1)

        if args.build_task != 'prepare' and args.build_task != 'cleanup':

            bashcmd = "\'find /home/${MYUNAME}/prepare-build.done "
            bashcmd += "&>/dev/null\'"
            cmd = self.k8s.generatePrefixCommand(podname, bashcmd, 0)

            ret = subprocess.call(cmd, shell=True)
            if ret != 0:
                self.logger.warning('***********************************' +
                                    '***********************************')
                self.logger.warning('The building env not be initialized yet!')
                self.logger.warning('Execute \'stx build prepare\' to ' +
                                    'finish the setup step before building')
                self.logger.warning('***********************************' +
                                    '***********************************')
                sys.exit(1)

        prefix_cmd = self.k8s.generatePrefixCommand(podname, '', 1, 1)

        if args.build_task == 'image':
            cmd = self.buildImageCMD(args, prefix_cmd)
            self.logger.debug('Execute the generation image command: [%s]',
                              cmd)

        elif args.build_task == 'layer':
            cmd = self.buildLayerCMD(args, prefix_cmd)
            self.logger.debug('Execute the layer compiling command: [%s].',
                              cmd)

        elif args.build_task == 'prepare':
            cmd = self.buildPrepareCMD(prefix_cmd)
            self.logger.debug('Execute the prepare command: [%s].', cmd)

        elif args.build_task == 'cleanup':
            cmd = self.buildCleanupCMD(prefix_cmd)
            self.logger.debug('Execute the cleanup command: [%s].', cmd)

        elif args.build_task == 'download':
            cmd = self.buildDownloadCMD(args, prefix_cmd)
            self.logger.debug('Execute the download command: [%s].', cmd)

        elif args.build_task == 'world':
            cmd = self.buildPackageCMD(args, prefix_cmd, True)
            self.logger.debug('Execute the build world command: [%s].', cmd)

        else:
            cmd = self.buildPackageCMD(args, prefix_cmd, False)
            self.logger.debug('Compile the package: [%s] with the command ' +
                              '[%s]', args.build_task, cmd)

        try:
            subprocess.check_call(cmd, shell=True)
        except subprocess.CalledProcessError as exc:
            raise Exception('Failed to build with the command [%s].\n' +
                            'Returncode: %s' % cmd, exc.returncode)
