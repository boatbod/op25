# Copyright 2017, 2018 Max H. Parke KA1RBI
#
# This file is part of OP25
#
# OP25 is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# OP25 is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
# License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OP25; see the file COPYING. If not, write to the Free
# Software Foundation, Inc., 51 Franklin Street, Boston, MA
# 02110-1301, USA.

import sys
import os
import time
import re
import json
import socket
import traceback
import threading

from gnuradio import gr
from flask import Flask, Response, request, send_from_directory, send_file
import logging
import click

my_input_q = None
my_output_q = None
my_recv_q = None
my_port = None

"""
fake http and ajax server module
TODO: make less fake
"""

def post_req(data):
    global my_input_q, my_output_q, my_recv_q, my_port
    valid_req = False
    try:
        for d in data:
            msg = gr.message().make_from_string(
                str(d['command']), -2, d['arg1'], d['arg2'])
            my_output_q.insert_tail(msg)
        valid_req = True
        time.sleep(0.2)
    except:
        sys.stderr.write('post_req: error processing input: %s\n%s\n' %
                         (str(data), traceback.format_exc()))

    resp_msg = []
    while not my_recv_q.empty_p():
        msg = my_recv_q.delete_head()
        if msg.type() == -4:
            resp_msg.append(json.loads(msg.to_string()))
    if not valid_req:
        resp_msg = []

    resp = Response(response=json.dumps(resp_msg), status=200, mimetype="application/json")
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp

def process_qmsg(msg):
    if my_recv_q.full_p():
        my_recv_q.delete_head_nowait()   # ignores result
    if my_recv_q.full_p():
        return
    my_recv_q.insert_tail(msg)


class http_server(object):
    server = Flask(__name__, static_url_path='')
    log = logging.getLogger('werkzeug')

    def secho(text, file=None, nl=None, err=None, color=None, **styles):
        pass

    def echo(text, file=None, nl=None, err=None, color=None, **styles):
        pass

    def __init__(self, input_q, output_q, endpoint, **kwds):
        global my_input_q, my_output_q, my_recv_q, my_port
        host, port = endpoint.split(':')
        if my_port is not None:
            raise AssertionError(
                'this server is already active on port %s' % my_port)
        my_input_q = input_q
        my_output_q = output_q
        my_port = int(port)

        my_recv_q = gr.msg_queue(10)
        self.q_watcher = queue_watcher(my_input_q, process_qmsg)

        self.http_host = host
        self.http_port = my_port

        # Disable Flask Logging
        self.log.setLevel(logging.ERROR)
        click.echo = self.echo
        click.secho = self.secho

    def run(self):
        try:
            self.server.run(host=self.http_host, port=self.http_port)
        except:
            sys.stderr.write(
                'Failed to create http terminal server\n%s\n' % traceback.format_exc())
            sys.exit(1)

    @server.after_request
    def add_headers(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'PUT, GET, POST, DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Expose-Headers', 'Content-Type,Content-Length,Authorization,X-Pagination')
        return response

    @server.route('/', methods=['GET', 'POST'])
    def send_app():
        if request.method == 'GET':
            return send_file('../www/www-static/index.html', 'text/html')
        else:
            return post_req(request.json)

    @server.route('/static/js/<path:path>')
    def send_js(path):
        return send_from_directory('../www/www-static/static/js', path)
    
    @server.route('/static/css/<path:path>')
    def send_css(path):
        return send_from_directory('../www/www-static/static/css', path)
    
    @server.route('/static/media/<path:path>')
    def send_media(path):
        return send_from_directory('../www/www-static/static/media', path)



class queue_watcher(threading.Thread):
    def __init__(self, msgq,  callback, **kwds):
        threading.Thread.__init__(self, **kwds)
        self.setDaemon(1)
        self.msgq = msgq
        self.callback = callback
        self.keep_running = True
        self.start()

    def run(self):
        while(self.keep_running):
            msg = self.msgq.delete_head()
            self.callback(msg)
