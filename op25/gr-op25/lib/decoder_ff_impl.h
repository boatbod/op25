/* -*- c++ -*- */
/* 
 * Copyright 2008-2011 Steve Glass
 * 
 * This file is part of OP25.
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

#ifndef INCLUDED_OP25_DECODER_FF_IMPL_H
#define INCLUDED_OP25_DECODER_FF_IMPL_H

#include <op25/decoder_ff.h>
#include "data_unit.h"
#include "data_unit_handler.h"
#include "imbe_decoder.h"
#include "p25cai_du_handler.h"
#include "snapshot_du_handler.h"

namespace gr {
  namespace op25 {

    class decoder_ff_impl : public decoder_ff
    {
    private:
      /**
       * Tests whether d_frame_header correlates with the APCO P25
       * frame sync sequence. This method must only be called when the
       * frame header is larger than 48 bits in length (the minimum
       * size for the FS).
       *
       * \return true if the frame header correlates; otherwise false.
       */
      bool correlated();

      /**
       * Tests whether d_frame_header identifies a known data unit and
       * if so sets d_data_unit to point to an appropriate instance
       * and returns a pointer to it. This method must only be called
       * when the frame header is larger than 114 bits in length (the
       * minimum size for a frame containing a NID).
       *
       * \return A data_unit_sptr pointing to an appropriate data_unit
       * instance or NULL if the frame header is unrecognized.
       */
      data_unit_sptr identified();

      /**
       * Handle a received symbol.
       *
       * \param d The symbol to process.
       */
      void receive_symbol(dibit d);

    private:
      /**
       * When d_state == READING the current data unit, otherwise
       * null.
       */
      data_unit_sptr d_data_unit;

      /**
       * The head of a chain of data_unit_handler instances.
       */
      data_unit_handler_sptr d_data_unit_handler;

      /**
       * A bit_queue used to correlate the FS.
       */
      bit_queue d_frame_hdr;

      /**
       * The IMBE decoder to use.
       */
      imbe_decoder_sptr d_imbe;

      /**
       * Valid states for the decoder state model.
       */
      enum { SYNCHRONIZING, IDENTIFYING, READING } d_state;

      /**
       * The p25cai (TUN/TAP) data unit handler.
       */
      class p25cai_du_handler *d_p25cai_du_handler;

      /**
       * The snapshot data unit handler.
       */
      class snapshot_du_handler *d_snapshot_du_handler;

    public:
      decoder_ff_impl();
      ~decoder_ff_impl();

      // Where all the action really happens
      void forecast (int noutput_items, gr_vector_int &ninput_items_required);

      int general_work(int noutput_items,
		       gr_vector_int &ninput_items,
		       gr_vector_const_void_star &input_items,
		       gr_vector_void_star &output_items);

      /**
       * Return a pointer to a string identifying the destination of
       * the received frames.
       *
       * \return A pointer to a NUL-terminated character string.
       */
      const char *destination() const;

      /**
       * Accessor for the msgq attribute. Returns a pointer to the
       * msgq if it exists.
       *
       * \return A (possibly NULL) gr_msg_queue_sptr pointing to the
       * message queue.
       */
      gr::msg_queue::sptr get_msgq() const;

      /**
       * Accessor for the msgq attribute. Sets the msgq to point to
       * the provided message queue object.
       *
       * \return A (possibly NULL) gr_msg_queue_sptr pointing to the
       * message queue.
       */
      void set_msgq(gr::msg_queue::sptr msgq);
    };
  } // namespace op25
} // namespace gr

#endif /* INCLUDED_OP25_DECODER_FF_IMPL_H */

