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

dmr_slot::dmr_slot() :
	d_type(0LL)
{
	memset(d_slot, 0, sizeof(d_slot));
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

	if (d_type == 0LL) // unknown sync type
		return;

	if (d_debug >= 10)
		fprintf(stderr, "dmr_slot::load_slot(%s): chan=%d, type=%lx\n", (sync_rx) ? "SYN":"EMB", d_chan, d_type);
}



