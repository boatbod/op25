/* -*- c++ -*- */
/* 
 * GNU Radio interface for Pavel Yazev's Project 25 IMBE Encoder/Decoder
 * 
 * Copyright 2009 Pavel Yazev E-mail: pyazev@gmail.com
 * Copyright 2009, 2010, 2011, 2012, 2013, 2014 KA1RBI
 * 
 * This is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * This software is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this software; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <gnuradio/io_signature.h>
#include "p25p1_voice_encode.h"

#include <vector>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

#include "imbe_vocoder/imbe_vocoder.h"
#include "p25_frame.h"
#include "op25_imbe_frame.h"

namespace gr {
  namespace op25_repeater {

/* bits to be preset to 1 for all transmitted frames */
static const bool ldu1_preset[] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 0-35 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1, /* 36-71 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 72-107 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 108-143 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 144-179 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 180-215 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 216-251 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 252-287 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 288-323 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 324-359 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 360-395 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 396-431 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 432-467 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1, /* 468-503 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 504-539 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 540-575 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 576-611 */
  0,1,0,1,1,0,1,1,0,1,0,1,0,1,0,1,1,0,0,1,0,1,0,1,0,1,1,0,0,0,0,0,0,0,1,0, /* 612-647 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 648-683 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 684-719 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 720-755 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,1,0, /* 756-791 */
  1,0,1,0,0,1,1,0,1,0,1,0,1,0,0,1,1,0,1,0,1,0,1,0,0,1,1,0,1,0,1,0,1,0,0,1, /* 792-827 */
  1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 828-863 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 864-899 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1, /* 900-935 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 936-971 */
  0,0,0,0,0,0,1,0,1,1,1,0,0,0,0,1,1,1,1,1,0,0,1,1,1,1,1,0,0,1,0,1,0,1,1,0, /* 972-1007 */
  0,1,0,0,1,0,0,1,0,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1008-1043 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1044-1079 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1080-1115 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1116-1151 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,1,1,1,1,0,1,1, /* 1152-1187 */
  1,1,1,1,0,0,1,1,1,1,0,0,0,0,1,0,0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1188-1223 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1224-1259 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1260-1295 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1296-1331 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,1,0,0,0,0,1,1, /* 1332-1367 */
  1,1,1,0,1,1,0,1,1,1,0,0,1,0,1,1,0,1,0,0,0,1,1,0,1,1,1,0,0,1,0,0,0,0,0,0, /* 1368-1403 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1404-1439 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1440-1475 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1476-1511 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1512-1547 */
  1,0,1,0,1,0,0,1,0,0,0,0,1,0,1,0,1,0,1,0,1,0,0,1,0,0,0,0,1,0,0,0,0,0,1,0, /* 1548-1583 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1584-1619 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1620-1655 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1656-1691 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0  /* 1692-1727 */
};

static const bool ldu2_preset[] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 0-35 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1, /* 36-71 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 72-107 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 108-143 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 144-179 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 180-215 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 216-251 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 252-287 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 288-323 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 324-359 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 360-395 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 396-431 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 432-467 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1, /* 468-503 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 504-539 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 540-575 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 576-611 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 612-647 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 648-683 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 684-719 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 720-755 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 756-791 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 792-827 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 828-863 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 864-899 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1, /* 900-935 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 936-971 */
  0,0,0,0,0,0,1,0,0,0,0,0,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 972-1007 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1008-1043 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1044-1079 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1080-1115 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1116-1151 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,1,0,1,1,1,0,1,0,0,0,1,0,1,1,0,1,0,0, /* 1152-1187 */
  1,0,0,0,1,0,1,1,0,1,1,0,0,1,0,0,1,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1188-1223 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1224-1259 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1260-1295 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1296-1331 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,1,1,0,1,0,1,0,1,1, /* 1332-1367 */
  1,1,1,1,0,1,0,0,1,1,1,1,0,0,0,1,1,1,1,1,1,1,0,1,0,1,1,0,0,0,0,0,0,0,0,0, /* 1368-1403 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1404-1439 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1440-1475 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1476-1511 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1512-1547 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1548-1583 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1584-1619 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1620-1655 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, /* 1656-1691 */
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0, /* 1692-1727 */
};

