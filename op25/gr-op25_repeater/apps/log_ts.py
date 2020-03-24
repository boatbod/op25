#!/usr/bin/env python

# Copyright 2020 Graham Norbury
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

# Modify TS_FORMAT to control logger timestamp format
# 0 = legacy epoch seconds
# 1 = formatted mm/dd/yy hh:mm:ss.usec
TS_FORMAT = 1

import time
class log_ts(object):
    @staticmethod
    def get(supplied_ts=None):
        if supplied_ts is None:
            ts = time.time()
        else:
            ts = supplied_ts

        if TS_FORMAT == 0:
            formatted_ts = "{:.6f}".format(ts)
        else:
            formatted_ts = "{:s}{:s}".format(time.strftime("%m/%d/%y %H:%M:%S",time.localtime(ts)),"{:.6f}".format(ts - int(ts)).lstrip("0"))

        return formatted_ts

