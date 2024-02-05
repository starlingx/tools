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
#
import logging
from stx import utils  # pylint: disable=E0611
import subprocess
import tempfile

logger = logging.getLogger('STX-k8s')
utils.set_logger(logger)


class KubeHelper:
    """Common k8s commands"""

    """Constructor:
    :param config: an instance of stx.config.Config
    """
    def __init__(self, config):
        self.config = config

    def get_pods_info(self):
        '''Get all pods information of the stx building tools.'''

        cmd = self.config.kubectl() + ' get pods '
        logger.info('stx-tools pods list:')
        subprocess.check_call(cmd, shell=True)

    def get_deployment_info(self):
        '''Get all deployment information of the stx building tools.'''

        cmd = self.config.kubectl() + ' get deployment'
        logger.info('stx-tools deployments list:')
        subprocess.check_call(cmd, shell=True)

    def get_helm_info(self):
        '''Get the helm list information of the stx building tools.'''

        cmd = self.config.helm() + ' ls'
        logger.info('helm list:\n')
        subprocess.check_call(cmd, shell=True)

    def get_helm_pods(self):
        '''Get currently-running pods associated with our helm project.

        Returns a dict of dicts:
            {
                "NAME": { "status": "...", ...},
                "..."
            }
        where NAME is the name of the pod, and status is its k8s status, such
        as "Running"

        Search for pods in the correct namespace:
        - minikube: always "default" in minikube, ie each project uses its own
          isolated minikube profile/instance
        - vanilla k8s: namespace is required and is defined by the env var
          STX_K8S_NAMESPACE

        All such pods have a label, app.kubernetes.io/instance=<project>
        where project is the value of project.name from stx.conf, and is
        set by "helm install" in a roundabout way.

        '''

        project_name = self.config.get('project', 'name')
        with tempfile.NamedTemporaryFile(mode='w+', encoding='utf-8', prefix='stx-get_helm_pods',
                                         suffix='.stderr') as stderr_file:
            cmd = f'{self.config.kubectl()} get pods --no-headers'
            cmd += f' --selector=app.kubernetes.io/instance={project_name} 2>{stderr_file.name}'
            process_result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
            if process_result.returncode != 0:
                logger.error('Command failed: %s\n%s', cmd, stderr_file.fread())
                raise RuntimeError("Failed to list pods")

            # command prints multiple lines "NAME READY STATUS RESTART AGE"
            # Example:
            #   stx-stx-builder-7f8bfc79cd-qtgcw 1/1 Running 0 36s
            result = {}
            for line in process_result.stdout.splitlines():
                words = line.split()
                if len(words) < 5:
                    raise RuntimeError("Unexpected output from command <%s>" % cmd)
                rec = {
                    'status': words[2]
                }
                result[words[0]] = rec
            return result

    def get_pod_name(self, dockername):
        '''get the detailed pod name from the four pods.'''

        if dockername == "lat":
            dockername = dockername + "-tool"

        selector = 'app.kubernetes.io/instance=%s,app.kubernetes.io/name=%s' \
            % (self.config.project_name, 'stx-' + dockername)
        cmd = self.config.kubectl() + f" get pods --selector '{selector}'" + \
            " | awk '$3 == \"Running\" {print $1}' | tail -n 1"
        logger.info('Running: %s', cmd)
        output = subprocess.check_output(cmd, shell=True)
        podname = str(output.decode('utf8').strip())

        return podname

    def helm_release_exists(self, projectname):
        '''Check if the helm release exists'''

        cmd = self.config.helm() + " ls | awk '{ print $1 }' | grep '^" + projectname + "$'"
        ret = subprocess.getoutput(cmd)
        if ret:
            return True
        else:
            return False

    def generatePrefixCommand(self, podname, command, enableuser, interactive=False):
        '''Generate the command executed in the host'''

        prefix_exec_cmd = self.config.kubectl() + ' exec -ti '
        builder_exec_cmd = prefix_exec_cmd + podname
        prefix_bash_cmd = ' -- bash -l -c '
        prefix_bash_with_user_cmd = ' -- bash -l -c \'sudo -u ${MYUNAME} \
    BASH_ENV=/home/$MYUNAME/userenv bash --rcfile /home/$MYUNAME/userenv -c '
        prefix_bash_with_interactive_user_cmd = ' -- bash -l -i -c \'sudo -u ${MYUNAME} bash \
    --rcfile /home/$MYUNAME/userenv -i -c '
        builder_exec_bash_cmd = builder_exec_cmd + prefix_bash_cmd
        builder_exec_bash_with_user_cmd = builder_exec_cmd + \
            prefix_bash_with_user_cmd
        builder_exec_bash_with_interactive_user_cmd = builder_exec_cmd + \
            prefix_bash_with_interactive_user_cmd

        if enableuser:
            if interactive:
                cmd = builder_exec_bash_with_interactive_user_cmd + command
            else:
                cmd = builder_exec_bash_with_user_cmd + command
        else:
            cmd = builder_exec_bash_cmd + command

        return cmd
