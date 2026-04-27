/* -*- c++ -*- */
/* 
 * Copyright 2017 Max H. Parke KA1RBI
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


#ifndef INCLUDED_OP25_REPEATER_FRAME_ASSEMBLER_H
#define INCLUDED_OP25_REPEATER_FRAME_ASSEMBLER_H

#include <gnuradio/op25_repeater/api.h>
#include <gnuradio/block.h>
#include <gnuradio/msg_queue.h>
#include <cstdint>
#include <string>

namespace gr {
    namespace op25_repeater {

        /*!
         * \brief Decode-quality counters exposed by frame_assembler::get_decode_stats().
         *
         * tsbk_attempted : number of TSBK frames the demodulator handed to the FEC layer
         * tsbk_passed    : number of TSBKs that survived process_blocks + CRC and were
         *                  emitted as messages
         * pdu_attempted  : same, for multi-block PDUs
         * pdu_passed     : same
         * timeout_count  : number of M_P25_TIMEOUT events (sync lost)
         */
        struct OP25_REPEATER_API op25_decode_stats
        {
            uint64_t tsbk_attempted;
            uint64_t tsbk_passed;
            uint64_t pdu_attempted;
            uint64_t pdu_passed;
            uint64_t timeout_count;
        };

        /*!
         * \brief <+description of block+>
         * \ingroup op25_repeater
         *
         */
        class OP25_REPEATER_API frame_assembler : virtual public gr::block
        {
            public:
                typedef std::shared_ptr<frame_assembler> sptr;

                /*!
                 * \brief Return a shared_ptr to a new instance of op25_repeater::frame_assembler.
                 */
                static sptr make(const char* options, int debug, int msgq_id, gr::msg_queue::sptr queue);
                virtual void set_debug(int debug) {}
                virtual void control(const std::string& args) {}

                /*!
                 * \brief Return cumulative TSBK/PDU decode counts since construction.
                 *
                 * Survey-tool extension. Empty (zero) struct on non-P25 sync types
                 * (Smartnet, subchannel) since they don't run the P25 FDMA decoder.
                 */
                virtual op25_decode_stats get_decode_stats() const { return {}; }
        };

    } // namespace op25_repeater
} // namespace gr

#endif /* INCLUDED_OP25_REPEATER_FRAME_ASSEMBLER_H */

