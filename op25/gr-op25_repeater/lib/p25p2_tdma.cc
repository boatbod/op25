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

#include <stdint.h>
#include <map>
#include <string.h>
#include <string>
#include <iostream>
#include <assert.h>

#include "p25p2_duid.h"
#include "p25p2_sync.h"
#include "p25p2_tdma.h"
#include "p25p2_vf.h"
#include "mbelib.h"
#include "ambe.h"

static const int BURST_SIZE = 180;
static const int SUPERFRAME_SIZE = (12*BURST_SIZE);

p25p2_tdma::p25p2_tdma(int slotid, std::deque<int16_t> *qptr) :	// constructor
	tdma_xormask(new uint8_t[SUPERFRAME_SIZE]),
	packets(0),
	d_slotid(slotid),
	output_queue_decode(qptr)
{
	assert (slotid == 0 || slotid == 1);
	mbe_initMbeParms (&cur_mp, &prev_mp, &enh_mp);
}

void p25p2_tdma::set_slotid(int slotid)
{
	assert (slotid == 0 || slotid == 1);
	d_slotid = slotid;
}

p25p2_tdma::~p25p2_tdma()	// destructor
{
	delete[](tdma_xormask);
}

void
p25p2_tdma::set_xormask(const char*p) {
	for (int i=0; i<SUPERFRAME_SIZE; i++)
		tdma_xormask[i] = p[i] & 3;
}

void p25p2_tdma::handle_voice_frame(const uint8_t dibits[]) 
{
	static const int NSAMP_OUTPUT=160;
	int b[9];
	int16_t snd;
	int K;
	int rc = -1;

	vf.process_vcw(dibits, b);
	if (b[0] < 120)
		rc = mbe_dequantizeAmbe2250Parms (&cur_mp, &prev_mp, b);
	/* FIXME: check RC */
	K = 12;
	if (cur_mp.L <= 36)
		K = int(float(cur_mp.L + 2.0) / 3.0);
	if (rc == 0)
		software_decoder.decode_tap(cur_mp.L, K, cur_mp.w0, &cur_mp.Vl[1], &cur_mp.Ml[1]);
	audio_samples *samples = software_decoder.audio();
	for (int i=0; i < NSAMP_OUTPUT; i++) {
		if (samples->size() > 0) {
			snd = (int16_t)(samples->front());
			samples->pop_front();
		} else {
			snd = 0;
		}
		output_queue_decode->push_back(snd);
	}
	mbe_moveMbeParms (&cur_mp, &prev_mp);
	mbe_moveMbeParms (&cur_mp, &enh_mp);
}

void p25p2_tdma::handle_packet(const uint8_t dibits[]) 
{
	static const int which_slot[] = {0,1,0,1,0,1,0,1,0,1,1,0};
	packets++;
	sync.check_confidence(dibits);
	if (!sync.in_sync())
		return;
	const uint8_t* burstp = &dibits[10];
	uint8_t xored_burst[170];
	int burst_type = duid.duid_lookup(duid.extract_duid(burstp));
	if (which_slot[sync.tdma_slotid()] == d_slotid && (burst_type == 0 || burst_type == 6))	{ // 4v or 2v (voice) ?
		for (int i=0; i<170; i++) {
			xored_burst[i] = burstp[i] ^ tdma_xormask[sync.tdma_slotid() * BURST_SIZE + i];
		}
		handle_voice_frame(&xored_burst[11]);
		handle_voice_frame(&xored_burst[48]);
		if (burst_type == 0) { // 4v ?
			handle_voice_frame(&xored_burst[96]);
			handle_voice_frame(&xored_burst[133]);
		}
	}
}
