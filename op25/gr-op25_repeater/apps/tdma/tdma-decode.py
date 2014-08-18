#! /usr/bin/python

# P25 TDMA Decoder (C) Copyright 2013 KA1RBI
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

"""
Decode a file of P25 TDMA symbols and write out all detected voice codewords

After FEC decoding, print the resulting "B" vectors (49 bits per CW).

Optionally, dump the timeslot info (type, position, type of content)

The input file must contain the demodulated symbols, one per character
using the low-order two bits of each byte
"""

import sys
import numpy as np
from optparse import OptionParser

from bit_utils import *
import isch
import duid
import lfsr
from vf import process_v

SUPERFRAME_LEN = 2160

def main():
        parser = OptionParser()
        parser.add_option("-v", "--verbose", action="store_true", default=False)
        parser.add_option("-i", "--input-file", type="string", default=None, help="input file name")
        parser.add_option("-n", "--nac", type="int", default=0, help="NAC")
        parser.add_option("-s", "--sysid", type="int", default=0, help="sysid")
        parser.add_option("-w", "--wacn", type="int", default=0, help="WACN")
        (options, args) = parser.parse_args()
        if len(args) != 0:
            parser.print_help()
            sys.exit(1)
	file = options.input_file

	my_isch = isch.p25p2_isch()
	my_duid = duid.p25p2_duid()
	my_lfsr = lfsr.p25p2_lfsr(options.nac, options.sysid, options.wacn)
	#print 'nac: %d' % options.nac

	d = open(file).read()

	symbols = []
	for c in d:
		symbols.append(ord(c))

	sync0= bits_to_dibits(mk_array(0x575d57f7ff,40))
	sync_start = find_sym(sync0, symbols)
	assert sync_start > 0	# unable to locate any sync sequence
	superframe = -1
	for i in xrange(sync_start, sync_start + (180*32), 180):
		chn, loc, fr, cnt = my_isch.decode_isch ( symbols [ i : i + 20 ])
		if chn == 0 and loc == 0:
			superframe = i
			break
	assert superframe > 0	# unable to locate start of superframe

	errors = 0
	for i in xrange(superframe,len(symbols)-SUPERFRAME_LEN,SUPERFRAME_LEN):
		syms1 = symbols[i + 10: i + SUPERFRAME_LEN + 10]
		syms2 = np.array(syms1) ^ my_lfsr.xorsyms
		for j in xrange(12):
			if options.verbose:
				print '%s superframe %d timeslot %d %s' % ('=' * 20, i, j, '=' * 20)
			chn, loc, fr, cnt = my_isch.decode_isch ( symbols [ i + (j*180) : i + (j*180) + 20 ])
			if chn == -1:
				if options.verbose:
					print 'unknown isch codeword at %d' % (i + (j*180))
				errors += 1
			elif chn == -2:
				if options.verbose:
					print 'sync isch codeword found at %d' % (i + (j*180))
				errors = 0
			else:
				if options.verbose:
					print "channel %d loc %d fr %d count %d" % (chn, loc, fr, cnt)
				errors = 0

			burst = syms1 [ (j*180) : (j*180) + 180 ]
			burst_d= syms2 [ (j*180) : (j*180) + 180 ]
			btype = my_duid.decode_duid(burst)
			if options.verbose:
				print 'burst at %d type %s' % (i + (j*180), btype)
			if btype == '2v' or btype == '4v':
				process_v(burst_d, btype)
			elif not btype.startswith('unknown'):
				maybe_sync = burst[79:79+21]
				if btype.endswith(' w'):	# scrambled
					burst = burst_d
				# process_oemi(burst, btype)
		if errors > 6:
			if options.verbose:
				print "too many successive errors, exiting at i=%d" % (i)
			break

if __name__ == "__main__":
	main()
