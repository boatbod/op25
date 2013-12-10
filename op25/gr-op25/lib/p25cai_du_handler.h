/* -*- C++ -*- */

/*
 * Copyright 2008-2011 Steve Glass
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

#ifndef INCLUDED_P25CAI_DU_HANDLER_H
#define INCLUDED_P25CAI_DU_HANDLER_H

#include "data_unit_handler.h"

#include <string>

/**
 * This data_unit_handler forwards received frames using p25cai - a
 * straighforward encapsulation of the P25 CAI in a UDP datagram. This
 * format is understood by Wireshark and replaces the use of TUN/TAP
 * which require root privileges and are not present by default on
 * some platforms.
 */
class p25cai_du_handler : public data_unit_handler
{

public:

   /**
    * p25cai_du_handler constructor.
    *
    * \param next The next data_unit_handler.
	 * \param addr The address of the receiver.
	 * \param port The port number of the receiver.
    */
   p25cai_du_handler(data_unit_handler_sptr next, const char *addr, int port);

   /**
    * p25cai_du_handler virtual destructor.
    */
   virtual ~p25cai_du_handler();

   /**
    * Handle a received P25 frame.
    *
    * \param du A non-null data_unit_sptr to handle.
    */
   virtual void handle(data_unit_sptr du);

   /**
    * Return a pointer to a string identifying the destination address.
    *
    * \return A pointer to a NUL-terminated character string.
    */
   const char *destination() const;

private:

   /**
    * file descriptor for the UDP socket.
    */
   int32_t d_cai;

   /**
    * A string identifying the address of the receiver.
    */
   std::string d_address;

};

#endif /* INCLUDED_P25CAI_DU_HANDLER_H */