static void clear_bits(bit_vector& v) {
	for (size_t i=0; i<v.size(); i++) {
		v[i]=0;
	}
}

/* ------------------------------------------------------------------------
 * Runtime P25 NAC and Link Control.
 *
 * op25's historic transmitter baked NAC 0x293 into the NID words (hws[]) and a
 * fixed Link Control into ldu1_preset[] (LCF 0 / MFID 0 / TGID 0x5555 / src
 * 0xAAAAAA). A licensed operator keying a specific repeater needs the NAC
 * settable, and a repeater that validates the LC needs a real one. These
 * helpers compute both at runtime. The FEC is ported verbatim from op25's own
 * apps/tx/p25craft.py (bch_64_16_23_encode / rs_24_12_13_encode /
 * hamming_10_6_3_encode), so a frame round-trips through op25's own receiver
 * (lib/bch.cc, lib/p25p1_fdma.cc). Verified in Python against the baked hws[]
 * and ldu1_preset[] before this was written: the default NAC/LC reproduce them
 * bit for bit.
 * ---------------------------------------------------------------------- */

// (64,16,23) BCH NID encoder (p25craft.bch_64_16_23_encode).
static uint64_t bch_64_16_23_encode(uint16_t data) {
	static const uint64_t matrix[16] = {
		0x8000cd930bdd3b2aULL, 0x4000ab5a8e33a6beULL,
		0x2000983e4cc4e874ULL, 0x10004c1f2662743aULL,
		0x0800eb9c98ec0136ULL, 0x0400b85d47ab3bb0ULL,
		0x02005c2ea3d59dd8ULL, 0x01002e1751eaceecULL,
		0x0080170ba8f56776ULL, 0x0040c616dfa78890ULL,
		0x0020630b6fd3c448ULL, 0x00103185b7e9e224ULL,
		0x000818c2dbf4f112ULL, 0x0004c1f2662743a2ULL,
		0x0002ad6a38ce9afbULL, 0x00019b2617ba7657ULL };
	uint64_t cw = 0;
	for (int i = 0; i < 16; i++)
		if (data & (0x8000 >> i)) cw ^= matrix[i];
	return cw;
}

// GF(2^6) multiply, primitive poly x^6+x+1 (p25craft.gf6mult).
static uint8_t gf6mult(uint8_t a, uint8_t b) {
	uint8_t p = 0;
	for (int i = 0; i < 6; i++) {
		if (b & 1) p ^= a;
		a <<= 1;
		if (a & 0x40) a ^= 0x43;
		b >>= 1;
	}
	return p & 0x3f;
}

// (24,12,13) shortened Reed-Solomon LC encoder: 12 hexbits in -> 24 hexbits out
// (p25craft.rs_24_12_13_encode).
static const uint8_t rs_24_12_13_matrix[12][24] = {
	{1,0,0,0,0,0,0,0,0,0,0,0,062,044,003,025,014,016,027,003,053,004,036,047},
	{0,1,0,0,0,0,0,0,0,0,0,0,011,012,011,011,016,064,067,055,001,076,026,073},
	{0,0,1,0,0,0,0,0,0,0,0,0,003,001,005,075,014,006,020,044,066,006,070,066},
	{0,0,0,1,0,0,0,0,0,0,0,0,021,070,027,045,016,067,023,064,073,033,044,021},
	{0,0,0,0,1,0,0,0,0,0,0,0,030,022,003,075,015,015,033,015,051,003,053,050},
	{0,0,0,0,0,1,0,0,0,0,0,0,001,041,027,056,076,064,021,053,004,025,001,012},
	{0,0,0,0,0,0,1,0,0,0,0,0,061,076,021,055,076,001,063,035,030,013,064,070},
	{0,0,0,0,0,0,0,1,0,0,0,0,024,022,071,056,021,035,073,042,057,074,043,076},
	{0,0,0,0,0,0,0,0,1,0,0,0,072,042,005,020,043,047,033,056,001,016,013,076},
	{0,0,0,0,0,0,0,0,0,1,0,0,072,014,065,054,035,025,041,016,015,040,071,026},
	{0,0,0,0,0,0,0,0,0,0,1,0,073,065,036,061,042,022,017,004,044,020,025,005},
	{0,0,0,0,0,0,0,0,0,0,0,1,071,005,055,003,071,034,060,011,074,002,041,050}};

