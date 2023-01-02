# P25 trunking module
#
# Copyright 2020, 2021 Graham J. Norbury - gnorbury@bondcar.com
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
import codecs
import ast
from helper_funcs import *
from log_ts import log_ts
from gnuradio import gr
import gnuradio.op25_repeater as op25_repeater

#################

CC_TIMEOUT_RETRIES = 3   # Number of control channel framing timeouts before hunting
VC_TIMEOUT_RETRIES = 3   # Number of voice channel framing timeouts before expiry
TGID_DEFAULT_PRIO = 3    # Default tgid priority when unassigned
TGID_HOLD_TIME = 2.0     # Number of seconds to give previously active tgid exclusive channel access
TGID_SKIP_TIME = 4.0     # Number of seconds to blacklist a previously skipped tgid
TGID_EXPIRY_TIME = 1.0   # Number of seconds to allow tgid to remain active with no updates received
FREQ_EXPIRY_TIME = 1.2   # Number of seconds to allow freq to remain active with no updates received
EXPIRY_TIMER = 0.2       # Number of seconds between checks for tgid/freq expiry
PATCH_EXPIRY_TIME = 20.0 # Number of seconds until patch expiry

#################
# Helper functions

def meta_update(meta_q, tgid = None, tag = None, msgq_id = 0, ts = time.time()):
    if meta_q is None:
        return
    d = {'json_type': 'meta_update'}
    d['tgid'] = tgid
    d['tag'] = tag
    msg = op25_repeater.message().make_from_string(json.dumps(d), -2, ts, 0)
    meta_q.insert_tail(msg)

def add_default_tgid(tgs, tgid):
    if tgs is None:
        return
    if tgid not in tgs:
        tgs[tgid] = {'counter':0}
        tgs[tgid]['tgid'] = tgid
        tgs[tgid]['prio'] = TGID_DEFAULT_PRIO
        tgs[tgid]['tag'] = ""
        tgs[tgid]['srcaddr'] = 0
        tgs[tgid]['time'] = 0
        tgs[tgid]['frequency'] = None
        tgs[tgid]['tdma_slot'] = None
        tgs[tgid]['encrypted'] = 0
        tgs[tgid]['algid'] = -1
        tgs[tgid]['keyid'] = -1
        tgs[tgid]['receiver'] = None

def add_default_rid(srcids, rid):
    if srcids is None:
        return
    if rid not in srcids:
        srcids[rid] = {'counter':0}
        srcids[rid]['rid'] = rid
        srcids[rid]['tag'] = ""
        srcids[rid]['time'] = 0
        srcids[rid]['tgs'] = {}

def get_slot(slot):
    if slot is not None:
        return str(slot)
    else:
        return "-"

def get_tgid(tgid):
    if tgid is not None:
        return str(tgid)
    else:
        return ""

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
                self.systems[sysname] = { 'system': None, 'receivers': [] }
                self.systems[sysname]['system'] = p25_system(debug  = self.debug,
                                                             config = chan)

    # add_receiver is called once per radio channel defined in cfg.json
    def add_receiver(self, msgq_id, config, meta_q = None, freq = 0):
        if msgq_id in self.receivers: # should be impossible
            return

        rx_sys  = None
        rx_rcvr = None
        rx_name = from_dict(config, 'name', str(msgq_id))
        rx_sysname = from_dict(config, 'trunking_sysname', "undefined")

        if rx_sysname in self.systems:   # known trunking system
            rx_sys  = from_dict(self.systems[rx_sysname], 'system', None)
            rx_rcvr = p25_receiver(debug         = self.debug,
                                   msgq_id       = msgq_id,
                                   frequency_set = self.frequency_set,
                                   nac_set       = self.nac_set,
                                   slot_set      = self.slot_set,
                                   system        = rx_sys,
                                   config        = config,
                                   meta_q        = meta_q,
                                   freq          = freq)
            self.systems[rx_sysname]['receivers'].append(rx_rcvr)
        else:                            # undefined or mis-configured trunking sysname
            sys.stderr.write("Receiver '%s' configured with unknown trunking_sysname '%s'\n" % (rx_name, rx_sysname))

        self.receivers[msgq_id] = {'msgq_id': msgq_id,
                                   'config' : config,
                                   'sysname': rx_sysname,
                                   'rx_rcvr': rx_rcvr}

    # post_init is called once after all receivers have been created
    def post_init(self):
        for rx in self.receivers:
            if self.receivers[rx]['rx_rcvr'] is not None:
                if self.debug >= 10:
                    sys.stderr.write("%s [rx_ctl] post initialize receiver[%d]\n" % (log_ts.get(), rx))
                self.receivers[rx]['rx_rcvr'].post_init()
        if self.debug >= 10:
            sys.stderr.write("%s [rx_ctl] post initialize check control channel assignments\n" % (log_ts.get()))
        self.check_cc_assignments()

    # process_qmsg is the main message dispatch handler connecting the 'radios' to python
    def process_qmsg(self, msg):
        curr_time = time.time()
        m_proto = ctypes.c_int16(msg.type() >> 16).value    # upper 16 bits of msg.type() is signed protocol
        if m_proto != 0: # P25 m_proto=0
            return

        m_type = ctypes.c_int16(msg.type() & 0xffff).value  # lower 16 bits is p25 duid
        m_rxid = int(msg.arg1()) >> 1                       # receiver's msgq_id
        m_ts = float(msg.arg2())                            # receive timestamp from frame_assembler

        updated = 0
        if m_rxid in self.receivers and self.receivers[m_rxid]['rx_rcvr'] is not None:
            if m_type in [7, 12, 18, 19]:                                                   # send signaling messages to p25_system object
                updated += self.systems[self.receivers[m_rxid]['sysname']]['system'].process_qmsg(msg, curr_time)
            else:
                updated += self.receivers[m_rxid]['rx_rcvr'].process_qmsg(msg, curr_time)   # send in-call messaging to p25_receiver objects

            if updated > 0:
                # Check for voice receiver assignments
                for rx in self.systems[self.receivers[m_rxid]['sysname']]['receivers']:
                    rx.scan_for_talkgroups(curr_time)

                # Check for control channel reassignment
                self.check_cc_assignments()

    # Check for control channel assignments to idle receivers
    def check_cc_assignments(self):
        for p25_sysname in self.systems:
            p25_system = self.systems[p25_sysname]['system']
            if p25_system.cc_msgq_id is None:
                if self.debug >= 10:
                    sys.stderr.write("%s [%s] needs control channel receiver\n" % (log_ts.get(), p25_sysname))
                for rx in self.systems[p25_sysname]['receivers']:
                    if rx.tuner_idle:
                        if self.debug >= 10:
                            sys.stderr.write("%s [%s] attempt to assign control channel receiver[%d]\n" % (log_ts.get(), p25_sysname, rx.msgq_id))
                        rx.tune_cc(p25_system.get_cc(rx.msgq_id))
                        break
                    else:
                        if self.debug >= 10:
                            sys.stderr.write("%s [%s] receiver[%d] not idle\n" % (log_ts.get(), p25_sysname, rx.msgq_id))
            if p25_system.cc_msgq_id is None: # no receivers assigned
                if self.debug >= 5:
                    sys.stderr.write("%s [%s] has no idle receivers for control channel monitoring\n" % (log_ts.get(), p25_sysname))

    # ui_command handles all requests from user interface
    def ui_command(self, cmd, data, msgq_id):
        curr_time = time.time()
        if msgq_id in self.receivers and self.receivers[msgq_id]['rx_rcvr'] is not None:
            self.receivers[msgq_id]['rx_rcvr'].ui_command(cmd = cmd, data = data, curr_time = curr_time)    # Dispatch message to the intended receiver
        # Check for control channel reassignment
        self.check_cc_assignments()

    def to_json(self):
        d = {'json_type': 'trunk_update'}
        syid = 0;
        for system in self.systems:
            d[syid] = json.loads(self.systems[system]['system'].to_json())
            syid += 1
        d['nac'] = 0
        return json.dumps(d)

    def dump_tgids(self):
        for system in self.systems:
            self.systems[system]['system'].dump_tgids()
            self.systems[system]['system'].dump_rids()
            self.systems[system]['system'].sourceid_history.dump()

    def get_chan_status(self):
        d = {'json_type': 'channel_update'}
        rcvr_ids = []
        for rcvr in self.receivers:
            if self.receivers[rcvr]['rx_rcvr'] is not None:
                rcvr_name = from_dict(self.receivers[rcvr]['config'], 'name', "")
                d[str(rcvr)] = json.loads(self.receivers[rcvr]['rx_rcvr'].get_status())
                d[str(rcvr)]['name'] = rcvr_name
                rcvr_ids.append(str(rcvr))
        d['channels'] = rcvr_ids
        return json.dumps(d)

    def set_debug(self, dbglvl):
        self.debug = dbglvl
        for rx_sys in self.systems:
            self.systems[rx_sys]['system'].set_debug(dbglvl)
        for rcvr in self.receivers:
            self.receivers[rcvr]['rx_rcvr'].set_debug(dbglvl)

