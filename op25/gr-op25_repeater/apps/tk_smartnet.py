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
import collections
import ctypes
import time
import json
from log_ts import log_ts
from collections import deque

OSW_QUEUE_SIZE = 3      # Some OSWs can be 3 commands long
CC_TIMEOUT_RETRIES = 3  # Number of control channel framing timeouts before hunting

class rx_ctl(object):
    def __init__(self, debug=0, frequency_set=None, slot_set=None, chans={}):
        self.frequency_set = frequency_set
        self.debug = debug
        self.receivers = {}
        self.systems = []
        self.chans = chans

        for chan in self.chans:
            self.systems.append(osw_receiver(debug=self.debug, frequency_set=self.frequency_set, config=chan))

    def add_receiver(self, msgq_id, config):
        if msgq_id in self.receivers:
            return

        rx_sys = None              # find first system that needs a receiver assigned for control channel use
        for sysid in self.systems: # once all control channels are assigned, remaining receivers will be available for voice
            if sysid.get_msgq_id() < 0:
                sysid.set_msgq_id(msgq_id)
                rx_sys = sysid
                break
        self.receivers[msgq_id] = {'msgq_id': msgq_id,
                                   'config' : config,
                                   'rx_sys' : rx_sys}

    def post_init(self):
       for sysid in self.systems:
           sysid.post_init()

    def process_qmsg(self, msg):
        m_rxid = int(msg.arg1()) >> 1
        if m_rxid in self.receivers and self.receivers[m_rxid]['rx_sys'] is not None:
            self.receivers[m_rxid]['rx_sys'].process_qmsg(msg)