static void rs_24_12_13_encode(const uint8_t hexbits[12], uint8_t cw[24]) {
	for (int i = 0; i < 24; i++) cw[i] = 0;
	for (int i = 0; i < 24; i++)
		for (int j = 0; j < 12; j++)
			cw[i] ^= gf6mult(hexbits[j], rs_24_12_13_matrix[j][i]);
}

// (10,6,3) shortened Hamming encoder (p25craft.hamming_10_6_3_encode).
static uint16_t hamming_10_6_3_encode(uint8_t data) {
	static const uint16_t matrix[6] = {0x20e, 0x10d, 0x08b, 0x047, 0x023, 0x01c};
	uint16_t cw = 0;
	for (int i = 0; i < 6; i++)
		if (data & (0x20 >> i)) cw ^= matrix[i];
	return cw;
}

// Build the 18-octet (144-bit) Link Control Word integer from its fields
// (p25craft.construct_lc; LCF high byte, MFID, service options, then group
// (lco 0) or individual (lco 3) addressing, then the source ID).
static void construct_lcw(uint8_t lco, uint8_t mfid, uint8_t svcopt, uint8_t s,
                          uint16_t tgid, uint32_t dst, uint32_t src,
                          uint64_t& hi, uint64_t& lo) {
	// 72-bit LC: [lcf 8][mfid 8][svcopt 8][addressing 24][src 24].
	// Split across two 64-bit halves (hi holds the top 8 bits).
	uint64_t lcf = lco;              // construct_lcf(0,0,lco): p=sf=0
	__uint128_t lc = (__uint128_t)lcf << 64;
	lc |= (__uint128_t)mfid << 56;
	lc |= (__uint128_t)svcopt << 48;
	if (lco == 0) {                  // group call
		lc |= (__uint128_t)(s & 1) << 32;
		lc |= (__uint128_t)(tgid & 0xffff) << 24;
	} else {                         // individual call (lco == 3)
		lc |= (__uint128_t)(dst & 0xffffff) << 24;
	}
	lc |= (src & 0xffffff);
	hi = (uint64_t)(lc >> 64) & 0xff;
	lo = (uint64_t)lc;
}

// Overlay a Hamming-encoded Link Control onto the 240 LC bit positions of an
// LDU1 frame body (op25_imbe_frame.h: imbe_ldu_ls_data_bits[0..239]).
static void overlay_ldu1_lc(bit_vector& frame_body,
                            uint8_t lco, uint8_t mfid, uint8_t svcopt, uint8_t s,
                            uint16_t tgid, uint32_t dst, uint32_t src) {
	uint64_t hi, lo;
	construct_lcw(lco, mfid, svcopt, s, tgid, dst, src, hi, lo);
	// The 72-bit LC as 12 hexbits (6 bits each), MSB first: hexbit 0 is bits
	// 71..66, which live in `hi` (bits 71..64) + the top of `lo`.
	__uint128_t lc72 = ((__uint128_t)(hi & 0xff) << 64) | lo;
	uint8_t hexbits[12];
	for (int j = 0; j < 12; j++)
		hexbits[j] = (uint8_t)((lc72 >> ((11 - j) * 6)) & 0x3f);
	uint8_t rs[24];
	rs_24_12_13_encode(hexbits, rs);
	// 24 hexbits -> 24 x 10-bit Hamming -> 240 bits, MSB first, into the LC
	// positions.
	int k = 0;
	for (int i = 0; i < 24; i++) {
		uint16_t h = hamming_10_6_3_encode(rs[i]);
		for (int b = 9; b >= 0; b--)
			frame_body[imbe_ldu_ls_data_bits[k++]] = (h >> b) & 1;
	}
}

