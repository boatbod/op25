// Smartnet Decoder (C) Copyright 2020 Graham J. Norbury
// Inspiration and code fragments from mottrunk.txt and gr-smartnet
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


#include "rx_subchannel.h"
#include "op25_msg_types.h"

namespace gr{
    namespace op25_repeater{

        // constructor
        rx_subchannel::rx_subchannel(const char * options, int debug, int msgq_id, gr::msg_queue::sptr queue) :
            d_debug(debug),
            d_cbuf_idx(0),
            d_msgq_id(msgq_id),
            d_msg_queue(queue),
            sync_timer(op25_timer(1000000)) {
                sync_reset();
            }

        // destructor
        rx_subchannel::~rx_subchannel() {
        }

        // symbol receiver and framer
        void rx_subchannel::rx_sym(const uint8_t sym) {
            bool crc_ok;
            bool sync_detected = false;
            d_symbol_count ++;
            d_sync_reg = ((d_sync_reg << 1) & 0x1f ) | (sym & 1);
            if ((d_sync_reg ^ (uint8_t)SUBCHANNEL_SYNC_MAGIC) == 0) {
                sync_detected = true;
            }
            cbuf_insert(sym);
            d_rx_count ++;

            fprintf(stderr, "%d", sym);
            if (sync_detected) {
                fprintf(stderr, "\n");
                d_rx_count = 0;
                d_sync_reg = 0x1f;
            }
            return;

            //if (sync_timer.expired()) {                                                 // Check for timeout
            //    d_in_sync = false;
            //    d_rx_count = 0;
            //    sync_timeout();
            //    return;
            //}

            //if (sync_detected && !d_in_sync) {                                          // First sync marks starts data collection
            //    d_in_sync = true;
            //    d_rx_count = 0;
            //    fprintf(stderr, "in sync\n");
            //    return;
            //}

            //if (!d_in_sync || (d_in_sync && (d_rx_count < SUBCHANNEL_FRAME_LENGTH))) {  // Collect up to expected data frame length
            //    return;                                                                 // any early sync sequence is treated as data
            //}
            
            //if (!sync_detected) {                                                       // Frame must end with sync for to be valid
            //    if (d_debug >= 10) {
            //        fprintf(stderr, "%s SUBCHANNEL sync lost\n", logts.get(d_msgq_id));
            //    }
            //    d_in_sync = false;
            //    d_rx_count = 0;
            //    return;
            //}

            d_rx_count = 0;
            int start_idx = d_cbuf_idx;
            assert (start_idx >= 0);
            uint8_t * symbol_ptr = d_cbuf + start_idx;                                  // Start of data frame in circular buffer
            uint16_t subchannel_data = 0;
            for (int i = 0; i < SUBCHANNEL_PAYLOAD_LENGTH; i++) {
                subchannel_data = (subchannel_data << 1) | *(symbol_ptr + i);
            }

            //if ((d_msgq_id < 0) && (d_debug >= 10)) {                                   // Log if no trunking, else trunking can do it
                fprintf(stderr, "%s SUBCHANNEL data: 0x%02x\n", logts.get(d_msgq_id), subchannel_data);
            //}

            //send_msg((const char*)d_pkt.raw_data);                                      // Send complete subchannel data word to trunking
            reset_timer();
        }

        void rx_subchannel::cbuf_insert(const uint8_t c) {
            d_cbuf[d_cbuf_idx] = c;
            d_cbuf[d_cbuf_idx + SUBCHANNEL_FRAME_LENGTH] = c;
            d_cbuf_idx = (d_cbuf_idx + 1) % SUBCHANNEL_FRAME_LENGTH;
        }

        void rx_subchannel::sync_reset(void) {
            d_symbol_count = 0;
            d_cbuf_idx = 0;
            d_rx_count = 0;
            d_shift_reg = 0;
            d_sync_reg = 0x1f;
            d_expires = 0;
            d_in_sync = false;

            // Timers reset
            reset_timer();
        }

        void rx_subchannel::reset_timer(void) {
            sync_timer.reset();
        }

        void rx_subchannel::sync_timeout()
        {
            if ((d_msgq_id >= 0) && (!d_msg_queue->full_p())) {
                std::string m_buf;
                gr::message::sptr msg;
                msg = gr::message::make_from_string(m_buf, get_msg_type(PROTOCOL_SMARTNET, M_SMARTNET_TIMEOUT), (d_msgq_id << 1), logts.get_ts());
                d_msg_queue->insert_tail(msg);
            }
            if (d_debug >= 10) {
                fprintf(stderr, "%s rx_subchannel::sync_timeout:\n", logts.get(d_msgq_id));
            }
            reset_timer();
        }

        void rx_subchannel::send_msg(const char* buf) {
            std::string msg_str = std::string(buf,5);
            if ((d_msgq_id >= 0) && (!d_msg_queue->full_p())) {

                gr::message::sptr msg = gr::message::make_from_string(msg_str, get_msg_type(PROTOCOL_SMARTNET, M_SMARTNET_SUB_CH), (d_msgq_id<<1), logts.get_ts());
                d_msg_queue->insert_tail(msg);
            }
        }

    } // end namespace op25_repeater
} // end namespace gr

