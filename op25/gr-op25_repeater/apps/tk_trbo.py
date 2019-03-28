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

CC_HUNT_TIMEOUTS = 3

class dmr_chan:
    def __init__(self, debug=0, lcn=0, freq=0, slot=0):
        self.debug = debug
        self.lcn = lcn
        self.frequency = freq
        self.slot = slot

class rx_ctl(object):
    def __init__(self, debug=0, frequency_set=None, chans=None):
        self.trbo_type = -1
        self.rest_lcn = 0
        self.frequency_set = frequency_set
        self.debug = debug
        self.cc_timeouts = 0

        self.chans = {}
        for _chan in chans:
            self.chans[(_chan['lcn'] << 1) + 0] = dmr_chan(debug, _chan['lcn'], _chan['frequency'], 0)
            sys.stderr.write("%f creating logical channel %d, frequency=%f, slot=%d, cc=%d\n" % (time.time(), ((_chan['lcn'] << 1) + 0), (_chan['frequency']/1e6), 0, _chan['cc']))
            self.chans[(_chan['lcn'] << 1) + 1] = dmr_chan(debug, _chan['lcn'], _chan['frequency'], 1)
            sys.stderr.write("%f creating logical channel %d, frequency=%f, slot=%d, cc=%d\n" % (time.time(), ((_chan['lcn'] << 1) + 1), (_chan['frequency']/1e6), 1, _chan['cc']))

        self.chan_list = self.chans.keys()
        self.current_chan = 0

    def find_freq(self, lcn):
        if self.chans.has_key(lcn):
            return (self.chans[lcn].frequency, self.chans[lcn].slot)
        else:
            return (None, None)

    def find_next_chan(self, current_chan):
        num_chans = len(self.chan_list)
        next_chan = current_chan + 2 # channels are in pairs for each frequency/timeslot combo
        if next_chan >= num_chans:
            next_chan = 0
        return next_chan

    def process_qmsg(self, msg):
        if msg.arg2() != 1: # discard anything not DMR
            return

        m_type = int(msg.type())
        m_ch_slot = int(msg.arg1())
        m_proto = int(msg.arg2())
        m_buf = msg.to_string()

        if m_type == -1:  # Sync Timeout
            if (m_ch_slot>>1) == 0:
                self.cc_timeouts += 1

                if self.cc_timeouts >= CC_HUNT_TIMEOUTS:
                    if self.debug >= 1:
                        sys.stderr.write("%f [%d] Searching for control channel\n" % (time.time(), (m_ch_slot >>1)))
                    self.cc_timeouts = 0
                    next_ch = self.find_next_chan(self.current_chan)
                    self.frequency_set({'tuner': 'trunk',
                                        'freq': self.chans[self.chan_list[next_ch]].frequency,
                                        'slot': 0})
                    self.current_chan = next_ch
            else:
                pass
            return
        elif m_type >= 0: # Receiving a PDU means sync must be present
            if (m_ch_slot>>1) == 0:
                self.cc_timeouts = 0

        # log received message
        if self.debug >= 9:
            d_buf = "0x"
            for byte in m_buf:
                d_buf += format(ord(byte),"02x")
            sys.stderr.write("%f [%d] DMR PDU: type(%d), slot(%d), data(%s)\n" % (time.time(), (m_ch_slot>>1), m_type, (m_ch_slot & 0x1), d_buf))

	if m_type == 0: # CACH SLC
            self.rx_CACH_SLC(m_ch_slot, m_buf)
        elif m_type == 1: # CACH CSBK
            pass
        elif m_type == 2: # SLOT PI
            pass
        elif m_type == 3: # SLOT VLC
            pass
        elif m_type == 4: # SLOT TLC
            pass
        elif m_type == 5: # SLOT CSBK
            self.rx_SLOT_CSBK(m_ch_slot, m_buf)
        elif m_type == 6: # SLOT MBC
            pass
        elif m_type == 7: # SLOT ELC
            pass
        elif m_type == 8: # SLOT ERC
            pass
        elif m_type == 9: # SLOT ESB
            pass
        else:             # Unknown Message
            return

    def rx_CACH_SLC(self, m_ch_slot, m_buf):
        slco = ord(m_buf[0])
        d0 = ord(m_buf[1])
        d1 = ord(m_buf[2])
        d2 = ord(m_buf[3])

        if slco == 9:    # Connect Plus Voice Channel
            netId = (d0 << 4) + (d1 >> 4)
            siteId = ((d1 & 0xf) << 4) + (d2 >> 4)
            if self.trbo_type < 0:
                self.trbo_type = 1
                sys.stderr.write("%f [%d] TRBO_TYPE SET TO CONNECT PLUS\n" % (time.time(), (m_ch_slot >> 1)))
            if self.debug >= 9:
                sys.stderr.write("%f [%d] CONNECT PLUS VOICE CHANNEL: netId(%d), siteId(%d)\n" % (time.time(), (m_ch_slot >> 1), netId, siteId))
        elif slco == 10: # Connect Plus Control Channel
            netId = (d0 << 4) + (d1 >> 4)
            siteId = ((d1 & 0xf) << 4) + (d2 >> 4)
            if self.trbo_type < 0:
                self.trbo_type = 1
                sys.stderr.write("%f [%d] TRBO_TYPE SET TO CONNECT PLUS\n" % (time.time(), (m_ch_slot >> 1)))
            if self.debug >= 9:
                sys.stderr.write("%f [%d] CONNECT PLUS CONTROL CHANNEL: netId(%d), siteId(%d)\n" % (time.time(), (m_ch_slot >> 1), netId, siteId))
        elif slco == 15: # Capacity Plus Channel
            lcn = d1
            if self.trbo_type < 0:
                self.trbo_type = 0
                sys.stderr.write("%f [%d] TRBO_TYPE SET TO CAPACITY PLUS\n" % (time.time(), (m_ch_slot >> 1)))
            self.rest_lcn = d1
            if self.debug >= 9:
                sys.stderr.write("%f [%d] CAPACITY PLUS REST CHANNEL: lcn(%d)\n" % (time.time(), (m_ch_slot >>1), lcn))
        else:
            if self.debug >= 9:
                sys.stderr.write("%f [%d] UNKNOWN CACH SLCO(%d)\n" % (time.time(), (m_ch_slot >> 1), slco))
            return

    def rx_SLOT_CSBK(self, m_ch_slot, m_buf):
        op  = ord(m_buf[0]) & 0x3f
        fid = ord(m_buf[1])

        if (op == 1) and (fid == 6):     # ConnectPlus Neighbors
            nb1 = ord(m_buf[2]) & 0x3f
            nb2 = ord(m_buf[3]) & 0x3f
            nb3 = ord(m_buf[4]) & 0x3f
            nb4 = ord(m_buf[5]) & 0x3f
            nb5 = ord(m_buf[6]) & 0x3f
            if self.debug >= 9:
                sys.stderr.write("%f [%d] CONNECT PLUS NEIGHBOR SITES: %d, %d, %d, %d, %d\n" % (time.time(), (m_ch_slot >> 1), nb1, nb2, nb3, nb4, nb5))
        elif (op == 3) and (fid == 6):   # ConnectPlus Channel Grant
            src_addr = (ord(m_buf[2]) << 16) + (ord(m_buf[3]) << 8) + ord(m_buf[4])
            grp_addr = (ord(m_buf[5]) << 16) + (ord(m_buf[6]) << 8) + ord(m_buf[7])
            lcn      = (ord(m_buf[8]) >> 3)
            if self.debug >= 9:
                sys.stderr.write("%f [%d] CONNECT PLUS CHANNEL GRANT: grpAddr(%06x), srcAddr(%06x), lcn(%d)\n" % (time.time(), (m_ch_slot >> 1), grp_addr, src_addr, lcn))

            freq, slot = self.find_freq(lcn)
            if freq is not None:
                self.frequency_set({'tuner': 'voice',
                                    'freq': freq,
                                    'slot': slot})

        elif (op == 59) and (fid == 16): # CapacityPlus Sys/Sites/TS
            fl   =  (ord(m_buf[2]) >> 6)
            ts   = ((ord(m_buf[2]) >> 5) & 0x1)
            rest =  (ord(m_buf[2]) & 0x1f)
            bcn  = ((ord(m_buf[3]) >> 7) & 0x1)
            site = ((ord(m_buf[3]) >> 3) & 0xf)
            nn   =  (ord(m_buf[3]) & 0x7)
            if nn > 6:
                nn = 6
            if self.debug >= 9:
                sys.stderr.write("%f [%d] CAPACITY PLUS SYSSITES: rest(%d), beacon(%d), siteId(%d), nn(%d)\n" % (time.time(), (m_ch_slot >> 1), rest, bcn, site, nn))
            
        elif (op == 62):                 # 
            pass




