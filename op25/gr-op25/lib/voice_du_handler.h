/* -*- C++ -*- */

/*
 * Copyright 2009 Steve Glass
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

#ifndef INCLUDED_VOICE_DU_HANDLER_H
#define INCLUDED_VOICE_DU_HANDLER_H

#include "data_unit_handler.h"
#include "imbe_decoder.h"

#include <boost/noncopyable.hpp>

/**
 * voice_data_unit_handler performs IMBE decoding.
 */
class voice_du_handler : public data_unit_handler
{

public:

   /**
    * voice_du_handler constructor.
    *
    * \param next The next data_unit_handler in the chain.
    * \param decoder An imbe_decoder_sptr to the IMBE decoder to use.
    */
   voice_du_handler(data_unit_handler_sptr next, imbe_decoder_sptr decoder);

   /**
    * voice_du_handler virtual destructor.
    */
   virtual ~voice_du_handler();

   /**
    * Handle a received P25 frame.
    *
    * \param next The next data_unit_handler in this chain.
    */
   virtual void handle(data_unit_sptr du);

private:

   /**
    * The IMBE decder to use.
    */
   imbe_decoder_sptr d_decoder;

};

#endif /* INCLUDED_VOICE_DU_HANDLER_H */
