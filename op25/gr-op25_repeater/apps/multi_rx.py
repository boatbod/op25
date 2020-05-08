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
import importlib

from gnuradio import audio, eng_notation, gr, gru, filter, blocks, fft, analog, digital
from gnuradio.eng_option import eng_option
from math import pi
from optparse import OptionParser

import op25
import op25_repeater
import p25_demodulator
import p25_decoder
from log_ts import log_ts

from gr_gnuplot import constellation_sink_c
from gr_gnuplot import fft_sink_c
from gr_gnuplot import symbol_sink_f
from gr_gnuplot import eye_sink_f
from gr_gnuplot import mixer_sink_c

sys.path.append('tdma')
import lfsr

os.environ['IMBE'] = 'soft'

_def_symbol_rate = 4800

# The P25 receiver
#

class device(object):
    def __init__(self, config):
        speeds = [250000, 1000000, 1024000, 1800000, 1920000, 2000000, 2048000, 2400000, 2560000]

        self.name = config['name']
        self.tunable = config['tunable']

        sys.stderr.write('device: %s\n' % config)
        if config['args'].startswith('rtl') and config['rate'] not in speeds:
            sys.stderr.write('WARNING: requested sample rate %d for device %s may not\n' % (config['rate'], config['name']))
            sys.stderr.write("be optimal.  You may want to use one of the following rates\n")
            sys.stderr.write('%s\n' % speeds)
        self.src = osmosdr.source(str(config['args']))

        for tup in config['gains'].split(','):
            name, gain = tup.split(':')
            self.src.set_gain(int(gain), str(name))

        self.src.set_freq_corr(config['ppm'])
        self.ppm = config['ppm']

        self.src.set_sample_rate(config['rate'])
        self.sample_rate = config['rate']

        self.src.set_center_freq(config['frequency'])
        self.frequency = config['frequency']

        self.offset = config['offset']

