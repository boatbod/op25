
# Copyright 2011, 2012, 2013 KA1RBI
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
# FIXME: hideously mixes indentation, some is tabs and some is spaces
#

import time

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

class trunked_system (object):
    def __init__(self, debug=0, config=None):
	self.debug = debug
	self.freq_table = {}
	self.stats = {}
	self.stats['tsbks'] = 0
	self.stats['crc'] = 0
	self.tsbk_cache = {}
	self.secondary = {}
	self.adjacent = {}
	self.rfss_syid = 0
	self.rfss_rfid = 0
	self.rfss_stid = 0
	self.rfss_chan = 0
	self.rfss_txchan = 0
	self.ns_syid = 0
	self.ns_wacn = 0
	self.ns_chan = 0
	self.voice_frequencies = {}
	self.blacklist = {}
	self.whitelist = None
	self.tgid_map = None
	self.offset = 0
	self.sysname = 0
	self.trunk_cc = 0
        if config:
            self.blacklist = config['blacklist']
            self.whitelist = config['whitelist']
            self.tgid_map  = config['tgid_map']
            self.offset    = config['offset']
            self.sysname   = config['sysname']
            self.trunk_cc  = config['cclist'][0]	# TODO: scan thru list

    def to_string(self):
        s = []
        s.append('rf: syid %x rfid %d stid %d frequency %f uplink %f' % ( self.rfss_syid, self.rfss_rfid, self.rfss_stid, float(self.rfss_chan) / 1000000.0, float(self.rfss_txchan) / 1000000.0))
        s.append('net: syid %x wacn %x frequency %f' % ( self.ns_syid, self.ns_wacn, float(self.ns_chan) / 1000000.0))
        s.append('secondary control channel(s): %s' % ','.join(['%f' % (float(k) / 1000000.0) for k in self.secondary.keys()]))
        s.append('stats: tsbks %d crc %d' % (self.stats['tsbks'], self.stats['crc']))
	s.append('')
        t = time.time()
        for f in self.voice_frequencies:
            s.append('voice frequency %f tgid %d %4.1fs ago count %d' %  (f / 1000000.0, self.voice_frequencies[f]['tgid'], t - self.voice_frequencies[f]['time'], self.voice_frequencies[f]['counter']))
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

# return frequency in Hz
    def channel_id_to_frequency(self, id):
	table = (id >> 12) & 0xf
	channel = id & 0xfff
	if table not in self.freq_table:
		return None
	return self.freq_table[table]['frequency'] + self.freq_table[table]['step'] * channel

    def channel_id_to_string(self, id):
	table = (id >> 12) & 0xf
	channel = id & 0xfff
	if table not in self.freq_table:
		return "%x-%d" % (table, channel)
        return "%f" % ((self.freq_table[table]['frequency'] + self.freq_table[table]['step'] * channel) / 1000000.0)

    def get_tag(self, tgid):
        if not tgid:
            return ""
        if tgid not in self.tgid_map:
            return "Talkgroup ID %d [0x%x]" % (tgid, tgid)
        return self.tgid_map[tgid]

    def update_voice_frequency(self, frequency, tgid=None):
        if frequency is None:
            return
        if frequency not in self.voice_frequencies:
            self.voice_frequencies[frequency] = {'counter':0}
        self.voice_frequencies[frequency]['tgid'] = tgid
        self.voice_frequencies[frequency]['counter'] += 1
        self.voice_frequencies[frequency]['time'] = time.time()

    def find_voice_frequency(self, start_time, tgid=None):
        for frequency in self.voice_frequencies:
            if self.voice_frequencies[frequency]['time'] < start_time:
                continue
            active_tgid = self.voice_frequencies[frequency]['tgid']
            if active_tgid in self.blacklist:
                continue
            if self.whitelist and active_tgid not in self.whitelist:
                continue
            if tgid is None or tgid == active_tgid:
                return frequency, active_tgid
        return None, None

    def add_blacklist(self, tgid):
        if not tgid:
            return
        self.blacklist[tgid] = 1

    def decode_mbt_data(self, opcode, header, mbt_data):
        if self.debug > 10:
            print "decode_mbt_data: %x %x" %(opcode, mbt_data)
	if opcode == 0x0:  # grp voice channel grant
		ch1  = (mbt_data >> 64) & 0xffff
		ch2  = (mbt_data >> 48) & 0xffff
		ga   = (mbt_data >> 32) & 0xffff
		if self.debug > 10:
			print "mbt00 voice grant ch1 %x ch2 %x addr 0x%x" %(ch1, ch2, ga)
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
		if self.debug > 10:
			print "mbt3c adjacent sys %x rfid %x stid %x ch1 %x ch2 %x f1 %s f2 %s" %(syid, rfid, stid, ch1, ch2, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2))
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
			print "mbt3b net stat sys %x wacn %x ch1 %s ch2 %s" %(syid, wacn, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2))
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
			print "mbt3a rfss stat sys %x rfid %x stid %x ch1 %s ch2 %s" %(syid, rfid, stid, self.channel_id_to_string(ch1), self.channel_id_to_string(ch2))
	#else:
	#	print "mbt other %x" % opcode

    def decode_tsbk(self, tsbk):
	self.stats['tsbks'] += 1
        updated = 0
