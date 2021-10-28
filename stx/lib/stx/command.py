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
from stx import utils  # pylint: disable=E0611
import subprocess
import sys

logger = logging.getLogger('STX-Command')
utils.set_logger(logger)


def check_prjdir_env():
    prjdir_value = os.getenv('PRJDIR', '')
    if not prjdir_value:
        logger.warning('Please source the file stx-init-env to export the \
PRJDIR variable.')
        logger.warning('If the minikube had already started, please source \
the file import-stx instead.')
        sys.exit(0)


def get_pods_info():
    '''Get all pods information of the stx building tools.'''

    cmd = 'minikube -p $MINIKUBENAME kubectl -- get pods '
    logger.info('stx-tools pods list:')
    subprocess.check_call(cmd, shell=True)


def get_deployment_info():
    '''Get all deployment information of the stx building tools.'''

    cmd = 'minikube -p $MINIKUBENAME kubectl -- get deployment'
    logger.info('stx-tools deployments list:')
    subprocess.check_call(cmd, shell=True)


def get_helm_info():
    '''Get the helm list information of the stx building tools.'''

    cmd = 'helm ls'
    logger.info('helm list:\n')
    subprocess.check_call(cmd, shell=True)


def get_pod_name(dockername):
    '''get the detailed pod name from the four pods.'''

    cmd = 'minikube -p $MINIKUBENAME kubectl -- get pods | grep Running| \
grep stx-' + dockername + ' | awk \'{print $1}\' '
    output = subprocess.check_output(cmd, shell=True)
    podname = str(output.decode('utf8').strip())

    return podname


def helm_release_exists(projectname):
    '''Check if the helm release exists'''

    cmd = 'helm ls | grep ' + projectname
    ret = subprocess.getoutput(cmd)
    if ret:
        return True
    else:
        return False


def generatePrefixCommand(podname, command, enableuser):
    '''Generate the command executed in the host'''

    prefix_exec_cmd = 'minikube -p $MINIKUBENAME kubectl -- exec -ti '
    builder_exec_cmd = prefix_exec_cmd + podname
    prefix_bash_cmd = ' -- bash -l -c '
    prefix_bash_with_user_cmd = ' -- bash -l -c \'sudo -u ${MYUNAME} bash \
--rcfile /home/$MYUNAME/userenv -i -c '
    builder_exec_bash_cmd = builder_exec_cmd + prefix_bash_cmd
    builder_exec_bash_with_user_cmd = builder_exec_cmd + \
        prefix_bash_with_user_cmd

    if enableuser:
        cmd = builder_exec_bash_with_user_cmd + command
    else:
        cmd = builder_exec_bash_cmd + command

    return cmd
