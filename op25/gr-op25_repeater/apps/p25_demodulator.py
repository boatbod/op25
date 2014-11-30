#
# Copyright 2005,2006,2007 Free Software Foundation, Inc.
#
# OP25 Demodulator Block
# Copyright 2009, 2010, 2011, 2012, 2013, 2014 Max H. Parke KA1RBI
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
P25 C4FM/CQPSK demodulation block.
"""

from gnuradio import gr, gru, eng_notation
from gnuradio import filter, analog, digital, blocks
from gnuradio.eng_option import eng_option
import op25
import op25_repeater
from math import pi

# default values (used in __init__ and add_options)
_def_output_sample_rate = 48000
_def_excess_bw = 0.1
_def_if_rate = 24000
_def_gain_mu = 0.025
_def_costas_alpha = 0.04
_def_symbol_rate = 4800
_def_symbol_deviation = 600.0

# /////////////////////////////////////////////////////////////////////////////
#                           demodulator
# /////////////////////////////////////////////////////////////////////////////

class p25_demod_cb(gr.hier_block2):

    def __init__(self,
                 input_rate	= None,
                 demod_type	= 'cqpsk',
                 relative_freq	= 0,
                 offset		= 0,
                 if_rate	= _def_if_rate,
                 gain_mu	= _def_gain_mu,
                 costas_alpha	= _def_costas_alpha,
                 symbol_rate	= _def_symbol_rate):
        """
	Hierarchical block for P25 demodulation.

	The complex input is tuned, decimated and demodulated
        @param input_rate: sample rate of complex input channel
        @type input_rate: int
	"""

	gr.hier_block2.__init__(self, "p25_demod_c",
				gr.io_signature(1, 1, gr.sizeof_gr_complex),       # Input signature
				gr.io_signature(1, 1, gr.sizeof_char)) # Output signature
#				gr.io_signature(0, 0, 0)) # Output signature

        self.input_rate = input_rate
        self.if_rate = if_rate
        self.symbol_rate = symbol_rate
        self.connect_state = None
        self.offset = 0
        self.sps = 0.0
        self.lo_freq = 0

        # local osc
        self.lo = analog.sig_source_c (input_rate, analog.GR_SIN_WAVE, 0, 1.0, 0)
        self.mixer = blocks.multiply_cc()
        lpf_coeffs = filter.firdes.low_pass(1.0, input_rate, 15000, 1500, filter.firdes.WIN_HANN)
        decimation = int(input_rate / if_rate)
        self.lpf = filter.fir_filter_ccf(decimation, lpf_coeffs)

        resampled_rate = float(input_rate) / float(decimation) # rate at output of self.lpf

        self.arb_resampler = filter.pfb.arb_resampler_ccf(
           float(self.if_rate) / resampled_rate)

        self.connect(self, (self.mixer, 0))
        self.connect(self.lo, (self.mixer, 1))
        self.connect(self.mixer, self.lpf, self.arb_resampler)

        levels = [ -2.0, 0.0, 2.0, 4.0 ]
        self.slicer = op25_repeater.fsk4_slicer_fb(levels)

        fm_demod_gain = self.if_rate / (2.0 * pi * _def_symbol_deviation)
        self.fm_demod = analog.quadrature_demod_cf(fm_demod_gain)
        sps = int(self.if_rate // self.symbol_rate)
        symbol_decim = 1
        ntaps = 11 * sps
        rrc_coeffs = (1.0/sps,)*sps
        self.symbol_filter = filter.fir_filter_fff(symbol_decim, rrc_coeffs)
        autotuneq = gr.msg_queue(2)
        self.fsk4_demod = op25.fsk4_demod_ff(autotuneq, self.if_rate, self.symbol_rate)

        omega = float(self.if_rate) / float(self.symbol_rate)
        gain_omega = 0.1  * gain_mu * gain_mu

        alpha = costas_alpha
        beta = 0.125 * alpha * alpha
        fmax = 2400	# Hz
        fmax = 2*pi * fmax / float(self.if_rate)

        self.clock = op25_repeater.gardner_costas_cc(omega, gain_mu, gain_omega, alpha,  beta, fmax, -fmax)

        self.agc = analog.feedforward_agc_cc(16, 1.0)

        # Perform Differential decoding on the constellation
        self.diffdec = digital.diff_phasor_cc()

        # take angle of the difference (in radians)
        self.to_float = blocks.complex_to_arg()

        # convert from radians such that signal is in -3/-1/+1/+3
        self.rescale = blocks.multiply_const_ff( (1 / (pi / 4)) )

        self.connect_chain(demod_type)
        self.connect(self.slicer, self)

        self.set_relative_frequency(relative_freq)

    def set_omega(self, omega):
        sps = self.if_rate / float(omega)
        if sps == self.sps:
            return
        self.sps = sps
        print 'set_omega %d %f' % (omega, sps)
        self.clock.set_omega(self.sps)

    def set_relative_frequency(self, freq):
        if abs(freq) > self.input_rate/2:
            #print 'set_relative_frequency: error, relative frequency %d exceeds limit %d' % (freq, self.input_rate/2)
            return False
        if freq == self.lo_freq:
            return True
        #print 'set_relative_frequency', freq
        self.lo_freq = freq
        self.lo.set_frequency(self.lo_freq)
        return True

    def set_output(self, slot, filename):
        print 'set_output', slot, filename

    def release(self):
        print 'release'

    # assumes lock held or init
    def disconnect_chain(self):
        if self.connect_state == 'cqpsk':
            self.disconnect(self.arb_resampler, self.agc, self.clock, self.diffdec, self.to_float, self.rescale, self.slicer)
        elif self.connect_state == 'fsk4':
            self.disconnect(self.arb_resampler, self.fm_demod, self.symbol_filter, self.fsk4_demod, self.slicer)
        self.connect_state = None

    # assumes lock held or init
    def connect_chain(self, demod_type):
        if self.connect_state == demod_type:
            return	# already in desired state
        self.disconnect_chain()
        self.connect_state = demod_type
        if demod_type == 'fsk4':
            self.connect(self.arb_resampler, self.fm_demod, self.symbol_filter, self.fsk4_demod, self.slicer)
        elif demod_type == 'cqpsk':
            self.connect(self.arb_resampler, self.agc, self.clock, self.diffdec, self.to_float, self.rescale, self.slicer)
        else:
            print 'connect_chain failed, type: %s' % demod_type
