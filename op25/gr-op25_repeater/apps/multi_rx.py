#!/bin/sh
# Copyright 2011, 2012, 2013, 2014, 2015, 2016, 2017 Max H. Parke KA1RBI
# Copyright 2020, 2021 Graham J. Norbury - gnorbury@bondcar.com
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
import op25_nbfm
import op25_iqsrc
import op25_wavsrc
from log_ts import log_ts

from gr_gnuplot import constellation_sink_c
from gr_gnuplot import fft_sink_c
from gr_gnuplot import symbol_sink_f
from gr_gnuplot import eye_sink_f
from gr_gnuplot import mixer_sink_c
from gr_gnuplot import fll_sink_c

sys.path.append('tdma')
import lfsr

os.environ['IMBE'] = 'soft'

_def_symbol_rate = 4800
_def_capture_file = "capture.bin"

# Helper functions
#
def from_dict(d, key, def_val):
    if key in d and d[key] != "":
        return d[key]
    else:
        return def_val

def get_fractional_ppm(tuned_freq, adj_val):
    return (adj_val * 1e6 / tuned_freq)

# The P25 receiver
#

class device(object):
    def __init__(self, config):
        speeds = [250000, 1000000, 1024000, 1800000, 1920000, 2000000, 2048000, 2400000, 2560000]

        self.name = config['name']
        self.args = config['args']
        self.tunable = bool(from_dict(config, 'tunable', False))

        sys.stderr.write('device: %s\n' % config)
        if config['args'] == 'iqsrc':
            self.src = op25_iqsrc.op25_iqsrc_c(str(config['name']), config)
            self.ppm = float(from_dict(config, 'ppm', "0.0"))
            self.tunable = False
            if self.src.is_dsd():
                self.frequency = self.src.get_center_freq()
                self.sample_rate = self.src.get_sample_rate()
                self.offset = 600000
            else:
                self.frequency = int(from_dict(config, 'frequency', 800000000))
                self.sample_rate = config['rate']
                self.offset = int(from_dict(config, 'offset', 0))
            self.fractional_corr = int((int(round(self.ppm)) - self.ppm) * (self.frequency/1e6))
            self.usable_bw = float(from_dict(config, 'usable_bw_pct', 1.0))

        elif config['args'] == 'wavsrc':
            self.src = op25_wavsrc.op25_wavsrc_f(str(config['name']), config)
            self.sample_rate = self.src.get_sample_rate()
            self.ppm = float(from_dict(config, 'ppm', "0.0"))
            self.frequency = int(from_dict(config, 'frequency', 800000000))
            self.offset = 0
            self.fractional_corr = 0
            self.tunable = False

        else:
            if config['args'].startswith('rtl') and config['rate'] not in speeds:
                sys.stderr.write('WARNING: requested sample rate %d for device %s may not\n' % (config['rate'], config['name']))
                sys.stderr.write("be optimal.  You may want to use one of the following rates\n")
                sys.stderr.write('%s\n' % speeds)
            sys.stderr.write('Device name: "%s", osmosdr args: "%s"\n' % (self.name, str(config['args'])))
            self.src = osmosdr.source(str(config['args']))

            if 'gain_mode' in config:
                gain_mode = from_dict(config, 'gain_mode', False)
                if gain_mode:
                    self.src.set_gain_mode(True, 0)
                else:
                    self.src.set_gain_mode(True, 0)  # UGH! Ugly workaround for gr-osmosdr airspy bug
                    self.src.set_gain_mode(False, 0)
                sys.stderr.write("gr-osmosdr driver gain_mode: %s\n" % self.src.get_gain_mode())

            for tup in config['gains'].split(','):
                name, gain = tup.split(':')
                self.src.set_gain(int(gain), str(name))

            self.ppm = float(from_dict(config, 'ppm', "0.0"))
            self.src.set_freq_corr(int(round(self.ppm)))

            self.src.set_sample_rate(config['rate'])
            self.sample_rate = config['rate']

            self.offset = int(from_dict(config, 'offset', 0))

            self.frequency = int(from_dict(config, 'frequency', 800000000))
            self.fractional_corr = int((int(round(self.ppm)) - self.ppm) * (self.frequency/1e6))
            self.src.set_center_freq(self.frequency + self.offset)
            self.usable_bw = float(from_dict(config, 'usable_bw_pct', 1.0))

    def get_ppm(self):
        return self.ppm

    def set_debug(self, dbglvl):
        pass

