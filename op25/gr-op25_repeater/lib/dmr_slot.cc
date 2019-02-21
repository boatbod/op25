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

#include "op25_yank.h"
#include "bit_utils.h"
#include "dmr_const.h"
#include "hamming.h"
#include "golay2087.h"
#include "bptc19696.h"
#include "crc16.h"

dmr_slot::dmr_slot(const int chan, const int debug) :
	d_chan(chan),
	d_debug(debug),
	d_lc_valid(false),
	d_type(0),
	d_cc(0xf)
{
	memset(d_slot, 0, sizeof(d_slot));
	d_slot_type.clear();
	d_emb_sig.clear();
}

dmr_slot::~dmr_slot() {
}

void
dmr_slot::load_slot(const uint8_t slot[]) {
	memcpy(d_slot, slot, sizeof(d_slot));

	// Check to see if burst contains SYNC identifying it as Voice or Data
	// SYNC pattern may not match exactly due to received bit errors
	// but the question is how many bit errors is too many...
	bool sync_rxd = false;
	uint64_t sl_sync = load_reg64(d_slot + SYNC_EMB, 48);
	for (int i = 0; i < DMR_SYNC_MAGICS_COUNT; i ++) {
		if (__builtin_popcountll(sl_sync ^ DMR_SYNC_MAGICS[i]) <= DMR_SYNC_THRESHOLD) {
			d_type = DMR_SYNC_MAGICS[i];
			sync_rxd = true;
			break;
		}
	}

	// All bursts not containing SYNC contain EMB instead
	if (!sync_rxd)
		decode_emb_sig();

	// Voice or Data decision is based on most recent SYNC
	switch(d_type) {
		case DMR_BS_VOICE_SYNC_MAGIC:
		case DMR_MS_VOICE_SYNC_MAGIC:
		case DMR_T1_VOICE_SYNC_MAGIC:
		case DMR_T2_VOICE_SYNC_MAGIC:
			// TODO: do voice decoding here rather than in rx_sync.cc
			break;

		case DMR_BS_DATA_SYNC_MAGIC:
		case DMR_MS_DATA_SYNC_MAGIC:
			decode_slot_type();
			break;

		default: // unknown type
			return;
	}
}

bool
dmr_slot::decode_slot_type() {
	bool rc = true;
	d_slot_type.clear();

	// deinterleave
	for (int i = SLOT_L; i < SYNC_EMB; i++)
		d_slot_type.push_back(d_slot[i]);
	for (int i = SLOT_R; i < (SLOT_R + 10); i++)
		d_slot_type.push_back(d_slot[i]);

	// golay (20,8)
	int gly_errs = CGolay2087::decode(d_slot_type);
	if ((gly_errs < 0) || (gly_errs > 3)) // only corrects 3-bit errors or less
		return false;

	d_cc = get_slot_cc();

	if (d_debug >= 10) {
		fprintf(stderr, "Slot(%d), CC(%x), Data Type=%x, gly_errs=%d\n", d_chan, get_slot_cc(), get_data_type(), gly_errs);
	}

	switch(get_data_type()) {
		case 0x0: { // Privacy Information header
			uint8_t pinf[96];
			if (bptc.decode(d_slot, pinf))
				rc = decode_pinf(pinf);
			else
				rc = false;
			break;
		}
		case 0x1: { // Voice LC header
			uint8_t vlch[96];
			if (bptc.decode(d_slot, vlch))
				rc = decode_vlch(vlch);
			else
				rc = false;
			break;
		}
		case 0x2: { // Terminator with LC
			uint8_t tlc[96];
			if (bptc.decode(d_slot, tlc))
				rc = decode_tlc(tlc);
			else
				rc = false;
			break;
		}
		case 0x3: { // CSBK
			uint8_t csbk[96];
			if (bptc.decode(d_slot, csbk))
				rc = decode_csbk(csbk);
			else
				rc = false;
		}
		case 0x4: // MBC
			break;
		case 0x5: // MBC continuation
			break;
		case 0x6: // Data header
			break;
		case 0x7: // Rate 1/2 data
			break;
		case 0x8: // Rate 3/4 data
			break;
		case 0x9: { // Idle
			if (d_debug >= 5) {
				fprintf(stderr, "Slot(%d), CC(%x), IDLE\n", d_chan, get_slot_cc());
			}
			break;
		}
		case 0xa: // Rate 1 data
			break;
		case 0xb: // Unified Single Block data
			break;
		default:
			break;
	}

	return rc;
}

bool
dmr_slot::decode_csbk(uint8_t* csbk) {
	// Apply CSBK mask and validate CRC
	for (int i = 0; i < 16; i++)
		csbk[i+80] ^= CSBK_CRC_MASK[i];
	if (crc16(csbk, 96) != 0)
		return false;

	// Extract parameters
	uint8_t  csbk_lb   = csbk[0] & 0x1;
	uint8_t  csbk_pf   = csbk[1] & 0x1;
	uint8_t  csbk_o    = extract(csbk, 2, 8);
	uint8_t  csbk_fid  = extract(csbk, 8, 16);
	uint64_t csbk_data = extract(csbk, 16, 80);

	if (d_debug >= 5) {
		fprintf(stderr, "Slot(%d), CC(%x), CSBK LB(%d), PF(%d), CSBKO(%02x), FID(%02x), DATA(%08lx)\n", d_chan, get_slot_cc(), csbk_lb, csbk_pf, csbk_o, csbk_fid, csbk_data);
	}

	// TODO: add known CSBKO opcodes

	return true;
}

