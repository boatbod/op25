# Copyright 2011 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
install(FILES
    op25_repeater_ambe_encoder_sb.block.yml
    op25_repeater_costas_loop_cc.block.yml
    op25_repeater_fsk4_slicer_fb.block.yml
    op25_repeater_iqfile_source.block.yml
    op25_repeater_rmsagc_ff.block.yml
    op25_repeater_analog_udp.block.yml
    op25_repeater_frame_assembler.block.yml
    op25_repeater_gardner_cc.block.yml
    op25_repeater_p25_frame_assembler.block.yml
    op25_repeater_vocoder.block.yml DESTINATION share/gnuradio/grc/blocks
)
