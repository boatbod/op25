
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
from waitress.server import create_server

my_input_q = None
my_output_q = None
my_recv_q = None
my_port = None

"""
fake http and ajax server module
TODO: make less fake
"""

def static_file(environ, start_response):
    content_types = { 'png': 'image/png', 'jpeg': 'image/jpeg', 'jpg': 'image/jpeg', 'gif': 'image/gif', 'css': 'text/css', 'js': 'application/javascript', 'html': 'text/html'}
    img_types = 'png jpg jpeg gif'.split()
    if environ['PATH_INFO'] == '/':
        filename = 'index.html'
    else:
        filename = re.sub(r'[^a-zA-Z0-9_.\-]', '', environ['PATH_INFO'])
    suf = filename.split('.')[-1]
    pathname = '../www/www-static'
    if suf in img_types:
        pathname = '../www/images'
    pathname = '%s/%s' % (pathname, filename)
    if suf not in content_types.keys() or '..' in filename or not os.access(pathname, os.R_OK):
        sys.stderr.write('404 %s\n' % pathname)
        status = '404 NOT FOUND'
        content_type = 'text/plain'
        output = status
    else:
        output = open(pathname).read()
        content_type = content_types[suf]
        status = '200 OK'
    return status, content_type, output

def post_req(environ, start_response, postdata):
    global my_input_q, my_output_q, my_recv_q, my_port
    valid_req = False
    try:
        data = json.loads(postdata)
        for d in data:
            msg = gr.message().make_from_string(str(d['command']), -2, d['data'], 0)
            my_output_q.insert_tail(msg)
        valid_req = True
        time.sleep(0.2)
    except:
        sys.stderr.write('post_req: error processing input: %s:\n' % (postdata))

    resp_msg = []
    while not my_recv_q.empty_p():
        msg = my_recv_q.delete_head()
        if msg.type() == -4:
            resp_msg.append(json.loads(msg.to_string()))
    if not valid_req:
        resp_msg = []
    status = '200 OK'
    content_type = 'application/json'
    output = json.dumps(resp_msg)
    return status, content_type, output

def http_request(environ, start_response):
    if environ['REQUEST_METHOD'] == 'GET':
        status, content_type, output = static_file(environ, start_response)
    elif environ['REQUEST_METHOD'] == 'POST':
        postdata = environ['wsgi.input'].read()
        status, content_type, output = post_req(environ, start_response, postdata)
    else:
        status = '200 OK'
        content_type = 'text/plain'
        output = status
        sys.stderr.write('http_request: unexpected input %s\n' % environ['PATH_INFO'])
    
    response_headers = [('Content-type', content_type),
                        ('Content-Length', str(len(output)))]
    start_response(status, response_headers)

    return [output]

def application(environ, start_response):
    failed = False
    try:
        result = http_request(environ, start_response)
    except:
        failed = True
        sys.stderr.write('application: request failed:\n%s\n' % traceback.format_exc())
        sys.exit(1)
    return result

def process_qmsg(msg):
    if my_recv_q.full_p():
        my_recv_q.delete_head_nowait()   # ignores result
    if my_recv_q.full_p():
        return
    my_recv_q.insert_tail(msg)

class http_server(object):
    def __init__(self, input_q, output_q, endpoint, **kwds):
        global my_input_q, my_output_q, my_recv_q, my_port
        host, port = endpoint.split(':')
        if my_port is not None:
            raise AssertionError('this server is already active on port %s' % my_port)
        my_input_q = input_q
        my_output_q = output_q
        my_port = int(port)

        my_recv_q = gr.msg_queue(10)
        self.q_watcher = queue_watcher(my_input_q, process_qmsg)

        self.server = create_server(application, host=host, port=my_port)

    def run(self):
        self.server.run()

class queue_watcher(threading.Thread):
    def __init__(self, msgq,  callback, **kwds):
        threading.Thread.__init__ (self, **kwds)
        self.setDaemon(1)
        self.msgq = msgq
        self.callback = callback
        self.keep_running = True
        self.start()

    def run(self):
        while(self.keep_running):
            msg = self.msgq.delete_head()
            self.callback(msg)
