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
from stx import command  # pylint: disable=E0611
from stx import utils  # pylint: disable=E0611
import subprocess


logger = logging.getLogger('STX-Repomgr')
utils.set_logger(logger)


def handleRepomgr(args):
    '''Sync the repo '''

    logger.setLevel(args.loglevel)
    logger.debug('Execute the repomgr command: [%s]', args.repomgr_task)

    podname = command.get_pod_name('builder')
    if not podname:
        logger.error('The builder container does not exist, so please \
                     consider to use the control module')

    prefix_cmd = command.generatePrefixCommand(podname, '', 1)
    cmd = prefix_cmd + '"repo_manage.py ' + args.repomgr_task + '"\''
    logger.debug('Manage the repo with the command [%s]', cmd)

    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as exc:
        raise Exception('Failed to manage the repo with the command [%s].\n \
Returncode: %s' % (cmd, exc.returncode))
