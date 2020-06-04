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
from gnuradio import gr

#################

OSW_QUEUE_SIZE = 3       # Some OSWs can be 3 commands long
CC_TIMEOUT_RETRIES = 3   # Number of control channel framing timeouts before hunting
VC_TIMEOUT_RETRIES = 3   # Number of voice channel framing timeouts before expiry
TGID_DEFAULT_PRIO = 3    # Default tgid priority when unassigned
TGID_HOLD_TIME = 2.0     # Number of seconds to give previously active tgid exclusive channel access
TGID_EXPIRY_TIME = 1.0   # Number of seconds to allow tgid to remain active with no updates received
EXPIRY_TIMER = 0.2       # Number of seconds between checks for tgid expiry

#################
# Helper functions
def utf_ascii(ustr):
    return (ustr.decode("utf-8")).encode("ascii", "ignore")

def get_frequency( f):    # return frequency in Hz
    if str(f).find('.') == -1:    # assume in Hz
        return int(f)
    else:     # assume in MHz due to '.'
        return int(float(f) * 1000000)

def get_int_dict(s, msgq_id = 0):      # used to read blacklist/whitelist files
    d = {}
    try:
        with open(s,"r") as f:
            for v in f:
                v = v.split("\t",1)                        # split on tab
                try:
                    v0 = int(v[0])                         # first parameter is tgid or start of tgid range
                    v1 = v0
                    if (len(v) > 1) and (int(v[1]) > v0):  # second parameter if present is end of tgid range
                        v1 = int(v[1])

                    for tg in range(v0, (v1 + 1)):
                            if tg not in d:      # is this a new tg?
                                    d[tg] = []   # if so, add to dict (key only, value null)
                                    sys.stderr.write('%s [%d] added talkgroup %d from %s\n' % (log_ts.get(), msgq_id, tg,s))

                except (IndexError, ValueError) as ex:
                    continue
        f.close()
    except (IOError) as ex:
        sys.stderr.write("%s: %s\n" % (ex.strerror, s))

    return dict.fromkeys(d)

def from_dict(d, key, def_val):
    if key in d and d[key] != "":
        return d[key]
    else:
        return def_val

def meta_update(meta_q, tgid = None, tag = None):
    if meta_q is None:
        return

    if tgid is None:
        metadata = "[idle]"
    else:
        metadata = "[" + str(tgid) + "]"
    if tag is not None:
        metadata += " " + tag
    msg = gr.message().make_from_string(metadata, -2, time.time(), 0)
    meta_q.insert_tail(msg)

