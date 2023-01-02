# Copyright 2011, 2012, 2013, 2014, 2015 Max H. Parke KA1RBI
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

import sys
import os
import time
import subprocess
import json

from gnuradio import gr, eng_notation
from gnuradio import blocks, audio
from gnuradio.eng_option import eng_option
import numpy as np
from gnuradio import gr

import gnuradio.op25_repeater as op25_repeater

_def_debug = 0
_def_sps = 5
_def_sps_mult = 2

GNUPLOT = '/usr/bin/gnuplot'

Y_AVG    = 0.03
FFT_AVG  = 0.05
MIX_AVG  = 0.10
BAL_AVG  = 0.05
FFT_BINS = 512    # number of fft bins
FFT_FREQ = 0.05   # time interval between fft updates
MIX_FREQ = 0.02   # time interval between mixer updates

class wrap_gp(object):
    def __init__(self, sps=_def_sps, plot_name="", chan = 0, out_q = None):
        self.sps = sps
        self.center_freq = 0.0
        self.relative_freq = 0.0
        self.offset_freq = 0.0
        self.width = None
        self.ffts = ()
        self.freqs = ()
        self.avg_pwr = np.zeros(FFT_BINS)
        self.min_y = -100.0
        self.buf = []
        self.plot_count = 0
        self.last_plot = 0
        self.plot_interval = None
        self.sequence = 0
        self.output_dir = None
        self.filename = None
        self.chan = chan
        self.out_q = out_q
        if plot_name == "":
            self.plot_name = ""
        else:
            self.plot_name = plot_name + " "

        self.attach_gp()

    def attach_gp(self):
        args = (GNUPLOT, '-noraise')
        exe  = GNUPLOT
        self.gp = subprocess.Popen(args, executable=exe, stdin=subprocess.PIPE)

    def set_sps(self, sps):
        self.sps = int(sps)

    def kill(self):
        try:
            self.gp.stdin.close()   # closing pipe should cause subprocess to exit
        except IOError:
            pass
        if self.out_q is not None:
            self.out_q.flush()
        self.out_q = None
        sleep_count = 0
        while True:                     # wait politely, but only for so long
            self.gp.poll()
            if self.gp.returncode is not None:
                break
            time.sleep(0.1)
            sleep_count += 1
            if (sleep_count % 5) == 0:
                self.gp.kill()

    def set_interval(self, v):
        self.plot_interval = v

    def set_output_dir(self, v):
        self.output_dir = v

    def plot(self, buf, bufsz, mode='eye'):
        BUFSZ = bufsz
        consumed = min(len(buf), BUFSZ-len(self.buf))
        if len(self.buf) < BUFSZ:
            self.buf = np.concatenate((self.buf, buf[:int(consumed)]))
        if len(self.buf) < BUFSZ:
            return consumed

        self.plot_count += 1
        if mode == 'eye' and self.plot_count % 20 != 0:
            self.buf = np.array([])
            return consumed

        plot_data = { "json_type": "plot", "chan": self.chan, "mode": mode, "data": [] }
        plots = []
        s = ''
        while(len(self.buf)):
            if mode == 'eye':
                if len(self.buf) < self.sps:
                    break
                for i in range(self.sps):
                    s += '%f\n' % self.buf[i]
                    plot_data['data'].append( (i, self.buf[i]) )
                s += 'e\n'
                self.buf=self.buf[self.sps:]
                plots.append('"-" with lines')
            elif mode == 'constellation':
                for b in self.buf:
                    s += '%f\t%f\n' % (b.real, b.imag)
                    plot_data['data'].append( (b.real, b.imag) )
                s += 'e\n'
                self.buf = []
                plots.append('"-" with points')
            elif mode == 'symbol':
                idx = 0
                for b in self.buf:
                    s += '%f\n' % (b)
                    plot_data['data'].append( (idx, b) )
                    idx += 1
                s += 'e\n'
                self.buf = []
                plots.append('"-" with points')
            elif mode == 'fft' or mode == 'mixer' or mode == 'fll':
                sum_pwr = 0.0
                self.ffts = np.fft.fft((self.buf * np.blackman(BUFSZ)), BUFSZ , 0) / (0.42 * BUFSZ)
                self.ffts = np.fft.fftshift(self.ffts)
                self.freqs = np.fft.fftfreq(len(self.ffts))
                self.freqs = np.fft.fftshift(self.freqs)
                tune_freq = (self.center_freq - self.relative_freq) / 1e6
                if self.center_freq and self.width:
                                    self.freqs = ((self.freqs * self.width) + self.center_freq + self.offset_freq) / 1e6
                elif self.width:
                                    self.freqs = (self.freqs * self.width)
                for i in range(len(self.ffts)):
                    if mode == 'fft':
                        self.avg_pwr[i] = ((1.0 - FFT_AVG) * self.avg_pwr[i]) + (FFT_AVG * np.abs(self.ffts[i]))
                    else:
                        self.avg_pwr[i] = ((1.0 - MIX_AVG) * self.avg_pwr[i]) + (MIX_AVG * np.abs(self.ffts[i]))
                    if self.avg_pwr[i] == 0: # guard against divide by zero
                        break
                    y_val = 20 * np.log10(self.avg_pwr[i])
                    s += '%f\t%f\n' % (self.freqs[i], y_val)
                    plot_data['data'].append( (self.freqs[i], y_val) )
                    if ((mode == 'mixer') or (mode == 'fll')) and (self.avg_pwr[i] > 1e-5):
                        if (self.freqs[i] - self.center_freq) < 0:
                            sum_pwr -= self.avg_pwr[i]
                        elif (self.freqs[i] - self.center_freq) > 0:
                            sum_pwr += self.avg_pwr[i]
                s += 'e\n'
                self.buf = []
                plots.append('"-" with lines')
                if min(self.avg_pwr) == 0: # plot is broken, probably because source device was missing
                    return
                min_y = 20 * np.log10(min(self.avg_pwr))
                self.min_y = ((1.0 - Y_AVG) * self.min_y) + (Y_AVG * min_y) 
        self.buf = []

        # FFT processing needs to be completed to maintain the weighted average buckets
        # regardless of whether we actually produce a new plot or not.
        if self.plot_interval and self.last_plot + self.plot_interval > time.time():
            return consumed
        self.last_plot = time.time()

        filename = None
        if self.output_dir:
            if self.sequence >= 2:
                delete_pathname = '%s/plot-%d-%s-%d.png' % (self.output_dir, self.chan, mode, self.sequence-2)
                if os.access(delete_pathname, os.W_OK):
                    os.remove(delete_pathname)
            h= 'set terminal png\n'
            filename = 'plot-%d-%s-%d.png' % (self.chan, mode, self.sequence)
            self.sequence += 1
            h += 'set output "%s/%s"\n' % (self.output_dir, filename)
        else:
            h= 'set terminal x11 noraise\n'

        #background = 'set object 1 circle at screen 0,0 size screen 1 fillcolor rgb"black"\n' #FIXME!
        background = ''
        h+= 'set key off\n'
        if mode == 'constellation':
            h+= background
            h+= 'set size square\n'
            h+= 'set xrange [-1:1]\n'
            h+= 'set yrange [-1:1]\n'
            h+= 'set title "%sConstellation"\n' % self.plot_name
            plot_data['xrange'] = (-1,1)
            plot_data['yrange'] = (-1,1)
            plot_data['title'] = "%sConstellation" % self.plot_name
        elif mode == 'eye':
            h+= background
            h+= 'set yrange [-4:4]\n'
            h+= 'set title "%sDatascope"\n' % self.plot_name
            plot_data['xrange'] = (0,len(plot_data['data']))
            plot_data['yrange'] = (-4,4)
            plot_data['title'] = "%sDatascope" % self.plot_name
        elif mode == 'symbol':
            h+= background
            h+= 'set yrange [-4:4]\n'
            h+= 'set title "%sSymbol"\n' % self.plot_name
            plot_data['xrange'] = (0,len(plot_data['data']))
            plot_data['yrange'] = (-4,4)
            plot_data['title'] = "%sSymbol" % self.plot_name
        elif mode == 'fft' or mode == 'mixer' or mode =='fll':
            h+= 'unset arrow; unset title\n'
            h+= 'set xrange [%f:%f]\n' % (self.freqs[0], self.freqs[len(self.freqs)-1])
            h+= 'set xlabel "Frequency"\n'
            h+= 'set ylabel "Power(dB)"\n'
            h+= 'set grid\n'
            h+= 'set yrange [%d:0]\n' % ((self.min_y // 20) * 20)
            plot_data['xrange'] = (self.freqs[0], self.freqs[len(self.freqs)-1])
            plot_data['yrange'] = (((self.min_y // 20) * 20), 0)
            if mode == 'mixer':
                h+= 'set title "%sRaw Mixer\n' % self.plot_name
                plot_data['title'] = "%sRaw Mixer" % self.plot_name
            elif mode == 'fll':
                h+= 'set title "%sTuned Mixer"\n' % self.plot_name
                plot_data['title'] = "%sTuned Mixer" % self.plot_name
            else:               # fft
                if self.center_freq:
                    arrow_pos = (self.center_freq - self.relative_freq) / 1e6
                    h+= 'set arrow from %f, graph 0 to %f, graph 1 nohead\n' % (arrow_pos, arrow_pos)
                    h+= 'set title "%sSpectrum: tuned to %f Mhz"\n' % (self.plot_name, arrow_pos)
                    plot_data['title'] = "%sSpectrum: tuned to %f Mhz" % (self.plot_name, arrow_pos)
                else:
                    h+= 'set title "%sSpectrum"\n' % self.plot_name
                    plot_data['title'] = "%sSpectrum" % self.plot_name
        dat = '%splot %s\n%s' % (h, ','.join(plots), s)
        if sys.version[0] != '2':
            dat = bytes(dat, 'utf8')
        self.gp.poll()
        if self.gp.returncode is None:  # make sure gnuplot is still running 
            try:
                self.gp.stdin.write(dat)
            except (IOError, ValueError):
                pass
        if filename:
            self.filename = filename

        if self.out_q is not None and not self.out_q.full_p():      # if configured, send raw plot data to UI
            msg = op25_repeater.message().make_from_string(json.dumps(plot_data), -4, 0, 0)
            self.out_q.insert_tail(msg)

        return consumed

    def set_center_freq(self, f):
        self.center_freq = f

    def set_relative_freq(self, f):
        self.relative_freq = f

    def set_offset(self, f):
        self.offset_freq = f

    def set_width(self, w):
        self.width = w

class eye_sink_f(gr.sync_block):
    """
    """
    def __init__(self, debug = _def_debug, sps = _def_sps, plot_name = "", chan = 0, out_q = None):
        gr.sync_block.__init__(self,
            name="eye_sink_f",
            in_sig=[np.float32],
            out_sig=None)
        self.debug = debug
        self.sps = sps * _def_sps_mult
        self.gnuplot = wrap_gp(sps=self.sps, plot_name=plot_name, chan=chan, out_q=out_q)

    def set_sps(self, sps):
        self.sps = sps * _def_sps_mult
        self.gnuplot.set_sps(self.sps)

    def work(self, input_items, output_items):
        in0 = input_items[0]
        consumed = self.gnuplot.plot(in0, 100 * self.sps, mode='eye')
        return consumed ### len(input_items[0])

    def kill(self):
        self.gnuplot.kill()

class constellation_sink_c(gr.sync_block):
    """
    """
    def __init__(self, debug = _def_debug, plot_name = "", chan = 0, out_q = None):
        gr.sync_block.__init__(self,
            name="constellation_sink_c",
            in_sig=[np.complex64],
            out_sig=None)
        self.debug = debug
        self.gnuplot = wrap_gp(plot_name=plot_name, chan=chan, out_q=out_q)

    def work(self, input_items, output_items):
        in0 = input_items[0]
        self.gnuplot.plot(in0, 1000, mode='constellation')
        return len(input_items[0])

    def kill(self):
        self.gnuplot.kill()

class fft_sink_c(gr.sync_block):
    """
    """
    def __init__(self, debug = _def_debug, plot_name = "", chan = 0, out_q = None):
        gr.sync_block.__init__(self,
            name="fft_sink_c",
            in_sig=[np.complex64],
            out_sig=None)
        self.debug = debug
        self.gnuplot = wrap_gp(plot_name=plot_name, chan=chan, out_q=out_q)
        self.next_due = time.time()

    def work(self, input_items, output_items):
        if time.time() > self.next_due:
            self.next_due = time.time() + FFT_FREQ
            in0 = input_items[0]
            self.gnuplot.plot(in0, FFT_BINS, mode='fft')
        return len(input_items[0])

    def kill(self):
        self.gnuplot.kill()

    def set_center_freq(self, f):
        self.gnuplot.set_center_freq(f)
        self.gnuplot.set_relative_freq(0.0)

    def set_relative_freq(self, f):
        self.gnuplot.set_relative_freq(f)

    def set_offset(self, f):
        self.gnuplot.set_offset(f)

    def set_width(self, w):
        self.gnuplot.set_width(w)

class mixer_sink_c(gr.sync_block):
    """
    """
    def __init__(self, debug = _def_debug, plot_name = "", chan = 0, out_q = None):
        gr.sync_block.__init__(self,
            name="mixer_sink_c",
            in_sig=[np.complex64],
            out_sig=None)
        self.debug = debug
        self.gnuplot = wrap_gp(plot_name=plot_name, chan=chan, out_q=out_q)
        self.next_due = time.time()

    def work(self, input_items, output_items):
        if time.time() > self.next_due:
            self.next_due = time.time() + MIX_FREQ
            in0 = input_items[0]
            self.gnuplot.plot(in0, FFT_BINS, mode='mixer')
        return len(input_items[0])

    def kill(self):
        self.gnuplot.kill()

    def set_width(self, w):
        self.gnuplot.set_width(w)

class fll_sink_c(gr.sync_block):
    """
    """
    def __init__(self, debug = _def_debug, plot_name = "", chan = 0, out_q = None):
        gr.sync_block.__init__(self,
            name="fll_sink_c",
            in_sig=[np.complex64],
            out_sig=None)
        self.debug = debug
        self.gnuplot = wrap_gp(plot_name=plot_name, chan=chan, out_q=out_q)
        self.next_due = time.time()

    def work(self, input_items, output_items):
        if time.time() > self.next_due:
            self.next_due = time.time() + MIX_FREQ
            in0 = input_items[0]
            self.gnuplot.plot(in0, FFT_BINS, mode='fll')
        return len(input_items[0])

    def kill(self):
        self.gnuplot.kill()

    def set_width(self, w):
        self.gnuplot.set_width(w)

class symbol_sink_f(gr.sync_block):
    """
    """
    def __init__(self, debug = _def_debug, plot_name = "", chan = 0, out_q = None):
        gr.sync_block.__init__(self,
            name="symbol_sink_f",
            in_sig=[np.float32],
            out_sig=None)
        self.debug = debug
        self.gnuplot = wrap_gp(plot_name=plot_name, chan=chan, out_q=out_q)

    def work(self, input_items, output_items):
        in0 = input_items[0]
        self.gnuplot.plot(in0, 2400, mode='symbol')
        return len(input_items[0])

    def kill(self):
        self.gnuplot.kill()
