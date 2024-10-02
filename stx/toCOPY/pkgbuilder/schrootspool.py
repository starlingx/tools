# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Copyright (C) 2022 Wind River Systems,Inc
#
import logging
import os
import re
import subprocess
import utils

SCHROOTS_CONFIG = '/etc/schroot/chroot.d/'


def bytes_to_human_readable(size):
    if size < 1024:
        return f'{size}B'
    if size < 1024 * 1024:
        x = int(size / 102.4) / 10
        return f'{x}KB'
    if size < 1024 * 1024 * 1024:
        x = int(size / (1024 * 102.4)) / 10
        return f'{x}MB'
    if size < 1024 * 1024 * 1024 * 1024:
        x = int(size / (1024 * 1024 * 102.4)) / 10
        return f'{x}GB'
    x = int(size / (1024 * 1024 * 1024 * 102.4)) / 10
    return f'{x}TB'


# Define unit multipliers
unit_multipliers = {
    '': 1,          # No unit
    'B': 1,         # No unit
    'K': 1024,      # Kilobytes
    'KB': 1024,     # Kilobytes
    'M': 1024**2,   # Megabytes
    'MB': 1024**2,  # Megabytes
    'G': 1024**3,   # Gigabytes
    'GB': 1024**3,  # Gigabytes
    'T': 1024**4,   # Terabytes
    'TB': 1024**4,  # Terabytes
}


def human_readable_to_bytes(human_size):
    # Define a regular expression pattern to match size strings
    pattern = re.compile(r'(?P<value>[.\d]+)(?P<unit>[KMGTB]+?)', re.IGNORECASE)
    # Match the input string
    match = pattern.match(str(human_size).strip())
    if match:
        # Extract the value and unit
        value = match.group('value')
        unit = match.group('unit').upper()
    else:
        pattern = re.compile(r'(?P<value>[.\d]+)')
        match = pattern.match(str(human_size).strip())
        if not match:
            raise ValueError(f"Invalid size string: '{human_size}'")
        value = match.group('value')
        unit = "B"

    if unit not in unit_multipliers:
        raise ValueError(f"Unknown unit: '{unit}'")
    multiplier = int(unit_multipliers[unit])
    value = int(float(value) * multiplier)
    return value


def get_schroot_conf_path(name):
    # Get path to schroot config file
    schroot_config_lines = subprocess.run(['grep', '-r', '-l', '^[[]' + name + '[]]$', SCHROOTS_CONFIG],
                                          stdout=subprocess.PIPE,
                                          universal_newlines=True).stdout.splitlines()
    for line in schroot_config_lines:
        return line.strip()
    return None


class Schroot(object):
    def __init__(self, name, state='idle'):
        self.name = name
        self.state = state
        self.size = 0
        self.tmpfs = False

        self.path = self.get_chroot_dir()
        if self.path:
            statvfs = os.statvfs(self.path)
            self.size = statvfs.f_frsize * statvfs.f_bavail
            self.tmpfs = utils.is_tmpfs(self.path)

    def get_chroot_dir(self):
        # Get path to chroot
        schroot_config_lines = subprocess.run(['schroot', '--config', '--chroot', self.name],
                                              stdout=subprocess.PIPE,
                                              universal_newlines=True).stdout.splitlines()
        for line in schroot_config_lines:
            if line.startswith('directory='):
                return line.split('=')[1].strip()
        return ''

    def is_idle(self):
        if self.state == 'idle':
            return True
        return False

    def set_busy(self):
        self.state = 'work'

    def get_name(self):
        return self.name

    def get_size(self):
        return self.size

    def get_path(self):
        return self.path

    def get_state(self):
        return self.state

    def is_tmpfs(self):
        return self.tmpfs