#################
# P25 system class
class p25_system(object):
    def __init__(self, debug, config):
        self.config = config
        self.debug = debug
        self.freq_table = {}
        self.voice_frequencies = {}
        self.talkgroups = {}
        self.sourceids = {}
        self.sourceid_history = rid_history(self.sourceids, 10)
        self.patches = {}
        self.blacklist = {}
        self.whitelist = None
        self.crypt_behavior = 1
        self.crypt_keys = {}
        self.cc_rate = 4800
        self.cc_list = []
        self.cc_index = -1
        self.cc_timeouts = 0
        self.cc_msgq_id = None
        self.last_tsbk = 0.0
        self.secondary = {}
        self.adjacent = {}
        self.adjacent_data = {}
        self.rfss_syid = 0
        self.rfss_rfid = 0
        self.rfss_stid = 0
        self.rfss_chan = 0
        self.rfss_txchan = 0
        self.ns_syid = 0
        self.ns_wacn = 0
        self.ns_chan = 0
        self.ns_valid = False
        self.rx_cc_freq = None
        self.rx_sys_id = None
        self.sysname = config['sysname']
        self.nac = int(ast.literal_eval(from_dict(config, "nac", "0")))
        self.last_expiry_check = 0.0
        self.stats = {}
        self.stats['tsbk_count'] = 0

        sys.stderr.write("%s [%s] Initializing P25 system\n" % (log_ts.get(), self.sysname))

        if 'tgid_tags_file' in self.config and self.config['tgid_tags_file'] != "":
            sys.stderr.write("%s [%s] reading system tgid_tags_file: %s\n" % (log_ts.get(), self.sysname, self.config['tgid_tags_file']))
            self.read_tags_file(self.config['tgid_tags_file'])

        if 'rid_tags_file' in self.config and self.config['rid_tags_file'] != "":
            sys.stderr.write("%s [%s] reading system rid_tags_file: %s\n" % (log_ts.get(), self.sysname, self.config['rid_tags_file']))
            self.read_rids_file(self.config['rid_tags_file'])

        if 'blacklist' in self.config and self.config['blacklist'] != "":
            sys.stderr.write("%s [%s] reading system blacklist file: %s\n" % (log_ts.get(), self.sysname, self.config['blacklist']))
            self.blacklist = get_int_dict(self.config['blacklist'], self.sysname)

        if 'whitelist' in self.config and self.config['whitelist'] != "":
            sys.stderr.write("%s [%s] reading system whitelist file: %s\n" % (log_ts.get(), self.sysname, self.config['whitelist']))
            self.whitelist = get_int_dict(self.config['whitelist'], self.sysname)

        self.tdma_cc = bool(from_dict(self.config, 'tdma_cc', False)) 
        if self.tdma_cc:
            self.cc_rate = 6000

        self.crypt_behavior = int(from_dict(self.config, 'crypt_behavior', 1))
        #if 'crypt_keys' in self.config and self.config['crypt_keys'] != "":
        #    sys.stderr.write("%s [%s] reading system crypt_keys file: %s\n" % (log_ts.get(), self.sysname, self.config['crypt_keys']))
        #    self.crypt_keys = get_key_dict(self.config['crypt_keys'], self.sysname)

        cc_list = from_dict(self.config, 'control_channel_list', "")
        if cc_list == "":
            sys.stderr.write("Aborting. P25 Trunking 'control_channel_list' parameter is empty or not found\n")
            sys.exit(1)

        for f in cc_list.split(','):
            self.cc_list.append(get_frequency(f))
        self.next_cc()

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
    
    def get_crypt_behavior(self):
        return self.crypt_behavior
    
    def get_tdma_params(self):
        return self.nac, self.ns_wacn, self.ns_syid, self.ns_valid

    def get_tdma_slot(self, id):
        table = (id >> 12) & 0xf
        channel = id & 0xfff
        if table not in self.freq_table:
            return None
        if 'tdma' not in self.freq_table[table]:
            return None
        if self.freq_table[table]['tdma'] < 2:
            return None
        return channel & 1 #TODO: won't work with more than 2 slots per channel

    def channel_id_to_frequency(self, id):
        table = (id >> 12) & 0xf
        channel = id & 0xfff
        if table not in self.freq_table:
            return None
        if 'tdma' not in self.freq_table[table]:
            return self.freq_table[table]['frequency'] + self.freq_table[table]['step'] * channel
        return self.freq_table[table]['frequency'] + self.freq_table[table]['step'] * int(channel / self.freq_table[table]['tdma'])

    def channel_id_to_string(self, id):
        f = self.channel_id_to_frequency(id)
        if f is None:
            return "ID-0x%x" % (id)
        return "%f" % (f / 1000000.0)

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
                        sys.stderr.write("read_tags_file: exception %s\n" % ex)
                        continue
                    if len(row) >= 3:
                        try:
                            prio = int(row[2])
                        except ValueError as ex:
                            prio = TGID_DEFAULT_PRIO
                    else:
                        prio = TGID_DEFAULT_PRIO

                    if tgid not in self.talkgroups:
                        add_default_tgid(self.talkgroups, tgid)
                    self.talkgroups[tgid]['tag'] = tag
                    self.talkgroups[tgid]['prio'] = prio
                    if self.debug > 1:
                        sys.stderr.write("%s [%s] setting tgid(%d), prio(%d), tag(%s)\n" % (log_ts.get(), self.sysname, tgid, prio, tag))
        except (IOError) as ex:
            sys.stderr.write("read_tags_file: exception %s\n" % ex)

    def read_rids_file(self, tags_file):
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
                        rid = int(row[0])
                        tag = utf_ascii(row[1])
                    except (IndexError, ValueError) as ex:
                        sys.stderr.write("read_rid_file: exception %s\n" % ex)
                        sys.stderr.write("row: %s\n" % row)
                        continue

                    if rid not in self.sourceids:
                        add_default_rid(self.sourceids, rid)
                    self.sourceids[rid]['tag'] = tag
                    if self.debug > 1:
                        sys.stderr.write("%s [%s] setting rid(%d), tag(%s)\n" % (log_ts.get(), self.sysname, rid, tag))
        except (IOError) as ex:
            sys.stderr.write("read_rid_file: exception %s\n" % ex)

    def get_cc(self, msgq_id):
        if msgq_id is None:
            return None

        if (self.cc_msgq_id is None) or (msgq_id == self.cc_msgq_id):
            self.cc_msgq_id = msgq_id
            if self.debug > 10:
                sys.stderr.write("%s [%s] Assigning control channel to receiver[%d]\n" % (log_ts.get(), self.sysname, msgq_id))

            assert self.cc_list[self.cc_index]
            return self.cc_list[self.cc_index]
        else:
            return None 

    def next_cc(self):
        self.cc_retries = 0
        self.cc_index += 1
        if self.cc_index >= len(self.cc_list):
            self.cc_index = 0

    def release_cc(self, msgq_id):
        if msgq_id is None or self.cc_msgq_id is None:
            return

        if self.cc_msgq_id == msgq_id:
            self.cc_msgq_id = None
            if self.debug > 10:
                sys.stderr.write("%s [%s] Releasing control channel from receiver[%d]\n" % (log_ts.get(), self.sysname, msgq_id))


    def has_cc(self, msgq_id):
        if msgq_id is None or msgq_id != self.cc_msgq_id:
            return False
        else:
            return True

    def valid_cc(self, msgq_id):
        if msgq_id is None or self.cc_msgq_id is None or msgq_id != self.cc_msgq_id:
            return False;
        self.cc_retries = 0
        return True

    def timeout_cc(self, msgq_id):
        if msgq_id is None or self.cc_msgq_id is None or msgq_id != self.cc_msgq_id:
            return False;
        self.cc_retries += 1
        if self.cc_retries >= CC_TIMEOUT_RETRIES:
            self.next_cc()
        return self.get_cc(msgq_id)

    def sync_cc(self):
        self.cc_retries = 0

    def get_nac(self):
        return self.nac

    def set_nac(self, nac):
        if (nac is None) or (nac == 0) or (nac == 0xffff) or ((self.nac !=0) and (nac != self.nac)):
            return False
        self.nac = nac
        return True

    def process_qmsg(self, msg, curr_time):
        s = msg.to_string()
        m_rxid = int(msg.arg1()) >> 1                       # receiver's msgq_id
        m_type = ctypes.c_int16(msg.type() & 0xffff).value  # lower 16 bits is p25 duid
        nac = get_ordinals(s[:2])                           # first two bytes are NAC
        self.set_nac(nac)

        updated = 0
        if m_type == 7:                                     # TSBK
            t = get_ordinals(s)
            updated += self.decode_tsbk(m_rxid, t)

        elif m_type == 12:                                  # MBT
            s1 = s[:10]     # header without crc
            s2 = s[12:]
            header = get_ordinals(s1)
            mbt_data = get_ordinals(s2)

            fmt = (header >> 72) & 0x1f
            sap = (header >> 64) & 0x3f
            src = (header >> 32) & 0xffffff
            if fmt != 0x17: # only Extended Format MBT presently supported
                return updated
            opcode = (header >> 16) & 0x3f
            updated += self.decode_mbt(m_rxid, opcode, src, header << 16, mbt_data << 32)

        elif m_type == 18:                                  # TDMA PDU
            updated += self.decode_tdma_msg(m_rxid, s[2:], curr_time)

        elif m_type == 19:                                  # FDMA LCW
            updated += self.decode_fdma_lcw(m_rxid, s[2:], curr_time)

        updated += self.expire_patches()
        return updated

    def decode_mbt_data(self, m_rxid, opcode, src, header, mbt_data):
        self.cc_timeouts = 0
        self.last_tsbk = time.time()
        self.stats['tsbk_count'] += 1
        updated = 0
        if opcode == 0x0:  # grp voice channel grant
            ch1  = (mbt_data >> 64) & 0xffff
            ch2  = (mbt_data >> 48) & 0xffff
            ga   = (mbt_data >> 32) & 0xffff
            f = self.channel_id_to_frequency(ch1)
            self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1), srcaddr=src)
            if f:
                updated += 1
            if self.debug >= 10:
                sys.stderr.write('%s [%d] mbt(0x00) grp_v_ch__grant: ch1: %x ch2: %x ga: %d\n' %(log_ts.get(), m_rxid, ch1, ch2, ga))
        elif opcode == 0x02: # grp regroup voice channel grant
            mfrid  = (mbt_data >> 168) & 0xff
            if mfrid == 0x90:    # MOT_GRG_CN_GRANT_EXP
                ch1  = (mbt_data >> 80) & 0xffff
                ch2  = (mbt_data >> 64) & 0xffff
                sg   = (mbt_data >> 48) & 0xffff
                f = self.channel_id_to_frequency(ch1)
                self.update_voice_frequency(f, tgid=sg, tdma_slot=self.get_tdma_slot(ch1), srcaddr=src)
                if f:
                    updated += 1
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] mbt(0x02) mfid90_grg_cn_grant_exp: ch1: %x ch2: %x sg: %d\n' % (log_ts.get(), m_rxid, ch1, ch2, ga))
        elif opcode == 0x28:  # grp_aff_rsp
            ta    = src
            mfrid = (header >> 56) & 0xff
            wacn  = ((header << 4) & 0xffff0) + ((mbt_data >> 188) & 0xf) 
            syid  = (mbt_data >> 176) & 0xfff
            gid   = (mbt_data >> 160) & 0xffff
            aga   = (mbt_data >> 144) & 0xffff
            ga    = (mbt_data >> 128) & 0xffff
            lg    = (mbt_data >> 127) & 0x1
            gav   = (mbt_data >> 120) & 0x3
            if self.debug >= 10:
                sys.stderr.write('%s [%d] mbt(0x28) grp_aff_rsp: mfrid: 0x%x wacn: 0x%x syid: 0x%x lg: %d gav: %d aga: %d ga: %d ta: %d\n\n' %(log_ts.get(), m_rxid, mfrid, wacn, syid, lg, gav, aga, ga, ta))
        elif opcode == 0x3c:  # adjacent status
            syid = (header >> 48) & 0xfff
            rfid = (header >> 24) & 0xff
            stid = (header >> 16) & 0xff
            ch1  = (mbt_data >> 80) & 0xffff
            ch2  = (mbt_data >> 64) & 0xffff
            f1 = self.channel_id_to_frequency(ch1)
            f2 = self.channel_id_to_frequency(ch2)
            if f1 and f2:
                self.adjacent[f1] = 'rfid: %d stid:%d uplink:%f' % (rfid, stid, f2 / 1000000.0)
                self.adjacent_data[f1] = {'rfid': rfid, 'stid':stid, 'uplink': f2, 'table': None}
            if self.debug >= 10:
                sys.stderr.write('%s [%d] mbt(0x3c) adj_sts_bcst: syid: %x rfid: %x stid: %x ch1: %x ch2: %x f1: %s f2: %s\n' % (log_ts.get(), m_rxid, syid, rfid, stid, ch1, ch2, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
        elif opcode == 0x3b:  # network status
            syid = (header >> 48) & 0xfff
            wacn = (mbt_data >> 76) & 0xfffff
            ch1  = (mbt_data >> 56) & 0xffff
            ch2  = (mbt_data >> 40) & 0xffff
            f1 = self.channel_id_to_frequency(ch1)
            f2 = self.channel_id_to_frequency(ch2)
            if f1 and f2:
                self.ns_syid = syid
                self.ns_wacn = wacn
                self.ns_chan = f1
                self.ns_valid = True
            if self.debug >= 10:
                sys.stderr.write('%s [%d] mbt(0x3b) net_sts_bcst: sys: %x wacn: %x ch1: %s ch2: %s\n' %(log_ts.get(), m_rxid, syid, wacn, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
        elif opcode == 0x3a:  # rfss status
            syid = (header >> 48) & 0xfff
            rfid = (mbt_data >> 88) & 0xff
            stid = (mbt_data >> 80) & 0xff
            ch1  = (mbt_data >> 64) & 0xffff
            ch2  = (mbt_data >> 48) & 0xffff
            f1 = self.channel_id_to_frequency(ch1)
            f2 = self.channel_id_to_frequency(ch2)
            if f1 and f2:
                self.rfss_syid = syid
                self.rfss_rfid = rfid
                self.rfss_stid = stid
                self.rfss_chan = f1
                self.rfss_txchan = f2
                add_unique_freq(self.cc_list, f1)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] mbt(0x3a) rfss_sts_bcst: sys: %x rfid: %x stid: %x ch1: %s ch2: %s\n' %(log_ts.get(), m_rxid, syid, rfid, stid, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
        else:
            if self.debug >= 10:
                sys.stderr.write('%s [%d] mbt(0x%02x) unhandled: %x\n' %(log_ts.get(), m_rxid, opcode, mbt_data))
        return updated

    def decode_tsbk(self, m_rxid, tsbk):
        self.cc_timeouts = 0
        self.last_tsbk = time.time()
        self.stats['tsbk_count'] += 1
        updated = 0
        tsbk = tsbk << 16    # for missing crc
        opcode = (tsbk >> 88) & 0x3f
        if opcode == 0x00:   # group voice chan grant
            mfrid  = (tsbk >> 80) & 0xff
            if mfrid == 0x90:    # MOT_GRG_ADD_CMD
                sg   = (tsbk >> 64) & 0xffff
                ga1  = (tsbk >> 48) & 0xffff
                ga2  = (tsbk >> 32) & 0xffff
                ga3  = (tsbk >> 16) & 0xffff
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] tsbk(0x00) mfid90_grg_add_cmd: sg: %d ga1: %d ga2: %d ga3: %d\n' % (log_ts.get(), m_rxid, sg, ga1, ga2, ga3))
                self.add_patch(sg, [ga1, ga2, ga3])
            else:
                opts = (tsbk >> 72) & 0xff
                ch   = (tsbk >> 56) & 0xffff
                ga   = (tsbk >> 40) & 0xffff
                sa   = (tsbk >> 16) & 0xffffff
                f = self.channel_id_to_frequency(ch)
                self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch), srcaddr=sa)
                if f:
                    updated += 1
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] tsbk(0x00) grp_v_ch_grant: freq: %s ga: %d sa: %d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch), ga, sa))
        elif opcode == 0x01:   # reserved
            mfrid  = (tsbk >> 80) & 0xff
            if mfrid == 0x90: #MOT_GRG_DEL_CMD
                sg   = (tsbk >> 64) & 0xffff
                ga1  = (tsbk >> 48) & 0xffff
                ga2  = (tsbk >> 32) & 0xffff
                ga3  = (tsbk >> 16) & 0xffff
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] tsbk(0x01) mfid90_grg_del_cmd: sg: %d ga1: %d ga2: %d ga3: %d\n' % (log_ts.get(), m_rxid, sg, ga1, ga2, ga3))
                self.del_patch(sg, [ga1, ga2, ga3])
        elif opcode == 0x02:   # group voice chan grant update
            mfrid  = (tsbk >> 80) & 0xff
            if mfrid == 0x90:
                ch  = (tsbk >> 56) & 0xffff
                sg  = (tsbk >> 40) & 0xffff
                sa  = (tsbk >> 16) & 0xffffff
                f = self.channel_id_to_frequency(ch)
                self.update_voice_frequency(f, tgid=sg, tdma_slot=self.get_tdma_slot(ch), srcaddr=sa)
                if f:
                    updated += 1
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] tsbk(0x02) mfid90_grg_ch_grant: freq: %s sg: %d sa: %d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch), sg, sa))
            else:
                ch1  = (tsbk >> 64) & 0xffff
                ga1  = (tsbk >> 48) & 0xffff
                ch2  = (tsbk >> 32) & 0xffff
                ga2  = (tsbk >> 16) & 0xffff
                f1 = self.channel_id_to_frequency(ch1)
                f2 = self.channel_id_to_frequency(ch2)
                self.update_voice_frequency(f1, tgid=ga1, tdma_slot=self.get_tdma_slot(ch1))
                if f1 != f2:
                    self.update_voice_frequency(f2, tgid=ga2, tdma_slot=self.get_tdma_slot(ch2))
                if f1:
                    updated += 1
                if f2:
                    updated += 1
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] tsbk(0x02) grp_v_ch_grant_up: ch1: %s ga1: %d ch2: %s ga2: %d\n' %(log_ts.get(), m_rxid, self.channel_id_to_string(ch1), ga1, self.channel_id_to_string(ch2), ga2))
        elif opcode == 0x03:   # group voice chan grant update exp : TIA.102-AABC-B-2005 page 56
            mfrid  = (tsbk >> 80) & 0xff
            if mfrid == 0x90: #MOT_GRG_CN_GRANT_UPDT
                ch1  = (tsbk >> 64) & 0xffff
                sg1  = (tsbk >> 48) & 0xffff
                ch2  = (tsbk >> 32) & 0xffff
                sg2  = (tsbk >> 16) & 0xffff
                f1 = self.channel_id_to_frequency(ch1)
                f2 = self.channel_id_to_frequency(ch2)
                self.update_voice_frequency(f1, tgid=sg1, tdma_slot=self.get_tdma_slot(ch1))
                if f1 != f2:
                    self.update_voice_frequency(f2, tgid=sg2, tdma_slot=self.get_tdma_slot(ch2))
                if f1:
                    updated += 1
                if f2:
                    updated += 1
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] tsbk(0x03) mfid90_grg_ch_grant_up: freq1: %s sg1: %d freq2: %s sg2:%d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch1), sg1, self.channel_id_to_string(ch2), sg2))
            elif mfrid == 0:
                ch1  = (tsbk >> 48) & 0xffff
                ch2   = (tsbk >> 32) & 0xffff
                ga  = (tsbk >> 16) & 0xffff
                f = self.channel_id_to_frequency(ch1)
                self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1))
                if f:
                    updated += 1
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] tsbk(0x03) grp_v_ch_grant_up_exp: freq-t: %s freq-r: %s ga: %d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2), ga))
        elif opcode == 0x16:   # sndcp data ch
            ch1  = (tsbk >> 48) & 0xffff
            ch2  = (tsbk >> 32) & 0xffff
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x16) sndcp_data_ch: ch1: %x ch2: %x\n' % (log_ts.get(), m_rxid, ch1, ch2))
        elif opcode == 0x28:   # grp_aff_rsp
            mfrid  = (tsbk >> 80) & 0xff
            lg     = (tsbk >> 79) & 0x01
            gav    = (tsbk >> 72) & 0x03
            aga    = (tsbk >> 56) & 0xffff
            ga     = (tsbk >> 40) & 0xffff
            ta     = (tsbk >> 16) & 0xffffff
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x28) grp_aff_rsp: mfid: 0x%x gav: %d aga: %d ga: %d ta: %d\n' % (log_ts.get(), m_rxid, mfrid, gav, aga, ga, ta))
        elif opcode == 0x29:   # secondary cc explicit form
            mfrid = (tsbk >> 80) & 0xff
            rfid  = (tsbk >> 72) & 0xff
            stid  = (tsbk >> 64) & 0xff
            ch1   = (tsbk >> 48) & 0xffff
            ch2   = (tsbk >> 24) & 0xffff
            f1 = self.channel_id_to_frequency(ch1)
            if f1:
                self.secondary[ f1 ] = 1
                sorted_freqs = collections.OrderedDict(sorted(self.secondary.items()))
                self.secondary = sorted_freqs
                add_unique_freq(self.cc_list, f1)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x29) sccb_exp: rfid: %x stid: %d ch1: %x(%s) ch2: %x(%s)\n' %(log_ts.get(), m_rxid, rfid, stid, ch1, self.channel_id_to_string(ch1), ch2, self.channel_id_to_string(ch2)))
        elif opcode == 0x2c:   # u_reg_rsp
            mfrid  = (tsbk >> 80) & 0xff
            rv     = (tsbk >> 76) & 0x3
            syid   = (tsbk >> 64) & 0xffff
            sid   = (tsbk >> 40) & 0xffffff
            sa     = (tsbk >> 16) & 0xffffff
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x2c) u_reg_rsp: mfid: 0x%x rv: %d syid: 0x%x sid: %d sa: %d\n' % (log_ts.get(), m_rxid, mfrid, rv, syid, sid, sa))
        elif opcode == 0x2f:   # u_de_reg_ack
            mfrid  = (tsbk >> 80) & 0xff
            wacn   = (tsbk >> 52) & 0xfffff
            syid   = (tsbk >> 40) & 0xffff
            sid    = (tsbk >> 16) & 0xffffff
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x2f) u_de_reg_ack: mfid: 0x%x wacn: 0x%x syid: 0x%x sid: %d\n' % (log_ts.get(), m_rxid, mfrid, wacn, syid, sid))
        elif opcode == 0x30:
            mfrid  = (tsbk >> 80) & 0xff
            if mfrid == 0xA4:  # GRG_EXENC_CMD
                grg_t   = (tsbk >> 79) & 0x1
                grg_g   = (tsbk >> 78) & 0x1
                grg_a   = (tsbk >> 77) & 0x1
                grg_ssn = (tsbk >> 72) & 0x1f # TODO: SSN should be stored and checked
                sg      = (tsbk >> 56) & 0xffff
                keyid   = (tsbk >> 40) & 0xffff
                rta     = (tsbk >> 16) & 0xffffff
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] tsbk(0x30) grg_exenc_cmd: grg_t: %d grg_g: %d, grg_a: %d, grg_ssn: %d, sg: %d, keyid: %d, rta: %d\n' % (log_ts.get(), m_rxid, grg_t, grg_g, grg_a, grg_ssn, sg, keyid, rta))
                if grg_a == 1: # Activate
                    if grg_g == 1: # Group request
                        algid = (rta >> 16) & 0xff
                        ga    =  rta        & 0xffff
                        self.add_patch(sg, [ga])
                    else:          # Unit request (currently unhandled)
                        pass
                else:          # Deactivate
                    if grg_g == 1: # Group request
                        algid = (rta >> 16) & 0xff
                        ga    =  rta        & 0xffff
                        self.del_patch(sg, [sg])
                    else:          # Unit request (currently unhandled)
                        pass
        elif opcode == 0x34:   # iden_up vhf uhf
            iden = (tsbk >> 76) & 0xf
            bwvu = (tsbk >> 72) & 0xf
            toff0 = (tsbk >> 58) & 0x3fff
            spac = (tsbk >> 48) & 0x3ff
            freq = (tsbk >> 16) & 0xffffffff
            toff_sign = (toff0 >> 13) & 1
            toff = toff0 & 0x1fff
            if toff_sign == 0:
                toff = 0 - toff
            txt = ["mob Tx-", "mob Tx+"]
            self.freq_table[iden] = {}
            self.freq_table[iden]['offset'] = toff * spac * 125
            self.freq_table[iden]['step'] = spac * 125
            self.freq_table[iden]['frequency'] = freq * 5
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x34) iden_up_vu: id: %d toff: %f spac: %f freq: %f [%s]\n' % (log_ts.get(), m_rxid, iden, toff * spac * 0.125 * 1e-3, spac * 0.125, freq * 0.000005, txt[toff_sign]))
        elif opcode == 0x33:   # iden_up_tdma
            mfrid  = (tsbk >> 80) & 0xff
            if mfrid == 0:
                iden = (tsbk >> 76) & 0xf
                channel_type = (tsbk >> 72) & 0xf
                toff0 = (tsbk >> 58) & 0x3fff
                spac = (tsbk >> 48) & 0x3ff
                toff_sign = (toff0 >> 13) & 1
                toff = toff0 & 0x1fff
                if toff_sign == 0:
                    toff = 0 - toff
                f1   = (tsbk >> 16) & 0xffffffff
                slots_per_carrier = [1,1,1,2,4,2,2,2,2,2,2,2,2,2,2,2] # values above 5 are reserved and not valid
                self.freq_table[iden] = {}
                self.freq_table[iden]['offset'] = toff * spac * 125
                self.freq_table[iden]['step'] = spac * 125
                self.freq_table[iden]['frequency'] = f1 * 5
                self.freq_table[iden]['tdma'] = slots_per_carrier[channel_type]
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] tsbk(0x33) iden_up_tdma: id: %d freq: %d toff: %d spac: %d slots/carrier: %d\n' % (log_ts.get(), m_rxid, iden, self.freq_table[iden]['frequency'], self.freq_table[iden]['offset'], self.freq_table[iden]['step'], self.freq_table[iden]['tdma']))
        elif opcode == 0x3d:   # iden_up
            iden = (tsbk >> 76) & 0xf
            bw   = (tsbk >> 67) & 0x1ff
            toff0 = (tsbk >> 58) & 0x1ff
            spac = (tsbk >> 48) & 0x3ff
            freq = (tsbk >> 16) & 0xffffffff
            toff_sign = (toff0 >> 8) & 1
            toff = toff0 & 0xff
            if toff_sign == 0:
                toff = 0 - toff
            txt = ["mob xmit < recv", "mob xmit > recv"]
            self.freq_table[iden] = {}
            self.freq_table[iden]['offset'] = toff * 250000
            self.freq_table[iden]['step'] = spac * 125
            self.freq_table[iden]['frequency'] = freq * 5
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x3d) iden_up id: %d toff: %f spac: %f freq: %f\n' % (log_ts.get(), m_rxid, iden, toff * 0.25, spac * 0.125, freq * 0.000005))
        elif opcode == 0x3a:   # rfss status
            syid = (tsbk >> 56) & 0xfff
            rfid = (tsbk >> 48) & 0xff
            stid = (tsbk >> 40) & 0xff
            chan = (tsbk >> 24) & 0xffff
            f1 = self.channel_id_to_frequency(chan)
            if f1:
                self.rfss_syid = syid
                self.rfss_rfid = rfid
                self.rfss_stid = stid
                self.rfss_chan = f1
                self.rfss_txchan = f1 + self.freq_table[chan >> 12]['offset']
                add_unique_freq(self.cc_list, f1)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x3a) rfss_sts_bcst: syid: %x rfid: %x stid: %d ch1: %x(%s)\n' %(log_ts.get(), m_rxid, syid, rfid, stid, chan, self.channel_id_to_string(chan)))
        elif opcode == 0x39:   # secondary cc
            mfrid = (tsbk >> 80) & 0xff
            rfid  = (tsbk >> 72) & 0xff
            stid  = (tsbk >> 64) & 0xff
            ch1   = (tsbk >> 48) & 0xffff
            ch2   = (tsbk >> 24) & 0xffff
            f1 = self.channel_id_to_frequency(ch1)
            f2 = self.channel_id_to_frequency(ch2)
            if f1 and f2:
                self.secondary[ f1 ] = 1
                self.secondary[ f2 ] = 1
                sorted_freqs = collections.OrderedDict(sorted(self.secondary.items()))
                self.secondary = sorted_freqs
                add_unique_freq(self.cc_list, f1)
                add_unique_freq(self.cc_list, f2)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x39) sccb: rfid: %x stid: %d ch1: %x(%s) ch2: %x(%s)\n' %(log_ts.get(), m_rxid, rfid, stid, ch1, self.channel_id_to_string(ch1), ch2, self.channel_id_to_string(ch2)))
        elif opcode == 0x3b:   # network status
            wacn = (tsbk >> 52) & 0xfffff
            syid = (tsbk >> 40) & 0xfff
            ch1  = (tsbk >> 24) & 0xffff
            f1 = self.channel_id_to_frequency(ch1)
            if f1:
                self.ns_syid = syid
                self.ns_wacn = wacn
                self.ns_chan = f1
                self.ns_valid = True
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x3b) net_sts_bcst: wacn: %x syid: %x ch1: %x(%s)\n' %(log_ts.get(), m_rxid, wacn, syid, ch1, self.channel_id_to_string(ch1)))
        elif opcode == 0x3c:   # adjacent status
            rfid = (tsbk >> 48) & 0xff
            stid = (tsbk >> 40) & 0xff
            ch1  = (tsbk >> 24) & 0xffff
            table = (ch1 >> 12) & 0xf
            f1 = self.channel_id_to_frequency(ch1)
            if f1 and table in self.freq_table:
                self.adjacent[f1] = 'rfid: %d stid:%d uplink:%f tbl:%d' % (rfid, stid, (f1 + self.freq_table[table]['offset']) / 1000000.0, table)
                self.adjacent_data[f1] = {'rfid': rfid, 'stid':stid, 'uplink': f1 + self.freq_table[table]['offset'], 'table': table}
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x3c) adj_sts_bcst: rfid: %x stid: %d ch1: %x(%s)\n' %(log_ts.get(), m_rxid, rfid, stid, ch1, self.channel_id_to_string(ch1)))
                if table in self.freq_table:
                    sys.stderr.write('%s [%d] tsbk(0x3c) adj_sts_bcst: base freq: %s step: %s\n' % (log_ts.get(), m_rxid, self.freq_table[table]['frequency'] , self.freq_table[table]['step'] ))
        else:
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tsbk(0x%02x) unhandled: 0x%024x\n' % (log_ts.get(), m_rxid, opcode, tsbk))
        return updated

    def decode_tdma_ptt(self, m_rxid, msg, curr_time):
        self.last_tsbk = time.time()
        self.stats['tsbk_count'] += 1
        mi    = get_ordinals(msg[0:9])
        algid = get_ordinals(msg[9:10])
        keyid = get_ordinals(msg[10:12])
        sa    = get_ordinals(msg[12:15])
        ga    = get_ordinals(msg[15:17])
        if self.debug >= 10:
            sys.stderr.write('%s [%d] mac_ptt: mi: %x algid: %x keyid:%x ga: %d sa: %d\n' % (log_ts.get(), m_rxid, mi, algid, keyid, ga, sa))
        return self.update_talkgroup_srcaddr(curr_time, ga, sa)

    def decode_tdma_endptt(self, m_rxid, msg, curr_time):
        self.last_tsbk = time.time()
        self.stats['tsbk_count'] += 1
        mi    = get_ordinals(msg[0:9])
        sa    = get_ordinals(msg[12:15])
        ga    = get_ordinals(msg[15:17])
        if self.debug >= 10:
            sys.stderr.write('%s [%d] mac_end_ptt: ga: %d sa: %d\n' % (log_ts.get(), m_rxid, ga, sa))
        return self.update_talkgroup_srcaddr(curr_time, ga, sa)

    def decode_tdma_msg(self, m_rxid, msg, curr_time):
        updated = 0
        self.cc_timeouts = 0
        self.last_tsbk = time.time()
        self.stats['tsbk_count'] += 1
        mfid = 0
        op = get_ordinals(msg[:1])
        b1b2 = (op >> 6) & 0x3
        if b1b2 == 2:    # Manufacturer-specific opcode has MFID in second octet
            mfid = get_ordinals(msg[1:2])

        # Opcode specific handlers
        if op == 0x01:   # Group Voice Channel User Abbreviated
            ga = get_ordinals(msg[2:4])
            sa = get_ordinals(msg[4:7])
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0x01) grp_v_ch_usr: ga: %d sa: %d\n' % (log_ts.get(), m_rxid, ga, sa))
            updated += self.update_talkgroup_srcaddr(curr_time, ga, sa)
        elif op == 0x05: # Group Voice Channel Grant Update Multiple - Implicit
            ch1 = get_ordinals(msg[2:4])
            ga1 = get_ordinals(msg[4:6])
            ch2 = get_ordinals(msg[7:9])
            ga2 = get_ordinals(msg[9:11])
            ch3 = get_ordinals(msg[12:14])
            ga3 = get_ordinals(msg[14:16])
            f1 = self.channel_id_to_frequency(ch1)
            f2 = self.channel_id_to_frequency(ch2)
            f3 = self.channel_id_to_frequency(ch3)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0x05) grp_v_ch_grant_up: f1: %s ga1: %d f2: %s ga2: %d f3: %s ga3: %d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch1), ga1, self.channel_id_to_string(ch2), ga2, self.channel_id_to_string(ch3), ga3))
            self.update_voice_frequency(f1, tgid=ga1, tdma_slot=self.get_tdma_slot(ch1))
            self.update_voice_frequency(f2, tgid=ga2, tdma_slot=self.get_tdma_slot(ch2))
            self.update_voice_frequency(f3, tgid=ga3, tdma_slot=self.get_tdma_slot(ch3))
            if f1 or f2 or f3:
                updated += 1
        elif op == 0x21: # Group Voice Channel User - Extended
            ga   = get_ordinals(msg[2:4])
            sa   = get_ordinals(msg[4:7])
            suid = get_ordinals(msg[7:14])
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0x21) grp_v_ch_usr: ga: %d sa: %d: suid: %d\n' % (log_ts.get(), m_rxid, ga, sa, suid))
            updated += self.update_talkgroup_srcaddr(curr_time, ga, sa)
        elif op == 0x25: # Group Voice Channel Grant Update Multiple - Explicit
            ch1t = get_ordinals(msg[2:4])
            ch1r = get_ordinals(msg[4:6])
            ga1  = get_ordinals(msg[6:8])
            ch2t = get_ordinals(msg[9:11])
            ch2r = get_ordinals(msg[11:13])
            ga2  = get_ordinals(msg[13:15])
            f1   = self.channel_id_to_frequency(ch1t)
            f2   = self.channel_id_to_frequency(ch2t)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0x25) grp_v_ch_grant_up: f1-t: %s f1-r: %s ga1: %d f2-t: %s f2-r: %s ga2: %d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch1t), self.channel_id_to_string(ch1r), ga1, self.channel_id_to_string(ch2t), self.channel_id_to_string(ch2r), ga2))
            self.update_voice_frequency(f1, tgid=ga1, tdma_slot=self.get_tdma_slot(ch1t))
            self.update_voice_frequency(f2, tgid=ga2, tdma_slot=self.get_tdma_slot(ch2t))
            if f1 or f2:
                updated += 1
        elif op == 0x30: # Power Control Signal Quality
            ta     = get_ordinals(msg[1:4])
            rf_ber = get_ordinals(msg[4:5])  
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0x30) pwr_ctl_sig_qual: ta: %d rf: 0x%x: ber: 0x%x\n' % (log_ts.get(), m_rxid, ta, ((rf_ber >> 4) & 0xf), (rf_ber & 0xf)))
        elif op == 0x31: # MAC_Release (subscriber call pre-emption)
            uf = (get_ordinals(msg[1:2]) >> 7) & 0x1
            ca = (get_ordinals(msg[1:2]) >> 6) & 0x1
            sa = get_ordinals(msg[2:5])
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0x31) MAC_Release: uf: %d ca: %d sa: %d\n' % (log_ts.get(), m_rxid, uf, ca, sa))
        elif op == 0x80 and mfid == 0x90: # MFID90 Group Regroup Voice Channel User Abbreviated
            sg = get_ordinals(msg[3:5])
            sa = get_ordinals(msg[5:8])
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0x80) mfid90 grp_regrp_v_ch_usr: sg: %d sa: %d\n' % (log_ts.get(), m_rxid, sg, sa))
            updated += self.update_talkgroup_srcaddr(curr_time, sg, sa)
        elif op == 0x81 and mfid == 0x90: # MFID90 Group Regroup Add Command
            wg_len = (get_ordinals(msg[2:3]) & 0x3f)
            wg_list = []
            sg = get_ordinals(msg[3:5])
            i = 5
            while i < wg_len:
                wg = get_ordinals(msg[i:i+2])
                if wg not in wg_list:
                    wg_list.append(wg)
                i += 2
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0x81) mfid90 grp_regrp_add: sg: %d wg_list: %s\n' % (log_ts.get(), m_rxid, sg, wg_list))
            self.add_patch(sg, wg_list)
        elif op == 0x83 and mfid == 0x90: # MFID90 Group Regroup Voice Channel Update
            sg = get_ordinals(msg[3:5])
            ch = get_ordinals(msg[5:7])
            f = self.channel_id_to_frequency(ch)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0x83) grp_regrp_v_ch_up freq: %s sg: %d\n' %(log_ts.get(), m_rxid, self.channel_id_to_string(ch), sg))
            self.update_voice_frequency(f, tgid=sg, tdma_slot=self.get_tdma_slot(ch))
            if f:
                updated += 1
        elif op == 0x89 and mfid == 0x90: # MFID90 Group Regroup Delete Command
            wg_len = (get_ordinals(msg[2:3]) & 0x3f)
            wg_list = []
            sg = get_ordinals(msg[3:5])
            i = 5
            while i < wg_len:
                wg = get_ordinals(msg[i:i+2])
                if wg not in wg_list:
                    wg_list.append(wg)
                i += 2
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0x89) mfid90 grp_regrp_del: sg: %d wg_list: %s\n' % (log_ts.get(), m_rxid, sg, wg_list))
            self.del_patch(sg, wg_list)
        elif op == 0xa0 and mfid == 0x90: # MFID90 Group Regroup Voice Channel User Extendd
            sg    = get_ordinals(msg[4:6])
            sa    = get_ordinals(msg[6:9])
            ssuid = get_ordinals(msg[9:16])
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xa0) mfid90 grp_regrp_v_ch_usr: sg: %d sa: %d, ssuid: %d\n' % (log_ts.get(), m_rxid, sg, sa, ssuid))
            updated += self.update_talkgroup_srcaddr(curr_time, sg, sa)
        elif op == 0xa3 and mfid == 0x90: # MFID90 Group Regroup Channel Grant Implicit
            ch = get_ordinals(msg[4:6])
            sg = get_ordinals(msg[6:8])
            sa = get_ordinals(msg[8:11])
            f = self.channel_id_to_frequency(ch)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xa3) grp_regrp_v_ch_grant freq: %s sg: %d sa: %d\n' %(log_ts.get(), m_rxid, self.channel_id_to_string(ch), sg, sa))
            self.update_voice_frequency(f, tgid=sg, tdma_slot=self.get_tdma_slot(ch), srcaddr=sa)
            if f:
                updated += 1
        elif op == 0xa4 and mfid == 0x90: # MFID90 Group Regroup Channel Grant Explicit
            ch1 = get_ordinals(msg[4:6])
            ch2 = get_ordinals(msg[6:8])
            sg = get_ordinals(msg[8:10])
            sa = get_ordinals(msg[10:13])
            f = self.channel_id_to_frequency(ch1)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xa4) grp_regrp_v_ch_grant freq-t: %s freq-r: %s sg: %d sa: %d\n' %(log_ts.get(), m_rxid, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2), sg, sa))
            self.update_voice_frequency(f, tgid=sg, tdma_slot=self.get_tdma_slot(ch1), srcaddr=sa)
            if f:
                updated += 1
        elif op == 0xa5 and mfid == 0x90: # MFID90 Group Regroup Channel Update
            sg1 = get_ordinals(msg[5:7])
            sg2 = get_ordinals(msg[9:11])
            ch1 = get_ordinals(msg[3:5])
            ch2 = get_ordinals(msg[7:9])
            f1 = self.channel_id_to_frequency(ch1)
            f2 = self.channel_id_to_frequency(ch2)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xa5) grp_regrp_ch_up f1: %s sg1: %d f2: %s sg2: %d\n' %(log_ts.get(), m_rxid, self.channel_id_to_string(ch1), sg1, self.channel_id_to_string(ch2), sg2))
            self.update_voice_frequency(f1, tgid=sg1, tdma_slot=self.get_tdma_slot(ch1))
            self.update_voice_frequency(f2, tgid=sg2, tdma_slot=self.get_tdma_slot(ch2))
            if f1 or f2:
                updated += 1
        elif op == 0xb0 and mfid == 0xa4: # MFIDA4 Group Regroup Explicit Encryption Command
            grg_len = get_ordinals(msg[2:3]) & 0x3f
            grg_opt = (get_ordinals(msg[3:4]) >> 5) & 0x07
            grg_ssn = get_ordinals(msg[3:4]) & 0x1f
            if (grg_opt & 0x2): # Group Address
                sg    = get_ordinals(msg[4:6])
                keyid = get_ordinals(msg[6:8])
                algid = get_ordinals(msg[8:9])
                wglst = []
                i = 9
                while i <= grg_len:
                    wg = get_ordinals(msg[i:i+2])
                    if wg:
                        wglst.append(wg)
                    i += 2
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] tdma(0xb0) grg_regrp_exenc_cmd: grg_opt: %d grg_ssn: %d sg: %d keyid: %x algid: %x wgids: %s\n' % (log_ts.get(), m_rxid, grg_opt, grg_ssn, sg, keyid, algid, wglst))
                if (grg_opt & 0x1): # Activate
                    self.add_patch(sg, wglst)
                else:               # Deactivate
                    self.del_patch(sg, wglst)
            else:               # Individual Address (not currently supported)
                pass
        elif op == 0xc0: # Group Voice Channel Grant Explicit
            ch1t = get_ordinals(msg[2:4])
            ch1r = get_ordinals(msg[4:6])
            ga   = get_ordinals(msg[6:8])
            sa   = get_ordinals(msg[8:11])
            f    = self.channel_id_to_frequency(ch1t)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xc0) grp_v_ch_grant: freq-t: %s freq-r: %s ga: %d sa: %d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch1t), self.channel_id_to_string(ch1r), ga, sa))
            self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1t), srcaddr=sa)
            if f:
                updated += 1
        elif op == 0xc3: # Group Voice Channel Grant Update Explicit
            ch1t = get_ordinals(msg[2:4])
            ch1r = get_ordinals(msg[4:6])
            ga   = get_ordinals(msg[6:8])
            f    = self.channel_id_to_frequency(ch1t)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xc3) grp_v_ch_grant_up: freq-t: %s freq-r: %s ga: %d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch1t), self.channel_id_to_string(ch1r), ga))
            self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1t))
            if f:
                updated += 1
        elif op == 0xe9: # Secondary Control Channel Broadcast Explicit
            rfid = get_ordinals(msg[1:2])
            stid = get_ordinals(msg[2:3])
            ch_t = get_ordinals(msg[3:5])
            ch_r = get_ordinals(msg[5:7])
            f    = self.channel_id_to_frequency(ch_t)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xe9) sccb: rfid: %x stid: %x freq-t: %s freq-r: %s\n' % (log_ts.get(), m_rxid, rfid, stid, self.channel_id_to_string(ch_t), self.channel_id_to_string(ch_r)))
            if f:
                self.secondary[ f ] = 1
                sorted_freqs = collections.OrderedDict(sorted(self.secondary.items()))
                self.secondary = sorted_freqs
                add_unique_freq(self.cc_list, f)
        elif op == 0xf3: # Identifier Update for TDMA Extended
            iden    = (get_ordinals(msg[2:3]) >> 4) & 0xf
            ch_type =  get_ordinals(msg[2:3]) & 0xf
            tx_off  = (get_ordinals(msg[3:5]) >> 2) & 0x3fff
            tx_off  = (0 - tx_off) if ((tx_off >> 13) & 0x1) else tx_off
            ch_spac =  get_ordinals(msg[4:6]) & 0x3ff
            base_f  =  get_ordinals(msg[6:10])
            wacn_id = (get_ordinals(msg[10:13]) >> 4) & 0xfffff
            sys_id  =  get_ordinals(msg[13:14]) & 0xfff
            slots_per_carrier = [1,1,1,2,4,2,2,2,2,2,2,2,2,2,2,2] # values above 5 are reserved and not valid
            self.freq_table[iden] = {}
            self.freq_table[iden]['offset'] = tx_off * ch_spac * 125
            self.freq_table[iden]['step'] = ch_spac * 125
            self.freq_table[iden]['frequency'] = base_f * 5
            self.freq_table[iden]['tdma'] = slots_per_carrier[ch_type]
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xf3) iden_up_tdma: id: %d base_f: %d offset: %d spacing: %d slots/carrier %d\n' % (log_ts.get(), m_rxid, iden, base_f, tx_off, ch_spac, slots_per_carrier[ch_type]))
        elif op == 0xfa: # RFSS Status Broadcast Explicit
            syid = get_ordinals(msg[2:4]) & 0xfff
            rfid = get_ordinals(msg[4:5])
            stid = get_ordinals(msg[5:6])
            ch_t = get_ordinals(msg[6:8])
            ch_r = get_ordinals(msg[8:10])
            f    = self.channel_id_to_frequency(ch_t)
            if f:
                self.rfss_syid = syid
                self.rfss_rfid = rfid
                self.rfss_stid = stid
                self.rfss_chan = f
                self.rfss_txchan = f + self.freq_table[ch_t >> 12]['offset']
                add_unique_freq(self.cc_list, f)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xfa) rfss_sts_bcst: syid: %x rfid: %x stid: %x ch %x(%s)\n' % (log_ts.get(), m_rxid, syid, rfid, stid, ch_t, self.channel_id_to_string(ch_t)))
        elif op == 0xfb: # Network Status Broadcast Explicit
            wacn = (get_ordinals(msg[2:5]) >> 4) & 0xfffff
            syid =  get_ordinals(msg[4:6]) & 0xfff
            ch_t = get_ordinals(msg[6:8])
            ch_r = get_ordinals(msg[8:10])
            f    = self.channel_id_to_frequency(ch_t)
            if f:
                self.ns_syid = syid
                self.ns_wacn = wacn
                self.ns_chan = f
                self.ns_valid = True
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xfb) net_sts_bcst: wacn: %x syid: %x ch %x(%s)\n' % (log_ts.get(), m_rxid, wacn, syid, ch_t, self.channel_id_to_string(ch_t)))
        elif op == 0xfc: # Adjacent Status Broadcast Explicit
            syid  = get_ordinals(msg[2:4]) & 0xfff
            rfid  = get_ordinals(msg[4:5])
            stid  = get_ordinals(msg[5:6])
            ch_t  = get_ordinals(msg[6:8])
            ch_r  = get_ordinals(msg[8:10])
            table = (ch_t >> 12) & 0xf
            f     = self.channel_id_to_frequency(ch_t)
            if f and table in self.freq_table:
                self.adjacent[f] = 'rfid: %d stid:%d uplink:%f tbl:%d' % (rfid, stid, (f + self.freq_table[table]['offset']) / 1000000.0, table)
                self.adjacent_data[f] = {'rfid': rfid, 'stid':stid, 'uplink': f + self.freq_table[table]['offset'], 'table': table}
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xfc) adj_sts_bcst: syid: %x rfid: %x stid: %x ch %x(%s)\n' % (log_ts.get(), m_rxid, syid, rfid, stid, ch_t, self.channel_id_to_string(ch_t)))
                if table in self.freq_table:
                    sys.stderr.write('%s [%d] tdma(0xfc) adj_sts_bcst: base freq: %s step: %s\n' % (log_ts.get(), m_rxid, self.freq_table[table]['frequency'] , self.freq_table[table]['step'] ))
        elif op == 0xfe: # Adjacent Status Broadcast Extended Explicit
            syid  = get_ordinals(msg[2:4]) & 0xfff
            rfid  = get_ordinals(msg[4:5])
            stid  = get_ordinals(msg[5:6])
            ch_t  = get_ordinals(msg[6:8])
            ch_r  = get_ordinals(msg[8:10])
            wacn  = (get_ordinals(msg[12:15]) >> 4) & 0xfffff
            table = (ch_t >> 12) & 0xf
            f     = self.channel_id_to_frequency(ch_t)
            if f and table in self.freq_table:
                self.adjacent[f] = 'rfid: %d stid:%d uplink:%f tbl:%d' % (rfid, stid, (f + self.freq_table[table]['offset']) / 1000000.0, table)
                self.adjacent_data[f] = {'rfid': rfid, 'stid':stid, 'uplink': f + self.freq_table[table]['offset'], 'table': table}
            if self.debug >= 10:
                sys.stderr.write('%s [%d] tdma(0xfe) adj_sts_bcst: wacn: %x syid: %x rfid: %x stid: %x ch %x(%s)\n' % (log_ts.get(), m_rxid, wacn, syid, rfid, stid, ch_t, self.channel_id_to_string(ch_t)))
                if table in self.freq_table:
                    sys.stderr.write('%s [%d] tdma(0xfe) adj_sts_bcst: base freq: %s step: %s\n' % (log_ts.get(), m_rxid, self.freq_table[table]['frequency'] , self.freq_table[table]['step'] ))
        else:
            if self.debug >= 10:
                m_data = get_ordinals(msg[1:])
                sys.stderr.write('%s [%d] tdma(0x%02x) unhandled: mfid: %x msg_data: %x\n' % (log_ts.get(), m_rxid, op, mfid, m_data))
        return updated

    def decode_fdma_lcw(self, m_rxid, msg, curr_time):
        updated = 0
        self.last_tsbk = time.time()
        self.stats['tsbk_count'] += 1
        pb_sf_lco = get_ordinals(msg[0:1])

        if (pb_sf_lco & 0x80): # encrypted format not supported
            return 0

        if pb_sf_lco   == 0x00:     # Group Voice Channel User
            mfid = get_ordinals(msg[1:2])
            ga = get_ordinals(msg[4:6])
            sa = get_ordinals(msg[6:9])
            if self.debug >= 10:
                sys.stderr.write('%s [%d] lcw(0x00) grp_v_ch_usr: ga: %d s: %d sa: %d\n' % (log_ts.get(), m_rxid, ga, (get_ordinals(msg[3:4]) & 0x1), sa))
            updated += self.update_talkgroup_srcaddr(curr_time, ga, sa)
        elif pb_sf_lco == 0x42:     # Group Voice Channel Update
            ch1 = get_ordinals(msg[1:3])
            ga1 = get_ordinals(msg[3:5])
            ch2 = get_ordinals(msg[5:7])
            ga2 = get_ordinals(msg[7:9])
            f1 = self.channel_id_to_frequency(ch1)
            f2 = self.channel_id_to_frequency(ch2)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] lcw(0x02) grp_v_ch_up f1: %s ga1: %d f2: %s ga2: %d\n' %(log_ts.get(), m_rxid, self.channel_id_to_string(ch1), ga1, self.channel_id_to_string(ch2), ga2))
            self.update_voice_frequency(f1, tgid=ga1, tdma_slot=self.get_tdma_slot(ch1))
            self.update_voice_frequency(f2, tgid=ga2, tdma_slot=self.get_tdma_slot(ch2))
            if f1 or f2:
                updated += 1
        elif pb_sf_lco == 0x44:   # Group Voice Channel Update Explicit
            ga   = get_ordinals(msg[3:5])
            ch1t = get_ordinals(msg[5:7])
            ch1r = get_ordinals(msg[7:9])
            f    = self.channel_id_to_frequency(ch1t)
            if self.debug >= 10:
                sys.stderr.write('%s [%d] lco(0x04) grp_v_ch_up: freq-t: %s freq-r: %s ga: %d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch1t), self.channel_id_to_string(ch1r), ga))
            self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1t))
            if f:
                updated += 1
        elif pb_sf_lco == 0x49:   # Source ID Extension
            netid = (get_ordinals(msg[2:5]) >> 4) & 0x0fffff
            syid  = get_ordinals(msg[4:6]) & 0x0fff
            sid   = get_ordinals(msg[6:9])
            if self.debug >= 10:
                sys.stderr.write('%s [%d] lcw(0x09) lc_source_id_ext: netid: %d, sysid: %d, sid: %d\n' % (log_ts.get(), m_rxid, netid, syid, sid))
        elif pb_sf_lco == 0x4f:   # Call Termination/Cancellation (included with DUID15/ETDU)
            sa   = get_ordinals(msg[6:9])
            if self.debug >= 10:
                sys.stderr.write('%s [%d] lco(0x0f) call_term_rel: sa: %d\n' % (log_ts.get(), m_rxid, sa))
        else:
            if self.debug >= 10:
                lcw_data = get_ordinals(msg[1:])
                sys.stderr.write('%s [%d] lcw(0x%02x) unhandled: pb: %d sf: %d lcw_data: %016x\n' % (log_ts.get(), m_rxid, (pb_sf_lco & 0x3f), ((pb_sf_lco >> 7) & 0x1), ((pb_sf_lco >> 6) & 0x1), lcw_data))
        return updated

    def find_voice_freq(self, tgid=None):
        if tgid is None:
            return (None, None)
        for freq in self.voice_frequencies:
            if self.voice_frequencies[freq]['tgid'][0] == tgid and self.voice_frequencies[freq]['tgid'][1] == tgid:
                return (freq, None)
            elif self.voice_frequencies[freq]['tgid'][0] == tgid:
                return (freq, 0)
            elif self.voice_frequencies[freq]['tgid'][1] == tgid:
                return (freq, 1)
        return (None, None)

    def update_voice_frequency(self, frequency, tgid=None, tdma_slot=None, srcaddr=0):
        if not frequency:    # e.g., channel identifier not yet known
            return
        prev_freq, prev_slot = self.find_voice_freq(tgid)
        self.update_talkgroups(frequency, tgid, tdma_slot, srcaddr)
        if frequency not in self.voice_frequencies:
            self.voice_frequencies[frequency] = {'counter':0}
            sorted_freqs = collections.OrderedDict(sorted(self.voice_frequencies.items()))
            self.voice_frequencies = sorted_freqs
            if self.debug >= 5:
                sys.stderr.write('%s [%s] new freq=%f\n' % (log_ts.get(), self.sysname, frequency/1000000.0))
        if 'tgid' not in self.voice_frequencies[frequency]:
            self.voice_frequencies[frequency]['tgid'] = [None, None]
            self.voice_frequencies[frequency]['ts'] = [0.0, 0.0]
        if prev_freq is not None and not (prev_freq == frequency and prev_slot == tdma_slot):
            if self.debug >= 5:
                sys.stderr.write("%s [%s] VF change: tgid: %s, prev_freq: %f, prev_slot: %s, new_freq: %f, new_slot: %s\n" % (log_ts.get(), self.sysname, tgid, prev_freq/1000000.0, prev_slot, frequency/1000000.0, tdma_slot))
            if prev_slot is None:
                self.voice_frequencies[prev_freq]['tgid'] = [None, None]
            else:
                self.voice_frequencies[prev_freq]['tgid'][prev_slot] = None
        curr_time = time.time()
        self.voice_frequencies[frequency]['time'] = curr_time
        self.voice_frequencies[frequency]['counter'] += 1
        if tdma_slot is None:   # FDMA mark both slots with same info
            if self.debug >= 10:
                sys.stderr.write("%s [%s] VF ts ph1: tgid: %s, freq: %f\n" % (log_ts.get(), self.sysname, tgid, frequency/1000000.0))
            for slot in [0, 1]:
                self.voice_frequencies[frequency]['tgid'][slot] = tgid
                self.voice_frequencies[frequency]['ts'][slot] = curr_time
        else:                   # TDMA mark just slot in use
            if self.debug >= 10:
                sys.stderr.write("%s [%s] VF ts ph2: tgid: %s, freq: %f, slot: %s\n" % (log_ts.get(), self.sysname, tgid, frequency/1000000.0, tdma_slot))
            self.voice_frequencies[frequency]['tgid'][tdma_slot] = tgid
            self.voice_frequencies[frequency]['ts'][tdma_slot] = curr_time

    def expire_voice_frequencies(self, curr_time):
        if curr_time < self.last_expiry_check + EXPIRY_TIMER:
            return
        self.last_expiry_check = curr_time
        for frequency in self.voice_frequencies:
            for slot in [0, 1]:
                tgid = self.voice_frequencies[frequency]['tgid'][slot]
                if tgid is not None and self.talkgroups[tgid]['receiver'] is None and curr_time >= self.voice_frequencies[frequency]['ts'][slot] + FREQ_EXPIRY_TIME:
                    if self.debug >= 10:
                        sys.stderr.write("%s [%s] VF expire: tgid: %s, freq: %f, slot: %s, ts: %s\n" % (log_ts.get(), self.sysname, tgid, frequency/1000000.0, slot, log_ts.get(self.voice_frequencies[frequency]['ts'][slot])))
                    self.voice_frequencies[frequency]['tgid'][slot] = None

    def update_talkgroups(self, frequency, tgid, tdma_slot, srcaddr):
        self.update_talkgroup(frequency, tgid, tdma_slot, srcaddr)
        if tgid in self.patches:
            for ptgid in self.patches[tgid]['ga']:
                self.update_talkgroup(frequency, ptgid, tdma_slot, srcaddr)
                if self.debug >= 5:
                    sys.stderr.write('%s [%s] update_talkgroups: sg(%d) patched tgid(%d)\n' % (log_ts.get(), self.sysname, tgid, ptgid))

    def update_talkgroup(self, frequency, tgid, tdma_slot, srcaddr):
        if self.debug >= 5:
            sys.stderr.write('%s [%s] set tgid=%s, srcaddr=%s\n' % (log_ts.get(), self.sysname, tgid, srcaddr))
        
        if tgid not in self.talkgroups:
            add_default_tgid(self.talkgroups, tgid)
            if self.debug >= 5:
                sys.stderr.write('%s [%s] new tgid=%s %s prio %d\n' % (log_ts.get(), self.sysname, tgid, self.talkgroups[tgid]['tag'], self.talkgroups[tgid]['prio']))
        self.talkgroups[tgid]['time'] = time.time()
        self.talkgroups[tgid]['counter'] += 1
        self.talkgroups[tgid]['frequency'] = frequency
        self.talkgroups[tgid]['tdma_slot'] = tdma_slot
        if (self.talkgroups[tgid]['receiver'] is not None):
            if (srcaddr > 0):
                self.talkgroups[tgid]['srcaddr'] = srcaddr      # don't overwrite with null srcaddr for active calls
        else:
            self.talkgroups[tgid]['srcaddr'] = srcaddr

    def update_talkgroup_srcaddr(self, curr_time, tgid, srcaddr):
        if (tgid is None or tgid <= 0 or srcaddr is None or srcaddr <= 0 or
            tgid not in self.talkgroups or self.talkgroups[tgid]['receiver'] is None):
            return 0

        self.talkgroups[tgid]['srcaddr'] = srcaddr
        add_default_rid(self.sourceids, srcaddr)
        self.sourceids[srcaddr]['counter'] += 1
        self.sourceids[srcaddr]['time'] = curr_time
        if tgid not in self.sourceids[srcaddr]['tgs']:
            self.sourceids[srcaddr]['tgs'][tgid] = 1;
        else:
            self.sourceids[srcaddr]['tgs'][tgid] += 1;
        self.sourceid_history.record(srcaddr, tgid, curr_time)
        return 1

    def expire_talkgroups(self, curr_time):
        if curr_time < self.last_expiry_check + EXPIRY_TIMER:
            return

        self.last_expiry_check = curr_time
        for tgid in self.talkgroups:
            if (self.talkgroups[tgid]['receiver'] is not None) and (curr_time >= self.talkgroups[tgid]['time'] + TGID_EXPIRY_TIME):
                if self.debug > 1:
                    sys.stderr.write("%s [%s] expiring tg(%d), freq(%f), slot(%s)\n" % (log_ts.get(), self.sysname, tgid, (self.talkgroups[tgid]['frequency']/1e6), get_slot(self.talkgroups[tgid]['tdma_slot'])))
                self.talkgroups[tgid]['receiver'].expire_talkgroup(reason="expiry")

    def add_patch(self, sg, ga_list):
        if sg not in self.patches:
            self.patches[sg] = {}
            self.patches[sg]['ga'] = set()
            self.patches[sg]['ts'] = time.time()

        for ga in ga_list:
            if (ga != sg):
                self.patches[sg]['ts'] = time.time() # update timestamp
                if ga not in self.patches[sg]['ga']:
                    self.patches[sg]['ga'].add(ga)
                    if self.debug >= 5:
                        sys.stderr.write("%s [%s] add_patch: tgid(%d) is patched to sg(%d)\n" % (log_ts.get(), self.sysname, ga, sg))

        if len(self.patches[sg]['ga']) == 0:
            del self.patches[sg]

    def del_patch(self, sg, ga_list):
        if sg not in self.patches:
            return

        for ga in ga_list:
            if ga in self.patches[sg]['ga']:
                self.patches[sg]['ga'].discard(ga)
                if self.debug >= 5:
                    sys.stderr.write("%s [%s] del_patch: tgid(%d) is unpatched from sg(%d)\n" % (log_ts.get(), self.sysname, ga, sg))

        if (sg in ga_list) or (len(self.patches[sg]['ga']) == 0):
            del self.patches[sg]
            if self.debug >= 5:
                sys.stderr.write("%s del_patch: deleting patch sg(%d)\n" % (log_ts.get(), sg))

    def expire_patches(self):
        updated = 0
        time_now = time.time()
        for sg in list(self.patches):
            if time_now > (self.patches[sg]['ts'] + PATCH_EXPIRY_TIME):
                updated += 1
                del self.patches[sg]
                if self.debug >= 5:
                    sys.stderr.write("%s [%s] expired_patches: expiring patch sg(%d)\n" % (log_ts.get(), self.sysname, sg))
        return updated

    def get_rid_tag(self, srcaddr):
        if srcaddr is None or srcaddr not in self.sourceids:
            return ""
        else:
            return self.sourceids[srcaddr]['tag']

    def dump_tgids(self):
        sys.stderr.write("%s [%s] Known talkgroup ids: {\n" % (log_ts.get(), self.sysname))
        for tgid in sorted(self.talkgroups.keys()):
            sys.stderr.write('%d\t"%s"\t%d\t#%d\n' % (tgid, self.talkgroups[tgid]['tag'], self.talkgroups[tgid]['prio'], self.talkgroups[tgid]['counter']));
        sys.stderr.write("}\n") 

    def dump_rids(self):
        sys.stderr.write("%s [%s] Known radio ids: {\n" % (log_ts.get(), self.sysname))
        for rid in sorted(self.sourceids.keys()):
            sys.stderr.write('%d\t"%s"\t# tgids %s\n' % (rid, self.sourceids[rid]['tag'], self.sourceids[rid]['tgs']));
        sys.stderr.write("}\n") 

    def to_json(self):  # ugly but required for compatibility with P25 trunking and terminal modules
        d = {}
        d['system']         = self.sysname
        d['top_line']       = 'P25 NAC 0x%x' % (self.nac)
        d['top_line']      += ' WACN 0x%x' % (self.ns_wacn if self.ns_wacn is not None else 0)
        d['top_line']      += ' SYSID 0x%x' % (self.ns_syid if self.ns_syid is not None else 0)
        d['top_line']      += ' %f' % ((self.rfss_chan if self.rfss_chan is not None else self.cc_list[self.cc_index]) / 1e6)
        d['top_line']      += '/%f' % ((self.rfss_txchan if self.rfss_txchan is not None else 0) / 1e6)
        d['top_line']      += ' tsbks %d' % (self.stats['tsbk_count'])
        d['nac'] = self.nac
        d['syid'] = self.rfss_syid
        d['rfid'] = self.rfss_rfid
        d['stid'] = self.rfss_stid
        d['sysid'] = self.ns_syid
        d['rxchan'] = self.rfss_chan
        d['txchan'] = self.rfss_txchan
        d['wacn'] = self.ns_wacn
        d['secondary'] = list(self.secondary.keys())
        d['frequencies']    = {}
        d['frequency_data'] = {}
        d['last_tsbk'] = self.last_tsbk
        t = time.time()
        self.expire_voice_frequencies(t)
        for f in list(self.voice_frequencies.keys()):
            vc0 = get_tgid(self.voice_frequencies[f]['tgid'][0])
            vc1 = get_tgid(self.voice_frequencies[f]['tgid'][1])
            if vc0 == vc1:  # if vc0 matches vc1 the channel is either idle or in phase 1 mode
                vc_tgs = "[   %5s   ]" % vc0
            else:
                vc_tgs = "[%5s|%5s]" % (vc1, vc0)
            d['frequencies'][f] = 'voice freq %f, active tgids %s, last seen %4.1fs, count %d' %  ((f/1e6), vc_tgs, t - self.voice_frequencies[f]['time'], self.voice_frequencies[f]['counter'])

            d['frequency_data'][f] = {'tgids': self.voice_frequencies[f]['tgid'], 'last_activity': '%7.1f' % (t - self.voice_frequencies[f]['time']), 'counter': self.voice_frequencies[f]['counter']}
        d['adjacent_data'] = self.adjacent_data
        return json.dumps(d)

