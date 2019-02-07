//
// DMR Protocol Decoder (C) Copyright 2019 Graham J. Norbury
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

#ifndef INCLUDED_DMR_SLOT_H
#define INCLUDED_DMR_SLOT_H

#include <stdint.h>
#include <vector>

#include "dmr_const.h"
#include "dmr_slot.h"

typedef std::vector<bool> bit_vector;

class dmr_slot {
public:
	dmr_slot();
	~dmr_slot();
	inline void set_debug(const int debug) { d_debug = debug; };
	inline void set_chan(const int chan) { d_chan = chan; };
	inline uint8_t get_cc() { return 	(d_slot_type[0] << 3) + 
						(d_slot_type[1] << 3) + 
						(d_slot_type[2] << 1) + 
						 d_slot_type[3]; };
	inline uint8_t get_data_type() { return (d_slot_type[4] << 3) + 
						(d_slot_type[5] << 3) + 
						(d_slot_type[6] << 1) + 
						 d_slot_type[7]; };
	void load_slot(const uint8_t slot[]);

private:
	static const int SLOT_SIZE  = 264; // bits
	static const int PAYLOAD_L  =   0;
	static const int PAYLOAD_R  = 156;
	static const int SYNC_EMB   = 108;
	static const int SLOT_L     =  98;
	static const int SLOT_R     = 156;

	uint8_t d_slot[SLOT_SIZE];       // array of bits comprising the current slot
	bit_vector d_slot_type;
	uint64_t d_type;
	int d_debug;
	int d_chan;

	bool decode_slot_type();

};

#endif /* INCLUDED_DMR_SLOT_H */
