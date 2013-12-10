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
 * or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
 * License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with OP25; see the file COPYING. If not, write to the Free
 * Software Foundation, Inc., 51 Franklin Street, Boston, MA
 * 02110-1301, USA.
 */

#include "voice_du_handler.h"

#include <cstdio>
#include <stdint.h>

using namespace std;

voice_du_handler::voice_du_handler(data_unit_handler_sptr next, imbe_decoder_sptr decoder) :
   data_unit_handler(next),
   d_decoder(decoder)
{
}


voice_du_handler::~voice_du_handler()
{
}

void
voice_du_handler::handle(data_unit_sptr du)
{
   du->decode_audio(*d_decoder);
   data_unit_handler::handle(du);
}
