#
# Copyright 2005,2006,2007 Free Software Foundation, Inc.
#
# OP25 Demodulator Block
# Copyright 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020 Max H. Parke KA1RBI
#
# Copyright 2020 Graham J. Norbury - gnorbury@bondcar.com
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
import pmt
import op25
import op25_repeater
import rms_agc
from math import pi

sys.path.append('tx')
import op25_c4fm_mod

# default values (used in __init__ and add_options)
_def_output_sample_rate = 48000
_def_if_rate = 24000
_def_gain_mu = 0.025
_def_costas_alpha = 0.008
_def_symbol_rate = 4800
_def_symbol_deviation = 600.0
_def_bb_gain = 1.0
_def_excess_bw = 0.2

_def_gmsk_mu = None
_def_mu = 0.5
_def_freq_error = 0.0
_def_omega_relative_limit = 0.005

TWO_PI = 2.0 * pi

# /////////////////////////////////////////////////////////////////////////////
#                           demodulator
# /////////////////////////////////////////////////////////////////////////////

def get_decim(speed):
    s = int(speed)
    if_freqs = [24000, 25000, 32000]
    for i_f in if_freqs:
        if s % i_f != 0:
            continue
        q = s // i_f
        if q & 1:
            continue
        if q >= 40 and q & 3 == 0:
            decim = q//4
            decim2 = 4
        else:
            decim = q//2
            decim2 = 2
        return decim, decim2
    return None

