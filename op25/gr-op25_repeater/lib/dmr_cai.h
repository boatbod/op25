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

#ifndef INCLUDED_OP25_REPEATER_DMR_CAI_H
#define INCLUDED_OP25_REPEATER_DMR_CAI_H

#include <stdint.h>
#include <vector>

typedef std::vector<bool> bit_vector;

namespace gr{
    namespace op25_repeater{

class dmr_cai {
public:
	dmr_cai(int debug);
	~dmr_cai();
	int load_frame(const uint8_t fr_sym[]);
	inline int slot() { return d_slot; };

private:
	static const int FRAME_SIZE = 288; // bits
	static const int INF_L      =  24;
	static const int INF_R      = 180;
	static const int SYNC_EMB   = 132;
	static const int CACH       =   0;
	static const int SLOT_L     = 122;
	static const int SLOT_R     = 180;

	uint8_t d_frame[FRAME_SIZE];       // array of bits comprising the current frame
	bit_vector d_cach_sig;
	int d_slot;
	int d_shift_reg;
	int d_debug;

	void extract_cach_fragment();
	bool decode_shortLC(bit_vector& cw);

};

    } // end namespace op25_repeater
} // end namespace gr
#endif /* INCLUDED_OP25_REPEATER_DMR_CAI_H */
