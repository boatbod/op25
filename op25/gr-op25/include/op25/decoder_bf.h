/* -*- c++ -*- */
/* 
 * Copyright 2010,2011 Steve Glass
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


#ifndef INCLUDED_OP25_DECODER_BF_H
#define INCLUDED_OP25_DECODER_BF_H

#include <op25/api.h>
#include <gnuradio/block.h>
#include <gnuradio/msg_queue.h>

namespace gr {
  namespace op25 {

    /*!
     * \brief Decode APCO P25 signals
     * \ingroup op25
     *
     * op25_decoder_bf is a GNU Radio block for decoding APCO P25
     * signals. This class expects its input to be a stream of dibit
     * symbols from the demodulator and produces a mono audio stream.
     *
     */
    class OP25_API decoder_bf : virtual public gr::block
    {
     public:
      typedef boost::shared_ptr<decoder_bf> sptr;

      /*!
       * \brief Return a shared_ptr to a new instance of op25::decoder_bf.
       *
       * To avoid accidental use of raw pointers, op25::decoder_bf's
       * constructor is in a private implementation
       * class. op25::decoder_bf::make is the public interface for
       * creating new instances.
       */
      static sptr make();

      /**
       * Return a pointer to a string identifying the destination of
       * the received frames.
       *
       * \return A pointer to a NUL-terminated character string.
       */
      virtual const char *destination() const = 0;

      /**
       * Accessor for the msgq attribute. Returns a pointer to the
       * msgq if it exists.
       *
       * \return A (possibly NULL) gr_msg_queue_sptr pointing to the
       * message queue.
       */
      virtual gr::msg_queue::sptr get_msgq() const = 0;

      /**
       * Accessor for the msgq attribute. Sets the msgq to point to
       * the provided message queue object.
       *
       * \return A (possibly NULL) gr_msg_queue_sptr pointing to the
       * message queue.
       */
      virtual void set_msgq(gr::msg_queue::sptr msgq) = 0;
    };

  } // namespace op25
} // namespace gr

#endif /* INCLUDED_OP25_DECODER_BF_H */