class osw_receiver(object):
    def __init__(self, debug, frequency_set, config):
        self.debug = debug
        self.msgq_id = -1
        self.config = config
        self.frequency_set = frequency_set
        self.osw_q = deque(maxlen=OSW_QUEUE_SIZE)
        self.voice_frequencies = {}
        self.talkgroups = {}
        self.cc_list = []
        self.cc_index = -1
        self.cc_retries = 0

    def get_msgq_id(self):
        return self.msgq_id

    def set_msgq_id(self, msgq_id):
        self.msgq_id = msgq_id

    def post_init(self):
        if self.msgq_id < 0:
            sys.stderr.write("%f Smartnet system has no channel assigned!\n" % (time.time()))
            return

        if self.debug >= 1:
            sys.stderr.write("%f [%d] Initializing Smartnet system\n" % (time.time(), self.msgq_id))

        for f in self.config['control_channel_list'].split(','):
            self.cc_list.append(self.get_frequency(f))

        self.tune_next_cc()

    def tune_next_cc(self):
        self.cc_retries = 0
        self.cc_index += 1
        if self.cc_index >= len(self.cc_list):
            self.cc_index = 0
        tune_params = {'tuner': self.msgq_id,
                       'freq': self.cc_list[self.cc_index]}
        self.frequency_set(tune_params)

    def get_frequency(self, f):    # return frequency in Hz
        if f.find('.') == -1:    # assume in Hz
            return int(f)
        else:     # assume in MHz due to '.'
            return int(float(f) * 1000000)

    def process_qmsg(self, msg):
        m_proto = ctypes.c_int16(msg.type() >> 16).value  # upper 16 bits of msg.type() is signed protocol
        if m_proto != 2: # Smartnet m_proto=2
            return

        m_type = ctypes.c_int16(msg.type() & 0xffff).value
        m_rxid = int(msg.arg1()) >> 1
        m_ts = float(msg.arg2())

        if (m_type == -1):  # Control Channel Timeout
            self.cc_retries += 1
            if self.cc_retries >= CC_TIMEOUT_RETRIES:
                self.tune_next_cc()

        elif (m_type == 0): # OSW Receieved
            s = msg.to_string()

            osw_addr = (ord(s[0]) << 8) + ord(s[1])
            osw_grp  =  ord(s[2])
            osw_cmd  = (ord(s[3]) << 8) + ord(s[4])
            self.enqueue(osw_addr, osw_grp, osw_cmd)
            self.process_osws()

    def is_chan(self, cmd): # Is the 'cmd' a valid frequency or an actual command
        band = self.config['bandplan'][:3]
        if band == "800":
            if (cmd >= 0 and cmd <= 0x2F7) or (cmd >= 0x32f and cmd <= 0x33F) or (cmd >= 0x3c1 and cmd <= 0x3FE) or cmd == 0x3BE:
                return True
        elif band == "900":
            if cmd >= 0 and cmd <= 0x1DE:
                return True
        elif band == "400":
            if (cmd >= int(self.config['bp_offset']) and cmd <= (int(self.config['bp_offset']) + 380)):
                return True
            else:
                return False
        return False

    def get_freq(self, cmd): # Convert 'cmd' into band-dependent frequency
        freq = 0.0
        band = self.config['bandplan'][:3]
        subtype = self.config['bandplan'][3:len(self.config['bandplan'])].lower().lstrip("_-:")

        if band == "800":
            if cmd <= 0x2CF:
                if subtype == "reband" and cmd >= 0x1B8 and cmd <= 0x22F: # REBAND site
                    freq = 851.0250 + (0.025 * (cmd - 0x1B8))
                elif subtype == "splinter" and cmd <= 0x257:              # SPLINTER site
                    freq = 851.0 + (0.025 * cmd)
                else:
                    freq = 851.0125 + (0.025 * cmd)                       # STANDARD site
            elif cmd <= 0x2f7:
                freq = 866.0000 + (0.025 * (cmd - 0x2D0))
            elif cmd >= 0x32F and cmd <= 0x33F:
                freq = 867.0000 + (0.025 * (cmd - 0x32F))
            elif cmd == 0x3BE:
                freq = 868.9750
            elif cmd >= 0x3C1 and cmd <= 0x3FE:
                freq = 867.4250 + (0.025 * (cmd - 0x3C1))

        elif band == "900":
            freq = 935.0125 + (0.0125 * cmd)

        elif band == "400":
            bp_offset = self.config['bp_offset']
            bp_high = self.config['bp_high']
            bp_base = self.config['bp_base']
            bp_spacing = self.config['bp_spacing']
            high_cmd = bp_offset + bp_high - bp_base / bp_spacing

            if (cmd >= bp_offset) and (cmd < high_cmd):
                freq = bp_base + (bp_spacing * (cmd - bp_offset ))
        return freq

    def enqueue(self, addr, grp, cmd):
        if self.is_chan(cmd):
            freq = self.get_freq(cmd)
        else:
            freq = 0.0
        self.osw_q.append((addr, (grp != 0), cmd, self.is_chan(cmd), freq))

    def process_osws(self):
        if len(self.osw_q) < OSW_QUEUE_SIZE:
            return

        osw_addr, osw_grp, osw_cmd, osw_ch, osw_f = self.osw_q.popleft()
        if self.debug >= 11:
            if osw_ch:
                sys.stderr.write("%s [%d] SMARTNET OSW (0x%04x,%s,0x%03x,%f)\n" % (log_ts.get(), self.msgq_id, osw_addr, osw_grp, osw_cmd, osw_f))
            else:
                sys.stderr.write("%s [%d] SMARTNET OSW (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, osw_addr, osw_grp, osw_cmd))

        if osw_cmd == 0x308:
            src_rid = osw_addr
            osw_addr, osw_grp, osw_cmd, osw_ch, osw_f = self.osw_q.popleft()
            if osw_ch and osw_grp and (osw_addr != 0) and (src_rid != 0):
                dst_tgid = osw_addr
                tgt_freq = osw_f
                self.update_voice_frequency(tgt_freq, dst_tgid, src_rid, mode=0)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET GROUP GRANT src(%d), tgid(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, tgt_freq))
        elif osw_cmd == 0x321:   # Two-OSW digital group voice grant
            src_rid = osw_addr
            osw_addr, osw_grp, osw_cmd, osw_ch, osw_f = self.osw_q.popleft()
            if osw_ch and osw_grp and (osw_addr != 0):
                dst_tgid = osw_addr
                tgt_freq = osw_f
                self.update_voice_frequency(tgt_freq, dst_tgid, src_rid, mode=1)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET ASTRO GRANT src(%d), tgid(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, tgt_freq))
        elif osw_ch and osw_grp: # Single-OSW voice update
            dst_tgid = osw_addr
            tgt_freq = osw_f
            self.update_voice_frequency(tgt_freq, dst_tgid)
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET GROUP UPDATE tgid(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, dst_tgid, tgt_freq))

    def update_voice_frequency(self, frequency, tgid=None, srcaddr=-1, mode=-1):
        if not frequency:    # e.g., channel identifier not yet known
            return
        self.update_talkgroups(frequency, tgid, srcaddr)
        if frequency not in self.voice_frequencies:
            self.voice_frequencies[frequency] = {'counter':0}
            sorted_freqs = collections.OrderedDict(sorted(self.voice_frequencies.items()))
            self.voice_frequencies = sorted_freqs
            if self.debug >= 5:
                sys.stderr.write('%s [%d] new freq=%f\n' % (log_ts.get(), self.msgq_id, frequency))

        if 'tgid' not in self.voice_frequencies[frequency]:
            self.voice_frequencies[frequency]['tgid'] = [None]
            self.voice_frequencies[frequency]['mode'] = 0
        self.voice_frequencies[frequency]['tgid'] = tgid
        self.voice_frequencies[frequency]['counter'] += 1
        self.voice_frequencies[frequency]['time'] = time.time()
        if mode >= 0:
            self.voice_frequencies[frequency]['mode'] = mode

    def update_talkgroups(self, frequency, tgid, srcaddr):
        self.update_talkgroup(frequency, tgid, srcaddr)
        #if tgid in self.patches:
        #    for ptgid in self.patches[tgid]['ga']:
        #        self.update_talkgroup(frequency, ptgid, srcaddr)
        #        if self.debug >= 5:
        #            sys.stderr.write('%s update_talkgroups: sg(%d) patched tgid(%d)\n' % (log_ts.get(), tgid, ptgid))

    def update_talkgroup(self, frequency, tgid, srcaddr):
        if self.debug >= 5:
            sys.stderr.write('%s [%d] set tgid=%s, srcaddr=%s\n' % (log_ts.get(), self.msgq_id, tgid, srcaddr))
        
        if tgid not in self.talkgroups:
            self.talkgroups[tgid] = {'counter':0}
            self.talkgroups[tgid]['srcaddr'] = 0
            if self.debug >= 5:
                #sys.stderr.write('%s new tgid=%s %s prio %d\n' % (log_ts.get(), tgid, self.get_tag(tgid), self.get_prio(tgid)))
                sys.stderr.write('%s [%d] new tgid=%s\n' % (log_ts.get(), self.msgq_id, tgid))
        self.talkgroups[tgid]['time'] = time.time()
        self.talkgroups[tgid]['frequency'] = frequency
        #self.talkgroups[tgid]['prio'] = self.get_prio(tgid)
        if srcaddr >= 0:
            self.talkgroups[tgid]['srcaddr'] = srcaddr

    def find_talkgroup(self, start_time, tgid=None, hold=False):
        tgt_tgid = None
        #self.blacklist_update(start_time)

        if tgid is not None and tgid in self.talkgroups:
            tgt_tgid = tgid

        for active_tgid in self.talkgroups:
            if hold:
                break
            if self.talkgroups[active_tgid]['time'] < start_time:
                continue
            #if active_tgid in self.blacklist and (not self.whitelist or active_tgid not in self.whitelist):
            #    continue
            #if self.whitelist and active_tgid not in self.whitelist:
            #    continue
            if tgt_tgid is None:
                tgt_tgid = active_tgid
            #elif self.talkgroups[active_tgid]['prio'] < self.talkgroups[tgt_tgid]['prio']:
            #    tgt_tgid = active_tgid
                   
        if tgt_tgid is not None and self.talkgroups[tgt_tgid]['time'] >= start_time:
            return self.talkgroups[tgt_tgid]['frequency'], tgt_tgid, self.talkgroups[tgt_tgid]['srcaddr']
        return None, None, None


