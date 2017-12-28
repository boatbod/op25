#!/usr/bin/env python

# Copyright 2011, 2012, 2013, 2014, 2015, 2016, 2017 Max H. Parke KA1RBI
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

import os
import sys
import threading
import time
import json
import traceback
import osmosdr

from gnuradio import audio, eng_notation, gr, gru, filter, blocks, fft, analog, digital
from gnuradio.eng_option import eng_option
from math import pi
from optparse import OptionParser

import op25
import op25_repeater
import p25_demodulator
import p25_decoder

from gr_gnuplot import constellation_sink_c
from gr_gnuplot import fft_sink_c
from gr_gnuplot import symbol_sink_f
from gr_gnuplot import eye_sink_f

os.environ['IMBE'] = 'soft'

_def_symbol_rate = 4800

# The P25 receiver
#

class device(object):
    def __init__(self, config):
        speeds = [250000, 1000000, 1024000, 1800000, 1920000, 2000000, 2048000, 2400000, 2560000]

        self.name = config['name']

        sys.stderr.write('device: %s\n' % config)
        if config['args'].startswith('rtl') and config['rate'] not in speeds:
            sys.stderr.write('WARNING: requested sample rate %d for device %s may not\n' % (config['rate'], config['name']))
            sys.stderr.write("be optimal.  You may want to use one of the following rates\n")
            sys.stderr.write('%s\n' % speeds)
        self.src = osmosdr.source(config['args'])

        for tup in config['gains'].split(','):
            name, gain = tup.split(':')
            self.src.set_gain(int(gain), name)

        self.src.set_freq_corr(config['ppm'])
        self.ppm = config['ppm']

        self.src.set_sample_rate(config['rate'])
        self.sample_rate = config['rate']

        self.src.set_center_freq(config['frequency'])
        self.frequency = config['frequency']

        self.offset = config['offset']

class channel(object):
    def __init__(self, config, dev, verbosity):
        sys.stderr.write('channel (dev %s): %s\n' % (dev.name, config))
        self.device = dev
        self.name = config['name']
        self.symbol_rate = _def_symbol_rate
        if 'symbol_rate' in config.keys():
            self.symbol_rate = config['symbol_rate']
        self.config = config
        self.demod = p25_demodulator.p25_demod_cb(
                         input_rate = dev.sample_rate,
                         demod_type = config['demod_type'],
                         filter_type = config['filter_type'],
                         excess_bw = config['excess_bw'],
                         relative_freq = dev.frequency + dev.offset - config['frequency'],
                         offset = dev.offset,
                         if_rate = config['if_rate'],
                         symbol_rate = self.symbol_rate)
        q = gr.msg_queue(1)
        self.decoder = op25_repeater.frame_assembler(config['destination'], verbosity, q)

        self.kill_sink = []

        if 'plot' not in config.keys():
            return

        self.sinks = []
        for plot in config['plot'].split(','):
            # fixme: allow multiple complex consumers (fft and constellation currently mutually exclusive)
            if plot == 'datascope':
                assert config['demod_type'] == 'fsk4'   ## datascope plot requires fsk4 demod type
                sink = eye_sink_f(sps=config['if_rate'] / self.symbol_rate)
                self.demod.connect_bb('symbol_filter', sink)
                self.kill_sink.append(sink)
            elif plot == 'symbol':
                sink = symbol_sink_f()
                self.demod.connect_float(sink)
                self.kill_sink.append(sink)
            elif plot == 'fft':
                i = len(self.sinks)
                self.sinks.append(fft_sink_c())
                self.demod.connect_complex('src', self.sinks[i])
                self.kill_sink.append(self.sinks[i])
            elif plot == 'constellation':
                i = len(self.sinks)
                assert config['demod_type'] == 'cqpsk'   ## constellation plot requires cqpsk demod type
                self.sinks.append(constellation_sink_c())
                self.demod.connect_complex('diffdec', self.sinks[i])
                self.kill_sink.append(self.sinks[i])
            else:
                sys.stderr.write('unrecognized plot type %s\n' % plot)
                return

class rx_block (gr.top_block):

    # Initialize the receiver
    #
    def __init__(self, verbosity, config):
        self.verbosity = verbosity
        gr.top_block.__init__(self)
        self.device_id_by_name = {}
        self.configure_devices(config['devices'])
        self.configure_channels(config['channels'])

    def configure_devices(self, config):
        self.devices = []
        for cfg in config:
            self.device_id_by_name[cfg['name']] = len(self.devices)
            self.devices.append(device(cfg))

    def find_device(self, chan):
        for dev in self.devices:
            d = abs(chan['frequency'] - dev.frequency)
            nf = dev.sample_rate / 2
            if d + 6250 <= nf:
                return dev
        return None

    def configure_channels(self, config):
        self.channels = []
        for cfg in config:
            dev = self.find_device(cfg)
            if dev is None:
                sys.stderr.write('* * * Frequency %d not within spectrum band of any device - ignoring!\n' % cfg['frequency'])
                continue
            chan = channel(cfg, dev, self.verbosity)
            self.channels.append(chan)
            self.connect(dev.src, chan.demod, chan.decoder)

    def scan_channels(self):
        for chan in self.channels:
            sys.stderr.write('scan %s: error %d\n' % (chan.config['frequency'], chan.demod.get_freq_error()))

class rx_main(object):
    def __init__(self):
        def byteify(input):	# thx so
            if isinstance(input, dict):
                return {byteify(key): byteify(value)
                        for key, value in input.iteritems()}
            elif isinstance(input, list):
                return [byteify(element) for element in input]
            elif isinstance(input, unicode):
                return input.encode('utf-8')
            else:
                return input

        self.keep_running = True

        # command line argument parsing
        parser = OptionParser(option_class=eng_option)
        parser.add_option("-c", "--config-file", type="string", default=None, help="specify config file name")
        parser.add_option("-v", "--verbosity", type="int", default=0, help="message debug level")
        parser.add_option("-p", "--pause", action="store_true", default=False, help="block on startup")
        (options, args) = parser.parse_args()

        # wait for gdb
        if options.pause:
            print 'Ready for GDB to attach (pid = %d)' % (os.getpid(),)
            raw_input("Press 'Enter' to continue...")

        if options.config_file == '-':
            config = json.loads(sys.stdin.read())
        else:
            config = json.loads(open(options.config_file).read())
        self.tb = rx_block(options.verbosity, config = byteify(config))

    def run(self):
        try:
            self.tb.start()
            while self.keep_running:
                time.sleep(1)
        except:
            sys.stderr.write('main: exception occurred\n')
            sys.stderr.write('main: exception:\n%s\n' % traceback.format_exc())

if __name__ == "__main__":
    rx = rx_main()
    rx.run()
