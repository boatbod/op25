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

#include "pdu.h"

using std::string;

pdu::pdu(const_bit_queue& frame_body) :
   abstract_data_unit(frame_body)
{
}
pdu::~pdu()
{
}

string
pdu::duid_str() const
{
   return string("PDU");
}

void
pdu::do_correct_errors(bit_vector& frame_body)
{
}

uint16_t
pdu::frame_size_max() const
{
#if 1
  const size_t HEADER_BLOCK_SIZE = 720;
  return HEADER_BLOCK_SIZE;
#else
  const size_t MIN_HEADER_BLOCK_SZ = 312;
  // after HEADER_BLOCK_SIZE bits have been read we can then use the
  // header contents to decide on frame_size_max

  size_t n = MIN_HEADER_BLOCK_SZ;
  if(n < ) {
     static const size_t BITS[] = {};
     static const size_t BITS_SZ = sizeof(BITS) / sizeof(BITS[0]);
     n = extract();
  }
  return n;

#endif
}
