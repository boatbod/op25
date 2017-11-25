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
#include <errno.h>
#include <sys/time.h>

#include "p25p2_duid.h"
#include "p25p2_sync.h"
#include "p25p2_tdma.h"
#include "p25p2_vf.h"
#include "mbelib.h"
#include "ambe.h"

static const int BURST_SIZE = 180;
static const int SUPERFRAME_SIZE = (12*BURST_SIZE);

static uint16_t crc12(const uint8_t bits[], unsigned int len) {
	uint16_t crc=0;
	static const unsigned int K = 12;
	static const uint8_t poly[K+1] = {1,1,0,0,0,1,0,0,1,0,1,1,1}; // p25 p2 crc 12 poly
	uint8_t buf[256];
	if (len+K > sizeof(buf)) {
		fprintf (stderr, "crc12: buffer length %u exceeds maximum %lu\n", len+K, sizeof(buf));
		return 0;
	}
	memset (buf, 0, sizeof(buf));
	for (int i=0; i<len; i++){
		buf[i] = bits[i];
	}
	for (int i=0; i<len; i++)
		if (buf[i])
			for (int j=0; j<K+1; j++)
				buf[i+j] ^= poly[j];
	for (int i=0; i<K; i++){
		crc = (crc << 1) + buf[len + i];
	}
	return crc ^ 0xfff;
}

static bool crc12_ok(const uint8_t bits[], unsigned int len) {
	uint16_t crc = 0;
	for (int i=0; i < 12; i++) {
		crc = (crc << 1) + bits[len+i];
	}
	return (crc == crc12(bits,len));
}

p25p2_tdma::p25p2_tdma(const op25_udp& udp, int slotid, int debug, std::deque<int16_t> &qptr, bool do_audio_output, bool do_nocrypt) :	// constructor
        op25udp(udp),
	write_bufp(0),
	tdma_xormask(new uint8_t[SUPERFRAME_SIZE]),
	symbols_received(0),
	packets(0),
	d_slotid(slotid),
	output_queue_decode(qptr),
	d_debug(debug),
	d_do_audio_output(do_audio_output),
        d_do_nocrypt(do_nocrypt),
	crc_errors(0),
        burst_id(-1),
        ESS_A(28,0),
        ESS_B(16,0),
        ess_algid(0x80),
        ess_keyid(0),
	p2framer()
{
	assert (slotid == 0 || slotid == 1);
	mbe_initMbeParms (&cur_mp, &prev_mp, &enh_mp);
}

