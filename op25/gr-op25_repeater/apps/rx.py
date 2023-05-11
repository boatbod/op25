#!/bin/sh
# Copyright 2008-2011 Steve Glass
# 
# Copyright 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020 Max H. Parke KA1RBI
# 
# Copyright 2018-2023 Graham J. Norbury
# 
# Copyright 2003,2004,2005,2006 Free Software Foundation, Inc.
#         (from radiorausch)
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
import io
import os
import pickle
import sys
import threading
import math
import numpy
import time
import re
import json
import traceback
try:
    import Hamlib
except:
    pass

try:
    import Numeric
except:
    pass

from gnuradio import audio, eng_notation, gr, gru, filter, blocks, fft, analog, digital
from gnuradio.eng_option import eng_option
from math import pi
from optparse import OptionParser

import op25
import op25_repeater

import trunking

import p25_demodulator
import p25_decoder

sys.path.append('tdma')
import lfsr

from gr_gnuplot import constellation_sink_c
from gr_gnuplot import fft_sink_c
from gr_gnuplot import symbol_sink_f
from gr_gnuplot import eye_sink_f
from gr_gnuplot import mixer_sink_c
from gr_gnuplot import fll_sink_c

from terminal import op25_terminal
from sockaudio  import audio_thread
from log_ts import log_ts
from helper_funcs import *

#speeds = [300, 600, 900, 1200, 1440, 1800, 1920, 2400, 2880, 3200, 3600, 3840, 4000, 4800, 6000, 6400, 7200, 8000, 9600, 14400, 19200]
speeds = [4800, 6000]

os.environ['IMBE'] = 'soft'

WIRESHARK_PORT = 23456

_def_interval = 1.0    # sec
_def_file_dir = '../www/images'

