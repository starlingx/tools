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
from stx import k8s
from stx import utils
import subprocess
import traceback

logger = logging.getLogger('STX-Cleanup')
utils.set_logger(logger)


class HandleCleanupTask:

    def __init__(self, config, shell):
        self.config = config
        self.k8s = k8s.KubeHelper(config)
        self.shell = shell
        self.logger = logger

    def cleanup_docker(self, args):
        self.logger.info("Cleaning up docker")
        cmd = "docker system prune --volumes"
        if args.force:
            cmd += " --force"
        shell_cmd = self.shell.create_shell_command('docker', cmd, no_tty=False)
        if not args.dry_run:
            self.logger.debug('Running command: %s', shell_cmd)
            subprocess.run(shell_cmd, shell=True, check=True)
        else:
            self.logger.debug('Would run command: %s', shell_cmd)

    def cleanup_minikube(self, args):
        self.logger.info("Cleaning up minikube docker")
        cmd = self.config.minikube_docker() + " system prune --volumes"
        if args.force:
            cmd += " --force"
        shell_cmd = cmd
        if not args.dry_run:
            self.logger.debug('Running command: %s', shell_cmd)
            subprocess.run(shell_cmd, shell=True, check=True)
        else:
            self.logger.debug('Would run command: %s', shell_cmd)

    def cleanup_default(self, args):

        failed = False

        # cleanup docker pod
        try:
            if self.__container_is_running('docker'):
                self.cleanup_docker(args)
            else:
                self.logger.info('docker container not running, skipping clean up')
        except subprocess.CalledProcessError:
            traceback.print_exc()
            failed = True

        # cleanup minikube's docker
        try:
            if self.config.use_minikube:
                self.cleanup_minikube(args)
            else:
                self.logger.info('minikube not in use, skipping minikube clean up')
        except subprocess.CalledProcessError:
            traceback.print_exc()
            failed = True

        # multiple errors
        if failed:
            raise RuntimeError("one or more cleanup commands failed")

    def __container_is_running(self, name):
        return bool(self.k8s.get_pod_name(name))

    def __add_common_args(self, p):
        p.add_argument(
            '-f', '--force', help="Don't prompt for confirmation",
            action='store_const', const=True)
        p.add_argument(
            '-n', '--dry-run', help="Log shell commands without executing them",
            action='store_const', const=True)

    def add_parser(self, subparsers):

        # stx cleanup
        cleanup_parser = subparsers.add_parser(
            'cleanup',
            help='Cleanup various things',
            usage='stx cleanup [--force] [--dry-run] [docker|minikube]',
            epilog='With no arguments clean everything'
        )
        self.__add_common_args(cleanup_parser)
        cleanup_parser.set_defaults(handle=self.cleanup_default)
        cleanup_subparsers = cleanup_parser.add_subparsers()

        # stx cleanup docker
        cleanup_docker_parser = cleanup_subparsers.add_parser(
            'docker',
            help='Delete cache & orphans in builder docker demon')
        self.__add_common_args(cleanup_docker_parser)
        cleanup_docker_parser.set_defaults(handle=self.cleanup_docker)

        # stx cleanup minikube
        cleanup_minikube_parser = cleanup_subparsers.add_parser(
            'minikube',
            help='Delete cache & orphans in minikube\'s docker demon')
        self.__add_common_args(cleanup_minikube_parser)
        cleanup_minikube_parser.set_defaults(handle=self.cleanup_minikube)
