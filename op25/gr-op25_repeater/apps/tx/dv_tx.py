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

from op25_c4fm_mod import c4fm_taps, transfer_function_dmr, transfer_function_tx, p25_mod_bf

class my_top_block(gr.top_block):

    """
    Reads up to two channels of input and generates an output stream (in float format)

    Input may be either from sound card or from files.

    Likewise the output channel may be directed to an audio output or to a file.

    the output audio is suitable for direct application to an FM modulator
    """

    def __init__(self):
        gr.top_block.__init__(self)
        parser = OptionParser(option_class=eng_option)

        parser.add_option("-b", "--bt", type="float", default=0.25, help="specify bt value")
        parser.add_option("-c", "--config-file", type="string", default=None, help="specify the config file name")
        parser.add_option("-f", "--file1", type="string", default=None, help="specify the input file slot 1")
        parser.add_option("-F", "--file2", type="string", default=None, help="specify the input file slot 2 (DMR)")
        parser.add_option("-g", "--gain", type="float", default=1.0, help="input gain")
        parser.add_option("-I", "--audio-input", type="string", default="", help="pcm input device name.  E.g., hw:0,0 or /dev/dsp")
        parser.add_option("-O", "--audio-output", type="string", default="default", help="pcm output device name.  E.g., hw:0,0 or /dev/dsp")
        parser.add_option("-o", "--output-file", type="string", default=None, help="specify the output file")
        parser.add_option("-p", "--protocol", type="choice", default=None, choices=('dmr', 'dstar', 'p25', 'ysf'), help="specify protocol")
        parser.add_option("-r", "--repeat", action="store_true", default=False, help="input file repeat")
        parser.add_option("-R", "--fullrate-mode", action="store_true", default=False, help="ysf fullrate")
        parser.add_option("-s", "--sample-rate", type="int", default=48000, help="output sample rate")
        parser.add_option("-v", "--verbose", type="int", default=0, help="additional output")
        (options, args) = parser.parse_args()

        max_inputs = 1
        if options.protocol == 'dmr':
            max_inputs = 2
            ENCODER  = op25_repeater.ambe_encoder_sb(options.verbose)
            ENCODER2 = op25_repeater.ambe_encoder_sb(options.verbose)
            DMR = op25_repeater.dmr_bs_tx_bb(options.verbose, options.config_file)
            self.connect(ENCODER, (DMR, 0))
            self.connect(ENCODER2, (DMR, 1))
            output_gain = 5.5
            generator = transfer_function_dmr	# RRC
        elif options.protocol == 'dstar':
            ENCODER = op25_repeater.dstar_tx_sb(options.verbose, options.config_file)
            output_gain = 0.95
        elif options.protocol == 'p25':
            ENCODER = op25_repeater.vocoder(True,		# 0=Decode,True=Encode
                                  0,	# Verbose flag
                                  0,	# flex amount
                                  "",			# udp ip address
                                  0,			# udp port
                                  False) 		# dump raw u vectors
            output_gain = 5.5
            generator = transfer_function_tx	# RC+preemphasis
        elif options.protocol == 'ysf':
            ENCODER = op25_repeater.ysf_tx_sb(options.verbose, options.config_file, options.fullrate_mode)
            output_gain = 5.5
            generator = transfer_function_dmr	# RRC
	else:
            print 'protocol [-p] option missing'
            sys.exit(0)

        nfiles = 0
        if options.file1:
            nfiles += 1
        if options.file2 and options.protocol == 'dmr':
            nfiles += 1
        if nfiles < max_inputs:
            AUDIO = audio.source(options.sample_rate, options.audio_input)
            lpf_taps = filter.firdes.low_pass(1.0, options.sample_rate, 3400.0, 3400 * 0.1, filter.firdes.WIN_HANN)
            audio_rate = 8000
            AUDIO_DECIM = filter.fir_filter_fff (int(options.sample_rate / audio_rate), lpf_taps)
            AUDIO_SCALE = blocks.multiply_const_ff(32767.0 * options.gain)
            AUDIO_F2S = blocks.float_to_short()
            self.connect(AUDIO, AUDIO_DECIM, AUDIO_SCALE, AUDIO_F2S)

        if options.file1: 
            IN1 = blocks.file_source(gr.sizeof_short, options.file1, options.repeat)
            S2F1 = blocks.short_to_float()
            AMP1 = blocks.multiply_const_ff(options.gain)
            F2S1 = blocks.float_to_short()
            self.connect(IN1, S2F1, AMP1, F2S1, ENCODER)
        else:
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

        if options.protocol == 'dstar':
            MOD = p25_mod_bf(output_sample_rate = options.sample_rate, dstar = True, bt = options.bt)
        else:
            MOD = p25_mod_bf(output_sample_rate = options.sample_rate, generator=generator)
        AMP = blocks.multiply_const_ff(output_gain)

        if options.output_file:
            OUT = blocks.file_sink(gr.sizeof_float, options.output_file)
        else:
            OUT = audio.sink(options.sample_rate, options.audio_output)

        if options.protocol == 'dmr':
            self.connect(DMR, MOD)
        else:
            self.connect(ENCODER, MOD)

        self.connect(MOD, AMP, OUT)

if __name__ == "__main__":
    print 'Multiprotocol Digital Voice TX (C) Copyright 2017 Max H. Parke KA1RBI'
    try:
        my_top_block().run()
    except KeyboardInterrupt:
        tb.stop()