#	if crc16(tsbk, 12) != 0:
#		self.stats['crc'] += 1
#		return	# crc check failed
	tsbk = tsbk << 16	# for missing crc
	opcode = (tsbk >> 88) & 0x3f
	if self.debug > 10:
		print "TSBK: 0x%02x 0x%024x" % (opcode, tsbk)
	if opcode == 0x02:   # group voice chan grant update
		mfrid  = (tsbk >> 80) & 0xff
		ch1  = (tsbk >> 64) & 0xffff
		ga1  = (tsbk >> 48) & 0xffff
		ch2  = (tsbk >> 32) & 0xffff
		ga2  = (tsbk >> 16) & 0xffff
		if mfrid == 0x90:
			if self.debug > 10:
				ch1  = (tsbk >> 56) & 0xffff
				f1 = self.channel_id_to_frequency(ch1)
				if f1 == None: f1 = 0
				print "tsbk02[90] %x %f" % (ch1, f1 / 1000000.0)
		else:
			f1 = self.channel_id_to_frequency(ch1)
			f2 = self.channel_id_to_frequency(ch2)
			self.update_voice_frequency(f1, tgid=ga1)
			if f1 != f2:
				self.update_voice_frequency(f2, tgid=ga2)
			if f1:
				updated += 1
			if f2:
				updated += 1
			if self.debug > 10:
				print "tsbk02 grant update: chan %s %d %s %d" %(self.channel_id_to_string(ch1), ga1, self.channel_id_to_string(ch2), ga2)
	elif opcode == 0x16:   # sndcp data ch
		ch1  = (tsbk >> 48) & 0xffff
		ch2  = (tsbk >> 32) & 0xffff
		if self.debug > 10:
			print "tsbk16 sndcp data ch: chan %x %x" %(ch1, ch2)
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
			print "tsbk34 iden vhf/uhf id %d toff %f spac %f freq %f [%s]" % (iden, toff * spac * 0.125 * 1e-3, spac * 0.125, freq * 0.000005, txt[toff_sign])
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
			print "tsbk3d iden id %d toff %f spac %f freq %f" % (iden, toff * 0.25, spac * 0.125, freq * 0.000005)
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
			print "tsbk3a rfss status: syid: %x rfid %x stid %d ch1 %x(%s)" %(syid, rfid, stid, chan, self.channel_id_to_string(chan))
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
		if self.debug > 10:
			print "tsbk39 secondary cc: rfid %x stid %d ch1 %x(%s) ch2 %x(%s)" %(rfid, stid, ch1, self.channel_id_to_string(ch1), ch2, self.channel_id_to_string(ch2))
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
			print "tsbk3b net stat: wacn %x syid %x ch1 %x(%s)" %(wacn, syid, ch1, self.channel_id_to_string(ch1))
	elif opcode == 0x3c:   # adjacent status
		rfid = (tsbk >> 48) & 0xff
		stid = (tsbk >> 40) & 0xff
		ch1  = (tsbk >> 24) & 0xffff
		table = (ch1 >> 12) & 0xf
		f1 = self.channel_id_to_frequency(ch1)
		if f1 and table in self.freq_table:
			self.adjacent[f1] = 'rfid: %d stid:%d uplink:%f tbl:%d' % (rfid, stid, (f1 + self.freq_table[table]['offset']) / 1000000.0, table)
		if self.debug > 10:
			print "tsbk3c adjacent: rfid %x stid %d ch1 %x(%s)" %(rfid, stid, ch1, self.channel_id_to_string(ch1))
			if table in self.freq_table:
			        print "tsbk3c : %s %s" % (self.freq_table[table]['frequency'] , self.freq_table[table]['step'] )
	#else:
	#	print "tsbk other %x" % opcode
        return updated


