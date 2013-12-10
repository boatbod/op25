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

#include "tsbk.h"

using namespace std;

tsbk::tsbk(const_bit_queue& frame_body) :
   abstract_data_unit(frame_body)
{
}

tsbk::~tsbk()
{
}

string
tsbk::duid_str() const
{
   return string("TSBK");
}

uint16_t
tsbk::frame_size_max() const
{
#if 1
   return 720;
#else
   // todo: check this out!
   return 358;
#endif
}
