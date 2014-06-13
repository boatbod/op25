#!/usr/bin/env python
#
# Copyright 2005,2006,2007 Free Software Foundation, Inc.
# 
# GNU Radio Multichannel APCO P25 Tx
# (c) Copyright 2009, 2014 Max H. Parke KA1RBI
# 
# This file is part of GNU Radio and part of OP25
# 
# This program is free software; you can redistribute it and/or modify
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
Transmit N simultaneous narrow band P25 C4FM signals.

They will be centered at the frequency specified on the command line,
and are spaced at 25kHz steps from there.

There are three main ways to run this program:
 A. Combined audio capture, speech coding, and USRP transmission [default]
 B. USRP transmission only, receives P25 symbol input via UDP channel [-p]
 C. USRP transmission only, P25 symbol input taken from file(s) [-i]

By using method B, the coding and transmission functions can be
split over separate machines.  Run the op25_remote_tx script prior to 
running this script when using method B.

"""

from gnuradio import gr, eng_notation, blocks, digital
from gnuradio import audio, filter, analog
from gnuradio.eng_option import eng_option
from optparse import OptionParser
from usrpm import usrp_dbid
import math
import sys
import osmosdr
import op25_repeater

from gnuradio.wxgui import stdgui2, fftsink2
import wx

import op25_c4fm_mod

########################################################
# instantiate one transmit chain for each call

class file_pipeline(gr.hier_block2):
    def __init__(self, lo_freq, if_rate, input_file):

        gr.hier_block2.__init__(self, "file_pipeline",
                                gr.io_signature(0, 0, 0),                    # Input signature
                                gr.io_signature(1, 1, gr.sizeof_gr_complex)) # Output signature

	fs = blocks.file_source(gr.sizeof_gr_complex, input_file, True)
        agc = analog.feedforward_agc_cc(160, 1.0)

        # Local oscillator
        lo = analog.sig_source_c (if_rate,        # sample rate
                              analog.GR_SIN_WAVE, # waveform type
                              lo_freq,        #frequency
                              1.0,            # amplitude
                              0)              # DC Offset
        mixer = blocks.multiply_cc ()

        self.connect (fs, agc, (mixer, 0))
        self.connect (lo, (mixer, 1))
        self.connect (mixer, self)

class pipeline(gr.hier_block2):
    def __init__(self, vocoder, lo_freq, audio_rate, if_rate):

        gr.hier_block2.__init__(self, "pipeline",
                                gr.io_signature(0, 0, 0),                    # Input signature
                                gr.io_signature(1, 1, gr.sizeof_gr_complex)) # Output signature

        c4fm = op25_c4fm_mod.p25_mod_bf(output_sample_rate=audio_rate,
                                 log=False,
                                 verbose=True)
        interp_factor = if_rate / audio_rate

        low_pass = 2.88e3
        interp_taps = filter.firdes.low_pass(1.0, if_rate, low_pass, low_pass * 0.1, filter.firdes.WIN_HANN)

        interpolator = filter.interp_fir_filter_fff (int(interp_factor), interp_taps)

        max_dev = 12.5e3
        k = 2 * math.pi * max_dev / if_rate

        adjustment = 1.5   # adjust for proper c4fm deviation level

        modulator = analog.frequency_modulator_fc (k * adjustment)

        # Local oscillator
        lo = analog.sig_source_c (if_rate,        # sample rate
                              analog.GR_SIN_WAVE, # waveform type
                              lo_freq,        #frequency
                              1.0,            # amplitude
                              0)              # DC Offset
        mixer = blocks.multiply_cc ()

        self.connect (vocoder, c4fm, interpolator, modulator, (mixer, 0))
        self.connect (lo, (mixer, 1))
        self.connect (mixer, self)

class fm_tx_block(stdgui2.std_top_block):
    def __init__(self, frame, panel, vbox, argv):
        MAX_CHANNELS = 7
        stdgui2.std_top_block.__init__ (self, frame, panel, vbox, argv)

        parser = OptionParser (option_class=eng_option)
        parser.add_option("-T", "--tx-subdev-spec", type="subdev", default=None,
                          help="select USRP Tx side A or B")
        parser.add_option("-e","--enable-fft", action="store_true", default=False,
                          help="enable spectrum plot (and use more CPU)")
        parser.add_option("-f", "--freq", type="eng_float", default=None,
                           help="set Tx frequency to FREQ [required]", metavar="FREQ")
        parser.add_option("-i","--file-input", action="store_true", default=False,
                          help="input from baseband-0.dat, baseband-1.dat ...")
        parser.add_option("-g", "--audio-gain", type="eng_float", default=1.0,
                           help="input audio gain multiplier")
        parser.add_option("-n", "--nchannels", type="int", default=1,
                           help="number of Tx channels [1,4]")
        parser.add_option("-a", "--udp-addr", type="string", default="127.0.0.1",
                           help="UDP host IP address")
        parser.add_option("--args", type="string", default="",
                           help="device args")
        parser.add_option("--gains", type="string", default="",
                           help="gains")
        parser.add_option("-p", "--udp-port", type="int", default=0,
                           help="UDP port number")
        parser.add_option("-r","--repeat", action="store_true", default=False,
                          help="continuously replay input file")
        parser.add_option("-S", "--stretch", type="int", default=0,
                           help="elastic buffer trigger value")
        parser.add_option("-v","--verbose", action="store_true", default=False,
                          help="print out stats")
        parser.add_option("-I", "--audio-input", type="string", default="", help="pcm input device name.  E.g., hw:0,0 or /dev/dsp")
        (options, args) = parser.parse_args ()

        if len(args) != 0:
            parser.print_help()
            sys.exit(1)

        if options.nchannels < 1 or options.nchannels > MAX_CHANNELS:
            sys.stderr.write ("op25_tx: nchannels out of range.  Must be in [1,%d]\n" % MAX_CHANNELS)
            sys.exit(1)
        
        if options.freq is None:
            sys.stderr.write("op25_tx: must specify frequency with -f FREQ\n")
            parser.print_help()
            sys.exit(1)

        # ----------------------------------------------------------------
        # Set up constants and parameters

        self.u = osmosdr.sink (options.args)       # the USRP sink (consumes samples)
        gain_names = self.u.get_gain_names()
        for name in gain_names:
            gain_range = self.u.get_gain_range(name)
            print "gain: name: %s range: start %d stop %d step %d" % (name, gain_range[0].start(), gain_range[0].stop(), gain_range[0].step())
        if options.gains:
            for tuple in options.gains.split(","):
                name, gain = tuple.split(":")
                gain = int(gain)
                print "setting gain %s to %d" % (name, gain)
                self.u.set_gain(gain, name)

        self.usrp_rate = 320000
        print 'setting sample rate'
        self.u.set_sample_rate(self.usrp_rate)
        self.u.set_center_freq(int(options.freq))
        #self.u.set_bandwidth(self.usrp_rate)

        #self.u = blocks.file_sink(gr.sizeof_gr_complex, 'usrp-samp.dat')

        #self.dac_rate = self.u.dac_rate()                    # 128 MS/s
        #self.usrp_interp = 400
        #self.u.set_interp_rate(self.usrp_interp)
        #self.usrp_rate = self.dac_rate / self.usrp_interp    # 320 kS/s
        #self.sw_interp = 10
        #self.audio_rate = self.usrp_rate / self.sw_interp    # 32 kS/s
        self.audio_rate = 32000

#       if not self.set_freq(options.freq):
#           freq_range = self.subdev.freq_range()
#           print "Failed to set frequency to %s.  Daughterboard supports %s to %s" % (
#               eng_notation.num_to_str(options.freq),
#               eng_notation.num_to_str(freq_range[0]),
#               eng_notation.num_to_str(freq_range[1]))
#           raise SystemExit
#       self.subdev.set_enable(True)                         # enable transmitter

        # instantiate vocoders
        self.vocoders   = []
        if options.file_input:
            i = 0
            t = blocks.file_source(gr.sizeof_char, "baseband-%d.dat" % i, options.repeat)
            self.vocoders.append(t)

        elif options.udp_port > 0:
          self.udp_sources   = []
          for i in range (options.nchannels):
            t = gr.udp_source(1, options.udp_addr, options.udp_port + i, 216)
            self.udp_sources.append(t)
            arity = 2
            t = gr.packed_to_unpacked_bb(arity, gr.GR_MSB_FIRST)
            self.vocoders.append(t)
            self.connect(self.udp_sources[i], self.vocoders[i])

        if 1: # else:
          input_audio_rate = 8000
          #self.audio_input = audio.source(input_audio_rate, options.audio_input)
          af = 1333
          audio_input = analog.sig_source_s( input_audio_rate, analog.GR_SIN_WAVE, af, 15000)
          t = op25_repeater.vocoder(True,		# 0=Decode,True=Encode
                                  options.verbose,	# Verbose flag
                                  options.stretch,	# flex amount
                                  "",			# udp ip address
                                  0,			# udp port
                                  False) 		# dump raw u vectors
          self.connect(audio_input, t)
          self.vocoders.append(t)

        sum = blocks.add_cc ()

        # Instantiate N NBFM channels
        step = 100e3
        offset = (0 * step, -1 * step, +1 * step, 2 * step, -2 * step, 3 * step, -3 * step)
        for i in range (options.nchannels):
            t = pipeline(self.vocoders[i], offset[i],
                         self.audio_rate, self.usrp_rate)
            self.connect(t, (sum, i))

        t = file_pipeline(offset[2], self.usrp_rate, '2013-320k-filt.dat')
        self.connect(t, (sum, options.nchannels))

        gain = blocks.multiply_const_cc (0.75 / (options.nchannels+1))

        # connect it all
        self.connect (sum, gain)
        self.connect (gain, self.u)

        # plot an FFT to verify we are sending what we want
        if options.enable_fft:
            post_mod = fftsink2.fft_sink_c(panel, title="Post Modulation",
                                           fft_size=512, sample_rate=self.usrp_rate,
                                           y_per_div=20, ref_level=40)
            self.connect (sum, post_mod)
            vbox.Add (post_mod.win, 1, wx.EXPAND)
            

        #if options.debug:
        #    self.debugger = tx_debug_gui.tx_debug_gui(self.subdev)
        #    self.debugger.Show(True)


    def set_freq(self, target_freq):
        """
        Set the center frequency we're interested in.

        @param target_freq: frequency in Hz
        @rypte: bool

        Tuning is a two step process.  First we ask the front-end to
        tune as close to the desired frequency as it can.  Then we use
        the result of that operation and our target_frequency to
        determine the value for the digital up converter.  Finally, we feed
        any residual_freq to the s/w freq translater.
        """

        r = self.u.tune(self.subdev.which(), self.subdev, target_freq)
        if r:
            print "r.baseband_freq =", eng_notation.num_to_str(r.baseband_freq)
            print "r.dxc_freq      =", eng_notation.num_to_str(r.dxc_freq)
            print "r.residual_freq =", eng_notation.num_to_str(r.residual_freq)
            print "r.inverted      =", r.inverted
            
            # Could use residual_freq in s/w freq translator
            return True

        return False

def main ():
    sys.stderr.write("GNU Radio Multichannel APCO P25 Tx (c) Copyright 2009, KA1RBI\n")
    app = stdgui2.stdapp(fm_tx_block, "Multichannel APCO P25 Tx", nstatus=1)
    app.MainLoop ()

if __name__ == '__main__':
    main ()
