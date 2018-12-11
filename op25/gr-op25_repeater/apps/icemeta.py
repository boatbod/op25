#!/usr/bin/env python

# Copyright 2018 Graham Norbury
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


# Based on original work metaPy.py by
# Copyright (C)2013, Brandon Rasmussen, K7BBR

import sys
import time
import threading
import requests
import json

# OP25 thread to send metadata tags to an Icecast server
class meta_server(threading.Thread):
    def __init__(self, input_q, metacfg, **kwds):
        threading.Thread.__init__(self, **kwds)
        self.setDaemon(1)
        self.input_q = input_q
        self.keep_running = True
        self.last_metadata = ""
        self.cfg = {}
        self.urlBase = ""
        self.load_json(metacfg)
        self.start()

    def load_json(self, metacfg):
        try:
            with open(metacfg) as json_file:
                self.cfg = json.load(json_file)
            self.urlBase = "http://" + self.cfg['icecastServerAddress'] + "/admin/metadata?mount=/" + self.cfg['icecastMountpoint'] + "&mode=updinfo&song="
        except ValueError:
            sys.stderr.write("Error reading metadata config file: %s\n" % metacfg)

    def run(self):
        while(self.keep_running):
            self.process_q_events()
            time.sleep(1)

    def stop(self):
        self.keep_running = False

    def process_q_events(self):
        while True:
            if self.input_q.empty_p():
                break
            msg = self.input_q.delete_head_nowait()
            if msg.type() == -2:
                self.send_metadata(msg.to_string())

    def send_metadata(self, metadata):
        if (self.urlBase != "") and (metadata != '') and (self.last_metadata != metadata):
            metadataFormatted = metadata.replace(" ","+") # add "+" instead of " " for icecast2
            requestToSend = (self.urlBase) +(metadataFormatted)
            r = requests.get((requestToSend), auth=("source",self.cfg['icecastPass']))
            status = r.status_code
            if status != 200:
                sys.stderr.write("Icecast Update Error: %s\n" % status)
            else:
                self.last_metadata = metadata

