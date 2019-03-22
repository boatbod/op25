# MotoTRBO trunking module
#
# Copyright 2019 Graham J. Norbury - gnorbury@bondcar.com
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
import time
import json

class rx_ctl(object):
    def __init__(self, debug=0, frequency_set=None):
        self.frequency_set = frequency_set
        self.debug = debug

    def process_qmsg(self, msg):
        m_type = int(msg.type())
        m_ch_id = int(msg.arg1()) >> 1
        m_ch_slot = int(msg.arg1()) & 0x1
        m_proto = int(msg.arg2())

        if m_proto != 1: # discard anything not DMR
            return

        # TODO: implement something useful!
        # right now just log that we received a message
        sys.stderr.write("%f DMR PDU: type(%d), ch_id(%d), slot(%d)\n" % (time.time(), m_type, m_ch_id, m_ch_slot))

