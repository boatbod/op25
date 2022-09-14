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

def from_dict(d, key, def_val):
    if key in d and d[key] != "":
        return d[key]
    else:
        return def_val

class op25_nbfm_c(gr.hier_block2):
    #def __init__(self, dest, debug, input_rate, deviation, squelch, gain, msgq_id, msg_q):
    def __init__(self, dest, debug, config, msgq_id, msg_q):

        gr.hier_block2.__init__(self, "op25_nbfm_c",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex), # Input signature
                                gr.io_signature(0, 0, 0))                    # Output signature

        self.debug = debug
        self.config = config
        self.msgq_id = msgq_id
        self.subchannel_framer = None

        sys.stderr.write("%s [%d] Enabling nbfm analog audio\n" % (log_ts.get(), msgq_id))

        # load config
        input_rate = int(from_dict(config, 'if_rate', 24000))
        deviation = int(from_dict(config, 'nbfm_deviation', 4000))
        squelch = int(from_dict(config, 'nbfm_squelch_threshold', -60))
        gain = float(from_dict(config, 'nbfm_squelch_gain', 0.0015))
        subchannel_enabled = bool(from_dict(config, 'nbfm_enable_subchannel', False))
        raw_in = str(from_dict(config, 'nbfm_raw_input', ""))
        raw_out = str(from_dict(config, 'nbfm_raw_output', ""))

        # 'switch' enables the analog decoding to be turned on/off
        self.switch = blocks.copy(gr.sizeof_gr_complex)
        self.switch.set_enabled(False)

        # power squelch
        self.squelch = analog.simple_squelch_cc(squelch, gain)

        # quadrature demod
        fm_demod_gain = input_rate / (4 * pi * deviation)
        self.fm_demod = analog.quadrature_demod_cf(fm_demod_gain)

        # fm deemphasis
        self.deemph = analog.fm_deemph(input_rate, 0.00075)

        # decimate and filter
        audio_decim = input_rate // _PCM_RATE
        lpf_taps = filter.firdes.low_pass(1.0,            # gain
                                          input_rate,     # sampling rate
                                          3000.0,         # Audio high cutoff (remove aliasing)
                                          200.0,          # transition
                                          filter.firdes.WIN_HAMMING)  # filter type
        hpf_taps = filter.firdes.high_pass(1.0,           # gain
                                          _PCM_RATE,      # sampling rate
                                          200.0,          # Audio low cutoff  (remove sub-audio signaling)
                                          10.0,           # Sharp transition band
                                          filter.firdes.WIN_HAMMING)  # filter type
        self.lp_filter = filter.fir_filter_fff(audio_decim, lpf_taps)
        self.hp_filter = filter.fir_filter_fff(1, hpf_taps)

        # analog_udp block converts +/-1.0 float samples to S16LE PCM and sends over UDP 
        self.analog_udp = op25_repeater.analog_udp(dest, debug, msgq_id, msg_q)

        # raw playback
        if raw_in != "":
            self.null_sink = blocks.null_sink(gr.sizeof_gr_complex)
            self.connect(self, self.null_sink)                                  # dispose of regular input
            self.raw_file = blocks.file_source(gr.sizeof_float, raw_in, False)
            self.throttle = blocks.throttle(gr.sizeof_float, input_rate)
            self.throttle.set_max_noutput_items(input_rate/50);
            self.fm_demod = self.throttle                                       # and replace fm_demod with throttled file source
            self.connect(self.raw_file, self.throttle)
            sys.stderr.write("%s [%d] Reading nbfm demod from file: %s\n" % (log_ts.get(), msgq_id, raw_in))

        else:
            self.connect(self, self.switch, self.squelch, self.fm_demod)

        self.connect(self.fm_demod, self.deemph, self.lp_filter, self.hp_filter, self.analog_udp)

        # raw capture
        if raw_in == "" and raw_out != "":
            sys.stderr.write("%s [%d] Saving nbfm demod to file: %s\n" % (log_ts.get(), msgq_id, raw_out))
            self.raw_sink = blocks.file_sink(gr.sizeof_float, raw_out)
            self.connect(self.fm_demod, self.raw_sink)

        # subchannel signaling
        if subchannel_enabled:
            self.subchannel_decimation = 25
            self.subchannel_gain = 10
            self.subchannelfilttaps = filter.firdes.low_pass(self.subchannel_gain, input_rate, 200, 40, filter.firdes.WIN_HANN)
            self.subchannelfilt = filter.fir_filter_fff(self.subchannel_decimation, self.subchannelfilttaps)
            self.subchannel_syms_per_sec = 150
            self.subchannel_samples_per_symbol = (input_rate / self.subchannel_decimation) / self.subchannel_syms_per_sec
            sys.stderr.write("%s [%d] Subchannel samples per symbol: %f\n" % (log_ts.get(), msgq_id, self.subchannel_samples_per_symbol))
            self.subchannel_clockrec = digital.clock_recovery_mm_ff(self.subchannel_samples_per_symbol,
                                                               0.25*0.01*0.01,
                                                               0.5,
                                                               0.01,
                                                               0.3)
            self.subchannel_slicer = digital.binary_slicer_fb()
            #self.subchannel_correlator = digital.correlate_access_code_bb("01000", 0)
            self.subchannel_framer = op25_repeater.frame_assembler("subchannel", debug, msgq_id, msg_q)
            self.connect(self.fm_demod, self.subchannelfilt, self.subchannel_clockrec, self.subchannel_slicer, self.subchannel_framer)            

    def control(self, action):
        self.switch.set_enabled(action)
        if self.debug >= 5:
            sys.stderr.write("%s [%d] op25_nbfm::control: analog audio %s\n" % (log_ts.get(), self.msgq_id, ('enabled' if action else 'disabled')))

    def set_debug(self, dbglvl):
        self.debug = dbglvl
        if self.subchannel_framer is not None:
            self.subchannel_framer.set_debug(dbglvl)

