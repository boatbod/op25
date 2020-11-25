#!/usr/bin/env python

# 
# Copyright 2020 Graham J. Norbury
# 
# This file is part of OP25 and part of GNU Radio
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
# Tool for converting raw dibit files between OP25 format and SDRTrunk format
#

import sys

# Read first 64 bytes of source file and see if it contains anything other than dibits
def identify_file(src):
    mode = 0
    try:
        with open(src, 'rb') as srcfile:
            data = srcfile.read(64)
            for d in data:
                if (ord(d) >> 2) > 0:
                    mode = 1
                    break
    except IOError:
        sys.stderr.write("%s: Unable to open file: %s\n" % (sys.argv[0], src))
        sys.exit(1)

    return mode

def convert_file(mode, src, dst):
    try:
        with open(src, 'rb') as srcfile, open(dst, 'wb') as dstfile:
            idx = 0
            d_out = 0
            data = srcfile.read()
            for d in data:
                if mode == 0:   # OP25 single dibit format to SDRTrunk packed dibits
                    d_out = (d_out << 2) + (ord(d) & 3)
                    idx += 1
                    if idx < 4:
                        continue
                    dstfile.write(chr(d_out))
                    idx = 0
                    d_out = 0
                else:           # SDRTrunk packed dibit format to OP25 single dibit
                    d_in = ord(d)
                    dstfile.write(chr((d_in >> 6) & 3) + chr((d_in >> 4) & 3) + chr((d_in >> 2) & 3) + chr(d_in & 3))
            if (mode == 0) and (idx > 0):
                d_out <<= (2 * (4 - idx))
                dstfile.write(chr(d_out))

    except IOError, e:
        sys.stderr.write("%s: %s\n" % (sys.argv[0], e))
        sys.exit(1)
 

###################
# Main body

if len(sys.argv) != 3:
    sys.stderr.write("Invalid args.\n  %s <source> <destination>\n" % sys.argv[0])
    sys.exit(1)

srcfile = sys.argv[1]
dstfile = sys.argv[2]

mode = identify_file(srcfile)
sys.stdout.write("Mode %d\n" % mode)
convert_file(mode, srcfile, dstfile)

