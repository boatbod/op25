
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

import numpy as np
from bit_utils import *

isch_map = {}

def mk_isch_lookup():
	g = np.array(np.mat('1 0 0 0 1 0 0 0 0 0 0 1 0 1 1 0 1 1 0 0 1 1 1 0 0 0 1 1 0 1 1 0 1 1 0 1 0 1 1 1; 0 0 1 0 0 0 0 0 0 0 0 1 1 1 0 1 1 1 1 1 1 1 0 1 0 1 0 0 1 1 1 1 0 1 1 0 0 1 0 0; 0 0 0 1 0 0 0 0 0 0 0 0 1 1 1 1 0 1 0 0 1 0 1 1 0 0 0 1 0 1 1 1 0 1 0 1 1 0 0 0; 0 0 0 0 1 1 0 0 0 0 0 0 0 0 0 0 1 1 0 1 1 1 1 0 1 1 0 1 0 0 0 1 1 0 0 0 1 1 1 0; 0 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 0 0 0 1 1 1 1 1 1 1 0 1 1 1 1 1 1 1 1 1 1 1; 0 0 0 0 1 0 0 1 0 0 0 0 0 1 0 0 1 0 0 0 1 1 0 1 1 0 0 1 1 0 1 1 0 1 1 1 0 0 1 0; 0 0 0 0 0 0 0 0 1 0 0 1 1 1 0 1 1 0 1 0 0 0 1 1 1 0 1 0 0 0 0 1 0 1 1 1 0 0 0 1; 0 0 0 0 0 0 0 0 0 1 0 1 1 0 0 0 1 1 0 0 1 0 1 1 1 0 1 0 1 0 1 0 0 1 0 0 1 1 1 0; 0 0 0 0 0 0 0 0 0 0 1 1 0 1 0 0 0 0 1 1 1 1 0 1 1 0 0 0 0 1 0 1 1 0 0 1 0 1 1 1'))
	c0 = 0x184229d461L
	for i in xrange(0, 2**7):
		codeword = mk_int(np.dot(mk_array(i, 9), g)) ^ c0
		isch_map['%x' % codeword] = i

def mk_isch(v):
	v1 = v & 3
	v = v >> 2
	v2 = v & 1
	v = v >> 1
	v3 = v & 3
	v = v >> 2
	v4 = v & 3
	v = v >> 2
	v5 = v & 3
	return v4, v3, v2, v1

def decode_isch(syms):
	sync0 = 0x575d57f7ff
	v = mk_int(dibits_to_bits(syms))
	vp = '%x' % v
	isch = 'unknown'
	if v == sync0:
		return -2, -2, -2, -2
	if vp in isch_map:
		chn,loc,fr,cnt = mk_isch(isch_map[vp])
		return chn, loc, fr, cnt
	# FIXME: if bit error(s), locate closest matching codeword
	return -1, -1, -1, -1
