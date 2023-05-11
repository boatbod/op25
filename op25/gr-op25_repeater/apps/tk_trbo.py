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
import ctypes
import time
import json
import traceback
from helper_funcs import *
from log_ts import log_ts

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

    def set_debug(self, dbglvl):
        self.debug = dbglvl

class dmr_receiver:
    def __init__(self, msgq_id, frequency_set=None, fa_ctrl=None, chans={}, debug=0):
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
        self.fa_ctrl = fa_ctrl
        self.msgq_id = msgq_id
        self.debug = debug
        self.cc_timeouts = 0
        self.chans = chans
        self.chan_list = list(self.chans.keys())
        self.current_chan = 0
        self.rest_lcn = 0
        self.active_tgids = {}
        self.tune_time = 0

    def set_debug(self, dbglvl):
        self.debug = dbglvl

    def post_init(self):
        if self.debug >= 1:
            sys.stderr.write("%s [%d] Initializing DMR receiver\n" % (log_ts.get(), self.msgq_id))
        if self.msgq_id == 0:
            self.tune_next_chan(msgq_id=0, chan=0, slot=0)
        else:
            self.tune_next_chan(msgq_id=1, chan=0, slot=4)

    def to_json(self):  # ugly but required for compatibility with P25 trunking and terminal modules
        d = {}
        d['system']         = "tk_trbo"
        d['top_line']       = "OP25 TRBO Trunking"
        d['secondary']      = ""
        d['frequencies']    = {}
        d['frequency_data'] = {}
        d['last_tsbk'] = 0
        d['adjacent_data'] = ""
        return json.dumps(d)

    def process_grant(self, m_buf):
            src_addr = get_ordinals(m_buf[2:5])
            grp_addr = get_ordinals(m_buf[5:8])
            lcn      = get_ordinals(m_buf[8]) >> 4
            slot     = (get_ordinals(m_buf[8]) >> 3) & 0x1
            chan, freq = self.find_freq(lcn)
            if freq is not None:
                lcn_sl = (lcn << 1) + slot
                if self.debug >= 9:
                    sys.stderr.write("%s [%d] CONNECT PLUS CHANNEL GRANT: srcAddr(%06x), grpAddr(%06x), lcn(%d), slot(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, src_addr, grp_addr, lcn, slot, (freq/1e6)))
                if (grp_addr not in self.active_tgids) or ((grp_addr in self.active_tgids) and (lcn_sl != self.active_tgids[grp_addr])):
                    if self.debug >= 1:
                        sys.stderr.write("%s [%d] Voice update:  tg(%d), freq(%f), slot(%d), lcn(%d)\n" % (log_ts.get(), self.msgq_id, grp_addr, (freq/1e6), slot, lcn))
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
                sys.stderr.write("%s [%d] CONNECT PLUS CHANNEL GRANT: srcAddr(%06x), grpAddr(%06x), unknown lcn(%d), slot(%d)\n" % (log_ts.get(), self.msgq_id, src_addr, grp_addr, lcn, slot))

    def find_freq(self, lcn):
        if lcn in self.chans:
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
            sys.stderr.write("%s [%d] Searching for control channel: lcn(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, self.chan_list[self.current_chan], (self.chans[self.chan_list[self.current_chan]].frequency/1e6)))

    def ui_command(self, msg):
        pass          # TODO: handle these requests

    def process_qmsg(self, msg):
        m_type = ctypes.c_int16(msg.type() & 0xffff).value  # lower 16 bits of msg.type() is signed message type
        m_slot = int(msg.arg1()) & 0x1                      # message slot id
        m_ts   = float(msg.arg2())                          # message sender timestamp
        m_buf = msg.to_string()                             # message data

        if m_type == -1:    # Sync Timeout
            if self.debug >= 9:
                sys.stderr.write("%s [%d] Timeout waiting for sync sequence\n" % (log_ts.get(), self.msgq_id))

            if self.msgq_id == 0: # primary/control channel
                self.cc_timeouts += 1
                if self.cc_timeouts >= CC_HUNT_TIMEOUTS:
                    self.cc_timeouts = 0
                    self.current_state = self.states.IDLE
                    self.tune_next_chan()
                    return
            else:                 # secondary/voice channel
                pass

        elif m_type >= 0:   # Receiving a PDU means sync must be present
            if self.msgq_id == 0:
                self.cc_timeouts = 0

        # If voice channel not identified, begin LCN search
        if (self.msgq_id > 0) and (self.current_state == self.states.SRCH) and (self.tune_time + VC_SRCH_TIME < time.time()):
            self.tune_next_chan()

        # log received message
        if self.debug >= 10:
            d_buf = "0x"
            for byte in m_buf:
                d_buf += format(get_ordinals(byte),"02x")
            sys.stderr.write("%s [%d] DMR PDU: lcn(%d), state(%d), type(%d), slot(%d), data(%s)\n" % (log_ts.get(), self.msgq_id, self.chan_list[self.current_chan], self.current_state, m_type, m_slot, d_buf))

        if m_type == 0:   # CACH SLC
            self.rx_CACH_SLC(m_buf)
        elif m_type == 1: # CACH CSBK
            pass
        elif m_type == 2: # SLOT PI
            self.rx_SLOT_PI(m_slot, m_buf)
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
                sys.stderr.write("%s [%d] Looking for control channel\n" % (log_ts.get(), self.msgq_id))
            self.cc_timeouts = 0
            self.current_state = self.states.IDLE
            self.tune_next_chan()

    def rx_CACH_SLC(self, m_buf):
        slco = get_ordinals(m_buf[0])
        d0   = get_ordinals(m_buf[1])
        d1   = get_ordinals(m_buf[2])
        d2   = get_ordinals(m_buf[3])

        if slco == 0:    # Null Msg (Idle Channel)
            if self.debug >= 9:
                sys.stderr.write("%s [%d] SLCO NULL MSG\n" % (log_ts.get(), self.msgq_id))
        elif slco == 1:  # Act Update
                ts1_act = d0 >> 4;
                ts2_act = d0 & 0xf;
                if self.debug >= 9:
                    sys.stderr.write("%s [%d] ACTIVITY UPDATE TS1(%x), TS2(%x), HASH1(%02x), HASH2(%02x)\n" % (log_ts.get(), self.msgq_id, ts1_act, ts2_act, d1, d2))
        elif slco == 9:  # Connect Plus Voice Channel
            netId = (d0 << 4) + (d1 >> 4)
            siteId = ((d1 & 0xf) << 4) + (d2 >> 4)
            if self.current_type < 0:
                self.current_type = 1
                if self.debug >= 2:
                    sys.stderr.write("%s [%d] System type is TRBO Connect Plus\n" % (log_ts.get(), self.msgq_id))
            # Sometimes only a voice channel exists and no control channel is present.  It's probably better to lock
            # on to a voice channel and wait for it to either dissapear or become a control channel rather than aimlessly
            # cycling the tuning looking for the non-existent control channel.
            self.current_state=self.states.VC
            if self.debug >= 9:
                sys.stderr.write("%s [%d] CONNECT PLUS VOICE CHANNEL: state(%d), netId(%d), siteId(%d)\n" % (log_ts.get(), self.msgq_id, self.current_state, netId, siteId))
        elif slco == 10: # Connect Plus Control Channel
            netId = (d0 << 4) + (d1 >> 4)
            siteId = ((d1 & 0xf) << 4) + (d2 >> 4)
            if self.current_type < 0:
                self.current_type = 1
                if self.debug >= 2:
                    sys.stderr.write("%s [%d] System type is TRBO Connect Plus\n" % (log_ts.get(), self.msgq_id))
            if self.msgq_id == 0:
                if self.current_state != self.states.CC:
                    self.current_state=self.states.CC # Found control channel
                    if self.debug >= 1:
                        sys.stderr.write("%s [%d] Found control channel: lcn(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, self.chan_list[self.current_chan], (self.chans[self.chan_list[self.current_chan]].frequency/1e6)))
            else:
                if self.current_state != self.states.VC:
                    self.current_state=self.states.VC # Control channel can also carry voice
            if self.debug >= 9:
                sys.stderr.write("%s [%d] CONNECT PLUS CONTROL CHANNEL: state(%d), netId(%d), siteId(%d)\n" % (log_ts.get(), self.msgq_id, self.current_state, netId, siteId))
        elif slco == 15: # Capacity Plus Channel
            lcn = d1
            if self.current_type < 0:
                self.current_type = 0
                self.fa_ctrl({'tuner': 0, 'cmd': 'set_slotid', 'slotid': 3})
                if self.debug >= 2:
                    sys.stderr.write("%s [%d] System type is TRBO Connect Plus\n" % (log_ts.get(), self.msgq_id))
            self.rest_lcn = d1
            if self.debug >= 9:
                sys.stderr.write("%s [%d] CAPACITY PLUS REST CHANNEL: lcn(%d)\n" % (log_ts.get(), self.msgq_id, lcn))
        else:
            if self.debug >= 9:
                sys.stderr.write("%s [%d] UNKNOWN CACH SLCO(%d)\n" % (log_ts.get(), self.msgq_id, slco))
            return

    def rx_SLOT_CSBK(self, m_slot, m_buf):
        op  = get_ordinals(m_buf[0]) & 0x3f
        fid = get_ordinals(m_buf[1])

        if (op == 1) and (fid == 6) and (self.msgq_id == 0):   # ConnectPlus Neighbors (control channel only)
            nb1 = get_ordinals(m_buf[2]) & 0x3f
            nb2 = get_ordinals(m_buf[3]) & 0x3f
            nb3 = get_ordinals(m_buf[4]) & 0x3f
            nb4 = get_ordinals(m_buf[5]) & 0x3f
            nb5 = get_ordinals(m_buf[6]) & 0x3f
            if self.debug >= 10:
                sys.stderr.write("%s [%d] CONNECT PLUS NEIGHBOR SITES: %d, %d, %d, %d, %d\n" % (log_ts.get(), self.msgq_id, nb1, nb2, nb3, nb4, nb5))

        elif (op == 3) and (fid == 6) and (self.msgq_id == 0): # ConnectPlus Channel Grant (control channel only)
            self.process_grant(m_buf)

        elif (op == 59) and (fid == 16): # CapacityPlus Sys/Sites/TS
            fl   =  (get_ordinals(m_buf[2]) >> 6)
            ts   = ((get_ordinals(m_buf[2]) >> 5) & 0x1)
            rest =  (get_ordinals(m_buf[2]) & 0x1f)
            bcn  = ((get_ordinals(m_buf[3]) >> 7) & 0x1)
            site = ((get_ordinals(m_buf[3]) >> 3) & 0xf)
            nn   =  (get_ordinals(m_buf[3]) & 0x7)
            if nn > 6:
                nn = 6
            if self.debug >= 9:
                sys.stderr.write("%s [%d] CAPACITY PLUS SYS/SITES: rest(%d), beacon(%d), siteId(%d), nn(%d)\n" % (log_ts.get(), self.msgq_id, rest, bcn, site, nn))

        elif (op == 62):                 # 
            pass

    def rx_SLOT_VLC(self, m_slot, m_buf):
        flco    = get_ordinals(m_buf[0]) & 0x3f
        fid     = get_ordinals(m_buf[1])
        svcopt  = get_ordinals(m_buf[2])
        dstaddr = get_ordinals(m_buf[3:6])
        srcaddr = get_ordinals(m_buf[6:9])
        if self.debug >= 9:
            sys.stderr.write("%s [%d] VOICE HDR LC: slot(%d), flco(%02x), fid(%02x), svcopt(%02x), srcAddr(%06x), grpAddr(%06x)\n" % (log_ts.get(), self.msgq_id, m_slot, flco, fid, svcopt, srcaddr, dstaddr))

        # TODO: handle flco

    def rx_SLOT_TLC(self, m_slot, m_buf):
        flco    = get_ordinals(m_buf[0]) & 0x3f
        fid     = get_ordinals(m_buf[1])
        svcopt  = get_ordinals(m_buf[2])
        dstaddr = get_ordinals(m_buf[3:6])
        srcaddr = get_ordinals(m_buf[6:9])
        if self.debug >= 9:
            sys.stderr.write("%s [%d] VOICE TERM LC: slot(%d), flco(%02x), fid(%02x), svcopt(%02x), srcAddr(%06x), grpAddr(%06x)\n" % (log_ts.get(), self.msgq_id, m_slot, flco, fid, svcopt, srcaddr, dstaddr))

        # TODO: handle flco

    def rx_SLOT_ELC(self, m_slot, m_buf):
        flco    = get_ordinals(m_buf[0]) & 0x3f
        fid     = get_ordinals(m_buf[1])
        svcopt  = get_ordinals(m_buf[2])
        dstaddr = get_ordinals(m_buf[3:6])
        srcaddr = get_ordinals(m_buf[6:9])
        if self.debug >= 9:
            sys.stderr.write("%s [%d] VOICE EMB LC: slot(%d), flco(%02x), fid(%02x), svcopt(%02x), srcAddr(%06x), grpAddr(%06x)\n" % (log_ts.get(), self.msgq_id, m_slot, flco, fid, svcopt, srcaddr, dstaddr))

        # TODO: handle flco

    def rx_SLOT_PI(self, m_slot, m_buf):
        algid   = get_ordinals(m_buf[0])
        keyid   = get_ordinals(m_buf[2])
        mi      = get_ordinals(m_buf[3:7])
        dstaddr = get_ordinals(m_buf[7:10])
        if self.debug >= 9:
            sys.stderr.write("%s [%d] PI HEADER: slot(%d), algId(%02x), keyId(%02x), mi(%08x), grpAddr(%06x)\n" % (log_ts.get(), self.msgq_id, m_slot, algid, keyid, mi, dstaddr))

    def get_status(self):
        d = {}
        d['freq'] = 0
        d['tdma'] = None
        d['tgid'] = None
        d['system'] = ""
        d['tag'] = ""
        d['srcaddr'] = 0
        d['srctag'] = ""
        d['encrypted'] = 0
        d['mode'] = None
        d['stream'] = None
        d['msgqid'] = self.msgq_id
        return json.dumps(d)


class rx_ctl(object):
    def __init__(self, debug=0, frequency_set=None, nbfm_ctrl=None, fa_ctrl=None, chans={}):
        self.frequency_set = frequency_set
        self.fa_ctrl = fa_ctrl
        self.debug = debug
        self.receivers = {}

        self.chans = {}
        for _chan in chans:
            if not 'lcn' in _chan:
                sys.stderr.write("%s Trunking chan[%d] has no lcn defined\n" % (log_ts.get(), chans.index(_chan)))
                continue
            self.chans[_chan['lcn']] = dmr_chan(debug, _chan['lcn'], get_frequency(from_dict(_chan, 'frequency', 0.0)))
            sys.stderr.write("%s Configuring channel lcn(%d), freq(%f), cc(%d)\n" % (log_ts.get(), _chan['lcn'], get_frequency(from_dict(_chan, 'frequency', 0.0))/1e6, int(from_dict(_chan, 'cc', 0))))
        if len(self.chans) == 0:
            sys.stderr.write("%s Trunking has no valid chans, aborting\n" % (log_ts.get()))
            exit(1)

    def set_debug(self, dbglvl):
        self.debug = dbglvl
        for chan in self.chans:
            self.chans[chan].set_debug(dbglvl)
        for rcvr in self.receivers:
            self.receivers[rcvr].set_debug(dbglvl)

    def post_init(self):
        for rx_id in self.receivers:
            self.receivers[rx_id].post_init()

    def add_receiver(self, msgq_id, config, meta_q = None, freq = 0):
        self.receivers[msgq_id] = dmr_receiver(msgq_id, self.frequency_set, self.fa_ctrl, self.chans, self.debug)

    def process_qmsg(self, msg):
        m_proto = ctypes.c_int16(msg.type() >> 16).value    # upper 16 bits of msg.type() is signed protocol
        m_type = ctypes.c_int16(msg.type() & 0xffff).value  # lower 16 bits of msg.type() is signed message type
        if (m_proto != 1) and (m_type != -1): # DMR m_proto=1 except for timeout when m_proto=0
            return

        self.check_expired_grants()

        m_rxid = int(msg.arg1()) >> 1
        if m_rxid in self.receivers:
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
                        sys.stderr.write("%s Shutting off voice channel lcn(%d), slot(%d)\n" % (log_ts.get(), act_lcn, act_slot))
                    self.receivers[1].vc_timeouts = 0
                    self.receivers[1].current_state = self.receivers[1].states.IDLE
                    self.fa_ctrl({'tuner': 1, 'cmd': 'set_slotid', 'slotid': 4})

    def get_chan_status(self):
        d = {'json_type': 'channel_update'}
        rcvr_ids = []
        for rcvr in self.receivers:
            if self.receivers[rcvr] is not None:
                rcvr_name = ("chan[%d]" % self.receivers[rcvr].msgq_id)
                d[str(rcvr)] = json.loads(self.receivers[rcvr].get_status())
                d[str(rcvr)]['name'] = rcvr_name
                rcvr_ids.append(str(rcvr))
        d['channels'] = rcvr_ids
        return json.dumps(d)

    def to_json(self):
        d = {'json_type': 'trunk_update'}
        syid = 0;
        for rcvr in self.receivers:
            d[syid] = json.loads(self.receivers[rcvr].to_json())
            syid += 1
        d['nac'] = 0
        return json.dumps(d)