bool
dmr_slot::decode_vlch(uint8_t* vlch) {
	// Apply VLCH mask
	for (int i = 0; i < 24; i++)
		vlch[i+72] ^= VOICE_LC_HEADER_CRC_MASK[i];

	int rs_errs = 0;
	bool rc = decode_lc(vlch, &rs_errs);
	if (!rc)
		return false;

	if (d_debug >= 5) {
		fprintf(stderr, "Slot(%d), CC(%x), VOICE LC PF(%d), FLCO(%02x), FID(%02x), SVCOPT(%02X), DSTADDR(%06x), SRCADDR(%06x), rs_errs=%d\n", 
			d_chan, get_slot_cc(), get_lc_pf(), get_lc_flco(), get_lc_fid(), get_lc_svcopt(), get_lc_dstaddr(), get_lc_srcaddr(), rs_errs);
	}

	// TODO: add known FLCO opcodes

	return rc;
}

bool
dmr_slot::decode_tlc(uint8_t* tlc) {
	// Apply TLC mask
	for (int i = 0; i < 24; i++)
		tlc[i+72] ^= TERMINATOR_WITH_LC_CRC_MASK[i];

	int rs_errs = 0;
	bool rc = decode_lc(tlc, &rs_errs);
	if (!rc)
		return false;

	if (d_debug >= 5) {
		fprintf(stderr, "Slot(%d), CC(%x), TERM LC PF(%d), FLCO(%02x), FID(%02x), SVCOPT(%02X), DSTADDR(%06x), SRCADDR(%06x), rs_errs=%d\n", 
			d_chan, get_slot_cc(), get_lc_pf(), get_lc_flco(), get_lc_fid(), get_lc_svcopt(), get_lc_dstaddr(), get_lc_srcaddr(), rs_errs);
	}

	// TODO: add known FLCO opcodes

	return rc;
}

bool
dmr_slot::decode_lc(uint8_t* lc, int* errs) {
	// Convert bits to bytes and apply Reed-Solomon(12,9) error correction
	d_lc.assign(12,0);
	for (int i = 0; i < 96; i++) {
		d_lc[i / 8] = (d_lc[i / 8] << 1) | lc[i];
	}
	int rs_errs = rs12.decode(d_lc);

	if (d_debug >=10) {
		fprintf(stderr, "FULL LC: %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x, rs_errs=%d\n",
			d_lc[0], d_lc[1], d_lc[2], d_lc[3], d_lc[4], d_lc[5],
			d_lc[6], d_lc[7], d_lc[7], d_lc[9], d_lc[10], d_lc[11],
			rs_errs);
	}

	if (errs != NULL)
		*errs = rs_errs;

	// Discard parity information and check results
	d_lc.resize(9);
	d_lc_valid = (rs_errs >= 0) ? true : false; 

	return d_lc_valid;
}

bool
dmr_slot::decode_pinf(uint8_t* pinf) {
	// Apply PI mask and validate CRC
	for (int i = 0; i < 16; i++)
		pinf[i+80] ^= PI_HEADER_CRC_MASK[i];
	if (crc16(pinf, 96) != 0)
		return false;

	// Convert bits to bytes and save PI information
	d_pi.assign(10,0);
	for (int i = 0; i < 80; i++) {
		d_pi[i / 8] = (d_pi[i / 8] << 1) | pinf[i];
	}

	if (d_debug >= 5) {
		fprintf(stderr, "Slot(%d), CC(%x), PI HEADER: %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x\n",
			d_chan, get_slot_cc(),
			d_pi[0], d_pi[1], d_pi[2], d_pi[3], d_pi[4], d_pi[5], d_pi[6], d_pi[7], d_pi[8], d_pi[9]);
	}

	return true;
}

bool
dmr_slot::decode_emb_sig() {
	bool rc = true;
	d_emb_sig.clear();

	// deinterleave
	for (int i = SYNC_EMB; i < (SYNC_EMB + 8); i++)
		d_emb_sig.push_back(d_slot[i]);
	for (int i = (SLOT_R - 8); i < SLOT_R; i++)
		d_emb_sig.push_back(d_slot[i]);

	// quadratic residue FEC
	int qr_errs = CQR1676::decode(d_emb_sig);
	if ((qr_errs < 0) || (qr_errs > 2))	// only corrects 2-bit errors or less
		return false;

	// validate correct color code received
	// this is necessary because FEC can pass (errs <= 2) but data contains garbage
	if (d_cc != get_emb_cc())
		return false;

	if (d_debug >= 10) {
		fprintf(stderr, "Slot(%d), CC(%x), PI(%d), EMB lcss(%x), qr_errs=%d\n", d_chan, get_emb_cc(), get_emb_pi(), get_emb_lcss(), qr_errs);
	}



	return true;
}
