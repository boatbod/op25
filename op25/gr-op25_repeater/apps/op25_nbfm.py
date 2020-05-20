#
# OP25 Narrowband FM Demodulator Block
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
OP25 Analog Narrowband FM Demodulator Block
"""

import sys
from gnuradio import gr, gru, eng_notation
from gnuradio import filter, analog, digital, blocks
from math import pi
import op25_repeater
from log_ts import log_ts

_PCM_RATE       = 8000   # PCM is 8kHz S16LE format

class op25_nbfm_f(gr.hier_block2):
    def __init__(self, dest, debug, input_rate, deviation, msgq_id, msg_q):

        gr.hier_block2.__init__(self, "op25_nbfm_f",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex), # Input signature
                                gr.io_signature(0, 0, 0))                    # Output signature

        self.debug = debug
        self.msgq_id = msgq_id

        # 'switch' enables the analog decoding to be turned on/off
        self.switch = blocks.copy(gr.sizeof_gr_complex)
        self.switch.set_enabled(False)

        # quadrature demod
        fm_demod_gain = input_rate / (2 * pi * deviation)
        self.fm_demod = analog.quadrature_demod_cf(fm_demod_gain)

        # fm deemphasis
        self.deemph = analog.fm_deemph(input_rate, 0.000150)

        # decimate and filter
        audio_decim = input_rate // _PCM_RATE
        audio_taps = filter.firdes.low_pass(1.0,            # gain
                                            input_rate,     # sampling rate
                                            2.7e3,          # Audio LPF cutoff
                                            0.5e3,          # Transition band
                                            filter.firdes.WIN_HAMMING)  # filter type
        self.audio_filter = filter.fir_filter_fff(audio_decim, audio_taps)

        # analog_udp block converts +/-1.0 float samples to S16LE PCM and sends over UDP 
        self.analog_udp = op25_repeater.analog_udp(dest, debug, msgq_id, msg_q)

        self.connect(self, self.switch, self.fm_demod, self.deemph, self.audio_filter, self.analog_udp)
        sys.stderr.write("%s [%d] Enabling nbfm analog audio\n" % (log_ts.get(), msgq_id))

    def control(self, action):
        self.switch.set_enabled(action)
        if self.debug >= 5:
            sys.stderr.write("%s [%d] op25_nbfm::control: analog audio %s\n" % (log_ts.get(), self.msgq_id, ('enabled' if action else 'disabled')))

