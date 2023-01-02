# Copyright 2011, 2012, 2013, 2014, 2015, 2016, 2017 Max H. Parke KA1RBI
# Copyright 2017, 2018, 2019, 2020, 2021 Graham Norbury
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
import collections
import json
import ast
sys.path.append('tdma')
import lfsr
from helper_funcs import *
from log_ts import log_ts
from gnuradio import gr
import gnuradio.op25_repeater as op25_repeater

def get_tgid(tgid):
    if tgid is not None:
        return str(tgid)
    else:
        return ""

class trunked_system (object):
    def __init__(self, debug=0, config=None, wildcard=False, rxctl=None):
        self.debug = debug
        self.wildcard_tsys = wildcard
        self.freq_table = {}
        self.stats = {}
        self.stats['tsbks'] = 0
        self.stats['crc'] = 0
        self.tsbk_cache = {}
        self.secondary = {}
        self.adjacent = {}
        self.adjacent_data = {}
        self.rfss_syid = 0
        self.rfss_rfid = 0
        self.rfss_stid = 0
        self.rfss_chan = 0
        self.rfss_txchan = 0
        self.ns_syid = -1
        self.ns_wacn = -1
        self.ns_chan = 0
        self.voice_frequencies = {}
        self.skiplist = {}
        self.blacklist = {}
        self.whitelist = None
        self.tgid_map = {}
        self.offset = 0
        self.sysname = 0
        self.rxctl = rxctl

        self.trunk_cc = 0
        self.last_trunk_cc = 0
        self.cc_list = []
        self.cc_list_index = -1
        self.cc_timeouts = -1
        self.CC_HUNT_TIME = 5.0
        self.PATCH_EXPIRY_TIME = 20.0
        self.FREQ_EXPIRY_TIME = 1.2
        self.center_frequency = 0
        self.last_tsbk = 0
        self.talkgroups = {}
        self.patches ={}
        if config:
            self.blacklist = config['blacklist']
            self.whitelist = config['whitelist']
            self.tgid_map  = config['tgid_map']
            self.offset    = config['offset']
            self.sysname   = config['sysname']
            self.cc_list   = config['cclist']
            self.center_frequency = config['center_frequency']
            self.modulation = config['modulation']
            self.hunt_cc(time.time())

    def set_debug(self, dbglvl):
        self.debug = dbglvl

    def reset(self):
        self.freq_table = {}
        self.stats = {}
        self.stats['tsbks'] = 0
        self.stats['crc'] = 0
        self.tsbk_cache = {}
        self.secondary = {}
        self.adjacent = {}
        self.adjacent_data = {}
        self.rfss_syid = 0
        self.rfss_rfid = 0
        self.rfss_stid = 0
        self.rfss_chan = 0
        self.rfss_txchan = 0
        self.ns_syid = -1
        self.ns_wacn = -1
        self.ns_chan = 0
        self.voice_frequencies = {}
        self.last_tsbk = 0
        self.cc_timeouts = 0
        self.talkgroups = {}

    def to_json(self, curr_tgid):
        d = {}
        d['top_line']  = 'WACN 0x%x' % (self.ns_wacn)
        d['top_line'] += ' SYSID 0x%x' % (self.ns_syid)
        d['top_line'] += ' %f' % (self.rfss_chan/ 1000000.0)
        d['top_line'] += '/%f' % (self.rfss_txchan/ 1000000.0)
        d['top_line'] += ' tsbks %d' % (self.stats['tsbks'])
        d['syid'] = self.rfss_syid
        d['rfid'] = self.rfss_rfid
        d['stid'] = self.rfss_stid
        d['sysid'] = self.ns_syid
        d['rxchan'] = self.rfss_chan
        d['txchan'] = self.rfss_txchan
        d['wacn'] = self.ns_wacn
        d['secondary'] = list(self.secondary.keys())
        d['frequencies'] = {}
        d['frequency_data'] = {}
        d['last_tsbk'] = self.last_tsbk
        d['tsbks'] = self.stats['tsbks']
        t = time.time()
        self.expire_voice_frequencies(t, curr_tgid)
        for f in list(self.voice_frequencies.keys()):
            vc0 = get_tgid(self.voice_frequencies[f]['tgid'][0])
            vc1 = get_tgid(self.voice_frequencies[f]['tgid'][1])
            if vc0 == vc1:  # if vc0 matches vc1 the channel is either idle or in phase 1 mode
                vc_tgs = "[   %5s   ]" % vc0
            else:
                vc_tgs = "[%5s|%5s]" % (vc1, vc0)
            d['frequencies'][f] = 'voice freq %f, active tgids %s, last seen %4.1fs, count %d' %  (f / 1000000.0, vc_tgs, t - self.voice_frequencies[f]['time'], self.voice_frequencies[f]['counter'])

            d['frequency_data'][f] = {'tgids': self.voice_frequencies[f]['tgid'], 'last_activity': '%7.1f' % (t - self.voice_frequencies[f]['time']), 'counter': self.voice_frequencies[f]['counter']}
        d['adjacent_data'] = self.adjacent_data
        return json.dumps(d)

    def to_string(self):
        s = []
        s.append('rf: syid %x rfid %d stid %d frequency %f uplink %f' % ( self.rfss_syid, self.rfss_rfid, self.rfss_stid, float(self.rfss_chan) / 1000000.0, float(self.rfss_txchan) / 1000000.0))
        s.append('net: syid %x wacn %x frequency %f' % ( self.ns_syid, self.ns_wacn, float(self.ns_chan) / 1000000.0))
        s.append('secondary control channel(s): %s' % ','.join(['%f' % (float(k) / 1000000.0) for k in list(self.secondary.keys())]))
        s.append('stats: tsbks %d crc %d' % (self.stats['tsbks'], self.stats['crc']))
        s.append('')
        t = time.time()
        for f in self.voice_frequencies:
            vc0 = get_tgid(self.voice_frequencies[f]['tgid'][0])
            vc1 = get_tgid(self.voice_frequencies[f]['tgid'][1])
            if vc0 == vc1:  # if vc0 matches vc1 the channel is either idle or in phase 1 mode
                vc_tgs = "[   %5s   ]" % vc0
            else:
                vc_tgs = "[%5s|%5s]" % (vc1, vc0)
            s.append('voice freq %f, active tgids %s, last seen %4.1fs, count %d' %  (f / 1000000.0, vc_tgs, t - self.voice_frequencies[f]['time'], self.voice_frequencies[f]['counter']))
        s.append('')
        for table in self.freq_table:
            a = self.freq_table[table]['frequency'] / 1000000.0
            b = self.freq_table[table]['step'] / 1000000.0
            c = self.freq_table[table]['offset'] / 1000000.0
            s.append('tbl-id: %x frequency: %f step %f offset %f' % ( table, a,b,c))
        for f in self.adjacent:
            s.append('adjacent %f: %s' % (float(f) / 1000000.0, self.adjacent[f]))
        return '\n'.join(s)

    def get_tdma_slot(self, id):
        table = (id >> 12) & 0xf
        channel = id & 0xfff
        if table not in self.freq_table:
            return None
        if 'tdma' not in self.freq_table[table]:
            return None
        if self.freq_table[table]['tdma'] < 2:
            return None
        return channel & 1 # TODO: this isn't going to work with more than 2 slots per channel!