class SchrootsPool(object):
    """
    schrootsPool manages all the schroots in current container
    The schroots listed by schroot --list will be registered
    and assigned the build task
    """
    def __init__(self, logger):
        self.schroots = []
        self.logger = logger

    def exists(self, name):
        for schroot in self.schroots:
            if schroot.name == name:
                return True
        return False

    def get_schroot_list(self):
        schroot_list = []
        for line in subprocess.run(['schroot', '--list'], stdout=subprocess.PIPE,
                                   universal_newlines=True).stdout.splitlines():
            schroot_list.append(line.split(':')[1].strip())
        return schroot_list

    def get_schroot_clone_list(self):
        schroot_clone_list = []
        for schroot_name in self.get_schroot_list():
            if len(schroot_name.split('-')) >= 4:
                schroot_clone_list.append(schroot_name)
        return schroot_clone_list

    def get_schroot_parent(self):
        for schroot_name in self.get_schroot_list():
            if len(schroot_name.split('-')) < 4:
                return schroot_name
        self.logger.error('parent schroot not found')
        raise ValueError('parent schroot not found')

    def load(self):
        self.schroots = []
        schroots = self.get_schroot_clone_list()
        if len(schroots) < 1:
            self.logger.error('There are no schroots found, exit')
            return False
        for name in schroots:
            if not self.exists(name):
                self.schroots.append(Schroot(name, 'idle'))
        return True

    def acquire(self, needed_size=1, allow_tmpfs=True):
        self.logger.debug("schroot pool status:")
        self.show()
        needed_size_bytes = human_readable_to_bytes(needed_size)
        if allow_tmpfs:
            # tmpfs is allowed. Try to find an idle tmpfs build environment.
            for schroot in self.schroots:
                if schroot.is_idle() and schroot.is_tmpfs() and (needed_size_bytes <= schroot.get_size()):
                    schroot.set_busy()
                    self.logger.debug('%s has been assigned', schroot.name)
                    return schroot.name

        # Find any suitable build environment that is idle
        for schroot in self.schroots:
            if schroot.is_idle() and (needed_size_bytes <= schroot.get_size()):
                if allow_tmpfs or not schroot.is_tmpfs():
                    schroot.set_busy()
                    self.logger.debug('%s has been assigned', schroot.name)
                    return schroot.name
        self.logger.debug("No idle schroot can be used")
        self.show()
        return None

    def release(self, name):
        for schroot in self.schroots:
            if schroot.name == name.strip():
                # Fixme, whether need to end session here
                schroot.state = 'idle'
                self.logger.debug('%s has been released', name)

    def is_tmpfs(self, name):
        for schroot in self.schroots:
            if schroot.name == name.strip():
                # Fixme, whether need to end session here
                return schroot.is_tmpfs()
        return False

    def get_busy(self):
        busy_schroots = []
        for schroot in self.schroots:
            schroot_name = schroot.get_name()
            if schroot.is_idle():
                continue
            busy_schroots.append(schroot_name)
            self.logger.warning('schroot %s is busy and can not be refreshed', schroot_name)
        return busy_schroots

    def get_idle(self):
        idle_schroots = []
        for schroot in self.schroots:
            schroot_name = schroot.get_name()
            if not schroot.is_idle():
                continue
            idle_schroots.append(schroot_name)
            self.logger.debug('schroot %s is idle and can be refreshed', schroot_name)
        return idle_schroots

    def release_all(self):
        for schroot in self.schroots:
            # Fixme, whether need to end session here
            schroot.state = 'idle'
        self.logger.debug('All chroots have been released')

    def show(self):
        for schroot in self.schroots:
            self.logger.info("schroot name:%s state:%s tmpfs:%s size:%s path=%s",
                             schroot.get_name(), schroot.get_state(),
                             schroot.is_tmpfs(), bytes_to_human_readable(schroot.get_size()),
                             schroot.get_path())


if __name__ == "__main__":
    """
    For unit tests
    """
    logger = logging.getLogger('schrootPool')
    logger.setLevel(logging.DEBUG)

    schroots_pool = SchrootsPool(logger)
    schroots_pool.load()
    s0 = schroots_pool.acquire()
    s1 = schroots_pool.acquire()
    s2 = schroots_pool.acquire()
    schroots_pool.show()
    schroots_pool.release(s0)
    schroots_pool.release(s1)
    schroots_pool.show()
