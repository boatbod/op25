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

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <string>
#include <iostream>
#include <deque>
#include <errno.h>
#include <unistd.h>

#include "dmr_cai.h"

#include "bit_utils.h"
#include "dmr_const.h"
#include "hamming.h"
#include "golay2087.h"

dmr_slot::dmr_slot() :
	d_type(0LL)
{
	memset(d_slot, 0, sizeof(d_slot));
	d_slot_type.clear();
}

dmr_slot::~dmr_slot() {
}

void
dmr_slot::load_slot(const uint8_t slot[]) {
	memcpy(d_slot, slot, sizeof(d_slot));

	bool sync_rx = false;
	uint64_t sl_sync = load_reg64(d_slot + SYNC_EMB, 48);
	switch(sl_sync) {
		case DMR_VOICE_SYNC_MAGIC:
			d_type = DMR_VOICE_SYNC_MAGIC;
			sync_rx = true;
			break;
		case DMR_DATA_SYNC_MAGIC:
			d_type = DMR_DATA_SYNC_MAGIC;
			sync_rx = true;
			break;
	}

	switch(d_type) {
		case DMR_VOICE_SYNC_MAGIC:
			break;

		case DMR_DATA_SYNC_MAGIC:
			decode_slot_type();
			break;

		default: // unknown type
			return;
	}
}

bool
dmr_slot::decode_slot_type() {
	d_slot_type.clear();

	// deinterleave
	for (int i = SLOT_L; i < SYNC_EMB; i++)
		d_slot_type.push_back(d_slot[i]);
	for (int i = SLOT_R; i < (SLOT_R + 10); i++)
		d_slot_type.push_back(d_slot[i]);

	// golay (20,8)
	int errs = CGolay2087::decode(d_slot_type);

	fprintf(stderr, "Slot CC=%x, Data Type=%x, errs=%d\n", get_cc(), get_data_type(), errs);
}



