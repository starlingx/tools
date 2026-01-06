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
import utils

STX_DISTRO = 'trixie'
STX_ARCH = 'amd64'
PKG_BUILDER_LOG = '/localdisk/pkgbuilder.log'

app = Flask(__name__)
app.debug = True

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('pkgbuilder')
handler = logging.FileHandler(PKG_BUILDER_LOG, encoding='UTF-8')
log_format = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")
handler.setFormatter(log_format)
log.addHandler(handler)

app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(handler)

utils.set_logger(log)
dbuilder = Debbuilder('private', STX_DISTRO, STX_ARCH, log)


def dbuilder_initialized():
    global dbuilder
    response = {}
    if not dbuilder:
        response['status'] = 'fail'
        response['msg'] = 'Package builder is not initialized'
        return response
    return True


def log_request(action, request):
    """
    Print request with parameters
    """
    msg = 'Received request: ' + request.method + ' ' + action + ': {'
    for key, value in request.args.items():
        msg += f"{key}={value}, "
    msg = msg.rstrip(', ') + '}'
    log.info(msg)


@app.route('/pkgbuilder/state', methods=['GET'])
def get_state():
    log_request('state', request)
    init_result = dbuilder_initialized()
    if init_result is not True:
        return jsonify(init_result), 400

    try:
        response = dbuilder.get_state()
        return jsonify(response)
    except Exception as e:
        log.error(f"Failed to get state: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Internal Server Error'
        }), 500


@app.route('/pkgbuilder/loadchroot', methods=['GET'])
def load_chroot():
    log_request('loadchroot', request)
    init_result = dbuilder_initialized()
    if init_result is not True:
        return jsonify(init_result), 400

    try:
        response = dbuilder.load_chroot(request.args)
        return jsonify(response)
    except Exception as e:
        log.error(f"Failed to load chroot: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Internal Server Error'
        }), 500


@app.route('/pkgbuilder/clonechroot', methods=['GET'])
def clone_chroot():
    log_request('clonechroot', request)
    init_result = dbuilder_initialized()
    if init_result is not True:
        return jsonify(init_result), 400

    try:
        response = dbuilder.clone_chroot(request.args)
        return jsonify(response)
    except Exception as e:
        log.error(f"Failed to clone chroot: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Internal Server Error'
        }), 500


@app.route('/pkgbuilder/savechroot', methods=['GET'])
def save_chroot():
    log_request('savechroot', request)
    init_result = dbuilder_initialized()
    if init_result is not True:
        return jsonify(init_result), 400

    try:
        response = dbuilder.save_chroot(request.args)
        return jsonify(response)
    except Exception as e:
        log.error(f"Failed to save chroot: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Internal Server Error'
        }), 500


@app.route('/pkgbuilder/addchroot', methods=['GET'])
def add_chroot():
    log_request('addchroot', request)
    init_result = dbuilder_initialized()
    if init_result is not True:
        return jsonify(init_result), 400

    try:
        response = dbuilder.add_chroot(request.args)
        return jsonify(response)
    except Exception as e:
        log.error(f"Failed to add chroot: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Internal Server Error'
        }), 500


@app.route('/pkgbuilder/refreshchroots', methods=['GET'])
def refresh_chroot():
    log_request('refreshchroots', request)
    init_result = dbuilder_initialized()
    if init_result is not True:
        return jsonify(init_result), 400

    try:
        response = dbuilder.refresh_chroots(request.args)
        return jsonify(response)
    except Exception as e:
        log.error(f"Failed to refresh chroot: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Internal Server Error'
        }), 500


@app.route('/pkgbuilder/addtask', methods=['POST'])
def add_task():
    init_result = dbuilder_initialized()
    if init_result is not True:
        return jsonify(init_result), 400

    try:
        reqs = request.get_json()
        log.debug("Request for adding task: %s", reqs)
        response = dbuilder.add_task(reqs)
        return jsonify(response)
    except Exception as e:
        log.error(f"Failed to add task: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Internal Server Error'
        }), 500


@app.route('/pkgbuilder/killtask', methods=['GET'])
def clean_env():
    log_request('killtask', request)
    init_result = dbuilder_initialized()
    if init_result is not True:
        return jsonify(init_result), 400

    try:
        response = dbuilder.kill_task(request.args)
        return jsonify(response)
    except Exception as e:
        log.error(f"Failed to kill task: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Internal Server Error'
        }), 500


@app.route('/pkgbuilder/stoptask', methods=['GET'])
def stop_task():
    log_request('stoptask', request)
    init_result = dbuilder_initialized()
    if init_result is not True:
        return jsonify(init_result), 400

    try:
        response = dbuilder.stop_task(request.args)
        return jsonify(response)
    except Exception as e:
        log.error(f"Failed to stop task: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Internal Server Error'
        }), 500


@app.route('/pkgbuilder/cleanstamp', methods=['GET'])
def clean_stamp():
    log_request('cleanstamp', request)
    init_result = dbuilder_initialized()
    if init_result is not True:
        return jsonify(init_result), 400

    try:
        response = dbuilder.clean_stamp(request.args)
        return jsonify(response)
    except Exception as e:
        log.error(f"Failed to clean stamp: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Internal Server Error'
        }), 500


@app.route('/pkgbuilder/freetmpfschroots', methods=['GET'])
def free_tmpfs_chroots():
    log_request('freetmpfschroots', request)
    init_result = dbuilder_initialized()
    if init_result is not True:
        return jsonify(init_result), 400

    try:
        response = dbuilder.free_tmpfs_chroots(request.args)
        return jsonify(response)
    except Exception as e:
        log.error(f"Failed to free tmpfs chroots: {e}")
        return jsonify({
            'status': 'error',
            'msg': 'Internal Server Error'
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