#################
# Main trunking class
class rx_ctl(object):
    def __init__(self, debug=0, frequency_set=None, slot_set=None, nbfm_ctrl=None, chans={}):
        self.frequency_set = frequency_set
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

    # add_receiver is called once per radio channel defined in cfg.json
    def add_receiver(self, msgq_id, config, meta_q = None):
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
                                        meta_q        = meta_q)
                self.systems[rx_sysname]['voice'].append(rx_sys)
        else:                            # undefined or mis-configured trunking sysname
            sys.stderr.write("Receiver '%s' configured with unknown trunking_sysname '%s'\n" % (rx_name, rx_sysname))

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
        if m_rxid in self.receivers and self.receivers[m_rxid]['rx_sys'] is not None:
            self.receivers[m_rxid]['rx_sys'].process_qmsg(msg, curr_time)        # First dispatch the message to the intended receiver
            for rx in self.systems[self.receivers[m_rxid]['sysname']]['voice']:  # then have all the voice receivers scan for activity
                rx.scan_for_talkgroups(curr_time)

    def to_json(self):
        d = {'json_type': 'trunk_update'}
        syid = 0;
        for system in self.systems:
            d[syid] = json.loads(self.systems[system]['control'].to_json())
            syid += 1
        d['nac'] = 0
        return json.dumps(d)

    def to_json2(self):
        d = {'json_type': 'voice_update'}
        syid = 0;
        for sysname in self.systems:
            for voice in self.systems[sysname]['voice']:
                vc_name = from_dict(voice.config, 'name', ("[%d]" % voice.msgq_id))
                d[syid] = json.loads(voice.to_json())
                d[syid]['name'] = vc_name
            syid += 1
        d['voice_count'] = syid
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

    def get_frequencies(self):
        return self.voice_frequencies

    def get_talkgroups(self):
        return self.talkgroups

    def get_blacklist(self):
        return self.blacklist

    def get_whitelist(self):
        return self.whitelist

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
        with open(tags_file, 'rb') as csvfile:
            sreader = csv.reader(csvfile, delimiter='\t', quotechar='"', quoting=csv.QUOTE_ALL)
            for row in sreader:
                try:
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
                    self.talkgroups[tgid] = {'counter':0}
                    self.talkgroups[tgid]['tgid'] = tgid
                    self.talkgroups[tgid]['srcaddr'] = 0
                    self.talkgroups[tgid]['receiver'] = None
                    self.talkgroups[tgid]['time'] = 0
                    self.talkgroups[tgid]['mode'] = -1
                self.talkgroups[tgid]['tag'] = tag
                self.talkgroups[tgid]['prio'] = prio
                sys.stderr.write("%s [%d] setting tgid(%d), prio(%d), tag(%s)\n" % (log_ts.get(), self.msgq_id, tgid, prio, tag))

    def tune_next_cc(self):
        self.cc_retries = 0
        self.cc_index += 1
        if self.cc_index >= len(self.cc_list):
            self.cc_index = 0
        tune_params = {'tuner': self.msgq_id,
                       'freq': self.cc_list[self.cc_index]}
        self.frequency_set(tune_params)

    def process_qmsg(self, msg, curr_time):
        m_proto = ctypes.c_int16(msg.type() >> 16).value  # upper 16 bits of msg.type() is signed protocol
        if m_proto != 2: # Smartnet m_proto=2
            return

        m_type = ctypes.c_int16(msg.type() & 0xffff).value
        m_rxid = int(msg.arg1()) >> 1
        m_ts = float(msg.arg2())

        if (m_type == -1):  # Control Channel Timeout
            if self.debug > 10:
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
            self.stats['osw_count'] += 1
            self.last_osw = curr_time

        self.process_osws()
        self.expire_talkgroups(curr_time)

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
            bp_offset = int(from_dict(self.config, 'bp_offset', "0"))
            if (cmd >= bp_offset) and cmd <= (bp_offset + 380):
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
            bp_offset = int(from_dict(self.config, 'bp_offset', "0"))
            bp_high = float(from_dict(self.config, 'bp_high', "0.0"))
            bp_base = float(from_dict(self.config, 'bp_base', "0.0"))
            bp_spacing = float(from_dict(self.config, 'bp_spacing', "0.025"))
            high_cmd = bp_offset + bp_high - bp_base / bp_spacing

            if (cmd >= bp_offset) and (cmd < high_cmd):
                freq = bp_base + (bp_spacing * (cmd - bp_offset ))
        return freq

    def enqueue(self, addr, grp, cmd):
        if self.is_chan(cmd):
            freq = self.get_freq(cmd)
            if self.debug >= 9:
                sys.stderr.write("%s [%d] SMARTNET OSW (0x%04x,%s,0x%03x,%f)\n" % (log_ts.get(), self.msgq_id, addr, "true", cmd, freq))
        else:
            freq = 0.0
            if self.debug >= 9:
                sys.stderr.write("%s [%d] SMARTNET OSW (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, addr, "false", cmd))
        self.osw_q.append((addr, (grp != 0), cmd, self.is_chan(cmd), freq))

    def process_osws(self):
        if len(self.osw_q) < OSW_QUEUE_SIZE:
            return

        osw2_addr, osw2_grp, osw2_cmd, osw2_ch, osw2_f = self.osw_q.popleft()

        if osw2_cmd == 0x308:
            osw1_addr, osw1_grp, osw1_cmd, osw1_ch, osw1_f = self.osw_q.popleft()
            if osw1_ch and osw1_grp and (osw1_addr != 0) and (osw2_addr != 0):   # Two-OSW analog group voice grant
                src_rid = osw2_addr
                dst_tgid = osw1_addr
                tgt_freq = osw1_f
                self.update_voice_frequency(tgt_freq, dst_tgid, src_rid, mode=0)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET GROUP GRANT src(%d), tgid(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, tgt_freq))
            elif osw1_ch and not osw1_grp and ((osw1_addr & 0xff00) == 0x1f00):  # SysId + Control Channel Frequency broadcast
                self.rx_sys_id = osw2_addr
                self.rx_cc_freq = osw1_f * 1e6
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET SYSID (%x) CONTROL CHANNEL (%f)\n" % (log_ts.get(), self.msgq_id, osw2_addr, osw1_f))
            elif osw1_cmd == 0x30b:
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch, osw0_f = self.osw_q.popleft()
                if osw0_ch and ((osw0_addr & 0xff00) == 0x1F00) and ((osw1_addr & 0xfc00) == 0x2800) and ((osw1_addr & 0x3ff) == osw0_cmd):
                    self.rx_sys_id = osw2_addr
                    self.rx_cc_freq = osw0_f * 1e6
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET SYSID (%x) CONTROL CHANNEL (%f)\n" % (log_ts.get(), self.msgq_id, osw2_addr, osw1_f))
                else:
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch, osw0_f)) # put back unused OSW0
                    if ((osw1_addr & 0xfc00) == 0x2800):
                        self.rx_sys_id = osw2_addr
                        self.rx_cc_freq = self.get_freq(osw1_addr & 0x3ff) * 1e6
                        if self.debug >= 11:
                            sys.stderr.write("%s [%d] SMARTNET SYSID (%x) CONTROL CHANNEL (%f)\n" % (log_ts.get(), self.msgq_id, osw2_addr, osw1_f))
            elif osw1_cmd == 0x320:
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch, osw0_f = self.osw_q.popleft()
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
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch, osw0_f)) # put back unused OSW0
            else: # OSW1 did not match, so put it back in the queue 
                self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch, osw1_f))
        elif osw2_cmd == 0x321:                                                  # Two-OSW digital group voice grant
            osw1_addr, osw1_grp, osw1_cmd, osw1_ch, osw1_f = self.osw_q.popleft()
            if osw1_ch and osw1_grp and (osw1_addr != 0):
                src_rid = osw2_addr
                dst_tgid = osw1_addr
                tgt_freq = osw1_f
                self.update_voice_frequency(tgt_freq, dst_tgid, src_rid, mode=1)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET ASTRO GRANT src(%d), tgid(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, tgt_freq))
            else: # OSW did not match, so put it back in the queue 
                self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch, osw1_f))
        elif osw2_ch and osw2_grp:                                               # Single-OSW voice update
            dst_tgid = osw2_addr
            tgt_freq = osw2_f
            self.update_voice_frequency(tgt_freq, dst_tgid)
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET GROUP UPDATE tgid(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, dst_tgid, tgt_freq))
        elif osw2_ch and not osw2_grp and ((osw2_addr & 0xff00) == 0x1f00):      # Control Channel Frequency broadcast
            self.rx_cc_freq = osw2_f * 1e6
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET CONTROL CHANNEL freq (%f)\n" % (log_ts.get(), self.msgq_id, osw2_f))

    def update_voice_frequency(self, float_freq, tgid=None, srcaddr=-1, mode=-1):
        if not float_freq:    # e.g., channel identifier not yet known
            return

        frequency = int(float_freq * 1e6) # use integer not float as dictionary keys

        self.update_talkgroups(frequency, tgid, srcaddr, mode)

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

    def update_talkgroups(self, frequency, tgid, srcaddr, mode=-1):
        self.update_talkgroup(frequency, tgid, srcaddr, mode)
        #if tgid in self.patches:
        #    for ptgid in self.patches[tgid]['ga']:
        #        self.update_talkgroup(frequency, ptgid, srcaddr)
        #        if self.debug >= 5:
        #            sys.stderr.write('%s update_talkgroups: sg(%d) patched tgid(%d)\n' % (log_ts.get(), tgid, ptgid))

    def update_talkgroup(self, frequency, tgid, srcaddr, mode=-1):
        base_tgid = tgid & 0xfff0
        tgid_stat = tgid & 0x000f

        if self.debug >= 5:
            sys.stderr.write('%s [%d] set tgid=%s, status=0x%x, srcaddr=%s\n' % (log_ts.get(), self.msgq_id, base_tgid, tgid_stat, srcaddr))
        
        if base_tgid not in self.talkgroups:
            self.talkgroups[base_tgid] = {'counter':0}
            self.talkgroups[base_tgid]['tgid'] = base_tgid
            self.talkgroups[base_tgid]['prio'] = TGID_DEFAULT_PRIO
            self.talkgroups[base_tgid]['tag'] = "TGID[" + str(base_tgid) + "]"
            self.talkgroups[base_tgid]['srcaddr'] = 0
            self.talkgroups[base_tgid]['mode'] = -1
            self.talkgroups[base_tgid]['receiver'] = None
            if self.debug >= 5:
                sys.stderr.write('%s [%d] new tgid=%s %s prio %d\n' % (log_ts.get(), self.msgq_id, base_tgid, self.talkgroups[base_tgid]['tag'], self.talkgroups[base_tgid]['prio']))
                sys.stderr.write('%s [%d] new tgid=%s\n' % (log_ts.get(), self.msgq_id, base_tgid))
        self.talkgroups[base_tgid]['time'] = time.time()
        self.talkgroups[base_tgid]['frequency'] = frequency
        self.talkgroups[base_tgid]['status'] = tgid_stat
        if srcaddr >= 0:
            self.talkgroups[base_tgid]['srcaddr'] = srcaddr
        if mode >= 0:
            self.talkgroups[base_tgid]['mode'] = mode

    def expire_talkgroups(self, curr_time):
        if curr_time < self.last_expiry_check + EXPIRY_TIMER:
            return

        self.last_expiry_check = curr_time
        for tgid in self.talkgroups:
            if (self.talkgroups[tgid]['receiver'] is not None) and (curr_time >= self.talkgroups[tgid]['time'] + TGID_EXPIRY_TIME):
                if self.debug > 1:
                    sys.stderr.write("%s [%d] expiring tg(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, tgid, (self.talkgroups[tgid]['frequency']/1e6)))
                self.talkgroups[tgid]['receiver'].expire_talkgroup(reason="expiry")

    def to_json(self):  # ugly but required for compatibility with P25 trunking and terminal modules
        d = {}
        d['top_line']  = 'Smartnet/Smartzone SysId %04x' % (self.rx_sys_id if self.rx_sys_id is not None else 0)
        d['top_line'] += ' Control Ch %f' % ((self.rx_cc_freq if self.rx_cc_freq is not None else self.cc_list[self.cc_index]) / 1e6)
        d['top_line'] += ' OSW count %d' % (self.stats['osw_count'])
        d['secondary'] = ""
        d['frequencies'] = {}
        d['frequency_data'] = {}
        d['last_tsbk'] = self.last_osw
        t = time.time()
        for f in list(self.voice_frequencies.keys()):
            d['frequencies'][f] = 'voice frequency %f tgid %5d %4.1fs ago count %d' %  ((f/1e6), self.voice_frequencies[f]['tgid'], t - self.voice_frequencies[f]['time'], self.voice_frequencies[f]['counter'])

            d['frequency_data'][f] = {'tgids': [self.voice_frequencies[f]['tgid']], 'last_activity': '%7.1f' % (t - self.voice_frequencies[f]['time']), 'counter': self.voice_frequencies[f]['counter']}
        d['adjacent_data'] = ""
        return json.dumps(d)

#################
# Voice channel class
class voice_receiver(object):
    def __init__(self, debug, msgq_id, frequency_set, slot_set, nbfm_ctrl, control, config, meta_q = None):
        self.debug = debug
        self.msgq_id = msgq_id
        self.frequency_set = frequency_set
        self.slot_set = slot_set
        self.nbfm_ctrl = nbfm_ctrl
        self.control = control
        self.config = config
        self.meta_q = meta_q
        self.talkgroups = None
        self.tuned_frequency = 0
        self.current_tgid = None
        self.hold_tgid = None
        self.hold_until = 0.0
        self.tgid_hold_time = TGID_HOLD_TIME
        self.blacklist = {}
        self.whitelist = None
        self.vc_retries = 0

    def post_init(self):
        if self.debug >= 1:
            sys.stderr.write("%s [%d] Initializing voice channel\n" % (log_ts.get(), self.msgq_id))
        self.slot_set({'tuner': self.msgq_id,'slot': 4})     # disable voice

        if self.control is not None:
            self.talkgroups = self.control.get_talkgroups()

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

        self.tgid_hold_time = float(from_dict(self.control.config, 'tgid_hold_time', TGID_HOLD_TIME))

        meta_update(self.meta_q)

 
    def process_qmsg(self, msg, curr_time):
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

    def blacklist_update(self, start_time):
        expired_tgs = [tg for tg in list(self.blacklist.keys())
                            if self.blacklist[tg] is not None
                            and self.blacklist[tg] < start_time]
        for tg in expired_tgs:
            self.blacklist.pop(tg)

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
            if self.debug > 1:
                sys.stderr.write("%s [%d] voice update:  tg(%d), freq(%f), mode(%d)\n" % (log_ts.get(), self.msgq_id, tgid, (freq/1e6), self.talkgroups[tgid]['mode']))
            self.tune_voice(freq, tgid)
        else:
            if self.debug > 1:
                sys.stderr.write("%s [%d] voice preempt: tg(%d), freq(%f), mode(%d)\n" % (log_ts.get(), self.msgq_id, tgid, (freq/1e6), self.talkgroups[tgid]['mode']))
            self.expire_talkgroup(update_meta=False, reason="preempt")
            self.tune_voice(freq, tgid)

        meta_update(self.meta_q, tgid, self.talkgroups[tgid]['tag'])

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

    def expire_talkgroup(self, tgid=None, update_meta = True, reason="unk"):
        self.nbfm_ctrl(self.msgq_id, False)                                   # disable nbfm
        self.slot_set({'tuner': self.msgq_id,'slot': 4})                      # disable p25cai
        if self.current_tgid is None:
            return
            
        self.talkgroups[self.current_tgid]['receiver'] = None
        self.talkgroups[self.current_tgid]['srcaddr'] = 0
        if self.debug > 1:
            sys.stderr.write("%s [%d] releasing:  tg(%d), freq(%f), reason(%s)\n" % (log_ts.get(), self.msgq_id, self.current_tgid, (self.tuned_frequency/1e6), reason))
        self.hold_tgid = self.current_tgid
        self.hold_until = time.time() + TGID_HOLD_TIME
        self.current_tgid = None

        if update_meta:
            meta_update(self.meta_q)

    def to_json(self):  # more uglyness
        d = {}
        d['freq'] = self.tuned_frequency
        d['tgid'] = self.current_tgid
        d['system'] = self.config['trunking_sysname']
        d['tag'] = self.talkgroups[self.current_tgid]['tag'] if self.current_tgid is not None else ""
        d['srcaddr'] = self.talkgroups[self.current_tgid]['srcaddr'] if self.current_tgid is not None else 0
        d['mode'] = self.talkgroups[self.current_tgid]['mode'] if self.current_tgid is not None else -1
        d['stream'] = self.config['meta_stream_name'] if 'meta_stream_name' in self.config else ""
        return json.dumps(d)
