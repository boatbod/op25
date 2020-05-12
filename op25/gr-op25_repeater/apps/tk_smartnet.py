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

OSW_QUEUE_SIZE = 3       # Some OSWs can be 3 commands long
CC_TIMEOUT_RETRIES = 3   # Number of control channel framing timeouts before hunting
VC_TIMEOUT_RETRIES = 3   # Number of voice channel framing timeouts before expiry
TGID_EXPIRY_TIME = 1.0   # Number of seconds to allow tgid to remain active with no updates received
EXPIRY_TIMER = 0.2       # Number of seconds between checks for tgid expiry

#################
def get_frequency( f):    # return frequency in Hz
    if str(f).find('.') == -1:    # assume in Hz
        return int(f)
    else:     # assume in MHz due to '.'
        return int(float(f) * 1000000)

#################
class rx_ctl(object):
    def __init__(self, debug=0, frequency_set=None, slot_set=None, chans={}):
        self.frequency_set = frequency_set
        self.slot_set = slot_set
        self.debug = debug
        self.receivers = {}
        self.systems = []
        self.chans = chans

        for chan in self.chans:
            self.systems.append(osw_receiver(debug=self.debug,
                                             frequency_set=self.frequency_set,
                                             request_rx=self.request_voice_receiver,
                                             config=chan))

    def add_receiver(self, msgq_id, config):
        if msgq_id in self.receivers:
            return

        rx_sys = None
        rx_type = 0
        cfg_dest = config['destination'].lower()
        if cfg_dest == "smartnet":   # control channel
            for sysid in self.systems:
                if sysid.get_msgq_id() < 0:
                    sysid.set_msgq_id(msgq_id)
                    rx_sys = sysid
                    rx_type = 1
                    break
            if rx_sys is None:
                sys.stderr.write("%s [%d] Receiver destination is 'smartnet' but insufficient control channels defined\n" % (log_ts.get(), msgq_id))
        elif cfg_dest[:4] == "udp:": # voice channel
            rx_sys = voice_receiver(debug=self.debug, msgq_id=msgq_id, frequency_set=self.frequency_set, slot_set=self.slot_set)
            rx_type = 2

        self.receivers[msgq_id] = {'msgq_id': msgq_id,
                                   'config' : config,
                                   'rx_sys' : rx_sys,
                                   'rx_type': rx_type}

    def post_init(self):
        for rx in self.receivers:
            if self.receivers[rx]['rx_sys'] is not None:
                self.receivers[rx]['rx_sys'].post_init()

    def process_qmsg(self, msg):
        m_rxid = int(msg.arg1()) >> 1
        if m_rxid in self.receivers and self.receivers[m_rxid]['rx_sys'] is not None:
            self.receivers[m_rxid]['rx_sys'].process_qmsg(msg)

    def request_voice_receiver(self):
        rx_sys = None
        for rx in self.receivers:
            if (self.receivers[rx]['rx_type'] == 2) and self.receivers[rx]['rx_sys'].available():
                rx_sys = self.receivers[rx]['rx_sys']
                break
        return rx_sys