# The P25 receiver
#
class p25_rx_block (gr.top_block):

    # Initialize the P25 receiver
    #
    def __init__(self, options):

        self.trunk_rx = None
        self.plot_sinks = []

        gr.top_block.__init__(self)

        self.channel_rate = 0
        self.baseband_input = False
        self.rtl_found = False
        self.channel_rate = options.sample_rate
        self.fft_sink = None
        self.constellation_sink = None
        self.symbol_sink = None
        self.eye_sink = None
        self.mixer_sink = None
        self.fll_sink = None
        self.target_freq = 0.0
        self.last_error_update = 0
        self.tuning_error = 0
        self.freq_correction = 0
        self.last_set_freq = 0
        self.last_set_freq_at = time.time()
        self.last_set_ppm = 0
        self.last_change_freq = 0
        self.last_change_freq_at = time.time()
        self.last_freq_params = {'freq' : 0.0, 'tgid' : None, 'tag' : "", 'tdma' : None}
        self.meta_server = None
        self.stream_url = ""
        self.ui_last_update = 0
        self.ui_timeout = 5.0

        self.src = None
        if (not options.ifile) and (not options.input) and (not options.audio) and (not options.audio_if) and (not options.symbols):
            # check if osmocom is accessible
            try:
                import osmosdr
                self.src = osmosdr.source(options.args)
            except Exception:
                sys.stdout.write("osmosdr source_c creation failure\n")
                ignore = True
 
            if any(x in options.args.lower() for x in ['rtl', 'airspy', 'hackrf', 'uhd']):
                self.rtl_found = True

            if options.gain_mode is not None:
                if options.gain_mode:
                    self.src.set_gain_mode(True, 0)
                else:
                    self.src.set_gain_mode(True, 0)  # UGH! Ugly workaround for gr-osmosdr airspy bug
                    self.src.set_gain_mode(False, 0)
                sys.stderr.write("gr-osmosdr driver gain_mode: %s\n" % self.src.get_gain_mode())

            gain_names = self.src.get_gain_names()
            for name in gain_names:
                g_range = self.src.get_gain_range(name)
                sys.stderr.write("gain: name: %s range: start %d stop %d step %d\n" % (name, g_range[0].start(), g_range[0].stop(), g_range[0].step()))
            if options.gains:
                for tup in options.gains.split(","):
                    name, gain = tup.split(":")
                    gain = int(gain)
                    sys.stderr.write("setting gain %s to %d\n" % (name, gain))
                    self.src.set_gain(gain, name)

            rates = self.src.get_sample_rates()
            try:
                sys.stderr.write("supported sample rates %d-%d step %d\n" % (rates.start(), rates.stop(), rates.step()))
            except:
                pass    # ignore

            if options.freq_corr:
                self.src.set_freq_corr(options.freq_corr)
                self.last_set_ppm = options.freq_corr

        if options.audio:
            self.channel_rate = 48000
            self.baseband_input = True

        if options.audio_if:
            self.channel_rate = 96000

        # setup (read-only) attributes
        if options.tdma_cc:
            self.symbol_rate = 6000
        else:
            self.symbol_rate = 4800
        self.symbol_deviation = 600.0
        self.basic_rate = 24000
        _default_speed = self.symbol_rate
        self.options = options
        #
        self.set_sps(_default_speed)

        # keep track of flow graph connections
        self.cnxns = []

        self.datascope_raw_input = False
        self.data_scope_connected = False

        self.constellation_scope_connected = False

        for i in range(len(speeds)):
            if speeds[i] == _default_speed:
                self.current_speed = i
                self.default_speed_idx = i

        if options.hamlib_model:
            self.hamlib_attach(options.hamlib_model)

        # wait for gdb
        if options.pause:
            sys.stdout.write("Ready for GDB to attach (pid = %d)\n" % (os.getpid(),))
            if sys.version[0] > '2':
                input("Press 'Enter' to continue...")
            else:
                raw_input("Press 'Enter' to continue...")

        self.input_q = gr.msg_queue(10)
        self.output_q = gr.msg_queue(10)
        self.meta_q = gr.msg_queue(10)
 
        # configure specified data source
        if options.input:
            self.open_file(options.input)
        elif (self.rtl_found or options.frequency):
            self.open_usrp()
        elif options.audio_if:
            self.open_audio_c(self.channel_rate, options.gain, options.audio_input)
        elif options.audio:
            self.open_audio(self.channel_rate, options.gain, options.audio_input)
        elif options.ifile:
            self.open_ifile2(self.channel_rate, options.ifile)
        elif options.symbols:
            self.open_symbols(self.symbol_rate, options.symbols, options.seek)
        else:
            pass

        # attach terminal thread and make sure currently tuned frequency is displayed
        self.terminal = op25_terminal(self.input_q, self.output_q, self.options.terminal_type)
        if self.terminal is None:
            sys.exit(1)

        # attach meta server thread
        if self.options.metacfg is not None:
            from icemeta import meta_server
            self.meta_server = meta_server(self.meta_q, self.options.metacfg, debug=self.options.verbosity)
            try:
                with open(self.options.metacfg) as json_file:
                    meta_cfg = json.load(json_file)
                self.stream_url = "http://" + meta_cfg['icecastServerAddress'] + "/" + meta_cfg['icecastMountpoint'] + meta_cfg['icecastMountExt']
                sys.stderr.write("streaming server url=\"%s\"\n" % self.stream_url)
            except (ValueError, KeyError):
                sys.stderr.write("error reading metadata config file: %s, streaming server url disabled\n" % self.options.metacfg)
        else:
            self.meta_server = None
            sys.stderr.write("metadata update not enabled\n")

        # attach audio thread
        if self.options.udp_player:
            self.audio = audio_thread("127.0.0.1", self.options.wireshark_port, self.options.audio_output, False, self.options.audio_gain)
        else:
            self.audio = None

    # setup common flow graph elements
    #
    def __build_graph(self, source, capture_rate):
        global speeds
        global WIRESHARK_PORT

        self.rx_q = gr.msg_queue(100)
        udp_port = 0

        if self.options.udp_player:
            self.options.vocoder = True
            self.options.wireshark = True
            self.options.wireshark_host = "127.0.0.1"

        if self.options.wireshark or (self.options.wireshark_host != "127.0.0.1"):
            udp_port = self.options.wireshark_port

        self.tdma_state = False
        self.xor_cache = {}

        self.fft_state  = False
        self.c4fm_state = False
        self.fscope_state = False
        self.corr_state = False
        self.fac_state = False
        self.fsk4_demod_connected = False
        self.psk_demod_connected = False
        self.fsk4_demod_mode = False
        self.corr_i_chan = False

        if self.baseband_input:
            self.demod = p25_demodulator.p25_demod_fb(msgq_id=0, debug=self.options.verbosity, input_rate=capture_rate, excess_bw=self.options.excess_bw)
        elif self.options.symbols:
            self.demod = None
        else:    # complex input
            # local osc
            self.lo_freq = self.options.offset
            if self.options.audio_if or self.options.ifile or self.options.input:
                self.lo_freq += self.options.calibration
            self.demod = p25_demodulator.p25_demod_cb( msgq_id = 0,
                                                       debug = self.options.verbosity,
                                                       input_rate = capture_rate,
                                                       demod_type = self.options.demod_type,
                                                       relative_freq = self.lo_freq,
                                                       offset = self.options.offset,
                                                       if_rate = self.sps * 4800,
                                                       gain_mu = self.options.gain_mu,
                                                       costas_alpha = self.options.costas_alpha,
                                                       excess_bw = self.options.excess_bw,
                                                       symbol_rate = self.symbol_rate)

        num_ambe = 0
        if self.options.phase2_tdma:
            num_ambe = 1

        if self.options.crypt_behavior > 0:
            self.options.nocrypt = True

        self.decoder = p25_decoder.p25_decoder_sink_b(dest='audio', do_imbe=self.options.vocoder, num_ambe=num_ambe, wireshark_host=self.options.wireshark_host, udp_port=udp_port, do_msgq = True, msgq=self.rx_q, audio_output=self.options.audio_output, debug=self.options.verbosity, nocrypt=self.options.nocrypt)

        # connect it all up
        if self.options.symbols:
            self.connect(source, self.decoder)
        else:
            self.connect(source, self.demod, self.decoder)

            if self.options.plot_mode == 'constellation':
                self.toggle_constellation()
            elif self.options.plot_mode == 'symbol':
                self.toggle_symbol()
            elif self.options.plot_mode == 'fft':
                self.toggle_fft()
            elif self.options.plot_mode == 'datascope':
                self.toggle_eye()
            elif self.options.plot_mode == 'mixer':
                self.toggle_mixer()
            elif self.options.plot_mode == 'fll':
                self.toggle_fll()

            if self.options.raw_symbols:
                sys.stderr.write("Saving raw symbols to file: %s\n" % self.options.raw_symbols)
                self.sink_sf = blocks.file_sink(gr.sizeof_char, self.options.raw_symbols)
                self.connect(self.demod, self.sink_sf)

        logfile_workers = []
        if self.options.phase2_tdma:
            num_ambe = 2
        if self.options.logfile_workers:
            for i in range(self.options.logfile_workers):
                demod = p25_demodulator.p25_demod_cb(msgq_id=0,
                                                     debug=self.options.verbosity,
                                                     input_rate=capture_rate,
                                                     demod_type=self.options.demod_type,
                                                     offset=self.options.offset)
                decoder = p25_decoder.p25_decoder_sink_b(debug = self.options.verbosity, do_imbe = self.options.vocoder, num_ambe=num_ambe)
                logfile_workers.append({'demod': demod, 'decoder': decoder, 'active': False})
                self.connect(source, demod, decoder)

        self.trunk_rx = trunking.rx_ctl(frequency_set = self.change_freq, fa_ctrl = self.control, debug = self.options.verbosity, conf_file = self.options.trunk_conf_file, logfile_workers=logfile_workers, meta_update = self.meta_update, crypt_behavior = self.options.crypt_behavior)

        self.du_watcher = du_queue_watcher(self.rx_q, self.trunk_rx.process_qmsg)

        # Dowload encryption keys if provided
        if self.options.crypt_keys is not None:
            sys.stderr.write("%s reading crypt_keys file: %s\n" % (log_ts.get(), self.options.crypt_keys))
            crypt_keys = get_key_dict(self.options.crypt_keys, 0)
            for keyid in crypt_keys.keys():
                self.decoder.control({'tuner': 0, 'cmd': 'crypt_key', 'keyid': int(keyid), 'algid': int(crypt_keys[keyid]['algid']), 'key': crypt_keys[keyid]['key']})

    # Connect up the flow graph
    #
    def __connect(self, cnxns):
        for l in cnxns:
            for b in l:
                if b == l[0]:
                    p = l[0]
                else:
                    self.connect(p, b)
                    p = b
        self.cnxns.extend(cnxns)

    # Disconnect the flow graph
    #
    def __disconnect(self):
        for l in self.cnxns:
            for b in l:
                if b == l[0]:
                    p = l[0]
                else:
                    self.disconnect(p, b)
                    p = b
        self.cnxns = []

    def set_speed(self, new_speed):
     # assumes that lock is held, or that we are in init
        self.disconnect_demods()
        self.current_speed = new_speed
        self.connect_fsk4_demod()

    def control(self, params):
        self.decoder.control(params)

    def configure_tdma(self, params):
        if params['tdma'] is not None and not self.options.phase2_tdma:
            sys.stderr.write("***TDMA request for frequency %d failed- phase2_tdma option not enabled" % params['freq'])
            return
        set_tdma = False
        if params['tdma'] is not None:
            set_tdma = True
            self.decoder.control({'tuner': 0, 'cmd': 'set_slotid', 'slotid': params['tdma']})
        if set_tdma == self.tdma_state:
            return    # already in desired state
        self.tdma_state = set_tdma
        if set_tdma:
            hash = '%x%x%x' % (params['nac'], params['sysid'], params['wacn'])
            if hash not in self.xor_cache:
                self.xor_cache[hash] = lfsr.p25p2_lfsr(params['nac'], params['sysid'], params['wacn']).xor_chars
            self.decoder.control({'tuner': 0, 'cmd': 'set_xormask', 'xormask': self.xor_cache[hash]})
            rate = 6000
        else:
            rate = self.symbol_rate

        self.set_sps(rate)
        if not self.options.symbols:
            self.demod.set_omega(rate)

    def set_sps(self, rate):
        self.sps = self.basic_rate // rate
        if (self.eye_sink is not None):
            self.eye_sink.set_sps(self.sps)

    def error_tracking(self):
        UPDATE_TIME = 3.0
        if self.last_error_update + UPDATE_TIME > time.time() \
            or self.last_change_freq_at + UPDATE_TIME > time.time():
            return
        self.last_error_update = time.time()
        freq_error = self.demod.get_freq_error()
        if abs(freq_error) >= 200: # avoid hunting by only compensating errors over 200hz
            self.freq_correction += freq_error * 0.15
            do_freq_update = 1
        else:
            do_freq_update = 0
        if self.freq_correction > 600:
            self.freq_correction -= 1200
        elif self.freq_correction < -600:
            self.freq_correction += 1200
        self.tuning_error = self.freq_correction
        err_hz = 0
        err_ppm = 0
        if self.last_change_freq > 0:
            err_ppm = round((self.tuning_error*1e6) / float(self.last_change_freq))
            err_hz = -int(self.tuning_error - (err_ppm * (self.last_change_freq / 1e6)))
        if self.options.verbosity >= 10:
            sys.stderr.write('%s frequency_tracking\t%d\t%d\t%d\t%d\n' % (log_ts.get(), freq_error, self.tuning_error, err_ppm, err_hz))
        if do_freq_update:
            corrected_ppm = self.options.freq_corr + err_ppm  # compute new device ppm based on starting point plus adjustment
            if corrected_ppm != self.last_set_ppm:
                self.src.set_freq_corr(corrected_ppm)
                self.last_set_ppm = corrected_ppm
                if self.options.verbosity >= 1:
                    sys.stderr.write('%s Adjusting tuning correction: ppm(%d) ["-q %d"]\n' % (log_ts.get(), corrected_ppm, corrected_ppm))
            self.options.fine_tune = err_hz                   # replace existing fine_tune with new correction value
            self.set_freq(self.target_freq)
            if self.options.verbosity >= 2:
                sys.stderr.write('%s Adjusting tuning: ppm(%d), fine_tune(%d) ["-q %d -d %d"]\n' % (log_ts.get(), corrected_ppm, err_hz, corrected_ppm, err_hz))

    def change_freq(self, params):
        last_freq = self.last_freq_params['freq']
        self.last_freq_params = params
        freq = params['freq']
        offset = params['offset']
        center_freq = params['center_frequency']
        #if self.options.freq_error_tracking:
        #    self.error_tracking()
        self.last_change_freq = freq
        self.last_change_freq_at = time.time()

        if freq != last_freq:                               # ignore requests to tune to same freq
            if self.options.hamlib_model:
                self.hamlib.set_freq(freq)
            elif (not self.options.symbols) and params['center_frequency']:
                relative_freq = center_freq - freq
                if abs(relative_freq + self.options.offset) > self.channel_rate / 2:
                    self.lo_freq = self.options.offset                       # relative tune not possible
                    self.demod.set_relative_frequency(self.lo_freq)              # reset demod relative freq
                    self.set_freq(freq + offset)                                 # direct tune instead
                else:    
                    self.lo_freq = self.options.offset + relative_freq
                    if self.demod.set_relative_frequency(self.lo_freq):      # relative tune successful
                        self.demod.reset()                                       # reset gardner-costas loop
                        self.set_freq(center_freq + offset)
                        if self.fft_sink:
                            self.fft_sink.set_relative_freq(relative_freq)
                    else:
                        self.lo_freq = self.options.offset                   # relative tune unsuccessful
                        self.demod.set_relative_frequency(self.lo_freq)          # reset demod relative freq
                        self.set_freq(freq + offset)                             # direct tune instead
            elif not self.options.symbols:
                self.set_freq(freq + offset)
            else:
                pass                                        # fake tuning when playing back symbols file
            self.decoder.control({'tuner': 0, 'cmd': 'reset_timer'})

        self.configure_tdma(params)
        self.freq_update()

    def freq_update(self):
        params = self.last_freq_params
        params['json_type'] = 'change_freq'
        params['fine_tune'] = self.options.fine_tune
        error = None
        if self.demod is not None:
            error = self.demod.get_freq_error()
        params['error'] = error
        params['stream_url'] = self.stream_url
        js = json.dumps(params)
        msg = gr.message().make_from_string(js, -4, 0, 0)
        if not self.input_q.full_p():
            self.input_q.insert_tail(msg)

    def meta_update(self, tgid, tag):
        if self.meta_server is None:
            return
        d = {'json_type': 'meta_update'}
        d['tgid'] = tgid
        d['tag'] = tag
        msg = gr.message().make_from_string(json.dumps(d), -2, time.time(), 0)
        if not self.meta_q.full_p():
            self.meta_q.insert_tail(msg)

    def hamlib_attach(self, model):
        Hamlib.rig_set_debug (Hamlib.RIG_DEBUG_NONE)    # RIG_DEBUG_TRACE

        self.hamlib = Hamlib.Rig (model)
        self.hamlib.set_conf ("serial_speed","9600")
        self.hamlib.set_conf ("retry","5")

        self.hamlib.open ()

    def q_action(self, action):
        msg = gr.message().make_from_string(action, -2, 0, 0)
        if not self.rx_q.full_p():
            self.rx_q.insert_tail(msg)

    def set_gain(self, gain):
        if self.rtl_found:
            self.src.set_gain(gain, 'LNA')
            if self.options.verbosity:
                sys.stderr.write('RTL Gain of %d set to: %.1f\n' % (gain, self.src.get_gain('LNA')))
        else:
            if self.baseband_input:
                f = 1.0
            else:
                f = 0.1
            self.demod.set_baseband_gain(float(gain) * f)

    def set_audio_scaler(self, vol):
        if hasattr(self.decoder, 'set_scaler_k'):
            self.decoder.set_scaler_k((1 / 32768.0) * (vol * 0.1))

    def set_rtl_ppm(self, ppm):
        self.src.set_freq_corr(ppm)

    def set_freq_tune(self, val):
        if self.demod is not None:
            self.demod.set_relative_frequency(val + self.lo_freq)

    def set_freq(self, target_freq):
        """
        Set the center frequency we're interested in.

        @param target_freq: frequency in Hz
        @rypte: bool

        Tuning is a two step process.  First we ask the front-end to
        tune as close to the desired frequency as it can.  Then we use
        the result of that operation and our target_frequency to
        determine the value for the digital down converter.
        """
        if not self.src:
            return False
        self.target_freq = target_freq
        tune_freq = target_freq + self.options.calibration + self.options.offset + self.options.fine_tune
        r = self.src.set_center_freq(tune_freq)
        self.demod.reset()      # reset gardner-costas loop

        if self.fft_sink:
            self.fft_sink.set_center_freq(target_freq)
            self.fft_sink.set_width(self.options.sample_rate)

        if r:
            #self.myform['freq'].set_value(target_freq)     # update displayed va
            #if self.show_debug_info:
            #    self.myform['baseband'].set_value(r.baseband_freq)
            #    self.myform['ddc'].set_value(r.dxc_freq)
            return True

        return False

    def adj_tune(self, tune_incr):
        if self.target_freq == 0.0:
            return False
        self.options.fine_tune += tune_incr;
        self.set_freq(self.target_freq)
        return True

    def set_debug(self, dbglvl):
        self.options.verbosity = dbglvl
        self.decoder.set_debug(dbglvl)
        if callable(getattr(self.demod, 'set_debug', None)):
            self.demod.set_debug(dbglvl)
        if self.trunk_rx is not None:
            self.trunk_rx.set_debug(dbglvl)

    def toggle_plot(self, plot_type):
        if self.options.symbols:
            return              # plots not supported when replacing symbol

        plot_off = 0
        if (self.fft_sink is not None):
            self.toggle_fft()
            plot_off = 1
        elif (self.constellation_sink is not None):
            self.toggle_constellation()
            plot_off = 2
        elif (self.symbol_sink is not None):
            self.toggle_symbol()
            plot_off = 3
        elif (self.eye_sink is not None):
            self.toggle_eye()
            plot_off = 4
        elif (self.mixer_sink is not None):
            self.toggle_mixer()
            plot_off = 5
        elif (self.fll_sink is not None):
            self.toggle_fll()
            plot_off = 6

        if (plot_type == 1) and (plot_off != 1):    # fft
            self.toggle_fft()
        elif (plot_type == 2) and (plot_off != 2):  # constellation
            self.toggle_constellation()
        elif (plot_type == 3) and (plot_off != 3):  # symbol
            self.toggle_symbol()
        elif (plot_type == 4) and (plot_off != 4):  # datascope
            self.toggle_eye()
        elif (plot_type == 5) and (plot_off != 5):  # mixer output
            self.toggle_mixer()
        elif (plot_type == 6) and (plot_off != 6):  # fll output
            self.toggle_fll()

    def toggle_mixer(self):
        if (self.mixer_sink is None):
            self.mixer_sink = mixer_sink_c()
            self.add_plot_sink(self.mixer_sink)
            self.lock()
            self.demod.connect_complex('agc', self.mixer_sink)
            self.mixer_sink.set_width(self.basic_rate)
            self.unlock()
        elif (self.mixer_sink is not None):
            self.lock()
            self.demod.disconnect_complex(self.mixer_sink)
            self.unlock()
            self.mixer_sink.kill()
            self.remove_plot_sink(self.mixer_sink)
            self.mixer_sink = None

    def toggle_fft(self):
        if (self.fft_sink is None):
            self.fft_sink = fft_sink_c()
            self.add_plot_sink(self.fft_sink)
            if self.options.decim_amt > 1:
                self.spectrum_decim = filter.rational_resampler_ccf(1, self.options.decim_amt)
            else:
                self.spectrum_decim = None
            self.fft_sink.set_offset(self.options.offset)
            self.fft_sink.set_center_freq(self.target_freq)
            self.fft_sink.set_width(self.options.sample_rate)
            self.lock()
            if self.spectrum_decim is not None:
                self.connect(self.spectrum_decim, self.fft_sink)
                self.demod.connect_complex('src', self.spectrum_decim)
            else:
                self.demod.connect_complex('src', self.fft_sink)
            self.unlock()
        elif (self.fft_sink is not None):
            self.lock()
            if self.spectrum_decim is not None:
                self.disconnect(self.spectrum_decim, self.fft_sink)
                self.demod.disconnect_complex(self.spectrum_decim)
            else:
                self.demod.disconnect_complex(self.fft_sink)
            self.unlock()
            self.fft_sink.kill()
            self.remove_plot_sink(self.fft_sink)
            self.spectrum_decim = None
            self.fft_sink = None

    def toggle_constellation(self):
        if (self.constellation_sink is None):
            if self.options.demod_type != 'cqpsk':
                sys.stderr.write("Constellation Plot requires 'cqpsk' modulation\n")
                return
            self.constellation_sink = constellation_sink_c()
            self.add_plot_sink(self.constellation_sink)
            self.lock()
            self.demod.connect_complex('costas', self.constellation_sink)
            self.unlock()
        elif (self.constellation_sink is not None):
            self.lock()
            self.demod.disconnect_complex(self.constellation_sink)
            self.unlock()
            self.constellation_sink.kill()
            self.remove_plot_sink(self.constellation_sink)
            self.constellation_sink = None
 
    def toggle_symbol(self):
        if (self.symbol_sink is None):
            self.symbol_sink = symbol_sink_f()
            self.add_plot_sink(self.symbol_sink)
            self.lock()
            self.demod.connect_float(self.symbol_sink)
            self.unlock()
        elif (self.symbol_sink is not None):
            self.lock()
            self.demod.disconnect_float(self.symbol_sink)
            self.unlock()
            self.symbol_sink.kill()
            self.remove_plot_sink(self.symbol_sink)
            self.symbol_sink = None

    def toggle_eye(self):
        if (self.eye_sink is None):
            self.eye_sink = eye_sink_f(sps=self.sps)
            self.add_plot_sink(self.eye_sink)
            self.lock()
            self.demod.connect_fm_demod() # make sure fm demod exists in flowgraph
            self.demod.connect_bb('symbol_filter', self.eye_sink)
            self.unlock()
        elif (self.eye_sink is not None):
            self.lock()
            self.demod.disconnect_bb(self.eye_sink)    # attempt to remove fm demod if not needed
            self.demod.disconnect_fm_demod()
            self.unlock()
            self.eye_sink.kill()
            self.remove_plot_sink(self.eye_sink)
            self.eye_sink = None

    def toggle_fll(self):
        if (self.fll_sink is None):
            self.fll_sink = fll_sink_c()
            self.add_plot_sink(self.fll_sink)
            self.lock()
            self.demod.connect_complex('fll', self.fll_sink)
            self.fll_sink.set_width(self.basic_rate)
            self.unlock()
        elif (self.fll_sink is not None):
            self.lock()
            self.unlock()
            self.fll_sink.kill()
            self.remove_plot_sink(self.fll_sink)
            self.fll_sink = None

    def add_plot_sink(self, plot):
        if plot not in self.plot_sinks:
            self.plot_sinks.append(plot)
        if self.options.terminal_type.startswith('http:'):
            plot.gnuplot.set_interval(_def_interval)
            plot.gnuplot.set_output_dir(_def_file_dir)

    def remove_plot_sink(self, plot):
        if plot in self.plot_sinks:
            self.plot_sinks.remove(plot)

    # read capture file properties (decimation etc.)
    #
    def __read_file_properties(self, filename):
        f = open(filename, "r")
        self.info = pickle.load(f)
        ToDo = True
        f.close()

    # setup to rx from file
    #
    def __set_rx_from_file(self, filename, capture_rate):
        file = blocks.file_source(gr.sizeof_gr_complex, filename, True)
        gain = blocks.multiply_const_cc(self.options.gain)
        throttle = blocks.throttle(gr.sizeof_gr_complex, capture_rate)
        self.__connect([[file, gain, throttle]])
        self.__build_graph(throttle, capture_rate)

    # setup to rx from Audio
    #
    def __set_rx_from_audio(self, capture_rate):
        self.__build_graph(self.source, capture_rate)

    # setup to rx from USRP
    #
    def __set_rx_from_osmosdr(self):
        # setup osmosdr
        capture_rate = self.src.set_sample_rate(self.options.sample_rate)
        if self.options.antenna:
            self.src.set_antenna(self.options.antenna)
        self.info["capture-rate"] = capture_rate
        self.src.set_bandwidth(capture_rate)
        # capture file
        # if preserve:
        if 0:
            try:
                self.capture_filename = os.tmpnam()
            except RuntimeWarning:
                ignore = True
            capture_file = blocks.file_sink(gr.sizeof_gr_complex, self.capture_filename)
            self.__connect([[self.usrp, capture_file]])
        else:
            self.capture_filename = None
        # everything else
        self.__build_graph(self.src, capture_rate)

    # Write capture file properties
    #
    def __write_file_properties(self, filename):
        f = open(filename, "w")
        pickle.dump(self.info, f)
        f.close()

    def open_ifile(self, capture_rate, gain, input_filename, file_seek):
        speed = 96000 # TODO: fixme
        ifile = blocks.file_source(gr.sizeof_gr_complex, input_filename, 1)
        if file_seek > 0:
            rc = ifile.seek(file_seek*1024, gr.SEEK_SET)
            assert rc == True
        throttle = blocks.throttle(gr.sizeof_gr_complex, speed)
        self.source = blocks.multiply_const_cc(gain)
        self.connect(ifile, throttle, self.source)
        self.__set_rx_from_audio(speed)

    def open_ifile2(self, capture_rate, file_name):
        source = blocks.file_source(gr.sizeof_gr_complex, file_name, False)
        throttle = blocks.throttle(gr.sizeof_gr_complex, capture_rate)
        self.connect(source, throttle)
        self.__build_graph(throttle, capture_rate)

    def open_symbols(self, symbol_rate, file_name, file_seek):
        sys.stderr.write("Reading raw symbols from file: %s\n" % self.options.symbols)
        source = blocks.file_source(gr.sizeof_char, file_name, False)
        if file_seek > 0:
            rc = source.seek(file_seek*4800, 0) # Seek in seconds (4800sps)
            assert rc == True
        throttle = blocks.throttle(gr.sizeof_char, symbol_rate)
        throttle.set_max_noutput_items(int(symbol_rate/50));
        self.connect(source, throttle)
        self.__build_graph(throttle, symbol_rate)

    def open_audio_c(self, capture_rate, gain, audio_input_filename):
        self.info = {
                "capture-rate": capture_rate,
                "center-freq": 0,
                "source-dev": "AUDIO",
                "source-decim": 1 }
        self.audio_source = audio.source(capture_rate, audio_input_filename)
        self.audio_cvt = blocks.float_to_complex()
        self.connect((self.audio_source, 0), (self.audio_cvt, 0))
        self.connect((self.audio_source, 1), (self.audio_cvt, 1))
        self.source = blocks.multiply_const_cc(gain)
        self.connect(self.audio_cvt, self.source)
        self.__set_rx_from_audio(capture_rate)

    def open_audio(self, capture_rate, gain, audio_input_filename):
            self.info = {
                "capture-rate": capture_rate,
                "center-freq": 0,
                "source-dev": "AUDIO",
                "source-decim": 1 }
            self.audio_source = audio.source(capture_rate, audio_input_filename)
            self.source = blocks.multiply_const_ff(gain)
            self.connect(self.audio_source, self.source)
            self.__set_rx_from_audio(capture_rate)

    # Open the USRP
    #
    def open_usrp(self):
        # try:
            self.info = {
                "capture-rate": "unknown",
                "center-freq": self.options.frequency,
                "source-dev": "USRP",
                "source-decim": 1 }
            self.__set_rx_from_osmosdr()
            if self.options.frequency:
                self.last_freq_params['freq'] = self.options.frequency
                self.set_freq(self.options.frequency)
        # except Exception, x:
        #     wx.MessageBox("Cannot open USRP: " + x.message, "USRP Error", wx.CANCEL | wx.ICON_EXCLAMATION)

    def process_ajax(self):
        if not self.options.terminal_type.startswith('http:'):
            return
        filenames = [sink.gnuplot.filename for sink in self.plot_sinks if sink.gnuplot.filename]
        error = None
        if self.demod is not None:
            error = self.demod.get_freq_error()
        d = {'json_type': 'rx_update', 'error': error, 'fine_tune': self.options.fine_tune, 'files': filenames}
        msg = gr.message().make_from_string(json.dumps(d), -4, 0, 0)
        if not self.input_q.full_p():
            self.input_q.insert_tail(msg)

    def process_qmsg(self, msg):
        # return true = end top block
        RX_COMMANDS = 'skip lockout hold whitelist reload'.split()
        s = msg.to_string()
        if type(s) is not str and isinstance(s, bytes):
            # should only get here if python3
            s = s.decode()
        if s == 'quit': return True
        elif s == 'update':
            self.ui_last_update = time.time()
            self.freq_update()
            if self.trunk_rx is None:
                return False    ## possible race cond - just ignore
            js = self.trunk_rx.to_json()
            msg = gr.message().make_from_string(js, -4, 0, 0)
            if not self.input_q.full_p():
                self.input_q.insert_tail(msg)
            self.process_ajax()
        elif s == 'set_debug':
            self.set_debug(int(msg.arg1()))
        elif s == 'set_freq':
            freq = msg.arg1()
            self.last_freq_params['freq'] = freq
            self.set_freq(freq)
        elif s == 'adj_tune':
            freq = msg.arg1()
            self.adj_tune(freq)
        elif s == 'toggle_plot':
            plot_type = msg.arg1()
            self.toggle_plot(plot_type)
        elif s == 'dump_tgids':
            self.trunk_rx.dump_tgids()
        elif s == 'add_default_config':
            nac = msg.arg1()
            self.trunk_rx.add_default_config(int(nac))
        elif s == 'capture':
            pass
        elif s == 'watchdog':
            if self.ui_last_update > 0 and (time.time() > (self.ui_last_update + self.ui_timeout)):
                self.ui_last_update = 0
                sys.stderr.write("%s UI Timeout\n" % log_ts.get())
                self.toggle_plot(0)

        elif s in RX_COMMANDS:
            if not self.rx_q.full_p():
                self.rx_q.insert_tail(msg)
        return False

