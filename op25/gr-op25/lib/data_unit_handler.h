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

#ifndef INCLUDED_DATA_UNIT_HANDLER_H
#define INCLUDED_DATA_UNIT_HANDLER_H

#include "data_unit.h"

#include <boost/noncopyable.hpp>
#include <boost/shared_ptr.hpp>

typedef boost::shared_ptr<class data_unit_handler> data_unit_handler_sptr;

/**
 * P25 data_unit_handler interface.
 */
class data_unit_handler : public boost::noncopyable
{

public:

   /**
    * data_unit_handler virtual destructor.
    */
   virtual ~data_unit_handler();

   /**
    * Handle a received P25 frame.
    *
    * \param du A non-null data_unit_sptr to handle.
    */
   virtual void handle(data_unit_sptr du) = 0;

protected:

   /**
    * data_unit_handler default constructor.
    *
    * \param next The next data_unit_handler in this chain.
    */
   data_unit_handler(data_unit_handler_sptr next);

private:

   /**
    * The next data_unit_handler in this chain.
    */
   data_unit_handler_sptr d_next;

};

#endif /* INCLUDED_DATA_UNIT_HANDLER_H */
