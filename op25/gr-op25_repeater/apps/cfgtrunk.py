#!/bin/sh
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
# Crude tool for editing trunk.tsv files
#
"true" '''\'
DEFAULT_PYTHON2=/usr/bin/python
DEFAULT_PYTHON3=/usr/bin/python3
if [ -f op25_python ]; then
    OP25_PYTHON=$(cat op25_python)
else
    OP25_PYTHON="/usr/bin/python"
fi

if [ -x $OP25_PYTHON ]; then
    echo Using Python $OP25_PYTHON >&2
    exec $OP25_PYTHON "$0" "$@"
elif [ -x $DEFAULT_PYTHON2 ]; then
    echo Using Python $DEFAULT_PYTHON2 >&2
    exec $DEFAULT_PYTHON2 "$0" "$@"
elif [ -x $DEFAULT_PYTHON3 ]; then
    echo Using Python $DEFAULT_PYTHON3 >&2
    exec $DEFAULT_PYTHON3 "$0" "$@"
else
    echo Unable to find Python >&2
fi
exit 127
'''

import sys
import csv

def read_configs(tsv_filename):
    hdrmap  = []
    configs = {}
    idx = 0
    try:
        with open(tsv_filename, 'r') as csvfile:
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
                for i in range(len(row)):
                    if row[i]:
                        fields[hdrmap[i]] = row[i]
                        if hdrmap[i] != 'sysname':
                            fields[hdrmap[i]] = fields[hdrmap[i]].lower()
                configs[idx] = fields
                idx += 1
    except IOError:
        sys.stderr.write("%s: Unable to open file: %s\n" % (sys.argv[0], tsv_filename))
        sys.exit(1)

    return hdrmap, configs

def write_configs(tsv_filename, hdrmap, configs):
    with open(tsv_filename, 'w') as csvfile:
        swriter = csv.writer(csvfile, delimiter='\t', quotechar='"', quoting=csv.QUOTE_ALL)
        swriter.writerow(hdrmap) # Header
        for idx in configs:      # Data
            row = []
            for field in hdrmap:
                if field in configs[idx]:
                    row.append(configs[idx][field])
                else:
                    row.append("")
            swriter.writerow(row)

def print_config(hdrmap, configs, idx):
    for field in hdrmap:
        if field in configs[idx]:
            data = configs[idx][field]
        else:
            data = "<not set>"
        sys.stdout.write("[%d.%d] %-20s = %s\n" % (idx,hdrmap.index(field), field, data))

def edit_config(hdrmap, configs, p_pos, p_value):
    p_list = p_pos.split(".")
    if len(p_list) != 2:
        return 1

    idx = int(p_list[0])
    param = int(p_list[1])
    if (idx not in configs) or (param < 0) or (param > len(hdrmap)):
        return 2

    if (p_value is not None) and (p_value != ""):
        configs[idx][hdrmap[param]] = p_value
    else:
        del configs[idx][hdrmap[param]]

    return 0

###################
# Main body

if (len(sys.argv) != 2) and (len(sys.argv) != 4):
    sys.stderr.write("Invalid args.\n  %s <trunk.tsv> (<position> <value>)\n" % sys.argv[0])
    sys.exit(1)

# Read existing trunk.tsv file
cfg_hdr, cfg_data = read_configs(sys.argv[1])

# Modify specified parameter
if len(sys.argv) == 4:
    ret = edit_config(cfg_hdr, cfg_data, sys.argv[2], sys.argv[3])

# Print on screen
for idx in cfg_data:
    print_config(cfg_hdr, cfg_data, idx)
    sys.stdout.write("\n")

if len(sys.argv) == 4:
    if ret == 0:
        write_configs(sys.argv[1], cfg_hdr, cfg_data)
    elif ret == 1:
        sys.stderr.write("Invalid <position> format: [%s]\n" % sys.argv[2])
    elif ret == 2: 
        sys.stderr.write("Invalid <position> parameter: [%s]\n" % sys.argv[2])