p25p1_voice_encode::p25p1_voice_encode(bool verbose_flag, int stretch_amt, op25_audio& udp, bool raw_vectors_flag, std::deque<uint8_t> &_output_queue) :
	opt_nac(0x293),       // historic op25 default NAC; set_nac() overrides
	opt_lc_set(false),    // overlay a custom Link Control only once set_lc() ran
	frame_cnt(0),
	write_bufp(0),
	peak_amplitude(0),
	peak(0),
	samp_ct(0),
	codeword_ct(0),
	sampbuf_ct(0),
	stretch_count(0),
	f_body(P25_VOICE_FRAME_SIZE),
	op25audio(udp),
	output_queue(_output_queue),
	opt_dump_raw_vectors(raw_vectors_flag),
	opt_verbose(verbose_flag)
	{
		opt_stretch_amt = 0;
		if (stretch_amt < 0) {
			opt_stretch_sign = -1;
			opt_stretch_amt = 0 - stretch_amt;
		} else {
			opt_stretch_sign = 1;
			opt_stretch_amt = stretch_amt;
		}

		clear_bits(f_body);
	}

    /*
     * Our virtual destructor.
     */
    p25p1_voice_encode::~p25p1_voice_encode()
    {
    }

static const int STATS_INTERVAL = 20;
static const int SAMP_INTERVAL = 8192;

void p25p1_voice_encode::append_imbe_codeword(bit_vector& frame_body, int16_t frame_vector[], unsigned int& codeword_ct)
{
	voice_codeword cw(voice_codeword_sz);
	uint8_t obuf[P25_VOICE_FRAME_SIZE/2];
	// construct 144-bit codeword from 88 bits of parameters
	imbe_header_encode(cw, frame_vector[0], frame_vector[1], frame_vector[2], frame_vector[3], frame_vector[4], frame_vector[5], frame_vector[6], frame_vector[7]);

	// add codeword to voice data unit
	imbe_interleave(frame_body, cw, codeword_ct);

	// after the ninth and final codeword added, dispose of frame
	if (++codeword_ct >= nof_voice_codewords) {
                int ldu_type = frame_cnt & 1;	// set ldu_type = 0(LDU1) or 1(LDU2)
		// NID word carries the (runtime) NAC and the DUID (0x5 LDU1, 0xA LDU2),
		// BCH(64,16,23)-encoded (was baked as hws[] for NAC 0x293).
		static const int duids[2] = { 0x5, 0xA };
		uint64_t hw = bch_64_16_23_encode((uint16_t)((opt_nac << 4) | duids[ldu_type]));
		const bool* ldu_preset = (ldu_type == 0) ? ldu1_preset : ldu2_preset;

		p25_setup_frame_header(frame_body, hw);
		for (size_t i = 0; i < frame_body.size(); i++) {
			frame_body[i] = frame_body[i] | ldu_preset[i];
		}
		// A custom Link Control replaces the preset's baked LC bits in LDU1
		// (LDU2 carries encryption sync / low-speed data, left as the preset).
		if (opt_lc_set && ldu_type == 0)
			overlay_ldu1_lc(frame_body, lc_lco, lc_mfid, lc_svcopt, lc_s,
			                lc_tgid, lc_dst, lc_src);
		// finally, output the frame
		if (op25audio.enabled()) {
			// pack the bits into bytes, MSB first
			size_t obuf_ct = 0;
			for (uint32_t i = 0; i < P25_VOICE_FRAME_SIZE; i += 8) {
				uint8_t b = 
					(frame_body[i+0] << 7) +
					(frame_body[i+1] << 6) +
					(frame_body[i+2] << 5) +
					(frame_body[i+3] << 4) +
					(frame_body[i+4] << 3) +
					(frame_body[i+5] << 2) +
					(frame_body[i+6] << 1) +
					(frame_body[i+7]     );
				obuf[obuf_ct++] = b;
			}
			op25audio.send_to(obuf, obuf_ct);
		} else {
			for (uint32_t i = 0; i < P25_VOICE_FRAME_SIZE; i += 2) {
				uint8_t dibit = 
					(frame_body[i+0] << 1) +
					(frame_body[i+1]     );
				output_queue.push_back(dibit);
			}
		}
		codeword_ct = 0;
		frame_cnt++;
		if (opt_verbose && (frame_cnt % STATS_INTERVAL) == 0) {
			gettimeofday(&tv, &tz);
			int s = tv.tv_sec - oldtv.tv_sec;
			int us = tv.tv_usec - oldtv.tv_usec;
			if (us < 0) {
				us = us + 1000000;
				s  = s - 1;
			}
			float f = us;
			f /= 1000000;
			f += s;
			fprintf (stderr, "time %f peak %5d\n", f / STATS_INTERVAL, peak_amplitude);
			oldtv = tv;
		}
		clear_bits(f_body);
	}
}

