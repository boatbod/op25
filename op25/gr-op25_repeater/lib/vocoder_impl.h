/* -*- c++ -*- */
/* 
 * Copyright 2009, 2010, 2011, 2012, 2013 KA1RBI
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

#ifndef INCLUDED_OP25_REPEATER_VOCODER_IMPL_H
#define INCLUDED_OP25_REPEATER_VOCODER_IMPL_H

#include <op25_repeater/vocoder.h>

#include <sys/time.h>
#include <netinet/in.h>
#include <stdint.h>
#include <vector>
#include <deque>

#include "imbe_vocoder/imbe_vocoder.h"

#include "imbe_decoder.h"
#include "software_imbe_decoder.h"

namespace gr {
  namespace op25_repeater {

    typedef std::vector<bool> bit_vector;
    class vocoder_impl : public vocoder
    {
     private:
      // Nothing to declare in this block.

     public:
      vocoder_impl(bool encode_flag, bool verbose_flag, int stretch_amt, char* udp_host, int udp_port, bool raw_vectors_flag);
      ~vocoder_impl();

      void forecast (int noutput_items, gr_vector_int &ninput_items_required);

      int general_work(int noutput_items,
		       gr_vector_int &ninput_items,
		       gr_vector_const_void_star &input_items,
		       gr_vector_void_star &output_items);

      int general_work_encode (int noutput_items,
		    gr_vector_int &ninput_items,
		    gr_vector_const_void_star &input_items,
		    gr_vector_void_star &output_items);
      int general_work_decode (int noutput_items,
		    gr_vector_int &ninput_items,
		    gr_vector_const_void_star &input_items,
		    gr_vector_void_star &output_items);

  private:
	static const int RXBUF_MAX = 80;

	/* data items */
	int frame_cnt ;
	int write_sock;
	struct sockaddr_in write_sock_addr;
	int write_bufp;
	char write_buf[512];
	struct timeval tv;
	struct timezone tz;
	struct timeval oldtv;
	int peak_amplitude;
	int peak;
	int samp_ct;
	char rxbuf[RXBUF_MAX];
	int rxbufp ;
	unsigned int codeword_ct ;
	int16_t sampbuf[FRAME];
	size_t sampbuf_ct ;
	int stretch_count ;
	uint8_t save_l;
	bit_vector f_body;
	imbe_vocoder vocoder;
	software_imbe_decoder software_decoder;
	bool d_software_imbe_decoder;

	std::deque<uint8_t> output_queue;
	std::deque<uint16_t> output_queue_decode;

	bool opt_encode_flag;
	bool opt_dump_raw_vectors;
	bool opt_verbose;
	int opt_stretch_amt;
	int opt_stretch_sign;
	int opt_udp_port;
	/* local methods */
	void append_imbe_codeword(bit_vector& frame_body, int16_t frame_vector[], unsigned int& codeword_ct);
	void rxchar(char c);
	void compress_frame(int16_t snd[]);
	void add_sample(int16_t samp);
	void compress_samp(int16_t samp);
	void init_sock(char* udp_host, int udp_port);
    };

  } // namespace op25_repeater
} // namespace gr

#endif /* INCLUDED_OP25_REPEATER_VOCODER_IMPL_H */
