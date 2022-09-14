/* -*- c++ -*- */
/*
 * construct P25 frames out of raw dibits
 * Copyright 2010, 2011, 2012, 2013, 2014 KA1RBI
 */

#include <vector>
#include <stdio.h>
#include <stdint.h>
#include <sys/time.h>
#include <p25p2_framer.h>

#include "check_frame_sync.h"

// constructor
p25p2_framer::p25p2_framer() :
	d_next_bit(0),
	d_in_sync(0),
	d_fs(0),
	nid_accum(0),
	symbols_received(0),
	d_frame_body(P25P2_BURST_SIZE)
{
}

// destructor
p25p2_framer::~p25p2_framer ()
{
}

/*
 * rx_sym: called once per received symbol
 * 1. looks for flags sequences
 * 2. after flags detected (nid_syms > 0), accumulate 64-bit NID word
 * 3. do BCH check on completed NID
 * 4. after valid BCH check (next_bit > 0), accumulate frame data bits
 *
 * Returns true when complete frame received, else false
 */
bool p25p2_framer::rx_sym(uint8_t dibit) {
        bool rc = false;

	symbols_received++;

	nid_accum <<= 2;
	nid_accum |= (dibit & 0x3);

	int found=0;
	if(check_frame_sync((nid_accum & P25P2_FRAME_SYNC_MASK) ^ P25P2_FRAME_SYNC_MAGIC, 4, 40)) {
        d_fs = P25P2_FRAME_SYNC_MAGIC;
		found = 1;
	}
	else if(check_frame_sync((nid_accum & P25P2_FRAME_SYNC_MASK) ^ P25P2_FRAME_SYNC_REV_P, 0, 40)) {
        d_fs = P25P2_FRAME_SYNC_REV_P;
		found = 1;
	}
	else if(check_frame_sync((nid_accum & P25P2_FRAME_SYNC_MASK) ^ P25P2_FRAME_SYNC_X2400, 0, 40)) {
        d_fs = P25P2_FRAME_SYNC_X2400;
		found = 1;
	}
	else if(check_frame_sync((nid_accum & P25P2_FRAME_SYNC_MASK) ^ P25P2_FRAME_SYNC_N1200, 0, 40)) {
        d_fs = P25P2_FRAME_SYNC_N1200;
		found = 1;
	}
	else if(check_frame_sync((nid_accum & P25P2_FRAME_SYNC_MASK) ^ P25P2_FRAME_SYNC_P1200, 0, 40)) {
        d_fs = P25P2_FRAME_SYNC_P1200;
		found = 1;
	}
	if (found) {
		uint64_t accum = d_fs;
		for (int i=0; i < 40; i++) {
			d_frame_body[39 - i] = accum & 1;
			accum = accum >> 1;
		}
		d_next_bit = 40;
		d_in_sync = 10;  // renew allowance
		return false;
	}
	if (d_in_sync) {
		d_frame_body[d_next_bit++] = (dibit >> 1) & 1;
		d_frame_body[d_next_bit++] =  dibit       & 1;
		// dispose of received frame (if exists) and complete frame is received
		if (d_next_bit >= P25P2_BURST_SIZE) {
			rc = true;	// set rc indicating frame available
			d_in_sync--;	// each frame reduces allowance
			d_next_bit = 0;
		}
	} else {
        d_fs = 0;
    }
	return rc;
}
