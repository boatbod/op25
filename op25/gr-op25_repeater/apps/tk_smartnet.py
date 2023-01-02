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
from helper_funcs import *
from log_ts import log_ts
from collections import deque
from gnuradio import gr
import gnuradio.op25_repeater as op25_repeater

#################

OSW_QUEUE_SIZE = 3       # Some OSWs can be 3 commands long
CC_TIMEOUT_RETRIES = 3   # Number of control channel framing timeouts before hunting
VC_TIMEOUT_RETRIES = 3   # Number of voice channel framing timeouts before expiry
TGID_DEFAULT_PRIO = 3    # Default tgid priority when unassigned
TGID_HOLD_TIME = 2.0     # Number of seconds to give previously active tgid exclusive channel access
TGID_SKIP_TIME = 4.0     # Number of seconds to blacklist a previously skipped tgid
TGID_EXPIRY_TIME = 1.0   # Number of seconds to allow tgid to remain active with no updates received
EXPIRY_TIMER = 0.2       # Number of seconds between checks for tgid expiry

#################
# Helper functions

def meta_update(meta_q, tgid = None, tag = None):
    if meta_q is None:
        return
    d = {'json_type': 'meta_update'}
    d['tgid'] = tgid
    d['tag'] = tag
    msg = op25_repeater.message().make_from_string(json.dumps(d), -2, time.time(), 0)
    meta_q.insert_tail(msg)

#################
# Main trunking class
class rx_ctl(object):
    def __init__(self, debug=0, frequency_set=None, nac_set=None, slot_set=None, nbfm_ctrl=None, chans={}):
        self.frequency_set = frequency_set
        self.nac_set = nac_set
        self.slot_set = slot_set
        self.nbfm_ctrl = nbfm_ctrl
        self.debug = debug
        self.receivers = {}
        self.systems = {}
        self.chans = chans

        for chan in self.chans:
            sysname = chan['sysname']
            if sysname not in self.systems:
                self.systems[sysname] = { 'control': None, 'voice' : [] }
                self.systems[sysname]['control'] = osw_receiver(debug         = self.debug,
                                                                frequency_set = self.frequency_set,
                                                                config        = chan)

    def set_debug(self, dbglvl):
        self.debug = dbglvl
        for sysname in self.systems:
            self.systems[sysname]['control'].set_debug(dbglvl)
        for rcvr in self.receivers:
            self.receivers[rcvr]['rx_sys'].set_debug(dbglvl)

    # add_receiver is called once per radio channel defined in cfg.json
    def add_receiver(self, msgq_id, config, meta_q = None, freq = 0):
        if msgq_id in self.receivers: # should be impossible
            return

        rx_ctl = None
        rx_sys = None
        rx_name = from_dict(config, 'name', str(msgq_id))
        rx_sysname = from_dict(config, 'trunking_sysname', "undefined")

        if rx_sysname in self.systems:   # known trunking system
            rx_ctl = from_dict(self.systems[rx_sysname], 'control', None)
            cfg_dest = (from_dict(config, 'destination', "undefined")).lower()
            if cfg_dest == "smartnet":   # control channel
                if rx_ctl is not None:
                    rx_ctl.set_msgq_id(msgq_id)
                    rx_sys = rx_ctl
            elif cfg_dest[:4] == "udp:": # voice channel:
                rx_sys = voice_receiver(debug         = self.debug,
                                        msgq_id       = msgq_id,
                                        frequency_set = self.frequency_set,
                                        slot_set      = self.slot_set,
                                        nbfm_ctrl     = self.nbfm_ctrl,
                                        control       = rx_ctl,
                                        config        = config,
                                        meta_q        = meta_q,
                                        freq          = freq)
                self.systems[rx_sysname]['voice'].append(rx_sys)
        else:                            # undefined or mis-configured trunking sysname
            sys.stderr.write("Receiver '%s' configured with unknown trunking_sysname '%s'\n" % (rx_name, rx_sysname))
            return

        self.receivers[msgq_id] = {'msgq_id': msgq_id,
                                   'config' : config,
                                   'sysname': rx_sysname,
                                   'rx_sys' : rx_sys}

    # post_init is called once after all receivers have been created
    def post_init(self):
        for rx in self.receivers:
            if self.receivers[rx]['rx_sys'] is not None:
                self.receivers[rx]['rx_sys'].post_init()

    # process_qmsg is the main message dispatch handler connecting the 'radios' to python
    def process_qmsg(self, msg):
        curr_time = time.time()
        m_rxid = int(msg.arg1()) >> 1
        if (m_rxid in self.receivers and 
            self.receivers[m_rxid]['rx_sys'] is not None and
            self.receivers[m_rxid]['rx_sys'].process_qmsg(msg, curr_time)):
            for rx in self.systems[self.receivers[m_rxid]['sysname']]['voice']: # Scan for voice activity if the arriving OSW caused a change
                rx.scan_for_talkgroups(curr_time)

    # ui_command handles all requests from user interface
    def ui_command(self, cmd, data, msgq_id):
        curr_time = time.time()
        if msgq_id in self.receivers and self.receivers[msgq_id]['rx_sys'] is not None:
            self.receivers[msgq_id]['rx_sys'].ui_command(cmd = cmd, data = data, curr_time = curr_time)    # Dispatch message to the intended receiver

    def to_json(self):
        d = {'json_type': 'trunk_update'}
        syid = 0;
        for system in self.systems:
            d[syid] = json.loads(self.systems[system]['control'].to_json())
            syid += 1
        d['nac'] = 0
        return json.dumps(d)

    def dump_tgids(self):
        for system in self.systems:
            self.systems[system]['control'].dump_tgids()

    def get_chan_status(self):
        d = {'json_type': 'channel_update'}
        rcvr_ids = []
        for rcvr in self.receivers:
            if self.receivers[rcvr]['rx_sys'] is not None:
                rcvr_name = from_dict(self.receivers[rcvr]['config'], 'name', "")
                d[str(rcvr)] = json.loads(self.receivers[rcvr]['rx_sys'].get_status())
                d[str(rcvr)]['name'] = rcvr_name
                rcvr_ids.append(str(rcvr))
        d['channels'] = rcvr_ids
        return json.dumps(d)