# return frequency in Hz
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

    def get_tag(self, tgid):
        if not tgid:
            return ""
        if tgid not in self.tgid_map:
            return ""
        return self.tgid_map[tgid][0]

    def get_prio(self, tgid):
        if (not tgid) or (tgid not in self.tgid_map):
            return 3
        return self.tgid_map[tgid][1]

    def update_talkgroups(self, frequency, tgid, tdma_slot, srcaddr):
        self.update_talkgroup(frequency, tgid, tdma_slot, srcaddr)
        if tgid in self.patches:
            for ptgid in self.patches[tgid]['ga']:
                self.update_talkgroup(frequency, ptgid, tdma_slot, srcaddr)
                if self.debug >= 5:
                    sys.stderr.write('%s update_talkgroups: sg(%d) patched tgid(%d)\n' % (log_ts.get(), tgid, ptgid))

    def update_talkgroup(self, frequency, tgid, tdma_slot, srcaddr):
        if self.debug >= 5:
            sys.stderr.write('%s set tgid=%s, srcaddr=%s\n' % (log_ts.get(), tgid, srcaddr))
        
        if tgid not in self.talkgroups:
            self.talkgroups[tgid] = {'counter':0}
            if self.debug >= 5:
                sys.stderr.write('%s new tgid=%s %s prio %d\n' % (log_ts.get(), tgid, self.get_tag(tgid), self.get_prio(tgid)))
        self.talkgroups[tgid]['time'] = time.time()
        self.talkgroups[tgid]['frequency'] = frequency
        self.talkgroups[tgid]['tdma_slot'] = tdma_slot
        self.talkgroups[tgid]['srcaddr'] = srcaddr
        self.talkgroups[tgid]['prio'] = self.get_prio(tgid)

    def update_talkgroup_srcaddr(self, curr_time, tgid, srcaddr):
        if tgid in self.talkgroups and srcaddr != 0:
            self.talkgroups[tgid]['srcaddr'] = srcaddr
            return 1
        else:
            return 0

    def update_talkgroup_encrypted(self, curr_time, tgid, encrypted):
        if self.rxctl.current_encrypted != encrypted:
            self.rxctl.current_encrypted = encrypted
            return 1
        else:
            return 0

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
                sys.stderr.write('%s new freq=%f\n' % (log_ts.get(), frequency/1000000.0))
        if 'tgid' not in self.voice_frequencies[frequency]:
            self.voice_frequencies[frequency]['tgid'] = [None, None]
            self.voice_frequencies[frequency]['ts'] = [0.0, 0.0]
        if prev_freq is not None and not (prev_freq == frequency and prev_slot == tdma_slot):
            if prev_slot is None:
                self.voice_frequencies[prev_freq]['tgid'] = [None, None]
            else:
                self.voice_frequencies[prev_freq]['tgid'][prev_slot] = None
        curr_time = time.time()
        self.voice_frequencies[frequency]['time'] = curr_time
        self.voice_frequencies[frequency]['counter'] += 1
        if tdma_slot is None:   # FDMA mark both slots with same info
            for slot in [0, 1]:
                self.voice_frequencies[frequency]['tgid'][slot] = tgid
                self.voice_frequencies[frequency]['ts'][slot] = curr_time
        else:                   # TDMA mark just slot in use
            self.voice_frequencies[frequency]['tgid'][tdma_slot] = tgid
            self.voice_frequencies[frequency]['ts'][tdma_slot] = curr_time

    def expire_voice_frequencies(self, curr_time, curr_tgid):
        for frequency in self.voice_frequencies:
            for slot in [0, 1]:
                tgid = self.voice_frequencies[frequency]['tgid'][slot]
                if tgid is not None and tgid != curr_tgid and curr_time >= self.voice_frequencies[frequency]['ts'][slot] + self.FREQ_EXPIRY_TIME:
                    self.voice_frequencies[frequency]['tgid'][slot] = None
                    if self.debug >= 5:
                        sys.stderr.write("%s clear tgid=%d, freq=%f, slot=%d\n" % (log_ts.get(), tgid, (frequency/1e6), slot))

    def get_updated_talkgroups(self, start_time):
        return [tgid for tgid in self.talkgroups if (
                       self.talkgroups[tgid]['time'] >= start_time and
                       ((self.whitelist and tgid in self.whitelist) or
                       (not self.whitelist and tgid not in self.blacklist)))]

    def blacklist_update(self, start_time):
        expired_tgs = [tg for tg in list(self.blacklist.keys())
                            if self.blacklist[tg] is not None
                            and self.blacklist[tg] < start_time]
        for tg in expired_tgs:
            if self.debug > 1:
                sys.stderr.write("%s removing expired blacklist: tg(%d)\n" % (log_ts.get(), tg))
            self.blacklist.pop(tg)

    def skiplist_update(self, start_time):
        expired_tgs = [tg for tg in list(self.skiplist.keys())
                            if self.skiplist[tg] is not None
                            and self.skiplist[tg] < start_time]
        for tg in expired_tgs:
            self.skiplist.pop(tg)
            if self.debug > 1:
                sys.stderr.write("%s removing expired skiplist: tg(%d)\n" % (log_ts.get(), tg));

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
                        sys.stderr.write("%s add_patch: tgid(%d) is patched to sg(%d)\n" % (log_ts.get(), ga, sg))

        if len(self.patches[sg]['ga']) == 0:
            del self.patches[sg]

    def del_patch(self, sg, ga_list):
        if sg not in self.patches:
            return

        for ga in ga_list:
            if ga in self.patches[sg]['ga']:
                self.patches[sg]['ga'].discard(ga)
                if self.debug >= 5:
                    sys.stderr.write("%s del_patch: tgid(%d) is unpatched from sg(%d)\n" % (log_ts.get(), ga, sg))

        if (sg in ga_list) or (len(self.patches[sg]['ga']) == 0):
            del self.patches[sg]
            if self.debug >= 5:
                sys.stderr.write("%s del_patch: deleting patch sg(%d)\n" % (log_ts.get(), sg))

    def expire_patches(self):
        time_now = time.time()
        for sg in list(self.patches):
            if time_now > (self.patches[sg]['ts'] + self.PATCH_EXPIRY_TIME):
                del self.patches[sg]
                if self.debug >= 5:
                    sys.stderr.write("%s expired_patches: expiring patch sg(%d)\n" % (log_ts.get(), sg))

    def find_talkgroup(self, start_time, tgid=None, hold=False):
        tgt_tgid = None
        self.skiplist_update(start_time)
        self.blacklist_update(start_time)

        if tgid is not None and tgid in self.talkgroups:
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
            if self.talkgroups[active_tgid]['tdma_slot'] is not None and (self.ns_syid < 0 or self.ns_wacn < 0):
                continue
            if tgt_tgid is None:
                tgt_tgid = active_tgid
            elif self.talkgroups[active_tgid]['prio'] < self.talkgroups[tgt_tgid]['prio']:
                tgt_tgid = active_tgid
                   
        if tgt_tgid is not None and self.talkgroups[tgt_tgid]['time'] >= start_time:
            return self.talkgroups[tgt_tgid]['frequency'], tgt_tgid, self.talkgroups[tgt_tgid]['tdma_slot'], self.talkgroups[tgt_tgid]['srcaddr']
        return None, None, None, None

    def dump_tgids(self):
        sys.stderr.write("Known tgids: { ")
        for tgid in sorted(self.talkgroups.keys()):
            sys.stderr.write("%d " % tgid);
        sys.stderr.write("}\n") 

    def add_skiplist(self, tgid, end_time=None):
        if not tgid or (tgid <= 0) or (tgid > 65534):
            if self.debug > 1:
                sys.stderr.write("%s skiplist tgid(%d) out of range (1-65534)\n" % (log_ts.get(), tgid))
            return
        if tgid in self.skiplist:
            return
        self.skiplist[tgid] = end_time
        if self.debug > 1:
            sys.stderr.write("%s skiplisting: tgid(%d)\n" % (log_ts.get(), tgid))

    def add_blacklist(self, tgid, end_time=None):
        if not tgid:
            return
        if tgid in self.blacklist:
            return
        if self.whitelist and tgid in self.whitelist:
            self.whitelist.pop(tgid)
            if self.debug > 1:
                sys.stderr.write("%s de-whitelisting tgid(%d)\n" % (log_ts.get(), tgid))
            if len(self.whitelist) == 0:
                self.whitelist = None
                if self.debug > 1:
                    sys.stderr.write("%s removing empty whitelist\n" % log_ts.get())
        self.blacklist[tgid] = end_time
        if self.debug > 1:
            sys.stderr.write("%s blacklisting tgid(%d)\n" % (log_ts.get(), tgid))

    def add_whitelist(self, tgid):
        if not tgid:
            return
        if self.blacklist and tgid in self.blacklist:
            self.blacklist.pop(tgid)
            if self.debug > 1:
                sys.stderr.write("%s de-blacklisting tgid(%d)\n" % (log_ts.get(), tgid))
        if not self.whitelist:
            self.whitelist = {}
        if tgid in self.whitelist:
            return
        self.whitelist[tgid] = None
        if self.debug > 1:
            sys.stderr.write("%s whitelisting tgid(%d)\n" % (log_ts.get(), tgid))

    def decode_mbt_data(self, opcode, src, header, mbt_data):
        self.cc_timeouts = 0
        self.last_tsbk = time.time()
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
                sys.stderr.write('%s [0] mbt(0x00) grp_v_ch_grant: ch1: %x ch2: %x ga: %d\n' %(log_ts.get(), ch1, ch2, ga))
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
                if self.debug >= 10:
                    sys.stderr.write('%s [0] mbt(0x02) mfid90_grg_cn_grant_exp: ch1: %x ch2: %x sg: %d\n' %(log_ts.get(), ch1, ch2, ga))
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
                sys.stderr.write('%s [0] mbt(0x28) grp_aff_rsp: mfid: 0x%x wacn: 0x%x syid: 0x%x lg: %d gav: %d aga: %d ga: %d ta: %d\n\n' %(log_ts.get(), mfrid, wacn, syid, lg, gav, aga, ga, ta))
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
                sys.stderr.write('%s [0] mbt(0x3c) adj_sts_bcst: syid: %x rfid %x stid %x ch1 %x ch2 %x f1 %s f2 %s\n' % (log_ts.get(), syid, rfid, stid, ch1, ch2, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
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
            if self.debug >= 10:
                sys.stderr.write('%s [0] mbt(0x3b) net_sts_bcst: syid: %x wacn: %x ch1: %s ch2: %s\n' %(log_ts.get(), syid, wacn, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
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
                sys.stderr.write('%s [0] mbt(0x3a) rfss_sts_bcst: sys %x rfid %x stid %x ch1 %s ch2 %s\n' %(log_ts.get(), syid, rfid, stid, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
        else:
            if self.debug >= 10:
                sys.stderr.write('%s [0] mbt(0x%02x) unhandled: %x\n' %(log_ts.get(), opcode, mbt_data))
        return updated

    def decode_tsbk(self, tsbk):
        self.cc_timeouts = 0
        self.last_tsbk = time.time()
        self.stats['tsbks'] += 1
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
                    sys.stderr.write('%s [0] tsbk(0x00) mfid90_grg_add_cmd: sg: %d ga1: %d ga2: %d ga3: %d\n' % (log_ts.get(), sg, ga1, ga2, ga3))
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
                    sys.stderr.write('%s [0] tsbk(0x00) grp_v_ch_grant: f: %s ga: %d sa: %d\n' % (log_ts.get(), self.channel_id_to_string(ch), ga, sa))
        elif opcode == 0x01:   # reserved
            mfrid  = (tsbk >> 80) & 0xff
            if mfrid == 0x90: #MOT_GRG_DEL_CMD
                sg   = (tsbk >> 64) & 0xffff
                ga1  = (tsbk >> 48) & 0xffff
                ga2  = (tsbk >> 32) & 0xffff
                ga3  = (tsbk >> 16) & 0xffff
                if self.debug >= 10:
                    sys.stderr.write('%s [0] tsbk(0x01) mfid90_grg_del_cmd: sg: %d ga1: %d ga2: %d ga3: %d\n' % (log_ts.get(), sg, ga1, ga2, ga3))
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
                    sys.stderr.write('%s [0] tsbk(0x02) mfid90_grg_ch_grant: f: %s sg: %d sa: %d\n' % (log_ts.get(), self.channel_id_to_string(ch), sg, sa))
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
                    sys.stderr.write('%s [0] tsbk(0x02) grp_v_ch_grant_updt: ch1: %s ga1: %d ch2: %s ga2: %d\n' %(log_ts.get(), self.channel_id_to_string(ch1), ga1, self.channel_id_to_string(ch2), ga2))
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
                    sys.stderr.write('%s [0] tsbk(0x03) mfid90_grg_ch_grant_updt: f1: %s sg1: %d f2: %s sg2: %d\n' % (log_ts.get(), self.channel_id_to_string(ch1), sg1, self.channel_id_to_string(ch2), sg2))
            elif mfrid == 0:
                ch1  = (tsbk >> 48) & 0xffff
                ch2   = (tsbk >> 32) & 0xffff
                ga  = (tsbk >> 16) & 0xffff
                f = self.channel_id_to_frequency(ch1)
                self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1))
                if f:
                    updated += 1
                if self.debug >= 10:
                    sys.stderr.write('%s [0] tsbk(0x03) grp_v_ch_grant_updt: freq-t: %s freq-r: %s ga: %d\n' % (log_ts.get(), self.channel_id_to_string(ch1), self.channel_id_to_string(ch2), ga))

        elif opcode == 0x16:   # sndcp data ch
            ch1  = (tsbk >> 48) & 0xffff
            ch2  = (tsbk >> 32) & 0xffff
            if self.debug >= 10:
                sys.stderr.write('%s [0] tsbk(0x16) sndcp_data_ch: ch1: %x ch2: %x\n' % (log_ts.get(), ch1, ch2))
        elif opcode == 0x28:   # grp_aff_rsp
            mfrid  = (tsbk >> 80) & 0xff
            lg     = (tsbk >> 79) & 0x01
            gav    = (tsbk >> 72) & 0x03
            aga    = (tsbk >> 56) & 0xffff
            ga     = (tsbk >> 40) & 0xffff
            ta     = (tsbk >> 16) & 0xffffff
            if self.debug >= 10:
                sys.stderr.write('%s [0] tsbk(28) grp_aff_rsp: mfid: 0x%x gav: %d aga: %d ga: %d ta: %d\n' % (log_ts.get(), mfrid, gav, aga, ga, ta))
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
                sys.stderr.write('%s [0] tsbk(0x29) sccb_exp: rfid: %x stid: %d ch1: %x(%s) ch2: %x(%s)\n' %(log_ts.get(), rfid, stid, ch1, self.channel_id_to_string(ch1), ch2, self.channel_id_to_string(ch2)))
        elif opcode == 0x2c:   # u_reg_rsp
            mfrid  = (tsbk >> 80) & 0xff
            rv     = (tsbk >> 76) & 0x3
            syid   = (tsbk >> 64) & 0xffff
            sid   = (tsbk >> 40) & 0xffffff
            sa     = (tsbk >> 16) & 0xffffff
            if self.debug >= 10:
                sys.stderr.write('%s [0] tsbk(0x2c) u_reg_rsp: mfid: 0x%x rv: %d syid: 0x%x sid: %d sa: %d\n' % (log_ts.get(), mfrid, rv, syid, sid, sa))
        elif opcode == 0x2f:   # u_de_reg_ack
            mfrid  = (tsbk >> 80) & 0xff
            wacn   = (tsbk >> 52) & 0xfffff
            syid   = (tsbk >> 40) & 0xffff
            sid    = (tsbk >> 16) & 0xffffff
            if self.debug >= 10:
                sys.stderr.write('%s [0] tsbk(0x2f) u_de_reg_ack: mfid: 0x%x wacn: 0x%x syid: 0x%x sid: %d\n' % (log_ts.get(), mfrid, wacn, syid, sid))
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
                    sys.stderr.write('%s [0] tsbk(0x30) mfida4_grg_exenc_cmd: grg_t: %d grg_g: %d grg_a: %d grg_ssn: %d sg: %d keyid: %d rta: %d\n' % (log_ts.get(), grg_t, grg_g, grg_a, grg_ssn, sg, keyid, rta))
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
                        self.del_patch(sg, [ga])
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
                sys.stderr.write('%s [0] tsbk(0x34) iden_up_vu: id: %d toff: %f spac: %f freq: %f [%s]\n' % (log_ts.get(), iden, toff * spac * 0.125 * 1e-3, spac * 0.125, freq * 0.000005, txt[toff_sign]))
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
                    sys.stderr.write('%s [0] tsbk(0x33) iden_up_tdma: %d freq: %d toff: %d spac: %d slots/carrier: %d\n' % (log_ts.get(), iden, self.freq_table[iden]['frequency'], self.freq_table[iden]['offset'], self.freq_table[iden]['step'], self.freq_table[iden]['tdma']))
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
                sys.stderr.write('%s [0] tsbk(0x3d) iden_up: id: %d toff: %f spac: %f freq: %f\n' % (log_ts.get(), iden, toff * 0.25, spac * 0.125, freq * 0.000005))
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
                sys.stderr.write('%s [0] tsbk(0x3a) rfss_sts_bcst: syid: %x rfid: %x stid: %d ch1: %x(%s)\n' %(log_ts.get(), syid, rfid, stid, chan, self.channel_id_to_string(chan)))
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
                add_unique_freq(self.cc_list, f1)
                add_unique_freq(self.cc_list, f2)
            if self.debug >= 10:
                sys.stderr.write('%s [0] tsbk(0x39) sccb: rfid: %x stid: %d ch1: %x(%s) ch2: %x(%s)\n' %(log_ts.get(), rfid, stid, ch1, self.channel_id_to_string(ch1), ch2, self.channel_id_to_string(ch2)))
        elif opcode == 0x3b:   # network status
            wacn = (tsbk >> 52) & 0xfffff
            syid = (tsbk >> 40) & 0xfff
            ch1  = (tsbk >> 24) & 0xffff
            f1 = self.channel_id_to_frequency(ch1)
            if f1:
                self.ns_syid = syid
                self.ns_wacn = wacn
                self.ns_chan = f1
            if self.debug >= 10:
                sys.stderr.write('%s [0] tsbk(0x3b) net_sts_bcst: wacn: %x syid: %x ch1: %x(%s)\n' %(log_ts.get(), wacn, syid, ch1, self.channel_id_to_string(ch1)))
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
                sys.stderr.write('%s [0] tsbk(0x3c) adj_sts_bcst: rfid: %x stid: %d ch1: %x(%s)\n' %(log_ts.get(), rfid, stid, ch1, self.channel_id_to_string(ch1)))
                if table in self.freq_table:
                    sys.stderr.write('%s tsbk(0x3c) adj_sts_bcst: %s %s\n' % (log_ts.get(), self.freq_table[table]['frequency'] , self.freq_table[table]['step'] ))
            else:
                if self.debug >= 10:
                    sys.stderr.write('%s [0] tsbk(0x%02x) unhandled: 0x%024x\n' % (log_ts.get(), opcode, tsbk))
        return updated

    def decode_tdma_ptt(self, msg, curr_time):
        updated = 0
        self.last_tsbk = time.time()
        self.stats['tsbks'] += 1
        mi    = get_ordinals(msg[0:9])
        algid = get_ordinals(msg[9:10])
        keyid = get_ordinals(msg[10:12])
        sa    = get_ordinals(msg[12:15])
        ga    = get_ordinals(msg[15:17])
        if self.debug >= 10:
            sys.stderr.write('%s [0] mac_ptt: mi: %x algid: %x keyid:%x ga: %d sa: %d\n' % (log_ts.get(), mi, algid, keyid, ga, sa))
        updated += self.update_talkgroup_srcaddr(curr_time, ga, sa)
        updated += self.update_talkgroup_encrypted(curr_time, ga, (algid != 0x80))
        self.rxctl.current_encrypted = (algid != 0x80)
        return updated

    def decode_tdma_endptt(self, msg, curr_time):
        self.last_tsbk = time.time()
        self.stats['tsbks'] += 1
        mi    = get_ordinals(msg[0:9])
        sa    = get_ordinals(msg[12:15])
        ga    = get_ordinals(msg[15:17])
        if self.debug >= 10:
            sys.stderr.write('%s [0] mac_end_ptt: ga: %d sa: %d\n' % (log_ts.get(), ga, sa))
        return self.update_talkgroup_srcaddr(curr_time, ga, sa)

    def decode_tdma_msg(self, msg, curr_time):
        updated = 0
        self.cc_timeouts = 0
        self.last_tsbk = time.time()
        self.stats['tsbks'] += 1
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
                sys.stderr.write('%s [0] tdma(0x01) grp_v_ch_usr: ga: %d sa: %d\n' % (log_ts.get(), ga, sa))
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
                sys.stderr.write('%s [0] tdma(0x05) grp_v_ch_grant_updt: f1: %s ga1: %d f2: %s ga2: %d f3: %s ga3: %d\n' % (log_ts.get(), self.channel_id_to_string(ch1), ga1, self.channel_id_to_string(ch2), ga2, self.channel_id_to_string(ch3), ga3))
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
                sys.stderr.write('%s [0] tdma(0x21) grp_v_ch_usr: ga: %d sa: %d: suid: %d\n' % (log_ts.get(), ga, sa, suid))
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
                sys.stderr.write('%s [0] tdma(0x25) grp_v_ch_grant_updt: f1-t: %s f1-r: %s ga1: %d f2-t: %s f2-r: %s ga2: %d\n' % (log_ts.get(), self.channel_id_to_string(ch1t), self.channel_id_to_string(ch1r), ga1, self.channel_id_to_string(ch2t), self.channel_id_to_string(ch2r), ga2))
            self.update_voice_frequency(f1, tgid=ga1, tdma_slot=self.get_tdma_slot(ch1t))
            self.update_voice_frequency(f2, tgid=ga2, tdma_slot=self.get_tdma_slot(ch2t))
            if f1 or f2:
                updated += 1
        elif op == 0x30: # Power Control Signal Quality
            ta     = get_ordinals(msg[1:4])
            rf_ber = get_ordinals(msg[4:5])  
            if self.debug >= 10:
                sys.stderr.write('%s [0] tdma(0x30) pwr_ctl_sig_qual: ta: %d rf: 0x%x: ber: 0x%x\n' % (log_ts.get(), ta, ((rf_ber >> 4) & 0xf), (rf_ber & 0xf)))
        elif op == 0x31: # MAC_Release (subscriber call pre-emption)
            uf = (get_ordinals(msg[1:2]) >> 7) & 0x1
            ca = (get_ordinals(msg[1:2]) >> 6) & 0x1
            sa = get_ordinals(msg[2:5])
            if self.debug >= 10:
                sys.stderr.write('%s [0] tdma(0x31) MAC_Release: uf: %d ca: %d sa: %d\n' % (log_ts.get(), uf, ca, sa))
        elif op == 0x80 and mfid == 0x90: # MFID90 Group Regroup Voice Channel User Abbreviated
            sg = get_ordinals(msg[3:5])
            sa = get_ordinals(msg[5:8])
            if self.debug >= 10:
                sys.stderr.write('%s [0] tdma(0x80) mfid90_grp_regrp_v_ch_usr: sg: %d sa: %d\n' % (log_ts.get(), sg, sa))
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
                sys.stderr.write('%s [0] tdma(0x81) mfid90_grp_regrp_add: sg: %d wg_list: %s\n' % (log_ts.get(), sg, wg_list))
            self.add_patch(sg, wg_list)
        elif op == 0x83 and mfid == 0x90: # MFID90 Group Regroup Voice Channel Update
            sg = get_ordinals(msg[3:5])
            ch = get_ordinals(msg[5:7])
            f = self.channel_id_to_frequency(ch)
            if self.debug >= 10:
                sys.stderr.write('%s [0] tdma(0x83) grp_regrp_v_ch_up freq: %s sg: %d\n' %(log_ts.get(), self.channel_id_to_string(ch), sg))
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
                sys.stderr.write('%s [0] tdma(0x89) mfid90_grp_regrp_del: sg: %d wg_list: %s\n' % (log_ts.get(), sg, wg_list))
            self.del_patch(sg, wg_list)
        elif op == 0xa0 and mfid == 0x90: # MFID90 Group Regroup Voice Channel User Extendd
            sg    = get_ordinals(msg[4:6])
            sa    = get_ordinals(msg[6:9])
            ssuid = get_ordinals(msg[9:16])
            if self.debug >= 10:
                sys.stderr.write('%s [0] tdma(0xa0) mfid90_grp_regrp_v_ch_usr: sg: %d sa: %d, ssuid: %d\n' % (log_ts.get(), sg, sa, ssuid))
            updated += self.update_talkgroup_srcaddr(curr_time, sg, sa)
        elif op == 0xa3 and mfid == 0x90: # MFID90 Group Regroup Channel Grant Implicit
            ch = get_ordinals(msg[4:6])
            sg = get_ordinals(msg[6:8])
            sa = get_ordinals(msg[8:11])
            f = self.channel_id_to_frequency(ch)
            if self.debug >= 10:
                sys.stderr.write('%s [0] tdma(0xa3) mfid90_grp_regrp_v_ch_grant freq: %s sg: %d sa: %d\n' %(log_ts.get(), self.channel_id_to_string(ch), sg, sa))
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
                sys.stderr.write('%s [0] tdma(0xa4) mfid90_grp_regrp_v_ch_grant freq-t: %s freq-r: %s sg: %d sa: %d\n' %(log_ts.get(), self.channel_id_to_string(ch1), self.channel_id_to_string(ch2), sg, sa))
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
                sys.stderr.write('%s [0] tdma(0xa5) mfid90_grp_regrp_ch_up f1: %s sg1: %d\n' %(log_ts.get(), self.channel_id_to_string(ch1), sg1, self.channel_id_to_string(ch2), sg2))
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
                    sys.stderr.write('%s [0] tdma(0xb0) mfida4_grg_regrp_exenc_cmd: grg_opt: %d grg_ssn: %d sg: %d keyid: %x algid: %x wgids: %s\n' % (log_ts.get(), grg_opt, grg_ssn, sg, keyid, algid, wglst))
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
                sys.stderr.write('%s [0] tdma(0xc0) grp_v_ch_grant: freq-t: %s freq-r: %s ga: %d sa: %d\n' % (log_ts.get(), self.channel_id_to_string(ch1t), self.channel_id_to_string(ch1r), ga, sa))
            self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1t), srcaddr=sa)
            if f:
                updated += 1
        elif op == 0xc3: # Group Voice Channel Grant Update Explicit
            ch1t = get_ordinals(msg[2:4])
            ch1r = get_ordinals(msg[4:6])
            ga   = get_ordinals(msg[6:8])
            f    = self.channel_id_to_frequency(ch1t)
            if self.debug >= 10:
                sys.stderr.write('%s [0] tdma(0xc3) grp_v_ch_grant_updt: freq-t: %s freq-r: %s ga: %d\n' % (log_ts.get(), self.channel_id_to_string(ch1t), self.channel_id_to_string(ch1r), ga))
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
                sys.stderr.write('%s [0] tdma(0xe9) sccb: rfid: %x stid: %x freq-t: %s freq-r: %s\n' % (log_ts.get(), rfid, stid, self.channel_id_to_string(ch_t), self.channel_id_to_string(ch_r)))
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
                sys.stderr.write('%s [0] tdma(0xf3) iden_up_tdma: id: %d base_f: %d offset: %d spacing: %d slots/carrier %d\n' % (log_ts.get(), iden, base_f, tx_off, ch_spac, slots_per_carrier[ch_type]))
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
                sys.stderr.write('%s [0] tdma(0xfa) rfss_sts_bcst: syid: %x rfid: %x stid: %x ch %x(%s)\n' % (log_ts.get(), syid, rfid, stid, ch_t, self.channel_id_to_string(ch_t)))
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
                sys.stderr.write('%s [0] tdma(0xfb) net_sts_bcst: wacn: %x syid: %x ch %x(%s)\n' % (log_ts.get(), wacn, syid, ch_t, self.channel_id_to_string(ch_t)))
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
                sys.stderr.write('%s [0] tdma(0xfc) adj_sts_bcst: syid: %x rfid: %x stid: %x ch %x(%s)\n' % (log_ts.get(), syid, rfid, stid, ch_t, self.channel_id_to_string(ch_t)))
                if table in self.freq_table:
                    sys.stderr.write('%s tdma(0xfc) adj_sts_bcst: %s %s\n' % (log_ts.get(), self.freq_table[table]['frequency'] , self.freq_table[table]['step'] ))
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
                sys.stderr.write('%s [0] tdma(0xfe) adj_sts_bcst: wacn: %x syid: %x rfid: %x stid: %x ch %x(%s)\n' % (log_ts.get(), wacn, syid, rfid, stid, ch_t, self.channel_id_to_string(ch_t)))
                if table in self.freq_table:
                    sys.stderr.write('%s tdma(fe) adj_sts_bcst: %s %s\n' % (log_ts.get(), self.freq_table[table]['frequency'] , self.freq_table[table]['step'] ))
        else:
            if self.debug >= 10:
                m_data = get_ordinals(msg[1:])
                sys.stderr.write('%s [0] tdma(0x%02x) unhandled: mfid: %x msg_data: %x\n' % (log_ts.get(), op, mfid, m_data))
        return updated

    def decode_fdma_lcw(self, msg, curr_time):
        updated = 0
        self.last_tsbk = time.time()
        self.stats['tsbks'] += 1
        pb_sf_lco = get_ordinals(msg[0:1])

        if (pb_sf_lco & 0x80): # encrypted format not supported
            return 0

        if pb_sf_lco   == 0x00:     # Group Voice Channel User
            mfid = get_ordinals(msg[1:2])
            ga = get_ordinals(msg[4:6])
            sa = get_ordinals(msg[6:9])
            if self.debug >= 10:
                sys.stderr.write('%s [0] lcw(0x00) grp_v_ch_usr: ga: %d s: %d sa: %d\n' % (log_ts.get(), ga, (get_ordinals(msg[3:4]) & 0x1), sa))
            updated += self.update_talkgroup_srcaddr(curr_time, ga, sa)
        elif pb_sf_lco == 0x42:     # Group Voice Channel Update
            ch1 = get_ordinals(msg[1:3])
            ga1 = get_ordinals(msg[3:5])
            ch2 = get_ordinals(msg[5:7])
            ga2 = get_ordinals(msg[7:9])
            f1 = self.channel_id_to_frequency(ch1)
            f2 = self.channel_id_to_frequency(ch2)
            if self.debug >= 10:
                sys.stderr.write('%s [0] lcw(0x02) grp_v_ch_up f1: %s ga1: %d f2: %s ga2: %d\n' %(log_ts.get(), self.channel_id_to_string(ch1), ga1, self.channel_id_to_string(ch2), ga2))
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
                sys.stderr.write('%s [0] lco(0x04) grp_v_ch_up: freq-t: %s freq-r: %s ga: %d\n' % (log_ts.get(), self.channel_id_to_string(ch1t), self.channel_id_to_string(ch1r), ga))
            self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1t))
            if f:
                updated += 1
        elif pb_sf_lco == 0x49:   # Source ID Extension
            netid = (get_ordinals(msg[2:5]) >> 4) & 0x0fffff
            syid  = get_ordinals(msg[4:6]) & 0x0fff
            sid   = get_ordinals(msg[6:9])
            if self.debug >= 10:
                sys.stderr.write('%s [0] lcw(0x09) lc_source_id_ext: netid: %d, sysid: %d, sid: %d\n' % (log_ts.get(), netid, syid, sid))
        elif pb_sf_lco == 0x4f:   # Call Termination/Cancellation (included with DUID15/ETDU)
            sa   = get_ordinals(msg[6:9])
            if self.debug >= 10:
                sys.stderr.write('%s [0] lco(0x0f) call_term_rel: sa: %d\n' % (log_ts.get(), sa))
        else:
            if self.debug >= 10:
                lcw_data = get_ordinals(msg[1:])
                sys.stderr.write('%s [0] lcw(0x%02x) unhandled: pb: %d sf: %d lcw_data: %016x\n' % (log_ts.get(), (pb_sf_lco & 0x3f), ((pb_sf_lco >> 7) & 0x1), ((pb_sf_lco >> 6) & 0x1), lcw_data))
        return updated

    def hunt_cc(self, curr_time):
        if ((self.cc_timeouts >=0) and (self.cc_timeouts < 6)) or (len(self.cc_list) == 0):
            return False
        self.cc_timeouts = 0
        self.cc_list_index += 1
        if self.cc_list_index >= len(self.cc_list):
            self.cc_list_index = 0
        self.trunk_cc = self.cc_list[self.cc_list_index]
        if self.trunk_cc != self.last_trunk_cc:
            self.last_trunk_cc = self.trunk_cc
            if self.debug >=5:
                sys.stderr.write('%s set control channel=%f\n' % (log_ts.get(curr_time), self.trunk_cc / 1000000.0))
            return True
        return False

