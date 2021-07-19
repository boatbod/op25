# Helper functions module
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
from log_ts import log_ts

#################
# Helper functions
def utf_ascii(ustr):
    if sys.version[0] == '2':
        return (ustr.decode("utf-8")).encode("ascii", "ignore")
    else:
        return ustr

def get_ordinals(s):
    t = 0
    if type(s) is int:                                  # integer
        return s
    elif type(s) is not str and isinstance(s, bytes):   # byte list
        for c in s:
            t = (t << 8) + c
    else:                                               # string list
        for c in s:
            t = (t << 8) + ord(c)
    return t

def get_frequency( f):    # return frequency in Hz
    if str(f).find('.') == -1:    # assume in Hz
        return int(f)
    else:     # assume in MHz due to '.'
        return int(float(f) * 1000000)

def get_int_dict(s, _id = 0):      # used to read blacklist/whitelist files
    d = {}
    try:
        with open(s,"r") as f:
            for v in f:
                v = v.split("\t",1)                        # split on tab
                try:
                    v0 = int(v[0])                         # first parameter is tgid or start of tgid range
                    v1 = v0
                    if (len(v) > 1) and (int(v[1]) > v0):  # second parameter if present is end of tgid range
                        v1 = int(v[1])

                    for tg in range(v0, (v1 + 1)):
                            if tg not in d:      # is this a new tg?
                                    d[tg] = []   # if so, add to dict (key only, value null)
                                    sys.stderr.write('%s [%s] added talkgroup %d from %s\n' % (log_ts.get(), _id, tg,s))

                except (IndexError, ValueError) as ex:
                    continue
        f.close()
    except (IOError) as ex:
        sys.stderr.write("%s: %s\n" % (ex.strerror, s))

    return dict.fromkeys(d)

def from_dict(d, key, def_val):
    if key in d and d[key] != "":
        return d[key]
    else:
        return def_val

def crc16(dat,len):    # slow version
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

def decomment(csvfile):
    for row in csvfile:
        raw = row.split('#')[0].strip()
        if raw: yield row