class channel(object):
    def __init__(self, config, dev, verbosity, msgq_id, rx_q, tb):
        sys.stderr.write('channel (dev %s): %s\n' % (dev.name, config))
        self.verbosity = verbosity
        ch_name = str(from_dict(config, 'name', ""))
        self.name = ("[%d] %s" % (msgq_id, ch_name)) if ch_name != "" else ("[%d]" % msgq_id) 
        self.device = dev
        self.frequency = int(from_dict(config, "frequency", dev.frequency))
        self.msgq_id = msgq_id
        self.tb = tb
        self.raw_sink = None
        self.raw_file = None
        self.throttle = None
        self.nbfm = None
        self.nbfm_mode = 0
        self.auto_tracking      = bool(from_dict(config, "cqpsk_tracking", False))
        self.tracking_threshold = int(from_dict(config, "tracking_threshold", 120))
        self.tracking_limit     = int(from_dict(config, "tracking_limit", 2400))
        self.tracking_feedback  = float(from_dict(config, "tracking_feedback", 0.85))
        #if str(from_dict(config, "demod_type", "")).lower() != "cqpsk":
        #    self.auto_tracking = False
        self.tracking = 0
        self.tracking_cache = {}
        self.error = None
        self.chan_idle = False
        self.sinks = {}
        self.tdma_state = False
        self.xor_cache = {}
        self.config = config
        self.symbol_rate = int(from_dict(config, 'symbol_rate', _def_symbol_rate))
        self.channel_rate = self.symbol_rate
        if dev.args == 'wavsrc':
            self.demod = p25_demodulator.p25_demod_fb(
                             msgq_id = self.msgq_id,
                             debug = self.verbosity,
                             input_rate=dev.sample_rate,
                             filter_type = config['filter_type'],
                             excess_bw=config['excess_bw'],
                             symbol_rate = self.symbol_rate)
        elif config['demod_type'] == "fsk": # Motorola 3600bps
            filter_type = from_dict(config, 'filter_type', 'fsk2mm')
            if filter_type[:4] != 'fsk2':   # has to be 'fsk2' or derivative such as 'fsk2mm'
                filter_type = 'fsk2mm'
            self.demod = p25_demodulator.p25_demod_cb(
                             msgq_id = self.msgq_id,
                             debug = self.verbosity,
                             input_rate = dev.sample_rate,
                             demod_type = 'fsk4',
                             filter_type = filter_type,
                             usable_bw = self.device.usable_bw,
                             excess_bw = float(from_dict(config, 'excess_bw', 0.2)),
                             relative_freq = (dev.frequency + dev.offset + dev.fractional_corr),
                             offset = dev.offset,
                             if_rate = config['if_rate'],
                             symbol_rate = self.symbol_rate)
        else:                             # P25, DMR, NXDN and everything else
            self.demod = p25_demodulator.p25_demod_cb(
                             msgq_id = self.msgq_id,
                             debug = self.verbosity,
                             input_rate = dev.sample_rate,
                             demod_type = config['demod_type'],
                             filter_type = config['filter_type'],
                             usable_bw = self.device.usable_bw,
                             excess_bw = float(from_dict(config, 'excess_bw', 0.2)),
                             relative_freq = (dev.frequency + dev.offset + dev.fractional_corr),
                             offset = dev.offset,
                             if_rate = config['if_rate'],
                             symbol_rate = self.symbol_rate)
        self.decoder = op25_repeater.frame_assembler(str(config['destination']), verbosity, msgq_id, rx_q)

        # Relative-tune the demodulator
        if not self.demod.set_relative_frequency((dev.frequency + dev.offset + dev.fractional_corr) - self.frequency):
            sys.stderr.write("%s [%d] Unable to initialize demod to freq: %d, using device freq: %d\n" % (log_ts.get(), self.msgq_id, self.frequency, dev.frequency))
            self.frequency = dev.frequency

        if 'key' in config and (config['key'] != ""):
            self.set_key(int(config['key'], 0))

        enable_analog = str(from_dict(config, 'enable_analog', "auto")).lower()
        if enable_analog == "off":
            self.nbfm_mode = 0;
        elif enable_analog == "on":
            self.nbfm_mode = 2;
        else:
            self.nbfm_mode = 1;
        
        if self.nbfm_mode > 0:
            self.nbfm = op25_nbfm.op25_nbfm_c(str(config['destination']), verbosity, config, msgq_id, rx_q)
            if self.demod.connect_nbfm(self.nbfm):
                if self.nbfm_mode == 2:
                    self.nbfm.control(True)
            else:
                self.nbfm = None

        if ('plot' not in list(config.keys())) or (config['plot'] == ""):
            return

        for plot in config['plot'].split(','):
            if plot == 'datascope':
                self.toggle_eye_plot()
            elif plot == 'symbol':
                self.toggle_symbol_plot()
            elif plot == 'fft':
                self.toggle_fft_plot()
            elif plot == 'constellation':
                self.toggle_constellation_plot()
            elif plot == 'mixer':
                self.toggle_mixer_plot()
            elif plot == 'fll':
                self.toggle_fll_plot()
            else:
                sys.stderr.write('unrecognized plot type %s\n' % plot)
                return

    def set_debug(self, dbglvl):
        self.verbosity = dbglvl
        if self.decoder is not None:
            self.decoder.set_debug(dbglvl)
        if self.nbfm is not None:
            self.nbfm.set_debug(dbglvl)
        if self.demod is not None:
            self.demod.set_debug(dbglvl)

    def toggle_capture(self):
        if self.raw_sink is None:   # turn on raw symbol capture
            sink_file = str(from_dict(self.config, "raw_output", "ch"+str(self.msgq_id)+"-"+_def_capture_file))
            sys.stderr.write("%s Saving raw symbols to file: %s\n" % (log_ts.get(), sink_file))
            self.tb.lock()
            self.raw_sink = blocks.file_sink(gr.sizeof_char, sink_file)
            self.tb.connect(self.demod, self.raw_sink)
            self.tb.unlock()
        else:                       # turn off raw symbol capture
            sys.stderr.write("%s Ending raw symbol capture\n" % log_ts.get())
            self.tb.lock()
            self.tb.disconnect(self.demod, self.raw_sink)
            self.tb.unlock()
            self.raw_sink = None

    def set_plot_destination(self, plot): # only required for http terminal
        if plot is None or plot not in self.sinks or self.tb.terminal_type is None:
            return
        if self.tb.terminal_type == "http":
            self.sinks[plot][0].gnuplot.set_interval(self.tb.http_plot_interval)
            self.sinks[plot][0].gnuplot.set_output_dir(self.tb.http_plot_directory)
        else:
            self.sinks[plot][0].gnuplot.set_interval(self.tb.curses_plot_interval)

    def toggle_plot(self, plot_type):
        if plot_type == 1:
            self.toggle_fft_plot()
        elif plot_type == 2:
            self.toggle_constellation_plot()
        elif plot_type == 3:
            self.toggle_symbol_plot()
        elif plot_type == 4:
            self.toggle_eye_plot()
        elif plot_type == 5:
            self.toggle_mixer_plot()
        elif plot_type == 6:
            self.toggle_fll_plot()

    def close_plots(self):
        for plot in list(self.sinks.keys()):
            self.sinks[plot][1]()

    def toggle_eye_plot(self):
        if 'eye' not in self.sinks:
            sink = eye_sink_f(plot_name=("Ch:%s" % self.name), chan=self.msgq_id, out_q=self.tb.ui_in_q)
            sink.set_sps(self.config['if_rate'] / self.symbol_rate)
            self.sinks['eye'] = (sink, self.toggle_eye_plot)
            self.set_plot_destination('eye')
            self.tb.lock()
            self.demod.connect_fm_demod()                   # add fm demod to flowgraph if not already present
            self.demod.connect_bb('symbol_filter', sink)
            self.tb.unlock()
        else:
            (sink, fn) = self.sinks.pop('eye')
            self.tb.lock()
            self.demod.disconnect_bb(sink)
            self.demod.disconnect_fm_demod()                # remove fm demod from flowgraph if no longer needed
            self.tb.unlock()
            sink.kill()

    def toggle_fll_plot(self):
        if 'fll' not in self.sinks:
            sink = fll_sink_c(plot_name=("Ch:%s" % self.name), chan=self.msgq_id, out_q=self.tb.ui_in_q)
            self.sinks['fll'] = (sink, self.toggle_mixer_plot)
            self.set_plot_destination('fll')
            sink.set_width(self.config['if_rate'])
            self.tb.lock()
            self.demod.connect_complex('fll', sink)
            self.tb.unlock()
        else:
            (sink, fn) = self.sinks.pop('fll')
            self.tb.lock()
            self.demod.disconnect_complex(sink)
            self.tb.unlock()
            sink.kill()

    def toggle_symbol_plot(self):
        if 'symbol' not in self.sinks:
            sink = symbol_sink_f(plot_name=("Ch:%s" % self.name), chan=self.msgq_id, out_q=self.tb.ui_in_q)
            self.sinks['symbol'] = (sink, self.toggle_symbol_plot)
            self.set_plot_destination('symbol')
            self.tb.lock()
            self.demod.connect_float(sink)
            self.tb.unlock()
        else:
            (sink, fn) = self.sinks.pop('symbol')
            self.tb.lock()
            self.demod.disconnect_float(sink)
            self.tb.unlock()
            sink.kill()

    def toggle_fft_plot(self):
        if 'fft' not in self.sinks:
            sink = fft_sink_c(plot_name=("Ch:%s" % self.name), chan=self.msgq_id, out_q=self.tb.ui_in_q)
            self.sinks['fft'] = (sink, self.toggle_fft_plot)
            self.set_plot_destination('fft')
            sink.set_offset(self.device.offset)
            sink.set_center_freq(self.device.frequency)
            sink.set_relative_freq(self.device.frequency - self.frequency)
            sink.set_width(self.device.sample_rate)
            self.tb.lock()
            self.demod.connect_complex('src', sink)
            self.tb.unlock()
        else:
            (sink, fn) = self.sinks.pop('fft')
            self.tb.lock()
            self.demod.disconnect_complex(sink)
            self.tb.unlock()
            sink.kill()

    def toggle_mixer_plot(self):
        if 'mixer' not in self.sinks:
            sink = mixer_sink_c(plot_name=("Ch:%s" % self.name), chan=self.msgq_id, out_q=self.tb.ui_in_q)
            self.sinks['mixer'] = (sink, self.toggle_mixer_plot)
            self.set_plot_destination('mixer')
            sink.set_width(self.config['if_rate'])
            self.tb.lock()
            self.demod.connect_complex('agc', sink)
            self.tb.unlock()
        else:
            (sink, fn) = self.sinks.pop('mixer')
            self.tb.lock()
            self.demod.disconnect_complex(sink)
            self.tb.unlock()
            sink.kill()

    def toggle_constellation_plot(self):
        if str(self.config['demod_type']).lower() != "cqpsk":
            return
        if 'constellation' not in self.sinks:
            sink = constellation_sink_c(plot_name=("Ch:%s" % self.name), chan=self.msgq_id, out_q=self.tb.ui_in_q)
            self.sinks['constellation'] = (sink, self.toggle_constellation_plot)
            self.set_plot_destination('constellation')
            self.tb.lock()
            self.demod.connect_complex('costas', sink)
            self.tb.unlock()
        else:
            (sink, fn) = self.sinks.pop('constellation')
            self.tb.lock()
            self.demod.disconnect_complex(sink)
            self.tb.unlock()
            sink.kill()

    def set_freq(self, freq):
        if self.frequency == freq:
            return True

        old_freq = self.frequency
        old_track = self.tracking
        self.frequency = freq
        self.tracking_cache[old_freq] = old_track
        if self.frequency in self.tracking_cache:
            self.tracking = self.tracking_cache[self.frequency]     # if cached value available use it otherwise continue with existing

        if not self.demod.set_relative_frequency(self.device.offset + self.device.frequency + self.device.fractional_corr + self.tracking - freq): # First attempt relative tune
            if self.device.tunable:                                                                  # then hard tune if allowed
                self.device.frequency = self.frequency
                self.device.src.set_center_freq(self.frequency + self.device.offset)
                self.device.fractional_corr = int((int(round(self.device.ppm)) - self.device.ppm) * (self.device.frequency/1e6))        # Calc frac ppm using new freq
                self.demod.set_relative_frequency(self.device.offset + self.device.frequency + self.device.fractional_corr + self.tracking - freq)
                if self.verbosity >= 9:
                    sys.stderr.write("%s [%d] Hardware tune: dev_freq(%d), dev_off(%d), dev_frac(%d), tune_freq(%d), tracking(%d)\n" % (log_ts.get(), self.msgq_id, self.device.frequency, self.device.offset, self.device.fractional_corr, (self.device.frequency - (self.device.offset + self.device.frequency + self.device.fractional_corr - freq)), self.tracking))
            else:                                                                                    # otherwise fail and reset to prev freq
                self.tracking = old_track
                self.demod.set_relative_frequency(self.device.offset + self.device.frequency + self.device.fractional_corr + self.tracking - old_freq)
                self.frequency = old_freq
                if self.verbosity:
                    sys.stderr.write("%s [%d] Unable to tune %s to frequency %f\n" % (log_ts.get(), self.msgq_id, self.name, (freq/1e6)))
                return False
        else:
            if self.verbosity >= 9:
                sys.stderr.write("%s [%d] Relative tune: dev_freq(%d), dev_off(%d), dev_frac(%d), tune_freq(%d), tracking(%d)\n" % (log_ts.get(), self.msgq_id, self.device.frequency, self.device.offset, self.device.fractional_corr, (self.device.frequency - (self.device.offset + self.device.frequency + self.device.fractional_corr + self.tracking - freq)), self.tracking))
        if 'fft' in self.sinks:
                self.sinks['fft'][0].set_center_freq(self.device.frequency)
                self.sinks['fft'][0].set_relative_freq(self.device.frequency - freq)
        if self.verbosity >= 9:
            sys.stderr.write("%s [%d] Tuning to frequency %f\n" % (log_ts.get(), self.msgq_id, (freq/1e6)))
        self.demod.reset()          # reset gardner-costas tracking loop
        self.decoder.sync_reset()   # reset frame_assembler
        return True

    def adj_tune(self, adjustment): # ideally this would all be done at the device level but the demod belongs to the channel object
        self.tracking = 0
        self.device.ppm -= get_fractional_ppm(self.device.frequency, adjustment)
        self.device.src.set_freq_corr(int(round(self.device.ppm)))
        self.device.src.set_center_freq(self.device.frequency + self.device.offset)
        self.device.fractional_corr = int((int(round(self.device.ppm)) - self.device.ppm) * (self.device.frequency/1e6))
        self.demod.set_relative_frequency(self.device.offset + self.device.frequency + self.device.fractional_corr + self.tracking - self.frequency)
        self.demod.reset()          # reset gardner-costas tracking loop

    def configure_p25_tdma(self, params):
        set_tdma = False
        if 'tdma' in params and params['tdma'] is not None:
            set_tdma = True
            self.decoder.set_slotid(params['tdma'])
        if set_tdma == self.tdma_state:
            return
        self.tdma_state = set_tdma
        if set_tdma:
            hash = '%x%x%x' % (params['nac'], params['sysid'], params['wacn'])
            if hash not in self.xor_cache:
                self.xor_cache[hash] = lfsr.p25p2_lfsr(params['nac'], params['sysid'], params['wacn']).xor_chars
                if self.verbosity >= 5:
                    sys.stderr.write("%s [%d] Caching TDMA xor mask for NAC: 0x%x, SYSID: 0x%x, WACN: 0x%x\n" % (log_ts.get(), self.msgq_id, params['nac'], params['sysid'], params['wacn'])) 
            self.decoder.set_xormask(self.xor_cache[hash])
            rate = 6000
        else:
            rate = self.channel_rate

        self.symbol_rate = rate
        self.demod.set_omega(rate)
        if 'eye' in self.sinks:
            self.sinks['eye'][0].set_sps(self.config['if_rate'] / rate)

    def set_rate(self, rate):
        self.symbol_rate = rate
        self.demod.set_omega(rate)
        if 'eye' in self.sinks:
            self.sinks['eye'][0].set_sps(self.config['if_rate'] / rate)

    def set_nac(self, nac):
        self.decoder.set_nac(nac)

    def set_slot(self, slot):
        self.chan_idle = True if (slot == 4) else False
        self.decoder.set_slotid(slot)

    def set_key(self, key):
        self.decoder.set_slotkey(key)

    def kill(self):
        for sink in self.sinks:
            self.sinks[sink][0].kill()

    def error_tracking(self):
        #if self.chan_idle or not self.auto_tracking:
        if self.chan_idle:
            self.error = None
            return
        self.error = self.demod.get_freq_error()
        #if self.verbosity >= 10:
        #if self.verbosity >= 1:
        #    sys.stderr.write("%s [%d] frequency tracking(%d): locked: % d, quality: %f, freq: %d\n" % (log_ts.get(), self.msgq_id, self.tracking, self.demod.locked(), self.demod.quality(), self.error))
        #if abs(self.error) >= self.tracking_threshold:
        #    self.tracking += self.error * self.tracking_feedback
        #    self.tracking = min(self.tracking_limit, max(-self.tracking_limit, self.tracking))
        #    self.tracking_cache[self.frequency] = self.tracking
        #    self.demod.set_relative_frequency(self.device.offset + self.device.frequency + self.device.fractional_corr + self.tracking - self.frequency)

    def dump_tracking(self):
        sys.stderr.write("%s [%d] Frequency Tracking Cache: ch(%d)\n{\n" % (log_ts.get(), self.msgq_id, self.msgq_id))
        for freq in sorted(self.tracking_cache):
            sys.stderr.write("%f : %d\n" % ((freq/1e6), self.tracking_cache[freq]))
        sys.stderr.write("}\n")

    def set_tracking(self, tracking):
        if tracking > 0:
            self.auto_tracking = True
        elif tracking == 0:
            self.auto_tracking = False
        else:
            self.auto_tracking = not self.auto_tracking
        if self.verbosity >= 10:
            sys.stderr.write("%s [%d] set auto_tracking:%s\n" % (log_ts.get(), self.msgq_id, ("on" if self.auto_tracking else "off")))

    def get_error(self):
        return self.error

    def get_tracking(self):
        return self.tracking

    def get_auto_tracking(self):
        return self.auto_tracking