class channel(object):
    def __init__(self, config, dev, verbosity, msgq_id, rx_q):
        sys.stderr.write('channel (dev %s): %s\n' % (dev.name, config))
        self.verbosity = verbosity
        self.name = config['name']
        self.device = dev
        if 'frequency' in config and (config['frequency'] != ""):
            self.frequency = config['frequency']
        else:
            self.frequency = self.device.frequency
        self.msgq_id = msgq_id
        self.raw_sink = None
        self.raw_file = None
        self.throttle = None
        self.scope_sink = None
        self.sinks = []
        self.kill_sink = []
        self.tdma_state = False
        self.xor_cache = {}
        self.symbol_rate = _def_symbol_rate
        if 'symbol_rate' in list(config.keys()):
            self.symbol_rate = config['symbol_rate']
        self.config = config
        if config['demod_type'] == "fsk": # Motorola 3600bps
            self.demod = p25_demodulator.p25_demod_cb(
                             input_rate = dev.sample_rate,
                             demod_type = 'fsk4',
                             filter_type = 'fsk',
                             excess_bw = config['excess_bw'],
                             relative_freq = dev.frequency + dev.offset - self.frequency,
                             offset = dev.offset,
                             if_rate = config['if_rate'],
                             symbol_rate = self.symbol_rate)
            self.decoder = op25_repeater.frame_assembler(str(config['destination']), verbosity, msgq_id, rx_q)

        else:                             # P25, DMR, NXDN and everything else
            self.demod = p25_demodulator.p25_demod_cb(
                             input_rate = dev.sample_rate,
                             demod_type = config['demod_type'],
                             filter_type = config['filter_type'],
                             excess_bw = config['excess_bw'],
                             relative_freq = dev.frequency + dev.offset - self.frequency,
                             offset = dev.offset,
                             if_rate = config['if_rate'],
                             symbol_rate = self.symbol_rate)
            self.decoder = op25_repeater.frame_assembler(str(config['destination']), verbosity, msgq_id, rx_q)

        if 'key' in config and (config['key'] != ""):
            self.set_key(int(config['key'], 0))

        if ('plot' not in list(config.keys())) or (config['plot'] == ""):
            return

        for plot in config['plot'].split(','):
            # fixme: allow multiple complex consumers (fft and constellation currently mutually exclusive)
            if plot == 'datascope':
                assert (config['demod_type'] == 'fsk4' or
                        config['demod_type'] == 'fsk')   ## datascope plot requires fsk or fsk4 demod type
                sink = eye_sink_f(plot_name=self.name, sps=config['if_rate'] / self.symbol_rate)
                self.demod.connect_bb('symbol_filter', sink)
                self.kill_sink.append(sink)
                self.scope_sink = sink
            elif plot == 'symbol':
                sink = symbol_sink_f(plot_name=self.name)
                self.demod.connect_float(sink)
                self.kill_sink.append(sink)
            elif plot == 'fft':
                i = len(self.sinks)
                self.sinks.append(fft_sink_c(plot_name=self.name))
                self.demod.connect_complex('src', self.sinks[i])
                self.kill_sink.append(self.sinks[i])
                self.sinks[i].set_offset(self.device.offset)
                self.sinks[i].set_center_freq(self.device.frequency)
                self.sinks[i].set_relative_freq(self.device.frequency + self.device.offset - self.frequency)
                self.sinks[i].set_width(self.device.sample_rate)
            elif plot == 'constellation':
                i = len(self.sinks)
                assert config['demod_type'] == 'cqpsk'   ## constellation plot requires cqpsk demod type
                self.sinks.append(constellation_sink_c(plot_name=self.name))
                self.demod.connect_complex('diffdec', self.sinks[i])
                self.kill_sink.append(self.sinks[i])
            elif plot == 'mixer':
                i = len(self.sinks)
                self.sinks.append(mixer_sink_c(plot_name=self.name))
                self.demod.connect_complex('mixer', self.sinks[i])
                self.kill_sink.append(self.sinks[i])
            else:
                sys.stderr.write('unrecognized plot type %s\n' % plot)
                return

    def set_freq(self, freq):
        if self.frequency == freq:
            return True
        old_freq = self.frequency
        self.frequency = freq
        if not self.demod.set_relative_frequency(self.device.frequency + self.device.offset - freq): # First attempt relative tune
            if self.device.tunable:                                                                  # then hard tune if allowed
                self.device.src.set_center_freq(self.frequency)
                self.device.frequency = self.frequency
                self.demod.set_relative_frequency(self.device.frequency + self.device.offset - freq)
            else:                                                                                    # otherwise fail and reset to prev freq
                self.demod.set_relative_frequency(self.device.frequency + self.device.offset - old_freq)
                self.frequency = old_freq
                if self.verbosity:
                    sys.stderr.write("%s [%d] Unable to tune %s to frequency %f\n" % (log_ts.get(), self.msgq_id, self.name, (freq/1e6)))
                return False
        for sink in self.sinks:
            if sink.name() == "fft_sink_c":
                sink.set_center_freq(self.device.frequency)
                sink.set_relative_freq(self.device.frequency + self.device.offset - freq)
        if self.verbosity >= 9:
            sys.stderr.write("%s [%d] Tuning to frequency %f\n" % (log_ts.get(), self.msgq_id, (freq/1e6)))
        self.decoder.sync_reset()
        return True

    def configure_p25_tdma(self, params):
        set_tdma = False
        if params['tdma'] is not None:
            set_tdma = True
            self.decoder.set_slotid(params['tdma'])
        if set_tdma == self.tdma_state:
            return
        self.tdma_state = set_tdma
        if set_tdma:
            hash = '%x%x%x' % (params['nac'], params['sysid'], params['wacn'])
            if hash not in self.xor_cache:
                self.xor_cache[hash] = lfsr.p25p2_lfsr(params['nac'], params['sysid'], params['wacn']).xor_chars
            self.decoder.set_xormask(self.xor_cache[hash])
            rate = 6000
        else:
            rate = self.config['symbol_rate']

        self.symbol_rate = rate
        self.demod.set_omega(rate)
        if self.scope_sink is not None:
            self.scope_sink.set_sps(self.config['if_rate'] / rate)

    def set_slot(self, slot):
        self.decoder.set_slotid(slot)

    def set_key(self, key):
        self.decoder.set_slotkey(key)

    def kill(self):
        for sink in self.kill_sink:
            sink.kill()

