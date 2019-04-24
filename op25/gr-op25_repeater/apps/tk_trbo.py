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

CC_HUNT_TIMEOUTS = 3   # number of sync timeouts to wait until control channel hunt
VC_SRCH_TIME     = 3.0 # seconds to wait from VC tuning until hunt
TGID_HOLD_TIME   = 2.0 # seconds to wait until releasing tgid after last GRANT message

class dmr_chan:
    def __init__(self, debug=0, lcn=0, freq=0):
        class _grant_info(object):
            grant_time = 0
            grp_addr = None
            src_addr = None
        self.debug = debug
        self.lcn = lcn
        self.frequency = freq
        self.slot = []
        self.slot.append(_grant_info)
        self.slot.append(_grant_info)

class dmr_receiver:
    def __init__(self, msgq_id, frequency_set=None, slot_set=None, chans={}, debug=0):
        class _states(object):
            IDLE = 0
            CC   = 1
            VC   = 2
            SRCH = 3
            REST = 4
        self.current_type = -1
        self.states = _states
        self.current_state = self.states.IDLE
        self.frequency_set = frequency_set
        self.slot_set = slot_set
        self.msgq_id = msgq_id
        self.debug = debug
        self.cc_timeouts = 0
        self.chans = chans
        self.chan_list = self.chans.keys()
        self.current_chan = 0
        self.rest_lcn = 0
        self.active_tgids = {}
        self.tune_time = 0

    def post_init(self):
        if self.debug >= 1:
            sys.stderr.write("%f [%d] Initializing DMR receiver\n" % (time.time(), self.msgq_id))
        if self.msgq_id == 0:
            self.tune_next_chan(msgq_id=0, chan=0, slot=0)
        else:
            self.tune_next_chan(msgq_id=1, chan=0, slot=4)

    def process_grant(self, m_buf):
            src_addr = (ord(m_buf[2]) << 16) + (ord(m_buf[3]) << 8) + ord(m_buf[4])
            grp_addr = (ord(m_buf[5]) << 16) + (ord(m_buf[6]) << 8) + ord(m_buf[7])
            lcn      = (ord(m_buf[8]) >> 4)
            slot     = (ord(m_buf[8]) >> 3) & 0x1 
            chan, freq = self.find_freq(lcn)
            if freq is not None:
                lcn_sl = (lcn << 1) + slot
                if self.debug >= 9:
                    sys.stderr.write("%f [%d] CONNECT PLUS CHANNEL GRANT: srcAddr(%06x), grpAddr(%06x), lcn(%d), slot(%d), freq(%f)\n" % (time.time(), self.msgq_id, src_addr, grp_addr, lcn, slot, (freq/1e6)))
                if (grp_addr not in self.active_tgids) or ((grp_addr in self.active_tgids) and (lcn_sl != self.active_tgids[grp_addr])):
                    if self.debug >= 1:
                        sys.stderr.write("%f [%d] Voice update:  tg(%d), freq(%f), slot(%d), lcn(%d)\n" % (time.time(), self.msgq_id, grp_addr, (freq/1e6), slot, lcn))
                    self.frequency_set({'tuner': 1,
                                        'freq': freq,
                                        'slot': (slot + 1),
                                        'chan': chan,
                                        'state': self.states.SRCH,
                                        'type': self.current_type,
                                        'time': time.time()})
                    self.active_tgids[grp_addr] = lcn_sl
                self.chans[lcn].slot[slot].grant_time = time.time()
                self.chans[lcn].slot[slot].grp_addr = grp_addr
                self.chans[lcn].slot[slot].src_addr = src_addr
            elif self.debug >=9:
                sys.stderr.write("%f [%d] CONNECT PLUS CHANNEL GRANT: srcAddr(%06x), grpAddr(%06x), unknown lcn(%d), slot(%d)\n" % (time.time(), self.msgq_id, src_addr, grp_addr, lcn, slot))

    def find_freq(self, lcn):
        if self.chans.has_key(lcn):
            return (self.chan_list.index(lcn), self.chans[lcn].frequency)
        else:
            return (None, None)

    def find_next_chan(self):
        next_chan = (self.current_chan + 1) % len(self.chan_list)
        return next_chan

    def tune_next_chan(self, msgq_id=None, chan=None, slot=None):
        if chan is not None:
            next_ch = chan
        else:
            next_ch = self.find_next_chan()
        
        tune_params = {'tuner': self.msgq_id,
                       'freq': self.chans[self.chan_list[next_ch]].frequency,
                       'chan': next_ch,
                       'time': time.time()}

        if msgq_id is not None:
            tune_params['tuner'] = msgq_id

        if slot is not None:
            tune_params['slot'] = slot

        self.frequency_set(tune_params)

        if (self.msgq_id == 0) and (self.debug >= 1):
            sys.stderr.write("%f [%d] Searching for control channel: lcn(%d), freq(%f)\n" % (time.time(), self.msgq_id, self.chan_list[self.current_chan], (self.chans[self.chan_list[self.current_chan]].frequency/1e6)))

    def process_qmsg(self, msg):
        if msg.arg2() != 1: # discard anything not DMR
            return

        m_type = int(msg.type())
        m_slot = int(msg.arg1()) & 0x1
        m_proto = int(msg.arg2())
        m_buf = msg.to_string()

        if m_type == -1:  # Sync Timeout
            if self.debug >= 9:
                sys.stderr.write("%f [%d] Timeout waiting for sync sequence\n" % (time.time(), self.msgq_id))

            if self.msgq_id == 0: # primary/control channel
                self.cc_timeouts += 1
                if self.cc_timeouts >= CC_HUNT_TIMEOUTS:
                    self.cc_timeouts = 0
                    self.current_state = self.states.IDLE
                    self.tune_next_chan()
                    return
            else:                 # secondary/voice channel
                pass

        elif m_type >= 0: # Receiving a PDU means sync must be present
            if self.msgq_id == 0:
                self.cc_timeouts = 0

        # If voice channel not identified, begin LCN search
        if (self.msgq_id > 0) and (self.current_state == self.states.SRCH) and (self.tune_time + VC_SRCH_TIME < time.time()):
            self.tune_next_chan()

        # log received message
        if self.debug >= 10:
            d_buf = "0x"
            for byte in m_buf:
                d_buf += format(ord(byte),"02x")
            sys.stderr.write("%f [%d] DMR PDU: lcn(%d), state(%d), type(%d), slot(%d), data(%s)\n" % (time.time(), self.msgq_id, self.chan_list[self.current_chan], self.current_state, m_type, m_slot, d_buf))

	if m_type == 0:   # CACH SLC
            self.rx_CACH_SLC(m_buf)
        elif m_type == 1: # CACH CSBK
            pass
        elif m_type == 2: # SLOT PI
            pass
        elif m_type == 3: # SLOT VLC
            self.rx_SLOT_VLC(m_slot, m_buf)
        elif m_type == 4: # SLOT TLC
            self.rx_SLOT_TLC(m_slot, m_buf)
        elif m_type == 5: # SLOT CSBK
            self.rx_SLOT_CSBK(m_slot, m_buf)
        elif m_type == 6: # SLOT MBC
            pass
        elif m_type == 7: # SLOT ELC
            self.rx_SLOT_ELC(m_slot, m_buf)
        elif m_type == 8: # SLOT ERC
            pass
        elif m_type == 9: # SLOT ESB
            pass
        else:             # Unknown Message
            return

        # If this is Capacity Plus, try to keep the first receiver tuned to a control channel
        if (self.current_type == 1) and (self.msgq_id == 0) and (self.current_state > self.states.CC):
            if self.debug >= 1:
                sys.stderr.write("%f [%d] Looking for control channel\n" % (time.time(), self.msgq_id))
            self.cc_timeouts = 0
            self.current_state = self.states.IDLE
            self.tune_next_chan()

    def rx_CACH_SLC(self, m_buf):
        slco = ord(m_buf[0])
        d0 = ord(m_buf[1])
        d1 = ord(m_buf[2])
        d2 = ord(m_buf[3])

        if slco == 0:    # Null Msg (Idle Channel)
            if self.debug >= 9:
                sys.stderr.write("%f [%d] SLCO NULL MSG\n" % (time.time(), self.msgq_id))
        elif slco == 1:  # Act Update
                ts1_act = d0 >> 4;
                ts2_act = d0 & 0xf;
                if self.debug >= 9:
                    sys.stderr.write("%f [%d] ACTIVITY UPDATE TS1(%x), TS2(%x), HASH1(%02x), HASH2(%02x)\n" % (time.time(), self.msgq_id, ts1_act, ts2_act, d1, d2))
        elif slco == 9:  # Connect Plus Voice Channel
            netId = (d0 << 4) + (d1 >> 4)
            siteId = ((d1 & 0xf) << 4) + (d2 >> 4)
            if self.current_type < 0:
                self.current_type = 1
                if self.debug >= 2:
                    sys.stderr.write("%f [%d] System type is TRBO Connect Plus\n" % (time.time(), self.msgq_id))
            # Sometimes only a voice channel exists and no control channel is present.  It's probably better to lock
            # on to a voice channel and wait for it to either dissapear or become a control channel rather than aimlessly
            # cycling the tuning looking for the non-existent control channel.
            self.current_state=self.states.VC
            if self.debug >= 9:
                sys.stderr.write("%f [%d] CONNECT PLUS VOICE CHANNEL: state(%d), netId(%d), siteId(%d)\n" % (time.time(), self.msgq_id, self.current_state, netId, siteId))
        elif slco == 10: # Connect Plus Control Channel
            netId = (d0 << 4) + (d1 >> 4)
            siteId = ((d1 & 0xf) << 4) + (d2 >> 4)
            if self.current_type < 0:
                self.current_type = 1
                if self.debug >= 2:
                    sys.stderr.write("%f [%d] System type is TRBO Connect Plus\n" % (time.time(), self.msgq_id))
            if self.msgq_id == 0:
                if self.current_state != self.states.CC:
                    self.current_state=self.states.CC # Found control channel
                    if self.debug >= 1:
                        sys.stderr.write("%f [%d] Found control channel: lcn(%d), freq(%f)\n" % (time.time(), self.msgq_id, self.chan_list[self.current_chan], (self.chans[self.chan_list[self.current_chan]].frequency/1e6)))
            else:
                if self.current_state != self.states.VC:
                    self.current_state=self.states.VC # Control channel can also carry voice
            if self.debug >= 9:
                sys.stderr.write("%f [%d] CONNECT PLUS CONTROL CHANNEL: state(%d), netId(%d), siteId(%d)\n" % (time.time(), self.msgq_id, self.current_state, netId, siteId))
        elif slco == 15: # Capacity Plus Channel
            lcn = d1
            if self.current_type < 0:
                self.current_type = 0
                self.slot_set({'tuner': 0,'slot': 3})
                if self.debug >= 2:
                    sys.stderr.write("%f [%d] System type is TRBO Connect Plus\n" % (time.time(), self.msgq_id))
            self.rest_lcn = d1
            if self.debug >= 9:
                sys.stderr.write("%f [%d] CAPACITY PLUS REST CHANNEL: lcn(%d)\n" % (time.time(), self.msgq_id, lcn))
        else:
            if self.debug >= 9:
                sys.stderr.write("%f [%d] UNKNOWN CACH SLCO(%d)\n" % (time.time(), self.msgq_id, slco))
            return

    def rx_SLOT_CSBK(self, m_slot, m_buf):
        op  = ord(m_buf[0]) & 0x3f
        fid = ord(m_buf[1])

        if (op == 1) and (fid == 6) and (self.msgq_id == 0):   # ConnectPlus Neighbors (control channel only)
            nb1 = ord(m_buf[2]) & 0x3f
            nb2 = ord(m_buf[3]) & 0x3f
            nb3 = ord(m_buf[4]) & 0x3f
            nb4 = ord(m_buf[5]) & 0x3f
            nb5 = ord(m_buf[6]) & 0x3f
            if self.debug >= 10:
                sys.stderr.write("%f [%d] CONNECT PLUS NEIGHBOR SITES: %d, %d, %d, %d, %d\n" % (time.time(), self.msgq_id, nb1, nb2, nb3, nb4, nb5))

        elif (op == 3) and (fid == 6) and (self.msgq_id == 0): # ConnectPlus Channel Grant (control channel only)
            self.process_grant(m_buf)

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
                sys.stderr.write("%f [%d] CAPACITY PLUS SYS/SITES: rest(%d), beacon(%d), siteId(%d), nn(%d)\n" % (time.time(), self.msgq_id, rest, bcn, site, nn))

        elif (op == 62):                 # 
            pass

    def rx_SLOT_VLC(self, m_slot, m_buf):
        flco    = ord(m_buf[0]) & 0x3f
        fid     = ord(m_buf[1])
        svcopt  = ord(m_buf[2])
        dstaddr = (ord(m_buf[3]) << 16) + (ord(m_buf[4]) << 8) + ord(m_buf[5])
        srcaddr = (ord(m_buf[6]) << 16) + (ord(m_buf[7]) << 8) + ord(m_buf[8])
        if self.debug >= 9:
            sys.stderr.write("%f [%d] VOICE HDR LC: slot(%d), flco(%02x), fid(%02x), svcopt(%02x), srcAddr(%06x), grpAddr(%06x)\n" % (time.time(), self.msgq_id, m_slot, flco, fid, svcopt, srcaddr, dstaddr))

        # TODO: handle flco

    def rx_SLOT_TLC(self, m_slot, m_buf):
        flco    = ord(m_buf[0]) & 0x3f
        fid     = ord(m_buf[1])
        svcopt  = ord(m_buf[2])
        dstaddr = (ord(m_buf[3]) << 16) + (ord(m_buf[4]) << 8) + ord(m_buf[5])
        srcaddr = (ord(m_buf[6]) << 16) + (ord(m_buf[7]) << 8) + ord(m_buf[8])
        if self.debug >= 9:
            sys.stderr.write("%f [%d] VOICE TERM LC: slot(%d), flco(%02x), fid(%02x), svcopt(%02x), srcAddr(%06x), grpAddr(%06x)\n" % (time.time(), self.msgq_id, m_slot, flco, fid, svcopt, srcaddr, dstaddr))

        # TODO: handle flco

    def rx_SLOT_ELC(self, m_slot, m_buf):
        flco    = ord(m_buf[0]) & 0x3f
        fid     = ord(m_buf[1])
        svcopt  = ord(m_buf[2])
        dstaddr = (ord(m_buf[3]) << 16) + (ord(m_buf[4]) << 8) + ord(m_buf[5])
        srcaddr = (ord(m_buf[6]) << 16) + (ord(m_buf[7]) << 8) + ord(m_buf[8])
        if self.debug >= 9:
            sys.stderr.write("%f [%d] VOICE EMB LC: slot(%d), flco(%02x), fid(%02x), svcopt(%02x), srcAddr(%06x), grpAddr(%06x)\n" % (time.time(), self.msgq_id, m_slot, flco, fid, svcopt, srcaddr, dstaddr))

        # TODO: handle flco


