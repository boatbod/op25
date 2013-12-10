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

#include "data_unit.h"
#include "hdu.h"
#include "ldu1.h"
#include "ldu2.h"
#include "pdu.h"
#include "tdu.h"
#include "tsbk.h"
#include "op25_yank.h"

using namespace std;

data_unit_sptr
data_unit::make_data_unit(const_bit_queue& frame_body)
{
   data_unit_sptr d;
   uint8_t duid = extract(frame_body, 60, 64);
   switch(duid) {
   case 0x0:
      d = data_unit_sptr(new hdu(frame_body));
      break;
   case 0x3:
      d = data_unit_sptr(new tdu(frame_body, false));
      break;
   case 0x5:
      d = data_unit_sptr(new ldu1(frame_body));
      break;
   case 0x7:
      d = data_unit_sptr(new tsbk(frame_body));
      break;
   case 0xa:
      d = data_unit_sptr(new ldu2(frame_body));
      break;
   case 0x9: // VSELP "voice PDU"
   case 0xc:
      d = data_unit_sptr(new pdu(frame_body));
      break;
   case 0xf:
      d = data_unit_sptr(new tdu(frame_body, true));
      break;
   };
   return d;
}

data_unit::~data_unit()
{
}

data_unit::data_unit()
{
}
