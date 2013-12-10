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

#ifndef INCLUDED_OFFLINE_IMBE_DECODER_H 
#define INCLUDED_OFFLINE_IMBE_DECODER_H 

#include "imbe_decoder.h"

#include <cstdio>

/**
 * offline_imbe_decoder dumps voice codewords to file for offline decoding.
 * 
 */
class offline_imbe_decoder : public imbe_decoder {
public:

   /**
    * offline_imbe_decoder default constructor.
    */
   offline_imbe_decoder();

   /**
    * offline_imbe_decoder (virtual) destructor.
    */
   virtual ~offline_imbe_decoder();

   /**
    * Dump voice_codeword in_out to file.
    *
    * \param cw IMBE codewords and parity.
    */
   virtual void decode(const voice_codeword& cw);

private:

   /**
    * The output file.
    */
   FILE *d_fp;

};

#endif /* INCLUDED_OFFLINE_IMBE_DECODER_H */
