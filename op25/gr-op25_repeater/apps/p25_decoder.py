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
_def_do_ambe = False
_def_do_imbe = True
_def_wireshark_host = ''
_def_udp_port = 0
_def_dest = 'wav'
_def_audio_rate = 8000
_def_audio_output = 'plughw:0,0'

# /////////////////////////////////////////////////////////////////////////////
#                           decoder
# /////////////////////////////////////////////////////////////////////////////

class p25_decoder_c(gr.hier_block2):

    def __init__(self,
                 dest           = _def_dest,
                 do_imbe	= _def_do_imbe,
                 do_ambe	= _def_do_ambe,
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

        self.debug = debug
        self.dest = dest
        do_output = 1
        do_audio_output = True

        if msgq is None:
            msgq = gr.msg_queue(1)
        
        self.p25decoder = op25_repeater.p25_frame_assembler(wireshark_host, udp_port, debug, do_imbe, do_output, do_msgq, msgq, do_audio_output, do_ambe)

        if dest == 'wav':
            filename = 'default-%f.wav' % (time.time())
            n_channels = 1
            sample_rate = 8000
            bits_per_sample = 16
            self.audio_sink = blocks.wavfile_sink(filename, n_channels, sample_rate, bits_per_sample)
        elif dest == 'audio':
            self.audio_sink = audio.sink(_def_audio_rate, audio_output, True)

        self.audio_s2f = blocks.short_to_float() # another ridiculous conversion
        self.scaler = blocks.multiply_const_ff(1 / 32768.0)

        self.connect(self, self.p25decoder, self.audio_s2f, self.scaler, self.audio_sink)

    def close_file(self):
        if self.dest != 'wav':
            return
        self.audio_sink.close()

    def set_output(self, slot, filename):
        if self.dest != 'wav':
            return
        self.audio_sink.open(filename)
        print 'set_output', slot, filename
