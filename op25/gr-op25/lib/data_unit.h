/* -*- C++ -*- */

/*
 * Copyright 2008 Steve Glass
 * 
 * This file is part of OP25.
 * 
 * OP25 is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * OP25 is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public
 * License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with OP25; see the file COPYING.  If not, write to the Free
 * Software Foundation, Inc., 51 Franklin Street, Boston, MA
 * 02110-1301, USA.
 */

#ifndef INCLUDED_DATA_UNIT_H
#define INCLUDED_DATA_UNIT_H

#include "imbe_decoder.h"

#include <boost/shared_ptr.hpp>
#include <boost/noncopyable.hpp>
#include <deque>
#include <iosfwd>
#include <stdint.h>

typedef std::deque<bool> bit_queue;
typedef const std::deque<bool> const_bit_queue;

typedef uint8_t dibit;

typedef std::deque<float> float_queue;

typedef boost::shared_ptr<class data_unit> data_unit_sptr;

/**
 * A P25 data unit.
 */
class data_unit : public boost::noncopyable
{
public:

   /**
    * data_unit (virtual) constructor. Returns a pointer to an
    * appropriate data_unit instance given the initial frame_body.
    * \param fs The frame sync value for this data_unit.
    * \param nid The network ID for this data_unit.
    * \return A (possibly null-valued) pointer to the data_unit.
    */
   static data_unit_sptr make_data_unit(const_bit_queue& frame_body);

   /**
    * data_unit (virtual) destructor.
    */
   virtual ~data_unit();

   /**
    * Apply error correction to this data_unit.
    *
    * \precondition is_complete() == true.
    */
   virtual void correct_errors() = 0;

   /**
    * Decode compressed audio using the supplied imbe_decoder and
    * writes output to audio.
    *
    * \precondition is_complete() == true.
    * \param imbe The imbe_decoder to use to generate the audio.
    */
   virtual void decode_audio(imbe_decoder& imbe) = 0;

   /**
    * Decode the frame into an octet vector.
    *
    * \precondition is_complete() == true.
    * \param msg_sz The size of the message buffer.
    * \param msg A pointer to the message buffer.
    * \return The number of octets written to msg.
    */
   virtual size_t decode_frame(size_t msg_sz, uint8_t *msg) = 0;

   /**
    * Dump this data unit in human readable format to stream s.
    *
    * \param s The stream to write on
    */
   virtual void dump(std::ostream& os) const = 0;

   /**
    * Extends this data_unit with the specified dibit. If this
    * data_unit is already complete a range_error is thrown.
    *
    * \precondition is_complete() == false.
    * \param d The dibit to extend the frame with.
    * \throws range_error When the frame already is at its maximum size.
    * \return true when the frame is complete otherwise false.
    */
   virtual void extend(dibit d) = 0;

   /**
    * Tests whether this data unit is complete. 
    *
    * \return true when this data_unit is complete; otherwise returns
    * false.
    * \ see extend()
    */
   virtual bool is_complete() const = 0;

   /**
    * Returns the size (in octets) of the data_unit.
    *
    * \return The actual size (in octets) of this data_unit.
    */
   virtual uint16_t size() const = 0;

   /**
    * Return a snapshot of the key fields from this frame in a manner
    * suitable for display by the UI. The string is encoded using the
    * Python pickle format allowing for different fields to be
    * returned.
    * 
    * \return A string containing the fields to display.
    */
   virtual std::string snapshot() const = 0;

protected:

   /**
    * data_unit default constructor.
    */
   data_unit();
};

#endif /* INCLUDED_DATA_UNIT_H */
