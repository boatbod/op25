#
# Copyright 2005,2006,2007 Free Software Foundation, Inc.
#
# OP25 4-Level Modulator Block
# Copyright 2009, 2010, 2011, 2012, 2013, 2014, 2015 Max H. Parke KA1RBI
#
# This file is part of GNU Radio and part of OP25
# 
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# It is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

"""
P25 C4FM pre-modulation block.
"""

from gnuradio import gr, gru, eng_notation
from gnuradio.digital import modulation_utils
from gnuradio import filter, digital, blocks
from gnuradio.eng_option import eng_option
from optparse import OptionParser
import math
from math import sin, cos, pi
import numpy as np

# default values (used in __init__ and add_options)
_def_output_sample_rate = 48000
_def_symbol_rate = 4800
_def_reverse = False
_def_verbose = False
_def_log = False
_def_span = 13  #desired number of impulse response coeffs, in units of symbols

def transfer_function_rx():
	# p25 c4fm de-emphasis filter
	# Specs undefined above 2,880 Hz.  It would be nice to have a sharper
	# rolloff, but this filter is cheap enough....
	xfer = []	# frequency domain transfer function
	for f in xrange(0,4800):
		# D(f)
		t = pi * f / 4800
		if t < 1e-6:
			df = 1.0
		else:
			df = sin (t) / t
		xfer.append(df)
	return xfer

def transfer_function_tx():
	xfer = []	# frequency domain transfer function
	for f in xrange(0, 2881):	# specs cover 0 - 2,880 Hz
		# H(f)
		if f < 1920:
			hf = 1.0
		else:
			hf = 0.5 + 0.5 * cos (2 * pi * float(f) / 1920.0)
		# P(f)
		t = pi * f / 4800.0
		if t < 1e-6:
			pf = 1
		else:
			pf = t / sin (t)
		# time domain convolution == frequency domain multiplication
		xfer.append(pf * hf)
	return xfer

class c4fm_taps(object):
	"""Generate filter coefficients as per P25 C4FM spec"""
	def __init__(self, filter_gain = 1.0, sample_rate=_def_output_sample_rate, symbol_rate=_def_symbol_rate, span=_def_span, generator=transfer_function_tx):
		self.sample_rate = sample_rate
		self.symbol_rate = symbol_rate
		self.filter_gain = filter_gain
		self.sps = int(sample_rate / symbol_rate)
		self.ntaps = (self.sps * span) | 1
		self.generator = generator

	def generate(self):
		impulse_response = np.fft.fftshift(np.fft.irfft(self.generator(), self.sample_rate))
		start = np.argmax(impulse_response) - (self.ntaps-1) / 2
		coeffs = impulse_response[start: start+self.ntaps]
		gain = self.filter_gain / sum(coeffs)
		return coeffs * gain

	def generate_code(self, varname='taps'):
		return '%s = [\n\t%s]' % (varname, ',\n\t'.join(['%10.6e' % f for f in self.generate()]))

# /////////////////////////////////////////////////////////////////////////////
#                           modulator
# /////////////////////////////////////////////////////////////////////////////

class p25_mod_bf(gr.hier_block2):

    def __init__(self,
                 output_sample_rate=_def_output_sample_rate,
                 reverse=_def_reverse,
                 verbose=_def_verbose,
                 log=_def_log):
        """
	Hierarchical block for RRC-filtered P25 FM modulation.

	The input is a dibit (P25 symbol) stream (char, not packed) and the
	output is the float "C4FM" signal at baseband, suitable for application
        to an FM modulator stage

        Input is at the base symbol rate (4800), output sample rate is
        typically either 32000 (USRP TX chain) or 48000 (sound card)

	@param output_sample_rate: output sample rate
	@type output_sample_rate: integer
        @param reverse: reverse polarity flag
        @type reverse: bool
        @param verbose: Print information about modulator?
        @type verbose: bool
        @param debug: Print modulation data to files?
        @type debug: bool
	"""

	gr.hier_block2.__init__(self, "p25_c4fm_mod_bf",
				gr.io_signature(1, 1, gr.sizeof_char),       # Input signature
				gr.io_signature(1, 1, gr.sizeof_float)) # Output signature

        input_sample_rate = 4800   # P25 baseband symbol rate
        lcm = gru.lcm(input_sample_rate, output_sample_rate)
        self._interp_factor = int(lcm // input_sample_rate)
        self._decimation = int(lcm // output_sample_rate)

        mod_map = [1.0/3.0, 1.0, -(1.0/3.0), -1.0]
        self.C2S = digital.chunks_to_symbols_bf(mod_map)
        if reverse:
            self.polarity = blocks.multiply_const_ff(-1)
        else:
            self.polarity = blocks.multiply_const_ff( 1)

        self.filter = filter.interp_fir_filter_fff(self._interp_factor, c4fm_taps(sample_rate=output_sample_rate).generate())

        if verbose:
            self._print_verbage()
        
        if log:
            self._setup_logging()

        self.connect(self, self.C2S, self.polarity, self.filter)
        if (self._decimation > 1):
            self.decimator = filter.rational_resampler_fff(1, self._decimation)
            self.connect(self.filter, self.decimator, self)
        else:
            self.connect(self.filter, self)

    def _print_verbage(self):
        print "\nModulator:"
        print "interpolation: %d decimation: %d" %(self._interp_factor, self._decimation)

    def _setup_logging(self):
        print "Modulation logging turned on."
        self.connect(self.C2S,
                     gr.file_sink(gr.sizeof_float, "tx_chunks2symbols.dat"))
        self.connect(self.polarity,
                     gr.file_sink(gr.sizeof_float, "tx_polarity.dat"))
        self.connect(self.filter,
                     gr.file_sink(gr.sizeof_float, "tx_filter.dat"))
        self.connect(self.shaping_filter,
                     gr.file_sink(gr.sizeof_float, "tx_shaping_filter.dat"))
        if (self._decimation > 1):
            self.connect(self.decimator,
                     gr.file_sink(gr.sizeof_float, "tx_decimator.dat"))

    def add_options(parser):
        """
        Adds QPSK modulation-specific options to the standard parser
        """
        add_options=staticmethod(add_options)


    def extract_kwargs_from_options(options):
        """
        Given command line options, create dictionary suitable for passing to __init__
        """
        return modulation_utils.extract_kwargs_from_options(dqpsk_mod.__init__,
                                                            ('self',), options)

    extract_kwargs_from_options=staticmethod(extract_kwargs_from_options)

#
# Add these to the mod/demod registry
#
modulation_utils.add_type_1_mod('op25_c4fm', p25_mod_bf)
