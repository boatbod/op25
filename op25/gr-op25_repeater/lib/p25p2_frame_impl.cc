/* -*- c++ -*- */
/* 
 * Copyright 2014 Max H. Parke KA1RBI
 *
 * This file is part of OP25
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
#include "p25p2_frame_impl.h"
#include "imbe_decoder.h"

namespace gr {
  namespace op25_repeater {

    p25p2_frame::sptr
    p25p2_frame::make(int debug, int slotid, bool do_msgq, gr::msg_queue::sptr msgq)
    {
      return gnuradio::get_initial_sptr
        (new p25p2_frame_impl(debug, slotid, do_msgq, msgq));
    }

    /*
     * The private constructor
     */
    p25p2_frame_impl::p25p2_frame_impl(int debug, int slotid, bool do_msgq, gr::msg_queue::sptr msgq)
      : gr::block("p25p2_frame",
              gr::io_signature::make(1, 1, sizeof(uint8_t)),
              gr::io_signature::make(1, 1, sizeof(short))),
	p2tdma(slotid, debug, &output_queue_decode),
	d_do_msgq(do_msgq),
	d_msg_queue(msgq)
    {}

    /*
     * Our virtual destructor.
     */
    p25p2_frame_impl::~p25p2_frame_impl()
    {
    }

    void 
    p25p2_frame_impl::queue_msg(int duid)
    {
	static const char wbuf[2] = {0xff, 0xff}; // dummy NAC
	if (!d_do_msgq)
		return;
	if (d_msg_queue->full_p())
		return;
	gr::message::sptr msg = gr::message::make_from_string(std::string(wbuf, 2), duid, 0, 0);
	d_msg_queue->insert_tail(msg);
    }
    void p25p2_frame_impl::handle_p2_frame(const bit_vector& bits) {
	uint8_t wbuf[180];
	int rc;
        for (int i=0; i<sizeof(wbuf); i++)
		wbuf[i] = bits[i*2+1] + (bits[i*2] << 1);
        rc = p2tdma.handle_packet(wbuf);
	if (rc > -1)
		queue_msg(rc);
    }

    void p25p2_frame_impl::set_xormask(const char*p) {
	p2tdma.set_xormask(p);
    }

    void p25p2_frame_impl::set_slotid(int slotid) {
	p2tdma.set_slotid(slotid);
    }

    void
    p25p2_frame_impl::forecast (int noutput_items, gr_vector_int &ninput_items_required)
    // input rate = 6 K s/s (input is dibits)
    // output rate = 4.8 K s/s (output is short)
    // i/o ratio is 1.25
    {
   const size_t nof_inputs = ninput_items_required.size();
   int nof_samples_reqd = 1.25 * noutput_items;
   std::fill(&ninput_items_required[0], &ninput_items_required[nof_inputs], nof_samples_reqd);

    }

    int
    p25p2_frame_impl::general_work (int noutput_items,
                       gr_vector_int &ninput_items,
                       gr_vector_const_void_star &input_items,
                       gr_vector_void_star &output_items)
    {
        const uint8_t *in = (const uint8_t *) input_items[0];

	for (int i = 0; i < noutput_items; i++) {
		if(p2framer.rx_sym(in[i])) {
			handle_p2_frame(p2framer.d_frame_body);
		}
	}
  int16_t *out = reinterpret_cast<int16_t*>(output_items[0]);
  const int n = std::min(static_cast<int>(output_queue_decode.size()), noutput_items);
  if(0 < n) {
     copy(output_queue_decode.begin(), output_queue_decode.begin() + n, out);
     output_queue_decode.erase(output_queue_decode.begin(), output_queue_decode.begin() + n);
  }
        // Tell runtime system how many input items we consumed on
        // each input stream.
        consume_each (noutput_items);

        // Tell runtime system how many output items we produced.
        return n;
    }

  } /* namespace op25_repeater */
} /* namespace gr */
