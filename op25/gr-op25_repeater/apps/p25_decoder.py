#
# Copyright 2005,2006,2007 Free Software Foundation, Inc.
#
# OP25 Decoder Block
# Copyright 2009, 2014 Max H. Parke KA1RBI
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
P25 decoding block.
"""

import time
from gnuradio import gr, gru, eng_notation
from gnuradio import blocks, audio
from gnuradio.eng_option import eng_option
import op25
import op25_repeater

# default values (used in __init__ and add_options)
_def_debug = 0
_def_num_ambe = False
_def_do_imbe = True
_def_wireshark_host = ''
_def_udp_port = 0
_def_dest = 'wav'
_def_audio_rate = 8000
_def_audio_output = 'plughw:0,0'
_def_max_tdma_timeslots = 2

# /////////////////////////////////////////////////////////////////////////////
#                           decoder
# /////////////////////////////////////////////////////////////////////////////

class p25_decoder_sink_b(gr.hier_block2):

    def __init__(self,
                 dest           = _def_dest,
                 do_imbe	= _def_do_imbe,
                 num_ambe	= _def_num_ambe,
                 wireshark_host	= _def_wireshark_host,
                 udp_port	= _def_udp_port,
                 do_msgq	= False,
                 msgq		= None,
                 audio_output	= _def_audio_output,
                 debug		= _def_debug):
        """
	Hierarchical block for P25 decoding.

        @param debug: debug level
        @type debug: int
	"""

	gr.hier_block2.__init__(self, "p25_demod_c",
				gr.io_signature(1, 1, gr.sizeof_char),       # Input signature
				gr.io_signature(0, 0, 0)) # Output signature

        assert 0 <= num_ambe <= _def_max_tdma_timeslots
        assert not (num_ambe > 1 and dest != 'wav')

        self.debug = debug
        self.dest = dest
        do_output = 1
        do_audio_output = True

        if msgq is None:
            msgq = gr.msg_queue(1)

        self.p25_decoders = []
        self.audio_s2f = []
        self.scaler = []
        self.audio_sink = []
        self.xorhash = []
        num_decoders = 1
        if num_ambe > 1:
           num_decoders += num_ambe - 1
        for slot in xrange(num_decoders):
            self.p25_decoders.append(op25_repeater.p25_frame_assembler(wireshark_host, udp_port, debug, do_imbe, do_output, do_msgq, msgq, do_audio_output, True))
            self.p25_decoders[slot].set_slotid(slot)

            self.audio_s2f.append(blocks.short_to_float()) # another ridiculous conversion
            self.scaler.append(blocks.multiply_const_ff(1 / 32768.0))
            self.xorhash.append('')

            if dest == 'wav':
                filename = 'default-%f-%d.wav' % (time.time(), slot)
                n_channels = 1
                sample_rate = 8000
                bits_per_sample = 16
                self.audio_sink.append(blocks.wavfile_sink(filename, n_channels, sample_rate, bits_per_sample))
            elif dest == 'audio':
                self.audio_sink.append(audio.sink(_def_audio_rate, audio_output, True))

            self.connect(self, self.p25_decoders[slot], self.audio_s2f[slot], self.scaler[slot], self.audio_sink[slot])

    def close_file(self, index=0):
        if self.dest != 'wav':
            return
        self.audio_sink[index].close()

    def set_slotid(self, slot, index=0):
        self.p25_decoders[index].set_slotid(slot)

    def set_output(self, filename, index=0):
        if self.dest != 'wav':
            return
        self.audio_sink[index].open(filename)

    def set_xormask(self, xormask, xorhash, index=0):
        if self.xorhash[index] == xorhash:
            return
        self.xorhash[index] = xorhash
        self.p25_decoders[index].set_xormask(xormask)

    def set_scaler_k(self, k, index=0):
        self.scaler[index].set_k(k)
