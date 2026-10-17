/* -*- c++ -*- */
/* 
 * Copyright 2009, 2010, 2011, 2012, 2013, 2014 Max H. Parke KA1RBI
 * 
 * This is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * This software is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this software; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

#ifndef INCLUDED_OP25_REPEATER_P25P1_VOICE_ENCODE_H
#define INCLUDED_OP25_REPEATER_P25P1_VOICE_ENCODE_H

#include <sys/time.h>
#include <stdint.h>
#include <vector>
#include <deque>

#include "op25_audio.h"
#include "imbe_vocoder/imbe_vocoder.h"

#include "imbe_decoder.h"
#include "software_imbe_decoder.h"

namespace gr {
  namespace op25_repeater {

    typedef std::vector<bool> bit_vector;
    class p25p1_voice_encode
    {
     private:
      // Nothing to declare in this block.

     public:
      p25p1_voice_encode(bool verbose_flag, int stretch_amt, op25_audio& udp, bool raw_vectors_flag, std::deque<uint8_t> &_output_queue);
      ~p25p1_voice_encode();
	void compress_samp(const int16_t * samp, int len);
      void set_gain_adjust(float gain_adjust);
      // Set the P25 NAC and Link Control at runtime (the defaults reproduce the
      // fixed NAC 0x293 and the preset LC).
      void set_nac(uint16_t nac);
      void set_lc(uint8_t lco, uint8_t mfid, uint8_t svcopt, uint8_t s,
                  uint16_t tgid, uint32_t dst, uint32_t src);
  private:
	uint16_t opt_nac;         // 12-bit P25 network access code (default 0x293)
	bool opt_lc_set;          // true once set_lc() ran: overlay a custom LC
	uint8_t  lc_lco, lc_mfid, lc_svcopt, lc_s;
	uint16_t lc_tgid;
	uint32_t lc_dst, lc_src;
	static const int RXBUF_MAX = 80;

	/* data items */
	int frame_cnt ;
	int write_bufp;
	char write_buf[512];
	struct timeval tv;
	struct timezone tz;
	struct timeval oldtv;
	int peak_amplitude;
	int peak;
	int samp_ct;
	char rxbuf[RXBUF_MAX];
	unsigned int codeword_ct ;
	int16_t sampbuf[FRAME];
	size_t sampbuf_ct ;
	int stretch_count ;
	bit_vector f_body;
	imbe_vocoder vocoder;
	op25_audio& op25audio;

	std::deque<uint8_t> &output_queue;

	bool opt_dump_raw_vectors;
	bool opt_verbose;
	int opt_stretch_amt;
	int opt_stretch_sign;
	/* local methods */
	void append_imbe_codeword(bit_vector& frame_body, int16_t frame_vector[], unsigned int& codeword_ct);
	void compress_frame(int16_t snd[]);
	void add_sample(int16_t samp);
    };

  } // namespace op25_repeater
} // namespace gr

#endif /* INCLUDED_OP25_REPEATER_P25P1_VOICE_ENCODE_H */