class rx_ctl (object):
    def __init__(self, debug=0, frequency_set=None, conf_file=None):
        class _states(object):
            ACQ = 0
            CC = 1
            TO_VC = 2
            VC = 3
        self.states = _states

        self.state = self.states.CC
        self.trunked_systems = {}
        self.frequency_set = frequency_set
        self.debug = debug
        self.tgid_hold = None
        self.tgid_hold_until = time.time()
        self.TGID_HOLD_TIME = 2.0	# TODO: make more configurable
        self.current_nac = None
        self.current_id = 0
        self.TSYS_HOLD_TIME = 3.0	# TODO: make more configurable
        self.wait_until = time.time()
        self.configs = {}

        if conf_file:
            self.build_config(conf_file)
            self.nacs = self.configs.keys()
            self.current_nac = self.nacs[0]
            self.current_state = self.states.CC

    def set_frequency(self, params):
        frequency = params['freq']
        if frequency and self.frequency_set:
            self.frequency_set(params)

    def add_trunked_system(self, nac):
        assert nac not in self.trunked_systems	# duplicate nac not allowed
        blacklist = {}
        whitelist = None
        tgid_map = {}
        cfg = None
        if nac in self.configs:
            cfg = self.configs[nac]
        self.trunked_systems[nac] = trunked_system(debug = self.debug, config=cfg)

    def build_config(self, config_filename):
        import ConfigParser
        config = ConfigParser.ConfigParser()
        config.read(config_filename)
        configs = {}
        for section in config.sections():
            nac = int(config.get(section, 'nac'), 0) # nac required
            assert nac != 0			# nac=0 not allowed
            assert nac not in configs		# duplicate nac not allowed
            configs[nac] = {}
            for option in config.options(section):
                configs[nac][option] = config.get(section, option).lower()
            configs[nac]['sysname'] = section

        for nac in configs:
            self.configs[nac] = {'cclist':[], 'offset':0, 'whitelist':None, 'blacklist':{}, 'tgid_map':{}, 'sysname': configs[nac]['sysname']}
            for f in configs[nac]['control_channel_list'].split(','):
                if f.find('.') == -1:	# assume in Hz
                    self.configs[nac]['cclist'].append(int(f))
                else:     # assume in MHz due to '.'
                    self.configs[nac]['cclist'].append(int(float(f) * 1000000))
            if 'offset' in configs[nac]:
                self.configs[nac]['offset'] = int(configs[nac]['offset'])
            if 'modulation' in configs[nac]:
                self.configs[nac]['modulation'] = configs[nac]['modulation']
            else:
                self.configs[nac]['modulation'] = 'cqpsk'
            if 'whitelist' in configs[nac]:
                self.configs[nac]['whitelist'] = dict.fromkeys([int(d) for d in configs[nac]['whitelist'].split(',')])
            if 'blacklist' in configs[nac]:
                self.configs[nac]['blacklist'] = dict.fromkeys([int(d) for d in configs[nac]['blacklist'].split(',')])
            if 'tgid_tags_file' in configs[nac]:
                import csv
                with open(configs[nac]['tgid_tags_file'], 'rb') as csvfile:
                    sreader = csv.reader(csvfile, delimiter='\t', quotechar='"', quoting=csv.QUOTE_ALL)
                    for row in sreader:
                        tgid = int(row[0])
                        txt = row[1]
                        self.configs[nac]['tgid_map'][tgid] = txt

            self.add_trunked_system(nac)

    def find_next_tsys(self):
        self.current_id += 1
        if self.current_id >= len(self.nacs):
            self.current_id = 0
        return self.nacs[self.current_id]

    def to_string(self):
        s = ''
        for nac in self.trunked_systems:
            s += '\n====== NAC 0x%x ====== %s ======\n' % (nac, self.trunked_systems[nac].sysname)
            s += self.trunked_systems[nac].to_string()
        return s

    def process_qmsg(self, msg):
        type = msg.type()
        updated = 0
        curr_time = time.time()
        if type == -2:
            cmd = msg.to_string()
            if self.debug > 10:
                print "process_qmsg: command: %s" % cmd
            self.update_state(cmd, curr_time)
            return
        elif type == -1:
            print "process_data_unit timeout"
            self.update_state('timeout', curr_time)
            return
        s = msg.to_string()
        # nac is always 1st two bytes
        nac = (ord(s[0]) << 8) + ord(s[1])
        s = s[2:]
        if self.debug > 10:
            print "nac %x type %d at %f state %d len %d" %(nac, type, time.time(), self.state, len(s))
        if (type == 7 or type == 12) and nac not in self.trunked_systems:
            if not self.configs:
                # TODO: allow whitelist/blacklist rather than blind automatic-add
                self.add_trunked_system(nac)
            else:
                return
        if type == 7:	# trunk: TSBK
            t = 0
            for c in s:
                t = (t << 8) + ord(c)
            updated += self.trunked_systems[nac].decode_tsbk(t)
	elif type == 12:	# trunk: MBT
            s1 = s[:10]
            s2 = s[10:]
            header = mbt_data = 0
            for c in s1:
                header = (header << 8) + ord(c)
            for c in s2:
                mbt_data = (mbt_data << 8) + ord(c)
            opcode = (header >> 16) & 0x3f
            if self.debug > 10:
                print "type %d at %f state %d len %d/%d opcode %x [%x/%x]" %(type, time.time(), self.state, len(s1), len(s2), opcode, header,mbt_data)
            self.trunked_systems[nac].decode_mbt_data(opcode, header << 16, mbt_data << 32)

        if nac != self.current_nac:
            return

        if updated:
            self.update_state('update', curr_time)
        else:
            self.update_state('duid%d' % type, curr_time)

    def update_state(self, command, curr_time):
        if not self.configs:
            return	# run in "manual mode" if no conf

        nac = self.current_nac
        tsys = self.trunked_systems[nac]

        new_frequency = None
        new_tgid = None
        new_state = None
        new_nac = None

        if command == 'timeout' or command == 'duid15':
            if self.current_state != self.states.CC:
                new_state = self.states.CC
                new_frequency = tsys.trunk_cc
        elif command == 'update':
            if self.current_state == self.states.CC:
                desired_tgid = None
                if self.tgid_hold_until > curr_time:
                    desired_tgid = self.tgid_hold
                new_frequency, new_tgid = tsys.find_voice_frequency(curr_time, tgid=desired_tgid)
                if new_frequency:
                    new_state = self.states.TO_VC
                    self.current_tgid = new_tgid
        elif command == 'duid3':
            if self.current_state != self.states.CC:
                new_state = self.states.CC
                new_frequency = tsys.trunk_cc
        elif command == 'duid0' or command == 'duid5' or command == 'duid10':
            if self.state == self.states.TO_VC:
                new_state = self.states.VC
            self.tgid_hold = self.current_tgid
            self.tgid_hold_until = max(curr_time + self.TGID_HOLD_TIME, self.tgid_hold_until)
            self.wait_until = curr_time + self.TSYS_HOLD_TIME
        elif command == 'duid7' or command == 'duid12':
            pass
        elif command == 'set_hold':
            if self.current_tgid:
                self.tgid_hold = self.current_tgid
                self.tgid_hold_until = curr_time + 86400 * 10000
                print 'set hold until %f' % self.tgid_hold_until
        elif command == 'unset_hold':
            if self.current_tgid:
                self.current_tgid = None
                self.tgid_hold = None
                self.tgid_hold_until = curr_time
        elif command == 'skip':
            pass	# TODO
        elif command == 'lockout':
            if self.current_tgid:
                tsys.add_blacklist(self.current_tgid)
                self.current_tgid = None
                self.tgid_hold = None
                self.tgid_hold_until = curr_time
                if self.current_state != self.states.CC:
                    new_state = self.states.CC
                    new_frequency = tsys.trunk_cc
        else:
            print 'update_state: unknown command: %s\n' % command
            assert 0 == 1

        if self.wait_until <= curr_time and self.tgid_hold_until <= curr_time:
            self.wait_until = curr_time + self.TSYS_HOLD_TIME
            new_nac = self.find_next_tsys()

        if new_nac:
            nac = self.current_nac = new_nac
            tsys = self.trunked_systems[nac]
            new_frequency = tsys.trunk_cc
            self.current_tgid = None

        if new_frequency:
            self.set_frequency({'freq': new_frequency, 'tgid': self.current_tgid, 'offset': tsys.offset, 'tag': tsys.get_tag(self.current_tgid), 'nac': nac, 'system': tsys.sysname})

        if new_state:
            self.current_state = new_state

def main():
	q = 0x3a000012ae01013348704a54
	rc = crc16(q,12)
	print "should be zero: %x" % rc
	assert rc == 0

	q = 0x3a001012ae01013348704a54
	rc = crc16(q,12)
	print "should be nonzero: %x" % rc
	assert rc != 0

	t = trunked_system(debug=255)
	q = 0x3a000012ae0101334870
	t.decode_tsbk(q)

	q = 0x02900031210020018e7c
	t.decode_tsbk(q)

if __name__ == '__main__':
	main()
