#!/usr/bin/env python

#
# (C) Copyright 2010, 2014 Max H. Parke, KA1RBI
#
# apply CQPSK demodulator and P25 decoder to a sample capture file.
#
# input file is a sampled complex signal, default rate=96k
#
# Example usage:
# cqpsk-demod-file.py -i samples/trunk-control-complex-96KSS.dat -c 25300 -g 22
#
# FIXME: many of the blocks in this program should be moved to a hier block
#

import sys
import os
import math
from gnuradio import gr, gru, audio, eng_notation
from gnuradio import filter, blocks, analog, digital
from gnuradio.eng_option import eng_option
from optparse import OptionParser

import op25_repeater

from math import pi

class my_top_block(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self)
        parser = OptionParser(option_class=eng_option)

        parser.add_option("-1", "--one-channel", action="store_true", default=False, help="software synthesized Q channel")
        parser.add_option("-a", "--agc", action="store_true", default=False, help="automatic gain control (overrides --gain)")
        parser.add_option("-c", "--calibration", type="eng_float", default=0, help="freq offset")
        parser.add_option("-d", "--debug", action="store_true", default=False, help="allow time at init to attach gdb")
        parser.add_option("-C", "--costas-alpha", type="eng_float", default=0.125, help="Costas alpha")
        parser.add_option("-g", "--gain", type="eng_float", default=1.0)
        parser.add_option("-i", "--input-file", type="string", default="in.dat", help="specify the input file")
        parser.add_option("-I", "--imbe", action="store_true", default=False, help="output IMBE codewords")
        parser.add_option("-L", "--low-pass", type="eng_float", default=6.5e3, help="low pass cut-off", metavar="Hz")
        parser.add_option("-o", "--output-file", type="string", default="out.dat", help="specify the output file")
        parser.add_option("-p", "--polarity", action="store_true", default=False, help="use reversed polarity")
        parser.add_option("-r", "--raw-symbols", type="string", default=None, help="dump decoded symbols to file")
        parser.add_option("-s", "--sample-rate", type="int", default=96000, help="input sample rate")
        parser.add_option("-t", "--tone-detect", action="store_true", default=False, help="use experimental tone detect algorithm")
        parser.add_option("-v", "--verbose", action="store_true", default=False, help="additional output")
        parser.add_option("-6", "--k6k", action="store_true", default=False, help="use 6K symbol rate")
        (options, args) = parser.parse_args()
 
        sample_rate = options.sample_rate
        if options.k6k:
            symbol_rate = 6000
        else:
            symbol_rate = 4800
        samples_per_symbol = sample_rate // symbol_rate

        IN = blocks.file_source(gr.sizeof_gr_complex, options.input_file)

        if options.one_channel:
            C2F = blocks.complex_to_float()
            F2C = blocks.float_to_complex()

        # osc./mixer for mixing signal down to approx. zero IF
        LO = analog.sig_source_c (sample_rate, analog.GR_COS_WAVE, options.calibration, 1.0, 0)
        MIXER = blocks.multiply_cc()

        # get signal into normalized range (-1.0 - +1.0)
        if options.agc:
            AMP = analog.feedforward_agc_cc(16, 1.0)
        else:
            AMP = blocks.multiply_const_cc(options.gain)

        lpf_taps = filter.firdes.low_pass(1.0, sample_rate, options.low_pass, options.low_pass * 0.1, filter.firdes.WIN_HANN)

        decim_amt = 1
        if options.tone_detect:
            if sample_rate != 96000:
                print "warning, only 96K has been tested."
                print "other rates may require theta to be reviewed/adjusted."
            step_size = 7.5e-8
            theta = -4	# optimum timing sampling point
            cic_length = 48
            DEMOD = op25_repeater.tdetect_cc(samples_per_symbol, step_size, theta, cic_length)
        else:
            # decim by 2 to get 48k rate
            samples_per_symbol /= 2	# for DECIM
            sample_rate /= 2	# for DECIM
            decim_amt = 2
            # create Gardner/Costas loop
            # the loop will not work if the sample levels aren't normalized (above)
            timing_error_gain = 0.025   # loop error gain
            gain_omega = 0.25 * timing_error_gain * timing_error_gain
            alpha = options.costas_alpha
            beta = 0.125 * alpha * alpha
            fmin = -0.025   # fmin and fmax are in radians/s
            fmax =  0.025
            DEMOD = op25_repeater.gardner_costas_cc(samples_per_symbol, timing_error_gain, gain_omega, alpha, beta, fmax, fmin)
        DECIM = filter.fir_filter_ccf (decim_amt, lpf_taps)

        # probably too much phase noise etc to attempt coherent demodulation
        # so we use differential
        DIFF = digital.diff_phasor_cc()

        # take angle of the phase difference (in radians)
        TOFLOAT = blocks.complex_to_arg()

        # convert from radians such that signal is in [-3, -1, +1, +3]
        RESCALE = blocks.multiply_const_ff(1 / (pi / 4.0))

        # optional polarity reversal (should be unnec. - now autodetected)
        p = 1.0
        if options.polarity:
            p = -1.0
        POLARITY = blocks.multiply_const_ff(p)

        # hard decision at specified points
        levels = [-2.0, 0.0, 2.0, 4.0 ]
        SLICER = op25_repeater.fsk4_slicer_fb(levels)

        # assemble received frames and route to Wireshark via UDP
        hostname = "127.0.0.1"
        port = 23456
        debug = 0
	if options.verbose:
                debug = 255
        do_imbe = False
        if options.imbe:
                do_imbe = True
        do_output = True # enable block's output stream
        do_msgq = False  # msgq output not yet implemented
        msgq = gr.msg_queue(2)
        DECODER = op25_repeater.p25_frame_assembler(hostname, port, debug, do_imbe, do_output, do_msgq, msgq, False, False)

        OUT = blocks.file_sink(gr.sizeof_char, options.output_file)

        if options.one_channel:
            self.connect(IN, C2F, F2C, (MIXER, 0))
        else:
            self.connect(IN, (MIXER, 0))
        self.connect(LO, (MIXER, 1))
        self.connect(MIXER, AMP, DECIM, DEMOD, DIFF, TOFLOAT, RESCALE, POLARITY, SLICER, DECODER, OUT)

        if options.raw_symbols:
            SINKC = blocks.file_sink(gr.sizeof_char, options.raw_symbols)
            self.connect(SLICER, SINKC)

        if options.debug:
            print 'Ready for GDB to attach (pid = %d)' % (os.getpid(),)
            raw_input("Press 'Enter' to continue...")

if __name__ == "__main__":
    try:
        my_top_block().run()
    except KeyboardInterrupt:
        tb.stop()
