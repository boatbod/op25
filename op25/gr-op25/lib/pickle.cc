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

#include "pickle.h"

#include <iomanip>
#include <sstream>

using namespace std;

pickle::pickle()
{
}

pickle::~pickle()
{
}

void
pickle::add(string key, string value)
{
   map_[key] = value;
}

string
pickle::to_string() const
{
   size_t n = 1;
   ostringstream os;
   os << "(dp" << n++ << endl;
   for(stringmap::const_iterator i(map_.begin()); i != map_.end(); ++i) {
      os << "S'" << i->first << "'" << endl;
      os << "p" << n++ << endl;
      os << "S'" << i->second << "'" << endl;
      os << "p" << n++ << endl << "s";
   }
   os << "." << endl;
   return os.str();
}
