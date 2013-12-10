
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

duid_str = {}
duid_str[0] = "4v"
duid_str[3] = "sacch w"
duid_str[6] = "2v"
duid_str[9] = "facch w"
duid_str[12] = "sacch w/o"
duid_str[15] = "facch w/o"

duid_map = {}
def mk_duid_lookup():
	g = np.array(np.mat('1 0 0 0 1 1 0 1; 0 1 0 0 1 0 1 1; 0 0 1 0 1 1 1 0; 0 0 0 1 0 1 1 1'))
	for i in xrange(16):
		codeword = mk_str(np.dot(mk_array(i, 4), g))
		duid_map[codeword] = i

def extract_duid(b):
	duid0 = b[10]	# duid 3,2
	duid1 = b[47]	# duid 1,0
	duid2 = b[132]	# par 3,2
	duid3 = b[169]	# par 1,0
	v = (duid0 << 6) + (duid1 << 4) + (duid2 << 2) + duid3
	va = mk_array(v, 8)
	return mk_str(va)

def decode_duid(burst):
	try:
		b = duid_str[duid_map[extract_duid(burst)]]
	except:	# FIXME: find closest matching codeword
		b = 'unknown' + extract_duid(burst)
	return b
