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

import sys
import os
import math
from gnuradio import gr, gru, audio, eng_notation
from gnuradio import filter, blocks, analog, digital
from gnuradio.eng_option import eng_option
from optparse import OptionParser

import op25
import op25_repeater

from math import pi

from op25_c4fm_mod import p25_mod_bf

RC_FILTER = {'dmr': 'rrc', 'p25': 'rc', 'ysf': 'rrc', 'dstar': None}

output_gains = {
	'dmr': 5.5,
	'dstar': 0.95,
	'p25': 4.5,
	'ysf': 5.5
}
gain_adjust = {
	'dmr': 3.0,
	'dstar': 7.5,
	'ysf': 4.0
}
gain_adjust_fullrate = {
	'p25': 2.0,
	'ysf': 3.0
}
mod_adjust = {	# rough values
	'dmr': 0.35,
	'dstar': 0.075,
	'p25': 0.33,
	'ysf': 0.42
}

class my_top_block(gr.top_block):

    """
    Reads up to two channels of input and generates an output stream (in float format)

    Input may be either from sound card or from files.

    Likewise the output channel may be directed to an audio output or to a file.

    the output audio is suitable for direct application to an FM modulator
    """

    def __init__(self):
        global output_gains, gain_adjust, gain_adjust_fullrate, mod_adjust
        gr.top_block.__init__(self)
        parser = OptionParser(option_class=eng_option)

        parser.add_option("-a", "--args", type="string", default="", help="device args")
        parser.add_option("-A", "--alt-modulator-rate", type="int", default=50000, help="when mod rate is not a submutiple of IF rate")
        parser.add_option("-b", "--bt", type="float", default=0.5, help="specify bt value")
        parser.add_option("-c", "--config-file", type="string", default=None, help="specify the config file name")
        parser.add_option("-f", "--file1", type="string", default=None, help="specify the input file slot 1")
        parser.add_option("-F", "--file2", type="string", default=None, help="specify the input file slot 2 (DMR)")
        parser.add_option("-g", "--gain", type="float", default=1.0, help="input gain")
        parser.add_option("-i", "--if-rate", type="int", default=480000, help="output rate to sdr")
        parser.add_option("-I", "--audio-input", type="string", default="", help="pcm input device name.  E.g., hw:0,0 or /dev/dsp")
        parser.add_option("-k", "--symbol-sink", type="string", default=None, help="write symbols to file (optional)")
        parser.add_option("-N", "--gains", type="string", default=None, help="gain settings")
        parser.add_option("-O", "--audio-output", type="string", default="default", help="pcm output device name.  E.g., hw:0,0 or /dev/dsp")
        parser.add_option("-o", "--output-file", type="string", default=None, help="specify the output file")
        parser.add_option("-p", "--protocol", type="choice", default=None, choices=('dmr', 'dstar', 'p25', 'ysf'), help="specify protocol: dmr, dstar, p25, ysf")
        parser.add_option("-q", "--frequency-correction", type="float", default=0.0, help="ppm")
        parser.add_option("-Q", "--frequency", type="float", default=0.0, help="Hz")
        parser.add_option("-r", "--repeat", action="store_true", default=False, help="input file repeat")
        parser.add_option("-R", "--fullrate-mode", action="store_true", default=False, help="ysf fullrate")
        parser.add_option("-s", "--modulator-rate", type="int", default=48000, help="must be submultiple of IF rate - see also -A")
        parser.add_option("-S", "--alsa-rate", type="int", default=48000, help="sound source/sink sample rate")
        parser.add_option("-t", "--test", type="string", default=None, help="test pattern symbol file")
        parser.add_option("-v", "--verbose", type="int", default=0, help="additional output")
        (options, args) = parser.parse_args()

        max_inputs = 1

	if options.protocol is None:
            print 'protocol [-p] option missing'
            sys.exit(0)

        if options.protocol == 'ysf' or options.protocol == 'dmr' or options.protocol == 'dstar':
            assert options.config_file # dstar, dmr and ysf require config file ("-c FILENAME" option)

	output_gain = output_gains[options.protocol]

        if options.test: # input file is in symbols of size=char
            ENCODER = blocks.file_source(gr.sizeof_char, options.test, True)
        elif options.protocol == 'dmr':
            max_inputs = 2
            ENCODER  = op25_repeater.ambe_encoder_sb(options.verbose)
            ENCODER2 = op25_repeater.ambe_encoder_sb(options.verbose)
            ENCODER2.set_gain_adjust(gain_adjust['dmr'])
            DMR = op25_repeater.dmr_bs_tx_bb(options.verbose, options.config_file)
            self.connect(ENCODER, (DMR, 0))
            self.connect(ENCODER2, (DMR, 1))
        elif options.protocol == 'dstar':
            ENCODER = op25_repeater.dstar_tx_sb(options.verbose, options.config_file)
        elif options.protocol == 'p25':
            ENCODER = op25_repeater.vocoder(True,		# 0=Decode,True=Encode
                                  False,	# Verbose flag
                                  0,	# flex amount
                                  "",			# udp ip address
                                  0,			# udp port
                                  False) 		# dump raw u vectors
        elif options.protocol == 'ysf':
            ENCODER = op25_repeater.ysf_tx_sb(options.verbose, options.config_file, options.fullrate_mode)
            if options.fullrate_mode:
                ENCODER.set_gain_adjust(gain_adjust_fullrate['ysf'])
            else:
                ENCODER.set_gain_adjust(gain_adjust['ysf'])
        if options.protocol == 'p25' and not options.test:
            ENCODER.set_gain_adjust(gain_adjust_fullrate[options.protocol])
        elif not options.test and not options.protocol == 'ysf':
            ENCODER.set_gain_adjust(gain_adjust[options.protocol])
        nfiles = 0
        if options.file1:
            nfiles += 1
        if options.file2 and options.protocol == 'dmr':
            nfiles += 1
        if nfiles < max_inputs and not options.test:
            AUDIO = audio.source(options.alsa_rate, options.audio_input)
            lpf_taps = filter.firdes.low_pass(1.0, options.alsa_rate, 3400.0, 3400 * 0.1, filter.firdes.WIN_HANN)
            audio_rate = 8000
            AUDIO_DECIM = filter.fir_filter_fff (int(options.alsa_rate / audio_rate), lpf_taps)
            AUDIO_SCALE = blocks.multiply_const_ff(32767.0 * options.gain)
            AUDIO_F2S = blocks.float_to_short()
            self.connect(AUDIO, AUDIO_DECIM, AUDIO_SCALE, AUDIO_F2S)

        if options.file1: 
            IN1 = blocks.file_source(gr.sizeof_short, options.file1, options.repeat)
            S2F1 = blocks.short_to_float()
            AMP1 = blocks.multiply_const_ff(options.gain)
            F2S1 = blocks.float_to_short()
            self.connect(IN1, S2F1, AMP1, F2S1, ENCODER)
        elif not options.test:
            self.connect(AUDIO_F2S, ENCODER)

        if options.protocol == 'dmr':
            if options.file2:
                IN2 = blocks.file_source(gr.sizeof_short, options.file2, options.repeat)
                S2F2 = blocks.short_to_float()
                AMP2 = blocks.multiply_const_ff(options.gain)
                F2S2 = blocks.float_to_short()
                self.connect(IN2, S2F2, AMP2, F2S2, ENCODER2)
            else:
                self.connect(AUDIO_F2S, ENCODER2)

        MOD = p25_mod_bf(output_sample_rate = options.modulator_rate, dstar = (options.protocol == 'dstar'), bt = options.bt, rc = RC_FILTER[options.protocol])
        AMP = blocks.multiply_const_ff(output_gain)

        if options.output_file:
            OUT = blocks.file_sink(gr.sizeof_float, options.output_file)
        elif not options.args:
            OUT = audio.sink(options.alsa_rate, options.audio_output)

        if options.symbol_sink:
            SYMBOL_SINK = blocks.file_sink(gr.sizeof_char, options.symbol_sink)
        if options.protocol == 'dmr' and not options.test:
            self.connect(DMR, MOD)
            if options.symbol_sink:
                self.connect(DMR, SYMBOL_SINK)
        else:
            self.connect(ENCODER, MOD)
            if options.symbol_sink:
                self.connect(ENCODER, SYMBOL_SINK)

        if options.args:
            self.setup_sdr_output(options, mod_adjust[options.protocol])
            f1 = float(options.if_rate) / options.modulator_rate
            i1 = int(options.if_rate / options.modulator_rate)
            if f1 - i1 > 1e-3:
                f1 = float(options.if_rate) / options.alt_modulator_rate
                i1 = int(options.if_rate / options.alt_modulator_rate)
                if f1 - i1 > 1e-3:
                    print '*** Error, sdr rate %d not an integer multiple of alt modulator rate %d - ratio=%f' % (options.if_rate, options.alt_modulator_rate, f1)
                    sys.exit(0)
                a_resamp = filter.pfb.arb_resampler_fff(options.alt_modulator_rate / float(options.modulator_rate))
                sys.stderr.write('adding resampler for rate change %d ===> %d\n' % (options.modulator_rate, options.alt_modulator_rate))
                interp = filter.rational_resampler_fff(options.if_rate / options.alt_modulator_rate, 1)
                self.connect(MOD, AMP, a_resamp, interp, self.fm_modulator, self.u)
            else:
                interp = filter.rational_resampler_fff(options.if_rate / options.modulator_rate, 1)
                self.connect(MOD, AMP, interp, self.fm_modulator, self.u)
        else:
            self.connect(MOD, AMP, OUT)

    def setup_sdr_output(self, options, adjustment):
        import osmosdr
        max_dev = 12.5e3
        k = 2 * math.pi * max_dev / options.if_rate

        self.fm_modulator = analog.frequency_modulator_fc (k * adjustment)

        self.u = osmosdr.sink (options.args)
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

        self.u.set_sample_rate(options.if_rate)
        self.u.set_center_freq(options.frequency)
        self.u.set_freq_corr(options.frequency_correction)
        #self.u.set_bandwidth(options.if_rate)

if __name__ == "__main__":
    print 'Multiprotocol Digital Voice TX (C) Copyright 2017 Max H. Parke KA1RBI'
    try:
        my_top_block().run()
    except KeyboardInterrupt:
        tb.stop()