class rx_block (gr.top_block):

    # Initialize the receiver
    #
    def __init__(self, verbosity, config):
        self.verbosity = verbosity
        gr.top_block.__init__(self)
        self.device_id_by_name = {}

        self.trunking = None
        self.du_watcher = None
        self.rx_q = gr.msg_queue(100)
        if "trunking" in config:
            self.configure_trunking(config['trunking'])

        self.configure_devices(config['devices'])
        self.configure_channels(config['channels'])

        if self.trunking is not None: # post-initialization after channels and devices created
            self.trunk_rx.post_init()

    def configure_trunking(self, config):
        if (("module" in config and (config['module'] == "")) or 
            ("chans" in config and (config['chans'] == ""))):
            return

        tk_mod = config['module']
        if tk_mod.endswith('.py'):
            tk_mod = tk_mod[:-3]
        try:
            self.trunking = importlib.import_module(tk_mod)
        except:
            sys.stderr.write("Error: unable to import trunking module: %s\n%s\n" % (config['module'], sys.exc_info()[1]))
            self.trunking = None

        if self.trunking is not None:
            self.trunk_rx = self.trunking.rx_ctl(frequency_set = self.change_freq, slot_set = self.set_slot, debug = self.verbosity, chans = config['chans'])
            self.du_watcher = du_queue_watcher(self.rx_q, self.trunk_rx.process_qmsg)
            sys.stderr.write("Enabled trunking module: %s\n" % config['module'])

    def configure_devices(self, config):
        self.devices = []
        for cfg in config:
            self.device_id_by_name[cfg['name']] = len(self.devices)
            self.devices.append(device(cfg))

    def find_device(self, chan):
        if 'device' in chan and (chan['device'] != "") and (chan['device'] in self.device_id_by_name):
            dev_id = self.device_id_by_name[chan['device']]
            sys.stderr.write("DEVICE ID=%d\n" % dev_id)
            if dev_id < len(self.devices):
                return self.devices[dev_id]
            
        if 'frequency' in chan and (chan['frequency'] != ""):
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
            if (dev is None) and 'frequency' in cfg:
                sys.stderr.write("* * * Frequency %d not within spectrum band of any device - ignoring!\n" % cfg['frequency'])
                continue
            elif dev is None:
                sys.stderr.write("* * * Channel '%s' not attached to any device - ignoring!\n" % cfg['name'])
                continue
            elif dev.tunable:
                for ch in self.channels:
                    if ch.device == dev:
                        sys.stderr.write("* * * Channel '%s' cannot share a tunable device - ignoring!\n" % cfg['name'])
                        dev = None
                        break
                if dev == None:
                    continue    
            if self.trunking is not None:
                msgq_id = len(self.channels)
                self.trunk_rx.add_receiver(msgq_id)
            else:
                msgq_id = -1 - len(self.channels)
            chan = channel(cfg, dev, self.verbosity, msgq_id, self.rx_q)
            self.channels.append(chan)
            if ("raw_input" in cfg) and (cfg['raw_input'] != ""):
                sys.stderr.write("%s Reading raw symbols from file: %s\n" % (log_ts.get(), cfg['raw_input']))
                chan.raw_file = blocks.file_source(gr.sizeof_char, str(cfg['raw_input']), False)
                if ("raw_seek" in cfg) and (cfg['raw_seek'] != 0):
                    chan.raw_file.seek(int(cfg['raw_seek']) * 4800, 0)
                chan.throttle = blocks.throttle(gr.sizeof_char, chan.symbol_rate)
                chan.throttle.set_max_noutput_items(chan.symbol_rate/50);
                self.connect(chan.raw_file, chan.throttle)
                self.connect(chan.throttle, chan.decoder)
            else:
                self.connect(dev.src, chan.demod, chan.decoder)
                if ("raw_output" in cfg) and (cfg['raw_output'] != ""):
                    sys.stderr.write("%s Saving raw symbols to file: %s\n" % (log_ts.get(), cfg['raw_output']))
                    chan.raw_sink = blocks.file_sink(gr.sizeof_char, str(cfg['raw_output']))
                    self.connect(chan.demod, chan.raw_sink)

    def scan_channels(self):
        for chan in self.channels:
            sys.stderr.write('scan %s: error %d\n' % (chan.config['frequency'], chan.demod.get_freq_error()))

    def change_freq(self, params):
        tuner = params['tuner']
        if (tuner < 0) or (tuner > len(self.channels)):
            if self.verbosity:
                sys.stderr.write("%s No %s channel available for tuning\n" % (log_ts.get(), params['tuner']))
            return False

        chan = self.channels[tuner]
        if 'sigtype' in params and params['sigtype'] == "P25": # P25 specific TDMA config
            chan.configure_p25_tdma(params)

        if not chan.set_freq(params['freq']):
            chan.set_slot(0)
            return False

        if 'slot' in params:
            chan.set_slot(params['slot'])

        if 'chan' in params:
            self.trunk_rx.receivers[tuner].current_chan = params['chan']

        if 'state' in params:
            self.trunk_rx.receivers[tuner].current_state = params['state']

        if 'type' in params:
            self.trunk_rx.receivers[tuner].current_type = params['type']

        if 'time' in params:
            self.trunk_rx.receivers[tuner].tune_time = params['time']

        return True

    def set_slot(self, params):
        tuner = params['tuner']
        chan = self.channels[tuner]
        if 'slot' in params:
            chan.set_slot(params['slot'])

    def kill(self):
        for chan in self.channels:
            chan.kill()

