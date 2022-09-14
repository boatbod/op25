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
from log_ts import log_ts

# Helper function
def from_dict(d, key, def_val):
    if key in d and d[key] != "":
        return d[key]
    else:
        return def_val

# OP25 thread to send metadata tags to an Icecast server
class meta_server(threading.Thread):
    def __init__(self, input_q, metacfg, debug = 0, **kwds):
        threading.Thread.__init__(self, **kwds)
        self.setDaemon(1)
        self.input_q = input_q
        self.logging = debug
        self.keep_running = True
        self.last_metadata = ""
        self.delay = 0
        self.msg = None
        self.urlBase = ""
        self.url = ""
        if isinstance(metacfg,dict):
            self.cfg = metacfg
        else:
            self.cfg = {}
            self.load_json(metacfg)
        self.urlBase = "http://" + self.cfg['icecastServerAddress'] + "/admin/metadata?mount=/" + self.cfg['icecastMountpoint'] + "&mode=updinfo&song="
        self.url = "http://" + self.cfg['icecastServerAddress'] + "/" + self.cfg['icecastMountpoint'] + self.cfg['icecastMountExt']
        self.delay = float(self.cfg['delay'])
        self.fmt_idle = from_dict(self.cfg, 'meta_format_idle', '[idle]')
        self.fmt_tgid = from_dict(self.cfg, 'meta_format_tgid', '[%TGID%]')
        self.fmt_tag = from_dict(self.cfg, 'meta_format_tag', '[%TGID%] %TAG%')
        self.start()

    def set_debug(self, dbglvl):
        self.logging = dbglvl

    def load_json(self, metacfg):
        try:
            with open(metacfg) as json_file:
                self.cfg = json.load(json_file)
        except (ValueError, KeyError):
            sys.stderr.write("%s meta_server::load_json(): Error reading metadata config file: %s\n" % (log_ts.get(), metacfg))

    def run(self):
        while(self.keep_running):
            self.process_q_events()
            if self.msg and (time.time() >= (self.msg.arg1() + self.delay)):
                self.send_metadata(self.format(json.loads(self.msg.to_string())))
                self.msg = None
            time.sleep(0.1)

    def format(self, meta):
        if meta['tgid'] is None:
            metatext = self.fmt_idle
        elif meta['tgid'] is not None and meta['tag'] is not None and meta['tag'] != "":
            metatext = self.fmt_tag
        else:
            metatext = self.fmt_tgid
        metatext = metatext.replace("%TGID%", str(meta['tgid']))
        metatext = metatext.replace("%TAG%", str(meta['tag']))
        return metatext

    def stop(self):
        self.keep_running = False

    def process_q_events(self):
        if (self.msg is None) and (self.input_q.empty_p() == False):
            self.msg = self.input_q.delete_head_nowait()
            if self.msg.type() != -2:
                self.msg = None

    def send_metadata(self, metadata):
        if (self.urlBase != "") and (metadata != '') and (self.last_metadata != metadata):
            metadataFormatted = metadata.replace(" ","+") # add "+" instead of " " for icecast2
            requestToSend = (self.urlBase) +(metadataFormatted)
            if self.logging >= 11:
                sys.stderr.write("%s metadata update: \"%s\"\n" % (log_ts.get(), requestToSend))
            try:
                r = requests.get((requestToSend), auth=("source",self.cfg['icecastPass']), timeout=1.0)
                status = r.status_code
                if self.logging >= 11:
                    sys.stderr.write("%s metadata result: \"%s\"\n" % (log_ts.get(), status))
                if status != 200:
                    if self.logging >= 1:
                        sys.stderr.write("%s meta_server::send_metadata(): metadata update error: %s\n" % (log_ts.get(), status))
                else:
                    self.last_metadata = metadata
            except (requests.ConnectionError, requests.Timeout):
                if self.logging >= 1:
                    sys.stderr.write("%s meta_server::send_metadata(): exception %s\n" % (log_ts.get(), sys.exc_info()[1]))

    def get_url(self):
        return self.url

