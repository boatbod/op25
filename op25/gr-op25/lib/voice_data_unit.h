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

#ifndef INCLUDED_VOICE_DATA_UNIT_H
#define INCLUDED_VOICE_DATA_UNIT_H

#include "abstract_data_unit.h"

/**
 * P25 Logical Data Unit 1 (compressed IBME voice).
 */
class voice_data_unit : public abstract_data_unit
{
public:

   /**
    * voice_data_unit (virtual) destuctor
    */
   virtual ~voice_data_unit();

protected:

   /**
    * voice_data_unit constuctor
    *
    * \param frame_body A const_bit_queue representing the frame body.
    */
   voice_data_unit(const_bit_queue& frame_body);

   /**
    * Applies error correction code to the specified bit_vector. Not
    * that this function removes the PN sequences from the source
    * frame.
    *
    * \param frame_body The bit vector to decode.
    * \return 
    */
   virtual void do_correct_errors(bit_vector& frame_body);

   /**
    * Decode compressed audio using the supplied imbe_decoder.
    *
    * \param frame_body The const_bit_vector to decode.
    * \param imbe The imbe_decoder to use to generate the audio.
    */
   virtual void do_decode_audio(const_bit_vector& frame_body, imbe_decoder& imbe);

   /**
    * Returns the expected size (in bits) of this data_unit. For
    * variable-length data this should return UINT16_MAX until the
    * actual length of this frame is known.
    *
    * \return The expected size (in bits) of this data_unit when encoded.
    */
   virtual uint16_t frame_size_max() const;

};

#endif /* INCLUDED_VOICE_DATA_UNIT_H */