#################
# Radio Id history class
class rid_history(object):
    def __init__(self, rids, maxlen = 5):
        self.rid_history = collections.deque((), maxlen)    # deque object self-trims when size would exceed maxlen elements
        self.rids = rids

        while len(self.rid_history) < self.rid_history.maxlen:
            self.rid_history.appendleft({"rid":None, "tgid":None, "ts":0.0})

    def record(self, rid, tgid, ts = time.time()):
        if rid is None:
            return

        if (self.rid_history[0]['rid'] == rid) and (self.rid_history[0]['tgid'] == tgid):
            self.rid_history[0]['ts'] = ts
        else:
            self.rid_history.appendleft({"rid": rid, "tgid": tgid, "ts": ts})

    def dump(self):
        sys.stderr.write("Last %d active radio ids {\n" % self.rid_history.maxlen)
        for rid_entry in reversed(self.rid_history):
            if rid_entry['rid'] is None:
                continue
            if rid_entry['rid'] in self.rids:
                rid_tag = self.rids[rid_entry['rid']]['tag']
            else:
                rid_tag = ""
            sys.stderr.write("@ %s rid(%s), rtag(%s), tg(%s)\n" % (log_ts.get(rid_entry['ts']), rid_entry['rid'], rid_tag.center(14)[:14], rid_entry['tgid']))
        sys.stderr.write("}\n")

