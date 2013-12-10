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

#include "abstract_data_unit.h"

#include <algorithm>
#include <cstring>
#include <functional>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <sstream>
#include <utility>

using namespace std;

abstract_data_unit::~abstract_data_unit()
{
}

void
abstract_data_unit::correct_errors()
{
   if(is_complete()) {
      do_correct_errors(d_frame_body);
   } else {
      ostringstream msg;
      msg << "cannot correct errors - frame is not complete" << endl;
      msg << "(size now: "  << frame_size() << ", expected size: " << frame_size_max() << ")" << endl;
      msg << "func: " << __PRETTY_FUNCTION__ << endl;
      msg << "file: " << __FILE__ << endl;
      msg << "line: " << __LINE__ << endl;
      throw logic_error(msg.str());
   }
}

void
abstract_data_unit::decode_audio(imbe_decoder& imbe)
{
   if(is_complete()) {
      do_decode_audio(d_frame_body, imbe);
   } else {
      ostringstream msg;
      msg << "cannot decode audio - frame is not complete" << endl;
      msg << "(size now: "  << frame_size() << ", expected size: " << frame_size_max() << ")" << endl;
      msg << "func: " << __PRETTY_FUNCTION__ << endl;
      msg << "file: " << __FILE__ << endl;
      msg << "line: " << __LINE__ << endl;
      throw logic_error(msg.str());
   }
}

size_t
abstract_data_unit::decode_frame(size_t msg_sz, uint8_t *msg)
{
   return decode_frame(d_frame_body, msg_sz, msg);
}

size_t
abstract_data_unit::decode_frame(const_bit_vector& frame_body, size_t msg_sz, uint8_t *msg)
{
   size_t n = 0;
   if(is_complete()) {
      if(size() <= msg_sz) {
         n = extract(frame_body, 0, static_cast<int>(frame_body.size()), msg);
      } else {
         ostringstream msg;
         msg << "cannot decode frame body ";
         msg << "(msg size: "  << msg_sz << ", actual size: " << size() << ")" << endl;
         msg << "func: " << __PRETTY_FUNCTION__ << endl;
         msg << "file: " << __FILE__ << endl;
         msg << "line: " << __LINE__ << endl;
         throw length_error(msg.str());
      }
   } else {
      ostringstream msg;
      msg << "cannot decode frame - frame is not complete" << endl;
      msg << "(size now: "  << frame_size() << ", expected size: " << frame_size_max() << ")" << endl;
      msg << "func: " << __PRETTY_FUNCTION__ << endl;
      msg << "file: " << __FILE__ << endl;
      msg << "line: " << __LINE__ << endl;
      throw logic_error(msg.str());
   }
   return n;

}

void
abstract_data_unit::extend(dibit d)
{
   if(frame_size() < frame_size_max()) {
      d_frame_body.push_back(d & 0x2);
      d_frame_body.push_back(d & 0x1);
   } else {
      ostringstream msg;
      msg << "cannot extend frame " << endl;
      msg << "(size now: " << frame_size() << ", expected size: " << frame_size_max() << ")" << endl;
      msg << "func: " << __PRETTY_FUNCTION__ << endl;
      msg << "file: " << __FILE__ << endl;
      msg << "line: " << __LINE__ << endl;
      throw length_error(msg.str());
   }
}

bool
abstract_data_unit::is_complete() const
{
   return frame_size() >= frame_size_max();
}

uint16_t
abstract_data_unit::size() const
{
   return (7 + frame_size_max()) >> 3;
}

std::string
abstract_data_unit::snapshot() const
{
   string empty;
   return empty;
}

void
abstract_data_unit::dump(ostream& os) const
{
   uint32_t nbits = d_frame_body.size();
   os << setw(4) << nbits << " ";
   for(size_t i = 48; i < nbits; ++i) {
      os << (d_frame_body[i] ? "#" : "-");
   }
   os << endl;
}

abstract_data_unit::abstract_data_unit(const_bit_queue& frame_body) :
   d_frame_body(frame_body.size())
{
   copy(frame_body.begin(), frame_body.end(), d_frame_body.begin());
}

void
abstract_data_unit::do_correct_errors(bit_vector& frame_body)
{
}

void
abstract_data_unit::do_decode_audio(const_bit_vector& frame_body, imbe_decoder& imbe)
{
}

const_bit_vector& 
abstract_data_unit::frame_body() const
{
   return d_frame_body;
}

uint16_t 
abstract_data_unit::frame_size() const
{
   return d_frame_body.size();
}
