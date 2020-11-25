/* -*- c++ -*- */
/* 
 * Copyright 2010, 2011, 2012, 2013, 2014 Max H. Parke KA1RBI 
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
#include "p25_frame_assembler_impl.h"

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

    void p25_frame_assembler_impl::set_xormask(const char*p) {
	p2tdma.set_xormask(p);
    }

    void p25_frame_assembler_impl::set_slotid(int slotid) {
	p2tdma.set_slotid(slotid);
    }

    void p25_frame_assembler_impl::set_slotkey(int key) {
    }

    void p25_frame_assembler_impl::reset_timer() {
	p1fdma.reset_timer();
    }

    p25_frame_assembler::sptr
    p25_frame_assembler::make(const char* udp_host, int port, int debug, bool do_imbe, bool do_output, bool do_msgq, gr::msg_queue::sptr queue, bool do_audio_output, bool do_phase2_tdma, bool do_nocrypt)
    {
      return gnuradio::get_initial_sptr
        (new p25_frame_assembler_impl(udp_host, port, debug, do_imbe, do_output, do_msgq, queue, do_audio_output, do_phase2_tdma, do_nocrypt));
    }

    /*
     * The private constructor
     */

    /*
     * Our virtual destructor.
     */
    p25_frame_assembler_impl::~p25_frame_assembler_impl()
    {
    }

static const int MIN_IN = 1;	// mininum number of input streams
static const int MAX_IN = 1;	// maximum number of input streams

/*
 * The private constructor
 */
    p25_frame_assembler_impl::p25_frame_assembler_impl(const char* udp_host, int port, int debug, bool do_imbe, bool do_output, bool do_msgq, gr::msg_queue::sptr queue, bool do_audio_output, bool do_phase2_tdma, bool do_nocrypt)
      : gr::block("p25_frame_assembler",
		   gr::io_signature::make (MIN_IN, MAX_IN, sizeof (char)),
		   gr::io_signature::make ((do_output) ? 1 : 0, (do_output) ? 1 : 0, (do_audio_output && do_output) ? sizeof(int16_t) : ((do_output) ? sizeof(char) : 0 ))),
	d_do_imbe(do_imbe),
	d_do_output(do_output),
	output_queue(),
        op25audio(udp_host, port, debug),
	p1fdma(op25audio, debug, do_imbe, do_output, do_msgq, queue, output_queue, do_audio_output, do_nocrypt),
	d_do_audio_output(do_audio_output),
	d_do_phase2_tdma(do_phase2_tdma),
	d_do_nocrypt(do_nocrypt),
	p2tdma(op25audio, 0, debug, do_msgq, queue, output_queue, do_audio_output, do_nocrypt),
	d_do_msgq(do_msgq),
	d_msg_queue(queue)
{
        fprintf(stderr, "p25_frame_assembler_impl: do_imbe[%d], do_output[%d], do_audio_output[%d], do_phase2_tdma[%d], do_nocrypt[%d]\n", do_imbe, do_output, do_audio_output, do_phase2_tdma, do_nocrypt);
}

#if 0
void
p25_frame_assembler_impl::forecast(int nof_output_items, gr_vector_int &nof_input_items_reqd)
{
   // for do_imbe=false: we output packed bytes (4:1 ratio)
   // for do_imbe=true: input rate= 4800, output rate= 1600 = 32 * 50 (3:1)
   // for do_audio_output: output rate=8000 (ratio 0.6:1)
   const size_t nof_inputs = nof_input_items_reqd.size();
   int nof_samples_reqd = 4.0 * nof_output_items;
   if (d_do_imbe)
     nof_samples_reqd = 3.0 * nof_output_items;
   nof_samples_reqd = nof_output_items;
   if (d_do_audio_output)
     nof_samples_reqd = 0.6 * nof_output_items;
   nof_samples_reqd = std::max(nof_samples_reqd, 256);
   std::fill(&nof_input_items_reqd[0], &nof_input_items_reqd[nof_inputs], nof_samples_reqd);
}
#endif

int 
p25_frame_assembler_impl::general_work (int noutput_items,
                               gr_vector_int &ninput_items,
                               gr_vector_const_void_star &input_items,
                               gr_vector_void_star &output_items)
{

  const uint8_t *in = (const uint8_t *) input_items[0];

  p1fdma.rx_sym(in, ninput_items[0]);
  if(d_do_phase2_tdma) {
	for (int i = 0; i < ninput_items[0]; i++) {
		if(p2tdma.rx_sym(in[i])) {
			int rc = p2tdma.handle_frame();
			if (rc > -1) {
				p1fdma.reset_timer(); // prevent P1 timeouts due to long TDMA transmissions
			}
		}
	}
  }
  int amt_produce = 0;
  if (d_do_output) {
    amt_produce = noutput_items;
    if (amt_produce > (int)output_queue.size())
      amt_produce = output_queue.size();
    if (amt_produce > 0) {
      if (d_do_audio_output) {
        int16_t *out = (int16_t *) output_items[0];
        for (int i=0; i < amt_produce; i++) {
          out[i] = output_queue[i];
        }
      } else {
        unsigned char *out = (unsigned char *) output_items[0];
        for (int i=0; i < amt_produce; i++) {
          out[i] = output_queue[i];
        }
      }
      output_queue.erase(output_queue.begin(), output_queue.begin() + amt_produce);
    }
  }
  consume_each(ninput_items[0]);
  // Tell runtime system how many output items we produced.
  return amt_produce;
}

  } /* namespace op25_repeater */
} /* namespace gr */
