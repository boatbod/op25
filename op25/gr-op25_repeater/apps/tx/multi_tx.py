#!/usr/bin/env python

#################################################################################
# 
# Multiprotocol Digital Voice TX (C) Copyright 2017 Max H. Parke KA1RBI
# 
# This file is part of OP25
# 
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#################################################################################


"""
Transmit four simultaneous RF channels (dmr, p25, dstar, and ysf)
"""

import sys
import os
import math
from gnuradio import gr, gru, audio, eng_notation
from gnuradio import filter, blocks, analog, digital
from gnuradio.eng_option import eng_option
from optparse import OptionParser

import osmosdr
import op25
import op25_repeater

from math import pi

from op25_c4fm_mod import p25_mod_bf

class pipeline(gr.hier_block2):
    def __init__(self, protocol=None, config_file=None, mod_adjust=None, gain_adjust=None, output_gain=None, if_freq=0, if_rate=0, verbose=0, fullrate_mode=False, sample_rate=0, bt=0, alt_input=None):
        gr.hier_block2.__init__(self, "dv_modulator",
            gr.io_signature(1, 1, gr.sizeof_short),       # Input signature
            gr.io_signature(1, 1, gr.sizeof_gr_complex))  # Output signature

        from dv_tx import RC_FILTER
        if protocol == 'dmr':
            assert config_file
            ENCODER  = op25_repeater.ambe_encoder_sb(verbose)
            ENCODER2 = op25_repeater.ambe_encoder_sb(verbose)
            ENCODER2.set_gain_adjust(gain_adjust)
            DMR = op25_repeater.dmr_bs_tx_bb(verbose, config_file)
            self.connect(self, ENCODER, (DMR, 0))
            if not alt_input:
                alt_input = self
            self.connect(alt_input, ENCODER2, (DMR, 1))
        elif protocol == 'dstar':
            assert config_file
            ENCODER = op25_repeater.dstar_tx_sb(verbose, config_file)
        elif protocol == 'p25':
            ENCODER = op25_repeater.vocoder(True,		# 0=Decode,True=Encode
                                  False,	# Verbose flag
                                  0,	# flex amount
                                  "",			# udp ip address
                                  0,			# udp port
                                  False) 		# dump raw u vectors
        elif protocol == 'ysf':
            assert config_file
            ENCODER = op25_repeater.ysf_tx_sb(verbose, config_file, fullrate_mode)
        ENCODER.set_gain_adjust(gain_adjust)

        MOD = p25_mod_bf(output_sample_rate = sample_rate, dstar = (protocol == 'dstar'), bt = bt, rc = RC_FILTER[protocol])

        AMP = blocks.multiply_const_ff(output_gain)

        max_dev = 12.5e3
        k = 2 * math.pi * max_dev / if_rate

        FM_MOD = analog.frequency_modulator_fc (k * mod_adjust)

        if protocol == 'dmr':
            self.connect(DMR, MOD)
        else:
            self.connect(self, ENCODER, MOD)

        INTERP = filter.rational_resampler_fff(if_rate / sample_rate, 1)

        MIXER = blocks.multiply_cc()
        LO = analog.sig_source_c(if_rate, analog.GR_SIN_WAVE, if_freq, 1.0, 0)

        self.connect(MOD, AMP, INTERP, FM_MOD, (MIXER, 0))
        self.connect(LO, (MIXER, 1))
        self.connect(MIXER, self)

