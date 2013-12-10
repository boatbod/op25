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

#ifndef INCLUDED_LDU2_H
#define INCLUDED_LDU2_H

#include "voice_data_unit.h"

/**
 * P25 Logical Data Unit 2.
 */
class ldu2 : public voice_data_unit
{
public:

   /**
    * ldu2 constructor.
    *
    * \param frame_body A const_bit_queue representing the frame body.
    */
   ldu2(const_bit_queue& frame_body);

   /**
    * ldu2 (virtual) destructor.
    */
   virtual ~ldu2();

   /**
    * Returns a string describing the Data Unit ID (DUID).
    */
   std::string duid_str() const;
};

#endif /* INCLUDED_LDU2_H */
