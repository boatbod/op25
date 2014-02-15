// P25 TDMA Decoder (C) Copyright 2013, 2014 Max H. Parke KA1RBI
// 
// This file is part of OP25
// 
// OP25 is free software; you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by
// the Free Software Foundation; either version 3, or (at your option)
// any later version.
// 
// OP25 is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
// or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
// License for more details.
// 
// You should have received a copy of the GNU General Public License
// along with OP25; see the file COPYING. If not, write to the Free
// Software Foundation, Inc., 51 Franklin Street, Boston, MA
// 02110-1301, USA.

#ifndef INCLUDED_P25P2_TDMA_H
#define INCLUDED_P25P2_TDMA_H

#include <stdint.h>
#include <deque>
#include "mbelib.h"
#include "imbe_decoder.h"
#include "software_imbe_decoder.h"
#include "p25p2_duid.h"
#include "p25p2_sync.h"
#include "p25p2_vf.h"

class p25p2_tdma;
class p25p2_tdma
{
public:
	p25p2_tdma(int slotid, std::deque<int16_t> * qptr);	// constructor
	void handle_packet(const uint8_t dibits[]) ;
	void handle_voice_frame(const uint8_t dibits[]) ;
	void set_slotid(int slotid);
	uint8_t* tdma_xormask;
	~p25p2_tdma();	// destructor
	void set_xormask(const char*p);
private:
	p25p2_sync sync;
	p25p2_duid duid;
	p25p2_vf vf;
	uint32_t packets;
	int d_slotid;
	mbe_parms cur_mp;
	mbe_parms prev_mp;
	mbe_parms enh_mp;
	software_imbe_decoder software_decoder;
	std::deque<int16_t> *output_queue_decode;
};
#endif /* INCLUDED_P25P2_TDMA_H */
