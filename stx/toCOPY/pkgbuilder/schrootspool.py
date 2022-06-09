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
import subprocess

SCHROOTS_CONFIG = '/etc/schroot/chroot.d/'


class Schroot:
    def __init__(self, name, state='idle'):
        self.name = name
        self.state = state

    def is_idle(self):
        if self.state == 'idle':
            return True
        return False

    def set_busy(self):
        self.state = 'work'

    def get_name(self):
        return self.name


class SchrootsPool:
    """
    schrootsPool manages all the schroots in current container
    The schroots listed by schroot -l will be registered
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

    def load(self):
        schroots = subprocess.run(['schroot', '-l'], stdout=subprocess.PIPE,
                                  universal_newlines=True).stdout.splitlines()
        if len(schroots) < 1:
            self.logger.error('There are no schroots found, exit')
            return False
        for sname in schroots:
            # Filter 'chroot:bullseye-amd64-<user>' as the backup chroot
            if len(sname.split('-')) >= 4 and not self.exists(sname):
                self.schroots.append(Schroot(sname.strip(), 'idle'))
        return True

    def apply(self):
        self.logger.debug("schroot pool status:")
        self.show()
        for schroot in self.schroots:
            if schroot.is_idle():
                schroot.set_busy()
                self.logger.debug('%s has been assigned', schroot.name)
                return schroot.name
        self.logger.debug("No idle schroot can be used")
        return None

    def release(self, name):
        for schroot in self.schroots:
            if schroot.name == name.strip():
                # Fixme, whether need to end session here
                schroot.state = 'idle'
                self.logger.debug('%s has been released', name)

    def get_idle(self):
        idle_schroots = []
        for schroot in self.schroots:
            schroot_name = schroot.get_name()
            if not schroot.is_idle():
                self.logger.error('schroot %s is busy and can not be refreshed', schroot_name)
                continue
            idle_schroots.append(schroot_name)
            self.logger.debug('schroot %s is idle and can be refreshed', schroot_name)
        return idle_schroots

    def release_all(self):
        for schroot in self.schroots:
            # Fixme, whether need to end session here
            schroot.state = 'idle'
        self.logger.debug('All chroots has been released')

    def show(self):
        for schroot in self.schroots:
            self.logger.info("schroot name:%s state:%s", schroot.name, schroot.state)


if __name__ == "__main__":
    """
    For unit tests
    """
    logger = logging.getLogger('schrootPool')
    logger.setLevel(logging.DEBUG)

    schroots_pool = SchrootsPool(logger)
    schroots_pool.load()
    s0 = schroots_pool.apply()
    s1 = schroots_pool.apply()
    s2 = schroots_pool.apply()
    schroots_pool.show()
    schroots_pool.release(s0)
    schroots_pool.release(s1)
    schroots_pool.show()
