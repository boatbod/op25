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

#ifndef INCLUDED_OP25_REPEATER_P25_FRAME_ASSEMBLER_IMPL_H
#define INCLUDED_OP25_REPEATER_P25_FRAME_ASSEMBLER_IMPL_H

#include <op25_repeater/p25_frame_assembler.h>

#include <gnuradio/msg_queue.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <deque>

#include "p25_framer.h"

typedef std::deque<uint8_t> dibit_queue;

namespace gr {
  namespace op25_repeater {

    class p25_frame_assembler_impl : public p25_frame_assembler
    {
     private:

  void init_sock(const char* udp_host, int udp_port);

  // internal functions
	typedef std::vector<bool> bit_vector;
	bool header_codeword(uint64_t acc, uint32_t& nac, uint32_t& duid);
	void proc_voice_unit(bit_vector& frame_body) ;
	void process_duid(uint32_t const duid, uint32_t const nac, uint8_t const buf[], int const len);
  // internal instance variables and state
	int write_bufp;
	int write_sock;
	struct sockaddr_in write_sock_addr;
	char write_buf[512];
	const char* d_udp_host;
	int d_port;
	int d_debug;
	bool d_do_imbe;
	bool d_do_output;
	bool d_do_msgq;
	gr::msg_queue::sptr d_msg_queue;
	dibit_queue symbol_queue;
	p25_framer* framer;
	struct timeval last_qtime;

 public:
   virtual void forecast(int nof_output_items, gr_vector_int &nof_input_items_reqd);
      // Nothing to declare in this block.

     public:
      p25_frame_assembler_impl(const char* udp_host, int port, int debug, bool do_imbe, bool do_output, bool do_msgq, gr::msg_queue::sptr queue);
      ~p25_frame_assembler_impl();

      // Where all the action really happens

      int general_work(int noutput_items,
		       gr_vector_int &ninput_items,
		       gr_vector_const_void_star &input_items,
		       gr_vector_void_star &output_items);
    };

  } // namespace op25_repeater
} // namespace gr

#endif /* INCLUDED_OP25_REPEATER_P25_FRAME_ASSEMBLER_IMPL_H */
