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

dmr_slot::dmr_slot(const int chan, const int debug, bool do_msgq, gr::msg_queue::sptr queue) :
	d_chan(chan),
	d_debug(debug),
	d_do_msgq(do_msgq),
	d_msg_queue(queue),
	d_mbc_state(DATA_INVALID),
	d_lc_valid(false),
	d_rc_valid(false),
	d_sb_valid(false),
	d_rc(0),
	d_sb(0),
	d_type(0),
	d_cc(0xf)
{
	memset(d_slot, 0, sizeof(d_slot));
	d_slot_type.clear();
	d_lc.clear();
	d_emb.clear();
	d_mbc.clear();
}

dmr_slot::~dmr_slot() {
}

bool
dmr_slot::load_slot(const uint8_t slot[], uint64_t sl_type) {
	bool is_voice_frame = false;
	memcpy(d_slot, slot, sizeof(d_slot));

	// Check if fresh Sync received
	if (sl_type != 0)
		d_type = sl_type;
	else
		decode_emb();

	// Voice or Data decision is based on most recent SYNC
	std::string v_type;
	switch(d_type) {
		case DMR_BS_VOICE_SYNC_MAGIC:
			v_type = "BS";
			is_voice_frame = true;
			break;
		case DMR_MS_VOICE_SYNC_MAGIC:
			v_type = "MS";
			is_voice_frame = true;
			break;
		case DMR_T1_VOICE_SYNC_MAGIC:
			v_type = "T1";
			is_voice_frame = true;
			break;
		case DMR_T2_VOICE_SYNC_MAGIC:
			v_type = "T2";
			is_voice_frame = true;
			break;
		case DMR_BS_DATA_SYNC_MAGIC:
		case DMR_MS_DATA_SYNC_MAGIC:
			decode_slot_type();
			break;

		default: // unknown type
			break;
	}
	if (is_voice_frame && (d_debug >= 5)) {
		fprintf(stderr, "Slot(%d), CC(%x), %s VOICE\n", d_chan, d_cc, v_type.c_str());
	}
	return is_voice_frame;
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

	// golay (20,8) hamming-weight of 6 reliably corrects at most 2 bit-errors
	int gly_errs = CGolay2087::decode(d_slot_type);
	if ((gly_errs < 0) || (gly_errs > 2))
		return false;
	
	uint8_t slot_cc = get_slot_cc();
	if ((d_cc != slot_cc) && (d_cc == 0xf))
		d_cc = slot_cc;
	else if (d_cc != slot_cc)
		return false;

	if (d_debug >= 10) {
		fprintf(stderr, "Slot(%d), CC(%x), Data Type=%x, gly_errs=%d\n", d_chan, get_slot_cc(), get_data_type(), gly_errs);
	}

	switch (get_data_type()) {
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
			break;
		}
		case 0x4: { // MBC header
			uint8_t mbc[96];
			if (bptc.decode(d_slot, mbc))
				rc = decode_mbc_header(mbc);
			else
				rc = false;
			break;
		}
		case 0x5: { // MBC continuation
			uint8_t mbc[96];
			if (bptc.decode(d_slot, mbc))
				rc = decode_mbc_continue(mbc);
			else
				rc = false;
			break;
		}
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
	// Apply mask and validate CRC
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

	// Known CSBKO opcodes
	switch((csbk_o << 8) + csbk_fid) {
		case 0x0106: { // MotoTRBO ConnectPlus Neighbors
			uint8_t nb1 = extract(csbk, 18, 24);
			uint8_t nb2 = extract(csbk, 26, 32);
			uint8_t nb3 = extract(csbk, 34, 40);
			uint8_t nb4 = extract(csbk, 42, 48);
			uint8_t nb5 = extract(csbk, 50, 56);
			if (d_debug >= 5) {
				fprintf(stderr, "Slot(%d), CC(%x), CSBK LB(%d), PF(%d), CSBKO(%02x), FID(%02x), CONNECT PLUS NB1(%02x), NB2(%02x), NB3(%02x), NB4(%02x), NB5(%02x)\n", d_chan, get_slot_cc(), csbk_lb, csbk_pf, csbk_o, csbk_fid, nb1, nb2, nb3, nb4, nb5);
			}
			break;
		}

		case 0x0306: { //MotoTRBO ConnectPlus Channel Grant
			uint32_t srcAddr = extract(csbk, 16, 40);
			uint32_t grpAddr = extract(csbk, 40, 64);
			uint8_t  lcn     = extract(csbk, 64, 68);
			uint8_t  tslot   = csbk[68];
			if (d_debug >= 5) {
				fprintf(stderr, "Slot(%d), CC(%x), CSBK LB(%d), PF(%d), CSBKO(%02x), FID(%02x), CONNECT PLUS GRANT srcAddr(%06x), grpAddr(%06x), LCN(%x), TS(%d)\n", d_chan, get_slot_cc(), csbk_lb, csbk_pf, csbk_o, csbk_fid, srcAddr, grpAddr, lcn, tslot);
			}
			break;
		}

		default: {
			if (d_debug >= 5) {
				fprintf(stderr, "Slot(%d), CC(%x), CSBK LB(%d), PF(%d), CSBKO(%02x), FID(%02x), DATA(%08lx)\n", d_chan, get_slot_cc(), csbk_lb, csbk_pf, csbk_o, csbk_fid, csbk_data);
			}
		}
	}

	return true;
}

