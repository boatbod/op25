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

#ifndef INCLUDED_ABSTRACT_DATA_UNIT_H
#define INCLUDED_ABSTRACT_DATA_UNIT_H

#include "data_unit.h"
#include "op25_yank.h"

#include <string>
#include <vector>

#include <itpp/base/vec.h>
#include <vector>

typedef std::vector<bool> bit_vector;
typedef const std::vector<bool> const_bit_vector;

/**
 * Abstract P25 data unit.
 */
class abstract_data_unit : public data_unit
{

public:

   /**
    * abstract data_unit virtual destructor.
    */
   virtual ~abstract_data_unit();

   /**
    * Apply error correction to this data_unit.
    *
    * \precondition is_complete() == true.
    */
   virtual void correct_errors();

   /**
    * Decode compressed audio using the supplied imbe_decoder.
    *
    * \precondition is_complete() == true.
    * \param imbe The imbe_decoder to use to generate the audio.
    */
   virtual void decode_audio(imbe_decoder& imbe);

   /**
    * Decode the frame into an octet vector.
    *
    * \precondition is_complete() == true.
    * \param msg_sz The size of the message buffer.
    * \param msg A pointer to the message buffer.
    * \return The number of octets written to msg.
    */
   virtual size_t decode_frame(size_t msg_sz, uint8_t *msg);

   /**
    * Dump this data unit in human readable format to stream s.
    *
    * \param s The stream to write on
    */
   virtual void dump(std::ostream& os) const;

   /**
    * Extends this data_unit with the specified dibit. If this
    * data_unit is already complete a range_error is thrown.
    *
    * \precondition is_complete() == false.
    * \param d The dibit to extend the frame with.
    * \throws range_error When the frame already is at its maximum size.
    * \return true when the frame is complete otherwise false.
    */
   virtual void extend(dibit d);

   /**
    * Tests whether this data unit has enough data to begin decoding.
    *
    * \return true when this data_unit is complete; otherwise returns
    * false.
    */
   virtual bool is_complete() const;

   /**
    * Returns the size (in octets) of this data_unit.
    *
    * \return The size (in octets) of this data_unit.
    */
   virtual uint16_t size() const;

   /**
    * Return a snapshot of the key fields from this frame in a manner
    * suitable for display by the UI. The string is encoded as a
    * pickled Python dictionary.
    * 
    * \precondition is_complete() == true.
    * \return A string containing the fields to display.
    */
   virtual std::string snapshot() const;

protected:

   /**
    * abstract_data_unit constructor.
    *
    * \param frame_body A const_bit_queue representing the frame body.
    */
   abstract_data_unit(const_bit_queue& frame_body);

   /**
    * Applies error correction code to the specified bit_vector.
    *
    * \param frame_body The bit vector to decode.
    */
   virtual void do_correct_errors(bit_vector& frame_body);

   /**
    * Decode compressed audio using the supplied imbe_decoder.
    *
    * \precondition is_complete() == true.
    * \param frame_body The const_bit_vector to decode.
    * \param imbe The imbe_decoder to use.
    */
   virtual void do_decode_audio(const_bit_vector& frame_body, imbe_decoder& imbe);

   /**
    * Decode frame_body and write the decoded frame contents to msg.
    *
    * \param frame_body The bit vector to decode.
    * \param msg_sz The size of the message buffer.
    * \param msg A pointer to where the data unit content will be written.
    * \return The number of octets written to msg.
    */
   virtual size_t decode_frame(const_bit_vector& frame_body, size_t msg_sz, uint8_t *msg);

   /**
    * Returns a string describing the Data Unit ID (DUID).
    *
    * \return A string identifying the DUID.
    */
   virtual std::string duid_str() const = 0;

   /**
    * Return a reference to the frame body.
    */
   const_bit_vector& frame_body() const;

   /**
    * Returns the expected size (in bits) of this data_unit. For
    * variable-length data this should return UINT16_MAX until the
    * actual length of this frame is known.
    *
    * \return The expected size (in bits) of this data_unit when encoded.
    */
   virtual uint16_t frame_size_max() const = 0;

   /**
    * Returns the current size (in bits) of this data_unit.
    *
    * \return The current size (in bits) of this data_unit.
    */
   virtual uint16_t frame_size() const;

private:

   /**
    * A bit vector containing the frame body.
    */
   bit_vector d_frame_body;

};

#endif /* INCLUDED_ABSTRACT_DATA_UNIT_H */
