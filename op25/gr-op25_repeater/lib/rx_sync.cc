// P25 Decoder (C) Copyright 2013, 2014, 2015, 2016, 2017 Max H. Parke KA1RBI
//             (C) Copyright 2019, 2020, 2021, 2022 Graham J. Norbury
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
#include <fstream>
#include <deque>
#include <assert.h>
#include <errno.h>
#include <unistd.h>

#include "rx_sync.h"

#include <nlohmann/json.hpp>

#include "bit_utils.h"

#include "check_frame_sync.h"

#include "p25p2_vf.h"
#include "mbelib.h"
#include "ambe.h"
#include "rs.h"
#include "crc16.h"

#include "p25_frame.h"
#include "op25_imbe_frame.h"
#include "software_imbe_decoder.h"
#include "op25_audio_wrapper.h"
#include "op25_audio.h"
#include "op25_msg_types.h"

namespace gr {
    namespace op25_repeater {

void rx_sync::cbuf_insert(const uint8_t c) {
	d_cbuf[d_cbuf_idx] = c;
	d_cbuf[d_cbuf_idx + CBUF_SIZE] = c;
	d_cbuf_idx = (d_cbuf_idx + 1) % CBUF_SIZE;
}

void rx_sync::reset_timer(void) {
	sync_timer.reset();
	p25fdma.reset_timer();
}

void rx_sync::set_destination(const char* dest) {
	d_audio = &op25_audio_wrapper::instance().get_audio(dest, logts, d_debug, d_msgq_id);
    p25fdma.set_destination(d_audio);
    p25tdma.set_destination(d_audio);
}

void rx_sync::sync_reset(void) {
	if (d_debug >= 10) {
		fprintf(stderr, "%s rx_sync::sync_reset:\n", logts.get(d_msgq_id));
	}

	// Sync counters and registers reset
	d_symbol_count = 0;
    //d_cbuf_idx = 0; // never reset, just let it wrap
	d_rx_count = 0;
	d_threshold = 0;
	d_shift_reg = 0;
	d_sync_reg = 0;
	d_fs = 0;
	d_expires = 0;
	d_current_type = RX_TYPE_NONE;
	d_fragment_len = MODE_DATA[d_current_type].fragment_len;

	// Audio reset
	for (int chan = 0; chan <= 1; chan++) {
		if (d_unmute_until[chan]) {
			d_unmute_until[chan] = 0;
			d_audio->send_audio_flag_channel(op25_audio::DRAIN, chan);
			if (d_debug >= 10) {
				fprintf(stderr, "%s mute channel(%d)\n", logts.get(d_msgq_id), chan);
			}
		}
	}

	// Timers reset
	reset_timer();
}

void rx_sync::call_end(void) {
	p25fdma.call_end();
	p25tdma.call_end();
}

void rx_sync::crypt_reset(void) {
	p25fdma.crypt_reset();
	p25tdma.crypt_reset();
}

void rx_sync::crypt_key(uint16_t keyid, uint8_t algid, const std::vector<uint8_t> &key) {
	p25fdma.crypt_key(keyid, algid, key);
	p25tdma.crypt_key(keyid, algid, key);
}

void rx_sync::set_nac(int nac) {
    p25fdma.set_nac(nac);
    p25tdma.set_nac(nac);
}

void rx_sync::set_slot_mask(int mask) {
	if (mask == d_slot_mask)
		return;

	if (d_debug >= 10) {
		fprintf(stderr, "%s rx_sync::set_slot_mask: current(%d), new(%d)\n", logts.get(d_msgq_id), d_slot_mask, mask);
	}

	if (d_slot_mask == 4) {
		reset_timer();
		sync_reset();
	}
	d_slot_mask = mask;
	p25tdma.set_slotid(mask & 0x1);
}

void rx_sync::set_xormask(const char* p) {
	p25tdma.set_xormask(p);
}

void rx_sync::set_slot_key(int mask) {
	if (d_debug >= 10) {
		fprintf(stderr, "%s rx_sync::set_slot_key: current(%d), new(%d)\n", logts.get(d_msgq_id), d_slot_key, mask);
	}
	d_slot_key = mask;
}

void rx_sync::crypt_behavior(int behavior) {
	d_behavior = behavior;
	p25fdma.crypt_behavior(behavior);
	p25tdma.crypt_behavior(behavior);
}

void rx_sync::set_debug(int debug) {
    d_debug = debug;
	d_audio->set_debug(debug);
	p25fdma.set_debug(debug);
	p25tdma.set_debug(debug);
}

// Build the FEC stats JSON envelope. Counters are monotonic since
// construction; consumers diff between samples to compute rates.
std::string rx_sync::get_fec_stats_json() const {
	nlohmann::json envelope = {
		{"cmd", "fec_stats"},
		{"schema", 1},
		{"data", {
			{"control", {
				{"tsbk_attempted",  p25fdma.stat_tsbk_attempted()},
				{"tsbk_crc_passed", p25fdma.stat_tsbk_passed()},
				{"pdu_attempted",   p25fdma.stat_pdu_attempted()},
				{"pdu_crc_passed",  p25fdma.stat_pdu_passed()},
			}},
			{"sync", {
				{"losses", p25fdma.stat_timeouts()},
			}},
		}},
	};
	return envelope.dump();
}

rx_sync::rx_sync(const char * options, log_ts& logger, int debug, int msgq_id, gr::msg_queue::sptr queue) :	// constructor
	sync_timer(op25_timer(1000000)),
	d_symbol_count(0),
	d_sync_reg(0),
	d_fs(0),
    d_cbuf(),
	d_cbuf_idx(0),
	d_current_type(RX_TYPE_NONE),
	d_rx_count(0),
	d_expires(0),
	d_slot_mask(3),
	d_slot_key(0),
	d_audio(&op25_audio_wrapper::instance().get_audio(options, logger, debug, msgq_id)),
	p25fdma(d_audio, logger, debug, true, false, true, queue, d_output_queue[0], true, msgq_id),
	p25tdma(d_audio, logger, 0, debug, true, queue, d_output_queue[0], true, msgq_id),
	d_msgq_id(msgq_id),
	d_msg_queue(queue),
	d_stereo(true),
	d_debug(debug),
    logts(logger)
{
	if (msgq_id >= 0)
		d_stereo = false; // single channel audio for trunking

	mbe_initMbeParms (&cur_mp[0], &prev_mp[0], &enh_mp[0]);
	mbe_initMbeParms (&cur_mp[1], &prev_mp[1], &enh_mp[1]);
	mbe_initErrParms (&errs_mp[0]);
	mbe_initErrParms (&errs_mp[1]);
	mbe_initToneParms (&tone_mp[0]);
	mbe_initToneParms (&tone_mp[1]);
	mbe_err_cnt[0] = 0;
	mbe_err_cnt[1] = 0;
	sync_reset();
}

rx_sync::~rx_sync()	// destructor
{
}

void rx_sync::stop() // called prior to shutdown
{
    d_audio->stop();
}

void rx_sync::sync_timeout(rx_types proto)
{
	if (d_debug >= 10) {
		fprintf(stderr, "%s rx_sync::sync_timeout: protocol %s\n", logts.get(d_msgq_id), MODE_DATA[proto].type);
	}
	if ((d_msgq_id >= 0) && (!d_msg_queue->full_p())) {
		std::string m_buf;
		gr::message::sptr msg;
		switch(proto) {
		case RX_TYPE_NONE:
		case RX_TYPE_P25P1:
		case RX_TYPE_P25P2:
			msg = gr::message::make_from_string(m_buf, get_msg_type(PROTOCOL_P25, M_P25_TIMEOUT), (d_msgq_id << 1), logts.get_ts());
            if (!d_msg_queue->full_p())
				d_msg_queue->insert_tail(msg);
			break;
		default:
			break;
		}
    }
	reset_timer();
}

void rx_sync::sync_established(rx_types proto)
{
	if (d_debug >= 10) {
		fprintf(stderr, "%s rx_sync::sync_established: protocol %s\n", logts.get(d_msgq_id), MODE_DATA[proto].type);
	}
	if ((d_msgq_id >= 0) && (!d_msg_queue->full_p())) {
		std::string m_buf;
		gr::message::sptr msg;
		switch(proto) {
		case RX_TYPE_NONE:
            break;
		case RX_TYPE_P25P1:
		case RX_TYPE_P25P2:
			msg = gr::message::make_from_string(m_buf, get_msg_type(PROTOCOL_P25, M_P25_SYNC_ESTAB), (d_msgq_id << 1), logts.get_ts());
            if (!d_msg_queue->full_p())
				d_msg_queue->insert_tail(msg);
			break;
		default:
			break;
        }
    }
}

void rx_sync::codeword(const uint8_t* cw, const enum codeword_types codeword_type, int slot_id) {
	bool do_fullrate = false;
	bool do_silence = false;
	bool do_tone = false;
	packed_codeword p_cw;
	voice_codeword fullrate_cw(voice_codeword_sz);

	switch(codeword_type) {
	case CODEWORD_P25P2:
		break; // Not used; handled by p25p2_tdma
	case CODEWORD_P25P1:
		break; // Not used; handled by p25p1_fdma
	}
	if (do_tone) {
		d_software_decoder[slot_id].decode_tone(tone_mp[slot_id].ID, tone_mp[slot_id].AD, &tone_mp[slot_id].n);
	} else {
		mbe_moveMbeParms (&cur_mp[slot_id], &prev_mp[slot_id]);
		if (do_fullrate) {
			d_software_decoder[slot_id].decode(fullrate_cw);
		} else {	/* halfrate */
			if (!do_silence) {
				d_software_decoder[slot_id].decode_tap(cur_mp[slot_id].L, 0, cur_mp[slot_id].w0, &cur_mp[slot_id].Vl[1], &cur_mp[slot_id].Ml[1]);
			}
		}
	}
	audio_samples *samples = d_software_decoder[slot_id].audio();
	float snd;
	int16_t samp_buf[NSAMP_OUTPUT];
	for (int i=0; i < NSAMP_OUTPUT; i++) {
		if ((!do_silence) && samples->size() > 0) {
			snd = samples->front();
			samples->pop_front();
		} else {
			snd = 0;
		}
		if (do_fullrate)
			snd *= 32768.0;
		samp_buf[i] = snd;
	}
	output(samp_buf, slot_id);
}

void rx_sync::output(int16_t * samp_buf, const ssize_t slot_id) {
	if (d_stereo) 
		d_audio->send_audio_channel(samp_buf, NSAMP_OUTPUT * sizeof(int16_t), slot_id);
	else
		d_audio->send_audio(samp_buf, NSAMP_OUTPUT * sizeof(int16_t));
}

void rx_sync::rx_sym(const uint8_t sym) {
	enum rx_types sync_detected = RX_TYPE_NONE;
	int excess_count = 0;

    if (d_slot_mask & 0x4) { // Setting bit 3 of slot mask disables framing for idle receiver 
        return;
    }

	d_symbol_count ++;
	d_sync_reg = (d_sync_reg << 2) | (sym & 3);
	for (int i = 0; i < KNOWN_MAGICS; i++) {
		if (check_frame_sync(SYNC_MAGIC[i].magic ^ d_sync_reg, (SYNC_MAGIC[i].type == d_current_type) ? d_threshold : 0, MODE_DATA[SYNC_MAGIC[i].type].sync_len)) {
			sync_detected = (enum rx_types) SYNC_MAGIC[i].type;
            d_fs = SYNC_MAGIC[i].magic;
			break;
		}
	}
	cbuf_insert(sym);
	if (d_current_type == RX_TYPE_NONE && sync_detected == RX_TYPE_NONE) {
		if (sync_timer.expired()) {
			sync_timeout(RX_TYPE_NONE);
		}
		return;
        }
	d_rx_count ++;
	if (sync_detected != RX_TYPE_NONE) {
		if (d_current_type != sync_detected) {
			d_current_type = sync_detected;
			d_expires = d_symbol_count + MODE_DATA[d_current_type].expiration;
			d_rx_count = MODE_DATA[d_current_type].sync_offset + (MODE_DATA[d_current_type].sync_len >> 1);
			d_fragment_len = MODE_DATA[d_current_type].fragment_len;
            sync_established(d_current_type);
		}
		if ((d_fragment_len != MODE_DATA[d_current_type].fragment_len) && (d_rx_count < d_fragment_len)) { // P25 variable length frames
			excess_count = MODE_DATA[d_current_type].sync_offset + (MODE_DATA[d_current_type].sync_len >> 1);
			d_fragment_len = d_rx_count - excess_count;
		}
		else if (d_rx_count != MODE_DATA[d_current_type].sync_offset + (MODE_DATA[d_current_type].sync_len >> 1)) {
			if (d_debug >= 10) {
				fprintf(stderr, "%s resync at count %d for protocol %s (expected count %d)\n", logts.get(d_msgq_id), d_rx_count, MODE_DATA[d_current_type].type, (MODE_DATA[d_current_type].sync_offset + (MODE_DATA[d_current_type].sync_len >> 1)));
            }
			sync_reset();
			d_rx_count = MODE_DATA[d_current_type].sync_offset + (MODE_DATA[d_current_type].sync_len >> 1);
		} else {
			d_threshold = std::min(d_threshold + 1, 2);
		}
		d_expires = d_symbol_count + MODE_DATA[d_current_type].expiration;
	}
	if ((d_current_type != RX_TYPE_NONE) && (d_symbol_count >= d_expires)) {
		if (d_debug >= 10) {
			fprintf(stderr, "%s %s: sync expiry, symbol %d\n", logts.get(d_msgq_id), MODE_DATA[d_current_type].type, d_symbol_count);
        }
        sync_reset();
		return;
	}
	if (d_rx_count < d_fragment_len)
		return;

	d_rx_count = excess_count;	// excess symbols may be carried forward to next frame
	int start_idx = d_cbuf_idx + CBUF_SIZE - d_fragment_len - excess_count;
	assert (start_idx >= 0);
	uint8_t * symbol_ptr = d_cbuf+start_idx;
	switch (d_current_type) {
	case RX_TYPE_NONE:
		break;
	case RX_TYPE_P25P1:
        if (d_fragment_len == MODE_DATA[d_current_type].fragment_len) {
		    int frame_len = p25fdma.load_nid(symbol_ptr, MODE_DATA[d_current_type].fragment_len, d_fs);
            if (frame_len > 0) {
                d_fragment_len = frame_len;                             // expected length of remainder of this frame
            } else {
                sync_reset();
            }
        } else {
		    p25fdma.load_body(symbol_ptr, d_fragment_len);
            d_fragment_len = MODE_DATA[d_current_type].fragment_len;    // accumulate next NID
        }
		break;
	case RX_TYPE_P25P2:
		p25tdma.handle_packet(symbol_ptr, d_fs); // passing 180 dibit packets is faster than bit-shuffling via p25tdma::rx_sym()
        p25fdma.reset_timer();                   // reset FDMA timer in case of long TDMA transmissions
		break;
	case RX_N_TYPES:
		assert(0==1);     /* should not occur */
		break;
	}
}

void rx_sync::dump_buffer() {
    std::string fname = "ch" + std::to_string(d_msgq_id) + "-dump.bin";
    std::fstream file(fname.c_str(), std::ios::out | std::ios::binary);
    file.write((const char *)(d_cbuf + d_cbuf_idx + 1), CBUF_SIZE);
    fprintf(stderr, "%s rx_sync::dump_buffer: %s\n", logts.get(d_msgq_id), fname.c_str());
}

    } // end namespace op25_repeater
} // end namespace gr
