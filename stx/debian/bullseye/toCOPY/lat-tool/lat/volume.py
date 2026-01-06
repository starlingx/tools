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

"""
volume module implements shared volume communication between STX builder
container and LAT container
"""

import logging
import os
import subprocess
import time
import yaml

logger = logging.getLogger('latd.volume')

workspace_dir = "/localdisk" if 'WORKSPACE_DIR' not in os.environ \
                else os.environ['WORKSPACE_DIR']

channel_dir = "/localdisk/channel"

client_message_watch_file = channel_dir + "/c-2-s.done"
client_message_content_file = channel_dir + "/c-2-s.msg"
server_message_watch_file = channel_dir + '/s-2-c.done'
server_message_content_file = channel_dir + '/s-2-c.msg'


def server_init_channel():
    """
    Init channel
    """
    if not os.path.exists(channel_dir):
        subprocess.check_call('mkdir -p %s' % channel_dir, shell=True)
    rm_cmd = 'rm -f %s %s %s %s' % (client_message_watch_file,
                                    client_message_content_file,
                                    server_message_watch_file,
                                    server_message_content_file)
    subprocess.check_call(rm_cmd, shell=True)


def get_client_message():
    """
    Get client message.
    Return a dict of {'action': '<action_str>', <extra_info>: xxx}

    If the message is related to file contents, store the contents into a LAT
    container local file, return dict containing the local file path.
    """
    # As we are using shared volume, the file contents could be shared,
    # so extra need for storing local files.
    while True:
        if os.path.exists(client_message_watch_file):
            with open(client_message_content_file) as f:
                msg = yaml.safe_load(f)
            os.unlink(client_message_watch_file)
            return msg

        time.sleep(0.1)


def get_server_message():
    """
    Get server message. Return a dict of {'action': '<action_str>',
                                          'result': xxx, <extra_info>: xxx}

    If the message is related to file contents, store the contents into a STX
    build container local file, return dict containing the local file path.
    """
    # As we are using shared volume, the file contents could be shared,
    # so extra need for storing local files.
    while True:
        if os.path.exists(server_message_watch_file):
            with open(server_message_content_file) as f:
                msg = yaml.safe_load(f)
            os.unlink(server_message_watch_file)
            return msg

        time.sleep(0.1)


def mark_client_message_valid(is_valid):
    """
    Mark client message valid or not
    """
    invalid_message_file = channel_dir + 'invalid_message'
    if is_valid:
        subprocess.check_call('rm -f %s' % invalid_message_file, shell=True)
    else:
        subprocess.check_call('touch %s' % invalid_message_file, shell=True)


def send_message_to_client(msg):
    """
    Send message to client.
    msg is a dict.
    """
    # According to different action in msg, it should behave differently.
    # For example, for messages which contain file path, the contents might
    # need to read and send out in other backend like REST.
    # But for shared volume backend, no need to do so, just letting the
    # client read the file is OK.

    with open(server_message_content_file, 'w') as f:
        yaml.safe_dump(msg, f)
    subprocess.check_call('touch %s' % server_message_watch_file, shell=True)


def send_message_to_server(msg):
    """
    Send message to server.
    msg is a dict.
    """
    with open(client_message_content_file, 'w') as f:
        yaml.safe_dump(msg, f)
    subprocess.check_call('touch %s' % client_message_watch_file, shell=True)