#################
class osw_receiver(object):
    def __init__(self, debug, frequency_set, request_rx, config):
        self.debug = debug
        self.msgq_id = -1
        self.config = config
        self.frequency_set = frequency_set
        self.request_rx = request_rx
        self.osw_q = deque(maxlen=OSW_QUEUE_SIZE)
        self.voice_frequencies = {}
        self.talkgroups = {}
        self.cc_list = []
        self.cc_index = -1
        self.cc_retries = 0
        self.last_expiry_check = 0.0

    def get_msgq_id(self):
        return self.msgq_id

    def set_msgq_id(self, msgq_id):
        self.msgq_id = msgq_id

    def post_init(self):
        if self.msgq_id < 0:
            sys.stderr.write("%f Smartnet system has no channel assigned!\n" % (time.time()))
            return

        if self.debug >= 1:
            sys.stderr.write("%s [%d] Initializing Smartnet system\n" % (log_ts.get(), self.msgq_id))

        for f in self.config['control_channel_list'].split(','):
            self.cc_list.append(get_frequency(f))

        self.tune_next_cc()

    def tune_next_cc(self):
        self.cc_retries = 0
        self.cc_index += 1
        if self.cc_index >= len(self.cc_list):
            self.cc_index = 0
        tune_params = {'tuner': self.msgq_id,
                       'freq': self.cc_list[self.cc_index]}
        self.frequency_set(tune_params)

    def process_qmsg(self, msg):
        m_proto = ctypes.c_int16(msg.type() >> 16).value  # upper 16 bits of msg.type() is signed protocol
        if m_proto != 2: # Smartnet m_proto=2
            return

        m_type = ctypes.c_int16(msg.type() & 0xffff).value
        m_rxid = int(msg.arg1()) >> 1
        m_ts = float(msg.arg2())

        if (m_type == -1):  # Control Channel Timeout
            if self.debug > 0:
                sys.stderr.write("%s [%d] control channel timeout\n" % (log_ts.get(), self.msgq_id))
            self.cc_retries += 1
            if self.cc_retries >= CC_TIMEOUT_RETRIES:
                self.tune_next_cc()

        elif (m_type == 0): # OSW Receieved
            s = msg.to_string()

            osw_addr = (ord(s[0]) << 8) + ord(s[1])
            osw_grp  =  ord(s[2])
            osw_cmd  = (ord(s[3]) << 8) + ord(s[4])
            self.enqueue(osw_addr, osw_grp, osw_cmd)

        time_now = time.time()
        self.process_osws()
        self.expire_talkgroups(time_now)
        self.assign_voice_receivers(time_now)

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
            self.talkgroups[tgid]['tgid'] = tgid
            self.talkgroups[tgid]['srcaddr'] = 0
            self.talkgroups[tgid]['receiver'] = None
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

        if (tgid is not None) and (tgid in self.talkgroups) and (self.talkgroups[tgid]['receiver'] is None):
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
            if (tgt_tgid is None) and (self.talkgroups[active_tgid]['receiver'] is None):
                tgt_tgid = active_tgid
            #elif self.talkgroups[active_tgid]['prio'] < self.talkgroups[tgt_tgid]['prio']:
            #    tgt_tgid = active_tgid
                   
        if tgt_tgid is not None and self.talkgroups[tgt_tgid]['time'] >= start_time:
            return self.talkgroups[tgt_tgid]['frequency'], tgt_tgid, self.talkgroups[tgt_tgid]['srcaddr']
        return None, None, None

    def expire_talkgroups(self, curr_time):
        if curr_time < self.last_expiry_check + EXPIRY_TIMER:
            return

        self.last_expiry_check = curr_time
        for tgid in self.talkgroups:
            if (self.talkgroups[tgid]['receiver'] is not None) and (curr_time >= self.talkgroups[tgid]['time'] + TGID_EXPIRY_TIME):
                if self.debug > 1:
                    sys.stderr.write("%s [%d] Expiring tg(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, tgid, self.talkgroups[tgid]['frequency']))
                self.talkgroups[tgid]['receiver'].release_voice()

    def assign_voice_receivers(self, curr_time):
        done_assigning = False
        while not done_assigning:
            freq, tgid, src = self.find_talkgroup(curr_time)
            if tgid is None:    # No tgid needs assigning
                done_assigning = True
                break

            rx_sys = self.request_rx()
            if rx_sys is None:  # No receiver available
                if self.debug > 1:
                    sys.stderr.write("%s [%d] no voice receiver available for tg(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, tgid, freq))
                done_assigning = True
                break

            if self.debug > 1:
                sys.stderr.write("%s [%d] voice update:  tg(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, tgid, freq))
            rx_sys.tune_voice(freq, self.talkgroups[tgid])

#################
class voice_receiver(object):
    def __init__(self, debug, msgq_id, frequency_set, slot_set):
        self.debug = debug
        self.msgq_id = msgq_id
        self.frequency_set = frequency_set
        self.slot_set = slot_set
        self.current_talkgroup = None
        self.tuned_frequency = 0
        self.vc_retries = 0

    def post_init(self):
        if self.debug >= 1:
            sys.stderr.write("%s [%d] Initializing voice channel\n" % (log_ts.get(), self.msgq_id))
        self.slot_set({'tuner': self.msgq_id,'slot': 4})     # disable voice

    def process_qmsg(self, msg):
        m_type = ctypes.c_int16(msg.type() & 0xffff).value
        m_rxid = int(msg.arg1()) >> 1
        m_ts = float(msg.arg2())

        if (m_type == -1):  # Voice Channel Timeout
            if self.current_talkgroup is not None and self.debug > 1:
                sys.stderr.write("%s [%d] voice timeout\n" % (log_ts.get(), self.msgq_id))
            self.vc_retries += 1
            if self.vc_retries >= VC_TIMEOUT_RETRIES:
                if self.debug > 1:
                    sys.stderr.write("%s [%d] releasing tg(%d), freq(%f) due to excess timeouts\n" % (log_ts.get(), self.msgq_id, self.current_talkgroup['tgid'], self.tuned_frequency))
                self.vc_retries = 0
                self.release_voice()

    def tune_voice(self, freq, talkgroup):
        if talkgroup is None:
            return

        tune_params = {'tuner': self.msgq_id,
                       'freq': get_frequency(freq)}
        if freq != self.tuned_frequency:
            self.frequency_set(tune_params)
            self.slot_set({'tuner': self.msgq_id,'slot': 0}) # enable voice

        self.current_talkgroup = talkgroup
        self.tuned_frequency = freq
        talkgroup['receiver'] = self

    def release_voice(self):
        self.current_talkgroup['receiver'] = None
        self.current_talkgroup = None
        self.slot_set({'tuner': self.msgq_id,'slot': 4})     # disable voice

    def available(self):
        return (self.current_talkgroup is None)

