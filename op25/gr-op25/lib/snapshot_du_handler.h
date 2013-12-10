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

#ifndef INCLUDED_SNAPSHOT_DU_HANDLER_H
#define INCLUDED_SNAPSHOT_DU_HANDLER_H

#include "data_unit_handler.h"

#include <gnuradio/msg_queue.h>
#include <boost/noncopyable.hpp>

/**
 * snapshot_du_handler. Writes traffic snapshots to a msg_queue based
 * on the HDU frame contents. The format used is that of a pickled
 * python dictionary allowing the other end of the queue to pick only
 * those fields of interest and ignore the rest.
 */
class snapshot_du_handler : public data_unit_handler
{

public:

   /**
    * snapshot_du_handler constructor.
    *
    * \param next The next data_unit_handler in the chain.
    * \param msgq A non-null msg_queue_sptr to the msg_queue to use.
    */
   snapshot_du_handler(data_unit_handler_sptr next);

   /**
    * snapshot_du_handler virtual destructor.
    */
   virtual ~snapshot_du_handler();

   /**
    * Handle a received P25 frame.
    *
    * \param du A non-null data_unit_sptr to handle.
    */
   virtual void handle(data_unit_sptr du);

   /**
    * Accessor for the msgq attribute. Returns a pointer to the msgq
    * if it exists.
    *
    * \return A (possibly NULL) gr_msg_queue_sptr pointing to the message queue.
    */
   gr::msg_queue::sptr get_msgq() const;

   /**
    * Accessor for the msgq attribute. Sets the msgq to point to the
    * provided message queue object.
    *
    * \return A (possibly NULL) gr_msg_queue_sptr pointing to the message queue.
    */
   void set_msgq(gr::msg_queue::sptr msgq);

private:

   /**
    * Count of the data units seen so far.
    */
   uint32_t d_data_units;

   /**
    * The msg_queue to which decoded frames are written.
    */
   gr::msg_queue::sptr d_msgq;

};



#endif /* INCLUDED_SNAPSHOT_DU_HANDLER_H */