#################
# Smartnet control channel class
class osw_receiver(object):
    def __init__(self, debug, frequency_set, config):
        self.debug = debug
        self.msgq_id = -1
        self.config = config
        self.frequency_set = frequency_set
        self.osw_q = deque(maxlen=OSW_QUEUE_SIZE)
        self.voice_frequencies = {}
        self.talkgroups = {}
        self.skiplist = {}
        self.blacklist = {}
        self.whitelist = None
        self.cc_list = []
        self.cc_index = -1
        self.cc_retries = 0
        self.last_expiry_check = 0.0
        self.last_osw = 0.0
        self.rx_cc_freq = None
        self.rx_sys_id = None
        self.stats = {}
        self.stats['osw_count'] = 0
        self.sysname = config['sysname']

    def set_debug(self, dbglvl):
        self.debug = dbglvl

    def get_frequencies(self):
        return self.voice_frequencies

    def get_talkgroups(self):
        return self.talkgroups

    def get_blacklist(self):
        return self.blacklist

    def get_whitelist(self):
        return self.whitelist

    def get_skiplist(self):
        return self.skiplist

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

        if 'tgid_tags_file' in self.config and self.config['tgid_tags_file'] != "":
            sys.stderr.write("%s [%d] reading system tgid_tags_file: %s\n" % (log_ts.get(), self.msgq_id, self.config['tgid_tags_file']))
            self.read_tags_file(self.config['tgid_tags_file'])

        if 'blacklist' in self.config and self.config['blacklist'] != "":
            sys.stderr.write("%s [%d] reading system blacklist file: %s\n" % (log_ts.get(), self.msgq_id, self.config['blacklist']))
            self.blacklist = get_int_dict(self.config['blacklist'], self.msgq_id)

        if 'whitelist' in self.config and self.config['whitelist'] != "":
            sys.stderr.write("%s [%d] reading system whitelist file: %s\n" % (log_ts.get(), self.msgq_id, self.config['whitelist']))
            self.whitelist = get_int_dict(self.config['whitelist'], self.msgq_id)

        cc_list = from_dict(self.config, 'control_channel_list', "")
        if cc_list == "":
            sys.stderr.write("Aborting. Smartnet Trunking 'control_channel_list' parameter is empty or not found\n")
            sys.exit(1)

        for f in cc_list.split(','):
            self.cc_list.append(get_frequency(f))

        self.tune_next_cc()

    def read_tags_file(self, tags_file):
        import csv
        try:
            with open(tags_file, 'r') as csvfile:
                sreader = csv.reader(decomment(csvfile), delimiter='\t', quotechar='"', quoting=csv.QUOTE_ALL)
                for row in sreader:
                    if len(row) < 2:
                        continue
                    try:
                        if ord(row[0][0]) == 0xfeff:
                            row[0] = row[0][1:] # remove UTF8_BOM (Python2 version)
                        if ord(row[0][0]) == 0xef and ord(row[0][1]) == 0xbb and ord(row[0][2]) == 0xbf:
                            row[0] = row[0][3:] # remove UTF8_BOM (Python3 version)
                        tgid = int(row[0])
                        tag = utf_ascii(row[1])
                    except (IndexError, ValueError) as ex:
                        continue
                    if len(row) >= 3:
                        try:
                            prio = int(row[2])
                        except ValueError as ex:
                            prio = TGID_DEFAULT_PRIO
                    else:
                        prio = TGID_DEFAULT_PRIO

                    if tgid not in self.talkgroups:
                        self.add_default_tgid(tgid)
                    self.talkgroups[tgid]['tag'] = tag
                    self.talkgroups[tgid]['prio'] = prio
                    sys.stderr.write("%s [%d] setting tgid(%d), prio(%d), tag(%s)\n" % (log_ts.get(), self.msgq_id, tgid, prio, tag))
        except IOError as ex:
            sys.stderr.write("%s [%d] Error: %s: %s\n" % (log_ts.get(), self.msgq_id, ex.strerror, tags_file))

    def tune_next_cc(self):
        self.cc_retries = 0
        self.cc_index += 1
        if self.cc_index >= len(self.cc_list):
            self.cc_index = 0
        tune_params = {'tuner': self.msgq_id,
                       'freq': self.cc_list[self.cc_index]}
        self.frequency_set(tune_params)

    def ui_command(self, cmd, data, curr_time):
        pass

    def process_qmsg(self, msg, curr_time):
        m_proto = ctypes.c_int16(msg.type() >> 16).value  # upper 16 bits of msg.type() is signed protocol
        if m_proto != 2: # Smartnet m_proto=2
            return False

        m_type = ctypes.c_int16(msg.type() & 0xffff).value
        m_rxid = int(msg.arg1()) >> 1
        m_ts = float(msg.arg2())

        if (m_type == -1):  # Control Channel Timeout
            if self.debug > 10:
                sys.stderr.write("%s [%d] control channel timeout\n" % (log_ts.get(), self.msgq_id))
            self.cc_retries += 1
            if self.cc_retries >= CC_TIMEOUT_RETRIES:
                self.tune_next_cc()

        elif (m_type == 0): # OSW Received
            s = msg.to_string()
            osw_addr = get_ordinals(s[0:2])
            osw_grp  = get_ordinals(s[2:3])
            osw_cmd  = get_ordinals(s[3:5])
            self.enqueue(osw_addr, osw_grp, osw_cmd, m_ts)
            self.stats['osw_count'] += 1
            self.last_osw = m_ts
            self.cc_retries = 0

        rc = False
        rc |= self.process_osws()
        rc |= self.expire_talkgroups(curr_time)
        return rc

    def is_chan(self, cmd): # Is the 'cmd' a valid frequency or an actual command
        bandplan = from_dict(self.config, 'bandplan', "800_reband")
        band = bandplan[:3]
        subtype = bandplan[3:len(bandplan)].lower().lstrip("_-:")
        if band == "800":
            if subtype == "reband" and cmd > 0x22f:
                return False
            if (cmd >= 0 and cmd <= 0x2F7) or (cmd >= 0x32f and cmd <= 0x33F) or (cmd >= 0x3c1 and cmd <= 0x3FE) or cmd == 0x3BE:
                return True
        elif band == "900":
            if cmd >= 0 and cmd <= 0x1DE:
                return True
        elif band == "400":
            bp_base_offset = int(from_dict(self.config, 'bp_base_offset', 380))
            if (cmd >= bp_base_offset) and cmd <= (bp_base_offset + 380):
                return True
            else:
                return False
        return False

    def get_freq(self, cmd): # Convert 'cmd' into band-dependent frequency
        freq = 0.0
        bandplan = from_dict(self.config, 'bandplan', "800_reband")
        band = bandplan[:3]
        subtype = bandplan[3:len(bandplan)].lower().lstrip("_-:")

        if band == "800":
            if cmd <= 0x2CF:
                if subtype == "reband":                                   # REBAND
                    if cmd < 0x1b8:
                        freq = 851.0125 + (0.025 * cmd)
                    if cmd >= 0x1B8 and cmd <= 0x22F:
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
            bp_spacing     = float(from_dict(self.config, 'bp_spacing',     "0.025"))
            bp_base_offset = int(from_dict(self.config,   'bp_base_offset', 380))
            bp_mid_offset  = int(from_dict(self.config,   'bp_mid_offset',  760))
            bp_high_offset = int(from_dict(self.config,   'bp_high_offset', 760))
            bp_base        = float(from_dict(self.config, 'bp_base',        "0.0"))
            bp_mid         = float(from_dict(self.config, 'bp_mid',         "0.0"))
            bp_high        = float(from_dict(self.config, 'bp_high',        "0.0"))

            if (cmd >= bp_base_offset) and (cmd < bp_mid_offset):
                freq = bp_base + (bp_spacing * (cmd - bp_base_offset ))
            elif (cmd >= bp_mid_offset) and (cmd < bp_high_offset):
                freq = bp_mid + (bp_spacing * (cmd - bp_mid_offset))
            elif (cmd >= bp_high_offset) and (cmd < 760):
                freq = bp_high + (bp_spacing * (cmd - bp_high_offset))
            else:
                if self.debug >= 5:
                    sys.stderr.write("%s [%d] SMARTNET OSW freq cmd: %d out of range\n" % (log_ts.get(), self.msgq_id, cmd))
        return round(freq, 5)   # round to 5 decimal places to eliminate accumulated floating point errors

    def enqueue(self, addr, grp, cmd, ts):
        grp_str = "G" if (grp != 0) else "I"
        if self.is_chan(cmd):
            freq = self.get_freq(cmd)
            if self.debug >= 9:
                sys.stderr.write("%s [%d] SMARTNET OSW (0x%04x,%s,0x%03x,%f)\n" % (log_ts.get(), self.msgq_id, addr, grp_str, cmd, freq))
        else:
            freq = 0.0
            if self.debug >= 9:
                sys.stderr.write("%s [%d] SMARTNET OSW (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, addr, grp_str, cmd))
        self.osw_q.append((addr, (grp != 0), cmd, self.is_chan(cmd), freq, ts))

    def process_osws(self):
        if len(self.osw_q) < OSW_QUEUE_SIZE:
            return False

        rc = False
        osw2_addr, osw2_grp, osw2_cmd, osw2_ch, osw2_f, osw2_t = self.osw_q.popleft()
        if (osw2_cmd == 0x308) or (osw2_cmd == 0x309):
            osw1_addr, osw1_grp, osw1_cmd, osw1_ch, osw1_f, osw1_t = self.osw_q.popleft()
            if osw1_ch and osw1_grp and (osw1_addr != 0) and (osw2_addr != 0):   # Two-OSW analog group voice grant
                src_rid = osw2_addr
                dst_tgid = osw1_addr
                tgt_freq = osw1_f
                rc |= self.update_voice_frequency(tgt_freq, dst_tgid, src_rid, mode=0, ts=osw1_t)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET GROUP GRANT src(%d), tgid(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, tgt_freq))
            elif osw1_ch and not osw1_grp and ((osw1_addr & 0xff00) == 0x1f00):  # SysId + Control Channel Frequency broadcast
                self.rx_sys_id = osw2_addr
                self.rx_cc_freq = osw1_f * 1e6
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET SYSID (%x) CONTROL CHANNEL (%f)\n" % (log_ts.get(), self.msgq_id, osw2_addr, osw1_f))
            elif osw1_cmd == 0x30b:
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch, osw0_f, osw0_t = self.osw_q.popleft()
                if osw0_ch and ((osw0_addr & 0xff00) == 0x1F00) and ((osw1_addr & 0xfc00) == 0x2800) and ((osw1_addr & 0x3ff) == osw0_cmd):
                    self.rx_sys_id = osw2_addr
                    self.rx_cc_freq = osw0_f * 1e6
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET SYSID (%x) CONTROL CHANNEL (%f)\n" % (log_ts.get(), self.msgq_id, osw2_addr, osw1_f))
                else:
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch, osw0_f, osw0_t)) # put back unused OSW0
                    if ((osw1_addr & 0xfc00) == 0x2800):
                        self.rx_sys_id = osw2_addr
                        self.rx_cc_freq = self.get_freq(osw1_addr & 0x3ff) * 1e6
                        if self.debug >= 11:
                            sys.stderr.write("%s [%d] SMARTNET SYSID (%x) CONTROL CHANNEL (%f)\n" % (log_ts.get(), self.msgq_id, osw2_addr, osw1_f))
            elif osw1_cmd == 0x310:                                              # Two-OSW Type II affiliation
                src_rid = osw2_addr
                dst_tgid = osw1_addr & 0xfff0
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET AFFILIATION src(%d), tgid(%d)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid))
            elif osw1_cmd == 0x320:
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch, osw0_f, osw0_t = self.osw_q.popleft()
                if osw0_cmd == 0x30b:
                    # There is information that can be extracted from these OSWs but it may apply to a neighbor not ourself
                    # proceed with caution!
                    if (osw0_addr & 0xfc00) == 0x6000:
                        sysid = osw2_addr
                        cellid = (osw1_addr >> 10) & 0x3f
                        band = (osw1_addr >> 7) & 0x7
                        feat = osw1_addr & 0x3f
                        freq = osw0_f
                        if self.debug >= 11:
                            sys.stderr.write("%s [%d] SMARTNET SYSID (%x) CELLID (%x) BAND (%d) FEATURES (%x) CONTROL CHANNEL (%f)\n" % (log_ts.get(), self.msgq_id, sysid, cellid, band, feat, freq))
                else:
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch, osw0_f, osw0_t)) # put back unused OSW0
            else: # OSW1 did not match, so put it back in the queue 
                self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch, osw1_f, osw1_t))
        elif osw2_cmd == 0x321:                                                  # Two-OSW digital group voice grant
            osw1_addr, osw1_grp, osw1_cmd, osw1_ch, osw1_f, osw1_t = self.osw_q.popleft()
            if osw1_ch and osw1_grp and (osw1_addr != 0):
                src_rid = osw2_addr
                dst_tgid = osw1_addr
                tgt_freq = osw1_f
                rc |= self.update_voice_frequency(tgt_freq, dst_tgid, src_rid, mode=1, ts=osw1_t)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET ASTRO GRANT src(%d), tgid(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, tgt_freq))
            else: # OSW did not match, so put it back in the queue 
                self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch, osw1_f, osw1_t))
        elif osw2_ch and osw2_grp:                                               # Single-OSW voice update
            dst_tgid = osw2_addr
            tgt_freq = osw2_f
            rc |= self.update_voice_frequency(tgt_freq, dst_tgid, ts=osw2_t)
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET GROUP UPDATE tgid(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, dst_tgid, tgt_freq))
        elif osw2_ch and not osw2_grp and ((osw2_addr & 0xff00) == 0x1f00):      # Control Channel Frequency broadcast
            self.rx_cc_freq = osw2_f * 1e6
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET CONTROL CHANNEL freq (%f)\n" % (log_ts.get(), self.msgq_id, osw2_f))
        return rc

    def update_voice_frequency(self, float_freq, tgid=None, srcaddr=-1, mode=-1, ts=time.time()):
        if not float_freq:    # e.g., channel identifier not yet known
            return False

        frequency = int(float_freq * 1e6) # use integer not float as dictionary keys

        rc = self.update_talkgroups(frequency, tgid, srcaddr, mode, ts)

        base_tgid = tgid & 0xfff0
        tgid_stat = tgid & 0x000f
        if frequency not in self.voice_frequencies:
            self.voice_frequencies[frequency] = {'counter':0}
            sorted_freqs = collections.OrderedDict(sorted(self.voice_frequencies.items()))
            self.voice_frequencies = sorted_freqs
            if self.debug >= 5:
                sys.stderr.write('%s [%d] new freq=%f\n' % (log_ts.get(), self.msgq_id, (frequency/1e6)))

        if 'tgid' not in self.voice_frequencies[frequency]:
            self.voice_frequencies[frequency]['tgid'] = [None]
        self.voice_frequencies[frequency]['tgid'] = base_tgid
        self.voice_frequencies[frequency]['counter'] += 1
        self.voice_frequencies[frequency]['time'] = time.time()
        return rc

    def update_talkgroups(self, frequency, tgid, srcaddr, mode=-1, ts=time.time()):
        rc = self.update_talkgroup(frequency, tgid, srcaddr, mode, ts)
        #if tgid in self.patches:
        #    for ptgid in self.patches[tgid]['ga']:
        #        rc |= self.update_talkgroup(frequency, ptgid, srcaddr)
        #        if self.debug >= 5:
        #            sys.stderr.write('%s update_talkgroups: sg(%d) patched tgid(%d)\n' % (log_ts.get(), tgid, ptgid))
        return rc

    def update_talkgroup(self, frequency, tgid, srcaddr, mode=-1, ts=time.time()):
        base_tgid = tgid & 0xfff0
        tgid_stat = tgid & 0x000f

        if self.debug >= 5:
            sys.stderr.write('%s [%d] set tgid=%s, status=0x%x, srcaddr=%s\n' % (log_ts.get(), self.msgq_id, base_tgid, tgid_stat, srcaddr))
        
        if base_tgid not in self.talkgroups:
            self.add_default_tgid(base_tgid)
            if self.debug >= 5:
                sys.stderr.write('%s [%d] new tgid=%s %s prio %d\n' % (log_ts.get(), self.msgq_id, base_tgid, self.talkgroups[base_tgid]['tag'], self.talkgroups[base_tgid]['prio']))
        elif ts < self.talkgroups[base_tgid]['release_time']: # screen out late arriving OSWs where subsequent action has already been taken
            if self.debug >= 5:
                sys.stderr.write('%s [%d] ignorning stale OSW for tgid=%s, time_diff=%f\n' % (log_ts.get(), self.msgq_id, base_tgid, (ts - self.talkgroups[base_tgid]['release_time'])))
            return False
        self.talkgroups[base_tgid]['time'] = time.time()
        self.talkgroups[base_tgid]['release_time'] = 0
        self.talkgroups[base_tgid]['frequency'] = frequency
        self.talkgroups[base_tgid]['status'] = tgid_stat
        if srcaddr >= 0:
            self.talkgroups[base_tgid]['srcaddr'] = srcaddr
        if mode >= 0:
            self.talkgroups[base_tgid]['mode'] = mode
        return True

    def add_default_tgid(self, tgid):
        if tgid not in self.talkgroups:
            self.talkgroups[tgid] = {'counter':0}
            self.talkgroups[tgid]['tgid'] = tgid
            self.talkgroups[tgid]['prio'] = TGID_DEFAULT_PRIO
            self.talkgroups[tgid]['tag'] = ""
            self.talkgroups[tgid]['srcaddr'] = 0
            self.talkgroups[tgid]['time'] = 0
            self.talkgroups[tgid]['release_time'] = 0
            self.talkgroups[tgid]['mode'] = -1
            self.talkgroups[tgid]['receiver'] = None
            self.talkgroups[tgid]['status'] = 0

    def expire_talkgroups(self, curr_time):
        if curr_time < self.last_expiry_check + EXPIRY_TIMER:
            return False

        rc = False
        self.last_expiry_check = curr_time
        for tgid in self.talkgroups:
            if (self.talkgroups[tgid]['receiver'] is not None) and (curr_time >= self.talkgroups[tgid]['time'] + TGID_EXPIRY_TIME):
                if self.debug > 1:
                    sys.stderr.write("%s [%d] expiring tg(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, tgid, (self.talkgroups[tgid]['frequency']/1e6)))
                self.talkgroups[tgid]['receiver'].expire_talkgroup(reason="expiry")
                rc = True
        return rc

    def dump_tgids(self):
        sys.stderr.write("Known tgids: { ")
        for tgid in sorted(self.talkgroups.keys()):
            sys.stderr.write("%d " % tgid);
        sys.stderr.write("}\n") 

    def to_json(self):  # ugly but required for compatibility with P25 trunking and terminal modules
        d = {}
        d['system']         = self.sysname
        d['top_line']       = 'Smartnet/Smartzone SysId %04x' % (self.rx_sys_id if self.rx_sys_id is not None else 0)
        d['top_line']      += ' Control Ch %f' % ((self.rx_cc_freq if self.rx_cc_freq is not None else self.cc_list[self.cc_index]) / 1e6)
        d['top_line']      += ' OSW count %d' % (self.stats['osw_count'])
        d['secondary']      = ""
        d['frequencies']    = {}
        d['frequency_data'] = {}
        d['last_tsbk'] = self.last_osw
        t = time.time()
        for f in list(self.voice_frequencies.keys()):
            d['frequencies'][f] = 'voice frequency %f tgid %5d %4.1fs ago count %d' %  ((f/1e6), self.voice_frequencies[f]['tgid'], t - self.voice_frequencies[f]['time'], self.voice_frequencies[f]['counter'])

            d['frequency_data'][f] = {'tgids': [self.voice_frequencies[f]['tgid']], 'last_activity': '%7.1f' % (t - self.voice_frequencies[f]['time']), 'counter': self.voice_frequencies[f]['counter']}
        d['adjacent_data'] = ""
        return json.dumps(d)

    def get_status(self):
        d = {}
        d['freq'] = self.cc_list[self.cc_index]
        d['tgid'] = None
        d['system'] = self.config['sysname']
        d['tag'] = None
        d['srcaddr'] = 0
        d['mode'] = None
        d['stream'] = ""
        d['msgqid'] = self.msgq_id
        return json.dumps(d)

#################
# Voice channel class
class voice_receiver(object):
    def __init__(self, debug, msgq_id, frequency_set, slot_set, nbfm_ctrl, control, config, meta_q = None, freq = 0):
        self.debug = debug
        self.msgq_id = msgq_id
        self.frequency_set = frequency_set
        self.slot_set = slot_set
        self.nbfm_ctrl = nbfm_ctrl
        self.control = control
        self.config = config
        self.meta_q = meta_q
        self.talkgroups = None
        self.tuned_frequency = freq
        self.current_tgid = None
        self.hold_tgid = None
        self.hold_until = 0.0
        self.hold_mode = False
        self.tgid_hold_time = TGID_HOLD_TIME
        self.blacklist = {}
        self.skiplist = {}
        self.whitelist = None
        self.vc_retries = 0

    def set_debug(self, dbglvl):
        self.debug = dbglvl

    def post_init(self):
        if self.debug >= 1:
            sys.stderr.write("%s [%d] Initializing voice channel\n" % (log_ts.get(), self.msgq_id))
        self.slot_set({'tuner': self.msgq_id,'slot': 4})     # disable voice
        if self.control is not None:
            self.talkgroups = self.control.get_talkgroups()
        self.load_bl_wl()
        self.tgid_hold_time = float(from_dict(self.control.config, 'tgid_hold_time', TGID_HOLD_TIME))
        meta_update(self.meta_q)

    def load_bl_wl(self):
        self.skiplist = self.control.get_skiplist()
        if 'blacklist' in self.config and self.config['blacklist'] != "":
            sys.stderr.write("%s [%d] reading channel blacklist file: %s\n" % (log_ts.get(), self.msgq_id, self.config['blacklist']))
            self.blacklist = get_int_dict(self.config['blacklist'], self.msgq_id)
        else:
            self.blacklist = self.control.get_blacklist()

        if 'whitelist' in self.config and self.config['whitelist'] != "":
            sys.stderr.write("%s [%d] reading channel whitelist file: %s\n" % (log_ts.get(), self.msgq_id, self.config['whitelist']))
            self.whitelist = get_int_dict(self.config['whitelist'], self.msgq_id)
        else:
            self.whitelist = self.control.get_whitelist()

    def ui_command(self, cmd, data, curr_time):
        if cmd == 'hold':
            self.hold_talkgroup(data, curr_time)
        elif cmd == 'whitelist':
            self.add_whitelist(data)
        elif cmd == 'skip':
            if self.current_tgid is not None:
                self.add_skiplist(self.current_tgid, curr_time + TGID_SKIP_TIME)
        elif cmd == 'lockout':
            if (data == 0) and self.current_tgid is not None:
                self.add_blacklist(self.current_tgid)
            elif data > 0:
                self.add_blacklist(data)
        elif cmd == 'reload':
            self.blacklist = {}
            self.whitelist = None
            self.load_bl_wl()
 
    def process_qmsg(self, msg, curr_time):
        rc = False
        m_type = ctypes.c_int16(msg.type() & 0xffff).value
        m_rxid = int(msg.arg1()) >> 1
        m_ts = float(msg.arg2())

        if (m_type == -1):   # Voice Channel Timeout
            pass
        elif (m_type == -4): # P25 sync established (indicates this is a digital channel)
            if self.current_tgid is not None:
                if self.debug >= 9:
                    sys.stderr.write("%s [%d] digital sync detected:  tg(%d), freq(%f), mode(%d)\n" % (log_ts.get(), self.msgq_id, self.current_tgid, (self.tuned_frequency/1e6), self.talkgroups[self.current_tgid]['mode']))
                self.nbfm_ctrl(self.msgq_id, False)              # disable nbfm
                self.talkgroups[self.current_tgid]['mode'] = 1   # set mode to digital
        elif (m_type == 3):  # DUID-3  (call termination without channel release)
            pass 
        elif (m_type == 15): # DUID-15 (call termination with channel release)
            self.expire_talkgroup(reason="duid15")
            rc = True
        return rc

    def add_skiplist(self, tgid, end_time=None):
        if not tgid or (tgid <= 0) or (tgid > 65534):
            if self.debug > 1:
                sys.stderr.write("%s [%d] skiplist tgid(%d) out of range (1-65534)\n" % (log_ts.get(), self.msgq_id, tgid))
            return
        if tgid in self.skiplist:
            return
        self.skiplist[tgid] = end_time
        if self.debug > 1:
            sys.stderr.write("%s [%d] skiplisting: tgid(%d)\n" % (log_ts.get(), self.msgq_id, tgid))
        if self.current_tgid and self.current_tgid in self.skiplist:
            self.expire_talkgroup(reason = "skiplisted")
            self.hold_mode = False
            self.hold_tgid = None
            self.hold_until = time.time()

    def add_blacklist(self, tgid, end_time=None):
        if not tgid or (tgid <= 0) or (tgid > 65534):
            if self.debug > 0:
                sys.stderr.write("%s [%d] blacklist tgid(%d) out of range (1-65534)\n" % (log_ts.get(), self.msgq_id, tgid))
            return
        if tgid in self.blacklist:
            return
        if end_time is None and self.whitelist and tgid in self.whitelist:
            self.whitelist.pop(tgid)
            if self.debug > 1:
                sys.stderr.write("%s [%d] de-whitelisting: tgid(%d)\n" % (log_ts.get(), self.msgq_id, tgid))
            if len(self.whitelist) == 0:
                self.whitelist = None
                if self.debug > 1:
                    sys.stderr.write("%s removing empty whitelist\n" % log_ts.get())
        self.blacklist[tgid] = end_time
        if self.debug > 1:
            sys.stderr.write("%s [%d] blacklisting tgid(%d)\n" % (log_ts.get(), self.msgq_id, tgid))
        if self.current_tgid and self.current_tgid in self.blacklist:
            self.expire_talkgroup(reason = "blacklisted")
            self.hold_mode = False
            self.hold_tgid = None
            self.hold_until = time.time()

    def add_whitelist(self, tgid):
        if not tgid or (tgid <= 0) or (tgid > 65534):
            if self.debug > 0:
                sys.stderr.write("%s [%d] whitelist tgid(%d) out of range (1-65534)\n" % (log_ts.get(), self.msgq_id, tgid))
            return
        if self.blacklist and tgid in self.blacklist:
            self.blacklist.pop(tgid)
            if self.debug > 1:
                sys.stderr.write("%s [%d] de-blacklisting tgid(%d)\n" % (log_ts.get(), self.msgq_id, tgid))
        if self.whitelist is None:
            self.whitelist = {}
        if tgid in self.whitelist:
            return
        self.whitelist[tgid] = None
        if self.debug > 1:
            sys.stderr.write("%s [%d] whitelisting tgid(%d)\n" % (log_ts.get(), self.msgq_id, tgid))
        if self.current_tgid and self.current_tgid not in self.whitelist:
            self.expire_talkgroup(reason = "not whitelisted")
            self.hold_mode = False
            self.hold_tgid = None
            self.hold_until = time.time()

    def blacklist_update(self, start_time):
        expired_tgs = [tg for tg in list(self.blacklist.keys())
                            if self.blacklist[tg] is not None
                            and self.blacklist[tg] < start_time]
        for tg in expired_tgs:
            self.blacklist.pop(tg)

    def skiplist_update(self, start_time):
        expired_tgs = [tg for tg in list(self.skiplist.keys())
                            if self.skiplist[tg] is not None
                            and self.skiplist[tg] < start_time]
        for tg in expired_tgs:
            self.skiplist.pop(tg)
            if self.debug > 1:
                sys.stderr.write("%s [%d] removing expired skiplist: tg(%d)\n" % (log_ts.get(), self.msgq_id, tg));

    def find_talkgroup(self, start_time, tgid=None, hold=False):
        tgt_tgid = None
        self.blacklist_update(start_time)

        # tgid status >=8 indicates encryption
        if (tgid is not None) and (tgid in self.talkgroups) and (self.talkgroups[tgid]['status'] < 8) and ((self.talkgroups[tgid]['receiver'] is None) or (self.talkgroups[tgid]['receiver'] == self)):
            tgt_tgid = tgid

        for active_tgid in self.talkgroups:
            if hold:
                break
            if self.talkgroups[active_tgid]['time'] < start_time:
                continue
            if active_tgid in self.skiplist:
                continue
            if active_tgid in self.blacklist and (not self.whitelist or active_tgid not in self.whitelist):
                continue
            if self.whitelist and active_tgid not in self.whitelist:
                continue
            if tgt_tgid is None:
                if (self.talkgroups[active_tgid]['status'] < 8) and (self.talkgroups[active_tgid]['receiver'] is None):
                    tgt_tgid = active_tgid
                    continue
            elif (self.talkgroups[active_tgid]['prio'] < self.talkgroups[tgt_tgid]['prio']) and (self.talkgroups[active_tgid]['status'] < 8) and (self.talkgroups[active_tgid]['receiver'] is None):
                tgt_tgid = active_tgid
                   
        if tgt_tgid is not None and self.talkgroups[tgt_tgid]['time'] >= start_time:
            return self.talkgroups[tgt_tgid]['frequency'], tgt_tgid, self.talkgroups[tgt_tgid]['srcaddr']
        return None, None, None

    def scan_for_talkgroups(self, curr_time):
        if self.current_tgid is None and self.hold_tgid is not None and (curr_time < self.hold_until):
            freq, tgid, src = self.find_talkgroup(curr_time, tgid=self.hold_tgid)
        else:
            freq, tgid, src = self.find_talkgroup(curr_time, tgid=self.current_tgid)
        if tgid is None or tgid == self.current_tgid:
            return

        if self.current_tgid is None:
            if self.debug > 0:
                sys.stderr.write("%s [%d] voice update:  tg(%d), freq(%f), mode(%d)\n" % (log_ts.get(), self.msgq_id, tgid, (freq/1e6), self.talkgroups[tgid]['mode']))
            self.tune_voice(freq, tgid)
        else:
            if self.debug > 0:
                sys.stderr.write("%s [%d] voice preempt: tg(%d), freq(%f), mode(%d)\n" % (log_ts.get(), self.msgq_id, tgid, (freq/1e6), self.talkgroups[tgid]['mode']))
            self.expire_talkgroup(update_meta=False, reason="preempt")
            self.tune_voice(freq, tgid)

        meta_update(self.meta_q, tgid, self.talkgroups[tgid]['tag'])

    def hold_talkgroup(self, tgid, curr_time):
        if tgid > 0:
            if self.whitelist is not None and tgid not in self.whitelist:
                if self.debug > 1:
                    sys.stderr.write("%s [%d] hold tg(%d) not in whitelist\n" % (log_ts.get(), self.msgq_id, tgid))
                return
            self.control.add_default_tgid(tgid)
            self.hold_tgid = tgid
            self.hold_until = curr_time + 86400 * 10000
            self.hold_mode = True
            if self.debug > 0:
                sys.stderr.write ('%s [%d] set hold tg(%d) until %f\n' % (log_ts.get(), self.msgq_id, self.hold_tgid, self.hold_until))
            if self.current_tgid != self.hold_tgid:
                self.expire_talkgroup(reason="new hold", auto_hold = False)
                self.current_tgid = self.hold_tgid
        elif self.hold_mode is False:
            if self.current_tgid:
                self.hold_tgid = self.current_tgid
                self.hold_until = curr_time + 86400 * 10000
                self.hold_mode = True
                if self.debug > 0:
                    sys.stderr.write ('%s [%d] set hold tg(%d) until %f\n' % (log_ts.get(), self.msgq_id, self.hold_tgid, self.hold_until))
        elif self.hold_mode is True:
            if self.debug > 0:
                sys.stderr.write ('%s [%d] clear hold tg(%d)\n' % (log_ts.get(), self.msgq_id, self.hold_tgid))
            self.hold_tgid = None
            self.hold_until = curr_time
            self.hold_mode = False
            self.expire_talkgroup(reason="clear hold", auto_hold = False)

    def tune_voice(self, freq, tgid):
        if freq != self.tuned_frequency:
            tune_params = {'tuner': self.msgq_id,
                           'freq': get_frequency(freq),
                           'tgid': tgid,
                           'tag': self.talkgroups[tgid]['tag'],
                           'system': self.config['trunking_sysname']}
            self.frequency_set(tune_params)
            self.tuned_frequency = freq
        self.current_tgid = tgid
        self.talkgroups[tgid]['receiver'] = self
        self.slot_set({'tuner': self.msgq_id,'slot': 0})                      # always enable digital p25cai
        self.nbfm_ctrl(self.msgq_id, (self.talkgroups[tgid]['mode'] != 1) )   # enable nbfm unless mode is digital

    def expire_talkgroup(self, tgid=None, update_meta = True, reason="unk", auto_hold = True):
        expire_time = time.time()
        self.nbfm_ctrl(self.msgq_id, False)                                   # disable nbfm
        self.slot_set({'tuner': self.msgq_id,'slot': 4})                      # disable p25cai
        if self.current_tgid is None:
            return
            
        self.talkgroups[self.current_tgid]['receiver'] = None
        self.talkgroups[self.current_tgid]['srcaddr'] = 0
        self.talkgroups[self.current_tgid]['release_time'] = expire_time
        if self.debug > 1:
            sys.stderr.write("%s [%d] releasing:  tg(%d), freq(%f), reason(%s)\n" % (log_ts.get(), self.msgq_id, self.current_tgid, (self.tuned_frequency/1e6), reason))
        if auto_hold:
            self.hold_tgid = self.current_tgid
            self.hold_until = expire_time + TGID_HOLD_TIME
        self.current_tgid = None

        if update_meta:
            meta_update(self.meta_q)

    def get_status(self):
        d = {}
        d['freq'] = self.tuned_frequency
        d['tgid'] = self.current_tgid
        d['system'] = self.config['trunking_sysname']
        d['tag'] = self.talkgroups[self.current_tgid]['tag'] if self.current_tgid is not None else ""
        d['srcaddr'] = self.talkgroups[self.current_tgid]['srcaddr'] if self.current_tgid is not None else 0
        d['mode'] = self.talkgroups[self.current_tgid]['mode'] if self.current_tgid is not None else -1
        d['stream'] = self.config['meta_stream_name'] if 'meta_stream_name' in self.config else ""
        d['msgqid'] = self.msgq_id
        return json.dumps(d)