#################
# P25 receiver class
class p25_receiver(object):
    def __init__(self, debug, msgq_id, frequency_set, nac_set, slot_set, system, config, meta_q = None, freq = 0):
        self.debug = debug
        self.msgq_id = msgq_id
        self.config = config
        self.frequency_set = frequency_set
        self.nac_set = nac_set
        self.slot_set = slot_set
        self.system = system
        self.meta_q = meta_q
        self.meta_stream = from_dict(self.config, 'meta_stream_name', "")
        self.tuned_frequency = freq
        self.tuner_idle = False
        self.voice_frequencies = self.system.get_frequencies()
        self.talkgroups = self.system.get_talkgroups()
        self.skiplist = {}
        self.blacklist = {}
        self.whitelist = None
        self.crypt_behavior = self.system.get_crypt_behavior()
        self.current_nac = 0
        self.current_tgid = None
        self.current_slot = None
        self.hold_tgid = None
        self.hold_until = 0.0
        self.hold_mode = False
        self.tgid_hold_time = TGID_HOLD_TIME
        self.vc_retries = 0

    def set_debug(self, dbglvl):
        self.debug = dbglvl

    def post_init(self):
        if self.debug >= 1:
            sys.stderr.write("%s [%d] Initializing P25 receiver: %s\n" % (log_ts.get(), self.msgq_id, from_dict(self.config, 'name', str(self.msgq_id))))
            if self.meta_q is None or self.meta_stream == "":
                sys.stderr.write("%s [%d] metadata updates not enabled\n" % (log_ts.get(), self.msgq_id))
            else:
                sys.stderr.write("%s [%d] metadata stream: %s\n" % (log_ts.get(), self.msgq_id, self.meta_stream))
            

        self.load_bl_wl()
        self.tgid_hold_time = float(from_dict(self.system.config, 'tgid_hold_time', TGID_HOLD_TIME))
        meta_update(self.meta_q, msgq_id=self.msgq_id)
        self.idle_rx()

    def load_bl_wl(self):
        if 'blacklist' in self.config and self.config['blacklist'] != "":
            sys.stderr.write("%s [%d] reading channel blacklist file: %s\n" % (log_ts.get(), self.msgq_id, self.config['blacklist']))
            self.blacklist = get_int_dict(self.config['blacklist'], self.msgq_id)
        else:
            self.blacklist = self.system.get_blacklist()

        if 'whitelist' in self.config and self.config['whitelist'] != "":
            sys.stderr.write("%s [%d] reading channel whitelist file: %s\n" % (log_ts.get(), self.msgq_id, self.config['whitelist']))
            self.whitelist = get_int_dict(self.config['whitelist'], self.msgq_id)
        else:
            self.whitelist = self.system.get_whitelist()

    def set_nac(self, nac):
        if self.current_nac != nac:
            self.current_nac = nac
            self.nac_set({'tuner': self.msgq_id,'nac': nac})

    def idle_rx(self):
        if not (self.tuner_idle or self.system.has_cc(self.msgq_id)): # don't idle a control channel or an already idle receiver
            if self.debug >= 5:
                sys.stderr.write("%s [%d] idling receiver\n" % (log_ts.get(), self.msgq_id))
            if self.slot_set is not None:
                self.slot_set({'tuner': self.msgq_id,'slot': 4})      # disable receiver (idle)
            self.tuner_idle = True
            self.current_slot = None

    def tune_cc(self, freq):
        if freq is None or int(freq) == 0:  # freq will be None when there is already another receiver listening to the control channel
            self.idle_rx()
            return

        if self.current_nac != self.system.get_nac():
            self.set_nac(self.system.get_nac())

        if self.tuner_idle:
            if self.slot_set is not None:
                self.slot_set({'tuner': self.msgq_id,'slot': 0})     # enable receiver
            self.tuner_idle = False
        if self.debug >= 5:
            sys.stderr.write("%s [%d] set control channel=%f\n" % (log_ts.get(), self.msgq_id, freq/1e6))
        tune_params = {'tuner':   self.msgq_id,
                       'sigtype': "P25",
                       'freq':    freq,
                       'rate':    self.system.cc_rate,
                       'tdma':    None}
        self.frequency_set(tune_params)
        self.tuned_frequency = freq
        self.current_slot = None

    def tune_voice(self, freq, tgid, slot):
        if freq is None or int(freq) == 0:
            return

        if self.tuner_idle:
            if self.slot_set is not None:
                self.slot_set({'tuner': self.msgq_id,'slot': 0})     # enable receiver
            self.tuner_idle = False
        else:
            if self.debug >= 5:
                sys.stderr.write("%s [%d] releasing control channel\n" % (log_ts.get(), self.msgq_id))
            self.system.release_cc(self.msgq_id)                 # release control channel responsibility

        if self.current_nac != self.system.get_nac():
            self.set_nac(self.system.get_nac())

        if (freq != self.tuned_frequency) or (slot != self.current_slot):
            nac, wacn, sysid, valid = self.system.get_tdma_params()
            if slot is not None and not valid:                   # Can only tune tdma voice channel if nac/wacn/sysid are known
                sys.stderr.write("%s [%d] cannot tune voice channel; wacn/sysid not yet known\n" % (log_ts.get(), self.msgq_id))
                return

            tune_params = {'tuner':   self.msgq_id,
                           'sigtype': "P25",
                           'freq':    get_frequency(freq),
                           'tgid':    tgid,
                           'rate':    4800 if slot is None else 6000,
                           'tdma':    slot,
                           'tag':     self.talkgroups[tgid]['tag'],
                           'system':  self.config['trunking_sysname'],
                           'nac':     nac,
                           'wacn':    wacn,
                           'sysid':   sysid}
            self.frequency_set(tune_params)
            self.tuned_frequency = freq

        self.vc_retries = 0
        self.current_tgid = tgid
        self.current_slot = slot
        self.talkgroups[tgid]['receiver'] = self

    def ui_command(self, cmd, data, curr_time):
        if self.debug > 10:
            sys.stderr.write("%s [%d] ui_command: cmd(%s), data(%d), time(%f)\n" % (log_ts.get(), self.msgq_id, cmd, data, curr_time))
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
        updated = 0
        m_proto = ctypes.c_int16(msg.type() >> 16).value  # upper 16 bits of msg.type() is signed protocol
        if m_proto != 0: # P25 m_proto=0
            return updated

        m_type = ctypes.c_int16(msg.type() & 0xffff).value
        m_rxid = int(msg.arg1()) >> 1
        m_ts = float(msg.arg2())

        if (m_type == -1):  # Channel Timeout
            updated += 1
            if self.current_tgid is None:
                if self.system.has_cc(self.msgq_id):
                    if self.debug > 0:
                        sys.stderr.write("%s [%d] control channel timeout, freq(%f)\n" % (log_ts.get(), self.msgq_id, (self.tuned_frequency/1e6)))
                    self.tune_cc(self.system.timeout_cc(self.msgq_id))
            else:
                if self.debug > 1:
                    sys.stderr.write("%s [%d] voice channel timeout, freq(%f)\n" % (log_ts.get(), self.msgq_id, (self.tuned_frequency/1e6)))
                self.vc_retries += 1
                if self.vc_retries >= VC_TIMEOUT_RETRIES:
                    self.expire_talkgroup(reason="timeout")
            return updated

        elif m_type == -3: # P25 call data (srcaddr, grpaddr, encryption)
            if self.debug > 10:
                sys.stderr.write("%s [%d] process_qmsg: P25 info: %s\n" % (log_ts.get(), self.msgq_id, msg.to_string()))
            js = json.loads(msg.to_string())
            grpaddr = from_dict(js, 'grpaddr', 0)
            srcaddr = from_dict(js, 'srcaddr', 0)
            encrypted = from_dict(js, 'encrypted', -1)
            algid = from_dict(js, 'algid', -1)
            keyid = from_dict(js, 'keyid', -1)

            if (self.current_tgid is None) or (grpaddr != 0 and grpaddr != self.current_tgid): # only consider data for current call
                return updated

            if encrypted >= 0 and algid >= 0 and keyid >= 0: # log and save encryption information
                if self.debug >= 5 and (algid != self.talkgroups[self.current_tgid]['algid'] or keyid != self.talkgroups[self.current_tgid]['keyid']):
                    sys.stderr.write('%s [%d] encrypt info: tg=%d, algid=0x%x, keyid=0x%x\n' % (log_ts.get(), self.msgq_id, self.current_tgid, algid, keyid))
                self.talkgroups[self.current_tgid]['encrypted'] = encrypted
                self.talkgroups[self.current_tgid]['algid'] = algid
                self.talkgroups[self.current_tgid]['keyid'] = keyid

            updated += self.system.update_talkgroup_srcaddr(curr_time, self.current_tgid, srcaddr)

            if self.crypt_behavior > 1:
                if self.talkgroups[self.current_tgid]['encrypted'] == 1:
                    updated += 1
                    if self.debug > 1:
                        sys.stderr.write('%s [%d] skipping encrypted tg(%d)\n' % (log_ts.get(), self.msgq_id, self.current_tgid))
                    self.add_skiplist(self.current_tgid, curr_time + TGID_SKIP_TIME)

        elif m_type == -4: # P25 sync established
            if self.current_tgid is None:
                if self.system.has_cc(self.msgq_id):
                    self.system.sync_cc()
            else:
                self.vc_retries = 0
            return updated

        elif m_type >= 0: # Channel Signaling (m_type is duid)
            s = msg.to_string()
            nac = get_ordinals(s[:2])   # first two bytes are NAC
            s = s[2:]
            if (nac != 0xffff) and (nac != self.system.get_nac()):
                return updated

            if   m_type ==  3: # call termination, no release
                pass

            elif m_type == 15: # call termination, with release
                self.expire_talkgroup(reason="duid15")
                updated += 1

            elif m_type == 16: # MAC_PTT
                mi    = get_ordinals(s[0:9])
                algid = get_ordinals(s[9:10])
                keyid = get_ordinals(s[10:12])
                sa    = get_ordinals(s[12:15])
                ga    = get_ordinals(s[15:17])
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] mac_ptt: mi: %x algid: %x keyid:%x ga: %d sa: %d\n' % (log_ts.get(), m_rxid, mi, algid, keyid, ga, sa))
                updated += self.system.update_talkgroup_srcaddr(curr_time, ga, sa)
                if algid != 0x80: # log and save encryption information
                    if self.debug >= 5 and (algid != self.talkgroups[ga]['algid'] or keyid != self.talkgroups[ga]['keyid']):
                        sys.stderr.write('%s [%d] encrypt info: tg=%d, algid=0x%x, keyid=0x%x\n' % (log_ts.get(), self.msgq_id, ga, algid, keyid))
                    if ga in self.talkgroups:
                        self.talkgroups[ga]['encrypted'] = 1
                        self.talkgroups[ga]['algid'] = algid
                        self.talkgroups[ga]['keyid'] = keyid
                    if self.crypt_behavior > 1:
                        updated += 1
                        if self.debug > 1:
                            sys.stderr.write('%s [%d] skipping encrypted tg(%d)\n' % (log_ts.get(), self.msgq_id, ga))
                        self.add_skiplist(ga, curr_time + TGID_SKIP_TIME)

            elif m_type == 17: # MAC_END_PTT
                sa    = get_ordinals(s[12:15])
                ga    = get_ordinals(s[15:17])
                if self.debug >= 10:
                    sys.stderr.write('%s [%d] mac_end_ptt: ga: %d sa: %d\n' % (log_ts.get(), m_rxid, ga, sa))
                self.system.update_talkgroup_srcaddr(curr_time, ga, sa)
                self.expire_talkgroup(reason="duid15")
                updated += 1

        return updated

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
            if self.debug > 1:
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
            sys.stderr.write("%s [%d] blacklisting: tgid(%d)\n" % (log_ts.get(), self.msgq_id, tgid))
        if self.current_tgid and self.current_tgid in self.blacklist:
            self.expire_talkgroup(reason = "blacklisted", auto_hold = False)
            self.hold_mode = False

    def add_whitelist(self, tgid):
        if not tgid or (tgid <= 0) or (tgid > 65534):
            if self.debug > 1:
                sys.stderr.write("%s [%d] whitelist tgid(%d) out of range (1-65534)\n" % (log_ts.get(), self.msgq_id, tgid))
            return
        if self.blacklist and tgid in self.blacklist:
            self.blacklist.pop(tgid)
            if self.debug > 1:
                sys.stderr.write("%s [%d] de-blacklisting: tgid(%d)\n" % (log_ts.get(), self.msgq_id, tgid))
        if self.whitelist is None:
            self.whitelist = {}
        if tgid in self.whitelist:
            return
        self.whitelist[tgid] = None
        if self.debug > 1:
            sys.stderr.write("%s [%d] whitelisting: tgid(%d)\n" % (log_ts.get(), self.msgq_id, tgid))
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
            if self.debug > 1:
                sys.stderr.write("%s [%d] removing expired blacklist: tg(%d)\n" % (log_ts.get(), self.msgq_id, tg));

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
        self.skiplist_update(start_time)
        self.blacklist_update(start_time)

        if (tgid is not None) and (tgid in self.talkgroups) and ((self.talkgroups[tgid]['receiver'] is None) or (self.talkgroups[tgid]['receiver'] == self)):
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
                if self.talkgroups[active_tgid]['receiver'] is None:
                    tgt_tgid = active_tgid
                    continue
            elif (self.talkgroups[active_tgid]['prio'] < self.talkgroups[tgt_tgid]['prio']) and (self.talkgroups[active_tgid]['receiver'] is None):
                tgt_tgid = active_tgid
                   
        if tgt_tgid is not None and self.talkgroups[tgt_tgid]['time'] >= start_time:
            return self.talkgroups[tgt_tgid]['frequency'], tgt_tgid, self.talkgroups[tgt_tgid]['tdma_slot'], self.talkgroups[tgt_tgid]['srcaddr']
        return None, None, None, None

    def scan_for_talkgroups(self, curr_time):
        if self.current_tgid is None and self.hold_tgid is not None and (curr_time < self.hold_until):
            freq, tgid, slot, src = self.find_talkgroup(curr_time, tgid=self.hold_tgid)
        else:
            freq, tgid, slot, src = self.find_talkgroup(curr_time, tgid=self.current_tgid)

        if self.current_tgid is not None and self.current_tgid == tgid:  # active call remains, nothing to do
            return

        if tgid is None:                                                 # no call
            return

        if self.current_tgid is None:
            if self.debug > 0:
                sys.stderr.write("%s [%d] voice update:  tg(%d), rid(%d), freq(%f), slot(%s), prio(%d)\n" % (log_ts.get(), self.msgq_id, tgid, self.talkgroups[tgid]['srcaddr'], (freq/1e6), get_slot(slot), self.talkgroups[tgid]['prio']))
            self.tune_voice(freq, tgid, slot)
        else:
            if self.debug > 0:
                sys.stderr.write("%s [%d] voice preempt: tg(%d), rid(%d), freq(%f), slot(%s), prio(%d)\n" % (log_ts.get(), self.msgq_id, tgid, self.talkgroups[tgid]['srcaddr'], (freq/1e6), get_slot(slot), self.talkgroups[tgid]['prio']))
            self.expire_talkgroup(update_meta=False, reason="preempt")
            self.tune_voice(freq, tgid, slot)

        meta_update(self.meta_q, tgid, self.talkgroups[tgid]['tag'], msgq_id=self.msgq_id)

    def expire_talkgroup(self, tgid=None, update_meta = True, reason="unk", auto_hold = True):
        if self.current_tgid is None:
            return
            
        self.talkgroups[self.current_tgid]['receiver'] = None
        self.talkgroups[self.current_tgid]['frequency'] = None
        self.talkgroups[self.current_tgid]['tdma_slot'] = None
        self.talkgroups[self.current_tgid]['srcaddr'] = 0
        if self.debug > 1:
            sys.stderr.write("%s [%d] releasing:  tg(%d), freq(%f), slot(%s), reason(%s)\n" % (log_ts.get(), self.msgq_id, self.current_tgid, (self.tuned_frequency/1e6), get_slot(self.current_slot), reason))
        if auto_hold:
            self.hold_tgid = self.current_tgid
            self.hold_until = time.time() + self.tgid_hold_time
        else:
            self.hold_until = time.time()
        self.current_tgid = None
        self.current_slot = None

        if reason == "preempt":                             # Do not retune or update metadata if in middle of tuning to a different tgid
            return

        if update_meta:
            meta_update(self.meta_q, msgq_id=self.msgq_id, ts=self.hold_until)  # Send Idle metadata update
        self.idle_rx()                                      # Make receiver available

    def hold_talkgroup(self, tgid, curr_time):
        if tgid > 0:
            if self.whitelist is not None and tgid not in self.whitelist:
                if self.debug > 1:
                    sys.stderr.write("%s [%d] hold tg(%d) not in whitelist\n" % (log_ts.get(), self.msgq_id, tgid))
                return
            add_default_tgid(self.talkgroups, tgid)
            self.hold_tgid = tgid
            self.hold_until = curr_time + 86400 * 10000
            self.hold_mode = True
            if self.debug > 1:
                sys.stderr.write ('%s [%d] set hold tg(%d) until %f\n' % (log_ts.get(), self.msgq_id, self.hold_tgid, self.hold_until))
            if self.current_tgid != self.hold_tgid:
                self.expire_talkgroup(reason="new hold", auto_hold = False)
                self.current_tgid = self.hold_tgid
        elif self.hold_mode is False:
            if self.current_tgid:
                self.hold_tgid = self.current_tgid
                self.hold_until = curr_time + 86400 * 10000
                self.hold_mode = True
                if self.debug > 1:
                    sys.stderr.write ('%s [%d] set hold tg(%d) until %f\n' % (log_ts.get(), self.msgq_id, self.hold_tgid, self.hold_until))
        elif self.hold_mode is True:
            if self.debug > 1:
                sys.stderr.write ('%s [%d] clear hold tg(%d)\n' % (log_ts.get(), self.msgq_id, self.hold_tgid))
            self.hold_tgid = None
            self.hold_until = curr_time
            self.hold_mode = False
            self.expire_talkgroup(reason="clear hold", auto_hold = False)

    def get_status(self):
        cc_tag = "Control Channel" if self.system.has_cc(self.msgq_id) else None
        d = {}
        d['freq'] = self.tuned_frequency
        d['tdma'] = self.current_slot
        d['tgid'] = self.current_tgid
        d['system'] = self.config['trunking_sysname']
        d['tag'] = self.talkgroups[self.current_tgid]['tag'] if self.current_tgid is not None else cc_tag
        d['srcaddr'] = self.talkgroups[self.current_tgid]['srcaddr'] if self.current_tgid is not None else 0
        d['srctag'] = self.system.get_rid_tag(self.talkgroups[self.current_tgid]['srcaddr']) if self.current_tgid is not None else ""
        d['encrypted'] = self.talkgroups[self.current_tgid]['encrypted'] if self.current_tgid is not None else 0
        d['mode'] = None
        d['stream'] = self.meta_stream
        d['msgqid'] = self.msgq_id
        return json.dumps(d)