bool
dmr_slot::decode_mbc_header(uint8_t* mbc) {
	d_mbc_state = DATA_INVALID;

	// Apply mask and validate CRC
	for (int i = 0; i < 16; i++)
		mbc[i+80] ^= MBC_HEADER_CRC_MASK[i];
	if (crc16(mbc, 96) != 0) {
		fprintf(stderr, "MBC Header CRC failure\n");
		return false;
	}

	// Extract parameters
	uint8_t  mbc_lb   = mbc[0] & 0x1;
	uint8_t  mbc_pf   = mbc[1] & 0x1;
	uint8_t  mbc_o    = extract(mbc, 2, 8);
	uint8_t  mbc_fid  = extract(mbc, 8, 16);

	// Save header and data, excluding last 16 bits of CRC
	for (int i = 0; i < 80; i++) {
		d_mbc.push_back(mbc[i]);
	}
	d_mbc_state = DATA_INCOMPLETE;

	if (d_debug >= 5) {
		fprintf(stderr, "Slot(%d), CC(%x), MBC HDR LB(%d), PF(%d), CSBKO(%02x), FID(%02x)\n", d_chan, get_slot_cc(), mbc_lb, mbc_pf, mbc_o, mbc_fid);
	}

	return true;
}

bool
dmr_slot::decode_mbc_continue(uint8_t* mbc) {
	// Can only continue if we have started accumulating MBC data
	if (d_mbc_state != DATA_INCOMPLETE)
		return false;

	// Extract last block indicator
	uint8_t  mbc_lb   = mbc[0] & 0x1;

	// Save data excluding last block indicator bit
	for (int i = 1; i < 96; i++) {
		d_mbc.push_back(mbc[i]);
	}

	if (!mbc_lb) {
		if (d_debug >= 5) {
			fprintf(stderr, "Slot(%d), CC(%x), MBC CONT LB(%d)\n", d_chan, get_slot_cc(), mbc_lb);
		}
	} else {
		// Validate CRC, excluding first 80 bits of header
		if ((d_mbc.size() < 175) || 
		    (crc16((uint8_t*)(d_mbc.data() + 80), d_mbc.size() - 80) != 0)) {
			d_mbc_state = DATA_INVALID;
			return false;
		}
		d_mbc.resize(d_mbc.size()-16); // discard trailing CRC
		d_mbc_state = DATA_VALID;

		if (d_debug >= 5) {
			fprintf(stderr, "Slot(%d), CC(%x), MBC CONT LB(%d), data size=%lu\n", d_chan, get_slot_cc(), mbc_lb, d_mbc.size());
		}

		// TODO: do something useful with the MBC data
	} 

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
			d_lc[6], d_lc[7], d_lc[8], d_lc[9], d_lc[10], d_lc[11],
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
dmr_slot::decode_emb() {
	bit_vector emb_sig;

	// deinterleave
	for (int i = SYNC_EMB; i < (SYNC_EMB + 8); i++)
		emb_sig.push_back(d_slot[i]);
	for (int i = (SLOT_R - 8); i < SLOT_R; i++)
		emb_sig.push_back(d_slot[i]);

	// quadratic residue FEC
	int qr_errs = CQR1676::decode(emb_sig);
	if ((qr_errs < 0) || (qr_errs > 2))	// only corrects 2-bit errors or less
		return false;

	// validate correct color code received
	// this is necessary because FEC can pass even with garbage data
	uint8_t emb_cc = (emb_sig[0] << 3) + (emb_sig[1] << 2) + (emb_sig[2] << 1) + emb_sig[3];
	if (d_cc != emb_cc)
		return false;

	uint8_t emb_pi = emb_sig[4];
	uint8_t emb_lcss = (emb_sig[5] << 1) + emb_sig[6];

	if (d_debug >= 10) {
		fprintf(stderr, "Slot(%d), CC(%x), PI(%d), EMB lcss(%x), qr_errs=%d\n", d_chan, emb_cc, emb_pi, emb_lcss, qr_errs);
	}

	switch (emb_lcss) {
		case 0:	// Single-fragment RC
			d_emb.clear();
			for (size_t i=0; i<32; i++)
				d_emb.push_back(d_slot[SYNC_EMB + 8 + i]);
			if (decode_embedded_sbrc(emb_pi)) {
				if (d_debug >= 5) {
					if (emb_pi)
						fprintf(stderr, "Slot(%d), CC(%x), EMB RC(%x)\n", d_chan, emb_cc, get_rc());
					else
						fprintf(stderr, "Slot(%d), CC(%x), EMB SB(%03x)\n", d_chan, emb_cc, get_sb());
				}
			}
			break;
		case 1: // First fragment LC
			d_emb.clear();
			for (size_t i=0; i<32; i++)
				d_emb.push_back(d_slot[SYNC_EMB + 8 + i]);
			break;
		case 2: // End LC
			for (size_t i=0; i<32; i++)
				d_emb.push_back(d_slot[SYNC_EMB + 8 + i]);
			if (decode_embedded_lc()) {
				if (d_debug >= 5) {
					fprintf(stderr, "Slot(%d), CC(%x), EMB LC PF(%d), FLCO(%02x), FID(%02x), SVCOPT(%02X), DSTADDR(%06x), SRCADDR(%06x)\n", 
						d_chan, emb_cc, get_lc_pf(), get_lc_flco(), get_lc_fid(), get_lc_svcopt(), get_lc_dstaddr(), get_lc_srcaddr());
				}
			}
			break;
		case 3: // Continue LC
			for (size_t i=0; i<32; i++)
				d_emb.push_back(d_slot[SYNC_EMB + 8 + i]);
			break;
 
	}

	return true;
}

bool
dmr_slot::decode_embedded_lc() {
	byte_vector emb_data;
	d_lc_valid = false;
	d_lc.clear();

	// The data is unpacked downwards in columns
	bool data[128];
	memset(data, 0, 128 * sizeof(bool));
	unsigned int b = 0;
	for (unsigned int a = 0; a < 128; a++) {
		data[b] = d_emb[a];
		b += 16;
		if (b > 127)
			b -= 127;
	}

	// Hamming (16,11,4) check each row except the last one
	for (unsigned int a = 0; a < 112; a += 16) {
		if (!CHamming::decode16114(data + a))
			return false;
	}

	// Check parity bits
	for (unsigned int a = 0; a < 16; a++) {
		bool parity = data[a + 0] ^ data[a + 16] ^ data[a + 32] ^ data[a + 48] ^ data[a + 64] ^ data[a + 80] ^ data[a + 96] ^ data[a + 112];
		if (parity)
			return false;
	}

	// Extract 72 bits of payload
	for (unsigned int a = 0; a < 11; a++)
		emb_data.push_back(data[a]);
	for (unsigned int a = 16; a < 27; a++)
		emb_data.push_back(data[a]);
	for (unsigned int a = 32; a < 42; a++)
		emb_data.push_back(data[a]);
	for (unsigned int a = 48; a < 58; a++)
		emb_data.push_back(data[a]);
	for (unsigned int a = 64; a < 74; a++)
		emb_data.push_back(data[a]);
	for (unsigned int a = 80; a < 90; a++)
		emb_data.push_back(data[a]);
	for (unsigned int a = 96; a < 106; a++)
		emb_data.push_back(data[a]);

	// Convert 72 bits payload to 9 bytes LC
	for (int i = 0; i < 72; i += 8)
		d_lc.push_back((emb_data[i+0] << 7) + (emb_data[i+1] << 6) + (emb_data[i+2] << 5) + (emb_data[i+3] << 4) +
			       (emb_data[i+4] << 3) + (emb_data[i+5] << 2) + (emb_data[i+6] << 1) +  emb_data[i+7]);

	// Extract 5 bit received CRC
	uint16_t rxd_crc = (data[42] << 4) + (data[58] << 3) + (data[74] << 2) + (data[90] << 1) + data[106];

	// Calculate LC CRC and compare with received value
	uint16_t calc_crc = (d_lc[0] + d_lc[1] + d_lc[2] + d_lc[3] + d_lc[4] + d_lc[5] + d_lc[6] + d_lc[7] + d_lc[8]) % 31;
	if (rxd_crc == calc_crc) {
		d_lc_valid = true;
		if (d_debug >=10) {
			fprintf(stderr, "EMB LC: %02x %02x %02x %02x %02x %02x %02x %02x %02x\n",
				d_lc[0], d_lc[1], d_lc[2], d_lc[3], d_lc[4], d_lc[5],
				d_lc[6], d_lc[7], d_lc[8]);
		}
	}

	return d_lc_valid;
}

bool
dmr_slot::decode_embedded_sbrc(bool _pi) {
	// Invalidate previous parameter values
	if (_pi)
		d_rc_valid = false;
	else
		d_sb_valid = false;

	// De-interleave data and unpack downward in columns
	bool data[32];
	memset(data, 0, 32 * sizeof(bool));
	unsigned int b = 0;
	for (unsigned int a = 0; a < 32; a++) {
		data[b] = d_emb[(a*17)%32];
		b += 16;
		if (b > 31)
			b -= 31;
	}

	// Hamming (16,11,4) check first row only
	if (!CHamming::decode16114(data)) {
		return false;
	}

	// Parity and CRC checks depends on msg type
	if (_pi) { // RC Info
		for (int i = 0; i < 16; i++) {
			if ((data[i + 0] ^ data[i + 16]) == 0) { // odd parity
				return false;
			}
		}
		if (crc7((uint8_t*)data, 11) != 0) {
			return false;
		}
		d_rc = 0;
		for (int i = 0; i < 4; i++)
			d_rc = (d_rc << 1) + data[i];
		d_rc_valid = true;
		if (d_debug >=10) {
			fprintf(stderr, "EMB RC: %x\n", get_rc());
		}

	} else { // SB Info
		for (int i = 0; i < 16; i++) {
			if ((data[i + 0] ^ data[i + 16]) != 0) { // even parity
				return false;
			}
		}
		d_sb = 0;
		for (int i = 0; i < 11; i++)
			d_sb = (d_sb << 1) + data[i];
		d_sb_valid = true;
		if (d_debug >=10) {
			fprintf(stderr, "EMB SB: %03x\n", get_sb());
		}
	}

	return true;
}
