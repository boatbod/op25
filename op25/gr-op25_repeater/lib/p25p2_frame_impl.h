/* -*- c++ -*- */
/* 
 * Copyright 2014 Max H. Parke KA1RBI
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

#ifndef INCLUDED_OP25_REPEATER_P25P2_FRAME_IMPL_H
#define INCLUDED_OP25_REPEATER_P25P2_FRAME_IMPL_H

#include <stdint.h>
#include <deque>
#include <gnuradio/msg_queue.h>
#include <op25_repeater/p25p2_frame.h>
#include "p25p2_framer.h"
#include "p25p2_tdma.h"

namespace gr {
  namespace op25_repeater {

    class p25p2_frame_impl : public p25p2_frame
    {
     private:
      // Nothing to declare in this block.
      p25p2_framer p2framer;
      p25p2_tdma p2tdma;
      std::deque<int16_t> output_queue_decode;
	bool d_do_msgq;
	gr::msg_queue::sptr d_msg_queue;
      void queue_msg(int duid);

     public:
	typedef std::vector<bool> bit_vector;
      p25p2_frame_impl(int debug, int slotid, bool do_msgq, gr::msg_queue::sptr msgq);
      ~p25p2_frame_impl();
      void handle_p2_frame(const bit_vector& bits);
      void set_xormask(const char*p);
      void set_slotid(int slotid);

      // Where all the action really happens
      void forecast (int noutput_items, gr_vector_int &ninput_items_required);

      int general_work(int noutput_items,
		       gr_vector_int &ninput_items,
		       gr_vector_const_void_star &input_items,
		       gr_vector_void_star &output_items);
    };

  } // namespace op25_repeater
} // namespace gr

#endif /* INCLUDED_OP25_REPEATER_P25P2_FRAME_IMPL_H */
