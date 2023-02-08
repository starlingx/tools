#
# Copyright (c) 2022 Wind River Systems, Inc.
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
import os
import re

from stx import stx_configparser
from stx import utils

logger = logging.getLogger('STX-Config')
utils.set_logger(logger)

ALL_CONTAINER_NAMES = ['builder', 'builder-files-http', 'pkgbuilder', 'lat', 'docker', 'repomgr']


def require_env(var):
    value = os.getenv(var)
    if value is None:
        logger.error(
            f'{var} not found in the environment')
        logger.error(
            'Please source the file \'import-stx\' to define the ' +
            f'{var} variable and execute \'stx-init-env\' to start builder pods')
        raise LookupError(f'{var} not found in the environment!')
    return value


class Config:
    """Configuration interface.

    This class provides a read-only interface to project
    configuration.

    Usage
    =====
    ::
        from stx import config

        # load once
        config = Config().load()

        # use this instance throughout the app
        value = config.get ('section', 'key')

        # returns "minikube -p $PROFILE kubectl -n $NAMESPACE --"
        # or similar
        # kubectl_command = config.kubectl()
    """

    def __init__(self):
        """Construct an empty instance; must call "load" explicitly before using"""
        self.prjdir = require_env('PRJDIR')
        self.config_filename = os.path.join(self.prjdir, 'stx.conf')
        self.use_minikube = os.getenv('STX_PLATFORM', 'minikube') == 'minikube'
        if self.use_minikube:
            self.minikube_profile = require_env('MINIKUBENAME')
        else:
            self.k8s_namespace = os.getenv('STX_K8S_NAMESPACE')

        self.build_home = require_env('STX_BUILD_HOME')
        self.docker_tag = require_env('DOCKER_TAG_LOCAL')
        self.kubectl_cmd = None
        self.helm_cmd = None

        reg_list_str = os.getenv('STX_INSECURE_DOCKER_REGISTRIES')
        if reg_list_str:
            self._insecure_docker_reg_list = re.split(r'[ \t;,]+', reg_list_str)
        else:
            self._insecure_docker_reg_list = []

        self._container_mtu = os.getenv('STX_CONTAINER_MTU')

    def load(self):
        """Load stx.conf"""
        self.data = stx_configparser.STXConfigParser(self.config_filename)
        self._init_kubectl_cmd()
        return self

    def get(self, section, key):
        """Get a config value"""
        assert self.data
        return self.data.getConfig(section, key)

    def impl(self):
        """Internal object that stores configuration"""
        return self.data

    def prjdir(self):
        """Path of starlingx/tools checkout"""
        return self.prjdir

    def kubectl(self):
        """Returns the command for invoking kubect"""
        assert self.data
        return self.kubectl_cmd

    def helm(self):
        """Returns the command for invoking helm"""
        assert self.data
        return self.helm_cmd

    def all_container_names(self):
        return ALL_CONTAINER_NAMES + []

    @property
    def insecure_docker_reg_list(self):
        """List of insecure docker registries we are allowed to access"""
        return self._insecure_docker_reg_list

    @property
    def container_mtu(self):
        """Container network MTU value"""
        return self._container_mtu

    @property
    def project_name(self):
        return self.get('project', 'name')

    def _init_kubectl_cmd(self):
        # helm
        if self.use_minikube:
            self.helm_cmd = f'helm --kube-context {self.minikube_profile}'
        else:
            self.helm_cmd = 'helm'
        # kubectl
        if self.use_minikube:
            self.kubectl_cmd = f'minikube -p {self.minikube_profile} kubectl --'
        else:
            self.kubectl_cmd = 'kubectl'
            # Kubernetes namespace
            if self.k8s_namespace:
                self.kubectl_cmd += f' -n {self.k8s_namespace}'
                self.helm_cmd += f' -n {self.k8s_namespace}'
