/* -*- c++ -*- */
/* 
 * Copyright 2014 Max H. Parke KA1RBI
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


#ifndef INCLUDED_OP25_REPEATER_P25P2_FRAME_H
#define INCLUDED_OP25_REPEATER_P25P2_FRAME_H

#include <op25_repeater/api.h>
#include <gnuradio/block.h>

namespace gr {
  namespace op25_repeater {

    /*!
     * \brief <+description of block+>
     * \ingroup op25_repeater
     *
     */
    class OP25_REPEATER_API p25p2_frame : virtual public gr::block
    {
     public:
      typedef boost::shared_ptr<p25p2_frame> sptr;

      /*!
       * \brief Return a shared_ptr to a new instance of op25_repeater::p25p2_frame.
       *
       * To avoid accidental use of raw pointers, op25_repeater::p25p2_frame's
       * constructor is in a private implementation
       * class. op25_repeater::p25p2_frame::make is the public interface for
       * creating new instances.
       */
      static sptr make(int debug, int slotid);
      virtual void set_xormask(const char*p) {}
      virtual void set_slotid(int slotid) {}
    };
  }
}
#endif /* INCLUDED_OP25_REPEATER_P25P2_FRAME_H */
