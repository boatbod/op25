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
import json
import ast
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

def add_unique_freq(freq_list, freq):
    if freq_list is None or freq is None:
        return
    normalized_freq = get_frequency(freq)
    if normalized_freq not in freq_list:
        freq_list.append(normalized_freq)

def get_key_dict(keys_file, _id = 0):      # used to read crypt keys files
    #TODO: error handling for borked .json files
    keys_config = {}
    raw_config = json.loads(open(keys_file).read())
    for dict_key in raw_config.keys():     # iterate through dict and convert strings to integers
        keyid = int(ast.literal_eval(str(dict_key)))
        algid = int(ast.literal_eval(str(from_dict(raw_config[dict_key], "algid", "0"))))
        keys_config[keyid] = {}
        keys_config[keyid]['algid'] = algid
        keys_config[keyid]['key'] = []
        raw_kval = from_dict(raw_config[dict_key], "key", [])
        for kval in raw_kval:
            keys_config[keyid]['key'].append(int(ast.literal_eval(str(kval))))
    return keys_config

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

def read_tsv_file(tsv_filename, key):
    import csv
    hdrmap = []
    tsv_obj = {}
    with open(tsv_filename, 'r') as csvfile:
        sreader = csv.reader(decomment(csvfile), delimiter='\t', quotechar='"', quoting=csv.QUOTE_ALL)
        for row in sreader:
            if len(row) < 4:
                continue
            if ord(row[0][0]) == 0xfeff:
                row[0] = row[0][1:] # remove UTF8_BOM (Python2 version)
            if ord(row[0][0]) == 0xef and ord(row[0][1]) == 0xbb and ord(row[0][2]) == 0xbf:
                row[0] = row[0][3:] # remove UTF8_BOM (Python3 version)
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
            for i in range(len(row)):
                if row[i]:
                    fields[hdrmap[i]] = row[i]
                    if hdrmap[i] != 'sysname':
                        fields[hdrmap[i]] = fields[hdrmap[i]].lower()
            key_val = int(fields[key], 0)
            tsv_obj[key_val] = fields

    return tsv_obj

def get_fractional_ppm(tuned_freq, adj_val):
    return (adj_val * 1e6 / tuned_freq)
