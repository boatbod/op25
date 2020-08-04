/* -*- c++ -*- */
/* 
 * Copyright 2020 Graham Norbury - gnorbury@bondcar.com
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

#ifndef INCLUDED_OP25_REPEATER_SUBCHANNEL_FRAMER_IMPL_H
#define INCLUDED_OP25_REPEATER_SUBCHANNEL_FRAMER_IMPL_H

#include <op25_repeater/subchannel_framer.h>

#include <gnuradio/msg_queue.h>
#include <sys/time.h>
#include "log_ts.h"

typedef std::deque<uint8_t> dibit_queue;

namespace gr {
    namespace op25_repeater {

        class subchannel_framer_impl : public subchannel_framer
        {
            private:
                int d_debug;
                int d_msgq_id;
                gr::msg_queue::sptr d_msg_queue;
                log_ts logts;

                // internal functions

            public:
                subchannel_framer_impl(int debug, int msgq_id, gr::msg_queue::sptr queue);
                ~subchannel_framer_impl();

                // Where all the action really happens
                int general_work(int noutput_items,
                        gr_vector_int &ninput_items,
                        gr_vector_const_void_star &input_items,
                        gr_vector_void_star &output_items);
        };

    } // namespace op25_repeater
} // namespace gr

#endif /* INCLUDED_OP25_REPEATER_SUBCHANNEL_FRAMER_IMPL_H */
