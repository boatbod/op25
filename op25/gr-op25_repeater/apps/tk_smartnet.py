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
    msg = gr.message().make_from_string(json.dumps(d), -2, time.time(), 0)
    if not meta_q.full_p():
        meta_q.insert_tail(msg)

#################
# Main trunking class
class rx_ctl(object):
    def __init__(self, debug=0, frequency_set=None, nbfm_ctrl=None, fa_ctrl=None, chans={}):
        self.frequency_set = frequency_set
        self.nbfm_ctrl = nbfm_ctrl
        self.fa_ctrl = fa_ctrl
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
                                        nbfm_ctrl     = self.nbfm_ctrl,
                                        fa_ctrl       = self.fa_ctrl,
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

    # Is the current config for an OBT system
    def is_obt_system(self):
        bandplan = from_dict(self.config, 'bandplan', "800_reband")
        band = bandplan[:3]
        return band == "OBT" or band == "400" # Still accept '400' for backwards compatibility

    # Attempt to auto-compute transmit offsets based on typical USA/Canada band plans
    def get_expected_obt_tx_freq(self, rx_freq):
        # VHF has no standard transmit offset so OBT systems usually use the same base freq, and assign different channel numbers
        if rx_freq >= 136.0 and rx_freq < 174.0:
            return rx_freq

        # UHF has standard transmit offsets so OBT systems usually use a different base freq, and assign the same channel number
        # Common US military
        if rx_freq >= 380.0 and rx_freq < 406.0:
            return rx_freq + 10.0
        # Common US federal
        if rx_freq >= 406.0 and rx_freq < 420.0:
            return rx_freq + 9.0
        # Standard US commercial
        if rx_freq >= 450.0 and rx_freq < 470.0:
            return rx_freq + 5.0
        # Standard US T-band
        if rx_freq >= 470.0 and rx_freq < 512.0:
            return rx_freq + 3.0

        # Unknown frequency range, so we can't get an expected value
        return 0.0

    # Is the 'chan' a valid frequency; uplink channel if is_tx=True (mostly applicable for OBT systems with explicit tx channel assignments)
    def is_chan(self, chan, is_tx=False):
        bandplan = from_dict(self.config, 'bandplan', "800_reband")
        band = bandplan[:3]
        subtype = bandplan[3:len(bandplan)].lower().lstrip("_-:")

        if band == "800":
            if subtype == "reband" and chan > 0x22f:
                return False
            if (chan >= 0 and chan <= 0x2f7) or (chan >= 0x32f and chan <= 0x33f) or (chan >= 0x3c1 and chan <= 0x3fe) or chan == 0x3be:
                return True

        elif band == "900":
            if chan >= 0 and chan <= 0x1de:
                return True

        elif band == "OBT" or band == "400": # Still accept '400' for backwards compatibility
            bp_base_offset    = int(from_dict(self.config, 'bp_base_offset', 380))
            bp_tx_base_offset = int(from_dict(self.config, 'bp_tx_base_offset', 0))
            if is_tx and (chan >= bp_tx_base_offset) and (chan < 380):
                return True
            elif not is_tx and (chan >= bp_base_offset) and (chan < 760):
                return True
            else:
                return False

        return False

    # Convert 'chan' into band-dependent frequency; uplink frequency if is_tx=True (mostly applicable for OBT systems with explicit tx channel assignments)
    def get_freq(self, chan, is_tx=False):
        # Short-circuit invalid frequencies
        if not self.is_chan(chan, is_tx):
            if self.debug >= 5:
                type_str = "transmit" if is_tx else "receive"
                sys.stderr.write("%s [%d] SMARTNET %s chan %d out of range\n" % (log_ts.get(), self.msgq_id, type_str, chan))
            return 0.0

        freq = 0.0
        bandplan = from_dict(self.config, 'bandplan', "800_reband")
        band = bandplan[:3]
        subtype = bandplan[3:len(bandplan)].lower().lstrip("_-:")

        if band == "800":
            if chan <= 0x2cf:
                # Rebanded site
                if subtype == "reband":
                    if chan < 0x1b8:
                        freq = 851.0125 + (0.025 * chan)
                    if chan >= 0x1b8 and chan <= 0x22f:
                        freq = 851.0250 + (0.025 * (chan - 0x1b8))
                # Splinter site
                elif subtype == "splinter" and chan <= 0x257:
                    freq = 851.0 + (0.025 * chan)
                # Standard site
                else:
                    freq = 851.0125 + (0.025 * chan)
            elif chan <= 0x2f7:
                freq = 866.0000 + (0.025 * (chan - 0x2d0))
            elif chan >= 0x32f and chan <= 0x33f:
                freq = 867.0000 + (0.025 * (chan - 0x32f))
            elif chan == 0x3be:
                freq = 868.9750
            elif chan >= 0x3c1 and chan <= 0x3fe:
                freq = 867.4250 + (0.025 * (chan - 0x3c1))
            if is_tx and freq != 0.0:
                freq -= 45.0 # Standard tx offset for 800 band

        elif band == "900":
            freq = 935.0125 + (0.0125 * chan)
            if is_tx and freq != 0.0:
                freq -= 39.0 # Standard tx offset for 900 band

        elif band == "OBT" or band == "400": # Still accept '400' for backwards compatibility
            # For OBT operation, we need a band plan. At minimum the user must provide a base frequency, and either
            # global or per-range spacing, so we read those directly rather than using from_dict() with a default value.

            # Receive parameters
            bp_base         = float(self.config['bp_base'])
            bp_mid          = float(from_dict(self.config, 'bp_mid',  bp_base))
            bp_high         = float(from_dict(self.config, 'bp_high', bp_mid))
            # Back-compat: assume all spacing is the same if new per-range spacing is not given
            if 'bp_spacing' in self.config and not ('bp_base_spacing' in self.config):
                bp_base_spacing = float(self.config['bp_spacing'])
            else:
                bp_base_spacing = float(self.config['bp_base_spacing'])
            bp_mid_spacing  = float(from_dict(self.config, 'bp_mid_spacing',  bp_base_spacing))
            bp_high_spacing = float(from_dict(self.config, 'bp_high_spacing', bp_mid_spacing))
            bp_base_offset  = int(from_dict(self.config,   'bp_base_offset',  380))
            bp_mid_offset   = int(from_dict(self.config,   'bp_mid_offset',   760))
            bp_high_offset  = int(from_dict(self.config,   'bp_high_offset',  760))

            if not is_tx:
                if (chan >= bp_base_offset) and (chan < bp_mid_offset):
                    freq = bp_base + (bp_base_spacing * (chan - bp_base_offset))
                elif (chan >= bp_mid_offset) and (chan < bp_high_offset):
                    freq = bp_mid + (bp_mid_spacing * (chan - bp_mid_offset))
                elif (chan >= bp_high_offset) and (chan < 760):
                    freq = bp_high + (bp_high_spacing * (chan - bp_high_offset))
                else:
                    if self.debug >= 5:
                        sys.stderr.write("%s [%d] SMARTNET receive chan %d out of range\n" % (log_ts.get(), self.msgq_id, chan))
            else:
                # Transmit parameters default to being based off receive parameters
                bp_tx_base         = float(from_dict(self.config, 'bp_tx_base',         self.get_expected_obt_tx_freq(bp_base)))
                bp_tx_mid          = float(from_dict(self.config, 'bp_tx_mid',          self.get_expected_obt_tx_freq(bp_mid)))
                bp_tx_high         = float(from_dict(self.config, 'bp_tx_high',         self.get_expected_obt_tx_freq(bp_high)))
                bp_tx_base_spacing = float(from_dict(self.config, 'bp_tx_base_spacing', bp_base_spacing))
                bp_tx_mid_spacing  = float(from_dict(self.config, 'bp_tx_mid_spacing',  bp_mid_spacing))
                bp_tx_high_spacing = float(from_dict(self.config, 'bp_tx_high_spacing', bp_high_spacing))
                bp_tx_base_offset  = int(from_dict(self.config,   'bp_tx_base_offset',  bp_base_offset - 380))
                bp_tx_mid_offset   = int(from_dict(self.config,   'bp_tx_mid_offset',   bp_mid_offset - 380))
                bp_tx_high_offset  = int(from_dict(self.config,   'bp_tx_high_offset',  bp_high_offset - 380))

                # Only return a frequency if we are given a (or computed an expected) transmit frequency. If not, return
                # 0.0, which can be handled by the display side.
                freq = 0.0
                if (chan >= bp_tx_base_offset) and (chan < bp_tx_mid_offset):
                    if bp_tx_base != 0.0:
                        freq = bp_tx_base + (bp_tx_base_spacing * (chan - bp_tx_base_offset))
                elif (chan >= bp_tx_mid_offset) and (chan < bp_tx_high_offset):
                    if bp_tx_mid != 0.0:
                        freq = bp_tx_mid + (bp_tx_mid_spacing * (chan - bp_tx_mid_offset))
                elif (chan >= bp_tx_high_offset) and (chan < 380):
                    if bp_tx_high != 0.0:
                        freq = bp_tx_high + (bp_tx_high_spacing * (chan - bp_tx_high_offset))
                else:
                    if self.debug >= 5:
                        sys.stderr.write("%s [%d] SMARTNET transmit chan %d out of range\n" % (log_ts.get(), self.msgq_id, chan))

        # Round to 5 decimal places to eliminate accumulated floating point errors
        return round(freq, 5)

    # Convert is-group bit to human-readable string
    def get_group_str(self, is_group):
        return "G" if is_group != 0 else "I"

    # Convert index into string of the frequency band
    def get_band(self, band):
        if band == 0:
            return "800 international splinter"
        elif band == 1:
            return "800 international"
        elif band == 2:
            return "800 domestic splinter"
        elif band == 3:
            return "800 domestic"
        elif band == 4:
            return "900"
        elif band == 5:
            return "800 rebanded"
        elif band == 7:
            return "OBT"
        else:
            return "%s" % (band)

    # Convert index into connect tone (Hz)
    def get_connect_tone(self, connect_tone_index):
        if connect_tone_index == 0:
            return 105.88
        elif connect_tone_index == 1:
            return 76.60
        elif connect_tone_index == 2:
            return 83.72
        elif connect_tone_index == 3:
            return 90.00
        elif connect_tone_index == 4:
            return 97.30
        elif connect_tone_index == 5:
            return 116.13
        elif connect_tone_index == 6:
            return 128.57
        elif connect_tone_index == 7:
            return 138.46
        else:
            return None

    # Convert features into a string showing the meaning
    def get_features_str(self, feat):
        failsoft    = (feat & 0x31 == 0)
        voc         = (feat & 0x20) >> 5
        wide_area   = (feat & 0x10) >> 4
        digital     = (feat & 0x8) >> 3
        analog      = (feat & 0x4) >> 2
        cvsd        = (feat & 0x2) >> 1
        active      = (feat & 0x1)

        feat_str = ""

        if failsoft:
            feat_str += "failsoft, "
        else:
            if voc:
                feat_str += "VOC, "
            if wide_area:
                feat_str += "wide area, "
            else:
                feat_str += "site trunk, "
        if digital:
            feat_str += "digital, "
        if analog:
            feat_str += "analog, "
        if cvsd:
            feat_str += "CVSD, "
        if active:
            feat_str += "active, "

        return feat_str[:-2]

    # Convert TGID into a string showing the call options; exclude "CLEAR" prefix if include_clear=False
    def get_call_options_str(self, tgid, include_clear=True):
        is_encrypted = (tgid & 0x8) >> 3
        options      = (tgid & 0x7)

        options_str = "ENCRYPTED" if is_encrypted else ("CLEAR" if include_clear else "")

        if options != 0:
            if options_str != "":
                options_str += " "

            if options == 1:
                options_str += "ANNOUNCEMENT"
            elif options == 2:
                options_str += "EMEREGENCY"
            elif options == 3:
                options_str += "PATCH"
            elif options == 4:
                options_str += "EMEREGENCY PATCH"
            elif options == 5:
                options_str += "EMERGENCY MULTISELECT"
            elif options == 6:
                options_str += "[UNDEFINED CALL OPTION]"
            elif options == 7:
                options_str += "MULTISELECT"

        return options_str

    # Do the TG's call options indicate a patch group
    def is_patch_group(self, tgid):
        return tgid & 0x7 == 3 or tgid & 0x7 == 4

    # Do the TG's call options indicate a multiselect group
    def is_multiselect_group(self, tgid):
        return tgid & 0x7 == 5 or tgid & 0x7 == 7

    def enqueue(self, addr, grp, cmd, ts):
        grp_str = self.get_group_str(grp)

        is_rx_chan = self.is_chan(cmd)
        is_tx_chan = self.is_chan(cmd, is_tx=True)

        rx_freq = 0.0
        tx_freq = 0.0
        if is_rx_chan:
            rx_freq = self.get_freq(cmd)
        if is_tx_chan:
            tx_freq = self.get_freq(cmd, is_tx=True)

        if self.debug >= 13:
            if is_rx_chan and is_tx_chan:
                sys.stderr.write("%s [%d] SMARTNET RAW OSW (0x%04x,%s,0x%03x;rx:%f,tx:%f)\n" % (log_ts.get(), self.msgq_id, addr, grp_str, cmd, rx_freq, tx_freq))
            elif is_rx_chan:
                sys.stderr.write("%s [%d] SMARTNET RAW OSW (0x%04x,%s,0x%03x;rx:%f)\n" % (log_ts.get(), self.msgq_id, addr, grp_str, cmd, rx_freq))
            elif is_tx_chan:
                sys.stderr.write("%s [%d] SMARTNET RAW OSW (0x%04x,%s,0x%03x;tx:%f)\n" % (log_ts.get(), self.msgq_id, addr, grp_str, cmd, tx_freq))
            else:
                sys.stderr.write("%s [%d] SMARTNET RAW OSW (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, addr, grp_str, cmd))

        self.osw_q.append((addr, (grp != 0), cmd, is_rx_chan, is_tx_chan, rx_freq, tx_freq, ts))

    def process_osws(self):
        if len(self.osw_q) < OSW_QUEUE_SIZE:
            return False

        rc = False
        osw2_addr, osw2_grp, osw2_cmd, osw2_ch_rx, osw2_ch_tx, osw2_f_rx, osw2_f_tx, osw2_t = self.osw_q.popleft()
        grp2_str = self.get_group_str(osw2_grp)

        # Parsing for OBT-specific commands. OBT systems sometimes (always?) use explicit commands that provide tx and
        # rx channels separately for certain system information, and for voice grants. Check for them specifically
        # first, but then fall back to non-OBT-specific parsing if that fails.
        if self.is_obt_system() and osw2_ch_tx:
            # Get next OSW in the queue
            osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t = self.osw_q.popleft()
            grp1_str = self.get_group_str(osw1_grp)

            # Three-OSW system information
            if osw1_cmd == 0x320 and osw2_grp and osw1_grp:
                # Get OSW0
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t = self.osw_q.popleft()

                # The information returned here may be for this site, or may be for other adjacent sites
                if osw0_cmd == 0x30b and not osw0_grp and osw0_addr & 0xfc00 == 0x6000:
                    type_str = "ADJACENT SITE" if osw0_grp else "ALTERNATE CONTROL CHANNEL"
                    sysid = osw2_addr
                    # Sites are encoded as 0-indexed but usually referred to as 1-indexed
                    site = ((osw1_addr & 0xfc00) >> 10) + 1
                    band = (osw1_addr & 0x380) >> 7
                    feat = (osw1_addr & 0x3f)
                    cc_rx_freq = self.get_freq(osw0_addr & 0x3ff)
                    cc_tx_freq = osw2_f_tx
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET OBT %s sys(0x%04x) site(%02d) band(%s) features(%s) cc_rx_freq(%f)" % (log_ts.get(), self.msgq_id, type_str, sysid, site, self.get_band(band), self.get_features_str(feat), cc_rx_freq))
                        if cc_tx_freq != 0.0:
                            sys.stderr.write(" cc_tx_freq(%f)" % (cc_tx_freq))
                        sys.stderr.write("\n")
                else:
                    # Put back unused OSW0
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t))

                    if self.debug >= 11:
                        ts = log_ts.get()
                        sys.stderr.write("%s [%d] SMARTNET OBT UNKNOWN OSW (0x%04x,%s,0x%03x)\n" % (ts, self.msgq_id, osw2_addr, grp2_str, osw2_cmd))
                        sys.stderr.write("%s [%d] SMARTNET OBT UNKNOWN OSW (0x%04x,%s,0x%03x)\n" % (ts, self.msgq_id, osw1_addr, grp1_str, osw1_cmd))
            # Two-OSW group voice grant command
            elif osw1_ch_rx and osw2_grp and osw1_grp and (osw1_addr != 0) and (osw2_addr != 0):
                mode = 0 if osw2_grp else 1
                type_str = "ANALOG" if osw2_grp else "DIGITAL"
                src_rid = osw2_addr
                dst_tgid = osw1_addr
                vc_rx_freq = osw1_f_rx
                vc_tx_freq = osw2_f_tx
                rc |= self.update_voice_frequency(vc_rx_freq, dst_tgid, src_rid, mode=mode, ts=osw1_t)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET OBT %s %s GROUP GRANT src(%05d) tgid(%05d/0x%03x) vc_rx_freq(%f)" % (log_ts.get(), self.msgq_id, type_str, self.get_call_options_str(dst_tgid), src_rid, dst_tgid, dst_tgid >> 4, vc_rx_freq))
                    if vc_tx_freq != 0.0:
                        sys.stderr.write(" vc_tx_freq(%f)" % (vc_tx_freq))
                    sys.stderr.write("\n")
            else:
                # Put back unused OSW1
                self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t))

                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET OBT UNKNOWN OSW (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, osw2_addr, grp2_str, osw2_cmd))
        # One-OSW voice update
        elif osw2_ch_rx and osw2_grp:
            dst_tgid = osw2_addr
            vc_freq = osw2_f_rx
            rc |= self.update_voice_frequency(vc_freq, dst_tgid, ts=osw2_t)
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET %s GROUP UPDATE tgid(%05d/0x%03x) vc_freq(%f)\n" % (log_ts.get(), self.msgq_id, self.get_call_options_str(dst_tgid), dst_tgid, dst_tgid >> 4, vc_freq))
        # One-OSW control channel broadcast
        elif osw2_ch_rx and not osw2_grp and ((osw2_addr & 0xff00) == 0x1f00):
            cc_freq = osw2_f_rx
            self.rx_cc_freq = cc_freq * 1e6
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET CONTROL CHANNEL 1 cc_freq(%f)\n" % (log_ts.get(), self.msgq_id, cc_freq))
        # One-OSW system idle
        elif osw2_cmd == 0x2f8 and not osw2_grp:
            grp_str = grp2_str
            data = osw2_addr
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET IDLE data(%s,0x%04x)\n" % (log_ts.get(), self.msgq_id, grp_str, data))
        # Two-OSW command
        elif osw2_cmd == 0x308:
            # Get next OSW in the queue
            osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t = self.osw_q.popleft()
            grp1_str = self.get_group_str(osw1_grp)

            # Two-OSW system ID + control channel broadcast
            if osw1_ch_rx and not osw1_grp and ((osw1_addr & 0xff00) == 0x1f00):
                system = osw2_addr
                cc_freq = osw1_f_rx
                data = osw1_addr & 0xff
                self.rx_sys_id = system
                self.rx_cc_freq = cc_freq * 1e6
                if self.debug == 11:
                    sys.stderr.write("%s [%d] SMARTNET CONTROL CHANNEL 2 sys(0x%04x) cc_freq(%f) data(0x%02x)\n" % (log_ts.get(), self.msgq_id, system, cc_freq, data))
            # Two-OSW analog group voice grant
            elif osw1_ch_rx and osw1_grp and (osw1_addr != 0) and (osw2_addr != 0):
                src_rid = osw2_addr
                dst_tgid = osw1_addr
                vc_freq = osw1_f_rx
                rc |= self.update_voice_frequency(vc_freq, dst_tgid, src_rid, mode=0, ts=osw1_t)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET ANALOG %s GROUP GRANT src(%05d) tgid(%05d/0x%03x) vc_freq(%f)\n" % (log_ts.get(), self.msgq_id, self.get_call_options_str(dst_tgid), src_rid, dst_tgid, dst_tgid >> 4, vc_freq))
            # One of many possible two- or three-OSW meanings...
            elif osw1_cmd == 0x30b:
                # Get next OSW in the queue
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t = self.osw_q.popleft()

                # Three-OSW system ID + control channel broadcast
                if (
                    osw1_grp and not osw0_grp and osw0_ch_rx and
                    (osw0_addr & 0xff00) == 0x1f00 and
                    (osw1_addr & 0xfc00) == 0x2800 and
                    (osw1_addr & 0x3ff) == osw0_cmd
                ):
                    system = osw2_addr
                    cc_freq = osw0_f_rx
                    data = osw0_addr & 0xff
                    self.rx_sys_id = system
                    self.rx_cc_freq = cc_freq * 1e6
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET CONTROL CHANNEL 3 sys(0x%04x) cc_freq(%f) data(0x%02x)\n" % (log_ts.get(), self.msgq_id, system, cc_freq, data))
                # Two-OSW messages
                else:
                    # Put back unused OSW0
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t))

                    # System ID + control channel broadcast
                    if (osw1_addr & 0xfc00) == 0x2800 and osw1_grp:
                        system = osw2_addr
                        cc_freq = self.get_freq(osw1_addr & 0x3ff)
                        self.rx_sys_id = system
                        self.rx_cc_freq = cc_freq * 1e6
                        if self.debug >= 11:
                            sys.stderr.write("%s [%d] SMARTNET CONTROL CHANNEL 2 sys(0x%04x) cc_freq(%f)\n" % (log_ts.get(), self.msgq_id, system, cc_freq))
                    # System ID + adjacent/alternate control channel broadcast
                    elif (osw1_addr & 0xfc00) == 0x6000:
                        type_str = "ADJACENT" if osw1_grp else "ALTERNATE"
                        system = osw2_addr
                        cc_freq = self.get_freq(osw1_addr & 0x3ff)
                        if self.debug >= 11:
                            sys.stderr.write("%s [%d] SMARTNET %s CONTROL CHANNEL sys(0x%04x) cc_freq(%f)\n" % (log_ts.get(), self.msgq_id, type_str, system, cc_freq))
                    # Extended functions on groups
                    elif osw1_grp:
                        # Patch/multiselect cancel
                        if osw1_addr == 0x2021 and (self.is_patch_group(osw2_addr) or self.is_multiselect_group(osw2_addr)):
                            type_str = self.get_call_options_str(osw2_addr, include_clear=False)
                            sub_tgid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET %s CANCEL sub_tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, type_str, sub_tgid, sub_tgid >> 4))
                        # Unknown extended function
                        else:
                            tgid = osw2_addr
                            code = osw1_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET GROUP EXTENDED FUNCTION tgid(%05d/0x%03x) code(0x%04x)\n" % (log_ts.get(), self.msgq_id, tgid, tgid >> 4, code))
                    # Extended functions on individuals
                    else:
                        # Radio check
                        if osw1_addr == 0x261b:
                            tgt_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET RADIO CHECK tgt(%05d)\n" % (log_ts.get(), self.msgq_id, tgt_rid))
                        # Deaffiliation
                        elif osw1_addr == 0x261c:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DEAFFILIATION src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Failsoft assign
                        elif osw1_addr == 0x8301:
                            tgt_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET FAILSOFT ASSIGN tgt(%05d)\n" % (log_ts.get(), self.msgq_id, tgt_rid))
                        # Selector unlocked
                        elif osw1_addr == 0x8302:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET SELECTOR UNLOCKED src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Selector locked
                        elif osw1_addr == 0x8303:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET SELECTOR LOCKED src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Failsoft canceled
                        elif osw1_addr == 0x8305:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET FAILSOFT CANCELED src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Radio inhibited
                        elif osw1_addr == 0x8307:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET RADIO INHIBITED src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Radio uninhibited
                        elif osw1_addr == 0x8308:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET RADIO UNINHIBITED src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Selector unlock
                        elif osw1_addr == 0x8312:
                            tgt_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET SELECTOR UNLOCK tgt(%05d)\n" % (log_ts.get(), self.msgq_id, tgt_rid))
                        # Selector lock
                        elif osw1_addr == 0x8313:
                            tgt_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET SELECTOR LOCK tgt(%05d)\n" % (log_ts.get(), self.msgq_id, tgt_rid))
                        # Failsoft cancel
                        elif osw1_addr == 0x8315:
                            tgt_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET FAILSOFT CANCEL tgt(%05d)\n" % (log_ts.get(), self.msgq_id, tgt_rid))
                        # Radio inhibit
                        elif osw1_addr == 0x8317:
                            tgt_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET RADIO INHIBIT tgt(%05d)\n" % (log_ts.get(), self.msgq_id, tgt_rid))
                        # Radio uninhibit
                        elif osw1_addr == 0x8318:
                            tgt_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET RADIO UNINHIBIT tgt(%05d)\n" % (log_ts.get(), self.msgq_id, tgt_rid))
                        # Denial
                        elif (osw1_addr & 0xfc00) == 0x2c00:
                            src_rid = osw2_addr
                            reason = osw1_addr & 0x3ff
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED src(%05d) code(0x%03x)\n" % (log_ts.get(), self.msgq_id, src_rid, reason))
                        # Unknown extended function
                        else:
                            src_rid = osw2_addr
                            code = osw1_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET INDIVIDUAL EXTENDED FUNCTION src(%05d) code(0x%04x)\n" % (log_ts.get(), self.msgq_id, src_rid, code))
            # Two-OSW dynamic regroup (unknown whether OSWs are group or individual)
            elif osw1_cmd == 0x30a:
                src_rid = osw2_addr
                tgid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET DYNAMIC REGROUP src(%05d) tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, src_rid, tgid, tgid >> 4))
            # Two-OSW affiliation
            elif osw1_cmd == 0x310 and not osw2_grp and not osw1_grp:
                src_rid = osw2_addr
                dst_tgid = osw1_addr & 0xfff0
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET AFFILIATION src(%05d) tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, dst_tgid >> 4))
            # Three-OSW system information
            elif osw1_cmd == 0x320:
                # Get OSW0
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t = self.osw_q.popleft()

                # The information returned here may be for this site, or may be for other adjacent sites
                if osw0_cmd == 0x30b and osw0_addr & 0xfc00 == 0x6000:
                    type_str = "ADJACENT SITE" if osw0_grp else "ALTERNATE CONTROL CHANNEL"
                    sysid = osw2_addr
                    # Sites are encoded as 0-indexed but usually referred to as 1-indexed
                    site = ((osw1_addr & 0xfc00) >> 10) + 1
                    band = (osw1_addr & 0x380) >> 7
                    feat = (osw1_addr & 0x3f)
                    cc_freq = self.get_freq(osw0_addr & 0x03ff)
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET %s sys(0x%04x) site(%02d) band(%s) features(%s) cc_freq(%f)\n" % (log_ts.get(), self.msgq_id, type_str, sysid, site, self.get_band(band), self.get_features_str(feat), cc_freq))
                else:
                    # Put back unused OSW0
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t))

                    if self.debug >= 11:
                        ts = log_ts.get()
                        sys.stderr.write("%s [%d] SMARTNET UNKNOWN OSW (0x%04x,%s,0x%03x)\n" % (ts, self.msgq_id, osw2_addr, grp2_str, osw2_cmd))
                        sys.stderr.write("%s [%d] SMARTNET UNKNOWN OSW (0x%04x,%s,0x%03x)\n" % (ts, self.msgq_id, osw1_addr, grp1_str, osw1_cmd))
            # Two-OSW date/time
            elif osw1_cmd == 0x322 and osw2_grp and osw1_grp:
                year   = ((osw2_addr & 0xfe00) >> 9) + 2000
                month  = (osw2_addr & 0x1e0) >> 5
                day    = (osw2_addr & 0x1f)
                data   = (osw1_addr & 0xe000) >> 13
                hour   = (osw1_addr & 0x1f00) >> 8
                minute = osw1_addr & 0xff
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET DATE/TIME %04d-%02d-%02d %02d:%02d data(0x%01x)\n" % (log_ts.get(), self.msgq_id, year, month, day, hour, minute, data))
            # Two-OSW patch/multiselect
            elif osw1_cmd == 0x340 and osw2_grp and osw1_grp and (self.is_patch_group(osw2_addr) or self.is_multiselect_group(osw2_addr)):
                type_str = self.get_call_options_str(osw2_addr, include_clear=False)
                tgid = (osw1_addr & 0xfff) << 4
                sub_tgid = osw2_addr & 0xfff0
                if self.debug >= 11:
                    if tgid == sub_tgid:
                        sys.stderr.write("%s [%d] SMARTNET %s tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, type_str, tgid, tgid >> 4))
                    else:
                        sys.stderr.write("%s [%d] SMARTNET %s tgid(%05d/0x%03x) sub_tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, type_str, tgid, tgid >> 4, sub_tgid, sub_tgid >> 4))
            else:
                # OSW1 did not match, so put it back in the queue
                self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t))
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET UNKNOWN OSW (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, osw2_addr, grp2_str, osw2_cmd))
        # Two-OSW command
        elif osw2_cmd == 0x321:
            # Get next OSW in the queue
            osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t = self.osw_q.popleft()

            # Two-OSW digital group voice grant
            if osw1_ch_rx and osw2_grp and osw1_grp and (osw1_addr != 0):
                src_rid = osw2_addr
                dst_tgid = osw1_addr
                vc_freq = osw1_f_rx
                rc |= self.update_voice_frequency(vc_freq, dst_tgid, src_rid, mode=1, ts=osw1_t)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET DIGITAL %s GROUP GRANT src(%05d) tgid(%05d/0x%03x) vc_freq(%f)\n" % (log_ts.get(), self.msgq_id, self.get_call_options_str(dst_tgid), src_rid, dst_tgid, dst_tgid >> 4, vc_freq))
            else:
                # OSW1 did not match, so put it back in the queue
                self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t))
        # One-OSW system ID / scan marker
        elif osw2_cmd == 0x32b and not osw2_grp:
            system   = osw2_addr
            type_str = "II"
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET SYSTEM sys(0x%04x) type(%s)\n" % (log_ts.get(), self.msgq_id, system, type_str))
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET SYSTEM sys(0x%04x)\n" % (log_ts.get(), self.msgq_id, system))
        # One-OSW AMSS (Automatic Multiple Site Select) message
        elif osw2_cmd >= 0x360 and osw2_cmd <= 0x39f and osw2_grp:
            # Sites are encoded as 0-indexed but usually referred to as 1-indexed
            site = osw2_cmd - 0x360 + 1
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET AMSS site(%02d)\n" % (log_ts.get(), self.msgq_id, site))
        # One-OSW system status update
        elif osw2_cmd == 0x3bf or osw2_cmd == 0x3c0:
            scope = "SYSTEM" if osw2_cmd == 0x3c0 else "NETWORK"
            opcode = (osw2_addr & 0xe000) >> 13
            data = osw2_addr & 0x1fff
            if opcode == 1:
                type_ii              = (data & 0x1000) >> 12
                type_str             = "II" if type_ii else "I"
                dispatch_timeout     = (data & 0xe00) >> 9
                connect_tone         = (data & 0x1e0) >> 5
                connect_tone_str     = self.get_connect_tone(connect_tone)
                interconnect_timeout = (data & 0x1f)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET %s STATUS type(%s) connect_tone(%.02f) dispatch_timeout(%d) interconnect_timeout(%d)\n" % (log_ts.get(), self.msgq_id, scope, type_str, connect_tone_str, dispatch_timeout, interconnect_timeout))
            elif opcode == 2:
                no_secure        = (data & 0x1000) >> 12
                secure_upgrade   = (data & 0x800) >> 11
                full_data        = (data & 0x400) >> 10
                no_data          = (data & 0x200) >> 9
                reduced_otar     = (data & 0x100) >> 8
                multikey_buf_b   = (data & 0x80) >> 7
                bit6             = (data & 0x40) >> 6
                cvsd_echo_delay  = (data & 0x3e) >> 1
                bit0             = (data & 0x1)
                # Try to make it more human-readable
                secure_str       = "None" if no_secure else ("Upgraded" if secure_upgrade else "Standard")
                data_str         = "None" if no_data else ("Full" if full_data else "Reduced")
                otar_str         = "Reduced" if reduced_otar else "Full"
                multikey_buf_str = "B" if multikey_buf_b else "A"
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET %s STATUS data(%s) secure(%s)" % (log_ts.get(), self.msgq_id, scope, data_str, secure_str))
                    # If we have secure enabled
                    if no_secure == 0:
                        # If we have data enabled
                        if no_data == 0:
                            sys.stderr.write(" otar(%s)" % (otar_str))
                        sys.stderr.write(" multikey_buf(%s) cvsd_echo_delay(%02d)" % (multikey_buf_str, cvsd_echo_delay))
                    sys.stderr.write(" bit6(%d) bit0(%d)\n" % (bit6, bit0))
            elif opcode == 3:
                rotation     = (data & 0x800) >> 11
                wide_pulse   = (data & 0x400) >> 10
                cvsd_mod_4   = (data & 0x200) >> 9
                cvsd_mod_str = "4" if cvsd_mod_4 else "2"
                trespass     = (data & 0x100) >> 8
                voc          = (data & 0x80) >> 7
                bit2_6       = (data & 0x7c) >> 2
                site_trunk   = (data & 0x2) >> 1
                wide_area    = (data & 0x1)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET %s STATUS rotation(%d) wide_pulse(%d) cvsd_mod(%s) trespass(%d) voc(%d) site_trunk(%d) wide_area(%d) bit2_6(0x%02x)\n" % (log_ts.get(), self.msgq_id, scope, rotation, wide_pulse, cvsd_mod_str, trespass, voc, site_trunk, wide_area, bit2_6))
            else:
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET %s STATUS type(%s) opcode(0x%x) data(0x%04x)\n" % (log_ts.get(), self.msgq_id, scope, grp2_str, opcode, data))
        else:
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET UNKNOWN OSW (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, osw2_addr, grp2_str, osw2_cmd))

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
        d['top_line']       = 'SmartNet/SmartZone SysId 0x%04x' % (self.rx_sys_id if self.rx_sys_id is not None else 0)
        d['top_line']      += ' Control Ch %f' % ((self.rx_cc_freq if self.rx_cc_freq is not None else self.cc_list[self.cc_index]) / 1e6)
        d['top_line']      += ' OSW count %d' % (self.stats['osw_count'])
        d['secondary']      = ""
        d['frequencies']    = {}
        d['frequency_data'] = {}
        d['last_tsbk'] = self.last_osw
        t = time.time()
        for f in list(self.voice_frequencies.keys()):
            # Show time in appropriate units based on how long ago - useful for some high-capacity/low-traffic sites
            time_ago = t - self.voice_frequencies[f]['time']
            if time_ago < (60.0):
                time_ago_str = "%4.1fs ago" % (time_ago)
            elif time_ago < (60.0 * 60.0):
                time_ago_str = "%4.1fm ago" % (time_ago / 60.0)
            elif time_ago < (60.0 * 60.0 * 24.0):
                time_ago_str = "%4.1fh ago" % (time_ago / 60.0 / 60.0)
            else:
                time_ago_str = "%4.1fd ago" % (time_ago / 60.0 / 60.0 / 24.0)

            # Only show TGID if we believe the call is currently ongoing
            if t - self.voice_frequencies[f]['time'] < TGID_EXPIRY_TIME:
                d['frequencies'][f] = 'voice frequency %f tgid [%5d 0x%03x]   Now     count %d' %  ((f/1e6), self.voice_frequencies[f]['tgid'], self.voice_frequencies[f]['tgid'] >> 4, self.voice_frequencies[f]['counter'])
            else:
                d['frequencies'][f] = 'voice frequency %f tgid [           ] %s count %d' %  ((f/1e6), time_ago_str, self.voice_frequencies[f]['counter'])

            d['frequency_data'][f] = {'tgids': [self.voice_frequencies[f]['tgid']], 'last_activity': '%7.1f' % (time_ago), 'counter': self.voice_frequencies[f]['counter']}
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
    def __init__(self, debug, msgq_id, frequency_set, nbfm_ctrl, fa_ctrl, control, config, meta_q = None, freq = 0):
        self.debug = debug
        self.msgq_id = msgq_id
        self.frequency_set = frequency_set
        self.nbfm_ctrl = nbfm_ctrl
        self.fa_ctrl = fa_ctrl
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
        self.fa_ctrl({'tuner': self.msgq_id, 'cmd': 'set_slotid', 'slotid': 4})     # disable voice
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
        self.fa_ctrl({'tuner': self.msgq_id, 'cmd': 'set_slotid', 'slotid': 0}) # always enable digital p25cai
        self.nbfm_ctrl(self.msgq_id, (self.talkgroups[tgid]['mode'] != 1) )     # enable nbfm unless mode is digital

    def expire_talkgroup(self, tgid=None, update_meta = True, reason="unk", auto_hold = True):
        expire_time = time.time()
        self.nbfm_ctrl(self.msgq_id, False)                                     # disable nbfm
        self.fa_ctrl({'tuner': self.msgq_id, 'cmd': 'set_slotid', 'slotid': 4}) # disable p25cai
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
