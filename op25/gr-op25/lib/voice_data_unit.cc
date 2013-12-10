/* -*- C++ -*- */

/*
 * Copyright 2008 Steve Glass
 * 
 * This file is part of OP25.
 * 
 * OP25 is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * OP25 is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public
 * License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with OP25; see the file COPYING.  If not, write to the Free
 * Software Foundation, Inc., 51 Franklin Street, Boston, MA
 * 02110-1301, USA.
 */

#include "voice_data_unit.h"
#include "op25_imbe_frame.h"

#include <sstream>

using namespace std;

voice_data_unit::~voice_data_unit()
{
}

voice_data_unit::voice_data_unit(const_bit_queue& frame_body) :
   abstract_data_unit(frame_body)
{
}

void
voice_data_unit::do_correct_errors(bit_vector& frame_body)
{
}

void
voice_data_unit::do_decode_audio(const_bit_vector& frame_body, imbe_decoder& imbe)
{
   voice_codeword cw(voice_codeword_sz);
   for(size_t i = 0; i < nof_voice_codewords; ++i) {
      imbe_deinterleave(frame_body, cw, i);
      imbe.decode(cw);
   }
}

uint16_t
voice_data_unit::frame_size_max() const
{
   return 1728;
}
