#!/usr/bin/python3
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
# Copyright (C) 2021-2022 Wind River Systems,Inc
#
from debbuilder import Debbuilder
from flask import Flask
from flask import jsonify
from flask import request
import logging
import subprocess

STX_ARCH = 'amd64'
PKG_BUILDER_LOG = '/localdisk/pkgbuilder.log'
STX_LOCALRC = '/usr/local/bin/stx/stx-localrc'
CMD = 'grep "^export DEBIAN_DISTRIBUTION=.*" %s | cut -d \\= -f 2' % STX_LOCALRC
STX_DISTRO = subprocess.check_output(CMD, shell=True).decode().split("\n")[0].strip('"')

app = Flask(__name__)
app.debug = True

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('pkgbuilder')
handler = logging.FileHandler(PKG_BUILDER_LOG, encoding='UTF-8')
log_format = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")
handler.setFormatter(log_format)
log.addHandler(handler)

dbuilder = Debbuilder('private', STX_DISTRO, STX_ARCH, log)
response = {}


def dbuider_initialized():
    global dbuilder
    if not dbuilder:
        response['status'] = 'fail'
        response['msg'] = 'Package builder is not initialized'
        return False
    return True


def log_request(action, request):
    """
    Print request with parameters
    """
    msg = 'Received request: ' + action + ': {'
    for key in request:
        value = key + ':' + request[key]
        msg = ' '.join([msg, value])
    msg = msg + '}'
    log.info(msg)


@app.route('/pkgbuilder/state', methods=['GET'])
def get_state():
    if dbuider_initialized():
        response = dbuilder.state()
    return jsonify(response)


@app.route('/pkgbuilder/loadchroot', methods=['GET'])
def load_chroot():
    log_request('loadchroot', request.form)
    if dbuider_initialized():
        response = dbuilder.load_chroot(request.form)
    return jsonify(response)


@app.route('/pkgbuilder/clonechroot', methods=['GET'])
def clone_chroot():
    log_request('clonechroot', request.form)
    if dbuider_initialized():
        response = dbuilder.clone_chroot(request.form)
    return jsonify(response)


@app.route('/pkgbuilder/savechroot', methods=['GET'])
def save_chroot():
    log_request('savechroot', request.form)
    if dbuider_initialized():
        response = dbuilder.save_chroot(request.form)
    return jsonify(response)


@app.route('/pkgbuilder/addchroot', methods=['GET'])
def add_chroot():
    log_request('addchroot', request.form)
    if dbuider_initialized():
        response = dbuilder.add_chroot(request.form)
    return jsonify(response)


@app.route('/pkgbuilder/refreshchroots', methods=['GET'])
def refresh_chroot():
    log_request('refreshchroots', request.form)
    if dbuider_initialized():
        response = dbuilder.refresh_chroots(request.form)
    return jsonify(response)


@app.route('/pkgbuilder/addtask', methods=['POST'])
def add_task():
    if dbuider_initialized():
        reqs = request.get_json()
        log.debug("Request for adding task: %s", reqs)
        response = dbuilder.add_task(reqs)
    return jsonify(response)


@app.route('/pkgbuilder/killtask', methods=['GET'])
def clean_env():
    log_request('killtask', request.form)
    if dbuider_initialized():
        response = dbuilder.kill_task(request.form)
    return jsonify(response)


@app.route('/pkgbuilder/stoptask', methods=['GET'])
def stop_task():
    log_request('stoptask', request.form)
    if dbuider_initialized():
        response = dbuilder.stop_task(request.form)
    return jsonify(response)


@app.route('/pkgbuilder/cleanstamp', methods=['GET'])
def clean_stamp():
    log_request('cleanstamp', request.form)
    if dbuider_initialized():
        response = dbuilder.clean_stamp(request.form)
    return jsonify(response)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
