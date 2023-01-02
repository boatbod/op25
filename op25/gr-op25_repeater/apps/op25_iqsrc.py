#
# OP25 IQ File Source Block
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
OP25 IQ File Source Block
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

class op25_iqsrc_c(gr.hier_block2):
    def __init__(self, name, config):

        gr.hier_block2.__init__(self, "op25_iqsrc_c",
                                gr.io_signature(0, 0, 0),                    # Input signature
                                gr.io_signature(1, 1, gr.sizeof_gr_complex)) # Output signature

        self.config = config
        self.name = name
        self.is_dsd_file = False
        self.freq = 0
        self.ts = 0

        sys.stderr.write("%s [%s] Enabling IQ file source\n" % (log_ts.get(), name))

        # load config
        self.iq_file = str(from_dict(config, 'iq_file', ""))
        self.iq_seek = int(from_dict(config, 'iq_seek', 0))
        self.iq_size = int(from_dict(config, 'iq_size', 1))
        self.iq_signed  = bool(from_dict(config, 'iq_signed', False))
        self.rate = int(from_dict(config, 'rate', 2400000))

        # Create the source block
        self.iqsrc = op25_repeater.iqfile_source(self.iq_size, self.iq_file, self.iq_signed, self.iq_seek, 0)
        if self.iqsrc.is_dsd():
            self.is_dsd_file = True
            self.rate = self.iqsrc.get_dsd_rate()
            self.freq = self.iqsrc.get_dsd_freq()
            self.ts = self.iqsrc.get_dsd_ts()

        # Create the throttle to set playback rate
        self.throttle = blocks.throttle(gr.sizeof_gr_complex, self.rate)

        # Connect src and throttle
        self.connect(self.iqsrc, self.throttle, self)            

    def set_sample_rate(self, iq_rate):
        self.rate = iq_rate
        self.throttle.set_sample_rate(self.rate)

    def get_sample_rate(self):
        return self.rate

    def set_freq_corr(self, ppm):
        pass

    def set_center_freq(self, freq):
        self.freq = freq

    def get_center_freq(self):
        return self.freq

    def get_ts(self):
        return self.ts

    def is_dsd(self):
        return self.is_dsd_file

