#
# Copyright 2005,2006,2007 Free Software Foundation, Inc.
#
# OP25 Demodulator Block
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
P25 C4FM/CQPSK demodulation block.
"""

import sys
from gnuradio import gr, gru, eng_notation
from gnuradio import filter, analog, digital, blocks
from gnuradio.eng_option import eng_option
import op25
import op25_repeater
from math import pi

sys.path.append('tx')
import op25_c4fm_mod

# default values (used in __init__ and add_options)
_def_output_sample_rate = 48000
_def_if_rate = 24000
_def_gain_mu = 0.025
_def_costas_alpha = 0.04
_def_symbol_rate = 4800
_def_symbol_deviation = 600.0
_def_bb_gain = 1.0

# /////////////////////////////////////////////////////////////////////////////
#                           demodulator
# /////////////////////////////////////////////////////////////////////////////

class p25_demod_base(gr.hier_block2):
    def __init__(self,
                 if_rate	= None,
                 symbol_rate	= _def_symbol_rate):
        """
	Hierarchical block for P25 demodulation base class

        @param if_rate: sample rate of complex input channel
        @type if_rate: int
	"""
        self.if_rate = if_rate
        self.symbol_rate = symbol_rate
        self.bb_sink = None

        self.baseband_amp = blocks.multiply_const_ff(_def_bb_gain)
        coeffs = op25_c4fm_mod.c4fm_taps(sample_rate=self.if_rate, span=9, generator=op25_c4fm_mod.transfer_function_rx).generate()
        self.symbol_filter = filter.fir_filter_fff(1, coeffs)
        autotuneq = gr.msg_queue(2)
        self.fsk4_demod = op25.fsk4_demod_ff(autotuneq, self.if_rate, self.symbol_rate)

        levels = [ -2.0, 0.0, 2.0, 4.0 ]
        self.slicer = op25_repeater.fsk4_slicer_fb(levels)

    def set_baseband_gain(self, k):
        self.baseband_amp.set_k(k)

    def disconnect_bb(self):
        # assumes lock held or init
        if not self.bb_sink:
            return
        self.disconnect(self.bb_sink[0], self.bb_sink[1])
        self.bb_sink = None

    def connect_bb(self, src, sink):
        # assumes lock held or init
        self.disconnect_bb()
        if src == 'symbol_filter':
            self.connect(self.symbol_filter, sink)
            self.bb_sink = [self.symbol_filter, sink]
        elif src == 'baseband_amp':
            self.connect(self.baseband_amp, sink)
            self.bb_sink = [self.baseband_amp, sink]

class p25_demod_fb(p25_demod_base):

    def __init__(self,
                 input_rate	= None,
                 symbol_rate	= _def_symbol_rate):
        """
	Hierarchical block for P25 demodulation.

	The float input is fsk4-demodulated
        @param input_rate: sample rate of complex input channel
        @type input_rate: int
	"""

	gr.hier_block2.__init__(self, "p25_demod_fb",
				gr.io_signature(1, 1, gr.sizeof_float),       # Input signature
				gr.io_signature(1, 1, gr.sizeof_char)) # Output signature

        p25_demod_base.__init__(self, if_rate=input_rate, symbol_rate=symbol_rate)

        self.input_rate = input_rate
        self.float_sink = None

        self.connect(self, self.baseband_amp, self.symbol_filter, self.fsk4_demod, self.slicer, self)

    def disconnect_float(self):
        # assumes lock held or init
        if not self.float_sink:
            return
        self.disconnect(self.float_sink[0], self.float_sink[1])
        self.float_sink = None

    def connect_float(self, sink):
        # assumes lock held or init
        self.disconnect_float()
        self.connect(self.fsk4_demod, sink)
        self.float_sink = [self.fsk4_demod, sink]

class p25_demod_cb(p25_demod_base):

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

	gr.hier_block2.__init__(self, "p25_demod_cb",
				gr.io_signature(1, 1, gr.sizeof_gr_complex),       # Input signature
				gr.io_signature(1, 1, gr.sizeof_char)) # Output signature
#				gr.io_signature(0, 0, 0)) # Output signature
        p25_demod_base.__init__(self, if_rate=if_rate, symbol_rate=symbol_rate)

        self.input_rate = input_rate
        self.if_rate = if_rate
        self.symbol_rate = symbol_rate
        self.connect_state = None
        self.offset = 0
        self.sps = 0.0
        self.lo_freq = 0
        self.float_sink = None
        self.complex_sink = None

        # local osc
        self.lo = analog.sig_source_c (input_rate, analog.GR_SIN_WAVE, 0, 1.0, 0)
        self.mixer = blocks.multiply_cc()
        lpf_coeffs = filter.firdes.low_pass(1.0, input_rate, 7250, 725, filter.firdes.WIN_HANN)
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

        # fm demodulator (needed in fsk4 case)
        fm_demod_gain = if_rate / (2.0 * pi * _def_symbol_deviation)
        self.fm_demod = analog.quadrature_demod_cf(fm_demod_gain)

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

    # assumes lock held or init
    def disconnect_chain(self):
        if self.connect_state == 'cqpsk':
            self.disconnect(self.arb_resampler, self.agc, self.clock, self.diffdec, self.to_float, self.rescale, self.slicer)
        elif self.connect_state == 'fsk4':
            self.disconnect(self.arb_resampler, self.fm_demod, self.baseband_amp, self.symbol_filter, self.fsk4_demod, self.slicer)
        self.connect_state = None

    # assumes lock held or init
    def connect_chain(self, demod_type):
        if self.connect_state == demod_type:
            return	# already in desired state
        self.disconnect_chain()
        self.connect_state = demod_type
        if demod_type == 'fsk4':
            self.connect(self.arb_resampler, self.fm_demod, self.baseband_amp, self.symbol_filter, self.fsk4_demod, self.slicer)
        elif demod_type == 'cqpsk':
            self.connect(self.arb_resampler, self.agc, self.clock, self.diffdec, self.to_float, self.rescale, self.slicer)
        else:
            print 'connect_chain failed, type: %s' % demod_type
            assert 0 == 1
        if self.float_sink is not None:
            self.connect_float(self.float_sink[1])

    def disconnect_float(self):
        # assumes lock held or init
        if not self.float_sink:
            return
        self.disconnect(self.float_sink[0], self.float_sink[1])
        self.float_sink = None

    def connect_float(self, sink):
        # assumes lock held or init
        self.disconnect_float()
        if self.connect_state == 'cqpsk':
            self.connect(self.rescale, sink)
            self.float_sink = [self.rescale, sink]
        elif self.connect_state == 'fsk4':
            self.connect(self.fsk4_demod, sink)
            self.float_sink = [self.fsk4_demod, sink]
        else:
            print 'connect_float: state error', self.connect_state
            assert 0 == 1

    def disconnect_complex(self):
        # assumes lock held or init
        if not self.complex_sink:
            return
        self.disconnect(self.complex_sink[0], self.complex_sink[1])
        self.complex_sink = None

    def connect_complex(self, src, sink):
        # assumes lock held or init
        self.disconnect_complex()
        if src == 'clock':
            self.connect(self.clock, sink)
            self.complex_sink = [self.clock, sink]
        elif src == 'diffdec':
            self.connect(self.diffdec, sink)
            self.complex_sink = [self.diffdec, sink]
        elif src == 'mixer':
            self.connect(self.mixer, sink)
            self.complex_sink = [self.mixer, sink]
