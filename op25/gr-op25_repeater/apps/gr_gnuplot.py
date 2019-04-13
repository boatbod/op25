#!/usr/bin/env python

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

from gnuradio import gr, gru, eng_notation
from gnuradio import blocks, audio
from gnuradio.eng_option import eng_option
import numpy as np
from gnuradio import gr

_def_debug = 0
_def_sps = 5
_def_sps_mult = 2

GNUPLOT = '/usr/bin/gnuplot'

FFT_AVG  = 0.25
MIX_AVG  = 0.15
BAL_AVG  = 0.05
FFT_BINS = 512

class wrap_gp(object):
	def __init__(self, sps=_def_sps, plot_name=""):
		self.sps = sps
		self.center_freq = 0.0
		self.relative_freq = 0.0
		self.offset_freq = 0.0
		self.width = None
		self.ffts = ()
		self.freqs = ()
		self.avg_pwr = np.zeros(FFT_BINS)
		self.avg_sum_pwr = 0.0
		self.buf = []
		self.plot_count = 0
		self.last_plot = 0
		self.plot_interval = None
		self.sequence = 0
		self.output_dir = None
		self.filename = None
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
            self.sps = sps

	def kill(self):
		try:
			self.gp.stdin.close()   # closing pipe should cause subprocess to exit
		except IOError:
			pass
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
			self.buf.extend(buf[:consumed])
			return consumed

		self.plot_count += 1
		if mode == 'eye' and self.plot_count % 20 != 0:
			self.buf = []
			return consumed

		plots = []
		s = ''
		while(len(self.buf)):
			if mode == 'eye':
				if len(self.buf) < self.sps:
					break
				for i in range(self.sps):
					s += '%f\n' % self.buf[i]
				s += 'e\n'
				self.buf=self.buf[self.sps:]
				plots.append('"-" with lines')
			elif mode == 'constellation':
				for b in self.buf:
					s += '%f\t%f\n' % (b.real, b.imag)
				s += 'e\n'
				self.buf = []
				plots.append('"-" with points')
			elif mode == 'symbol':
				for b in self.buf:
					s += '%f\n' % (b)
				s += 'e\n'
				self.buf = []
				plots.append('"-" with points')
			elif mode == 'fft' or mode == 'mixer':
				sum_pwr = 0.0
				self.ffts = np.fft.fft(self.buf * np.blackman(BUFSZ)) / (0.42 * BUFSZ)
				self.ffts = np.fft.fftshift(self.ffts)
				self.freqs = np.fft.fftfreq(len(self.ffts))
				self.freqs = np.fft.fftshift(self.freqs)
				tune_freq = (self.center_freq - self.relative_freq) / 1e6
				if self.center_freq and self.width:
                                	self.freqs = ((self.freqs * self.width) + self.center_freq + self.offset_freq) / 1e6
				for i in xrange(len(self.ffts)):
					if mode == 'fft':
						self.avg_pwr[i] = ((1.0 - FFT_AVG) * self.avg_pwr[i]) + (FFT_AVG * np.abs(self.ffts[i]))
					else:
						self.avg_pwr[i] = ((1.0 - MIX_AVG) * self.avg_pwr[i]) + (MIX_AVG * np.abs(self.ffts[i]))
					s += '%f\t%f\n' % (self.freqs[i], 20 * np.log10(self.avg_pwr[i]))
					if (mode == 'mixer') and (self.avg_pwr[i] > 1e-5):
						if (self.freqs[i] - self.center_freq) < 0:
							sum_pwr -= self.avg_pwr[i]
						elif (self.freqs[i] - self.center_freq) > 0:
							sum_pwr += self.avg_pwr[i]
						self.avg_sum_pwr = ((1.0 - BAL_AVG) * self.avg_sum_pwr) + (BAL_AVG * sum_pwr)
				s += 'e\n'
				self.buf = []
				plots.append('"-" with lines')
		self.buf = []

		# FFT processing needs to be completed to maintain the weighted average buckets
		# regardless of whether we actually produce a new plot or not.
		if self.plot_interval and self.last_plot + self.plot_interval > time.time():
			return consumed
		self.last_plot = time.time()

		filename = None
		if self.output_dir:
			if self.sequence >= 2:
				delete_pathname = '%s/plot-%s-%d.png' % (self.output_dir, mode, self.sequence-2)
				if os.access(delete_pathname, os.W_OK):
					os.remove(delete_pathname)
			h= 'set terminal png\n'
			filename = 'plot-%s-%d.png' % (mode, self.sequence)
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
		elif mode == 'eye':
			h+= background
			h+= 'set yrange [-4:4]\n'
                        h+= 'set title "%sDatascope"\n' % self.plot_name
		elif mode == 'symbol':
			h+= background
			h+= 'set yrange [-4:4]\n'
                        h+= 'set title "%sSymbol"\n' % self.plot_name
		elif mode == 'fft' or mode == 'mixer':
			h+= 'unset arrow; unset title\n'
			h+= 'set xrange [%f:%f]\n' % (self.freqs[0], self.freqs[len(self.freqs)-1])
                        h+= 'set xlabel "Frequency"\n'
                        h+= 'set ylabel "Power(dB)"\n'
                        h+= 'set grid\n'
			h+= 'set yrange [-100:0]\n'
			if mode == 'mixer':	# mixer
                                h+= 'set title "%sMixer: balance %3.0f (smaller is better)"\n' % (self.plot_name, (np.abs(self.avg_sum_pwr * 1000)))
			else:			# fft
                                h+= 'set title "%sSpectrum"\n' % self.plot_name
				if self.center_freq:
					arrow_pos = (self.center_freq - self.relative_freq) / 1e6
					h+= 'set arrow from %f, graph 0 to %f, graph 1 nohead\n' % (arrow_pos, arrow_pos)
					h+= 'set title "%sSpectrum: tuned to %f Mhz"\n' % (self.plot_name, arrow_pos)
		dat = '%splot %s\n%s' % (h, ','.join(plots), s)
		self.gp.poll()
		if self.gp.returncode is None:	# make sure gnuplot is still running 
			try:
				self.gp.stdin.write(dat)
			except (IOError, ValueError):
				pass
		if filename:
			self.filename = filename
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
    def __init__(self, debug = _def_debug, sps = _def_sps, plot_name = ""):
        gr.sync_block.__init__(self,
            name="eye_sink_f",
            in_sig=[np.float32],
            out_sig=None)
        self.debug = debug
        self.sps = sps * _def_sps_mult
        self.gnuplot = wrap_gp(sps=self.sps, plot_name=plot_name)

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
    def __init__(self, debug = _def_debug, plot_name = ""):
        gr.sync_block.__init__(self,
            name="constellation_sink_c",
            in_sig=[np.complex64],
            out_sig=None)
        self.debug = debug
        self.gnuplot = wrap_gp(plot_name=plot_name)

    def work(self, input_items, output_items):
        in0 = input_items[0]
	self.gnuplot.plot(in0, 1000, mode='constellation')
        return len(input_items[0])

    def kill(self):
        self.gnuplot.kill()

