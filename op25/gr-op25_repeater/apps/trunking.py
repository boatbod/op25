
# Copyright 2011, 2012, 2013, 2014, 2015, 2016, 2017 Max H. Parke KA1RBI
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
sys.path.append('tdma')
import lfsr

def utf_ascii(ustr):
    return (ustr.decode("utf-8")).encode("ascii", "ignore")

def crc16(dat,len):	# slow version
    poly = (1<<12) + (1<<5) + (1<<0)
    crc = 0
    for i in range(len):
        bits = (dat >> (((len-1)-i)*8)) & 0xff
        for j in range(8):
            bit = (bits >> (7-j)) & 1
            crc = ((crc << 1) | bit) & 0x1ffff
            if crc & 0x10000:
                crc = (crc & 0xffff) ^ poly
    crc = crc ^ 0xffff
    return crc

def get_frequency(f):	# return frequency in Hz
    if f.find('.') == -1:	# assume in Hz
        return int(f)
    else:     # assume in MHz due to '.'
        return int(float(f) * 1000000)

class trunked_system (object):
    def __init__(self, debug=0, config=None, wildcard=False):
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
        self.blacklist = {}
        self.whitelist = None
        self.tgid_map = {}
        self.offset = 0
        self.sysname = 0

        self.trunk_cc = 0
        self.last_trunk_cc = 0
        self.cc_list = []
        self.cc_list_index = 0
        self.CC_HUNT_TIME = 5.0
        self.PATCH_EXPIRY_TIME = 20.0
        self.center_frequency = 0
        self.last_tsbk = 0
        self.cc_timeouts = 0
        self.talkgroups = {}
        self.patches ={}
        if config:
            self.blacklist = config['blacklist']
            self.whitelist = config['whitelist']
            self.tgid_map  = config['tgid_map']
            self.offset    = config['offset']
            self.sysname   = config['sysname']
            self.trunk_cc  = config['cclist'][0]	# TODO: scan thru list
            self.cc_list   = config['cclist']
            self.center_frequency = config['center_frequency']
            self.modulation = config['modulation']

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

    def to_json(self):
        d = {}
        d['syid'] = self.rfss_syid
        d['rfid'] = self.rfss_rfid
        d['stid'] = self.rfss_stid
        d['sysid'] = self.ns_syid
        d['rxchan'] = self.rfss_chan
        d['txchan'] = self.rfss_txchan
        d['wacn'] = self.ns_wacn
        d['secondary'] = self.secondary.keys()
        d['tsbks'] = self.stats['tsbks']
        d['frequencies'] = {}
        d['frequency_data'] = {}
        d['last_tsbk'] = self.last_tsbk
        t = time.time()
        for f in self.voice_frequencies.keys():
            tgs = '%s %s' % (self.voice_frequencies[f]['tgid'][0], self.voice_frequencies[f]['tgid'][1])
            d['frequencies'][f] = 'voice frequency %f tgid(s) %s %4.1fs ago count %d' %  (f / 1000000.0, tgs, t - self.voice_frequencies[f]['time'], self.voice_frequencies[f]['counter'])

            d['frequency_data'][f] = {'tgids': self.voice_frequencies[f]['tgid'], 'last_activity': '%7.1f' % (t - self.voice_frequencies[f]['time']), 'counter': self.voice_frequencies[f]['counter']}
	d['adjacent_data'] = self.adjacent_data
        return json.dumps(d)

    def to_string(self):
        s = []
        s.append('rf: syid %x rfid %d stid %d frequency %f uplink %f' % ( self.rfss_syid, self.rfss_rfid, self.rfss_stid, float(self.rfss_chan) / 1000000.0, float(self.rfss_txchan) / 1000000.0))
        s.append('net: syid %x wacn %x frequency %f' % ( self.ns_syid, self.ns_wacn, float(self.ns_chan) / 1000000.0))
        s.append('secondary control channel(s): %s' % ','.join(['%f' % (float(k) / 1000000.0) for k in self.secondary.keys()]))
        s.append('stats: tsbks %d crc %d' % (self.stats['tsbks'], self.stats['crc']))
        s.append('')
        t = time.time()
        for f in self.voice_frequencies:
            tgs = '%s %s' % (self.voice_frequencies[f]['tgid'][0], self.voice_frequencies[f]['tgid'][1])
            s.append('voice frequency %f tgid(s) %s %4.1fs ago count %d' %  (f / 1000000.0, tgs, t - self.voice_frequencies[f]['time'], self.voice_frequencies[f]['counter']))
        s.append('')
        for table in self.freq_table:
            a = self.freq_table[table]['frequency'] / 1000000.0
            b = self.freq_table[table]['step'] / 1000000.0
            c = self.freq_table[table]['offset'] / 1000000.0
            s.append('tbl-id: %x frequency: %f step %f offset %f' % ( table, a,b,c))
            #self.freq_table[table]['frequency'] / 1000000.0, self.freq_table[table]['step'] / 1000000.0, self.freq_table[table]['offset']) / 1000000.0)
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
            return "Talkgroup ID %d [0x%x]" % (tgid, tgid)
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
                    sys.stderr.write('%f update_talkgroups: sg(%d) patched tgid(%d)\n' % (time.time(), tgid, ptgid))

    def update_talkgroup(self, frequency, tgid, tdma_slot, srcaddr):
        if self.debug >= 5:
            sys.stderr.write('%f set tgid=%s, srcaddr=%s\n' % (time.time(), tgid, srcaddr))
        
        if tgid not in self.talkgroups:
            self.talkgroups[tgid] = {'counter':0}
            if self.debug >= 5:
                sys.stderr.write('%f new tgid: %s %s prio %d\n' % (time.time(), tgid, self.get_tag(tgid), self.get_prio(tgid)))
        self.talkgroups[tgid]['time'] = time.time()
        self.talkgroups[tgid]['frequency'] = frequency
        self.talkgroups[tgid]['tdma_slot'] = tdma_slot
        self.talkgroups[tgid]['srcaddr'] = srcaddr
        self.talkgroups[tgid]['prio'] = self.get_prio(tgid)

    def update_voice_frequency(self, frequency, tgid=None, tdma_slot=None, srcaddr=0):
        if not frequency:	# e.g., channel identifier not yet known
            return
        self.update_talkgroups(frequency, tgid, tdma_slot, srcaddr)
        if frequency not in self.voice_frequencies:
            self.voice_frequencies[frequency] = {'counter':0}
            sorted_freqs = collections.OrderedDict(sorted(self.voice_frequencies.items()))
            self.voice_frequencies = sorted_freqs
            if self.debug >= 5:
                sys.stderr.write('%f new freq: %f\n' % (time.time(), frequency/1000000.0))

        if tdma_slot is None:
            tdma_slot = 0
        if 'tgid' not in self.voice_frequencies[frequency]:
            self.voice_frequencies[frequency]['tgid'] = [None, None]
        self.voice_frequencies[frequency]['tgid'][tdma_slot] = tgid
        self.voice_frequencies[frequency]['counter'] += 1
        self.voice_frequencies[frequency]['time'] = time.time()

    def get_updated_talkgroups(self, start_time):
        return [tgid for tgid in self.talkgroups if (
                       self.talkgroups[tgid]['time'] >= start_time and
                       ((self.whitelist and tgid in self.whitelist) or
                       (not self.whitelist and tgid not in self.blacklist)))]

    def blacklist_update(self, start_time):
        expired_tgs = [tg for tg in self.blacklist.keys()
                            if self.blacklist[tg] is not None
                            and self.blacklist[tg] < start_time]
        for tg in expired_tgs:
            self.blacklist.pop(tg)

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
                        sys.stderr.write("%f add_patch: tgid(%d) is patched to sg(%d)\n" % (time.time(), ga, sg))

        if len(self.patches[sg]['ga']) == 0:
            del self.patches[sg]

    def del_patch(self, sg, ga1, ga2, ga3):
        if sg not in self.patches:
            return

        for ga in [ga1, ga2, ga3]:
            if ga in self.patches[sg]['ga']:
                self.patches[sg]['ga'].discard(ga)
                if self.debug >= 5:
                    sys.stderr.write("%f del_patch: tgid(%d) is unpatched from sg(%d)\n" % (time.time(), ga, sg))

        if ((ga1, ga2, ga3) == (0, 0, 0)) or (len(self.patches[sg]['ga']) == 0):
            del self.patches[sg]
            if self.debug >= 5:
                sys.stderr.write("%f del_patch: deleting patch sg(%d)\n" % (time.time(), sg))

    def expire_patches(self):
        time_now = time.time()
        for sg in list(self.patches):
            if time_now > (self.patches[sg]['ts'] + self.PATCH_EXPIRY_TIME):
                del self.patches[sg]
                if self.debug >= 5:
                    sys.stderr.write("%f expired_patches: expiring patch sg(%d)\n" % (time.time(), sg))

    def find_talkgroup(self, start_time, tgid=None, hold=False):
        tgt_tgid = None
        self.blacklist_update(start_time)

        if tgid is not None and tgid in self.talkgroups:
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

    def add_blacklist(self, tgid, end_time=None):
        if not tgid:
            return
        if tgid in self.blacklist:
            return
        if self.whitelist and tgid in self.whitelist:
            self.whitelist.pop(tgid)
            if self.debug > 0:
                sys.stderr.write("%f de-whitelisting tgid(%d)\n" % (time.time(), tgid))
        self.blacklist[tgid] = end_time
        if self.debug > 0:
            sys.stderr.write("%f blacklisting tgid(%d)\n" % (time.time(), tgid))

    def add_whitelist(self, tgid):
        if not tgid:
            return
        if self.blacklist and tgid in self.blacklist:
            self.blacklist.pop(tgid)
            if self.debug > 0:
                sys.stderr.write("%f de-blacklisting tgid(%d)\n" % (time.time(), tgid))
        if not self.whitelist or tgid in self.whitelist:
            return
        self.whitelist[tgid] = None
        if self.debug > 0:
            sys.stderr.write("%f whitelisting tgid(%d)\n" % (time.time(), tgid))

    def decode_mbt_data(self, opcode, src, header, mbt_data):
        self.cc_timeouts = 0
        self.last_tsbk = time.time()
        updated = 0
        if self.debug > 10:
            sys.stderr.write('decode_mbt_data: %x %x\n' %(opcode, mbt_data))
        if opcode == 0x0:  # grp voice channel grant
            ch1  = (mbt_data >> 64) & 0xffff
            ch2  = (mbt_data >> 48) & 0xffff
            ga   = (mbt_data >> 32) & 0xffff
            f = self.channel_id_to_frequency(ch1)
            self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1), srcaddr=src)
            if f:
                updated += 1
            if self.debug > 10:
                sys.stderr.write('mbt00 voice grant ch1 %x ch2 %x addr 0x%x\n' %(ch1, ch2, ga))
        if opcode == 0x02: # grp regroup voice channel grant
            mfrid  = (mbt_data >> 168) & 0xff
            if mfrid == 0x90:	# MOT_GRG_CN_GRANT_EXP
                ch1  = (mbt_data >> 80) & 0xffff
                ch2  = (mbt_data >> 64) & 0xffff
                sg   = (mbt_data >> 48) & 0xffff
                f = self.channel_id_to_frequency(ch1)
                self.update_voice_frequency(f, tgid=sg, tdma_slot=self.get_tdma_slot(ch1), srcaddr=src)
                if f:
                    updated += 1
                if self.debug > 10:
                    sys.stderr.write('mbt02 voice regroup grant ch1 %x ch2 %x addr 0x%x\n' %(ch1, ch2, ga))
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
                sys.stderr.write('mbt3c adjacent sys %x rfid %x stid %x ch1 %x ch2 %x f1 %s f2 %s\n' % (syid, rfid, stid, ch1, ch2, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
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
            if self.debug > 10:
                sys.stderr.write('mbt3b net stat sys %x wacn %x ch1 %s ch2 %s\n' %(syid, wacn, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
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
                sys.stderr.write('mbt3a rfss stat sys %x rfid %x stid %x ch1 %s ch2 %s\n' %(syid, rfid, stid, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2)))
        #else:
        #    sys.stderr.write('mbt other %x\n' % opcode
        return updated

    def decode_tsbk(self, tsbk):
        self.cc_timeouts = 0
        self.last_tsbk = time.time()
        self.stats['tsbks'] += 1
        updated = 0
        tsbk = tsbk << 16	# for missing crc
        opcode = (tsbk >> 88) & 0x3f
        if self.debug > 10:
            sys.stderr.write('TSBK: 0x%02x 0x%024x\n' % (opcode, tsbk))
        if opcode == 0x00:   # group voice chan grant
            mfrid  = (tsbk >> 80) & 0xff
            if mfrid == 0x90:	# MOT_GRG_ADD_CMD
                sg   = (tsbk >> 64) & 0xffff
                ga1  = (tsbk >> 48) & 0xffff
                ga2  = (tsbk >> 32) & 0xffff
                ga3  = (tsbk >> 16) & 0xffff
                if self.debug > 10:
                    sys.stderr.write('MOT_GRG_ADD_CMD(0x00): sg:%d ga1:%d ga2:%d ga3:%d\n' % (sg, ga1, ga2, ga3))
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
                    sys.stderr.write('tsbk00 grant freq %s ga %d sa %d\n' % (self.channel_id_to_string(ch), ga, sa))
        elif opcode == 0x01:   # reserved
            mfrid  = (tsbk >> 80) & 0xff
            if mfrid == 0x90: #MOT_GRG_DEL_CMD
                sg   = (tsbk >> 64) & 0xffff
                ga1  = (tsbk >> 48) & 0xffff
                ga2  = (tsbk >> 32) & 0xffff
                ga3  = (tsbk >> 16) & 0xffff
                if self.debug > 10:
                    sys.stderr.write('MOT_GRG_DEL_CMD(0x01): sg:%d ga1:%d ga2:%d ga3:%d\n' % (sg, ga1, ga2, ga3))
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
                    sys.stderr.write('MOT_GRG_CN_GRANT(0x02): freq %s sg:%d sa:%d\n' % (self.channel_id_to_string(ch), sg, sa))
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
                    sys.stderr.write('tsbk02 grant update: chan %s %d %s %d\n' %(self.channel_id_to_string(ch1), ga1, self.channel_id_to_string(ch2), ga2))
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
                    sys.stderr.write('MOT_GRG_CN_GRANT_UPDT(0x03): freq %s sg1:%d freq %s sg2:%d\n' % (self.channel_id_to_string(ch1), sg1, self.channel_id_to_string(ch2), sg2))
            elif mfrid == 0:
                ch1  = (tsbk >> 48) & 0xffff
                ch2   = (tsbk >> 32) & 0xffff
                ga  = (tsbk >> 16) & 0xffff
                f = self.channel_id_to_frequency(ch1)
                self.update_voice_frequency(f, tgid=ga, tdma_slot=self.get_tdma_slot(ch1))
                if f:
                    updated += 1
                if self.debug > 10:
                    sys.stderr.write('tsbk03: freq-t %s freq-r %s ga:%d\n' % (self.channel_id_to_string(ch1), self.channel_id_to_string(ch2), ga))

        elif opcode == 0x16:   # sndcp data ch
            ch1  = (tsbk >> 48) & 0xffff
            ch2  = (tsbk >> 32) & 0xffff
            if self.debug > 10:
                sys.stderr.write('tsbk16 sndcp data ch: chan %x %x\n' % (ch1, ch2))
        elif opcode == 0x28:   # grp_aff_rsp
            mfrid  = (tsbk >> 80) & 0xff
            lg     = (tsbk >> 79) & 0x01
            gav    = (tsbk >> 72) & 0x03
            aga    = (tsbk >> 56) & 0xffff
            ga     = (tsbk >> 40) & 0xffff
            ta     = (tsbk >> 16) & 0xffffff
            if self.debug > 10:
                sys.stderr.write('tsbk28 grp_aff_resp: mfrid: 0x%x, gav: %d, aga: %d, ga: %d, ta: %d\n' % (mfrid, gav, aga, ga, ta))
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
                    sys.stderr.write('GRG_EXENC_CMD(0x30): grg_t:%d, grg_g:%d, grg_a:%d, grg_ssn:%d, sg:%d, keyid:%d, rta:%d\n' % (grg_t, grg_g, grg_a, grg_ssn, sg, keyid, rta))
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
                sys.stderr.write('tsbk34 iden vhf/uhf id %d toff %f spac %f freq %f [%s]\n' % (iden, toff * spac * 0.125 * 1e-3, spac * 0.125, freq * 0.000005, txt[toff_sign]))
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
                    sys.stderr.write('tsbk33 iden up tdma id %d f %d offset %d spacing %d slots/carrier %d\n' % (iden, self.freq_table[iden]['frequency'], self.freq_table[iden]['offset'], self.freq_table[iden]['step'], self.freq_table[iden]['tdma']))

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
                sys.stderr.write('tsbk3d iden id %d toff %f spac %f freq %f\n' % (iden, toff * 0.25, spac * 0.125, freq * 0.000005))
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
                sys.stderr.write('tsbk3a rfss status: syid: %x rfid %x stid %d ch1 %x(%s)\n' %(syid, rfid, stid, chan, self.channel_id_to_string(chan)))
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
                sys.stderr.write('tsbk39 secondary cc: rfid %x stid %d ch1 %x(%s) ch2 %x(%s)\n' %(rfid, stid, ch1, self.channel_id_to_string(ch1), ch2, self.channel_id_to_string(ch2)))
        elif opcode == 0x3b:   # network status
            wacn = (tsbk >> 52) & 0xfffff
            syid = (tsbk >> 40) & 0xfff
            ch1  = (tsbk >> 24) & 0xffff
            f1 = self.channel_id_to_frequency(ch1)
            if f1:
                self.ns_syid = syid
                self.ns_wacn = wacn
                self.ns_chan = f1
            if self.debug > 10:
                sys.stderr.write('tsbk3b net stat: wacn %x syid %x ch1 %x(%s)\n' %(wacn, syid, ch1, self.channel_id_to_string(ch1)))
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
                sys.stderr.write('tsbk3c adjacent: rfid %x stid %d ch1 %x(%s)\n' %(rfid, stid, ch1, self.channel_id_to_string(ch1)))
                if table in self.freq_table:
                    sys.stderr.write('tsbk3c : %s %s\n' % (self.freq_table[table]['frequency'] , self.freq_table[table]['step'] ))
            #else:
            #	sys.stderr.write('tsbk other %x\n' % opcode)
        return updated

    def hunt_cc(self, curr_time):
        if self.cc_timeouts < 6:
            return False
        self.cc_timeouts = 0
        self.cc_list_index += 1
        if self.cc_list_index >= len(self.cc_list):
            self.cc_list_index = 0
        self.trunk_cc = self.cc_list[self.cc_list_index]
        if self.trunk_cc != self.last_trunk_cc:
            self.last_trunk_cc = self.trunk_cc
            if self.debug >=5:
                sys.stderr.write('%f set control channel: %f\n' % (curr_time, self.trunk_cc / 1000000.0))
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
                v0 = int(v[0])				# first parameter is tgid or start of tgid range
		v1 = v0
		if (len(v) > 1) and (int(v[1]) > v0):	# second parameter if present is end of tgid range
                	v1 = int(v[1])
		
		for tg in range(v0, (v1 + 1)):
                	if tg not in d:      # is this a new tg?
                		d[tg] = []   # if so, add to dict (key only, value null)
                		sys.stderr.write('added talkgroup %d from %s\n' % (tg,s))

            except (IndexError, ValueError) as ex:
                continue
    f.close()
    return dict.fromkeys(d)

class rx_ctl (object):
    def __init__(self, debug=0, frequency_set=None, conf_file=None, logfile_workers=None, meta_update=None):
        class _states(object):
            ACQ = 0
            CC = 1
            TO_VC = 2
            VC = 3
        self.states = _states

        self.current_state = self.states.CC
        self.trunked_systems = {}
        self.frequency_set = frequency_set
        self.meta_update = meta_update
        self.meta_state = 0
        self.debug = debug
        self.tgid_hold = None
        self.tgid_hold_until = time.time()
        self.hold_mode = False
        self.TGID_HOLD_TIME = 2.0	# TODO: make more configurable
        self.TGID_SKIP_TIME = 1.0	# TODO: make more configurable
        self.current_nac = None
        self.current_id = 0
        self.current_tgid = None
        self.current_srcaddr = 0
        self.current_grpaddr = 0	# from P25 LCW
        self.current_encrypted = 0
        self.current_slot = None
        self.TSYS_HOLD_TIME = 3.0	# TODO: make more configurable
        self.wait_until = time.time()
        self.configs = {}
        self.nacs = []
        self.logfile_workers = logfile_workers
        self.active_talkgroups = {}
        self.working_frequencies = {}
        self.xor_cache = {}
        self.last_garbage_collect = 0
        self.last_tune_time = 0.0;
        self.last_tune_freq = 0;
        if self.logfile_workers:
            self.input_rate = self.logfile_workers[0]['demod'].input_rate

        if conf_file:
            if conf_file.endswith('.tsv'):
                self.build_config_tsv(conf_file)
            else:
                self.build_config(conf_file)
            self.nacs = self.configs.keys()
            self.current_nac = self.find_next_tsys()
            self.current_state = self.states.CC

            tsys = self.trunked_systems[self.current_nac]

            if self.logfile_workers and tsys.modulation == 'c4fm':
                for worker in self.logfile_workers:
                    worker['demod'].connect_chain('fsk4')

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
        if frequency and self.frequency_set:
            if self.debug > 10:
                sys.stderr.write("%f set_frequency(%s)\n" % (time.time(), frequency))
            if frequency != self.last_tune_freq:
                self.last_tune_time = time.time()
                self.last_tune_freq = frequency
            self.frequency_set(params)

    def do_metadata(self, state, tgid, tag):
        if (state == 1) and (self.meta_state == 1): # don't update more than once for an idle channel (state=1)
            return

        if self.debug > 1:
            sys.stderr.write("%f do_metadata state=%d: [%s] %s\n" % (time.time(), state, tgid, tag))
        self.meta_update(tgid, tag)
        self.meta_state = state

    def add_trunked_system(self, nac):
        assert nac not in self.trunked_systems	# duplicate nac not allowed
        blacklist = {}
        whitelist = None
        tgid_map = {}
        cfg = None
        nac0 = False
        if nac in self.configs:
            cfg = self.configs[nac]
        if nac == 0:
            nac0 = True
        self.trunked_systems[nac] = trunked_system(debug = self.debug, config=cfg, wildcard=nac0)

    def build_config_tsv(self, tsv_filename):
        import csv
        hdrmap = []
        configs = {}
        with open(tsv_filename, 'rb') as csvfile:
            sreader = csv.reader(csvfile, delimiter='\t', quotechar='"', quoting=csv.QUOTE_ALL)
            for row in sreader:
                if row[0].startswith('#'):
                    continue 
                if not hdrmap:
                    # process first line of tsv file - header line
                    for hdr in row:
                        hdr = hdr.replace(' ', '_')
                        hdr = hdr.lower()
                        hdrmap.append(hdr)
                    continue
                fields = {}
                if (len(row) < 4) or (len(row) > 9):
                    sys.stderr.write("Skipping invalid row in %s: %s\n" % (tsv_filename, row))
                    continue
                for i in xrange(len(row)):
                    if row[i]:
                        fields[hdrmap[i]] = row[i]
                        if hdrmap[i] != 'sysname':
                            fields[hdrmap[i]] = fields[hdrmap[i]].lower()
                nac = int(fields['nac'], 0)
                configs[nac] = fields

        if 0 in configs: # if NAC 0 exists, remove all other configs
            for nac in configs.keys():
                if nac != 0:
                    configs.pop(nac)

        if len(configs) < 1:
            sys.stderr.write("No valid trunking configs. Aborting!\n")
            sys.exit(1)

        self.setup_config(configs)

    def build_config(self, config_filename):
        import ConfigParser
        config = ConfigParser.ConfigParser()
        config.read(config_filename)
        configs = {}
        for section in config.sections():
            nac = int(config.get(section, 'nac'), 0)	# nac required
            assert nac != 0				# nac=0 not allowed
            assert nac not in configs	# duplicate nac not allowed
            configs[nac] = {}
            for option in config.options(section):
                configs[nac][option] = config.get(section, option).lower()
            configs[nac]['sysname'] = section
        self.setup_config(configs)

    def add_default_config(self, nac, cclist=[], offset=0, whitelist=None, blacklist={}, tgid_map={}, sysname=None, center_frequency=None, modulation='cqpsk'):
        if nac in self.configs.keys():
            return
        if nac not in self.trunked_systems.keys():
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
        if not sysname:
            sysname = 'NAC 0x%x' % nac
        if not cclist:
            cclist = [tsys.rfss_chan]
            cclist.extend(tsys.secondary.keys())
            tsys.cc_list = cclist
        self.configs[nac] = {'cclist':cclist, 'offset':offset, 'whitelist':whitelist, 'blacklist':blacklist, 'tgid_map':tgid_map, 'sysname': sysname, 'center_frequency': center_frequency, 'modulation':modulation}
        self.current_nac = nac
        self.current_state = self.states.CC
        if nac not in self.nacs:
            self.nacs.append(nac)

    def setup_config(self, configs):
        for nac in configs:
            self.configs[nac] = {'cclist':[], 'offset':0, 'whitelist':None, 'blacklist':{}, 'tgid_map':{}, 'sysname': configs[nac]['sysname'], 'center_frequency': None}
            for f in configs[nac]['control_channel_list'].split(','):
                self.configs[nac]['cclist'].append(get_frequency(f))
            if 'offset' in configs[nac]:
                self.configs[nac]['offset'] = int(configs[nac]['offset'])
            if 'modulation' in configs[nac]:
                self.configs[nac]['modulation'] = configs[nac]['modulation']
            else:
                self.configs[nac]['modulation'] = 'cqpsk'
            for k in ['whitelist', 'blacklist']:
                if k in configs[nac]:
                    sys.stderr.write("Reading %s file\n" % k)
                    self.configs[nac][k + ".file"] = configs[nac][k]
                    self.configs[nac][k] = get_int_dict(configs[nac][k])
            if 'tgid_tags_file' in configs[nac]:
                import csv
                with open(configs[nac]['tgid_tags_file'], 'rb') as csvfile:
                    sreader = csv.reader(csvfile, delimiter='\t', quotechar='"', quoting=csv.QUOTE_ALL)
                    for row in sreader:
                        try:
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

            self.add_trunked_system(nac)

    def find_next_tsys(self):
        self.current_id += 1
        if self.current_id >= len(self.nacs):
            self.current_id = 0
        return self.nacs[self.current_id]

    def to_json(self):
        d = {'json_type': 'trunk_update'}
        for nac in self.trunked_systems.keys():
            d[nac] = json.loads(self.trunked_systems[nac].to_json())
        d['srcaddr'] = self.current_srcaddr
        d['grpaddr'] = self.current_grpaddr
        d['encrypted'] = self.current_encrypted
        d['nac'] = self.current_nac
        return json.dumps(d)

    def dump_tgids(self):
        for nac in self.trunked_systems.keys():
            self.trunked_systems[nac].dump_tgids()

    def to_string(self):
        s = ''
        for nac in self.trunked_systems:
            s += '\n====== NAC 0x%x ====== %s ======\n' % (nac, self.trunked_systems[nac].sysname)
            s += self.trunked_systems[nac].to_string()
        return s

    def process_qmsg(self, msg):
        m_proto = ctypes.c_int16(msg.type() >> 16).value
        m_type = ctypes.c_int16(msg.type() & 0xffff).value
        m_ts = float(msg.arg2())

        if m_proto > 0:	# P25 m_proto=0
            return

        if (m_ts < self.last_tune_time) and (m_type != -2):
            if self.debug > 10:
                sys.stderr.write("type %d at %f with ts %f ignored due to frequency change\n" % (m_type, time.time(), m_ts))
            return

        updated = 0
        curr_time = time.time()
        if m_type == -3:	# P25 call signalling data
            if self.debug > 10:
                sys.stderr.write("process_qmsg: P25 info: %s\n" % msg.to_string())
            js = json.loads(msg.to_string())
            if ('srcaddr' in js) and (js['srcaddr'] != 0):
                self.current_srcaddr = js['srcaddr']
            if ('grpaddr' in js):
                self.current_grpaddr = js['grpaddr']
            if 'encrypted' in js:
                self.current_encrypted = js['encrypted']
            return 
        elif m_type == -2:	# request from gui
            cmd = msg.to_string()
            if self.debug > 10:
                sys.stderr.write('process_qmsg: command: %s\n' % cmd)
            self.update_state(cmd, curr_time, int(msg.arg1()))
            return
        elif m_type == -1:	# timeout
            if self.debug > 10:
                sys.stderr.write('%f process_data_unit timeout\n' % time.time())
            self.update_state('timeout', curr_time)
            if self.logfile_workers:
                self.logging_scheduler(curr_time)
            return
        elif m_type < 0:
            sys.stderr.write('unknown message type %d\n' % (m_type))
            return
        s = msg.to_string()
        # nac is always 1st two bytes
        nac = (ord(s[0]) << 8) + ord(s[1])
        if nac == 0xffff:
            if (m_type != 7) and (m_type != 12): # TDMA duid (end of call etc)
                self.update_state('tdma_duid%d' % m_type, curr_time)
                return
            else: # voice channel derived TSBK or MBT PDU
                nac = self.current_nac
        s = s[2:]
        if self.debug > 10:
            sys.stderr.write('nac %x type %d at %f state %d len %d\n' %(nac, m_type, time.time(), self.current_state, len(s)))
        if (m_type == 7 or m_type == 12) and nac not in self.trunked_systems:
            if not self.configs:
                # TODO: allow whitelist/blacklist rather than blind automatic-add
                self.add_trunked_system(nac)
            else:
                # If trunk.tsv file configured with nac=0, use decoded nac instead
                if 0 in self.trunked_systems:
                    sys.stderr.write("%f Reconfiguring NAC from 0x000 to 0x%x\n" % (time.time(), nac))
                    self.trunked_systems[nac] = self.trunked_systems.pop(0)
                    self.configs[nac] = self.configs.pop(0)
                    self.nacs = self.configs.keys()
                    self.current_nac = nac
                else:
                    sys.stderr.write("%f NAC %x not configured\n" % (time.time(), nac))
                return
        if m_type == 7:	# trunk: TSBK
            t = 0
            for c in s:
                t = (t << 8) + ord(c)
            updated += self.trunked_systems[nac].decode_tsbk(t)
        elif m_type == 12:	# trunk: MBT
            s1 = s[:10]		# header without crc
            s2 = s[12:]
            header = mbt_data = 0
            for c in s1:
                header = (header << 8) + ord(c)
            for c in s2:
                mbt_data = (mbt_data << 8) + ord(c)

            fmt = (header >> 72) & 0x1f
            sap = (header >> 64) & 0x3f
            src = (header >> 32) & 0xffffff
            if fmt != 0x17: # only Extended Format MBT presently supported
                return

            opcode = (header >> 16) & 0x3f
            if self.debug > 10:
                sys.stderr.write('type %d at %f state %d len %d/%d opcode %x [%0x/%0x]\n' %(m_type, time.time(), self.current_state, len(s1), len(s2), opcode, header,mbt_data))
            updated += self.trunked_systems[nac].decode_mbt_data(opcode, src, header << 16, mbt_data << 32)

        if nac != self.current_nac:
            if self.debug > 10: # this is occasionally expected if cycling between different tsys
                sys.stderr.write("%f received NAC %x does not match expected NAC %x\n" % (time.time(), nac, self.current_nac))
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
        sys.stderr.write('%f release worker frequency %d\n' % (curr_time, frequency))

    def free_talkgroup(self, frequency, tgid, curr_time):
        decoder = self.working_frequencies[frequency]['worker']['decoder']
        tdma_slot = self.working_frequencies[frequency]['tgids'][tgid]['tdma_slot']
        index = tdma_slot
        if tdma_slot is None:
            index = 0
        self.working_frequencies[frequency]['tgids'].pop(tgid)
        sys.stderr.write('%f release tgid %d frequency %d\n' % (curr_time, tgid, frequency))

    def logging_scheduler(self, curr_time):
        tsys = self.trunked_systems[self.current_nac]
        for tgid in tsys.get_updated_talkgroups(curr_time):
            frequency = tsys.talkgroups[tgid]['frequency']
            tdma_slot = tsys.talkgroups[tgid]['tdma_slot']
            # see if this tgid active on any other freq(s)
            other_freqs = [f for f in self.working_frequencies if f != frequency and tgid in self.working_frequencies[f]['tgids']]
            if other_freqs:
                sys.stderr.write('%f tgid %d slot %s frequency %d found on other frequencies %s\n' % (curr_time, tgid, tdma_slot, frequency, ','.join(['%s' % f for f in other_freqs])))
                for f in other_freqs:
                    self.free_talkgroup(f, tgid, curr_time)
                    if not self.working_frequencies[f]['tgids']:
                        self.free_frequency(f, curr_time)
            diff = abs(tsys.center_frequency - frequency)
            if diff > self.input_rate/2:
                #sys.stderr.write('%f request for frequency %d tgid %d failed, offset %d exceeds maximum %d\n' % (curr_time, frequency, tgid, diff, self.input_rate/2))
                continue

            update = True
            if frequency in self.working_frequencies:
                tgids = self.working_frequencies[frequency]['tgids']
                if tgid in tgids:
                    if tgids[tgid]['tdma_slot'] == tdma_slot:
                        update = False
                    else:
                        sys.stderr.write('%f slot switch %s was %s tgid %d frequency %d\n' % (curr_time, tdma_slot, tgids[tgid]['tdma_slot'], tgid, frequency))
                        worker = self.working_frequencies[frequency]['worker']
                else:
                    #active_tdma_slots = [tgids[tg]['tdma_slot'] for tg in tgids]
                    sys.stderr.write("%f new tgid %d slot %s arriving on already active frequency %d\n" % (curr_time, tgid, tdma_slot, frequency))
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
                sys.stderr.write('%f starting worker frequency %d tg %d slot %s\n' % (curr_time, frequency, tgid, tdma_slot))
            self.working_frequencies[frequency]['tgids'][tgid] = {'updated': curr_time, 'tdma_slot': tdma_slot}
            if not update:
                continue
            filename = 'tgid-%d-%f.wav' % (tgid, curr_time)
            sys.stderr.write('%f update frequency %d tg %d slot %s file %s\n' % (curr_time, frequency, tgid, tdma_slot, filename))
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
        for frequency, tgid in gc_tgids:	# expire talkgroups
            self.free_talkgroup(frequency, tgid, curr_time)
        for frequency in gc_frequencies:	# expire working frequencies
            self.free_frequency(frequency, curr_time)

    def update_state(self, command, curr_time, cmd_data = 0):
        if not self.configs:
            return	# run in "manual mode" if no conf

        nac = self.current_nac
        tsys = self.trunked_systems[nac]

        new_frequency = None
        new_tgid = None
        new_state = None
        new_nac = None
        new_slot = None

        if command == 'timeout':
            if self.current_state == self.states.CC:
                if self.debug > 0:
                    sys.stderr.write("%f control channel timeout\n" % time.time())
                tsys.cc_timeouts += 1
            elif self.current_state != self.states.CC:
                if self.debug > 1:
                    sys.stderr.write("%f voice timeout\n" % time.time())
                if self.hold_mode is False:
                    self.current_tgid = None
                self.current_srcaddr = 0
                self.current_grpaddr = 0
                self.current_encrypted = 0
                new_state = self.states.CC
                new_frequency = tsys.trunk_cc
        elif command == 'update':
            tsys.expire_patches()
            if self.current_state == self.states.CC:
                desired_tgid = None
                if (self.tgid_hold is not None) and (self.tgid_hold_until > curr_time):
                    if self.debug > 1:
                        sys.stderr.write("%f hold active tg(%s)\n" % (time.time(), self.tgid_hold))
                    desired_tgid = self.tgid_hold
                elif (self.tgid_hold is not None) and (self.hold_mode == False):
                    self.tgid_hold = None
                new_frequency, new_tgid, tdma_slot, srcaddr = tsys.find_talkgroup(curr_time, tgid=desired_tgid, hold=self.hold_mode)
                if new_frequency:
                    if self.debug > 0:
                        tslot = tdma_slot if tdma_slot is not None else '-'
                        sys.stderr.write("%f voice update:  tg(%s), freq(%s), slot(%s), prio(%d)\n" % (time.time(), new_tgid, new_frequency, tslot, tsys.get_prio(new_tgid)))
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
                        sys.stderr.write("%f voice preempt: tg(%s), freq(%s), slot(%s), prio(%d)\n" % (time.time(), new_tgid, new_frequency, tslot, tsys.get_prio(new_tgid)))
                    new_state = self.states.TO_VC
                    self.current_tgid = new_tgid
                    self.current_srcaddr = srcaddr
                    self.tgid_hold = new_tgid
                    self.tgid_hold_until = max(curr_time + self.TGID_HOLD_TIME, self.tgid_hold_until)
                    self.wait_until = curr_time + self.TSYS_HOLD_TIME
                    new_slot = tdma_slot
                    self.do_metadata(0, new_tgid,tsys.get_tag(new_tgid))
                else:
                    new_frequency = None
        elif command == 'duid3' or command == 'tdma_duid3': # termination, no channel release
            if self.current_state != self.states.CC:
                self.wait_until = curr_time + self.TSYS_HOLD_TIME
                self.tgid_hold = self.current_tgid
                self.tgid_hold_until = max(curr_time + self.TGID_HOLD_TIME, self.tgid_hold_until)
        elif command == 'duid15' or command == 'tdma_duid15': # termination with channel release
            if self.current_state != self.states.CC:
                if self.debug > 1:
                    sys.stderr.write("%f %s, tg(%d)\n" % (time.time(), command, self.current_tgid))
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
        elif command == 'duid0' or command == 'duid5' or command == 'duid10' or command == 'tdma_duid5':
            if self.current_state == self.states.TO_VC:
                new_state = self.states.VC
            self.tgid_hold = self.current_tgid
            self.tgid_hold_until = max(curr_time + self.TGID_HOLD_TIME, self.tgid_hold_until)
            self.wait_until = curr_time + self.TSYS_HOLD_TIME
        elif command == 'duid7' or command == 'duid12': # tsbk/pdu should never arrive here...
            pass
        elif command == 'hold':
            if cmd_data > 0:
                    self.tgid_hold = cmd_data
                    self.tgid_hold_until = curr_time + 86400 * 10000
                    self.hold_mode = True
                    if self.debug > 0:
                        sys.stderr.write ('%f set hold tg(%s) until %f\n' % (time.time(), self.tgid_hold, self.tgid_hold_until))
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
                        sys.stderr.write ('%f set hold tg(%s) until %f\n' % (time.time(), self.tgid_hold, self.tgid_hold_until))
            elif self.hold_mode is True:
                if self.debug > 0:
                    sys.stderr.write ('%f clear hold tg(%s)\n' % (time.time(), self.tgid_hold))
                self.current_tgid = None
                self.tgid_hold = None
                self.tgid_hold_until = curr_time
                self.hold_mode = False
        elif command == 'skip' or command == 'lockout':
            if self.current_tgid and cmd_data == self.current_id:
                end_time = None
                if command == 'skip':
                    end_time = curr_time + self.TGID_SKIP_TIME
                tsys.add_blacklist(self.current_tgid, end_time=end_time)
                self.current_tgid = None
                self.tgid_hold = None
                self.tgid_hold_until = curr_time
                self.hold_mode = False
                if self.current_state != self.states.CC:
                    new_state = self.states.CC
                    new_frequency = tsys.trunk_cc
            else:
                if (cmd_data <= 0) or (cmd_data > 65534):
                    if self.debug > 0:
                        sys.stderr.write("%f blacklist tgid(%d) out of range (1-65534)\n" % (time.time(), cmd_data))
                    return
                tsys.add_blacklist(cmd_data)
        elif command == 'whitelist':
            if (cmd_data <= 0) or (cmd_data > 65534):
                if self.debug > 0:
                    sys.stderr.write("%f whitelist tgid(%d) out of range (1-65534)\n" % (time.time(), cmd_data))
                return
            tsys.add_whitelist(cmd_data)
            if self.current_tgid and self.whitelist and self.current_id not in self.whitelist:
                self.current_tgid = None
                self.tgid_hold = None
                self.tgid_hold_until = curr_time
                self.hold_mode = False
                if self.current_state != self.states.CC:
                    new_state = self.states.CC
                    new_frequency = tsys.trunk_cc
        elif command == 'reload':
            nac = self.current_nac
            sys.stderr.write("%f reloading blacklist & whitelist files for nac(%x)\n" % (time.time(), nac))
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
                sys.stderr.write("%f reset tsys to NAC 0 after control channel change\n" % time.time())
            self.trunked_systems[0] = self.trunked_systems.pop(self.current_nac)
            self.configs[0] = self.configs.pop(self.current_nac)
            self.nacs = self.configs.keys()
            self.current_nac = 0
            self.current_state = self.states.CC
            self.current_tgid = None
            self.current_srcaddr = 0
            self.current_grpaddr = 0
            self.current_encrypted = 0
            tsys.reset()

        if self.current_state != self.states.CC and self.tgid_hold_until <= curr_time and self.hold_mode is False and new_state is None:
            if self.debug > 1:
                sys.stderr.write("%f release tg(%s)\n" % (time.time(), self.current_tgid))
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