class rx_ctl(object):
    def __init__(self, debug=0, frequency_set=None, slot_set=None, chans=None):
        self.frequency_set = frequency_set
        self.slot_set = slot_set
        self.debug = debug
        self.receivers = {}

        self.chans = {}
        for _chan in chans:
            self.chans[_chan['lcn']] = dmr_chan(debug, _chan['lcn'], _chan['frequency'])
            sys.stderr.write("%f Configuring channel lcn(%d), freq(%f), cc(%d)\n" % (time.time(), _chan['lcn'], (_chan['frequency']/1e6), _chan['cc']))

    def post_init(self):
        for rx_id in self.receivers:
            self.receivers[rx_id].post_init()

    def add_receiver(self, msgq_id):
        self.receivers[msgq_id] = dmr_receiver(msgq_id, self.frequency_set, self.slot_set, self.chans, self.debug)

    def process_qmsg(self, msg):
        if msg.arg2() != 1: # discard anything not DMR
            return

        self.check_expired_grants()

        m_rxid = int(msg.arg1()) >> 1
        if self.receivers.has_key(m_rxid):
            self.receivers[m_rxid].process_qmsg(msg)

    def check_expired_grants(self):
        cur_time = time.time()
        for tgid in list(self.receivers[0].active_tgids):
            act_lcn = self.receivers[0].active_tgids[tgid] >> 1
            act_slot = self.receivers[0].active_tgids[tgid] & 1

            if (self.chans[act_lcn].slot[act_slot].grant_time + TGID_HOLD_TIME) < cur_time:
                self.receivers[0].active_tgids.pop(tgid, None)
                if self.receivers[0].current_type > 0: # turn off voice channel receiver for Connect Plus systems
                    if self.debug >=2:
                        sys.stderr.write("%f Shutting off voice channel lcn(%d), slot(%d)\n" % (time.time(), act_lcn, act_slot))
                    self.receivers[1].vc_timeouts = 0
                    self.receivers[1].current_state = self.receivers[1].states.IDLE
                    self.slot_set({'tuner': 1,'slot': 4})