############################################################################

# data unit receive queue
#
class du_queue_watcher(threading.Thread):

    def __init__(self, msgq,  callback, **kwds):
        threading.Thread.__init__ (self, **kwds)
        self.daemon = True
        self.msgq = msgq
        self.callback = callback
        self.keep_running = True
        self.start()

    def run(self):
        while(self.keep_running):
            if not self.msgq.empty_p(): # check queue before trying to read a message to avoid deadlock at startup
                msg = self.msgq.delete_head()
                if msg is not None:
                    self.callback(msg)
                else:
                    self.keep_running = False
            else: # empty queue
                time.sleep(0.01)            

class rx_main(object):
    def __init__(self):
        self.keep_running = True
        self.cli_options()
        self.tb = p25_rx_block(self.options)
        self.q_watcher = du_queue_watcher(self.tb.output_q, self.process_qmsg)
        sys.stderr.write('python version detected: %s\n' % sys.version)

    def process_qmsg(self, msg):
        if self.tb.process_qmsg(msg):
            #self.tb.stop()
            self.keep_running = False

    def run(self):
        try:
            self.tb.start()
            if self.options.symbols:
                self.tb.wait()
            else:
                while self.keep_running:
                    time.sleep(1)
                    msg = gr.message().make_from_string("watchdog", -2, 0, 0)
                    if not self.tb.output_q.full_p():
                        self.tb.output_q.insert_tail(msg)
            sys.stderr.write('Flowgraph completed. Exiting\n')
        except:
            sys.stderr.write('main: exception occurred\n')
            sys.stderr.write('main: exception:\n%s\n' % traceback.format_exc())
        if self.tb.terminal:
            self.tb.terminal.end_terminal()
        if self.tb.meta_server:
            self.tb.meta_server.stop()
        if self.tb.audio:
            self.tb.audio.stop()
        self.tb.stop()
        for sink in self.tb.plot_sinks:
            sink.kill()

    def cli_options(self):
        # command line argument parsing
        parser = OptionParser(option_class=eng_option)
        parser.add_option("--args", type="string", default="", help="device args")
        parser.add_option("--antenna", type="string", default="", help="select antenna")
        parser.add_option("-a", "--audio", action="store_true", default=False, help="use direct audio input")
        parser.add_option("-A", "--audio-if", action="store_true", default=False, help="soundcard IF mode (use --calibration to set IF freq)")
        parser.add_option("-I", "--audio-input", type="string", default="", help="pcm input device name.  E.g., hw:0,0 or /dev/dsp")
        parser.add_option("-i", "--input", default=None, help="input file name")
        parser.add_option("-b", "--excess-bw", type="eng_float", default=0.2, help="for RRC filter", metavar="Hz")
        parser.add_option("-c", "--calibration", type="eng_float", default=0.0, help="USRP offset or audio IF frequency", metavar="Hz")
        parser.add_option("-C", "--costas-alpha", type="eng_float", default=0.001, help="value of alpha for Costas loop", metavar="Hz")
        parser.add_option("-D", "--demod-type", type="choice", default="cqpsk", choices=('cqpsk', 'fsk4'), help="cqpsk | fsk4")
        parser.add_option("-P", "--plot-mode", type="choice", default=None, choices=(None, 'constellation', 'fft', 'symbol', 'datascope', 'mixer', 'fll'), help="constellation | fft | symbol | datascope | mixer | tuner")
        parser.add_option("-f", "--frequency", type="eng_float", default=0.0, help="USRP center frequency", metavar="Hz")
        parser.add_option("-F", "--ifile", type="string", default=None, help="read input from complex capture file")
        parser.add_option("-H", "--hamlib-model", type="int", default=None, help="specify model for hamlib")
        parser.add_option("-s", "--seek", type="int", default=0, help="ifile seek in K, symbols file seek in seconds")
        parser.add_option("-l", "--terminal-type", type="string", default='curses', help="'curses' or udp port or 'http:host:port'")
        parser.add_option("-L", "--logfile-workers", type="int", default=None, help="number of demodulators to instantiate")
        parser.add_option("-M", "--metacfg", type="string", default=None, help="Icecast Metadata Config File")
        parser.add_option("-S", "--sample-rate", type="int", default=960000, help="source samp rate")
        parser.add_option("-t", "--tone-detect", action="store_true", default=False, help="use experimental tone detect algorithm")
        parser.add_option("-T", "--trunk-conf-file", type="string", default=None, help="trunking config file name")
        parser.add_option("-v", "--verbosity", type="int", default=0, help="message debug level")
        parser.add_option("-V", "--vocoder", action="store_true", default=False, help="voice codec")
        parser.add_option("-n", "--nocrypt", action="store_true", default=False, help="silence encrypted traffic")
        parser.add_option("--crypt-behavior", type="int", default=2, help="encrypted traffic behavior: 0=allow, 1=silence, 2=skip")
        parser.add_option("-k", "--crypt-keys", type="string", default=None, help="decryption keys file (in json format)")
        parser.add_option("-o", "--offset", type="eng_float", default=0.0, help="tuning offset frequency [to circumvent DC offset]", metavar="Hz")
        parser.add_option("-p", "--pause", action="store_true", default=False, help="block on startup")
        parser.add_option("-w", "--wireshark", action="store_true", default=False, help="output data to Wireshark")
        parser.add_option("-W", "--wireshark-host", type="string", default="127.0.0.1", help="Wireshark host")
        parser.add_option("-u", "--wireshark-port", type="int", default=23456, help="Wireshark udp port")
        parser.add_option("-r", "--raw-symbols", type="string", default=None, help="dump decoded symbols to file")
        parser.add_option("--symbols", type="string", default="", help="playback symbols file (captured using -r)")
        parser.add_option("-R", "--rx-subdev-spec", type="subdev", default=(0, 0), help="select USRP Rx side A or B (default=A)")
        parser.add_option("-g", "--gain", type="eng_float", default=None, help="set USRP gain in dB (default is midpoint) or set audio gain")
        parser.add_option("--gain-mode", type="int", help="Control SDR AGC with set_gain_mode()")
        parser.add_option("-G", "--gain-mu", type="eng_float", default=0.025, help="gardner gain")
        parser.add_option("-N", "--gains", type="string", default=None, help="gain settings")
        parser.add_option("-O", "--audio-output", type="string", default="default", help="audio output device name")
        parser.add_option("-x", "--audio-gain", type="eng_float", default="1.0", help="audio gain (default = 1.0)")
        parser.add_option("-X", "--freq-error-tracking", action="store_true", default=False, help="enable experimental frequency error tracking")
        parser.add_option("-U", "--udp-player", action="store_true", default=False, help="enable built-in udp audio player")
        parser.add_option("-q", "--freq-corr", type="eng_float", default=0.0, help="frequency correction")
        parser.add_option("-d", "--fine-tune", type="eng_float", default=0.0, help="fine tuning")
        parser.add_option("-2", "--phase2-tdma", action="store_true", default=False, help="enable phase2 tdma decode")
        parser.add_option("--tdma-cc", action="store_true", default=False, help="enable tdma control channel")
        parser.add_option("-Z", "--decim-amt", type="int", default=1, help="spectrum decimation")
        (options, args) = parser.parse_args()
        if len(args) != 0:
            parser.print_help()
            sys.exit(1)
        self.options = options

# Start the receiver
#

if __name__ == "__main__":
    if sys.version[0] > '2':
        sys.stderr = io.TextIOWrapper(sys.stderr.detach().detach(), write_through=True) # disable stderr buffering
    rx = rx_main()
    rx.run()
