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

#ifndef INCLUDED_PICKLE_H
#define INCLUDED_PICKLE_H

#include "abstract_data_unit.h"

#include <map>

/**
 * A pickled Python dictionary. Used to pass stuff to the UI.
 */
class pickle
{

public:

   /**
    * pickle constructor.
    *
    * \param frame_body A const_bit_queue representing the frame body.
    */
   pickle();

   /**
    * pickle virtual destructor.
    */
   ~pickle();

   /**
    * Add a key/value pair to the pickled dictionary
    */
   void add(std::string key, std::string value);

   /**
    * Returns a string describing the Data Unit ID (DUID).
    */
   std::string to_string() const;

private:

   typedef std::map<std::string, std::string> stringmap;

   stringmap map_;

};

#endif /* INCLUDED_PICKLE_H */