class fft_sink_c(gr.sync_block):
    """
    """
    def __init__(self, debug = _def_debug, plot_name = ""):
        gr.sync_block.__init__(self,
            name="fft_sink_c",
            in_sig=[np.complex64],
            out_sig=None)
        self.debug = debug
        self.gnuplot = wrap_gp(plot_name=plot_name)
        self.skip = 0

    def work(self, input_items, output_items):
        self.skip += 1
        if self.skip == 50:
            self.skip = 0
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
    def __init__(self, debug = _def_debug, plot_name = ""):
        gr.sync_block.__init__(self,
            name="mixer_sink_c",
            in_sig=[np.complex64],
            out_sig=None)
        self.debug = debug
        self.gnuplot = wrap_gp(plot_name=plot_name)

    def work(self, input_items, output_items):
        in0 = input_items[0]
	self.gnuplot.plot(in0, FFT_BINS, mode='mixer')
        return len(input_items[0])

    def kill(self):
        self.gnuplot.kill()

class symbol_sink_f(gr.sync_block):
    """
    """
    def __init__(self, debug = _def_debug, plot_name = ""):
        gr.sync_block.__init__(self,
            name="symbol_sink_f",
            in_sig=[np.float32],
            out_sig=None)
        self.debug = debug
        self.gnuplot = wrap_gp(plot_name=plot_name)

    def work(self, input_items, output_items):
        in0 = input_items[0]
	self.gnuplot.plot(in0, 2400, mode='symbol')
        return len(input_items[0])

    def kill(self):
        self.gnuplot.kill()
