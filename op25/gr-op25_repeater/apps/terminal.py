#!/usr/bin/python3
#
# Copyright 2008-2011 Steve Glass
# Copyright 2011, 2012, 2013, 2014, 2015, 2016, 2017 Max H. Parke KA1RBI
# Copyright 2017-2026 Graham J. Norbury
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
import time
import json
import threading
import traceback

from gnuradio import gr

import gnuradio.op25_repeater as op25_repeater

KEEPALIVE_TIME = 3.0   # no data received in (seconds)

class http_terminal(threading.Thread):
    def __init__(self, input_q,  output_q, endpoint, **kwds):
        from http_server import http_server

        threading.Thread.__init__ (self, **kwds)
        self.setDaemon(1)
        self.input_q = input_q
        self.output_q = output_q
        self.endpoint = endpoint
        self.keep_running = True
        self.server = http_server(self.input_q, self.output_q, self.endpoint)
        self.start()

    def get_terminal_type(self):
        return "http"

    def end_terminal(self):
        self.keep_running = False

    def run(self):
        self.server.run()

def op25_terminal(input_q,  output_q, terminal_type):
        if terminal_type == 'curses':
            sys.stderr.write('Configuration option "terminal_type": "curses" is no longer supported. Please use "http:"\n')
            return None
        elif terminal_type.startswith('http:'):
            return http_terminal(input_q, output_q, terminal_type.replace('http:', ''))
        else:
            sys.stderr.write('warning: unsupported terminal type: %s\n' % terminal_type)
            return None

if __name__ == '__main__':
    terminal = None