bool p25p2_tdma::rx_sym(uint8_t sym)
{
	symbols_received++;
	return p2framer.rx_sym(sym);
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

int p25p2_tdma::process_mac_pdu(const uint8_t byte_buf[], const unsigned int len) 
{
	unsigned int opcode = (byte_buf[0] >> 5) & 0x7;
	unsigned int offset = (byte_buf[0] >> 2) & 0x7;

	// TODO: decode MAC PDU's more thoroughly
        switch (opcode)
        {
                case 1: // MAC_PTT
                        handle_mac_ptt(byte_buf, len);
                        break;

                case 2: // MAC_END_PTT
                        handle_mac_end_ptt(byte_buf, len);
                        break;

                case 3: // MAC_IDLE
                        handle_mac_idle(byte_buf, len);
                        break;

                case 4: // MAC_ACTIVE
                        handle_mac_active(byte_buf, len);
                        break;

                case 6: // MAC_HANGTIME
                        handle_mac_hangtime(byte_buf, len);
                        op25udp.send_audio_flag(op25_udp::DRAIN);
                        break;
        }
	// maps sacch opcodes into phase I duid values 
	static const int opcode_map[8] = {3, 5, 15, 15, 5, 3, 3, 3};
	return opcode_map[opcode];
}

void p25p2_tdma::handle_mac_ptt(const uint8_t byte_buf[], const unsigned int len) 
{
        if (d_debug >= 10) {
                uint32_t srcaddr = (byte_buf[13] << 16) + (byte_buf[14] << 8) + byte_buf[15];
                uint16_t grpaddr = (byte_buf[16] << 8) + byte_buf[17];
                fprintf(stderr, "MAC_PTT: srcaddr=%u, grpaddr=%u", srcaddr, grpaddr);
        }
        if (d_do_nocrypt) {
                for (int i = 0; i < 9; i++) {
                        ess_mi[i] = byte_buf[i+1];
                }
                ess_algid = byte_buf[10];
                ess_keyid = (byte_buf[11] << 8) + byte_buf[12];
                if (d_debug >= 10) {
                        fprintf(stderr, ", algid=%x, keyid=%x, mi=", ess_algid, ess_keyid);
                        for (int i = 0; i < 9; i++) {
                                fprintf(stderr,"%02x ", ess_mi[i]);
                        }
                }
        }
        if (d_debug >= 10) {
                fprintf(stderr, "\n");
        }

        reset_vb();
}

void p25p2_tdma::handle_mac_end_ptt(const uint8_t byte_buf[], const unsigned int len) 
{
        if (d_debug >= 10) {
                uint16_t colorcd = ((byte_buf[1] & 0x0f) << 8) + byte_buf[2];
                uint32_t srcaddr = (byte_buf[13] << 16) + (byte_buf[14] << 8) + byte_buf[15];
                uint16_t grpaddr = (byte_buf[16] << 8) + byte_buf[17];
                fprintf(stderr, "MAC_END_PTT: colorcd=0x%03x, srcaddr=%u, grpaddr=%u\n", colorcd, srcaddr, grpaddr);
        }

        op25udp.send_audio_flag(op25_udp::DRAIN);
}

void p25p2_tdma::handle_mac_idle(const uint8_t byte_buf[], const unsigned int len) 
{
        if (d_debug >= 10) {
                fprintf(stderr, "MAC_IDLE: ");
                decode_mac_msg(byte_buf, len);
                fprintf(stderr, "\n");
        }

        op25udp.send_audio_flag(op25_udp::DRAIN);
}

void p25p2_tdma::handle_mac_active(const uint8_t byte_buf[], const unsigned int len) 
{
        if (d_debug >= 10) {
                fprintf(stderr, "MAC_ACTIVE: ");
                decode_mac_msg(byte_buf, len);
                fprintf(stderr, "\n");
        }
}

void p25p2_tdma::handle_mac_hangtime(const uint8_t byte_buf[], const unsigned int len) 
{
        if (d_debug >= 10) {
                fprintf(stderr, "MAC_HANGTIME: ");
                decode_mac_msg(byte_buf, len);
                fprintf(stderr, "\n");
        }

        op25udp.send_audio_flag(op25_udp::DRAIN);
}


void p25p2_tdma::decode_mac_msg(const uint8_t byte_buf[], const unsigned int len) 
{
        if (d_debug >= 10) {
                uint16_t grpaddr, ch_t, ch_r;
                uint32_t srcaddr;
                uint8_t b1b2 = byte_buf[1] >> 6;
                uint8_t mco  = byte_buf[1] & 0x3f;
                fprintf(stderr, "b1b2=%x, mco=%02x", b1b2, mco);

		switch(mco)
                {
                        case 0x00: // Group Voice Channel Grant or Null Information Message
                                switch(b1b2)
                                {
                                        case 0x0: // Null
                                                break;
                                        case 0x1:
                                                ch_t = (byte_buf[3] << 8) + byte_buf[4];
                                                grpaddr = (byte_buf[5] << 8) + byte_buf[6];
                                                srcaddr = (byte_buf[7] << 16) + (byte_buf[8] << 8) + byte_buf[9];
                                                fprintf(stderr, ", srcaddr=%u, grpaddr=%u, ch=%u", srcaddr, grpaddr, ch_t);
                                                break;
                                        case 0x2:
                                                fprintf(stderr, ", len=%d", len);
                                                break;
                                        case 0x3:
                                                ch_t = (byte_buf[3] << 8) + byte_buf[4];
                                                ch_r = (byte_buf[5] << 8) + byte_buf[6];
                                                grpaddr = (byte_buf[7] << 8) + byte_buf[8];
                                                srcaddr = (byte_buf[9] << 16) + (byte_buf[10] << 8) + byte_buf[11];
                                                fprintf(stderr, ", srcaddr=%u, grpaddr=%u, ch_t=%u, ch_r=%u", srcaddr, grpaddr, ch_t, ch_r);
                                                break;
                                }
                                break;

                        case 0x01: // Group Voice Channel User Message
                                grpaddr = (byte_buf[3] << 8) + byte_buf[4];
                                srcaddr = (byte_buf[5] << 16) + (byte_buf[6] << 8) + byte_buf[7];
                                fprintf(stderr, ", srcaddr=%u, grpaddr=%u", srcaddr, grpaddr);
                                break;
                }
        }
}

int p25p2_tdma::handle_acch_frame(const uint8_t dibits[], bool fast) 
{
	int rc = -1;
	uint8_t bits[512];
	uint8_t byte_buf[32];
	unsigned int bufl=0;
	unsigned int len=0;
	if (fast) {
		for (int i=11; i < 11+36; i++) {
			bits[bufl++] = (dibits[i] >> 1) & 1;
			bits[bufl++] = dibits[i] & 1;
		}
		for (int i=48; i < 48+31; i++) {
			bits[bufl++] = (dibits[i] >> 1) & 1;
			bits[bufl++] = dibits[i] & 1;
		}
		for (int i=100; i < 100+32; i++) {
			bits[bufl++] = (dibits[i] >> 1) & 1;
			bits[bufl++] = dibits[i] & 1;
		}
		for (int i=133; i < 133+36; i++) {
			bits[bufl++] = (dibits[i] >> 1) & 1;
			bits[bufl++] = dibits[i] & 1;
		}
	} else {
		for (int i=11; i < 11+36; i++) {
			bits[bufl++] = (dibits[i] >> 1) & 1;
			bits[bufl++] = dibits[i] & 1;
		}
		for (int i=48; i < 48+84; i++) {
			bits[bufl++] = (dibits[i] >> 1) & 1;
			bits[bufl++] = dibits[i] & 1;
		}
		for (int i=133; i < 133+36; i++) {
			bits[bufl++] = (dibits[i] >> 1) & 1;
			bits[bufl++] = dibits[i] & 1;
		}
	}
	// FIXME: TODO: add RS decode
	if (fast)
		len = 144;
	else
		len = 168;
	if (crc12_ok(bits, len)) {
		for (int i=0; i<len/8; i++) {
			byte_buf[i] = (bits[i*8 + 0] << 7) + (bits[i*8 + 1] << 6) + (bits[i*8 + 2] << 5) + (bits[i*8 + 3] << 4) + (bits[i*8 + 4] << 3) + (bits[i*8 + 5] << 2) + (bits[i*8 + 6] << 1) + (bits[i*8 + 7] << 0);
		}
		rc = process_mac_pdu(byte_buf, len/8);
	} else {
		crc_errors++;
	}
	return rc;
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
	write_bufp = 0;
	for (int i=0; i < NSAMP_OUTPUT; i++) {
		if (samples->size() > 0) {
			snd = (int16_t)(samples->front());
			samples->pop_front();
		} else {
			snd = 0;
		}
		write_buf[write_bufp++] = snd & 0xFF ;
		write_buf[write_bufp++] = snd >> 8;
#if 0
		output_queue_decode.push_back(snd);
#endif
	}
	if (d_do_audio_output && (write_bufp >= 0)) { 
		op25udp.send_audio(write_buf, write_bufp);
		write_bufp = 0;
	}

	mbe_moveMbeParms (&cur_mp, &prev_mp);
	mbe_moveMbeParms (&cur_mp, &enh_mp);
}

int p25p2_tdma::handle_frame(void)
{
	uint8_t dibits[180];
	int rc;
	for (int i=0; i<sizeof(dibits); i++)
		dibits[i] = p2framer.d_frame_body[i*2+1] + (p2framer.d_frame_body[i*2] << 1);
	rc = handle_packet(dibits);
	return rc;
}

/* returns true if in sync and slot matches current active slot d_slotid */
int p25p2_tdma::handle_packet(const uint8_t dibits[]) 
{
	int rc = -1;
	static const int which_slot[] = {0,1,0,1,0,1,0,1,0,1,1,0};
	packets++;
	sync.check_confidence(dibits);
	if (!sync.in_sync())
		return -1;
	const uint8_t* burstp = &dibits[10];
	uint8_t xored_burst[BURST_SIZE - 10];
	int burst_type = duid.duid_lookup(duid.extract_duid(burstp));
	if (which_slot[sync.tdma_slotid()] != d_slotid) // active slot?
		return -1;
	for (int i=0; i<BURST_SIZE - 10; i++) {
		xored_burst[i] = burstp[i] ^ tdma_xormask[sync.tdma_slotid() * BURST_SIZE + i];
	}
	if (burst_type == 0 || burst_type == 6)	{       // 4V or 2V burst
                track_vb(burst_type);
                handle_4V2V_ess(&xored_burst[84]);
                if ( !d_do_nocrypt || !encrypted() ) {
                        handle_voice_frame(&xored_burst[11]);
                        handle_voice_frame(&xored_burst[48]);
                        if (burst_type == 0) {
                                handle_voice_frame(&xored_burst[96]);
                                handle_voice_frame(&xored_burst[133]);
                        }
                } else if (d_debug > 1) {
                        fprintf(stderr, "p25p2_tdma: encrypted audio algid(%0x)\n", ess_algid);
                }
		return -1;
	} else if (burst_type == 3) {                   // scrambled sacch
		rc = handle_acch_frame(xored_burst, 0);
	} else if (burst_type == 9) {                   // scrambled facch
		rc = handle_acch_frame(xored_burst, 1);
	} else if (burst_type == 12) {                  // unscrambled sacch
		rc = handle_acch_frame(burstp, 0);
	} else if (burst_type == 15) {                  // unscrambled facch
		rc = handle_acch_frame(burstp, 1);
	} else {
		// unsupported type duid
		return -1;
	}
	return rc;
}

void p25p2_tdma::handle_4V2V_ess(const uint8_t dibits[])
{
        if (d_debug >= 10) {
		fprintf(stderr, "%s_BURST ", (burst_id < 4) ? "4V" : "2V");
	}

        if ( !d_do_nocrypt ) {
                if (d_debug >= 10) {
	                fprintf(stderr, "\n");
                }
                return;
        }

        if (burst_id < 4) {
                for (int i=0; i < 12; i += 3) { // ESS-B is 4 hexbits / 12 dibits
                        ESS_B[(4 * burst_id) + (i / 3)] = (uint8_t) ((dibits[i] << 4) + (dibits[i+1] << 2) + dibits[i+2]);
                }
        }
        else {
                int i, j, k, ec;

                j = 0;
                for (i = 0; i < 28; i++) { // ESS-A is 28 hexbits / 84 dibits
                        ESS_A[i] = (uint8_t) ((dibits[j] << 4) + (dibits[j+1] << 2) + dibits[j+2]);
                        j = (i == 15) ? (j + 4) : (j + 3);  // skip dibit containing DUID#3
                }

                ec = rs28.decode(ESS_B, ESS_A);

                if (ec >= 0) { // save info if good decode
                        ess_algid = (ESS_B[0] << 2) + (ESS_B[1] >> 4);
                        ess_keyid = ((ESS_B[1] & 15) << 12) + (ESS_B[2] << 6) + ESS_B[3]; 

                        j = 0;
                        for (i = 0; i < 9;) {
                                 ess_mi[i++] = (uint8_t)  (ESS_B[j+4]         << 2) + (ESS_B[j+5] >> 4);
                                 ess_mi[i++] = (uint8_t) ((ESS_B[j+5] & 0x0f) << 4) + (ESS_B[j+6] >> 2);
                                 ess_mi[i++] = (uint8_t) ((ESS_B[j+6] & 0x03) << 6) +  ESS_B[j+7];
                                 j += 4;
                        }
                }
        }     

        if (d_debug >= 10) {
                fprintf(stderr, "ESS: algid=%x, keyid=%x, mi=", ess_algid, ess_keyid);        
                for (int i = 0; i < 9; i++) {
                        fprintf(stderr,"%02x ", ess_mi[i]);
                }
		fprintf(stderr, "\n");
        }
}

