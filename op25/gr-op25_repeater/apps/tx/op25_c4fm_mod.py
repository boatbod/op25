#
# Copyright 2005,2006,2007 Free Software Foundation, Inc.
#
# OP25 4-Level Modulator Block
# Copyright 2009, 2014 Max H. Parke KA1RBI
#
# coeffs for shaping and cosine filters from Eric Ramsey thesis 
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

# default values (used in __init__ and add_options)
_def_output_sample_rate = 48000
_def_excess_bw = 0.2
_def_reverse = False
_def_verbose = False
_def_log = False

# /////////////////////////////////////////////////////////////////////////////
#                           modulator
# /////////////////////////////////////////////////////////////////////////////

class p25_mod_bf(gr.hier_block2):

    def __init__(self,
                 output_sample_rate=_def_output_sample_rate,
                 excess_bw=_def_excess_bw,
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
	@param excess_bw: Root-raised cosine filter excess bandwidth
	@type excess_bw: float
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
        self._excess_bw = excess_bw

        mod_map = [1.0/3.0, 1.0, -(1.0/3.0), -1.0]
        self.C2S = digital.chunks_to_symbols_bf(mod_map)
        if reverse:
            self.polarity = blocks.multiply_const_ff(-1)
        else:
            self.polarity = blocks.multiply_const_ff( 1)

        ntaps = 11 * self._interp_factor
        rrc_taps = filter.firdes.root_raised_cosine(
            self._interp_factor, # gain (since we're interpolating by sps)
            lcm,                      # sampling rate
            input_sample_rate,        # symbol rate
            self._excess_bw,          # excess bandwidth (roll-off factor)
            ntaps)

        # rrc_coeffs work slightly differently: each input sample
        # (from mod_map above) at 4800 rate, then 9 zeros are inserted
        # to bring to 48000 rate, then this filter is applied:
        # rrc_filter = gr.fir_filter_fff(1, rrc_coeffs)
        # FIXME: how to insert the 9 zero samples using gr ?
        # rrc_coeffs = [0, -0.003, -0.006, -0.009, -0.012, -0.014, -0.014, -0.013, -0.01, -0.006, 0, 0.007, 0.014, 0.02, 0.026, 0.029, 0.029, 0.027, 0.021, 0.012, 0, -0.013, -0.027, -0.039, -0.049, -0.054, -0.055, -0.049, -0.038, -0.021, 0, 0.024, 0.048, 0.071, 0.088, 0.098, 0.099, 0.09, 0.07, 0.039, 0, -0.045, -0.091, -0.134, -0.17, -0.193, -0.199, -0.184, -0.147, -0.085, 0, 0.105, 0.227, 0.36, 0.496, 0.629, 0.751, 0.854, 0.933, 0.983, 1, 0.983, 0.933, 0.854, 0.751, 0.629, 0.496, 0.36, 0.227, 0.105, 0, -0.085, -0.147, -0.184, -0.199, -0.193, -0.17, -0.134, -0.091, -0.045, 0, 0.039, 0.07, 0.09, 0.099, 0.098, 0.088, 0.071, 0.048, 0.024, 0, -0.021, -0.038, -0.049, -0.055, -0.054, -0.049, -0.039, -0.027, -0.013, 0, 0.012, 0.021, 0.027, 0.029, 0.029, 0.026, 0.02, 0.014, 0.007, 0, -0.006, -0.01, -0.013, -0.014, -0.014, -0.012, -0.009, -0.006, -0.003, 0]

        self.rrc_filter = filter.interp_fir_filter_fff(self._interp_factor, rrc_taps)


        # FM pre-emphasis filter
        shaping_coeffs = [-0.018, 0.0347, 0.0164, -0.0064, -0.0344, -0.0522, -0.0398, 0.0099, 0.0798, 0.1311, 0.121, 0.0322, -0.113, -0.2499, -0.3007, -0.2137, -0.0043, 0.2825, 0.514, 0.604, 0.514, 0.2825, -0.0043, -0.2137, -0.3007, -0.2499, -0.113, 0.0322, 0.121, 0.1311, 0.0798, 0.0099, -0.0398, -0.0522, -0.0344, -0.0064, 0.0164, 0.0347, -0.018]
        self.shaping_filter = filter.fir_filter_fff(1, shaping_coeffs)

        if verbose:
            self._print_verbage()
        
        if log:
            self._setup_logging()

        self.connect(self, self.C2S, self.polarity, self.rrc_filter, self.shaping_filter)
        if (self._decimation > 1):
            self.decimator = filter.rational_resampler_fff(1, self._decimation)
            self.connect(self.shaping_filter, self.decimator, self)
        else:
            self.connect(self.shaping_filter, self)

    def _print_verbage(self):
        print "\nModulator:"
        print "RRS roll-off factor: %f" % self._excess_bw
        print "interpolation: %d decimation: %d" %(self._interp_factor, self._decimation)

    def _setup_logging(self):
        print "Modulation logging turned on."
        self.connect(self.C2S,
                     gr.file_sink(gr.sizeof_float, "tx_chunks2symbols.dat"))
        self.connect(self.polarity,
                     gr.file_sink(gr.sizeof_float, "tx_polarity.dat"))
        self.connect(self.rrc_filter,
                     gr.file_sink(gr.sizeof_float, "tx_rrc_filter.dat"))
        self.connect(self.shaping_filter,
                     gr.file_sink(gr.sizeof_float, "tx_shaping_filter.dat"))
        if (self._decimation > 1):
            self.connect(self.decimator,
                     gr.file_sink(gr.sizeof_float, "tx_decimator.dat"))

    def add_options(parser):
        """
        Adds QPSK modulation-specific options to the standard parser
        """
        parser.add_option("", "--excess-bw", type="float", default=_def_excess_bw,
                          help="set RRC excess bandwith factor [default=%default] (PSK)")
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
