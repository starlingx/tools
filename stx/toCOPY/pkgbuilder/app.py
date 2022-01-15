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
# Copyright (C) 2021 Wind River Systems,Inc
#
from debbuilder import Debbuilder
from flask import Flask
from flask import jsonify
from flask import request
import logging

app = Flask(__name__)
log = logging.getLogger('pkgbuilder')
dbuilder = Debbuilder('private', log)


@app.route('/pkgbuilder/state', methods=['GET'])
def get_state():
    response = {
        'status': dbuilder.state,
        'msg': ''
    }
    return jsonify(response)


@app.route('/pkgbuilder/loadchroot', methods=['GET'])
def load_chroot():
    attrs = ['user', 'project']
    if all(t in request.form for t in attrs):
        user = request.form['user']
        project = request.form['project']
        response = dbuilder.load_chroot(user, project)
        log.info("Reply to load chroot, response=%s", str(response))
    else:
        response = {
            'status': 'fail',
            'msg': 'invalid request, missing parameter'
        }
    return jsonify(response)


@app.route('/pkgbuilder/savechroot', methods=['GET'])
def save_chroot():
    attrs = ['user', 'project']
    if all(t in request.form for t in attrs):
        user = request.form['user']
        project = request.form['project']
        response = dbuilder.save_chroot(user, project)
        log.info("Reply to save chroot, response=%s", str(response))
    else:
        response = {
            'status': 'fail',
            'msg': 'invalid request, missing parameter'
        }
    return jsonify(response)


@app.route('/pkgbuilder/addchroot', methods=['GET'])
def add_chroot():
    if not request.form or 'user' not in request.form:
        log.error("Invalid request to add user chroot")
        response = {
            'status': 'fail',
            'msg': 'invalid request'
        }
    else:
        user = request.form['user']
        project = request.form['project']
        if 'mirror' in request.form:
            response = dbuilder.add_chroot(user, project,
                                           request.form['mirror'])
        else:
            response = dbuilder.add_chroot(user, project)
        log.info("Reply to add user chroot, response=%s", str(response))
    return jsonify(response)


@app.route('/pkgbuilder/addtask', methods=['GET'])
def add_task():
    response = {}
    attrs = ['user', 'project', 'dsc', 'type', 'name', 'mode', 'run_tests']
    if not all(t in request.form for t in attrs):
        log.error("Invalid request to add task")
        response['status'] = 'fail'
        response['msg'] = 'invalid request'
    else:
        dbuilder.mode = request.form['mode']
        user = request.form['user']
        project = request.form['project']

        task_info = {
            'package': request.form['name'],
            'dsc': request.form['dsc'],
            'type': request.form['type'],
            'run_tests': request.form['run_tests']
            }
        if 'jobs' in request.form:
            task_info['jobs'] = request.form['jobs']

        response = dbuilder.add_task(user, project, task_info)
        log.info("Reply to add task, response=%s", str(response))
    return jsonify(response)


@app.route('/pkgbuilder/killtask', methods=['GET'])
def clean_env():
    response = {}
    attrs = ['user', 'owner']
    if all(t in request.form for t in attrs):
        user = request.form['user']
        owner = request.form['owner']
        response = dbuilder.kill_task(user, owner)
        log.info("Reply to kill task, response=%s", str(response))
    else:
        log.error("Invalid request to kill task")
        response = {
            'status': 'fail',
            'msg': 'invalid request'
        }
    return jsonify(response)


@app.route('/pkgbuilder/stoptask', methods=['GET'])
def stop_task():
    response = {}
    attrs = ['user']
    if all(t in request.form for t in attrs):
        user = request.form['user']
        response = dbuilder.stop_task(user)
        log.info("Reply to stop task, response=%s", str(response))
    else:
        log.error("Invalid request to stop task")
        response = {
            'status': 'fail',
            'msg': 'invalid request'
        }
    return jsonify(response)


if __name__ == '__main__':
    app.debug = True
    handler = logging.FileHandler('/localdisk/pkgbuilder.log',
                                  encoding='UTF-8')
    logging.basicConfig(level=logging.DEBUG)
    log_format = logging.Formatter('pkgbuilder: %(levelname)s %(message)s')
    handler.setFormatter(log_format)
    log.addHandler(handler)

    app.run(host='0.0.0.0', port=80, debug=True)
