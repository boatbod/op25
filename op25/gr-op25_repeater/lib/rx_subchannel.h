// Type II Subchannel Decoder (C) Copyright 2020 Graham J. Norbury
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

#ifndef INCLUDED_RX_SUBCHANNEL_H
#define INCLUDED_RX_SUBCHANNEL_H

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <string>
#include <iostream>
#include <deque>
#include <assert.h>
#include <gnuradio/msg_queue.h>

#include "bit_utils.h"
#include "check_frame_sync.h"
#include "frame_sync_magics.h"
#include "op25_timer.h"
#include "log_ts.h"

#include "rx_base.h"

namespace gr{
    namespace op25_repeater{

        static const int SUBCHANNEL_SYNC_LENGTH    =  5;
        static const int SUBCHANNEL_FRAME_LENGTH   = 28;
        static const int SUBCHANNEL_PAYLOAD_LENGTH = 23;

        class rx_subchannel : public rx_base {
            public:
                void rx_sym(const uint8_t sym);
                void sync_reset(void);
                void reset_timer(void);
                void set_slot_mask(int mask) { };
                void set_slot_key(int mask) { };
                void set_xormask(const char* p) { };
                rx_subchannel(const char * options, int debug, int msgq_id, gr::msg_queue::sptr queue);
                ~rx_subchannel();

            private:
                void sync_timeout();
                void cbuf_insert(const uint8_t c);
                void send_msg(const char* buf);

                int d_debug;
                int d_msgq_id;
                gr::msg_queue::sptr d_msg_queue;

                op25_timer sync_timer;
                bool d_in_sync;
                unsigned int d_symbol_count;
                uint8_t d_sync_reg;
                uint8_t d_cbuf[SUBCHANNEL_FRAME_LENGTH * 2];
                unsigned int d_cbuf_idx;
                int d_rx_count;
                unsigned int d_expires;
                int d_shift_reg;
                std::deque<int16_t> d_output_queue[2];
                log_ts logts;
        };

    } // end namespace op25_repeater
} // end namespace gr
#endif // INCLUDED_RX_SUBCHANNEL_H
