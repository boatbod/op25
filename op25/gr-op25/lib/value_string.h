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

#ifndef INCLUDED_VALUE_STRING
#define INCLUDED_VALUE_STRING

#include <stdint.h>
#include <string>

/*
 * Look up a value in a value_string array.
 *
 */
extern std::string lookup(uint16_t value, const class value_string mappings[], size_t mappings_sz);

/*
 * Look up tables.
 */

extern const value_string ALGIDS[];
extern const size_t ALGIDS_SZ;

extern const value_string MFIDS[];
extern const size_t MFIDS_SZ;

extern const value_string NACS[];
extern const size_t NACS_SZ;

#endif // INCLUDED_VALUE_STRING
