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

#ifndef INCLUDED_TSBK_H
#define INCLUDED_TSBK_H

#include "abstract_data_unit.h"

/**
 * P25 trunking signalling block (TSBK).
 */
class tsbk : public abstract_data_unit
{

public:

   /**
    * tsbk constructor.
    *
    * \param frame_body A const_bit_queue representing the frame body.
    */
   tsbk(const_bit_queue& frame_body);

   /**
    * tsbk virtual destructor.
    */
   virtual ~tsbk();

   /**
    * Returns a string describing the Data Unit ID (DUID).
    */
   std::string duid_str() const;

protected:

   /**
    * Returns the expected size (in bits) of this data unit in
    * bits.
    *
    * \return The expected size (in bits) of this data_unit when encoded.
    */
   virtual uint16_t frame_size_max() const;

};

#endif /* INCLUDED_TSBK_H */
