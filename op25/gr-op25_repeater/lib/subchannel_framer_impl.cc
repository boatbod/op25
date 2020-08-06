/* -*- c++ -*- */
/* 
 * Copyright 2012 Nick Foster (gr-smartnet)
 * Copyright 2020 Graham J. Norbury - gnorbury@bondcar.com
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

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <gnuradio/io_signature.h>
#include "subchannel_framer_impl.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <vector>
#include <sys/time.h>

namespace gr {
    namespace op25_repeater {

        subchannel_framer::sptr
            subchannel_framer::make(int debug, int msgq_id, gr::msg_queue::sptr queue)
            {
                return gnuradio::get_initial_sptr
                    (new subchannel_framer_impl(debug, msgq_id, queue));
            }

        /*
         * Our public destructor
         */
        subchannel_framer_impl::~subchannel_framer_impl()
        {
        }

        static const int MIN_IN = 1;	// mininum number of input streams
        static const int MAX_IN = 1;	// maximum number of input streams

        /*
         * The private constructor
         */
        subchannel_framer_impl::subchannel_framer_impl(int debug, int msgq_id, gr::msg_queue::sptr queue)
            : gr::block("subchannel_framer",
                    gr::io_signature::make (MIN_IN, MAX_IN, sizeof (char)),
                    gr::io_signature::make (0, 0, 0)),
            d_debug(debug),
            d_msgq_id(msgq_id),
            d_msg_queue(queue)
        {
        }

        int 
            subchannel_framer_impl::general_work (int noutput_items,
                    gr_vector_int &ninput_items,
                    gr_vector_const_void_star &input_items,
                    gr_vector_void_star &output_items)
            {
                const char *in = (const char *) input_items[0];

                //fprintf(stderr, "%s subchannel_framer_impl::general_work: ninput_items=%d\n", logts.get(d_msgq_id), ninput_items[0]);
                for(int i=0; i < noutput_items; i++) {
                    if(in[i] & 0x02) {
                        //if(noutput_items-i >= 21) {
                        //if(in[i+21] & 0x02) {
                        //out[i] = in[i];
                        fprintf(stderr, "Subchannel frame data: ");
                        for(int q = 0; q < 42; q++) {
                            if(in[i+q-5] & 0x01) fprintf(stderr,"1");
                            else fprintf(stderr,"0");
                        }
                        fprintf(stderr,"\n");
                        //				}
                        //	else out[i] = in[i] & 0x01;
                        //} else return i; //weren't enough to validate it, so go back for more
                    }
                }

                consume_each(ninput_items[0]);
                // Tell runtime system how many output items we produced.
                return 0;
            }

    } /* namespace op25_repeater */
} /* namespace gr */