# data unit receive queue
#
class du_queue_watcher(threading.Thread):

    def __init__(self, msgq,  callback, **kwds):
        threading.Thread.__init__ (self, **kwds)
        self.setDaemon(1)
        self.msgq = msgq
        self.callback = callback
        self.keep_running = True
        self.start()

    def run(self):
        while(self.keep_running):
            msg = self.msgq.delete_head()
            self.callback(msg)

    def kill(self):
        self.keep_running = False

class rx_main(object):
    def __init__(self):
        def byteify(input):    # thx so
            if isinstance(input, dict):
                return {byteify(key): byteify(value)
                        for key, value in list(input.items())}
            elif isinstance(input, list):
                return [byteify(element) for element in input]
            elif isinstance(input, str):
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
            sys.stdout.write("Ready for GDB to attach (pid = %d)\n" % (os.getpid(),))
            input("Press 'Enter' to continue...")

        if options.config_file == '-':
            config = json.loads(sys.stdin.read())
        else:
            config = json.loads(open(options.config_file).read())
        self.tb = rx_block(options.verbosity, config = byteify(config))

    def run(self):
        try:
            self.tb.start()
            self.tb.wait()
            sys.stderr.write('Flowgraph complete. Exiting\n')
        except (KeyboardInterrupt):
            self.tb.stop()
            self.tb.kill()
        except:
            self.tb.stop()
            self.tb.kill()
            sys.stderr.write('main: exception occurred\n')
            sys.stderr.write('main: exception:\n%s\n' % traceback.format_exc())

if __name__ == "__main__":
    rx = rx_main()
    rx.run()
