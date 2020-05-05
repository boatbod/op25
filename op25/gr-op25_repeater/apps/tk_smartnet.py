# Smartnet trunking module
#
# Copyright 2020 Graham J. Norbury - gnorbury@bondcar.com
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
#

import sys
import ctypes
import time
import json
from log_ts import log_ts

class rx_ctl(object):
    def __init__(self, debug=0, frequency_set=None, slot_set=None, chans={}):
        self.frequency_set = frequency_set
        self.debug = debug
        self.receivers = {}

        self.chans = chans

    def post_init(self):
       pass
       #for rx_id in self.receivers:
       #    self.receivers[rx_id].post_init()

    def add_receiver(self, msgq_id):
        self.receivers[msgq_id] = msgq_id # TODO: fill this placeholder

    def process_qmsg(self, msg):
        m_proto = ctypes.c_int16(msg.type() >> 16).value  # upper 16 bits of msg.type() is signed protocol
        if m_proto != 2: # Smartnet m_proto=2
            return

        m_type = ctypes.c_int16(msg.type() & 0xffff).value
        m_rxid = int(msg.arg1()) >> 1
        m_ts = float(msg.arg2())

        if (m_type == -1):  # Timeout
            pass
        elif (m_type == 0): # OSW
            s = msg.to_string()

            osw_addr = (ord(s[0]) << 8) + ord(s[1])
            osw_grp  =  ord(s[2])
            osw_cmd  = (ord(s[3]) << 8) + ord(s[4])

            sys.stderr.write("%s SMARTNET OSW (%d,%d,0x%03x)\n" % (log_ts.get(), osw_addr, osw_grp, osw_cmd))