class my_top_block(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self)
        parser = OptionParser(option_class=eng_option)

        parser.add_option("-a", "--args", type="string", default="", help="device args")
        parser.add_option("-A", "--do-audio", action="store_true", default=False, help="live input audio")
        parser.add_option("-b", "--bt", type="float", default=0.5, help="specify bt value")
        parser.add_option("-f", "--file", type="string", default=None, help="specify the input file (mono 8000 sps S16_LE)")
        parser.add_option("-g", "--gain", type="float", default=1.0, help="input gain")
        parser.add_option("-i", "--if-rate", type="int", default=480000, help="output rate to sdr")
        parser.add_option("-I", "--audio-input", type="string", default="", help="pcm input device name.  E.g., hw:0,0 or /dev/dsp")
        parser.add_option("-N", "--gains", type="string", default=None, help="gain settings")
        parser.add_option("-o", "--if-offset", type="float", default=100000, help="channel spacing (Hz)")
        parser.add_option("-q", "--frequency-correction", type="float", default=0.0, help="ppm")
        parser.add_option("-Q", "--frequency", type="float", default=0.0, help="Hz")
        parser.add_option("-r", "--repeat", action="store_true", default=False, help="input file repeat")
        parser.add_option("-R", "--fullrate-mode", action="store_true", default=False, help="ysf fullrate")
        parser.add_option("-s", "--modulator-rate", type="int", default=48000, help="must be submultiple of IF rate")
        parser.add_option("-S", "--alsa-rate", type="int", default=48000, help="sound source/sink sample rate")
        parser.add_option("-v", "--verbose", type="int", default=0, help="additional output")
        (options, args) = parser.parse_args()

        assert options.file # input file name (-f filename) required

        f1 = float(options.if_rate) / options.modulator_rate
        i1 = int(options.if_rate / options.modulator_rate)
        if f1 - i1 > 1e-3:
            print '*** Error, sdr rate %d not an integer multiple of modulator rate %d - ratio=%f' % (options.if_rate, options.modulator_rate, f1)
            sys.exit(1)

        protocols = 'dmr p25 dstar ysf'.split()
        bw = options.if_offset * len(protocols) + 50000
        if bw > options.if_rate:
            print '*** Error, a %d Hz band is required for %d channels and guardband.' % (bw, len(protocols))
            print '*** Either reduce channel spacing using -o (current value is %d Hz),' % (options.if_offset) 
            print '*** or increase SDR output sample rate using -i (current rate is %d Hz)' % (options.if_rate) 
            sys.exit(1)

        max_inputs = 1

        from dv_tx import output_gains, gain_adjust, gain_adjust_fullrate, mod_adjust

        if options.do_audio:
            AUDIO = audio.source(options.alsa_rate, options.audio_input)
            lpf_taps = filter.firdes.low_pass(1.0, options.alsa_rate, 3400.0, 3400 * 0.1, filter.firdes.WIN_HANN)
            audio_rate = 8000
            AUDIO_DECIM = filter.fir_filter_fff (int(options.alsa_rate / audio_rate), lpf_taps)
            AUDIO_SCALE = blocks.multiply_const_ff(32767.0 * options.gain)
            AUDIO_F2S = blocks.float_to_short()
            self.connect(AUDIO, AUDIO_DECIM, AUDIO_SCALE, AUDIO_F2S)
            alt_input = AUDIO_F2S
        else:
            alt_input = None

        SUM = blocks.add_cc()
        input_repeat = True
        for i in xrange(len(protocols)):
            SOURCE = blocks.file_source(gr.sizeof_short, options.file, input_repeat)
            protocol = protocols[i]
            if (options.fullrate_mode and protocol == 'ysf') or protocol == 'p25':
                gain_adj = gain_adjust_fullrate[protocols[i]]
            else:
                gain_adj = gain_adjust[protocols[i]]
            if protocols[i] == 'dmr':
                cfg = 'dmr-cfg.dat'
            elif protocols[i] == 'ysf':
                cfg = 'ysf-cfg.dat'
            elif protocols[i] == 'dstar':
                cfg = 'dstar-cfg.dat'
            else:
                cfg = None

            CHANNEL = pipeline(
                protocol = protocols[i],
                output_gain = output_gains[protocols[i]],
                gain_adjust = gain_adj,
                mod_adjust = mod_adjust[protocols[i]],
                if_freq = (i - len(protocols)/2) * options.if_offset,
                if_rate = options.if_rate,
                sample_rate = options.modulator_rate,
                bt = options.bt,
                fullrate_mode = options.fullrate_mode,
                alt_input = alt_input,
                config_file = cfg)
            self.connect(SOURCE, CHANNEL, (SUM, i))

        self.u = osmosdr.sink (options.args)
        AMP = blocks.multiply_const_cc(1.0 / float(len(protocols)))
        self.setup_sdr_output(options)

        self.connect(SUM, AMP, self.u)

    def setup_sdr_output(self, options):
        gain_names = self.u.get_gain_names()
        for name in gain_names:
            range = self.u.get_gain_range(name)
            print "gain: name: %s range: start %d stop %d step %d" % (name, range[0].start(), range[0].stop(), range[0].step())
        if options.gains:
            for tuple in options.gains.split(","):
                name, gain = tuple.split(":")
                gain = int(gain)
                print "setting gain %s to %d" % (name, gain)
                self.u.set_gain(gain, name)

        print 'setting sample rate'
        self.u.set_sample_rate(options.if_rate)
        self.u.set_center_freq(options.frequency)
        self.u.set_freq_corr(options.frequency_correction)

if __name__ == "__main__":
    print 'Multiprotocol Digital Voice TX (C) Copyright 2017 Max H. Parke KA1RBI'
    try:
        my_top_block().run()
    except KeyboardInterrupt:
        tb.stop()
