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

#ifndef INCLUDED_TDU_H
#define INCLUDED_TDU_H

#include "abstract_data_unit.h"

/**
 * P25 terminator data unit (TDU).
 */
class tdu : public abstract_data_unit
{
public:

   /**
    * tdu constructor.
    *
    * \param frame_body A const_bit_queue representing the frame body.
    * \param has_link_control true if frame has link control data, otherwise false.
    */
   tdu(const_bit_queue& frame_body, bool has_link_control);

   /**
    * tdu constructor.
    */
   virtual ~tdu();

   /**
    * Returns a string describing the Data Unit ID (DUID).
    */
   std::string duid_str() const;

protected:

   /**
    * Applies error correction code to the specified bit_vector.
    *
    * \param frame_body The bit vector to decode.
    * \return 
    */
   virtual void do_correct_errors(bit_vector& frame_body);

   /**
    * Apply Golay error correction code to the specified bit_vector.
    *
    * \param frame_body The bit vector to decode.
    * \return 
    */
   virtual void apply_golay_correction(bit_vector& frame_body);

   /**
    * Apply Reed-Solomon error correction code to the specified
    * bit_vector.
    *
    * \param frame_body The bit vector to decode.
    * \return 
    */
   virtual void apply_rs_correction(bit_vector& frame_body);

   /**
    * Returns the expected size (in bits) of this data unit in
    * bits. For variable-length data this should return UINT16_MAX
    * until the actual length of this frame is known.
    *
    * \return The expected size (in bits) of this data_unit when encoded.
    */
   virtual uint16_t frame_size_max() const;

private:

   /**
    * Does this TDU have a link_control field?
    */
   bool d_has_link_control;

};

#endif /* INCLUDED_TDU_H */