class rx_block (gr.top_block):

    # Initialize the receiver
    #
    def __init__(self, verbosity, config):
        self.config = config
        self.verbosity = verbosity
        self.devices = []
        self.channels = []
        self.terminal = None
        self.terminal_type = None
        self.terminal_config = None
        self.interactive = True
        self.audio = None
        self.audio_instances = {}
        self.metadata = None
        self.meta_streams = {}
        self.trunking = None
        self.du_watcher = None
        self.rx_q = gr.msg_queue(100)
        self.ui_in_q = gr.msg_queue(100)
        self.ui_out_q = gr.msg_queue(100)
        self.ui_timeout = 5.0
        self.ui_last_update = 0.0

        gr.top_block.__init__(self)
        self.device_id_by_name = {}

        if "audio" in config:
            self.configure_audio(config['audio'])

        if "metadata" in config:
            self.configure_metadata(config['metadata'])

        if "trunking" in config:
            self.configure_trunking(config['trunking'])

        self.configure_devices(config['devices'])
        self.configure_channels(config['channels'])

        if self.trunking is not None: # post-initialization after channels and devices created
            self.trunk_rx.post_init()

        if "terminal" in config:
            self.configure_terminal(config['terminal'])

    def set_debug(self, dbglvl):
        self.verbosity = dbglvl
        for ch in self.channels:
            ch.set_debug(dbglvl)
        for dev in self.devices:
            dev.set_debug(dbglvl)
        if self.trunking is not None and self.trunk_rx is not None:
            self.trunk_rx.set_debug(dbglvl)
        if self.metadata is not None:
            for stream in self.meta_streams:
                self.meta_streams[stream][0].set_debug(dbglvl)

    def set_interactive(self, session_type):
        self.interactive = session_type

    def get_interactive(self):
        return self.interactive

    def configure_audio(self, config):
        audio_mod = config['module']
        if audio_mod.endswith('.py'):
            audio_mod = audio_mod[:-3]
        try:
            self.audio = importlib.import_module(audio_mod)
        except:
            self.audio = None
            sys.stderr.write("Error: unable to import audio module: %s\n%s\n" % (config['module'], sys.exc_info()[1]))

        idx = 0
        for instance in config['instances']:
            if 'instance_name' in instance and instance['instance_name'] != "":
                instance_name = instance['instance_name']
                if instance_name in self.audio_instances:
                    sys.stderr.write("Ignoring duplicate audio instance #%d [%s]\n" % (idx, instance_name))
                    break
                audio_port = int(from_dict(instance,'udp_port', 23456))
                audio_device = str(from_dict(instance,'device_name', "default"))
                audio_gain = float(from_dict(instance,'audio_gain', "0.0"))
                audio_2chan = True if int(from_dict(instance,'number_channels', 1)) == 2 else False
                sys.stderr.write("Configuring audio instance #%d [%s]\n" % (idx, instance_name))
                try:
                    audio_s = self.audio.audio_thread("127.0.0.1", audio_port, audio_device, audio_2chan, audio_gain)
                    self.audio_instances[instance_name] = audio_s
                except:
                    sys.stderr.write("Error configuring audio instance #%d; %s\n" % (idx, sys.exc_info()[1]))
                    #sys.exc_clear()
                    self.audio_instances[instance_name] = None
            else:
                sys.stderr.write("Ignoring unnamed audio instance #%d\n" % idx)
            idx += 1

    def configure_terminal(self, config):
        term_mod = config['module']
        if term_mod.endswith('.py'):
            term_mod = term_mod[:-3]
        try:
            terminal = importlib.import_module(term_mod)
        except:
            terminal = None
            sys.stderr.write("Error: unable to import terminal module: %s\n%s\n" % (config['module'], sys.exc_info()[1]))
            return
        term_type = str(from_dict(config,'terminal_type', "curses"))
        self.terminal = terminal.op25_terminal(self.ui_in_q, self.ui_out_q, term_type)
        self.terminal_type = self.terminal.get_terminal_type()
        self.terminal_config = config
        self.curses_plot_interval = float(from_dict(config, 'curses_plot_interval', 0.0))
        self.http_plot_interval = float(from_dict(config, 'http_plot_interval', 1.0))
        self.http_plot_directory = str(from_dict(config, 'http_plot_directory', "../www/images"))
        self.ui_timeout = float(from_dict(config, 'terminal_timeout', 5.0))

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
            self.trunk_rx = self.trunking.rx_ctl(frequency_set = self.change_freq, nac_set = self.set_nac, slot_set = self.set_slot, nbfm_ctrl = self.nbfm_control, debug = self.verbosity, chans = config['chans'])
            self.du_watcher = du_queue_watcher(self.rx_q, self.trunk_rx.process_qmsg)
            sys.stderr.write("Enabled trunking module: %s\n" % config['module'])

    def configure_metadata(self, config):
        meta_mod = config['module']
        if meta_mod.endswith('.py'):
            meta_mod = meta_mod[:-3]
        try:
            self.metadata = importlib.import_module(meta_mod)
        except:
            self.metadata = None
            sys.stderr.write("Error: unable to import metadata module: %s\n%s\n" % (config['module'], sys.exc_info()[1]))

        idx = 0
        for stream in config['streams']:
            if 'stream_name' in stream and stream['stream_name'] != "":
                stream_name = stream['stream_name']
                if stream_name in self.meta_streams:
                    sys.stderr.write("Ignoring duplicate metadata stream #%d [%s]\n" % (idx, stream_name))
                    break
                try:
                    meta_q = gr.msg_queue(10)
                    meta_s = self.metadata.meta_server(meta_q, stream, debug=self.verbosity)
                    self.meta_streams[stream_name] = (meta_s, meta_q)
                    sys.stderr.write("Configuring metadata stream #%d [%s]: %s\n" % (idx, stream_name, stream['icecastServerAddress'] + "/" + stream['icecastMountpoint']))
                except:
                    sys.stderr.write("Error configuring metadata stream #%d; %s\n" % (idx, sys.exc_info()[1]))
                    #sys.exc_clear()
            else:
                sys.stderr.write("Ignoring unnamed metadata stream #%d\n" % idx)
            idx += 1

    def configure_devices(self, config):
        self.devices = []
        for cfg in config:
            self.device_id_by_name[cfg['name']] = len(self.devices)
            self.devices.append(device(cfg))

    def find_device(self, chan):
        if 'device' in chan and (chan['device'] != "") and (chan['device'] in self.device_id_by_name):
            dev_id = self.device_id_by_name[chan['device']]
            if dev_id < len(self.devices):
                return self.devices[dev_id]
            
        if 'frequency' in chan and (chan['frequency'] != ""):
            for dev in self.devices:
                d = abs(chan['frequency'] - dev.frequency)
                nf = dev.sample_rate / 2
                if d + 6250 <= nf:
                    return dev
        return None

    def find_channel(self, msgq_id):
        return self.channels[msgq_id]

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
            meta_s, meta_q = None, None
            if self.metadata is not None and 'meta_stream_name' in cfg and cfg['meta_stream_name'] != "" and cfg['meta_stream_name'] in self.meta_streams:
                meta_s, meta_q = self.meta_streams[cfg['meta_stream_name']]
            if self.trunking is not None:
                msgq_id = len(self.channels)
                chan = channel(cfg, dev, self.verbosity, msgq_id, self.rx_q, self)
                self.channels.append(chan)
                self.trunk_rx.add_receiver(msgq_id, config=cfg, meta_q=meta_q, freq=chan.frequency)
            else:
                msgq_id = -1 - len(self.channels)
                chan = channel(cfg, dev, self.verbosity, msgq_id, self.rx_q, self)
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
                self.set_interactive(False) # this is non-interactive 'replay' session 
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
        if 'sigtype' in params and params['sigtype'] == "P25": # P25 specific config
            chan.configure_p25_tdma(params)

        if not chan.set_freq(params['freq']):
            chan.set_slot(0)
            return False

        if 'slot' in params:
            chan.set_slot(params['slot'])

        if 'rate' in params:
            chan.set_rate(params['rate'])

        if 'chan' in params:
            self.trunk_rx.receivers[tuner].current_chan = params['chan']

        if 'state' in params:
            self.trunk_rx.receivers[tuner].current_state = params['state']

        if 'type' in params:
            self.trunk_rx.receivers[tuner].current_type = params['type']

        if 'time' in params:
            self.trunk_rx.receivers[tuner].tune_time = params['time']

        return True

    def set_nac(self, params):
        tuner = params['tuner']
        chan = self.channels[tuner]
        if 'nac' in params:
            chan.set_nac(params['nac'])

    def set_slot(self, params):
        tuner = params['tuner']
        chan = self.channels[tuner]
        if 'slot' in params:
            chan.set_slot(params['slot'])

    def nbfm_control(self, msgq_id, action):
        if (msgq_id >= 0 and msgq_id < len(self.channels)) and self.channels[msgq_id].nbfm is not None:
            self.channels[msgq_id].nbfm.control(action)

    def process_qmsg(self, msg):            # Handle UI requests
        RX_COMMANDS = 'skip lockout hold whitelist reload'.split()
        if msg is None:
            return True
        s = msg.to_string()
        if type(s) is not str and isinstance(s, bytes):
            # should only get here if python3
            s = s.decode()
        if s == 'quit':
            return True
        elif s == 'update':                 # UI initiated update request
            self.ui_last_update = time.time()
            self.ui_freq_update()
            if self.trunking is None or self.trunk_rx is None:
                return False
            js = self.trunk_rx.to_json()    # extract data from trunking module
            msg = gr.message().make_from_string(js, -4, 0, 0)
            self.ui_in_q.insert_tail(msg)   # send info back to UI
            self.ui_plot_update()
        elif s == 'toggle_plot':
            if not self.get_interactive():
                sys.stderr.write("%s Cannot start plots for non-realtime (replay) sessions\n" % log_ts.get())
                return
            plot_type = int(msg.arg1())
            msgq_id = int(msg.arg2())
            self.find_channel(msgq_id).toggle_plot(plot_type)
        elif s == 'adj_tune':
            freq = msg.arg1()
            msgq_id = int(msg.arg2())
            self.find_channel(msgq_id).adj_tune(freq)
        elif s == 'set_debug':
            dbglvl = int(msg.arg1())
            self.set_debug(dbglvl)
        elif s == 'get_terminal_config':
            if self.terminal is not None and self.terminal_config is not None:
                self.terminal_config['json_type'] = "terminal_config"
                js = json.dumps(self.terminal_config)
                msg = gr.message().make_from_string(js, -4, 0, 0)
                self.ui_in_q.insert_tail(msg)
            else:
                return False
        elif s == 'get_full_config':
            cfg = self.config
            cfg['json_type'] = "full_config"
            js = json.dumps(cfg)
            msg = gr.message().make_from_string(js, -4, 0, 0)
            self.ui_in_q.insert_tail(msg)
        elif s == 'set_full_config':
            pass
        elif s == 'dump_tgids':
            self.trunk_rx.dump_tgids()
        elif s == 'dump_tracking':
            msgq_id = int(msg.arg2())
            self.channels[msgq_id].dump_tracking()
        elif s == 'set_tracking':
            tracking = msg.arg1()
            msgq_id = int(msg.arg2())
            self.find_channel(msgq_id).set_tracking(tracking)
        elif s == 'capture':
            if not self.get_interactive():
                sys.stderr.write("%s Cannot start capture for non-realtime (replay) sessions\n" % log_ts.get())
                return
            msgq_id = int(msg.arg2())
            self.find_channel(msgq_id).toggle_capture()
        elif s == 'watchdog':
            if self.ui_last_update > 0 and (time.time() > (self.ui_last_update + self.ui_timeout)):
                self.ui_last_update = 0
                sys.stderr.write("%s UI Timeout\n" % log_ts.get())
                for chan in self.channels:
                    chan.close_plots()
            # Experimental automatic fine tuning 
            # TODO: find a better way to invoke
            for chan in self.channels:
                chan.error_tracking()
        elif s in RX_COMMANDS:
            if self.trunking is not None and self.trunk_rx is not None:
                self.trunk_rx.ui_command(s, msg.arg1(), msg.arg2())
        return False

    def ui_freq_update(self):
        if self.trunking is None or self.trunk_rx is None:
            return False
        params = json.loads(self.trunk_rx.get_chan_status())   # extract data from all channels
        for rx_id in params['channels']:                       # iterate and convert stream name to url
            params[rx_id]['ppm'] = self.find_channel(int(rx_id)).device.get_ppm()
            params[rx_id]['capture'] = False if self.find_channel(int(rx_id)).raw_sink is None else True
            params[rx_id]['error'] = self.find_channel(int(rx_id)).get_error() if self.find_channel(int(rx_id)).auto_tracking else None
            params[rx_id]['auto_tracking'] = self.find_channel(int(rx_id)).get_auto_tracking()
            params[rx_id]['tracking'] = self.find_channel(int(rx_id)).get_tracking()
            s_name = params[rx_id]['stream']
            if s_name not in self.meta_streams:
                continue
            meta_s, meta_q = self.meta_streams[s_name]
            params[rx_id]['stream_url'] = meta_s.get_url()
        js = json.dumps(params)
        msg = gr.message().make_from_string(js, -4, 0, 0)
        self.ui_in_q.insert_tail(msg)

    def ui_plot_update(self):
        if self.terminal_type is None or self.terminal_type != "http":
            return

        filenames = []
        for chan in self.channels:
            for sink in chan.sinks:
                if chan.sinks[sink][0].gnuplot.filename is not None:
                    filenames.append(chan.sinks[sink][0].gnuplot.filename)
        d = {'json_type': 'rx_update', 'files': filenames}
        msg = gr.message().make_from_string(json.dumps(d), -4, 0, 0)
        self.ui_in_q.insert_tail(msg)

    def kill(self):
        for chan in self.channels:
            chan.kill()

        for instance in self.audio_instances:
            if self.audio_instances[instance] is not None:
                self.audio_instances[instance].stop()

        for meta_s in self.meta_streams:
            if self.meta_streams[meta_s] is not None:
                self.meta_streams[meta_s][0].stop()

        if self.terminal is not None:
            self.terminal.end_terminal()

    def stop(self):
        self.kill()
        gr.top_block.stop(self)

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
        try:
            while(self.keep_running):
                msg = self.msgq.delete_head()
                if msg is not None:
                    self.callback(msg)
                else:
                    self.keep_running = False
        except KeyboardInterrupt:
            self.keep_running = False

    def kill(self):
        self.keep_running = False

