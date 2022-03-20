#
# OP25 WAV File Source Block
# Copyright 2021 Graham J. Norbury - gnorbury@bondcar.com
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
OP25 WAV File Source Block
"""

import sys
from gnuradio import gr
from gnuradio import blocks
import gnuradio.op25_repeater as op25_repeater
from log_ts import log_ts


def from_dict(d, key, def_val):
    if key in d and d[key] != "":
        return d[key]
    else:
        return def_val

class op25_wavsrc_f(gr.hier_block2):
    def __init__(self, name, config):

        gr.hier_block2.__init__(self, "op25_wavsrc_f",
                                gr.io_signature(0, 0, 0),               # Input signature
                                gr.io_signature(1, 1, gr.sizeof_float)) # Output signature

        self.config = config
        self.name = name
        self.freq = 0

        # load config
        self.wav_file = str(from_dict(config, 'wav_file', ""))
        self.wav_size = int(from_dict(config, 'wav_size', 1))
        self.wav_gain = float(from_dict(config, 'wav_gain', 1.0))

        # Create the source block
        self.wavsrc = blocks.wavfile_source(self.wav_file)
        self.rate = self.wavsrc.sample_rate()
        self.size = self.wavsrc.bits_per_sample()
        self.chans = self.wavsrc.channels()

        sys.stderr.write("%s [%s] Enabling WAV file source: rate=%d, bit=%d, channels=%d\n" % (log_ts.get(), name, self.rate, self.size, self.chans))


        # Create the throttle to set playback rate
        self.throttle = blocks.throttle(gr.sizeof_float, self.rate)

        # Gain
        self.gain = blocks.multiply_const_ff(self.wav_gain)

        # Connect src and throttle
        self.connect(self.wavsrc, self.throttle, self.gain, self)            

    def get_sample_rate(self):
        return self.rate;

    def set_freq_corr(self, ppm):
        pass

    def set_center_freq(self, freq):
        self.freq = freq

    def get_center_freq(self):
        return self.freq

