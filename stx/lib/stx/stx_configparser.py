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


import configparser
import logging
import os
import re
from stx import helper  # pylint: disable=E0611
from stx import utils   # pylint: disable=E0611
import sys

logger = logging.getLogger('STX-Config-Parser')
utils.set_logger(logger)


class STXConfigParser:

    def __init__(self, filepath=None):
        if filepath:
            configpath = filepath
        else:
            configpath = os.path.join(os.environ['PRJDIR'], "stx.conf")

        self.configpath = configpath
        self.cf = configparser.ConfigParser()
        self.cf.read(self.configpath, encoding="utf-8")

    def showAll(self):
        '''Output all of contents of the configfile'''

        sections = self.cf.sections()
        logger.info("The config file as follows:")
        print("[section]")
        print("('key' = 'value')")
        for section in sections:
            print("\r")
            print("[%s]" % section)
            items = self.cf.items(section)
            for item in items:
                print("%s" % str(item).replace(',', ' ='))

    def getConfig(self, section, option):
        '''Get the value of section.option'''

        if not self.cf.has_section(section):
            logger.error("There is no section '%s' in the config file. Please", section)
            logger.error("use the command 'stx config --add section.option = value'")
            logger.error("add this key/value pair, or select another setion.")
            sys.exit(1)

        if not self.cf.has_option(section, option):
            logger.error("There is no option '%s' within section '%s'. Please use", option, section)
            logger.error("the command 'stx config --add section.option = value' ")
            logger.error("to add it or select another option of section.")
            sys.exit(1)

        value = self.cf.get(section, option)
        if not value:
            if self.cf.has_option('default', option):
                value = self.cf.get('default', option)

        return value

    def setConfig(self, section, option, value):
        '''Set the pair of section.option and value'''

        if not self.cf.has_section(section):
            self.cf.add_section(section)
        if not self.cf.has_option(section, option):
            logger.warning("Option [%s] will be new added. perhaps you " +
                           "need to restart the helm project with the " +
                           "command 'stx control stop' and " +
                           "'stx control start' to make sure the new " +
                           "config be effective, if the helm release " +
                           "exists.", option)

        self.cf.set(section, option, value)
        self.syncConfigFile()

    def removeSection(self, section):
        '''Remove the whole of section from the configfile'''

        if not self.cf.has_section(section):
            logger.error("Section [%s] doesn't exist in the configfile.\n", section)
            sys.exit(1)

        ret = self.cf.remove_section(section)
        self.syncConfigFile()

        return ret

    def removeOption(self, section, option):
        '''Remove the option from this section in the configfile'''

        if not self.cf.has_section(section):
            logger.error("Section [%s] doesn't exist in the configfile.\n", section)
            sys.exit(1)
        if not self.cf.has_option(section, option):
            logger.error("Option [%s] doesn't exist in the section [%s].\n", option, section)
            sys.exit(1)

        ret = self.cf.remove_option(section, option)

        if not self.cf.options(section):
            self.cf.remove_section(section)

        self.syncConfigFile()

        return ret

    def syncConfigFile(self):
        self.cf.write(open(self.configpath, "w"))

    def __delete_key(self, section, option):
        if self.cf.has_option(section, option):
            self.cf.remove_option(section, option)

    def __upgrade_nonempty_key(self, section, option, value):
        old_value = self.cf.get(section, option)
        if old_value != value:
            logger.warn('%s: setting option %s.%s to %s', self.configpath,
                        section, option, value)
            self.cf.set(section, option, value)

    def __raise_upgrade_error(self, bad_section_key):
        logger.error('%s: unexpected %s', self.configpath, bad_section_key)
        logger.error("Please upgrade %s manually", self.configpath)
        raise RuntimeError("Failed to upgrade %s" % self.configpath)

    def upgradeConfigFile(self):
        ref_config_path = os.path.join(os.environ['PRJDIR'], "stx.conf.sample")
        ref_config = configparser.ConfigParser()
        ref_config.read(ref_config_path, encoding="utf-8")
        for section_name, data in ref_config.items():
            if section_name == 'DEFAULT':
                ref_options = ref_config.defaults()
            else:
                ref_options = ref_config.options(section_name)
                if not self.cf.has_section(section_name):
                    logger.info('%s: adding missing section "%s"',
                                self.configpath, section_name)
                    self.cf.add_section(section_name)
            for key in ref_options:
                value = ref_config.get(section_name, key, raw=True)
                if not self.cf.has_option(section_name, key):
                    logger.info(
                        '%s: adding missing option %s.%s = %s',
                        self.configpath, section_name, key, value)
                    self.cf.set(section_name, key, value)

        # Convert debian_snapshot => debian_snapshot_{base,timestamp}
        if self.cf.has_option('project', 'debian_snapshot'):
            obsolete = self.cf.get('project', 'debian_snapshot')
            match = re.fullmatch(r'^(.*)/+(\d{4,}[^/]*)/*$', obsolete)
            if match:
                self.__upgrade_nonempty_key(
                    'project', 'debian_snapshot_base', match.group(1))
                self.__upgrade_nonempty_key(
                    'project', 'debian_snapshot_timestamp', match.group(2))
            else:
                self.__raise_upgrade_error('project.debian_snapshot')
            # delete old key
            self.__delete_key('project', 'debian_snapshot')

        # Convert debian_security_snapshot => debian_security_snapshot_base
        if self.cf.has_option('project', 'debian_security_snapshot'):
            obsolete = self.cf.get('project', 'debian_security_snapshot')
            match = re.fullmatch(r'^(.*)/+(\d{4,}[^/]*)/*$', obsolete)
            fail = True
            if match:
                self.__upgrade_nonempty_key(
                    'project', 'debian_security_snapshot_base', match.group(1))
                # make sure the timestamp portion in debian_security_snapshot
                # is the same as debian_snapshot_timestamp
                timestamp = self.cf.get(
                    'project', 'debian_snapshot_timestamp', fallback='')
                if timestamp == match.group(2):
                    fail = False
            if fail:
                self.__raise_upgrade_error('project.debian_security_snapshot')
            # delete old key
            self.__delete_key('project', 'debian_security_snapshot')

        # Save changes
        self.syncConfigFile()