class rx_main(object):
    def __init__(self):
        def byteify(input):    # thx so
            if sys.version[0] != '2':
                return input
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
            if sys.version[0] > '2':
                input("Press 'Enter' to continue...")
            else:
                raw_input("Press 'Enter' to continue...")

        if options.config_file == '-':
            config = json.loads(sys.stdin.read())
        else:
            if options.config_file is None:
                parser.print_help()
                exit(1)
            config = json.loads(open(options.config_file).read())
        self.tb = rx_block(options.verbosity, config = byteify(config))
        self.q_watcher = du_queue_watcher(self.tb.ui_out_q, self.process_qmsg)
        sys.stderr.write('python version detected: %s\n' % sys.version)

    def process_qmsg(self, msg):
        if msg is None or self.tb.process_qmsg(msg):
            self.tb.stop()
            self.keep_running = False

    def run(self):
        try:
            self.tb.start()
            if self.tb.get_interactive():
                while self.keep_running:
                    time.sleep(1.0)
                    msg = gr.message().make_from_string("watchdog", -2, 0, 0)
                    self.tb.ui_out_q.insert_tail(msg)
            else:
                self.tb.wait() # curiously wait() matures when a flowgraph gets locked
            sys.stderr.write('Flowgraph complete. Exiting\n')
        except (KeyboardInterrupt):
            self.tb.stop()
            self.tb.kill()
            self.keep_running = False
            sys.stderr.write("Ctrl-C detected\n")
        except:
            self.tb.stop()
            self.tb.kill()
            self.keep_running = False
            sys.stderr.write('main: exception occurred\n')
            sys.stderr.write('main: exception:\n%s\n' % traceback.format_exc())

if __name__ == "__main__":
    if sys.version[0] > '2':
        sys.stderr = io.TextIOWrapper(sys.stderr.detach().detach(), write_through=True) # disable stderr buffering
    rx = rx_main()
    rx.run()
