#!/usr/bin/env python

# Copyright 2017, 2018 Graham Norbury
# 
# Copyright 2011, 2012, 2013, 2014, 2015, 2016, 2017 Max H. Parke KA1RBI
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

import signal
import sys
import time

from optparse import OptionParser
from sockaudio import socket_audio

def signal_handler(signal, frame):
   sys.stderr.write("audio.py shutting down\n")
   audio_handler.stop()
   sys.exit(0)

parser = OptionParser()
parser.add_option("-O", "--audio-output", type="string", default="default", help="audio output device name")
parser.add_option("-u", "--wireshark-port", type="int", default=23456, help="Wireshark port")
parser.add_option("-2", "--two-channel", action="store_true", default=False, help="single or two channel audio")
parser.add_option("-x", "--audio-gain", type="float", default="1.0", help="audio gain (default = 1.0)")
parser.add_option("-s", "--stdout", action="store_true", default=False, help="write to stdout instead of audio device")
 
(options, args) = parser.parse_args()
if len(args) != 0:
   parser.print_help()
   sys.exit(1)

audio_handler = socket_audio("0.0.0.0", options.wireshark_port, options.audio_output, options.two_channel, options.audio_gain, options.stdout)

if __name__ == "__main__":
   signal.signal(signal.SIGINT, signal_handler)
   audio_handler.run()