void p25p1_voice_encode::compress_frame(int16_t snd[])
{
	int16_t frame_vector[8];	

	// encode 160 audio samples into 88 bits (u0-u7)
	vocoder.imbe_encode(frame_vector, snd);

	// if dump option, dump u0-u7 to output
	if (opt_dump_raw_vectors) {
		char s[128];
		sprintf(s, "%03x %03x %03x %03x %03x %03x %03x %03x\n", frame_vector[0], frame_vector[1], frame_vector[2], frame_vector[3], frame_vector[4], frame_vector[5], frame_vector[6], frame_vector[7]);
		memcpy(&write_buf[write_bufp], s, strlen(s));
		write_bufp += strlen(s);
		if (write_bufp >= 288) {
			op25audio.send_to(write_buf, 288);
			write_bufp = 0;
		}
		return;
	}
	append_imbe_codeword(f_body, frame_vector, codeword_ct);
}

void p25p1_voice_encode::add_sample(int16_t samp)
{
	// add one sample to 160-sample frame buffer and process if filled
	sampbuf[sampbuf_ct++] = samp;
	if (sampbuf_ct >= FRAME) {
		compress_frame(sampbuf);
		sampbuf_ct = 0;
	}

	// track signal amplitudes
	int16_t asamp = (samp < 0) ? 0 - samp : samp;
	peak = (asamp > peak) ? asamp : peak;
	if (++samp_ct >= SAMP_INTERVAL) {
		peak_amplitude = peak;
		peak = 0;
		samp_ct = 0;
	}
}

void p25p1_voice_encode::compress_samp(const int16_t * samp, int len)
{
	// Apply sample rate slew to accomodate sound card rate discrepancy -
	// workaround for USRP underrun problem occurring when sound card
	// capture rate is slower than the correct rate

	// FIXME: autodetect proper value for opt_stretch_amt
	// perhaps by steering the LDU output rate to a 180.0 msec. rate

	for (int i = 0; i < len; i++ ) {
		stretch_count++;
		if (opt_stretch_amt != 0 && stretch_count >= opt_stretch_amt) {
			stretch_count = 0;
			if (opt_stretch_sign < 0)
				// spill this samp
				continue;
				// repeat this samp
			add_sample(samp[i]);
		}
		add_sample(samp[i]);
	}
}

void
p25p1_voice_encode::set_gain_adjust(float gain_adjust) {
	vocoder.set_gain_adjust(gain_adjust);
}

void
p25p1_voice_encode::set_nac(uint16_t nac) {
	opt_nac = nac & 0xfff;
}

void
p25p1_voice_encode::set_lc(uint8_t lco, uint8_t mfid, uint8_t svcopt, uint8_t s,
                           uint16_t tgid, uint32_t dst, uint32_t src) {
	lc_lco = lco; lc_mfid = mfid; lc_svcopt = svcopt; lc_s = s;
	lc_tgid = tgid; lc_dst = dst; lc_src = src;
	opt_lc_set = true;
}

  } /* namespace op25_repeater */
} /* namespace gr */
