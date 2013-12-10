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

#include "offline_imbe_decoder.h"
#include "stdint.h"
#include "op25_yank.h"

#include <cstdio>

using namespace std;

offline_imbe_decoder::offline_imbe_decoder()
{
   const char *dev = getenv("IMBE_FILE");
   if(!dev) {
      const char *default_filename = "imbe.dat";
      dev = default_filename;
   }
   d_fp = fopen(dev, "w");
   if(NULL == d_fp) {
      perror("fopen(dev, \"w\");"); // a warning, not an error
   }
}

offline_imbe_decoder::~offline_imbe_decoder()
{
   if(d_fp) {
      fclose(d_fp);
   }
}

void
offline_imbe_decoder::decode(const voice_codeword& cw)
{
   if(d_fp) {
      uint8_t codewords[18];
      extract(cw, 0, 144, codewords);
      if(0 == fwrite(codewords, sizeof(codewords), 1, d_fp)) {
         perror("fwrite(codewords, sizeof(codewords), 1, d_fp)");
         fclose(d_fp);
         d_fp = NULL;
      }
   }
}
