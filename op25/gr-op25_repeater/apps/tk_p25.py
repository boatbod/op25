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
from gnuradio import gr

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

def meta_update(meta_q, tgid = None, tag = None, msgq_id = 0):
    if meta_q is None:
        return
    d = {'json_type': 'meta_update'}
    d['tgid'] = tgid
    d['tag'] = tag
    msg = gr.message().make_from_string(json.dumps(d), -2, time.time(), 0)
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
                self.receivers[rx]['rx_rcvr'].post_init()

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
            if m_type == 7 or m_type == 12:                                                 # send TSBKs and MBTs messages to p25_system object
                updated += self.systems[self.receivers[m_rxid]['sysname']]['system'].process_qmsg(msg, curr_time)
            else:
                updated += self.receivers[m_rxid]['rx_rcvr'].process_qmsg(msg, curr_time)   # send in-call messaging to p25_receiver objects

            if updated > 0:
                for rx in self.systems[self.receivers[m_rxid]['sysname']]['receivers']:     # only have voice receivers scan for activity if something changed
                    rx.scan_for_talkgroups(curr_time)

    # ui_command handles all requests from user interface
    def ui_command(self, cmd, data, msgq_id):
        curr_time = time.time()
        if msgq_id in self.receivers and self.receivers[msgq_id]['rx_rcvr'] is not None:
            self.receivers[msgq_id]['rx_rcvr'].ui_command(cmd = cmd, data = data, curr_time = curr_time)    # Dispatch message to the intended receiver

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
        self.patches = {}
        self.blacklist = {}
        self.whitelist = None
        self.crypt_behavior = 1
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
        self.nac = int(eval(from_dict(config, "nac", "0")))
        self.last_expiry_check = 0.0
        self.stats = {}
        self.stats['tsbk_count'] = 0

        sys.stderr.write("%s [%s] Initializing P25 system\n" % (log_ts.get(), self.sysname))

        if 'tgid_tags_file' in self.config and self.config['tgid_tags_file'] != "":
            sys.stderr.write("%s [%s] reading system tgid_tags_file: %s\n" % (log_ts.get(), self.sysname, self.config['tgid_tags_file']))
            self.read_tags_file(self.config['tgid_tags_file'])

        if 'blacklist' in self.config and self.config['blacklist'] != "":
            sys.stderr.write("%s [%s] reading system blacklist file: %s\n" % (log_ts.get(), self.sysname, self.config['blacklist']))
            self.blacklist = get_int_dict(self.config['blacklist'], self.sysname)

        if 'whitelist' in self.config and self.config['whitelist'] != "":
            sys.stderr.write("%s [%s] reading system whitelist file: %s\n" % (log_ts.get(), self.sysname, self.config['whitelist']))
            self.whitelist = get_int_dict(self.config['whitelist'], self.sysname)

        self.crypt_behavior = int(from_dict(self.config, 'crypt_behavior', 1))

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
        with open(tags_file, 'r') as csvfile:
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
                    add_default_tgid(self.talkgroups, tgid)
                self.talkgroups[tgid]['tag'] = tag
                self.talkgroups[tgid]['prio'] = prio
                if self.debug > 1:
                    sys.stderr.write("%s [%s] setting tgid(%d), prio(%d), tag(%s)\n" % (log_ts.get(), self.sysname, tgid, prio, tag))

    def get_cc(self, msgq_id):
        if msgq_id is None:
            return None

        if (self.cc_msgq_id is None) or (msgq_id == self.cc_msgq_id):
            self.cc_msgq_id = msgq_id

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
        if m_type == 7 and self.valid_cc(m_rxid): # TSBK
            t = get_ordinals(s)
            updated += self.decode_tsbk(m_rxid, t)

        elif m_type == 12 and self.valid_cc(m_rxid): # MBT
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

        updated += self.expire_patches()
        return updated

    def decode_mbt_data(self, m_rxid, opcode, src, header, mbt_data):
        self.cc_timeouts = 0
        self.last_tsbk = time.time()
        self.stats['tsbk_count'] += 1
        updated = 0
        if self.debug > 10:
            sys.stderr.write('%s [%d] decode_mbt_data: %x %x\n' %(log_ts.get(), m_rxid, opcode, mbt_data))
        if opcode == 0x0:  # grp voice channel grant
            ch1  = (mbt_data >> 64) & 0xffff
            ch2  = (mbt_data >> 48) & 0xffff
            ga   = (mbt_data >> 32) & 0xffff
            f = self.channel_id_to_frequency(ch1)
            self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1), srcaddr=src)
            if f:
                updated += 1
            if self.debug > 10:
                sys.stderr.write('%s [%d] mbt00 voice grant ch1 %x ch2 %x addr 0x%x\n' %(log_ts.get(), m_rxid, ch1, ch2, ga))
        if opcode == 0x02: # grp regroup voice channel grant
            mfrid  = (mbt_data >> 168) & 0xff
            if mfrid == 0x90:    # MOT_GRG_CN_GRANT_EXP
                ch1  = (mbt_data >> 80) & 0xffff
                ch2  = (mbt_data >> 64) & 0xffff
                sg   = (mbt_data >> 48) & 0xffff
                f = self.channel_id_to_frequency(ch1)
                self.update_voice_frequency(f, tgid=sg, tdma_slot=self.get_tdma_slot(ch1), srcaddr=src)
                if f:
                    updated += 1
                if self.debug > 10:
                    sys.stderr.write('%s [%d] mbt02 voice regroup grant ch1 %x ch2 %x addr 0x%x\n' %(log_ts.get(), m_rxid, ch1, ch2, ga))
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
            if self.debug > 10:
                sys.stderr.write('%s [%d] mbt3c adjacent sys %x rfid %x stid %x ch1 %x ch2 %x f1 %s f2 %s\n' % (log_ts.get(), m_rxid, syid, rfid, stid, ch1, ch2, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
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
            if self.debug > 10:
                sys.stderr.write('%s [%d] mbt3b net stat sys %x wacn %x ch1 %s ch2 %s\n' %(log_ts.get(), m_rxid, syid, wacn, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
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
            if self.debug > 10:
                sys.stderr.write('%s [%d] mbt3a rfss stat sys %x rfid %x stid %x ch1 %s ch2 %s\n' %(log_ts.get(), m_rxid, syid, rfid, stid, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
        return updated

    def decode_tsbk(self, m_rxid, tsbk):
        self.cc_timeouts = 0
        self.last_tsbk = time.time()
        self.stats['tsbk_count'] += 1
        updated = 0
        tsbk = tsbk << 16    # for missing crc
        opcode = (tsbk >> 88) & 0x3f
        if self.debug > 10:
            sys.stderr.write('%s [%d] TSBK: 0x%02x 0x%024x\n' % (log_ts.get(), m_rxid, opcode, tsbk))
        if opcode == 0x00:   # group voice chan grant
            mfrid  = (tsbk >> 80) & 0xff
            if mfrid == 0x90:    # MOT_GRG_ADD_CMD
                sg   = (tsbk >> 64) & 0xffff
                ga1  = (tsbk >> 48) & 0xffff
                ga2  = (tsbk >> 32) & 0xffff
                ga3  = (tsbk >> 16) & 0xffff
                if self.debug > 10:
                    sys.stderr.write('%s [%d] MOT_GRG_ADD_CMD(0x00): sg:%d ga1:%d ga2:%d ga3:%d\n' % (log_ts.get(), m_rxid, sg, ga1, ga2, ga3))
                self.add_patch(sg, ga1, ga2, ga3)
            else:
                opts = (tsbk >> 72) & 0xff
                ch   = (tsbk >> 56) & 0xffff
                ga   = (tsbk >> 40) & 0xffff
                sa   = (tsbk >> 16) & 0xffffff
                f = self.channel_id_to_frequency(ch)
                self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch), srcaddr=sa)
                if f:
                    updated += 1
                if self.debug > 10:
                    sys.stderr.write('%s [%d] tsbk00 grant freq %s ga %d sa %d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch), ga, sa))
        elif opcode == 0x01:   # reserved
            mfrid  = (tsbk >> 80) & 0xff
            if mfrid == 0x90: #MOT_GRG_DEL_CMD
                sg   = (tsbk >> 64) & 0xffff
                ga1  = (tsbk >> 48) & 0xffff
                ga2  = (tsbk >> 32) & 0xffff
                ga3  = (tsbk >> 16) & 0xffff
                if self.debug > 10:
                    sys.stderr.write('%s [%d] MOT_GRG_DEL_CMD(0x01): sg:%d ga1:%d ga2:%d ga3:%d\n' % (log_ts.get(), m_rxid, sg, ga1, ga2, ga3))
                self.del_patch(sg, ga1, ga2, ga3)
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
                if self.debug > 10:
                    sys.stderr.write('%s [%d] MOT_GRG_CN_GRANT(0x02): freq %s sg:%d sa:%d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch), sg, sa))
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
                if self.debug > 10:
                    sys.stderr.write('%s [%d] tsbk02 grant update: chan %s %d %s %d\n' %(log_ts.get(), m_rxid, self.channel_id_to_string(ch1), ga1, self.channel_id_to_string(ch2), ga2))
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
                if self.debug > 10:
                    sys.stderr.write('%s [%d] MOT_GRG_CN_GRANT_UPDT(0x03): freq %s sg1:%d freq %s sg2:%d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch1), sg1, self.channel_id_to_string(ch2), sg2))
            elif mfrid == 0:
                ch1  = (tsbk >> 48) & 0xffff
                ch2   = (tsbk >> 32) & 0xffff
                ga  = (tsbk >> 16) & 0xffff
                f = self.channel_id_to_frequency(ch1)
                self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1))
                if f:
                    updated += 1
                if self.debug > 10:
                    sys.stderr.write('%s [%d] tsbk03: freq-t %s freq-r %s ga:%d\n' % (log_ts.get(), m_rxid, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2), ga))

        elif opcode == 0x16:   # sndcp data ch
            ch1  = (tsbk >> 48) & 0xffff
            ch2  = (tsbk >> 32) & 0xffff
            if self.debug > 10:
                sys.stderr.write('%s [%d] tsbk16 sndcp data ch: chan %x %x\n' % (log_ts.get(), m_rxid, ch1, ch2))
        elif opcode == 0x28:   # grp_aff_rsp
            mfrid  = (tsbk >> 80) & 0xff
            lg     = (tsbk >> 79) & 0x01
            gav    = (tsbk >> 72) & 0x03
            aga    = (tsbk >> 56) & 0xffff
            ga     = (tsbk >> 40) & 0xffff
            ta     = (tsbk >> 16) & 0xffffff
            if self.debug > 10:
                sys.stderr.write('%s [%d] tsbk28 grp_aff_resp: mfrid: 0x%x, gav: %d, aga: %d, ga: %d, ta: %d\n' % (log_ts.get(), m_rxid, mfrid, gav, aga, ga, ta))
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
                if self.debug > 10:
                    sys.stderr.write('%s [%d] GRG_EXENC_CMD(0x30): grg_t:%d, grg_g:%d, grg_a:%d, grg_ssn:%d, sg:%d, keyid:%d, rta:%d\n' % (log_ts.get(), m_rxid, grg_t, grg_g, grg_a, grg_ssn, sg, keyid, rta))
                if grg_a == 1: # Activate
                    if grg_g == 1: # Group request
                        algid = (rta >> 16) & 0xff
                        ga    =  rta        & 0xffff
                        self.add_patch(sg, ga, ga, ga)
                    else:          # Unit request (currently unhandled)
                        pass
                else:          # Deactivate
                    self.del_patch(sg, 0, 0, 0)
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
            if self.debug > 10:
                sys.stderr.write('%s [%d] tsbk34 iden vhf/uhf id %d toff %f spac %f freq %f [%s]\n' % (log_ts.get(), m_rxid, iden, toff * spac * 0.125 * 1e-3, spac * 0.125, freq * 0.000005, txt[toff_sign]))
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
                if self.debug > 10:
                    sys.stderr.write('%s [%d] tsbk33 iden up tdma id %d f %d offset %d spacing %d slots/carrier %d\n' % (log_ts.get(), m_rxid, iden, self.freq_table[iden]['frequency'], self.freq_table[iden]['offset'], self.freq_table[iden]['step'], self.freq_table[iden]['tdma']))
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
            if self.debug > 10:
                sys.stderr.write('%s [%d] tsbk3d iden id %d toff %f spac %f freq %f\n' % (log_ts.get(), m_rxid, iden, toff * 0.25, spac * 0.125, freq * 0.000005))
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
            if self.debug > 10:
                sys.stderr.write('%s [%d] tsbk3a rfss status: syid: %x rfid %x stid %d ch1 %x(%s)\n' %(log_ts.get(), m_rxid, syid, rfid, stid, chan, self.channel_id_to_string(chan)))
        elif opcode == 0x39:   # secondary cc
            rfid = (tsbk >> 72) & 0xff
            stid = (tsbk >> 64) & 0xff
            ch1  = (tsbk >> 48) & 0xffff
            ch2  = (tsbk >> 24) & 0xffff
            f1 = self.channel_id_to_frequency(ch1)
            f2 = self.channel_id_to_frequency(ch2)
            if f1 and f2:
                self.secondary[ f1 ] = 1
                self.secondary[ f2 ] = 1
                sorted_freqs = collections.OrderedDict(sorted(self.secondary.items()))
                self.secondary = sorted_freqs
            if self.debug > 10:
                sys.stderr.write('%s [%d] tsbk39 secondary cc: rfid %x stid %d ch1 %x(%s) ch2 %x(%s)\n' %(log_ts.get(), m_rxid, rfid, stid, ch1, self.channel_id_to_string(ch1), ch2, self.channel_id_to_string(ch2)))
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
            if self.debug > 10:
                sys.stderr.write('%s [%d] tsbk3b net stat: wacn %x syid %x ch1 %x(%s)\n' %(log_ts.get(), m_rxid, wacn, syid, ch1, self.channel_id_to_string(ch1)))
        elif opcode == 0x3c:   # adjacent status
            rfid = (tsbk >> 48) & 0xff
            stid = (tsbk >> 40) & 0xff
            ch1  = (tsbk >> 24) & 0xffff
            table = (ch1 >> 12) & 0xf
            f1 = self.channel_id_to_frequency(ch1)
            if f1 and table in self.freq_table:
                self.adjacent[f1] = 'rfid: %d stid:%d uplink:%f tbl:%d' % (rfid, stid, (f1 + self.freq_table[table]['offset']) / 1000000.0, table)
                self.adjacent_data[f1] = {'rfid': rfid, 'stid':stid, 'uplink': f1 + self.freq_table[table]['offset'], 'table': table}
            if self.debug > 10:
                sys.stderr.write('%s [%d] tsbk3c adjacent: rfid %x stid %d ch1 %x(%s)\n' %(log_ts.get(), m_rxid, rfid, stid, ch1, self.channel_id_to_string(ch1)))
                if table in self.freq_table:
                    sys.stderr.write('%s [%d] tsbk3c : %s %s\n' % (log_ts.get(), m_rxid, self.freq_table[table]['frequency'] , self.freq_table[table]['step'] ))
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
                sys.stderr.write("%s [%s] VF change: tgid: %s, prev_freq: %f, prev_slot: %s, new_freq: %f, new_slot: %s\n" % (log_ts.get(), self.sysname, tgid, prev_freq, prev_slot, frequency, tdma_slot))
            if prev_slot is None:
                self.voice_frequencies[prev_freq]['tgid'] = [None, None]
            else:
                self.voice_frequencies[prev_freq]['tgid'][prev_slot] = None
        curr_time = time.time()
        self.voice_frequencies[frequency]['time'] = curr_time
        self.voice_frequencies[frequency]['counter'] += 1
        if tdma_slot is None:   # FDMA mark both slots with same info
            if self.debug >= 10:
                sys.stderr.write("%s [%s] VF ts ph1: tgid: %s, freq: %f\n" % (log_ts.get(), self.sysname, tgid, frequency))
            for slot in [0, 1]:
                self.voice_frequencies[frequency]['tgid'][slot] = tgid
                self.voice_frequencies[frequency]['ts'][slot] = curr_time
        else:                   # TDMA mark just slot in use
            if self.debug >= 10:
                sys.stderr.write("%s [%s] VF ts ph2: tgid: %s, freq: %f, slot: %s\n" % (log_ts.get(), self.sysname, tgid, frequency, tdma_slot))
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
                        sys.stderr.write("%s [%s] VF expire: tgid: %s, freq: %f, slot: %s, ts: %s\n" % (log_ts.get(), self.sysname, tgid, frequency, slot, log_ts.get(self.voice_frequencies[frequency]['ts'][slot])))
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
        self.talkgroups[tgid]['frequency'] = frequency
        self.talkgroups[tgid]['tdma_slot'] = tdma_slot
        if (self.talkgroups[tgid]['receiver'] is None) or (srcaddr > 0): # don't overwrite with a null srcaddr for active calls
            self.talkgroups[tgid]['srcaddr']

    def expire_talkgroups(self, curr_time):
        if curr_time < self.last_expiry_check + EXPIRY_TIMER:
            return

        self.last_expiry_check = curr_time
        for tgid in self.talkgroups:
            if (self.talkgroups[tgid]['receiver'] is not None) and (curr_time >= self.talkgroups[tgid]['time'] + TGID_EXPIRY_TIME):
                if self.debug > 1:
                    sys.stderr.write("%s [%s] expiring tg(%d), freq(%f), slot(%s)\n" % (log_ts.get(), self.sysname, tgid, (self.talkgroups[tgid]['frequency']/1e6), get_slot(self.talkgroups[tgid]['tdma_slot'])))
                self.talkgroups[tgid]['receiver'].expire_talkgroup(reason="expiry")

    def add_patch(self, sg, ga1, ga2, ga3):
        if sg not in self.patches:
            self.patches[sg] = {}
            self.patches[sg]['ga'] = set()
            self.patches[sg]['ts'] = time.time()

        for ga in [ga1, ga2, ga3]:
            if (ga != sg):
                self.patches[sg]['ts'] = time.time() # update timestamp
                if ga not in self.patches[sg]['ga']:
                    self.patches[sg]['ga'].add(ga)
                    if self.debug >= 5:
                        sys.stderr.write("%s [%s] add_patch: tgid(%d) is patched to sg(%d)\n" % (log_ts.get(), self.sysname, ga, sg))

        if len(self.patches[sg]['ga']) == 0:
            del self.patches[sg]

    def del_patch(self, sg, ga1, ga2, ga3):
        if sg not in self.patches:
            return

        for ga in [ga1, ga2, ga3]:
            if ga in self.patches[sg]['ga']:
                self.patches[sg]['ga'].discard(ga)
                if self.debug >= 5:
                    sys.stderr.write("%s [%s] del_patch: tgid(%d) is unpatched from sg(%d)\n" % (log_ts.get(), self.sysname, ga, sg))

        if ((ga1, ga2, ga3) == (0, 0, 0)) or (len(self.patches[sg]['ga']) == 0):
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

    def dump_tgids(self):
        sys.stderr.write("Known tgids: { ")
        for tgid in sorted(self.talkgroups.keys()):
            sys.stderr.write("%d " % tgid);
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
        self.tune_cc(self.system.get_cc(self.msgq_id))
        meta_update(self.meta_q, msgq_id=self.msgq_id)

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
        self.current_nac = nac
        self.nac_set({'tuner': self.msgq_id,'nac': nac})

    def tune_cc(self, freq):
        if freq is None or int(freq) == 0:  # freq will be None when there is already another receiver listening to the control channel
            if not self.tuner_idle:
                if self.debug >= 5:
                    sys.stderr.write("%s [%d] idling receiver\n" % (log_ts.get(), self.msgq_id))
                self.slot_set({'tuner': self.msgq_id,'slot': 4}) # disable receiver (idle)
                self.tuner_idle = True
                self.current_slot = None
            return

        if self.current_nac != self.system.get_nac():
            self.set_nac(self.system.get_nac())

        if self.tuner_idle:
            self.slot_set({'tuner': self.msgq_id,'slot': 0})     # enable receiver
            self.tuner_idle = False
        if self.debug >= 5:
            sys.stderr.write("%s [%d] set control channel=%f\n" % (log_ts.get(), self.msgq_id, freq/1e6))
        tune_params = {'tuner':   self.msgq_id,
                       'sigtype': "P25",
                       'freq':    freq,
                       'tdma':    None}
        self.frequency_set(tune_params)
        self.tuned_frequency = freq
        self.current_slot = None

    def tune_voice(self, freq, tgid, slot):
        if freq is None or int(freq) == 0:
            return

        if self.tuner_idle:
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
                if self.debug > 0:
                    sys.stderr.write("%s [%d] control channel timeout\n" % (log_ts.get(), self.msgq_id))
                self.tune_cc(self.system.timeout_cc(self.msgq_id))
            else:
                if self.debug > 1:
                    sys.stderr.write("%s [%d] voice channel timeout\n" % (log_ts.get(), self.msgq_id))
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
                    sys.stderr.write('%s [%d] encrypt info tg=%d, algid=0x%x, keyid=0x%x\n' % (log_ts.get(), self.msgq_id, self.current_tgid, algid, keyid))
                self.talkgroups[self.current_tgid]['encrypted'] = encrypted
                self.talkgroups[self.current_tgid]['algid'] = algid
                self.talkgroups[self.current_tgid]['keyid'] = keyid

            if srcaddr > 0:
                self.talkgroups[self.current_tgid]['srcaddr'] = srcaddr

            if self.crypt_behavior > 1:
                if self.talkgroups[self.current_tgid]['encrypted'] == 1:
                    updated += 1
                    if self.debug > 1:
                        sys.stderr.write('%s [%d] skipping encrypted tg(%d)\n' % (log_ts.get(), self.msgq_id, self.current_tgid))
                    self.add_skiplist(self.current_tgid, curr_time + TGID_SKIP_TIME)

        elif m_type == -4: # P25 sync established
            return updated

        elif m_type >= 0: # Channel Signaling (m_type is duid)
            s = msg.to_string()
            nac = get_ordinals(s[:2])   # first two bytes are NAC
            if (nac != 0xffff) and (nac != self.system.get_nac()):
                return updated

            if   m_type ==  3: # call termination, no release
                return updated
            elif m_type == 15: # call termination, with release
                updated += 1
                self.expire_talkgroup(reason="duid15")
                return updated
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
            self.expire_talkgroup(reason = "blacklisted")
            self.hold_mode = False
            self.hold_tgid = None
            self.hold_until = time.time()

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

        if tgid is None:                                                 # no call, check if we need to assume control channel
            if self.tuner_idle:
                self.tune_cc(self.system.get_cc(self.msgq_id))
            return

        if self.current_tgid is None:
            if self.debug > 0:
                sys.stderr.write("%s [%d] voice update:  tg(%d), freq(%f), slot(%s), prio(%d)\n" % (log_ts.get(), self.msgq_id, tgid, (freq/1e6), get_slot(slot), self.talkgroups[tgid]['prio']))
            self.tune_voice(freq, tgid, slot)
        else:
            if self.debug > 0:
                sys.stderr.write("%s [%d] voice preempt: tg(%d), freq(%f), slot(%s), prio(%d)\n" % (log_ts.get(), self.msgq_id, tgid, (freq/1e6), get_slot(slot), self.talkgroups[tgid]['prio']))
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
            self.hold_until = time.time() + TGID_HOLD_TIME
        self.current_tgid = None
        self.current_slot = None

        if reason == "preempt":                         # Do not retune or update metadata if in middle of tuning to a different tgid
            return

        if update_meta:
            meta_update(self.meta_q, msgq_id=self.msgq_id)                    # Send Idle metadata update
        self.tune_cc(self.system.get_cc(self.msgq_id))  # Retune to control channel (if needed)

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
        d['encrypted'] = self.talkgroups[self.current_tgid]['encrypted'] if self.current_tgid is not None else 0
        d['mode'] = None
        d['stream'] = self.meta_stream
        d['msgqid'] = self.msgq_id
        return json.dumps(d)