class HandleConfigTask:
    '''Handle the task for the config sub-command'''

    def __init__(self, config):
        self.stxconfig = config.impl()

    def handleShow(self):
        self.stxconfig.showAll()

    def handleGetTask(self, args):

        if args.get[0].count('.') != 1:
            logger.error('Please input the correct style for the key. eg: section.option')
            sys.exit(1)

        section, option = args.get[0].split('.')
        value = self.stxconfig.getConfig(section, option)
        print("[%s]" % section)
        print("( %s = %s )" % (option, value))

    def handleAddTask(self, args):

        if args.add[0].count('.') != 1:
            logger.error('Please input the correct style for the key. eg: section.option')
            print(helper.help_config())
            sys.exit(1)

        section, option = args.add[0].split('.')
        value = args.add[1]

        self.stxconfig.setConfig(section, option, value)

    def handleRemoveSectionTask(self, args):
        section = args.removesection[0]
        return self.stxconfig.removeSection(section)

    def handleUnsetOptionTask(self, args):

        if args.unset[0].count('.') != 1:
            logger.error('Please input the correct style to unset. eg: section.option|section')
            print(helper.help_config())
            sys.exit(1)

        section, option = args.unset[0].split('.')
        return self.stxconfig.removeOption(section, option)

    def handleConfig(self, args):

        if args.add:
            self.handleAddTask(args)

        elif args.get:
            self.handleGetTask(args)

        elif args.unset:
            self.handleUnsetOptionTask(args)

        elif args.removesection:
            self.handleRemoveSectionTask(args)

        elif args.show is True:
            self.handleShow()

        elif args.upgrade:
            self.stxconfig.upgradeConfigFile()

        else:
            print(helper.help_config())
