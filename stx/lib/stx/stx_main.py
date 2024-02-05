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

import argparse
import logging

from stx import config
from stx import stx_build  # pylint: disable=E0611
from stx import stx_cleanup  # pylint: disable=E0611
from stx import stx_configparser  # pylint: disable=E0611
from stx import stx_control  # pylint: disable=E0611
from stx import stx_repomgr  # pylint: disable=E0611
from stx import stx_shell  # pylint: disable=E0611
from stx import utils  # pylint: disable=E0611

logger = logging.getLogger('STX')
utils.set_logger(logger)


class STXMainException(Exception):
    pass


class CommandLine:
    '''Handles parsing the commandline parameters for stx tool'''

    def __init__(self):
        self.config = config.Config().load()
        self.handleconfig = stx_configparser.HandleConfigTask(self.config)
        self.handlecontrol = stx_control.HandleControlTask(self.config)
        self.handlebuild = stx_build.HandleBuildTask(self.config)
        self.handlerepomgr = stx_repomgr.HandleRepomgrTask(self.config)
        self.handleshell = stx_shell.HandleShellTask(self.config)
        self.handlecleanup = stx_cleanup.HandleCleanupTask(self.config, self.handleshell)
        self.parser = self.parseCommandLine()

    def parseCommandLine(self):
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter,
            add_help=False,
            description='STX Build Tool',
            epilog='''Tips:
Use %(prog)s --help to get help for all of parameters\n\n''')

        subparsers = parser.add_subparsers(title='Builtin Commands:',
                                           help='sub-command for stx\n\n')

        control_subparser = subparsers.add_parser('control',
                                                  help='Execute the control \
task.\t\teg: [start|enter|stop|is-started|status|upgrade|keys-add]')
        control_subparser.add_argument('ctl_task',
                                       help='[ start|stop|enter|status|upgrade\
                                       |keys-add ]: Create or Stop or Enter or \
                                       List or Upgrade or Add keys on \
                                       the stx-builder/obs/lat/pulp \
                                       containers.\n\n')
        control_subparser.add_argument('--dockername',
                                       help='[ builder|pkgbuilder|repomgr|' +
                                       'lat|docker|builder-files-http ]: ' +
                                       'container name to enter, ' +
                                       'default: builder\n\n',
                                       required=False)
        control_subparser.add_argument('--key-type',
                                       help='[ signing-server ]: ' +
                                       'key-type name to enter, ' +
                                       'default: signing-server\n\n',
                                       required=False)
        control_subparser.add_argument('--key',
                                       help='key file to enter, ' +
                                       'default: ~/.ssh/id_rsa\n\n',
                                       required=False)
        control_subparser.add_argument('--wait',
                                       help='wait for operation to finish, ' +
                                       'for start, stop\n\n',
                                       action='store_true')
        control_subparser.set_defaults(handle=self.handlecontrol.handleControl)

        config_subparser = subparsers.add_parser('config',
                                                 help='Change stx config \
settings.\t\teg: [ --show|--get|--add|--unset|--remove-section|--upgrade ]')
        config_subparser.add_argument('--show',
                                      help='Show all the content of the config\
                                      file\n\n', action='store_true')
        config_subparser.add_argument('--add',
                                      help='Add the setting section.key and \
                                      value into the config file.\n\n',
                                      nargs=2, required=False)
        config_subparser.add_argument('--get',
                                      help='Get the value of the section.key \
                                      from the config file.\n\n', nargs=1,
                                      required=False)
        config_subparser.add_argument('--unset',
                                      help='Remove value of the section.key \
                                      from the config file.\n\n', nargs=1,
                                      required=False)
        config_subparser.add_argument('--removesection',
                                      help='Remove the section from the \
                                      config file.\n\n', nargs=1,
                                      required=False)
        config_subparser.add_argument('--upgrade',
                                      help='Upgrade stx.conf',
                                      action='store_true')
        config_subparser.set_defaults(handle=self.handleconfig.handleConfig)

        build_subparser = subparsers.add_parser('build',
                                                help='Run to build packages or\
image.\t\teg: [ prepare|layer|image|download|world|${pkgname}]')
        build_subparser.add_argument('build_task',
                                     help='[ prepare|cleanup|layer|image|' +
                                     'download|world|${pkgname} ]:\
                                     Prepare for building enviroment and \
                                     build packages, distro layer or image.\
                                     \n\n')
        build_subparser.add_argument('-b', '--download-binary',
                                     help="download binary debs",
                                     action='store_true', required=False)
        build_subparser.add_argument('-e', '--exit-on-fail',
                                     help="Exit for any failure.",
                                     action='store_true', required=False)
        build_subparser.add_argument('-f', '--force',
                                     help='Force to execute the task again.',
                                     action='store_true', required=False)
        build_subparser.add_argument('-l', '--layers',
                                     help='[ flock|distro ]: Compile the \
                                     packages for the layer.', required=False)
        build_subparser.add_argument('-s', '--download-source',
                                     help="download starlingx source recipes",
                                     action='store_true', required=False)
        build_subparser.add_argument('-t', '--buildtype',
                                     help='[ rt|std ]: Select the build type.\
                                     ', required=False)
        build_subparser.add_argument('--enable-test',
                                     help='Enable the automatic test for \
                                     the package building.',
                                     action='store_true', required=False)
        build_subparser.set_defaults(handle=self.handlebuild.handleBuild)

        repo_subparser = subparsers.add_parser('repomgr',
                                               help='Manage source|binary \
packages.\t\teg: [ list|list_pkgs|download|sync|mirror|clean|\
remove_repo|search_pkg|upload_pkg|delete_pkg ]')
        repo_subparser.add_argument('repomgr_task',
                                    help='[ list|list_pkgs|download|sync|\
                                    merge|mirror|clean|remove_repo|search_pkg|\
                                    upload_pkg|delete_pkg ]: \
                                    Execute the management task.\n\n')
        # Pass remaining arguements into repo_manage.py for additional processing
        repo_subparser.add_argument('args', nargs=argparse.REMAINDER)
        repo_subparser.set_defaults(handle=self.handlerepomgr.handleCommand)

        # stx shell
        shell_subparser = subparsers.add_parser(
            'shell',
            help='Run a shell command or start an interactive shell')
        shell_subparser.add_argument(
            '-c', '--command',
            help='Shell snippet to execute inside a container. If omitted ' +
                 'start a shell that reads commands from STDIN.')
        shell_subparser.add_argument(
            '--no-tty',
            help="Disable terminal emulation for STDIN and start shell in " +
                 "non-interactive mode, even if STDIN is a TTY",
            action='store_const', const=True)
        shell_subparser.add_argument(
            '--container',
            metavar='builder|pkgbuilder|lat|repomgr|docker|builder-files-http',
            help='Container name (default: builder)')
        shell_subparser.set_defaults(handle=self.handleshell.cmd_shell)

        # stx cleanup
        self.handlecleanup.add_parser(subparsers)

        # common args
        parser.add_argument('-d', '--debug',
                            help='Enable debug output\n\n',
                            action='store_const', const=logging.DEBUG,
                            dest='loglevel', default=logging.INFO)

        parser.add_argument('-h', '--help',
                            help='Show this help message and exit\n\n',
                            action='help')

        parser.add_argument('-q', '--quiet',
                            help='Hide all output except error messages\n\n',
                            action='store_const', const=logging.ERROR,
                            dest='loglevel')

        parser.add_argument('-v', '--version',
                            help='Stx build tools version\n\n',
                            action='version', version='%(prog)s 1.0.0')

        return parser

    def parseArgs(self):
        args = self.parser.parse_args()
        logger.setLevel(args.loglevel)
        return args


def stx_main():
    command_line = CommandLine()
    args = command_line.parseArgs()

    if hasattr(args, 'handle'):
        args.handle(args)
    else:
        command_line.parser.print_help()

    return 0
