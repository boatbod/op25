/* -*- c++ -*- */
/* 
 * Copyright 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017 Max H. Parke KA1RBI 
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
#include "frame_assembler_impl.h"
#include "rx_sync.h"
#include "rx_smartnet.h"
#include "rx_subchannel.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <vector>
#include <sys/time.h>

#include <nlohmann/json.hpp>
using json = nlohmann::json;

namespace gr {
    namespace op25_repeater {

        // Accept and dispatch JSON formatted commands from python
        void frame_assembler_impl::control(const std::string& args) {
            json j = json::parse(args);
            std::string cmd = j["cmd"].get<std::string>();
            if (d_debug >= 10) {
                fprintf(stderr, "%s frame_assembler_impl::control: cmd(%s), args(%s)\n", logts.get(d_msgq_id), cmd.c_str(), args.c_str());
            }
            if        (cmd == "set_xormask") {
                if (d_sync)
                    d_sync->set_xormask(j["xormask"].get<std::string>().c_str());
            } else if (cmd == "set_slotid") {
                if (d_sync)
                d_sync->set_slot_mask(j["slotid"].get<int>());
            } else if (cmd == "set_slotkey") {
                if (d_sync)
                    d_sync->set_slot_key(j["slotkey"].get<int>());
            } else if (cmd == "set_nac") {
                if (d_sync)
                    d_sync->set_nac(j["nac"].get<int>());
            } else if (cmd == "sync_reset") {
                if (d_sync)
                    d_sync->sync_reset();
            } else if (cmd == "call_end") {
                if (d_sync)
                    d_sync->call_end();
            } else if (cmd == "crypt_reset") {
                if (d_sync)
                    d_sync->crypt_reset();
            } else if (cmd == "crypt_key") {
                if (d_sync)
                    d_sync->crypt_key(j["keyid"].get<uint16_t>(), j["keyid"].get<uint8_t>(), j["key"].get<std::vector<uint8_t>>());
            } else if (cmd == "set_debug") {
                if (d_sync)
                    d_sync->set_debug(j["debug"].get<int>());
            } else {
                if (d_debug >= 10) {
                    fprintf(stderr, "%s frame_assembler_impl::control: unhandled cmd(%s)\n", logts.get(d_msgq_id), cmd.c_str());
                }
            }
        }

        void frame_assembler_impl::set_debug(int debug) {
            if (d_sync)
                d_sync->set_debug(debug);
        }

        frame_assembler::sptr
            frame_assembler::make(const char* options, int debug, int msgq_id, gr::msg_queue::sptr queue)
            {
                return gnuradio::get_initial_sptr
                    (new frame_assembler_impl(options, debug, msgq_id, queue));
            }

        /*
         * Our public destructor
         */
        frame_assembler_impl::~frame_assembler_impl()
        {
            if (d_sync)
                delete d_sync;
        }

        static const int MIN_IN = 1;	// mininum number of input streams
        static const int MAX_IN = 1;	// maximum number of input streams

        /*
         * The private constructor
         */
        frame_assembler_impl::frame_assembler_impl(const char* options, int debug, int msgq_id, gr::msg_queue::sptr queue)
            : gr::block("frame_assembler",
                    gr::io_signature::make (MIN_IN, MAX_IN, sizeof (char)),
                    gr::io_signature::make (0, 0, 0)),
            d_debug(debug),
            d_msgq_id(msgq_id),
            d_msg_queue(queue),
            d_sync(NULL)
        {
            if (strcasecmp(options, "smartnet") == 0)
                d_sync = new rx_smartnet(options, logts, debug, msgq_id, queue);
            else if (strcasecmp(options, "subchannel") == 0)
                d_sync = new rx_subchannel(options, logts, debug, msgq_id, queue);
            else
                d_sync = new rx_sync(options, logts, debug, msgq_id, queue);
        }

        int 
            frame_assembler_impl::general_work (int noutput_items,
                    gr_vector_int &ninput_items,
                    gr_vector_const_void_star &input_items,
                    gr_vector_void_star &output_items)
            {

                const uint8_t *in = (const uint8_t *) input_items[0];

                if (d_sync) {
                    for (int i=0; i<ninput_items[0]; i++) {
                        d_sync->rx_sym(in[i]);
                    }
                }
                consume_each(ninput_items[0]);
                // Tell runtime system how many output items we produced.
                return 0;
            }

    } /* namespace op25_repeater */
} /* namespace gr */