def get_int_dict(s):
    # test below looks like it was meant to read a csv list from the config
    # file directly, rather than from a separate file.  Not sure if this is
    # actually used anymore, and could break if whitelist/blacklist file
    # path begins with a digit.

    if s[0].isdigit():
        return dict.fromkeys([int(d) for d in s.split(',')])

    # create dict by reading from file
    d = {}                     # this is the dict
    with open(s,"r") as f:
        for v in f:
            v = v.split("\t",1) # split on tab
            try:
                v0 = int(v[0])                         # first parameter is tgid or start of tgid range
                v1 = v0
                if (len(v) > 1) and (int(v[1]) > v0):  # second parameter if present is end of tgid range
                    v1 = int(v[1])

                for tg in range(v0, (v1 + 1)):
                        if tg not in d:      # is this a new tg?
                                d[tg] = []   # if so, add to dict (key only, value null)
                                sys.stderr.write('%s added talkgroup %d from %s\n' % (log_ts.get(),tg,s))

            except (IndexError, ValueError) as ex:
                continue
    f.close()
    return dict.fromkeys(d)

class rx_ctl (object):
    def __init__(self, debug=0, frequency_set=None, conf_file=None, logfile_workers=None, meta_update=None, crypt_behavior=0, nac_set=None, slot_set=None, nbfm_ctrl=None, chans={}):
        class _states(object):
            ACQ = 0
            CC = 1
            TO_VC = 2
            VC = 3
        self.autostart = False
        self.states = _states
        self.current_state = self.states.CC
        self.trunked_systems = {}
        self.receivers = {}
        self.frequency_set = frequency_set
        self.nac_set = nac_set
        self.meta_update = meta_update
        self.crypt_behavior = crypt_behavior
        self.meta_state = 0
        self.meta_q = None
        self.debug = debug
        self.tgid_hold = None
        self.tgid_hold_until = time.time()
        self.hold_mode = False
        self.TGID_HOLD_TIME = 2.0    # TODO: make more configurable
        self.TGID_SKIP_TIME = 4.0    # TODO: make more configurable
        self.current_nac = None
        self.current_id = 0
        self.current_tgid = None
        self.current_srcaddr = 0
        self.current_grpaddr = 0     # from P25 LCW
        self.current_encrypted = 0
        self.current_slot = None
        self.TSYS_HOLD_TIME = 3.0    # TODO: make more configurable
        self.wait_until = time.time()
        self.configs = {}
        self.config = None           # multi_rx.py channel config
        self.chans = chans
        self.nacs = []
        self.logfile_workers = logfile_workers
        self.working_frequencies = {}
        self.xor_cache = {}
        self.last_garbage_collect = 0
        self.last_tune_time = 0.0;
        self.last_tune_freq = 0;

        if self.logfile_workers:
            self.input_rate = self.logfile_workers[0]['demod'].input_rate

        if conf_file or len(chans) > 0:
            if len(chans) > 0:               # called from multi_rx.py
                self.build_config_chans(self.chans)
            elif conf_file.endswith('.tsv'): # called from rx.py
                self.build_config_tsv(conf_file)
                self.post_init()
            else:
                self.build_config(conf_file)
                self.post_init()

    def set_debug(self, dbglvl):
        self.debug = dbglvl
        for tsys in self.trunked_systems:
            self.trunked_systems[tsys].set_debug(dbglvl)

    def add_receiver(self, msgq_id, config, meta_q = None, freq = 0):
        self.config = config
        self.receivers[msgq_id] = msgq_id
        self.last_tune_freq = freq
        self.last_tune_time = time.time()
        if meta_q is not None:
            self.meta_q = meta_q
            self.meta_update = self.update_meta

    def update_meta(self, tgid = None, tag = None):
        if self.meta_q is None:
            return
        d = {'json_type': 'meta_update'}
        d['tgid'] = tgid
        d['tag'] = tag
        msg = op25_repeater.message().make_from_string(json.dumps(d), -2, time.time(), 0)
        self.meta_q.insert_tail(msg)

    def post_init(self):
        self.nacs = list(self.configs.keys())
        self.current_nac = self.find_next_tsys()
        self.current_state = self.states.CC

        tsys = self.trunked_systems[self.current_nac]

        if self.logfile_workers and tsys.modulation == 'c4fm':
            for worker in self.logfile_workers:
                worker['demod'].connect_chain('fsk4')

        if self.current_nac is None:
            self.nac_set({'tuner': 0,'nac': 0})
        else:
            self.nac_set({'tuner': 0,'nac': self.current_nac})
        self.set_frequency({
            'freq':   tsys.trunk_cc,
            'tgid':   None,
            'offset': tsys.offset,
            'tag':    "",
            'nac':    self.current_nac,
            'system': tsys.sysname,
            'center_frequency': tsys.center_frequency,
            'tdma':   None, 
            'wacn':   None, 
            'sysid':  None})

    def set_frequency(self, params):
        frequency = params['freq']
        params['tuner'] = 0
        params['sigtype'] = "P25"
        if frequency and self.frequency_set:
            if self.debug > 10:
                sys.stderr.write("%s set_frequency(%s)\n" % (log_ts.get(), frequency))
            if frequency != self.last_tune_freq:
                self.last_tune_time = time.time()
                self.last_tune_freq = frequency
            self.frequency_set(params)
            self.current_slot = params['tdma']

    def do_metadata(self, state, tgid, tag):
        if self.meta_update is None:
            return

        if (state == 1) and (self.meta_state == 1): # don't update more than once for an idle channel (state=1)
            return

        if self.debug > 10:
            sys.stderr.write("%s do_metadata state=%d: [%s] %s\n" % (log_ts.get(), state, tgid, tag))
        self.meta_update(tgid, tag)
        self.meta_state = state

    def add_trunked_system(self, nac):
        assert nac not in self.trunked_systems    # duplicate nac not allowed
        blacklist = {}
        whitelist = None
        tgid_map = {}
        cfg = None
        nac0 = False
        if nac in self.configs:
            cfg = self.configs[nac]
        if nac == 0:
            nac0 = True
        self.trunked_systems[nac] = trunked_system(debug = self.debug, config=cfg, wildcard=nac0, rxctl=self)

    def build_config_tsv(self, tsv_filename):
        configs = read_tsv_file(tsv_filename, "nac")

        if 0 in configs: # if NAC 0 exists, remove all other configs
            for nac in list(configs.keys()):
                if nac != 0:
                    configs.pop(nac)

        if len(configs) < 1:
            sys.stderr.write("No valid trunking configs. Aborting!\n")
            sys.exit(1)

        self.setup_config(configs)

    def build_config_chans(self, config):
        configs = {}
        for cfg in config:
            nac = ast.literal_eval(cfg['nac'])
            configs[nac] = cfg
        self.setup_config(configs)

    def build_config(self, config_filename):
        import configparser
        config = configparser.ConfigParser()
        config.read(config_filename)
        configs = {}
        for section in config.sections():
            nac = int(config.get(section, 'nac'), 0)    # nac required
            assert nac != 0                             # nac=0 not allowed
            assert nac not in configs                   # duplicate nac not allowed
            configs[nac] = {}
            for option in config.options(section):
                configs[nac][option] = config.get(section, option).lower()
            configs[nac]['sysname'] = section
        self.setup_config(configs)

    def add_default_config(self, nac, cclist=[], offset=0, whitelist=None, blacklist={}, tgid_map={}, sysname=None, center_frequency=None, modulation='cqpsk'):
        if nac in list(self.configs.keys()):
            return
        if nac not in list(self.trunked_systems.keys()):
            return
        tsys = self.trunked_systems[nac]
        if not tsys.rfss_chan:
            return
        if not tsys.ns_chan:
            return
        if tsys.ns_wacn < 0:
            return
        if tsys.ns_syid < 0:
            return

        if self.debug >= 1:
            sys.stderr.write("%s Initialize Trunking for NAC 0x%x\n" % (log_ts.get(), nac))
            
        if not sysname:
            sysname = 'NAC 0x%x' % nac
        if not cclist:
            cclist = [tsys.rfss_chan]
            cclist.extend(list(tsys.secondary.keys()))
            tsys.cc_list = cclist
        self.configs[nac] = {'cclist':cclist, 'offset':offset, 'whitelist':whitelist, 'blacklist':blacklist, 'tgid_map':tgid_map, 'sysname': sysname, 'center_frequency': center_frequency, 'modulation':modulation}
        self.current_nac = nac
        self.current_state = self.states.CC
        if nac not in self.nacs:
            self.nacs.append(nac)

    def setup_config(self, configs):
        for nac in configs:
            self.configs[nac] = {'cclist':[], 'offset':0, 'whitelist':None, 'blacklist':{}, 'tgid_map':{}, 'sysname': configs[nac]['sysname'], 'center_frequency': None}
            if len(configs[nac]['control_channel_list']) > 0:
                for f in configs[nac]['control_channel_list'].split(','):
                    self.configs[nac]['cclist'].append(get_frequency(f))
            if 'offset' in configs[nac]:
                self.configs[nac]['offset'] = int(configs[nac]['offset'])
            if 'modulation' in configs[nac]:
                self.configs[nac]['modulation'] = configs[nac]['modulation']
            else:
                self.configs[nac]['modulation'] = 'cqpsk'
            for k in ['whitelist', 'blacklist']:
                if (k in configs[nac]) and (configs[nac][k] != ""):
                    sys.stderr.write("%s Reading %s file\n" % (log_ts.get(), k))
                    self.configs[nac][k + ".file"] = configs[nac][k]
                    self.configs[nac][k] = get_int_dict(configs[nac][k])
            if 'tgid_tags_file' in configs[nac] and (configs[nac]['tgid_tags_file'] != ""):
                import csv
                with open(configs[nac]['tgid_tags_file'], 'r') as csvfile:
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
                            txt = utf_ascii(row[1])
                        except (IndexError, ValueError) as ex:
                            continue
                        if len(row) >= 3:
                            try:
                                prio = int(row[2])
                            except ValueError as ex:
                                prio = 3
                        else:
                            prio = 3
                        self.configs[nac]['tgid_map'][tgid] = (txt, prio)
            if 'center_frequency' in configs[nac]:
                self.configs[nac]['center_frequency'] = get_frequency(configs[nac]['center_frequency'])

            if 'crypt_behavior' in configs[nac]:
                self.configs[nac]['crypt_behavior'] = configs[nac]['crypt_behavior']
                self.crypt_behavior = int(configs[nac]['crypt_behavior'])

            self.add_trunked_system(nac)

    def find_next_tsys(self):
        self.current_id += 1
        if self.current_id >= len(self.nacs):
            self.current_id = 0
        return self.nacs[self.current_id]

    def find_current_tsys(self):
        return self.trunked_systems[self.nacs[self.current_id]]

    def to_json(self):
        d = {'json_type': 'trunk_update'}
        for nac in list(self.trunked_systems.keys()):
            if nac is not None:
                if nac == self.current_nac:
                    curr_tgid = self.current_tgid
                else:
                    curr_tgid = None
                d[nac] = json.loads(self.trunked_systems[nac].to_json(curr_tgid))
                d[nac]['top_line'] = 'NAC 0x%x %s' % (nac, d[nac]['top_line']) # prepend NAC which is not known by trunked_systems 
        d['srcaddr'] = self.current_srcaddr
        d['grpaddr'] = self.current_grpaddr
        d['encrypted'] = self.current_encrypted
        d['nac'] = self.current_nac
        return json.dumps(d)

    def get_chan_status(self):
        tsys = self.find_current_tsys()
        d = {'json_type': 'channel_update'}
        d['0'] = {}
        d['0']['name'] = ""
        d['0']['freq'] = self.last_tune_freq
        d['0']['tdma'] = self.current_slot
        d['0']['tgid'] = self.current_tgid
        d['0']['tag'] = tsys.get_tag(self.current_tgid)
        d['0']['srcaddr'] = self.current_srcaddr
        d['0']['encrypted'] = self.current_encrypted
        d['0']['msgqid'] = 0
        d['0']['system'] = tsys.sysname
        d['0']['stream'] = self.config['meta_stream_name'] if self.config is not None and 'meta_stream_name' in self.config else ""
        d['channels'] = ['0']
        return json.dumps(d)

    def dump_tgids(self):
        for nac in list(self.trunked_systems.keys()):
            self.trunked_systems[nac].dump_tgids()

    def to_string(self):
        s = ''
        for nac in self.trunked_systems:
            s += '\n====== NAC 0x%x ====== %s ======\n' % (nac, self.trunked_systems[nac].sysname)
            s += self.trunked_systems[nac].to_string()
        return s

    def ui_command(self, cmd, data, msgq_id):
        curr_time = time.time()
        if self.debug > 10:
            sys.stderr.write('ui_command: command: %s, data: %d\n' % (cmd, int(data)))
        self.update_state(cmd, curr_time, int(data))

    def process_qmsg(self, msg):
        m_proto = ctypes.c_int16(msg.type() >> 16).value
        m_type = ctypes.c_int16(msg.type() & 0xffff).value
        m_ts = float(msg.arg2())

        if m_proto > 0:     # P25 m_proto=0
            return

        if (m_ts < self.last_tune_time) and (m_type != -2):
            if self.debug > 10:
                sys.stderr.write("%s type %d with ts %s ignored due to frequency change\n" % (log_ts.get(), m_type, log_ts.get(m_ts)))
            return

        updated = 0
        curr_time = time.time()

        if m_type == -2:    # Request from gui
            cmd = msg.to_string()
            if type(cmd) is not str and isinstance(cmd, bytes):
                cmd = cmd.decode()
            if self.debug > 10:
                sys.stderr.write('%s process_qmsg: command: %s\n' % (log_ts.get(), cmd))
            self.update_state(cmd, curr_time, int(msg.arg1()))
            return

        if m_type == -3:    # P25 call signalling data
            if self.debug > 10:
                sys.stderr.write("%s process_qmsg: P25 info: %s\n" % (log_ts.get(), msg.to_string()))
            js = json.loads(msg.to_string())
            if ('srcaddr' in js) and (js['srcaddr'] != 0):
                self.current_srcaddr = js['srcaddr']
            if ('grpaddr' in js):
                self.current_grpaddr = js['grpaddr']
            if 'encrypted' in js and self.current_nac is not None and self.current_nac in self.trunked_systems:
                self.trunked_systems[self.current_nac].update_talkgroup_encrypted(curr_time, self.current_tgid, js['encrypted'])
            return 
        elif m_type == -1:  # timeout
            if self.current_nac is None: # trunking not started
                return
            if self.debug > 10:
                sys.stderr.write('%s process_data_unit timeout\n' % log_ts.get())
            self.update_state('timeout', curr_time)
            if self.logfile_workers:
                self.logging_scheduler(curr_time)
            return
        elif m_type == -4:  # P25 sync established
            if self.debug > 10:
                sys.stderr.write('%s P25 sync established\n' % log_ts.get())
            return
        elif m_type < 0:
            if self.debug > 10:
                sys.stderr.write('%s unknown message type %d\n' % (log_ts.get(), m_type))
            return
        s = msg.to_string()
        # nac is always 1st two bytes
        nac = get_ordinals(s[:2])
        if nac == 0xffff:
            if m_type not in [7, 12, 16, 17, 18]: # TDMA duid (end of call etc)
                self.update_state('tdma_duid%d' % m_type, curr_time)
                return
            else: # voice channel derived TSBK or MBT PDU
                nac = self.current_nac
        s = s[2:]
        if self.debug > 10:
            sys.stderr.write('%s nac %x type %d state %d len %d\n' %(log_ts.get(), nac, m_type, self.current_state, len(s)))
        if nac not in self.trunked_systems:
            if not self.configs:
                # TODO: allow whitelist/blacklist rather than blind automatic-add
                sys.stderr.write("%s Adding default config for NAC 0x%x\n" % (log_ts.get(), nac))
                cfgs = {int(nac): {"sysname": "P25", "control_channel_list": "", "offset": 0, "nac": nac, "modulation": "cqpsk", "tgid_tags_file": "", "whitelist": "", "blacklist": "", "center_frequency": 0} }
                self.setup_config(cfgs)
                self.autostart = True
                #TODO: make trunking properly auto-start with minimal configuration
                #self.nacs = list(self.configs.keys())
                #self.current_nac = nac
                #self.nac_set({'tuner': 0,'nac': nac})
            else:
                # If trunk.tsv file configured with nac=0, use decoded nac instead
                if 0 in self.trunked_systems:
                    sys.stderr.write("%s Reconfiguring NAC from 0x000 to 0x%x\n" % (log_ts.get(), nac))
                    self.trunked_systems[nac] = self.trunked_systems.pop(0)
                    self.configs[nac] = self.configs.pop(0)
                    self.nacs = list(self.configs.keys())
                    self.current_nac = nac
                    self.nac_set({'tuner': 0,'nac': nac})
                else:
                    sys.stderr.write("%s NAC %x not configured\n" % (log_ts.get(), nac))
                return
        if m_type == 7:     # trunk: TSBK
            t = get_ordinals(s)
            updated += self.trunked_systems[nac].decode_tsbk(t)
        elif m_type == 12:  # trunk: MBT
            s1 = s[:10]     # header without crc
            s2 = s[12:]
            header = get_ordinals(s1)
            mbt_data = get_ordinals(s2)

            fmt = (header >> 72) & 0x1f
            sap = (header >> 64) & 0x3f
            src = (header >> 32) & 0xffffff
            if fmt != 0x17: # only Extended Format MBT presently supported
                return

            opcode = (header >> 16) & 0x3f
            if self.debug > 10:
                sys.stderr.write('%s type %d state %d len %d/%d opcode %x [%0x/%0x]\n' %(log_ts.get(), m_type, self.current_state, len(s1), len(s2), opcode, header,mbt_data))
            updated += self.trunked_systems[nac].decode_mbt_data(opcode, src, header << 16, mbt_data << 32)

        elif m_type == 16:   # trunk: MAC_PTT
            updated += self.trunked_systems[nac].decode_tdma_ptt(s, curr_time)

        elif m_type == 17:   # trunk: MAC_END_PTT
            updated += self.trunked_systems[nac].decode_tdma_endptt(s, curr_time)

        elif m_type == 18:   # trunk: MAC_PDU
            updated += self.trunked_systems[nac].decode_tdma_msg(s, curr_time)

        elif m_type == 19:   # trunk: FDMA LCW
            updated += self.trunked_systems[nac].decode_fdma_lcw(s, curr_time)

        if self.autostart:
            nac_list = list(self.configs.keys()) # for autostart there really should only be one NAC entry
            if (len(nac_list) > 0):
                tsys = self.trunked_systems[nac_list[0]]
                if (tsys.rfss_chan > 0) and (len(tsys.secondary) > 0):
                    add_unique_freq(tsys.cc_list, tsys.rfss_chan)
                    for f in list(tsys.secondary.keys()):
                        add_unique_freq(tsys.cc_list, f)
                    sys.stderr.write("%s Autostart trunking for NAC 0x%03x with cc_list: %s\n" % (log_ts.get(), nac_list[0], tsys.cc_list))
                    self.nacs = list(self.configs.keys())
                    self.current_nac = nac_list[0]
                    self.nac_set({'tuner': 0,'nac': nac_list[0]})
                    self.current_state = self.states.CC
                    self.autostart = False

        if self.current_nac is None:
            return          # Trunking not yet enabled so discard anything further

        if nac != self.current_nac:
            if self.debug > 10: # this is occasionally expected if cycling between different tsys
                sys.stderr.write("%s received NAC %x does not match expected NAC %s\n" % (log_ts.get(), nac, self.current_nac))
            return

        if self.logfile_workers:
            self.logging_scheduler(curr_time)
            return

        if updated:
            self.update_state('update', curr_time)
        else:
            self.update_state('duid%d' % m_type, curr_time)

    def find_available_worker(self):
        for worker in self.logfile_workers:
            if not worker['active']:
                worker['active'] = True
                return worker
        return None

    def free_frequency(self, frequency, curr_time):
        assert not self.working_frequencies[frequency]['tgids']
        self.working_frequencies[frequency]['worker']['demod'].set_relative_frequency(0)
        self.working_frequencies[frequency]['worker']['active'] = False
        self.working_frequencies.pop(frequency)
        sys.stderr.write('%s release worker frequency %d\n' % (log_ts.get(curr_time), frequency))

    def free_talkgroup(self, frequency, tgid, curr_time):
        decoder = self.working_frequencies[frequency]['worker']['decoder']
        tdma_slot = self.working_frequencies[frequency]['tgids'][tgid]['tdma_slot']
        index = tdma_slot
        if tdma_slot is None:
            index = 0
        self.working_frequencies[frequency]['tgids'].pop(tgid)
        sys.stderr.write('%s release tgid %d frequency %d\n' % (log_ts.get(curr_time), tgid, frequency))

    def logging_scheduler(self, curr_time):
        tsys = self.trunked_systems[self.current_nac]
        for tgid in tsys.get_updated_talkgroups(curr_time):
            frequency = tsys.talkgroups[tgid]['frequency']
            tdma_slot = tsys.talkgroups[tgid]['tdma_slot']
            # see if this tgid active on any other freq(s)
            other_freqs = [f for f in self.working_frequencies if f != frequency and tgid in self.working_frequencies[f]['tgids']]
            if other_freqs:
                sys.stderr.write('%s tgid %d slot %s frequency %d found on other frequencies %s\n' % (log_ts.get(curr_time), tgid, tdma_slot, frequency, ','.join(['%s' % f for f in other_freqs])))
                for f in other_freqs:
                    self.free_talkgroup(f, tgid, curr_time)
                    if not self.working_frequencies[f]['tgids']:
                        self.free_frequency(f, curr_time)
            diff = abs(tsys.center_frequency - frequency)
            if diff > self.input_rate/2:
                #sys.stderr.write('%s request for frequency %d tgid %d failed, offset %d exceeds maximum %d\n' % (log_ts.get(curr_time), frequency, tgid, diff, self.input_rate/2))
                continue

            update = True
            if frequency in self.working_frequencies:
                tgids = self.working_frequencies[frequency]['tgids']
                if tgid in tgids:
                    if tgids[tgid]['tdma_slot'] == tdma_slot:
                        update = False
                    else:
                        sys.stderr.write('%s slot switch %s was %s tgid %d frequency %d\n' % (log_ts.get(curr_time), tdma_slot, tgids[tgid]['tdma_slot'], tgid, frequency))
                        worker = self.working_frequencies[frequency]['worker']
                else:
                    #active_tdma_slots = [tgids[tg]['tdma_slot'] for tg in tgids]
                    sys.stderr.write("%s new tgid %d slot %s arriving on already active frequency %d\n" % (log_ts.get(curr_time), tgid, tdma_slot, frequency))
                    previous_tgid = [id for id in tgids if tgids[id]['tdma_slot'] == tdma_slot]
                    assert len(previous_tgid) == 1   ## check for logic error
                    self.free_talkgroup(frequency, previous_tgid[0], curr_time)
                    worker = self.working_frequencies[frequency]['worker']
            else:
                worker = self.find_available_worker()
                if worker is None:
                    sys.stderr.write('*** error, no free demodulators, freq %d tgid %d\n' % (frequency, tgid))
                    continue
                self.working_frequencies[frequency] = {'tgids' : {}, 'worker': worker}
                worker['demod'].set_relative_frequency(tsys.center_frequency - frequency)
                sys.stderr.write('%s starting worker frequency %d tg %d slot %s\n' % (log_ts.get(curr_time), frequency, tgid, tdma_slot))
            self.working_frequencies[frequency]['tgids'][tgid] = {'updated': curr_time, 'tdma_slot': tdma_slot}
            if not update:
                continue
            filename = 'tgid-%d-%f.wav' % (tgid, curr_time)
            sys.stderr.write('%s update frequency %d tg %d slot %s file %s\n' % (log_ts.get(curr_time), frequency, tgid, tdma_slot, filename))
            # set demod speed, decoder slot, output file name
            demod = worker['demod']
            decoder = worker['decoder']
            symbol_rate = 4800

            if tdma_slot is None:
                index = 0
            else:
                index = tdma_slot
                symbol_rate = 6000
                xorhash = '%x%x%x' % (self.current_nac, tsys.ns_syid, tsys.ns_wacn)
                if xorhash not in self.xor_cache:
                    self.xor_cache[xorhash] = lfsr.p25p2_lfsr(self.current_nac, tsys.ns_syid, tsys.ns_wacn).xor_chars
                decoder.set_xormask(self.xor_cache[xorhash], xorhash, index=index)
            demod.set_omega(symbol_rate)
            decoder.set_output(filename, index=index)

        # garbage collection
        if self.last_garbage_collect + 1 > curr_time:
            return
        self.last_garbage_collect = curr_time

        gc_frequencies = []
        gc_tgids = []
        for frequency in self.working_frequencies:
            tgids = self.working_frequencies[frequency]['tgids']
            inactive_tgids = [[frequency, tgid] for tgid in tgids if tgids[tgid]['updated'] + self.TGID_HOLD_TIME < curr_time]
            if len(inactive_tgids) == len(tgids):
                gc_frequencies += [frequency]
            gc_tgids += inactive_tgids
        for frequency, tgid in gc_tgids:    # expire talkgroups
            self.free_talkgroup(frequency, tgid, curr_time)
        for frequency in gc_frequencies:    # expire working frequencies
            self.free_frequency(frequency, curr_time)

    def update_state(self, command, curr_time, cmd_data = 0):
        if not self.configs:
            return    # run in "manual mode" if no conf

        nac = self.current_nac
        if nac is None or nac not in self.trunked_systems:
            return
        tsys = self.trunked_systems[nac]

        new_frequency = None
        new_tgid = None
        new_state = None
        new_nac = None
        new_slot = None

        if command == 'timeout':
            if self.current_state == self.states.CC:
                if self.debug > 0:
                    sys.stderr.write("%s control channel timeout\n" % log_ts.get())
                tsys.cc_timeouts += 1
            elif self.current_state != self.states.CC:
                if self.debug > 1:
                    sys.stderr.write("%s voice timeout\n" % log_ts.get())
                if self.hold_mode is False:
                    self.current_tgid = None
                self.current_srcaddr = 0
                self.current_grpaddr = 0
                self.current_encrypted = 0
                new_state = self.states.CC
                new_frequency = tsys.trunk_cc
        elif command == 'update':
            # check for expired patches
            tsys.expire_patches()

            # check for encrypted calls
            if (self.crypt_behavior > 1) and self.current_tgid is not None and self.current_encrypted:
                if self.debug > 1:
                    sys.stderr.write("%s skip encrypted call: tg(%d)\n" % (log_ts.get(), self.current_tgid))
                self.current_srcaddr = 0
                self.current_grpaddr = 0
                self.current_encrypted = 0
                end_time = curr_time + self.TGID_SKIP_TIME
                tsys.add_skiplist(self.current_tgid, end_time=end_time)
                if self.hold_mode is False:
                    self.current_tgid = None
                    self.tgid_hold = None
                new_state = self.states.CC
                new_frequency = tsys.trunk_cc
            
            # look for new calls or call preemption
            elif self.current_state == self.states.CC:
                desired_tgid = None
                if (self.tgid_hold is not None) and (self.tgid_hold_until > curr_time):
                    if self.debug > 1:
                        sys.stderr.write("%s hold active tg(%s)\n" % (log_ts.get(), self.tgid_hold))
                    desired_tgid = self.tgid_hold
                elif (self.tgid_hold is not None) and (self.hold_mode == False):
                    self.tgid_hold = None
                new_frequency, new_tgid, tdma_slot, srcaddr = tsys.find_talkgroup(curr_time, tgid=desired_tgid, hold=self.hold_mode)
                if new_frequency:
                    if self.debug > 0:
                        tslot = tdma_slot if tdma_slot is not None else '-'
                        sys.stderr.write("%s voice update:  tg(%s), freq(%s), slot(%s), prio(%d)\n" % (log_ts.get(), new_tgid, new_frequency, tslot, tsys.get_prio(new_tgid)))
                    new_state = self.states.TO_VC
                    self.current_tgid = new_tgid
                    self.current_srcaddr = srcaddr
                    self.tgid_hold = new_tgid
                    self.tgid_hold_until = max(curr_time + self.TGID_HOLD_TIME, self.tgid_hold_until)
                    self.wait_until = curr_time + self.TSYS_HOLD_TIME
                    new_slot = tdma_slot
                    self.do_metadata(0, new_tgid,tsys.get_tag(new_tgid))
            else: # check for priority tgid preemption
                new_frequency, new_tgid, tdma_slot, srcaddr = tsys.find_talkgroup(tsys.talkgroups[self.current_tgid]['time'], tgid=self.current_tgid, hold=self.hold_mode)
                if new_tgid != self.current_tgid:
                    if self.debug > 0:
                        tslot = tdma_slot if tdma_slot is not None else '-'
                        sys.stderr.write("%s voice preempt: tg(%s), freq(%s), slot(%s), prio(%d)\n" % (log_ts.get(), new_tgid, new_frequency, tslot, tsys.get_prio(new_tgid)))
                    new_state = self.states.TO_VC
                    self.current_tgid = new_tgid
                    self.current_srcaddr = srcaddr
                    self.tgid_hold = new_tgid
                    self.tgid_hold_until = max(curr_time + self.TGID_HOLD_TIME, self.tgid_hold_until)
                    self.wait_until = curr_time + self.TSYS_HOLD_TIME
                    new_slot = tdma_slot
                    self.do_metadata(0, new_tgid,tsys.get_tag(new_tgid))
                else:
                    if tsys.talkgroups[self.current_tgid]['srcaddr'] != 0:
                        self.current_srcaddr = tsys.talkgroups[self.current_tgid]['srcaddr']
                        self.current_grpaddr = self.current_tgid
                    new_frequency = None
        elif command in ['duid3', 'tdma_duid3']: # termination, no channel release
            if self.current_state != self.states.CC:
                self.wait_until = curr_time + self.TSYS_HOLD_TIME
                self.tgid_hold = self.current_tgid
                self.tgid_hold_until = max(curr_time + self.TGID_HOLD_TIME, self.tgid_hold_until)
        elif command in ['duid15', 'tdma_duid15', 'duid17']: # termination with channel release
            if self.current_state != self.states.CC:
                if self.debug > 1:
                    sys.stderr.write("%s %s, tg(%d)\n" % (log_ts.get(), command, self.current_tgid))
                self.current_srcaddr = 0
                self.current_grpaddr = 0
                self.current_encrypted = 0
                self.wait_until = curr_time + self.TSYS_HOLD_TIME
                self.tgid_hold = self.current_tgid
                self.tgid_hold_until = max(curr_time + self.TGID_HOLD_TIME, self.tgid_hold_until)
                if self.hold_mode is False:
                    self.current_tgid = None
                new_state = self.states.CC
                new_frequency = tsys.trunk_cc
        elif command in ['duid0', 'duid5', 'duid10', 'tdma_duid5']:
            if self.current_state == self.states.TO_VC:
                new_state = self.states.VC
            self.tgid_hold = self.current_tgid
            self.tgid_hold_until = max(curr_time + self.TGID_HOLD_TIME, self.tgid_hold_until)
            self.wait_until = curr_time + self.TSYS_HOLD_TIME
        elif command in ['duid7', 'duid12', 'duid16', 'duid18', 'duid19']: # tsbk/pdu/tdma should never arrive here...
            pass
        elif command == 'hold':
            if cmd_data > 0:
                    self.tgid_hold = cmd_data
                    self.tgid_hold_until = curr_time + 86400 * 10000
                    self.hold_mode = True
                    if self.debug > 0:
                        sys.stderr.write ('%s set hold tg(%s) until %f\n' % (log_ts.get(), self.tgid_hold, self.tgid_hold_until))
                    if self.current_tgid != self.tgid_hold:
                        self.current_tgid = self.tgid_hold
                        self.current_srcaddr = 0
                        self.current_grpaddr = 0
                        self.current_encrypted = 0
                        new_state = self.states.CC
                        new_frequency = tsys.trunk_cc
            elif self.hold_mode is False:
                if self.current_tgid:
                    self.tgid_hold = self.current_tgid
                    self.tgid_hold_until = curr_time + 86400 * 10000
                    self.hold_mode = True
                    if self.debug > 0:
                        sys.stderr.write ('%s set hold tg(%s) until %f\n' % (log_ts.get(), self.tgid_hold, self.tgid_hold_until))
            elif self.hold_mode is True:
                if self.debug > 0:
                    sys.stderr.write ('%s clear hold tg(%s)\n' % (log_ts.get(), self.tgid_hold))
                self.current_tgid = None
                self.tgid_hold = None
                self.tgid_hold_until = curr_time
                self.hold_mode = False
        elif command == 'skip' or command == 'lockout':
            if self.current_tgid and ((cmd_data == self.current_tgid) or (cmd_data == 0)):
                end_time = None
                if command == 'skip':
                    end_time = curr_time + self.TGID_SKIP_TIME
                    tsys.add_skiplist(self.current_tgid, end_time=end_time)
                else:
                    tsys.add_blacklist(self.current_tgid, end_time=end_time)
                self.current_tgid = None
                self.current_srcaddr = 0
                self.current_grpaddr = 0
                self.current_encrypted = 0
                self.tgid_hold = None
                self.tgid_hold_until = curr_time
                self.hold_mode = False
                if self.current_state != self.states.CC:
                    new_state = self.states.CC
                    new_frequency = tsys.trunk_cc
            else:
                if (cmd_data <= 0) or (cmd_data > 65534):
                    if self.debug > 0:
                        sys.stderr.write("%s blacklist tgid(%d) out of range (1-65534)\n" % (log_ts.get(), cmd_data))
                    return
                if command == 'skip':
                    end_time = curr_time + self.TGID_SKIP_TIME
                    tsys.add_skiplist(cmd_data, end_time=end_time)
                else:
                    tsys.add_blacklist(cmd_data)
        elif command == 'whitelist':
            if (cmd_data <= 0) or (cmd_data > 65534):
                if self.debug > 0:
                    sys.stderr.write("%s whitelist tgid(%d) out of range (1-65534)\n" % (log_ts.get(), cmd_data))
                return
            tsys.add_whitelist(cmd_data)
            if self.current_tgid and tsys.whitelist and self.current_tgid not in tsys.whitelist:
                self.current_tgid = None
                self.tgid_hold = None
                self.tgid_hold_until = curr_time
                self.hold_mode = False
                if self.current_state != self.states.CC:
                    new_state = self.states.CC
                    new_frequency = tsys.trunk_cc
        elif command == 'reload':
            nac = self.current_nac
            sys.stderr.write("%s reloading blacklist & whitelist files for nac(%x)\n" % (log_ts.get(), nac))
            tsys.blacklist.clear()
            if 'blacklist.file' in self.configs[nac]:
                self.configs[nac]['blacklist'] = get_int_dict(self.configs[nac]['blacklist.file'])
                tsys.blacklist = self.configs[nac]['blacklist']
            if 'whitelist.file' in self.configs[nac]:
                self.configs[nac]['whitelist'] = get_int_dict(self.configs[nac]['whitelist.file'])
                tsys.whitelist = self.configs[nac]['whitelist']
            self.current_tgid = None
            self.tgid_hold = None
            self.tgid_hold_until = curr_time
            self.hold_mode = False
            if self.current_state != self.states.CC:
                new_state = self.states.CC
                new_frequency = tsys.trunk_cc
        else:
            sys.stderr.write('update_state: unknown command: %s\n' % command)
            assert 0 == 1

        hunted_cc = tsys.hunt_cc(curr_time)
        if tsys.wildcard_tsys and hunted_cc and self.current_nac != 0:
            if self.debug >= 5:
                sys.stderr.write("%s reset tsys to NAC 0 after control channel change\n" % log_ts.get())
            self.trunked_systems[0] = self.trunked_systems.pop(self.current_nac)
            self.configs[0] = self.configs.pop(self.current_nac)
            self.nacs = list(self.configs.keys())
            self.current_nac = 0 
            self.current_state = self.states.CC
            self.current_tgid = None
            self.current_srcaddr = 0
            self.current_grpaddr = 0
            self.current_encrypted = 0
            self.nac_set({'tuner': 0,'nac': 0})
            tsys.reset()

        if self.current_state != self.states.CC and self.tgid_hold_until <= curr_time and self.hold_mode is False and new_state is None:
            if self.debug > 1:
                sys.stderr.write("%s release tg(%s)\n" % (log_ts.get(), self.current_tgid))
                sys.stderr.write("%s command=%s, timer=%f, hold_mode=%s\n" % (log_ts.get(), command, (self.tgid_hold_until - curr_time), self.hold_mode))
            self.tgid_hold = None
            self.current_tgid = None
            self.current_srcaddr = 0
            self.current_grpaddr = 0
            self.current_encrypted = 0
            new_state = self.states.CC
            new_frequency = tsys.trunk_cc
        elif self.wait_until <= curr_time and self.tgid_hold_until <= curr_time and self.hold_mode is False and new_state is None:
            self.wait_until = curr_time + self.TSYS_HOLD_TIME
            self.current_srcaddr = 0
            self.current_grpaddr = 0
            self.current_encrypted = 0
            new_nac = self.find_next_tsys()
            new_state = self.states.CC

        if self.current_state == self.states.CC and self.tgid_hold_until <= curr_time:
            self.do_metadata(1, None, None)

        if new_nac is not None:
            nac = self.current_nac = new_nac
            tsys = self.trunked_systems[nac]
            new_frequency = tsys.trunk_cc
            self.nac_set({'tuner': 0,'nac': new_nac})
            self.current_srcaddr = 0
            self.current_grpaddr = 0
            self.current_encrypted = 0
            self.current_tgid = None

        if new_frequency is not None:
            self.set_frequency({
                'freq':   new_frequency,
                'tgid':   self.current_tgid,
                'offset': tsys.offset,
                'tag':    tsys.get_tag(self.current_tgid),
                'nac':    nac,
                'system': tsys.sysname,
                'center_frequency': tsys.center_frequency,
                'tdma':   new_slot, 
                'wacn':   tsys.ns_wacn, 
                'sysid':  tsys.ns_syid})

        if new_state is not None:
            self.current_state = new_state

def main():
    q = 0x3a000012ae01013348704a54
    rc = crc16(q,12)
    sys.stderr.write('should be zero: %x\n' % rc)
    assert rc == 0

    q = 0x3a001012ae01013348704a54
    rc = crc16(q,12)
    sys.stderr.write('should be nonzero: %x\n' % rc)
    assert rc != 0

    t = trunked_system(debug=255)
    q = 0x3a000012ae0101334870
    t.decode_tsbk(q)

    q = 0x02900031210020018e7c
    t.decode_tsbk(q)

if __name__ == '__main__':
    main()
