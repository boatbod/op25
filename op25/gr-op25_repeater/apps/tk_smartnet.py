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

# Message queue message types (defined in lib/op25_msg_types.h)
M_SMARTNET_TIMEOUT      = -1
M_SMARTNET_BAD_OSW      = -2
M_SMARTNET_OSW          =  0
M_SMARTNET_END_PTT      = 15

# OSW queue values
OSW_QUEUE_SIZE          = 5 + 1 # Some messages can be 3 OSWs long, plus up to two IDLEs can be inserted in between
                                # useful messages. Additionally, keep one slot for a QUEUE RESET message.
OSW_QUEUE_RESET_CMD     = 0xffe # OSW command representing QUEUE RESET took place; not a valid cmd so it won't conflict

# SmartNet trunking constants
CC_TIMEOUT_RETRIES      = 3     # Number of control channel framing timeouts before hunting
VC_TIMEOUT_RETRIES      = 3     # Number of voice channel framing timeouts before expiry
TGID_DEFAULT_PRIO       = 3     # Default tgid priority when unassigned
TGID_HOLD_TIME          = 2.0   # Number of seconds to give previously active tgid exclusive channel access
TGID_SKIP_TIME          = 4.0   # Number of seconds to blacklist a previously skipped tgid
TGID_EXPIRY_TIME        = 1.0   # Number of seconds to allow tgid to remain active with no updates received
EXPIRY_TIMER            = 0.2   # Number of seconds between checks for expirations
PATCH_EXPIRY_TIME       = 20.0  # Number of seconds until patch expiry
ALT_CC_EXPIRY_TIME      = 120.0 # Number of seconds until alternate CC expiry
ADJ_SITE_EXPIRY_TIME    = 300.0 # Number of seconds until adjacent site expiry

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
        self.patches = {}
        self.skiplist = {}
        self.blacklist = {}
        self.whitelist = None
        self.alternate_cc_freqs = {}
        self.adjacent_sites = {}
        self.cc_list = []
        self.cc_index = -1
        self.cc_retries = 0
        self.last_expiry_check = 0.0
        self.last_osw = 0.0
        self.rx_cc_freq = None
        self.rx_sys_id = None
        self.rx_site_id = None
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

        # Control Channel Timeout
        if m_type == M_SMARTNET_TIMEOUT:
            if self.debug > 10:
                sys.stderr.write("%s [%d] control channel timeout\n" % (log_ts.get(), self.msgq_id))
            self.cc_retries += 1
            if self.cc_retries >= CC_TIMEOUT_RETRIES:
                self.tune_next_cc()

        # Bad OSW received (sync failure or bad CRC)
        elif m_type == M_SMARTNET_BAD_OSW:
            # Clear the OSW queue - this avoids us incorrectly trying to parse multi-OSW messages across the bad OSW.
            # This increases decoding accuracy at the cost of reduced "performance" in extremely marginal conditions,
            # though odds are we'd be incorrectly parsing the messages we received anyway.
            self.osw_q.clear()

            # Enqueue a "QUEUE RESET" message that we can identify so that we know any OSWs after it that we fail to
            # parse may be due to a missing first OSW in a multi-OSW sequence.
            self.enqueue(0xffff, 0x1, OSW_QUEUE_RESET_CMD, m_ts)

        # Good OSW received
        elif m_type == M_SMARTNET_OSW:
            s = msg.to_string()
            osw_addr = get_ordinals(s[0:2])
            osw_grp  = get_ordinals(s[2:3])
            osw_cmd  = get_ordinals(s[3:5])
            self.enqueue(osw_addr, osw_grp, osw_cmd, m_ts)
            self.stats['osw_count'] += 1
            self.last_osw = m_ts
            self.cc_retries = 0

        # Some message we don't know about or expect
        else:
            if self.debug > 10:
                sys.stderr.write("%s [%d] unknown queue message type %d\n" % (log_ts.get(), self.msgq_id, m_type))

        rc = False
        rc |= self.process_osws()

        if curr_time >= self.last_expiry_check + EXPIRY_TIMER:
            rc |= self.expire_talkgroups(curr_time)
            rc |= self.expire_patches(curr_time)
            rc |= self.expire_alternate_cc_freqs(curr_time)
            rc |= self.expire_adjacent_sites(curr_time)

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

        # Trim the trailing comma and space
        return feat_str[:-2]

    # Convert TGID options into a string showing the call options; exclude "CLEAR" prefix if include_clear=False
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

    # Convert mode and TGID options into a set of letter flags showing the call options
    def get_call_options_flags_str(self, tgid, mode=None):
        is_encrypted = (tgid & 0x8) >> 3
        options      = (tgid & 0x7)

        if mode == None:    options_str = ""
        elif mode == 0:     options_str = "A"
        elif mode == 1:     options_str = "D"
        else:               options_str = "U"

        options_str += "E " if is_encrypted else "  "

        if options != 0:
            if options == 1:    options_str += "Ann"
            elif options == 2:  options_str += "Em"
            elif options == 3:  options_str += "   P"
            elif options == 4:  options_str += "Em P"
            elif options == 5:  options_str += "Em MS"
            elif options == 6:  options_str += "UNDEF"
            elif options == 7:  options_str += "   MS"

        return options_str

    # Convert mode and TGID options into a set of letter flags showing the call options, but for web interface
    def get_call_options_flags_web_str(self, tgid, mode):
        is_encrypted = (tgid & 0x8) >> 3
        options      = (tgid & 0x7)

        if mode == 0:   options_str = "A"
        elif mode == 1: options_str = "D"
        else:           options_str = "U"

        options_str += "E" if is_encrypted else "&nbsp;"
        options_str += "&nbsp;"

        # Ensure the string is always length 8, but use non-breaking space, because web
        if options == 0:    options_str += "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        elif options == 1:  options_str += "Ann" + "&nbsp;&nbsp;"
        elif options == 2:  options_str += "Em" + "&nbsp;&nbsp;&nbsp;"
        elif options == 3:  options_str += "P" + "&nbsp;&nbsp;&nbsp;&nbsp;"
        elif options == 4:  options_str += "Em" + "&nbsp;" + "P" + "&nbsp;"
        elif options == 5:  options_str += "Em" + "&nbsp;" + "MS"
        elif options == 6:  options_str += "UNDEF"
        elif options == 7:  options_str += "MS" + "&nbsp;&nbsp;&nbsp;"

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

        is_unknown_osw = False
        is_queue_reset = False

        # Identify the QUEUE RESET message if present. This means that we have received a bad OSW (lost sync or bad CRC)
        # that caused us to dump the queue. If we see one (and sometimes there are several in a row), we should treat
        # any unknown OSWs that follow specially for logging - identify them as potentially due to a missing first OSW
        # in a multi-OSW sequence rather than just being unknown.
        while osw2_cmd == OSW_QUEUE_RESET_CMD:
            is_queue_reset = True

            # Save the queue reset message for later - if we end up with an unknown OSW, we'll keep putting it back at
            # the head of the queue until we successfully parse an OSW, since that is the likely cause of unknown OSWs
            queue_reset_addr  = osw2_addr
            queue_reset_grp   = osw2_grp
            queue_reset_cmd   = osw2_cmd
            queue_reset_ch_rx = osw2_ch_rx
            queue_reset_ch_tx = osw2_ch_tx
            queue_reset_f_rx  = osw2_f_rx
            queue_reset_f_tx  = osw2_f_tx
            queue_reset_t     = osw2_t

            # Get the next message until it is a good OSW
            osw2_addr, osw2_grp, osw2_cmd, osw2_ch_rx, osw2_ch_tx, osw2_f_rx, osw2_f_tx, osw2_t = self.osw_q.popleft()
            grp2_str = self.get_group_str(osw2_grp)

        if is_queue_reset:
            # If we only had a single queue reset message, continue to process the OSWs (queue was sized accordingly)
            if len(self.osw_q) == OSW_QUEUE_SIZE - 2:
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET QUEUE RESET DUE TO BAD OSW\n" % (log_ts.get(), self.msgq_id))
            # If we only had more than one queue reset message, we need to put one back and wait for more OSWs
            else:
                self.osw_q.appendleft((queue_reset_addr, queue_reset_grp, queue_reset_cmd, queue_reset_ch_rx, queue_reset_ch_tx, queue_reset_f_rx, queue_reset_f_tx, queue_reset_t))
                return rc

        # Parsing for OBT-specific messages. OBT systems sometimes (always?) use explicit messages that provide tx and
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
                if osw0_cmd == 0x30b and osw0_addr & 0xfc00 == 0x6000:
                    type_str = "ADJACENT SITE" if osw0_grp else "ALTERNATE CONTROL CHANNEL"
                    system = osw2_addr
                    # Sites are encoded as 0-indexed but usually referred to as 1-indexed
                    site = ((osw1_addr & 0xfc00) >> 10) + 1
                    band = (osw1_addr & 0x380) >> 7
                    feat = (osw1_addr & 0x3f)
                    cc_rx_chan = osw0_addr & 0x3ff
                    cc_rx_freq = self.get_freq(cc_rx_chan)
                    cc_tx_freq = osw2_f_tx
                    self.rx_sys_id = system
                    if osw0_grp:
                        self.add_adjacent_site(osw1_t, site, cc_rx_freq, cc_tx_freq)
                    else:
                        self.rx_site_id = site
                        self.add_alternate_cc_freq(osw1_t, cc_rx_freq, cc_tx_freq)
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET OBT %s sys(0x%04x) site(%02d) band(%s) features(%s) cc_rx_freq(%f)" % (log_ts.get(), self.msgq_id, type_str, system, site, self.get_band(band), self.get_features_str(feat), cc_rx_freq))
                        if cc_tx_freq != 0.0:
                            sys.stderr.write(" cc_tx_freq(%f)" % (cc_tx_freq))
                        sys.stderr.write("\n")
                else:
                    # Track that we got an unknown OSW and put back unused OSW0
                    is_unknown_osw = True
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t))

                    if self.debug >= 11:
                        ts = log_ts.get()
                        type_str = "UNKNOWN OSW AFTER BAD OSW" if is_queue_reset else "UNKNOWN OSW"
                        sys.stderr.write("%s [%d] SMARTNET OBT %s (0x%04x,%s,0x%03x)\n" % (ts, self.msgq_id, type_str, osw2_addr, grp2_str, osw2_cmd))
                        sys.stderr.write("%s [%d] SMARTNET OBT %s (0x%04x,%s,0x%03x)\n" % (ts, self.msgq_id, type_str, osw1_addr, grp1_str, osw1_cmd))
            # Two-OSW system idle
            elif osw1_cmd == 0x2f8 and osw2_ch_tx:
                type_str = "ANALOG" if osw2_grp else "DIGITAL"
                src_rid = osw2_addr
                grp_str = grp1_str
                data = osw1_addr
                vc_tx_freq = osw2_f_tx
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET OBT IDLE %s src(%05d) data(%s,0x%04x)" % (log_ts.get(), self.msgq_id, type_str, src_rid, grp_str, data))
                    if vc_tx_freq != 0.0:
                        sys.stderr.write(" vc_tx_freq(%f)" % (vc_tx_freq))
                    sys.stderr.write("\n")
            # Two-OSW group voice grant
            elif osw2_ch_tx and osw1_ch_rx and osw1_grp and (osw1_addr != 0) and (osw2_addr != 0):
                mode = 0 if osw2_grp else 1
                type_str = "ANALOG" if osw2_grp else "DIGITAL"
                src_rid = osw2_addr
                dst_tgid = osw1_addr
                vc_rx_freq = osw1_f_rx
                vc_tx_freq = osw2_f_tx
                rc |= self.update_voice_frequency(osw1_t, vc_rx_freq, dst_tgid, src_rid, mode=mode)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET OBT %s %s GROUP GRANT src(%05d) tgid(%05d/0x%03x) vc_rx_freq(%f)" % (log_ts.get(), self.msgq_id, type_str, self.get_call_options_str(dst_tgid), src_rid, dst_tgid, dst_tgid >> 4, vc_rx_freq))
                    if vc_tx_freq != 0.0:
                        sys.stderr.write(" vc_tx_freq(%f)" % (vc_tx_freq))
                    sys.stderr.write("\n")
            # Two-OSW private call voice grant/update (sent for duration of the call)
            elif osw2_ch_tx and osw1_ch_rx and not osw1_grp and (osw1_addr != 0) and (osw2_addr != 0):
                type_str = "ENCRYPTED" if osw2_grp else "CLEAR"
                dst_rid = osw2_addr
                src_rid = osw1_addr
                vc_rx_freq = osw1_f_rx
                vc_tx_freq = osw2_f_tx
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET OBT %s PRIVATE CALL src(%05d) dst(%05d) vc_rx_freq(%f)" % (log_ts.get(), self.msgq_id, type_str, src_rid, dst_rid, vc_rx_freq))
                    if vc_tx_freq != 0.0:
                        sys.stderr.write(" vc_tx_freq(%f)" % (vc_tx_freq))
                    sys.stderr.write("\n")
            # Two-OSW interconnect call voice grant/update (sent for duration of the call)
            elif osw2_ch_tx and osw1_ch_rx and not osw2_grp and not osw1_grp and (osw1_addr != 0) and (osw2_addr == 0):
                src_rid = osw1_addr
                vc_rx_freq = osw1_f_rx
                vc_tx_freq = osw2_f_tx
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET OBT INTERCONNECT CALL src(%05d) vc_rx_freq(%f)" % (log_ts.get(), self.msgq_id, src_rid, vc_rx_freq))
                    if vc_tx_freq != 0.0:
                        sys.stderr.write(" vc_tx_freq(%f)" % (vc_tx_freq))
                    sys.stderr.write("\n")
            else:
                # Track that we got an unknown OSW and put back unused OSW1
                is_unknown_osw = True
                self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t))

                if self.debug >= 11:
                    type_str = "UNKNOWN OSW AFTER BAD OSW" if is_queue_reset else "UNKNOWN OSW"
                    sys.stderr.write("%s [%d] SMARTNET OBT %s (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, type_str, osw2_addr, grp2_str, osw2_cmd))
        # One-OSW voice update
        elif osw2_ch_rx and osw2_grp:
            dst_tgid = osw2_addr
            vc_freq = osw2_f_rx
            rc |= self.update_voice_frequency(osw2_t, vc_freq, dst_tgid)
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
        # One-OSW group busy queued
        elif osw2_cmd == 0x300 and osw2_grp:
            tgid = osw2_addr
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET GROUP BUSY QUEUED tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, tgid, tgid >> 4))
        # One-OSW emergency busy queued
        elif osw2_cmd == 0x303 and osw2_grp:
            tgid = osw2_addr
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET EMERGENCY BUSY QUEUED tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, tgid, tgid >> 4))
        # Two- or three-OSW message
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
                rc |= self.update_voice_frequency(osw1_t, vc_freq, dst_tgid, src_rid, mode=0)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET ANALOG %s GROUP GRANT src(%05d) tgid(%05d/0x%03x) vc_freq(%f)\n" % (log_ts.get(), self.msgq_id, self.get_call_options_str(dst_tgid), src_rid, dst_tgid, dst_tgid >> 4, vc_freq))
            # Two-OSW analog private call voice grant/update (sent for duration of the call)
            elif osw1_ch_rx and not osw1_grp and (osw1_addr != 0) and (osw2_addr != 0):
                dst_rid = osw2_addr
                src_rid = osw1_addr
                vc_freq = osw1_f_rx
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET ANALOG PRIVATE CALL src(%05d) dst(%05d) vc_freq(%f)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_rid, vc_freq))
            # Two-OSW interconnect call voice grant/update (sent for duration of the call)
            elif osw1_ch_rx and not osw1_grp and (osw1_addr != 0) and (osw2_addr == 0):
                src_rid = osw1_addr
                vc_freq = osw1_f_rx
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET INTERCONNECT CALL src(%05d) vc_freq(%f)\n" % (log_ts.get(), self.msgq_id, src_rid, vc_freq))
            # One- or two-OSW system idle
            elif osw1_cmd == 0x2f8:
                # Get next OSW in the queue
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t = self.osw_q.popleft()
                grp0_str = self.get_group_str(osw0_grp)

                # Valid two-OSW system idle (next command is not the continuation of a two- or three-OSW message)
                if osw0_cmd not in [0x30a, 0x30b, 0x30d, 0x310, 0x311, 0x317, 0x318, 0x319, 0x31a, 0x320, 0x322, 0x32e, 0x340]:
                    # Put back unused OSW0
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t))

                    src_rid = osw2_addr
                    grp_str = grp1_str
                    data = osw1_addr
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET IDLE ANALOG src(%05d) data(%s,0x%04x)\n" % (log_ts.get(), self.msgq_id, src_rid, grp_str, data))
                # One-OSW system idle that was delayed by one OSW and is now stuck in the middle of a different two- or
                # three-OSW message.
                #
                # Example:
                #   [OSW A-1] [OSW A-2] [OSW B-1] [IDLE] [OSW B-2] [OSW C-1] [OSW C-2]
                #
                # Reorder it (process it after OSW A-2 and before OSW B-1) and put back the message it was inside to try
                # processing the message again.
                else:
                    # Put back unused OSW0 and OSW2
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t))
                    self.osw_q.appendleft((osw2_addr, osw2_grp, osw2_cmd, osw2_ch_rx, osw2_ch_tx, osw2_f_rx, osw2_f_tx, osw2_t))

                    grp_str = grp1_str
                    data = osw1_addr
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET IDLE DELAYED 1-1 data(%s,0x%04x)\n" % (log_ts.get(), self.msgq_id, grp_str, data))
            # Two-OSW group busy queued
            elif osw1_cmd == 0x300 and osw1_grp:
                src_rid = osw2_addr
                tgid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET GROUP BUSY QUEUED src(%05d) tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, src_rid, tgid, tgid >> 4))
            # Two-OSW private call busy queued
            elif osw1_cmd == 0x302 and not osw1_grp:
                src_rid = osw2_addr
                tgt_rid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET PRIVATE CALL BUSY QUEUED src(%05d) tgt(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid, tgt_rid))
            # Two-OSW emergency busy queued
            elif osw1_cmd == 0x303 and osw1_grp:
                src_rid = osw2_addr
                tgid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET EMERGENCY BUSY QUEUED src(%05d) tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, src_rid, tgid, tgid >> 4))
            # Possible out-of-order two-OSW system idle
            elif osw1_cmd == 0x308:
                # Get next OSW in the queue
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t = self.osw_q.popleft()
                grp0_str = self.get_group_str(osw0_grp)

                # Two-OSW system idle that got separated and interleaved with a different two- or three-OSW message.
                #
                # Example:
                #   [OSW A-1] [OSW A-2] [IDLE-1] [OSW B-1] [IDLE-2] [OSW B-2] [OSW C-1] [OSW C-2]
                #
                # Reorder it (process it after OSW A-2 and before OSW B-1) and put back the message that it was
                # interleaved with to try processing the message again in the next pass.
                if osw0_cmd == 0x2f8:
                    # Put back unused OSW1 (that this idle was interleaved with)
                    self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t))

                    src_rid = osw2_addr
                    grp_str = grp0_str
                    data = osw0_addr
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET IDLE INTERLEAVED src(%05d) data(%s,0x%04x)\n" % (log_ts.get(), self.msgq_id, src_rid, grp_str, data))
                # It's beyond repair, just mark it unknown
                else:
                    # Track that we got an unknown OSW and put back unused OSW0 and OSW1
                    is_unknown_osw = True
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t))
                    self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t))

                    if self.debug >= 11:
                        type_str = "UNKNOWN OSW AFTER BAD OSW" if is_queue_reset else "UNKNOWN OSW"
                        sys.stderr.write("%s [%d] SMARTNET %s (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, type_str, osw2_addr, grp2_str, osw2_cmd))
            # Two-OSW dynamic regroup
            elif osw1_cmd == 0x30a and not osw2_grp and not osw1_grp:
                src_rid = osw2_addr
                tgid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET DYNAMIC REGROUP src(%05d) tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, src_rid, tgid, tgid >> 4))
            # One of many possible two- or three-OSW meanings...
            elif osw1_cmd == 0x30b:
                # Get next OSW in the queue
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t = self.osw_q.popleft()
                grp0_str = self.get_group_str(osw0_grp)

                # One-OSW system idle that was delayed by two OSWs and is now stuck between the last two OSWs of a
                # of a different three-OSW message.
                #
                # Example:
                #   [OSW A-1] [OSW A-2] [OSW B-1] [OSW B-2] [IDLE] [OSW B-3] [OSW C-1] [OSW C-2]
                #
                # Reorder it (process it after OSW A-2 and before OSW B-1) and continue processing using the following
                # OSW.
                if osw0_cmd == 0x2f8 and not osw0_grp:
                    grp_str = grp0_str
                    data = osw0_addr
                    osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t = self.osw_q.popleft()
                    grp0_str = self.get_group_str(osw0_grp)
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET IDLE DELAYED 2-1 data(%s,0x%04x)\n" % (log_ts.get(), self.msgq_id, grp_str, data))

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
                        cc_chan = osw1_addr & 0x3ff
                        cc_rx_freq = self.get_freq(cc_chan)
                        cc_tx_freq = self.get_freq(cc_chan, is_tx=True)
                        self.rx_sys_id = system
                        if not osw1_grp:
                            self.add_alternate_cc_freq(osw1_t, cc_rx_freq, cc_tx_freq)
                        if self.debug >= 11:
                            sys.stderr.write("%s [%d] SMARTNET %s CONTROL CHANNEL sys(0x%04x) cc_freq(%f)\n" % (log_ts.get(), self.msgq_id, type_str, system, cc_rx_freq))
                    # Extended functions on groups
                    elif osw1_grp:
                        # Patch/multiselect cancel
                        if osw1_addr == 0x2021 and (self.is_patch_group(osw2_addr) or self.is_multiselect_group(osw2_addr)):
                            type_str = self.get_call_options_str(osw2_addr, include_clear=False)
                            tgid = osw2_addr & 0xfff0
                            rc |= self.delete_patches(tgid)
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET %s CANCEL tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, type_str, tgid, tgid >> 4))
                        # Unknown extended function
                        else:
                            tgid = osw2_addr
                            opcode = osw1_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET GROUP EXTENDED FUNCTION tgid(%05d/0x%03x) opcode(0x%04x)\n" % (log_ts.get(), self.msgq_id, tgid, tgid >> 4, opcode))
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
                        # Status acknowledgement
                        elif osw1_addr >= 0x26e0 and osw1_addr <= 0x26e7:
                            src_rid = osw2_addr
                            status = (osw1_addr & 0x7) + 1
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET STATUS ACK src(%05d) status(%01d)\n" % (log_ts.get(), self.msgq_id, src_rid, status))
                        # Emergency acknowledgement
                        elif osw1_addr == 0x26e8:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET EMERGENCY ALARM ACK src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Message acknowledgement
                        elif osw1_addr >= 0x26f0 and osw1_addr <= 0x26ff:
                            src_rid = osw2_addr
                            message = (osw0_addr & 0xf) + 1
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET MESSAGE ACK src(%05d) msg(%d)\n" % (log_ts.get(), self.msgq_id, src_rid, message))
                        # Invalid talkgroup (e.g. TGID 0xfff)
                        elif osw1_addr == 0x2c04:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED INVALID TALKGROUP src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Announcement listen only
                        elif osw1_addr == 0x2c11:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED ANNOUNCEMENT LISTEN ONLY src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Clear TX only
                        elif osw1_addr == 0x2c12:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED CLEAR TX ONLY src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Listen only
                        elif osw1_addr == 0x2c13:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED LISTEN ONLY src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # No private call
                        elif osw1_addr == 0x2c14:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED NO PRIVATE CALL src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Private call invalid ID
                        elif osw1_addr == 0x2c15:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED PRIVATE CALL INVALID ID src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # No interconnect
                        elif osw1_addr == 0x2c16:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED NO INTERCONNECT src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Unsupported mode (CVSD, digital)
                        elif osw1_addr == 0x2c20:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED UNSUPPORTED MODE src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Private call target offline
                        elif osw1_addr == 0x2c41:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED PRIVATE CALL TARGET OFFLINE src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Group busy (call in progress)
                        elif osw1_addr == 0x2c47:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED GROUP BUSY CALL IN PROGRESS src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Private call ring target offline
                        elif osw1_addr == 0x2c48:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED PRIVATE CALL RING TARGET OFFLINE src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Radio ID and/or talkgroup forbidden on site
                        elif osw1_addr == 0x2c4a:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED FORBIDDEN ON SITE src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Call alert invalid ID
                        elif osw1_addr == 0x2c4e:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED CALL ALERT INVALID ID src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Call alert target offline
                        elif osw1_addr == 0x2c4f:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED CALL ALERT TARGET OFFLINE src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Denied radio wrong modulation (e.g. radio digital, talkgroup analog)
                        elif osw1_addr == 0x2c56:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED RADIO WRONG MODULATION src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # OmniLink trespass rejected
                        elif osw1_addr == 0x2c60:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED OMNILINK TRESPASS src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Denied radio ID
                        elif osw1_addr == 0x2c65:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED RADIO ID src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Denied talkgroup ID
                        elif osw1_addr == 0x2c66:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED TALKGROUP ID src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Group busy (call is just starting)
                        elif osw1_addr == 0x2c90:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED GROUP BUSY CALL STARTING src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
                        # Private call target busy
                        elif osw1_addr == 0x2c96:
                            src_rid = osw2_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET DENIED PRIVATE CALL TARGET BUSY src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
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
                            opcode = osw1_addr
                            if self.debug >= 11:
                                sys.stderr.write("%s [%d] SMARTNET INDIVIDUAL EXTENDED FUNCTION src(%05d) opcode(0x%04x)\n" % (log_ts.get(), self.msgq_id, src_rid, opcode))
            # Two-OSW status / emergency / dynamic regroup acknowledgement
            elif osw1_cmd == 0x30d and not osw2_grp and not osw1_grp:
                src_rid = osw2_addr
                dst_tgid = osw1_addr & 0xfff0
                opcode = osw1_addr & 0xf
                if self.debug >= 11:
                    if opcode < 0x8:
                        status = opcode + 1
                        sys.stderr.write("%s [%d] SMARTNET STATUS src(%05d) tgid(%05d/0x%03x) status(%01d)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, dst_tgid >> 4, status))
                    elif opcode == 0x8:
                        sys.stderr.write("%s [%d] SMARTNET EMERGENCY ALARM src(%05d) tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, dst_tgid >> 4))
                    elif opcode == 0xa:
                        sys.stderr.write("%s [%d] SMARTNET DYNAMIC REGROUP ACK src(%05d) tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, dst_tgid >> 4))
                    else:
                        sys.stderr.write("%s [%d] SMARTNET UNKNOWN STATUS src(%05d) tgid(%05d/0x%03x) opcode(%02d)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, dst_tgid >> 4, opcode))
            # Two-OSW affiliation
            elif osw1_cmd == 0x310 and not osw2_grp and not osw1_grp:
                src_rid = osw2_addr
                dst_tgid = osw1_addr & 0xfff0
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET AFFILIATION src(%05d) tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, dst_tgid >> 4))
            # Two-OSW message
            elif osw1_cmd == 0x311 and not osw2_grp and not osw1_grp:
                src_rid = osw2_addr
                dst_tgid = osw1_addr & 0xfff0
                message = (osw1_addr & 0xf) + 1
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET MESSAGE src(%05d) tgid(%05d/0x%03x) msg(%02d)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, dst_tgid >> 4, message))
            # Two-OSW encrypted private call ring
            elif osw1_cmd == 0x315 and not osw2_grp and not osw1_grp:
                dst_rid = osw2_addr
                src_rid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET ANALOG ENCRYPTED PRIVATE CALL RING src(%05d) dst(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_rid))
            # Two-OSW clear private call ring
            elif osw1_cmd == 0x317 and not osw2_grp and not osw1_grp:
                dst_rid = osw2_addr
                src_rid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET ANALOG CLEAR PRIVATE CALL RING src(%05d) dst(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_rid))
            # Two-OSW private call ring acknowledgement
            elif osw1_cmd == 0x318 and not osw2_grp and not osw1_grp:
                dst_rid = osw2_addr
                src_rid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET PRIVATE CALL RING ACK src(%05d) dst(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_rid))
            # Two-OSW call alert
            elif osw1_cmd == 0x319 and not osw2_grp and not osw1_grp:
                dst_rid = osw2_addr
                src_rid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET CALL ALERT src(%05d) dst(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_rid))
            # Two-OSW call alert acknowledgement
            elif osw1_cmd == 0x31a and not osw2_grp and not osw1_grp:
                dst_rid = osw2_addr
                src_rid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET CALL ALERT ACK src(%05d) dst(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_rid))
            # Two-OSW OmniLink trespass permitted
            elif osw1_cmd == 0x31b and not osw2_grp and not osw1_grp:
                src_rid = osw2_addr
                system = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET OMNILINK TRESPASS PERMITTED sys(0x%04x) src(%05d)\n" % (log_ts.get(), self.msgq_id, system, src_rid))
            # Three-OSW system information
            elif osw1_cmd == 0x320:
                # Get OSW0
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t = self.osw_q.popleft()
                grp0_str = self.get_group_str(osw0_grp)

                # One-OSW system idle that was delayed by two OSWs and is now stuck between the last two OSWs of a
                # of a different three-OSW message.
                #
                # Example:
                #   [OSW A-1] [OSW A-2] [OSW B-1] [OSW B-2] [IDLE] [OSW B-3] [OSW C-1] [OSW C-2]
                #
                # Reorder it (process it after OSW A-2 and before OSW B-1) and continue processing using the following
                # OSW.
                if osw0_cmd == 0x2f8 and not osw0_grp:
                    grp_str = grp0_str
                    data = osw0_addr
                    osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t = self.osw_q.popleft()
                    grp0_str = self.get_group_str(osw0_grp)
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET IDLE DELAYED 2-2 data(%s,0x%04x)\n" % (log_ts.get(), self.msgq_id, grp_str, data))

                # The information returned here may be for this site, or may be for other adjacent sites
                if osw0_cmd == 0x30b and osw0_addr & 0xfc00 == 0x6000:
                    type_str = "ADJACENT SITE" if osw0_grp else "ALTERNATE CONTROL CHANNEL"
                    system = osw2_addr
                    # Sites are encoded as 0-indexed but usually referred to as 1-indexed
                    site = ((osw1_addr & 0xfc00) >> 10) + 1
                    band = (osw1_addr & 0x380) >> 7
                    feat = (osw1_addr & 0x3f)
                    cc_chan = osw0_addr & 0x03ff
                    cc_rx_freq = self.get_freq(cc_chan)
                    cc_tx_freq = self.get_freq(cc_chan, is_tx=True)
                    self.rx_sys_id = system
                    if osw0_grp:
                        self.add_adjacent_site(osw1_t, site, cc_rx_freq, cc_tx_freq)
                    else:
                        self.rx_site_id = site
                        self.add_alternate_cc_freq(osw1_t, cc_rx_freq, cc_tx_freq)
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET %s sys(0x%04x) site(%02d) band(%s) features(%s) cc_freq(%f)\n" % (log_ts.get(), self.msgq_id, type_str, system, site, self.get_band(band), self.get_features_str(feat), cc_rx_freq))
                else:
                    # Track that we got an unknown OSW and put back unused OSW0
                    is_unknown_osw = True
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t))

                    if self.debug >= 11:
                        ts = log_ts.get()
                        type_str = "UNKNOWN OSW AFTER BAD OSW" if is_queue_reset else "UNKNOWN OSW"
                        sys.stderr.write("%s [%d] SMARTNET %s (0x%04x,%s,0x%03x)\n" % (ts, self.msgq_id, type_str, osw2_addr, grp2_str, osw2_cmd))
                        sys.stderr.write("%s [%d] SMARTNET %s (0x%04x,%s,0x%03x)\n" % (ts, self.msgq_id, type_str, osw1_addr, grp1_str, osw1_cmd))
            # Two-OSW date/time
            elif osw1_cmd == 0x322 and osw2_grp and osw1_grp:
                year      = ((osw2_addr & 0xfe00) >> 9) + 2000
                month     = (osw2_addr & 0x1e0) >> 5
                day       = (osw2_addr & 0x1f)
                dayofweek = (osw1_addr & 0xe000) >> 13
                if dayofweek == 0:
                    dayofweek_str = "Sunday"
                elif dayofweek == 1:
                    dayofweek_str = "Monday"
                elif dayofweek == 2:
                    dayofweek_str = "Tuesday"
                elif dayofweek == 3:
                    dayofweek_str = "Wednesday"
                elif dayofweek == 4:
                    dayofweek_str = "Thursday"
                elif dayofweek == 5:
                    dayofweek_str = "Friday"
                elif dayofweek == 6:
                    dayofweek_str = "Saturday"
                else:
                    dayofweek_str = "unknown day of week"
                hour      = (osw1_addr & 0x1f00) >> 8
                minute    = osw1_addr & 0xff
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET DATE/TIME %04d-%02d-%02d %02d:%02d (%s)\n" % (log_ts.get(), self.msgq_id, year, month, day, hour, minute, dayofweek_str))
            # Two-OSW emergency PTT
            elif osw1_cmd == 0x32e and osw2_grp and osw1_grp:
                src_rid = osw2_addr
                dst_tgid = osw1_addr & 0xfff0
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET EMEREGENCY PTT src(%05d) tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_tgid, dst_tgid >> 4))
            # Two-OSW patch/multiselect
            elif osw1_cmd == 0x340 and osw2_grp and osw1_grp and (self.is_patch_group(osw2_addr) or self.is_multiselect_group(osw2_addr)):
                type_str = self.get_call_options_str(osw2_addr, include_clear=False)
                tgid = (osw1_addr & 0xfff) << 4
                sub_tgid = osw2_addr & 0xfff0
                mode = osw2_addr & 0xf
                rc |= self.add_patch(osw1_t, tgid, sub_tgid, mode)
                if self.debug >= 11:
                    if tgid == sub_tgid:
                        sys.stderr.write("%s [%d] SMARTNET %s tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, type_str, tgid, tgid >> 4))
                    else:
                        sys.stderr.write("%s [%d] SMARTNET %s tgid(%05d/0x%03x) sub_tgid(%05d/0x%03x)\n" % (log_ts.get(), self.msgq_id, type_str, tgid, tgid >> 4, sub_tgid, sub_tgid >> 4))
            else:
                # Track that we got an unknown OSW; OSW1 did not match, so put it back in the queue
                is_unknown_osw = True
                self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t))

                if self.debug >= 11:
                    type_str = "UNKNOWN OSW AFTER BAD OSW" if is_queue_reset else "UNKNOWN OSW"
                    sys.stderr.write("%s [%d] SMARTNET %s (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, type_str, osw2_addr, grp2_str, osw2_cmd))
        # Two-OSW message
        elif osw2_cmd == 0x321:
            # Get next OSW in the queue
            osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t = self.osw_q.popleft()
            grp1_str = self.get_group_str(osw1_grp)
            # Two-OSW digital group voice grant
            if osw1_ch_rx and osw2_grp and osw1_grp and (osw1_addr != 0):
                src_rid = osw2_addr
                dst_tgid = osw1_addr
                vc_freq = osw1_f_rx
                rc |= self.update_voice_frequency(osw1_t, vc_freq, dst_tgid, src_rid, mode=1)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET DIGITAL %s GROUP GRANT src(%05d) tgid(%05d/0x%03x) vc_freq(%f)\n" % (log_ts.get(), self.msgq_id, self.get_call_options_str(dst_tgid), src_rid, dst_tgid, dst_tgid >> 4, vc_freq))
            # Two-OSW digital private call voice grant/update (sent for duration of the call)
            elif osw1_ch_rx and not osw1_grp and (osw1_addr != 0) and (osw2_addr != 0):
                dst_rid = osw2_addr
                src_rid = osw1_addr
                vc_freq = osw1_f_rx
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET DIGITAL PRIVATE CALL src(%05d) dst(%05d) vc_freq(%f)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_rid, vc_freq))
            # One- or two-OSW system idle
            elif osw1_cmd == 0x2f8:
                # Get next OSW in the queue
                osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t = self.osw_q.popleft()
                grp0_str = self.get_group_str(osw0_grp)

                # Valid two-OSW system idle (next command is not a continuation)
                if osw0_cmd not in [0x317, 0x318]:
                    # Put back unused OSW0
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t))

                    src_rid = osw2_addr
                    grp_str = grp1_str
                    data = osw1_addr
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET IDLE DIGITAL src(%05d) data(%s,0x%04x)\n" % (log_ts.get(), self.msgq_id, src_rid, grp_str, data))
                # One-OSW system idle that was delayed by one OSW and is now stuck in the middle of a different two- or
                # three-OSW message.
                #
                # Example:
                #   [OSW A-1] [OSW A-2] [OSW B-1] [OSW B-2] [IDLE] [OSW B-3] [OSW C-1] [OSW C-2]
                #
                # Reorder it (process it after OSW A-2 and before OSW B-1) and put back the message it was inside to try
                # processing the message again.
                else:
                    # Put back unused OSW0 and OSW2
                    self.osw_q.appendleft((osw0_addr, osw0_grp, osw0_cmd, osw0_ch_rx, osw0_ch_tx, osw0_f_rx, osw0_f_tx, osw0_t))
                    self.osw_q.appendleft((osw2_addr, osw2_grp, osw2_cmd, osw2_ch_rx, osw2_ch_tx, osw2_f_rx, osw2_f_tx, osw2_t))

                    grp_str = grp1_str
                    data = osw1_addr
                    if self.debug >= 11:
                        sys.stderr.write("%s [%d] SMARTNET IDLE DELAYED 1-2 data(%s,0x%04x)\n" % (log_ts.get(), self.msgq_id, grp_str, data))
            # Two-OSW encrypted private call ring
            elif osw1_cmd == 0x315 and not osw2_grp and not osw1_grp:
                dst_rid = osw2_addr
                src_rid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET DIGITAL ENCRYPTED PRIVATE CALL RING src(%05d) dst(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_rid))
            # Two-OSW clear private call ring
            elif osw1_cmd == 0x317 and not osw2_grp and not osw1_grp:
                dst_rid = osw2_addr
                src_rid = osw1_addr
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET DIGITAL CLEAR PRIVATE CALL RING src(%05d) dst(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid, dst_rid))
            else:
                # Track that we got an unknown OSW; OSW1 did not match, so put it back in the queue
                is_unknown_osw = True
                self.osw_q.appendleft((osw1_addr, osw1_grp, osw1_cmd, osw1_ch_rx, osw1_ch_tx, osw1_f_rx, osw1_f_tx, osw1_t))

                if self.debug >= 11:
                    type_str = "UNKNOWN OSW AFTER BAD OSW" if is_queue_reset else "UNKNOWN OSW"
                    sys.stderr.write("%s [%d] SMARTNET %s (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, type_str, osw2_addr, grp2_str, osw2_cmd))
        # One-OSW interconnect reject
        elif osw2_cmd == 0x324 and not osw2_grp:
            src_rid = osw2_addr
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET INTERCONNECT REJECT src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
        # One-OSW send affiliation request
        elif osw2_cmd == 0x32a and osw2_grp:
            tgt_rid = osw2_addr
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET SEND AFFILIATION REQUEST tgt(%05d)\n" % (log_ts.get(), self.msgq_id, tgt_rid))
        # One-OSW system ID / scan marker
        elif osw2_cmd == 0x32b and not osw2_grp:
            system   = osw2_addr
            type_str = "II"
            self.rx_sys_id = system
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET SYSTEM sys(0x%04x) type(%s)\n" % (log_ts.get(), self.msgq_id, system, type_str))
        # One-OSW roaming
        elif osw2_cmd == 0x32c and not osw2_grp:
            src_rid = osw2_addr
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET ROAMING src(%05d)\n" % (log_ts.get(), self.msgq_id, src_rid))
        # One-OSW AMSS (Automatic Multiple Site Select) message
        elif osw2_cmd >= 0x360 and osw2_cmd <= 0x39f:
            # Sites are encoded as 0-indexed but usually referred to as 1-indexed
            site = osw2_cmd - 0x360 + 1
            if osw2_grp and (osw2_addr == 0x00000 or osw2_addr == 0xffff):
                data_str = ""
            else:
                # No idea what the data means if it's marked as individual, or group with a value
                data_str = " data(%s,0x%04x)" % (grp2_str, osw2_addr)
            self.rx_site_id = site
            if self.debug >= 11:
                sys.stderr.write("%s [%d] SMARTNET AMSS site(%02d)%s\n" % (log_ts.get(), self.msgq_id, site, data_str))
        # One-OSW BSI / diagnostic
        elif osw2_cmd == 0x3a0 and osw2_grp:
            # Note that this is still highly speculative - it seems correct for the values that are defined below, but
            # all other combinations are truly unknown
            opcode = (osw2_addr & 0xf000) >> 12

            if opcode == 0x8 or opcode == 0x9:
                status = (osw2_addr & 0xf00) >> 8
                if status == 0xa:
                    status_str = "enabled"
                elif status == 0xb:
                    status_str = "disabled"
                elif status == 0xc:
                    status_str = "malfunction"
                else:
                    status_str = "unknown 0x%01x" % (status)

                component = (osw2_addr & 0xff)
                if component >= 0x30 and component <= 0x4b:
                    component_str = "receiver %02d" % (component - 0x30 + 1)
                elif component >= 0x60 and component <= 0x7b:
                    component_str = "transmitter %02d" % (component - 0x60 + 1)
                else:
                    component_str = "unknown 0x%02x" % (component)

                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET DIAGNOSTIC STATUS opcode(0x%01x) component(%s) status(%s)\n" % (log_ts.get(), self.msgq_id, opcode, component_str, status_str))
            elif opcode == 0xe or opcode == 0xf:
                action_str = "BSI" if opcode == 0xf else "END BSI"
                if self.debug >= 11:
                    if self.is_chan(osw2_addr & 0x3ff):
                        data = (osw2_addr & 0xc00) >> 10
                        vc_freq = self.get_freq(osw2_addr & 0x3ff)
                        sys.stderr.write("%s [%d] SMARTNET %s data(0x%01x) vc_freq(%f)\n" % (log_ts.get(), self.msgq_id, action_str, data, vc_freq))
                    else:
                        data = osw2_addr & 0xfff
                        sys.stderr.write("%s [%d] SMARTNET %s data(0x%03x)\n" % (log_ts.get(), self.msgq_id, action_str, data, vc_freq))
            else:
                data = osw2_addr & 0x3ff
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET DIAGNOSTIC opcode(0x%01x) data(0x%03x)\n" % (log_ts.get(), self.msgq_id, opcode, data))
        # One-OSW system status update
        elif osw2_cmd == 0x3bf or osw2_cmd == 0x3c0:
            scope = "SYSTEM" if osw2_cmd == 0x3c0 else "NETWORK"
            opcode = (osw2_addr & 0xe000) >> 13
            data = osw2_addr & 0x1fff
            bitG = grp2_str
            if opcode == 1:
                type_ii              = (data & 0x1000) >> 12
                type_str             = "II" if type_ii else "I"
                dispatch_timeout     = (data & 0xe00) >> 9
                connect_tone         = (data & 0xe0) >> 5
                connect_tone_str     = self.get_connect_tone(connect_tone)
                interconnect_timeout = (data & 0x1f)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET %s STATUS type(%s) connect_tone(%.02f) dispatch_timeout(%d) interconnect_timeout(%d) bitG(%s)\n" % (log_ts.get(), self.msgq_id, scope, type_str, connect_tone_str, dispatch_timeout, interconnect_timeout, bitG))
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
                secure_str       = "none" if no_secure else ("upgraded" if secure_upgrade else "standard")
                data_str         = "none" if no_data else ("full" if full_data else "reduced")
                otar_str         = "reduced" if reduced_otar else "full"
                multikey_buf_str = "B" if multikey_buf_b else "A"
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET %s STATUS data(%s) secure(%s)" % (log_ts.get(), self.msgq_id, scope, data_str, secure_str))
                    # If we have secure enabled
                    if no_secure == 0:
                        # If we have data enabled
                        if no_data == 0:
                            sys.stderr.write(" otar(%s)" % (otar_str))
                        sys.stderr.write(" multikey_buf(%s) cvsd_echo_delay(%02d)" % (multikey_buf_str, cvsd_echo_delay))
                    sys.stderr.write(" bit6(%d) bit0(%d) bitG(%s)\n" % (bit6, bit0, bitG))
            elif opcode == 3:
                rotation     = (data & 0x800) >> 11
                wide_pulse   = (data & 0x400) >> 10
                cvsd_mod_4   = (data & 0x200) >> 9
                cvsd_mod_str = "4" if cvsd_mod_4 else "2"
                trespass     = (data & 0x100) >> 8
                voc          = (data & 0x80) >> 7
                bit6_5       = (data & 0x60) >> 5
                # Occurs immediately before and after voice grant on VOC
                voc_active   = (data & 0x10) >> 4
                bit3         = (data & 0x8) >> 3
                simulcast    = (data & 0x4) >> 2
                site_trunk   = (data & 0x2) >> 1
                bit0         = (data & 0x1)
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET %s STATUS rotation(%d) wide_pulse(%d) cvsd_mod(%s) trespass(%d) voc(%d)" % (log_ts.get(), self.msgq_id, scope, rotation, wide_pulse, cvsd_mod_str, trespass, voc))
                    if voc or voc_active:
                        sys.stderr.write(" voc_active(%d)" % (voc_active))
                    sys.stderr.write(" simulcast(%d) site_trunk(%d) bit6_5(0x%01x) bit3(%d) bit0(%d) bitG(%s)\n" % (simulcast, site_trunk, bit6_5, bit3, bit0, bitG))
            else:
                if self.debug >= 11:
                    sys.stderr.write("%s [%d] SMARTNET %s STATUS opcode(0x%x) data(0x%04x) bitG(%s)\n" % (log_ts.get(), self.msgq_id, scope, grp2_str, opcode, data, bitG))
        else:
            # Track that we got an unknown OSW
            is_unknown_osw = True
            if self.debug >= 11:
                type_str = "UNKNOWN OSW AFTER BAD OSW" if is_queue_reset else "UNKNOWN OSW"
                sys.stderr.write("%s [%d] SMARTNET %s (0x%04x,%s,0x%03x)\n" % (log_ts.get(), self.msgq_id, type_str, osw2_addr, grp2_str, osw2_cmd))

        # If we got an unknown OSW after a queue reset, put back the queue reset message so that we know the next
        # unknown OSW is likely caused by the queue reset as well
        if is_unknown_osw and is_queue_reset:
            self.osw_q.appendleft((queue_reset_addr, queue_reset_grp, queue_reset_cmd, queue_reset_ch_rx, queue_reset_ch_tx, queue_reset_f_rx, queue_reset_f_tx, queue_reset_t))

        return rc

    def update_voice_frequency(self, ts, float_freq, tgid=None, srcaddr=-1, mode=-1):
        if not float_freq:    # e.g., channel identifier not yet known
            return False

        frequency = int(float_freq * 1e6) # use integer not float as dictionary keys

        rc = self.update_talkgroups(ts, frequency, tgid, srcaddr, mode)

        base_tgid = tgid & 0xfff0
        flags     = tgid & 0x000f
        if frequency not in self.voice_frequencies:
            self.voice_frequencies[frequency] = {'counter':0}
            sorted_freqs = collections.OrderedDict(sorted(self.voice_frequencies.items()))
            self.voice_frequencies = sorted_freqs
            if self.debug >= 5:
                sys.stderr.write('%s [%d] new freq=%f\n' % (log_ts.get(), self.msgq_id, (frequency/1e6)))

        # If we get a valid mode, store it
        if mode != -1:
            self.voice_frequencies[frequency]['mode'] = mode
        # If the TG is already there and has not changed under us (or has not expired), leave it be
        elif (
            ('tgid' in self.voice_frequencies[frequency] and self.voice_frequencies[frequency]['tgid'] == base_tgid) or
            ('time' in self.voice_frequencies[frequency] and ts <= self.voice_frequencies[frequency]['time'] + TGID_EXPIRY_TIME)
        ):
            pass
        # Otherwise store the unknown state
        else:
            self.voice_frequencies[frequency]['mode'] = mode

        self.voice_frequencies[frequency]['tgid'] = base_tgid
        self.voice_frequencies[frequency]['flags'] = flags
        self.voice_frequencies[frequency]['counter'] += 1
        self.voice_frequencies[frequency]['time'] = ts
        return rc

    def update_talkgroups(self, ts, frequency, tgid, srcaddr, mode=-1):
        rc = self.update_talkgroup(ts, frequency, tgid, srcaddr, mode)
        if tgid in self.patches:
            for sub_tgid in self.patches[tgid]['sub_tgid']:
                self.update_talkgroup(ts, frequency, sub_tgid, srcaddr, mode)
                if self.debug >= 5:
                    sys.stderr.write('%s [%d] update_talkgroups: tgid(%d) patched sub_tgid(%d)\n' % (log_ts.get(), self.msgq_id, tgid, sub_tgid))
        return rc

    def update_talkgroup(self, ts, frequency, tgid, srcaddr, mode=-1):
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
        rc = False
        self.last_expiry_check = curr_time
        for tgid in self.talkgroups:
            if (self.talkgroups[tgid]['receiver'] is not None) and (curr_time >= self.talkgroups[tgid]['time'] + TGID_EXPIRY_TIME):
                if self.debug > 1:
                    sys.stderr.write("%s [%d] expiring tg(%d), freq(%f)\n" % (log_ts.get(), self.msgq_id, tgid, (self.talkgroups[tgid]['frequency']/1e6)))
                self.talkgroups[tgid]['receiver'].expire_talkgroup(reason="expiry")
                rc = True
        return rc

    def add_patch(self, ts, tgid, sub_tgid, mode):
        if tgid not in self.patches and sub_tgid != tgid:
            self.patches[tgid] = {}

        if sub_tgid != tgid:
            is_update = sub_tgid in self.patches[tgid]
            self.patches[tgid][sub_tgid] = {'time': ts, 'mode': mode}
            if self.debug >= 5:
                action_str = "updated" if is_update else "added"
                sys.stderr.write("%s [%d] add_patch: %s patch to tgid(%d) from sub_tgid(%d)\n" % (log_ts.get(), self.msgq_id, action_str, tgid, sub_tgid))

        return True

    def delete_patches(self, tgid):
        if tgid not in self.patches:
            return False

        del self.patches[tgid]
        if self.debug >= 5:
            sys.stderr.write("%s [%d] delete_patches: deleted all patches to tgid(%d)\n" % (log_ts.get(), self.msgq_id, tgid))

        return True

    def expire_patches(self, curr_time):
        deleted = 0
        for tgid in list(self.patches.keys()):
            for sub_tgid in list(self.patches[tgid].keys()):
                if curr_time > (self.patches[tgid][sub_tgid]['time'] + PATCH_EXPIRY_TIME):
                    deleted += 1
                    del self.patches[tgid][sub_tgid]
                    if self.debug >= 5:
                        sys.stderr.write("%s [%d] expire_patches: expired patch to tgid(%d) from sub_tgid(%d)\n" % (log_ts.get(), self.msgq_id, tgid, sub_tgid))
            if len(list(self.patches[tgid].keys())) == 0:
                del self.patches[tgid]
                if self.debug >= 5:
                    sys.stderr.write("%s [%d] expire_patches: expired all patches to tgid(%d)\n" % (log_ts.get(), self.msgq_id, tgid))

        return deleted

    def add_alternate_cc_freq(self, ts, cc_rx_freq, cc_tx_freq):
        cc_freq_key = int(cc_rx_freq * 1e6)
        is_update = cc_freq_key in self.alternate_cc_freqs
        self.alternate_cc_freqs[cc_freq_key] = {'time': ts, 'cc_rx_freq': cc_rx_freq, 'cc_tx_freq': cc_tx_freq}
        if self.debug >= 5:
            action_str = "updated" if is_update else "added"
            sys.stderr.write("%s [%d] add_alternate_cc_freq: %s alternate cc_freq(%f)\n" % (log_ts.get(), self.msgq_id, action_str, cc_rx_freq))
        return True

    def expire_alternate_cc_freqs(self, curr_time):
        for freq in list(self.alternate_cc_freqs.keys()):
            if curr_time > self.alternate_cc_freqs[freq]['time'] + ALT_CC_EXPIRY_TIME:
                del self.alternate_cc_freqs[freq]
                if self.debug >= 5:
                    sys.stderr.write("%s [%d] expire_alternate_cc_freqs: expired cc_freq(%f)\n" % (log_ts.get(), self.msgq_id, freq / 1e6))
        return True

    def add_adjacent_site(self, ts, site, cc_rx_freq, cc_tx_freq):
        is_update = site in self.adjacent_sites
        self.adjacent_sites[site] = {'time': ts, 'cc_rx_freq': cc_rx_freq, 'cc_tx_freq': cc_tx_freq}
        if self.debug >= 5:
            action_str = "updated" if is_update else "added"
            sys.stderr.write("%s [%d] add_adjacent_site: %s adjacent site(%d)\n" % (log_ts.get(), self.msgq_id, action_str, site))
        return True

    def expire_adjacent_sites(self, curr_time):
        for site in list(self.adjacent_sites.keys()):
            if curr_time > self.adjacent_sites[site]['time'] + ADJ_SITE_EXPIRY_TIME:
                del self.adjacent_sites[site]
                if self.debug >= 5:
                    sys.stderr.write("%s [%d] expire_adjacent_sites: expired site(%d)\n" % (log_ts.get(), self.msgq_id, site))
        return True

    def dump_tgids(self):
        sys.stderr.write("Known tgids: { ")
        for tgid in sorted(self.talkgroups.keys()):
            sys.stderr.write("%d " % tgid);
        sys.stderr.write("}\n")

    def to_json(self):  # ugly but required for compatibility with P25 trunking and terminal modules
        system_id_str = "%04X" % (self.rx_sys_id) if self.rx_sys_id is not None else "----"

        d = {}
        d['type']           = 'smartnet'
        d['system']         = self.sysname
        if self.rx_site_id is None:
            d['top_line']   = 'SmartNet    System ID %s         ' % (system_id_str)
        else:
            site_id_str     = "%02d" % (self.rx_site_id)
            d['top_line']   = 'SmartZone   System ID %s  Site %s' % (system_id_str, site_id_str)
        d['top_line']      += '   CC %f' % ((self.rx_cc_freq if self.rx_cc_freq is not None else self.cc_list[self.cc_index]) / 1e6)
        d['top_line']      += '   OSW count %d' % (self.stats['osw_count'])
        d['secondary']      = list(self.alternate_cc_freqs.keys())
        d['frequencies']    = {}
        d['frequency_data'] = {}
        d['patch_data']     = {}
        d['adjacent_data']  = {}
        d['last_tsbk']      = self.last_osw

        t = time.time()

        # Get all current frequencies we know about (CC, alternate CC, VC)
        all_freqs = list(self.voice_frequencies.keys()) + list(self.alternate_cc_freqs.keys())
        if self.rx_cc_freq != None:
            all_freqs += [int(self.rx_cc_freq)]

        self.expire_talkgroups(t)
        for f in all_freqs:
            # Type-specific parameters
            time_ago = None
            count = 0
            if f in self.voice_frequencies:
                chan_type = "voice"
                time_ago = t - self.voice_frequencies[f]['time']
                count = self.voice_frequencies[f]['counter']
            if f in self.alternate_cc_freqs:
                chan_type = "alternate"
            if f == self.rx_cc_freq:
                chan_type = "control"
                time_ago = t - self.last_osw

            # Show time in appropriate units based on how long ago - useful for some high-capacity/low-traffic sites
            tgids = []
            if time_ago == None:
                time_ago_str = "Never"
            elif time_ago < TGID_EXPIRY_TIME:
                time_ago_str = "  Now"
                # Only show TGID if we believe the call is currently ongoing
                if f in self.voice_frequencies:
                    tgids = ["0x%03x" % (self.voice_frequencies[f]['tgid'] >> 4), "%5d" % (self.voice_frequencies[f]['tgid'])]
            elif time_ago < (60.0):
                time_ago_str = "%4.1fs" % (time_ago)
            elif time_ago < (60.0 * 60.0):
                time_ago_str = "%4.1fm" % (time_ago / 60.0)
            elif time_ago < (60.0 * 60.0 * 24.0):
                time_ago_str = "%4.1fh" % (time_ago / 60.0 / 60.0)
            else:
                time_ago_str = "%4.1fd" % (time_ago / 60.0 / 60.0 / 24.0)

            # Format here to show in theses console viewer
            time_ago_ncurses_str = time_ago_str + " ago" if time_ago_str != "Never" and time_ago_str != "  Now" else time_ago_str + "    "

            mode_str_web = ""
            if chan_type == "control":
                d['frequencies'][f] = '- %f       [----- CC -----][--------]  %s' % ((f / 1e6), time_ago_ncurses_str)
            elif chan_type == "alternate" and len(tgids) == 0:
                d['frequencies'][f] = '- %f  tgid [              ][ Alt CC ]  %s  count %d' % ((f / 1e6), time_ago_ncurses_str, count)
            elif len(tgids) != 0:
                mode_str = (self.get_call_options_flags_str(self.voice_frequencies[f]['flags'], self.voice_frequencies[f]['mode']) + "        ")[:8]
                mode_str_web = self.get_call_options_flags_web_str(self.voice_frequencies[f]['flags'], self.voice_frequencies[f]['mode'])
                d['frequencies'][f] = '- %f  tgid [ %s  %s ][%s]  %s  count %d' % ((f / 1e6), tgids[1], tgids[0], mode_str, time_ago_ncurses_str, count)
            else:
                d['frequencies'][f] = '- %f  tgid [              ][        ]  %s  count %d' % ((f / 1e6), time_ago_ncurses_str, count)

            # The easy part: send pure JSON and let the display layer handle formatting
            d['frequency_data'][f] = {'type': chan_type, 'tgids': tgids, 'last_activity': time_ago_str, 'counter': count, 'mode': mode_str_web}

        # Patches
        self.expire_patches(t)
        for tgid in sorted(self.patches.keys()):
            d['patch_data'][tgid] = {}
            for sub_tgid in sorted(self.patches[tgid].keys()):
                tgid_dec = "%5d" % (tgid)
                tgid_hex = "0x%03x" % (tgid >> 4)
                sub_tgid_dec = "%5d" % (sub_tgid)
                sub_tgid_hex = "0x%03x" % (sub_tgid >> 4)
                mode = self.get_call_options_flags_str(self.patches[tgid][sub_tgid]['mode'])
                d['patch_data'][tgid][sub_tgid] = {'tgid_dec': tgid_dec, 'tgid_hex': tgid_hex, 'sub_tgid_dec': sub_tgid_dec, 'sub_tgid_hex': sub_tgid_hex, 'mode': mode.strip()}

        # Adjacent sites
        self.expire_adjacent_sites(t)
        for site in sorted(self.adjacent_sites.keys()):
            # Use integers in data we send up to the display layer
            cc_rx_freq = int(self.adjacent_sites[site]['cc_rx_freq'] * 1e6)
            cc_tx_freq = int(self.adjacent_sites[site]['cc_tx_freq'] * 1e6)
            d['adjacent_data'][cc_rx_freq] = {'stid': site, 'uplink': cc_tx_freq}

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
