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
import os
import shlex
from stx.k8s import KubeHelper
from stx import utils  # pylint: disable=E0611
import subprocess
import sys

# Logger can only be initialized once globally, not in class constructor.
# FIXME: review/fix utils.set_logger()
logger = logging.getLogger('STX-Shell')
utils.set_logger(logger)


def quote(wordlist):
    if hasattr(wordlist, '__iter__') and not isinstance(wordlist, str):
        return ' '.join([shlex.quote(w) for w in wordlist])
    return shlex.quote(wordlist)


class HandleShellTask:

    def __init__(self, config):
        self.config = config
        self.k8s = KubeHelper(config)
        self.all_container_names = self.config.all_container_names()
        self.logger = logger

    def __get_container_name(self, container):
        if container not in self.config.all_container_names():
            raise NameError('Invalid container %s, expecting one of: %s'
                            % (container, self.all_container_names))
        name = self.k8s.get_pod_name(container)
        if not name:
            raise RuntimeError('Container "%s" is not running' % container)
        return name

    def create_shell_command(self, container, command, no_tty):
        kubectl_args = ['exec', '--stdin']

        if not no_tty and sys.stdin.isatty():
            kubectl_args += ['--tty']

        kubectl_args += [self.__get_container_name(container)]

        # builder
        if container == 'builder':

            # This environment script is always required
            req_env_file = '/home/$MYUNAME/userenv'

            user_cmd = 'runuser -u $MYUNAME -- '

            # Shells have a concept of "interactive mode", when enabled:
            # - define PS1 (prompt string, printed before every command)
            # - source ~/.bashrc or --rcfile on startup
            # - include "i" in "$-" shell var
            # This mode is automatically enabled with either "bash -i",
            # or if STDIN is a terminal.

            # No command given: interactive mode + source our own
            # env file instead of ~/.bashrc
            if command is None:
                user_cmd += 'bash --rcfile %s -i' % req_env_file
            # User provided a command to execute - shell may or may not run in
            # interactive mode, depending on STDIN being a terminal. If it's
            # not interactive, it won't source any rcfiles, so add an explicit
            # "source FILENAME" in front of user command, and disable rcfiles
            # to cover both situations.
            else:
                user_cmd += 'bash --norc -c '
                user_cmd += quote('source %s && { %s ; }' %
                                  (req_env_file, command.strip() or ':'))

            kubectl_args += ['--', 'bash', '-l', '-c', user_cmd]

        elif container == 'docker':
            kubectl_args += ['--', 'sh', '-l']
            if command:
                kubectl_args += ['-c', command]
        else:
            kubectl_args += ['--', 'bash', '-l']
            if command:
                kubectl_args += ['-c', command]

        return self.config.kubectl() + ' ' + quote(kubectl_args)

    def _do_shell(self, args, no_tty, command, container_arg='container'):
        container = getattr(args, container_arg) or 'builder'
        if container not in self.all_container_names:
            self.logger.error("--%s must be one of: %s",
                              container_arg, self.all_container_names)
            sys.exit(1)

        shell_command = self.create_shell_command(container, command, no_tty)
        self.logger.debug('Running command: %s', shell_command)
        shell_status = subprocess.call(shell_command, shell=True)
        sys.exit(shell_status)

    def cmd_shell(self, args):
        self.logger.setLevel(args.loglevel)
        self._do_shell(args, args.no_tty, args.command)

    def cmd_control_enter(self, args):
        self.logger.setLevel(args.loglevel)
        self.logger.warn("""This command is deprecated, please use "stx shell" instead""")
        self._do_shell(args, False, None, 'dockername')