class p25_demod_base(gr.hier_block2):
    def __init__(self,
                 msgq_id = 0,
                 debug = 0,
                 if_rate     = None,
                 filter_type = None,
                 excess_bw   = _def_excess_bw,
                 symbol_rate = _def_symbol_rate):
        """
        Hierarchical block for P25 demodulation base class

        @param if_rate: sample rate of complex input channel
        @type if_rate: int
        """
        self.msgq_id = msgq_id
        self.debug = debug
        self.if_rate = if_rate
        self.symbol_rate = symbol_rate
        self.bb_sink = {}
        self.bb_tuner_sink = {}
        self.spiir = filter.single_pole_iir_filter_ff(0.0001)

        self.null_sink = blocks.null_sink(gr.sizeof_float)
        self.baseband_amp = blocks.multiply_const_ff(_def_bb_gain)
        coeffs = op25_c4fm_mod.c4fm_taps(sample_rate=self.if_rate, span=9, generator=op25_c4fm_mod.transfer_function_rx).generate()
        sps = self.if_rate // self.symbol_rate
        if filter_type == 'rrc':
            ntaps = 7 * sps
            if ntaps & 1 == 0:
                ntaps += 1
            coeffs = filter.firdes.root_raised_cosine(1.0, self.if_rate, self.symbol_rate, excess_bw, ntaps)
        if filter_type == 'nxdn':
            coeffs = op25_c4fm_mod.c4fm_taps(sample_rate=self.if_rate, span=9, generator=op25_c4fm_mod.transfer_function_nxdn, symbol_rate=self.symbol_rate).generate()
            gain_adj = 1.8	# for nxdn48 6.25 KHz
            if self.symbol_rate == 4800:
               gain_adj = 0.77	# nxdn96 12.5 KHz
            coeffs = [x * gain_adj for x in coeffs]
        if filter_type == 'gmsk':
            # lifted from gmsk.py
            _omega = sps
            _gain_mu = _def_gmsk_mu
            _mu = _def_mu
            if not _gain_mu:
                _gain_mu = 0.175
            _gain_omega = .25 * _gain_mu * _gain_mu        # critically damped
            self.symbol_filter = blocks.multiply_const_ff(1.0)
            self.fsk4_demod = digital.clock_recovery_mm_ff(_omega, _gain_omega,
                                                           _mu, _gain_mu,
                                                           _def_omega_relative_limit)
            self.slicer = digital.binary_slicer_fb()
        elif filter_type == 'fsk4mm':
            self.symbol_filter = filter.fir_filter_fff(1, coeffs)
            _omega = sps
            _gain_mu = _def_gmsk_mu
            _mu = _def_mu
            if not _gain_mu:
                _gain_mu = 0.0175
            _gain_omega = .25 * _gain_mu * _gain_mu        # critically damped
            self.fsk4_demod = digital.clock_recovery_mm_ff(_omega, _gain_omega,
                                                           _mu, _gain_mu,
                                                           _def_omega_relative_limit)
            levels = [ -2.0, 0.0, 2.0, 4.0 ]
            self.slicer = op25_repeater.fsk4_slicer_fb(self.msgq_id, self.debug, levels)
        elif filter_type == 'fsk2mm':
            ntaps = 7 * sps
            if ntaps & 1 == 0:
                ntaps += 1
            coeffs = filter.firdes.root_raised_cosine(1.0, self.if_rate, self.symbol_rate, excess_bw, ntaps)
            self.fsk4_demod = digital.clock_recovery_mm_ff(sps, 0.1, 0.5, 0.05, 0.005)
            self.baseband_amp = op25_repeater.rmsagc_ff(alpha=0.01, k=1.0)
            self.symbol_filter = filter.fir_filter_fff(1, coeffs)
            self.slicer = digital.binary_slicer_fb()
        elif filter_type == 'fsk2':
            ntaps = 7 * sps
            if ntaps & 1 == 0:
                ntaps += 1
            coeffs = filter.firdes.root_raised_cosine(1.0, self.if_rate, self.symbol_rate, excess_bw, ntaps)
            autotuneq = gr.msg_queue(2)
            self.fsk4_demod = op25.fsk4_demod_ff(autotuneq, self.if_rate, self.symbol_rate, True)
            self.baseband_amp = op25_repeater.rmsagc_ff(alpha=0.01, k=1.0)
            self.symbol_filter = filter.fir_filter_fff(1, coeffs)
            self.slicer = digital.binary_slicer_fb()
        elif filter_type == "widepulse":
            coeffs = op25_c4fm_mod.c4fm_taps(sample_rate=self.if_rate, span=9, generator=op25_c4fm_mod.transfer_function_rx).generate(rate_multiplier = 2.0)
            self.symbol_filter = filter.fir_filter_fff(1, coeffs)
            autotuneq = gr.msg_queue(2)
            self.fsk4_demod = op25.fsk4_demod_ff(autotuneq, self.if_rate, self.symbol_rate)
            levels = [ -2.0, 0.0, 2.0, 4.0 ]
            self.slicer = op25_repeater.fsk4_slicer_fb(self.msgq_id, self.debug, levels)
        else:
            self.symbol_filter = filter.fir_filter_fff(1, coeffs)
            autotuneq = gr.msg_queue(2)
            self.fsk4_demod = op25.fsk4_demod_ff(autotuneq, self.if_rate, self.symbol_rate)
            levels = [ -2.0, 0.0, 2.0, 4.0 ]
            self.slicer = op25_repeater.fsk4_slicer_fb(self.msgq_id, self.debug, levels)

    def set_debug(self, debug):
        if callable(getattr(self.slicer, 'set_debug', None)):
            self.slicer.set_debug(debug)

    def set_symbol_rate(self, rate):
        self.symbol_rate = rate
        if callable(getattr(self.fsk4_demod, 'set_rate', None)):       # op25.fsk4_demod_ff
            self.fsk4_demod.set_rate(self.if_rate, self.symbol_rate)
        elif callable(getattr(self.fsk4_demod, 'set_omega', None)):    # digital.clock_recovery_mm_ff
            self.fsk4_demod.set_omega(self.if_rate // self.symbol_rate)

    def set_baseband_gain(self, k):
        self.baseband_amp.set_k(k)

    def disconnect_bb(self, sink):
        # assumes lock held or init
        if sink not in self.bb_sink:
            return
        self.disconnect(self.bb_sink[sink], sink)
        self.bb_sink.pop(sink)

    def connect_bb(self, src, sink):
        # assumes lock held or init
        self.disconnect_bb(sink)
        if src == 'symbol_filter':
            self.connect(self.symbol_filter, sink)
            self.bb_sink[sink] = self.symbol_filter
        elif src == 'baseband_amp':
            self.connect(self.baseband_amp, sink)
            self.bb_sink[sink] = self.baseband_amp

    def disconnect_bb_tuner(self, sink):
        # assumes lock held or init
        if sink not in self.bb_tuner_sink:
            return
        self.disconnect(self.bb_tuner_sink[sink], self.spiir, sink)
        self.bb_tuner_sink.pop(sink)

    def connect_bb_tuner(self, src, sink):
        # assumes lock held or init
        self.disconnect_bb_tuner(sink)
        self.connect(self.symbol_filter, self.spiir, sink)
        self.bb_tuner_sink[sink] = self.symbol_filter

    def reset(self):
        pass

    def locked(self):
        return -1

    def quality(self):
        return 0

    def get_freq_error(self):
        return 0

class p25_demod_fb(p25_demod_base):

    def __init__(self,
                 msgq_id = 0,
                 debug = 0,
                 input_rate  = None,
                 filter_type = None,
                 excess_bw   = _def_excess_bw,
                 symbol_rate = _def_symbol_rate):
        """
        Hierarchical block for P25 demodulation.

        The float input is fsk4-demodulated
        @param input_rate: sample rate of complex input channel
        @type input_rate: int
        """
        self.msgq_id = msgq_id
        self.debug = debug
        sys.stderr.write("p25_demod_fb: input_rate=%d, symbol_rate=%d\n" % (input_rate, symbol_rate))
        gr.hier_block2.__init__(self, "p25_demod_fb",
                                gr.io_signature(1, 1, gr.sizeof_float), # Input signature
                                gr.io_signature(1, 1, gr.sizeof_char))  # Output signature

        p25_demod_base.__init__(self, msgq_id=msgq_id, debug=debug, if_rate=input_rate, symbol_rate=symbol_rate, filter_type=filter_type, excess_bw = excess_bw)

        self.input_rate = input_rate
        self.float_sink = {}

        self.connect(self, self.baseband_amp, self.symbol_filter, self.fsk4_demod, self.slicer, self)

    def disconnect_float(self, sink):
        # assumes lock held or init
        if sink not in self.float_sink:
            return
        self.disconnect(self.float_sink[sink], sink)
        self.float_sink.pop(sink)

    def connect_float(self, sink):
        # assumes lock held or init
        self.disconnect_float(sink)
        self.connect(self.fsk4_demod, sink)
        self.float_sink[sink] = self.fsk4_demod

    def connect_complex(self, src, sink):
        # stub to catch unsupported plot types
        return

    def disconnect_complex(self, sink):
        # stub to catch unsupported plot types
        return

    def connect_fm_demod(self):
        # stub to catch unsupported plot types
        return

    def disconnect_fm_demod(self):
        # stub to catch unsupported plot types
        return

    def set_omega(self, rate):
        self.set_symbol_rate(rate)
        try: # only supported by op25.fsk4_demod_ff()
            self.fsk4_demod.set_rate(self.if_rate, self.symbol_rate)
        except:
            pass

    def set_relative_frequency(self, freq):
        return True

class p25_demod_cb(p25_demod_base):

    def __init__(self,
                 msgq_id = 0,
                 debug = 0,
                 input_rate     = None,
                 demod_type     = 'cqpsk',
                 filter_type    = None,
                 usable_bw      = 1.0,
                 excess_bw      = _def_excess_bw,
                 relative_freq  = 0,
                 offset         = 0,
                 if_rate        = _def_if_rate,
                 gain_mu        = _def_gain_mu,
                 costas_alpha   = _def_costas_alpha,
                 symbol_rate    = _def_symbol_rate):
        """
        Hierarchical block for P25 demodulation.

        The complex input is tuned, decimated and demodulated
        @param input_rate: sample rate of complex input channel
        @type input_rate: int
        """
        self.msgq_id = msgq_id
        self.debug = debug
        gr.hier_block2.__init__(self, "p25_demod_cb",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex),  # Input signature
                                gr.io_signature(1, 1, gr.sizeof_char))        # Output signature
        p25_demod_base.__init__(self, msgq_id=msgq_id, debug=debug, if_rate=if_rate, symbol_rate=symbol_rate, filter_type=filter_type, excess_bw = excess_bw)

        self.usable_bw = usable_bw
        self.input_rate = input_rate
        self.if_rate = if_rate
        self.symbol_rate = symbol_rate
        self.connect_state = None
        self.aux_fm_connected = 0
        self.nbfm = None
        self.offset = 0
        self.sps = if_rate / float(symbol_rate)
        self.lo_freq = 0
        self.float_sink = {}
        self.complex_sink = {}
        self.if1 = 0
        self.if2 = 0
        self.t_cache = {}
        if filter_type == 'rrc':
            self.set_baseband_gain(0.61)
        elif filter_type == 'widepulse':
            self.set_baseband_gain(0.7)

        self.mixer = blocks.multiply_cc()
        decimator_values = get_decim(input_rate)
        if decimator_values:
            self.decim, self.decim2 = decimator_values
            self.if1 = input_rate / self.decim
            self.if2 = self.if1 / self.decim2
            sys.stderr.write( 'Using two-stage decimator for speed=%d, decim=%d/%d if1=%d if2=%d\n' % (input_rate, self.decim, self.decim2, self.if1, self.if2))
            bpf_coeffs = filter.firdes.complex_band_pass(1.0, input_rate, -self.if1/2, self.if1/2, self.if1/2, filter.firdes.WIN_HAMMING)
            self.t_cache[0] = bpf_coeffs
            fa = 6250
            fb = self.if2 / 2
            if filter_type == 'nxdn' and self.symbol_rate == 2400:	# nxdn48 6.25 KHz
                fa = 3125
            lpf_coeffs = filter.firdes.low_pass(1.0, self.if1, (fb+fa)/2, fb-fa, filter.firdes.WIN_HAMMING)
            self.bpf = filter.fir_filter_ccc(self.decim,  bpf_coeffs)
            self.lpf = filter.fir_filter_ccf(self.decim2, lpf_coeffs)
            resampled_rate = self.if2
            self.bfo = analog.sig_source_c (self.if1, analog.GR_SIN_WAVE, 0, 1.0, 0)
            self.connect(self, self.bpf, (self.mixer, 0))
            self.connect(self.bfo, (self.mixer, 1))
        else:
            sys.stderr.write( 'Unable to use two-stage decimator for speed=%d\n' % (input_rate))
            # local osc
            self.lo = analog.sig_source_c (input_rate, analog.GR_SIN_WAVE, 0, 1.0, 0)
            f1 = 7250
            f2 = 1450
            if filter_type == 'nxdn' and self.symbol_rate == 2400:	# nxdn48 6.25 KHz
                f1 = 3125
                f2 = 625
            lpf_coeffs = filter.firdes.low_pass(1.0, input_rate, f1, f2, filter.firdes.WIN_HANN)
            decimation = int(input_rate / if_rate)
            self.lpf = filter.fir_filter_ccf(decimation, lpf_coeffs)
            resampled_rate = float(input_rate) / float(decimation) # rate at output of self.lpf
            self.connect(self, (self.mixer, 0))
            self.connect(self.lo, (self.mixer, 1))
        self.connect(self.mixer, self.lpf)

        if self.if_rate != resampled_rate:
            self.if_out = filter.pfb.arb_resampler_ccf(float(self.if_rate) / resampled_rate)
            self.connect(self.lpf, self.if_out)
        else:
            self.if_out = self.lpf

        #fa = 7250
        #fb = fa + 1450
        fa = 6250
        fb = fa + 1250
        cutoff_coeffs = filter.firdes.low_pass(1.0, self.if_rate, (fb+fa)/2, fb-fa, filter.firdes.WIN_HANN)
        self.cutoff = filter.fir_filter_ccf(1, cutoff_coeffs)

        omega = float(self.if_rate) / float(self.symbol_rate)
        sps = self.if_rate // self.symbol_rate
        gain_omega = 0.1  * gain_mu * gain_mu

        self.agc = rms_agc.rms_agc(0.45, 0.85)
        self.fll = digital.fll_band_edge_cc(sps, excess_bw, 2*sps+1, TWO_PI/sps/250) # automatic frequency correction
        self.clock = op25_repeater.gardner_cc(omega, gain_mu, gain_omega)            # timing recovery
        self.costas = op25_repeater.costas_loop_cc(costas_alpha, 4, TWO_PI/4)        # phase stabilization, range-limited to +/-90deg

        # Perform Differential decoding on the constellation
        self.diffdec = digital.diff_phasor_cc()

        # take angle of the difference (in radians)
        self.to_float = blocks.complex_to_arg()

        # convert from radians such that signal is in -3/-1/+1/+3
        self.rescale = blocks.multiply_const_ff( (1 / (pi / 4)) )

        # fm demodulator (needed in fsk4 case)
        if filter_type is not None and filter_type[:4] == 'fsk2':
            fm_demod_gain = if_rate / (TWO_PI * 3600)
        else:
            fm_demod_gain = if_rate / (TWO_PI * _def_symbol_deviation)
        self.fm_demod = analog.quadrature_demod_cf(fm_demod_gain)

        self.connect_chain(demod_type)
        self.connect(self.slicer, self)

        self.set_relative_frequency(relative_freq)

    def locked(self):
        return 1 if self.clock.locked() else 0

    def quality(self):
        return self.clock.quality()

    def get_freq_error(self):   # get frequency error from FLL and convert to Hz
        return int((self.fll.get_frequency() / TWO_PI) * self.if_rate)

    def set_omega(self, rate):
        self.set_symbol_rate(rate)
        sps = self.if_rate / float(rate)
        if sps == self.sps:
            return
        self.sps = sps
        self.clock.set_omega(self.sps)
        self.fll.set_samples_per_symbol(sps)
        self.costas_reset()

    def reset(self):
        self.costas_reset()
        if callable(getattr(self.fsk4_demod, 'reset', None)):
            self.fsk4_demod.reset()

    def set_relative_frequency(self, freq):
        if abs(freq) > (((self.input_rate * self.usable_bw) / 2) - (self.if1 / 2)):
            return False
        if freq == self.lo_freq:
            return True
        self.lo_freq = freq
        if self.if1:
            if freq not in list(self.t_cache.keys()):
                self.t_cache[freq] = filter.firdes.complex_band_pass(1.0, self.input_rate, -freq - self.if1/2, -freq + self.if1/2, self.if1/2, filter.firdes.WIN_HAMMING)
            self.bpf.set_taps(self.t_cache[freq])
            bfo_f = self.decim * -freq / float(self.input_rate)
            bfo_f -= int(bfo_f)
            if bfo_f < -0.5:
                bfo_f += 1.0
            if bfo_f > 0.5:
                bfo_f -= 1.0
            self.bfo.set_frequency(-bfo_f * self.if1)
        else:
            self.lo.set_frequency(self.lo_freq)
        return True

    # assumes lock held or init
    def disconnect_chain(self):
        if self.nbfm is not None:
            self.disconnect(self.nbfm)
            self.nbfm = None
        if self.connect_state == 'cqpsk':
            self.disconnect_fm_demod()
            self.disconnect(self.if_out, self.cutoff, self.agc, self.fll, self.clock, self.diffdec, self.costas, self.to_float, self.rescale, self.slicer)
        elif self.connect_state == 'fsk4':
            self.disconnect(self.if_out, self.cutoff, self.fm_demod, self.baseband_amp, self.symbol_filter, self.fsk4_demod, self.slicer)
        self.connect_state = None

    # assumes lock held or init
    def connect_chain(self, demod_type):
        if self.connect_state == demod_type:
            return  # already in desired state
        self.disconnect_chain()
        self.connect_state = demod_type
        if demod_type == 'fsk4':
            self.connect(self.if_out, self.cutoff, self.agc, self.fll, self.fm_demod, self.baseband_amp, self.symbol_filter, self.fsk4_demod, self.slicer)
        elif demod_type == 'cqpsk':
            self.connect(self.if_out, self.cutoff, self.agc, self.fll, self.clock, self.diffdec, self.costas, self.to_float, self.rescale, self.slicer)
        else:
            sys.stderr.write("connect_chain failed, type: %s\n" % demod_type)
            assert 0 == 1

    # assumes lock held or init
    def connect_fm_demod(self):
        if self.connect_state != 'cqpsk':   # only valid for cqpsk demod type
            return
        if self.aux_fm_connected == 0:
            self.connect(self.fll, self.fm_demod, self.baseband_amp, self.symbol_filter, self.null_sink)
            #self.connect(self.agc, self.fm_demod, self.baseband_amp, self.symbol_filter, self.null_sink)
        self.aux_fm_connected += 1          # increment refcount

    # assumes lock held or init
    def disconnect_fm_demod(self):
        #if not self.aux_fm_connected or self.connect_state != 'cqpsk':  # only valid for cqpsk demod type
        if self.connect_state != 'cqpsk':  # only valid for cqpsk demod type
            return
        self.aux_fm_connected -= 1          # decrement refcount
        if self.aux_fm_connected == 0:
            self.disconnect(self.fll, self.fm_demod, self.baseband_amp, self.symbol_filter, self.null_sink)
            #self.disconnect(self.agc, self.fm_demod, self.baseband_amp, self.symbol_filter, self.null_sink)

    def disconnect_float(self, sink):
        # assumes lock held or init
        if sink not in self.float_sink:
            return
        self.disconnect(self.float_sink[sink], sink)
        self.float_sink.pop(sink)

    def connect_float(self, sink):
        # assumes lock held or init
        self.disconnect_float(sink)
        if self.connect_state == 'cqpsk':
            self.connect(self.rescale, sink)
            self.float_sink[sink] = self.rescale
        elif self.connect_state == 'fsk4':
            self.connect(self.fsk4_demod, sink)
            self.float_sink[sink] = self.fsk4_demod
        else:
            sys.stderr.write("connect_float: state error: %s\n" % self.connect_state)
            assert 0 == 1

    def disconnect_complex(self, sink):
        # assumes lock held or init
        if sink not in self.complex_sink:
            return
        self.disconnect(self.complex_sink[sink], sink)
        self.complex_sink.pop(sink)

    def connect_complex(self, src, sink):
        # assumes lock held or init
        self.disconnect_complex(sink)
        if src == 'clock':
            self.connect(self.clock, sink)
            self.complex_sink[sink] = self.clock
        elif src == 'diffdec':
            self.connect(self.diffdec, sink)
            self.complex_sink[sink] = self.diffdec
        elif src == 'costas':
            self.connect(self.costas, sink)
            self.complex_sink[sink] = self.costas
        elif src == 'mixer':
            self.connect(self.mixer, sink)
            self.complex_sink[sink] = self.mixer
        elif src == 'cutoff':
            self.connect(self.cutoff, sink)
            self.complex_sink[sink] = self.cutoff
        elif src == 'fll':
            self.connect(self.fll, sink)
            self.complex_sink[sink] = self.fll
        elif src == 'src':
            self.connect(self, sink)
            self.complex_sink[sink] = self
        elif src == 'bpf':
            self.connect(self.bpf, sink)
            self.complex_sink[sink] = self.bpf
        elif src == 'if_out':
            self.connect(self.if_out, sink)
            self.complex_sink[sink] = self.if_out
        elif src == 'agc':
            self.connect(self.agc, sink)
            self.complex_sink[sink] = self.agc

    def connect_nbfm(self, nbfm_blk):
        if self.connect_state == 'fsk4':
            self.nbfm = nbfm_blk
            self.connect(self.cutoff, nbfm_blk)
            return True
        else:
            return False

    def costas_reset(self):
        self.costas.set_frequency(0)
        self.costas.set_phase(0)
