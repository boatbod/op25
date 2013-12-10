/* -*- c++ -*- */
/* 
 * GNU Radio interface for Pavel Yazev's Project 25 IMBE Encoder/Decoder
 * 
 * Copyright 2009 Pavel Yazev E-mail: pyazev@gmail.com
 * Copyright 2009, 2010, 2011, 2012, 2013 KA1RBI
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
#include "vocoder_impl.h"

#include <vector>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

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

    vocoder::sptr
    vocoder::make(bool encode_flag, bool verbose_flag, int stretch_amt, char* udp_host, int udp_port, bool raw_vectors_flag)
    {
      return gnuradio::get_initial_sptr
        (new vocoder_impl(encode_flag, verbose_flag, stretch_amt, udp_host, udp_port, raw_vectors_flag));
    }

//////////////////////////////////////////////////////////////
//	enc/dec		udp	operation
//	dec		no	byte input; short output
//	dec		yes	byte input; null output
//	enc		no	short input; char output
//	enc		yes	short input; null output

#define M_IN(encode_flag, udp_port)  (1)
#define M_OUT(encode_flag, udp_port) ((udp_port) ? 0 : 1)
#define S_IN(encode_flag, udp_port)  ((encode_flag) ? sizeof(int16_t) : sizeof(uint8_t))
#define S_OUT(encode_flag, udp_port) ((udp_port) ? 0 : ((encode_flag) ? sizeof(uint8_t) : sizeof(int16_t)))

    /*
     * The private constructor
     */
    vocoder_impl::vocoder_impl(bool encode_flag, bool verbose_flag, int stretch_amt, char* udp_host, int udp_port, bool raw_vectors_flag)
      : gr::block("vocoder",
              gr::io_signature::make (M_IN(encode_flag, udp_port), M_IN(encode_flag, udp_port), S_IN(encode_flag, udp_port)),
              gr::io_signature::make (M_OUT(encode_flag, udp_port), M_OUT(encode_flag, udp_port), S_OUT(encode_flag, udp_port))),
	frame_cnt(0),
	write_sock(0),
	write_bufp(0),
	peak_amplitude(0),
	peak(0),
	samp_ct(0),
	rxbufp(0),
	codeword_ct(0),
	sampbuf_ct(0),
	stretch_count(0),
	save_l(0),
	f_body(P25_VOICE_FRAME_SIZE)
    {
	opt_encode_flag = encode_flag;
	opt_dump_raw_vectors = raw_vectors_flag;
	opt_verbose = verbose_flag;
	opt_udp_port = udp_port;

	opt_stretch_amt = 0;
	if (stretch_amt < 0) {
		opt_stretch_sign = -1;
		opt_stretch_amt = 0 - stretch_amt;
	} else {
		opt_stretch_sign = 1;
		opt_stretch_amt = stretch_amt;
	}

	if (opt_udp_port == 0)
		if (encode_flag) {
			// local output to gr source
			// encoding: an LDU's worth of dibits
			set_output_multiple(P25_VOICE_FRAME_SIZE >> 1);
		} else {
			// decoding: an LDU's worth of audio samples
			// set_output_multiple(FRAME * nof_voice_codewords);
		}
	else
		// remote UDP output
		init_sock(udp_host, opt_udp_port);

	clear_bits(f_body);

	const char *p = getenv("IMBE");
	if (p && strcasecmp(p, "soft") == 0)
		d_software_imbe_decoder = true;
	else
		d_software_imbe_decoder = false;
    }

    /*
     * Our virtual destructor.
     */
    vocoder_impl::~vocoder_impl()
    {
    }

static const int STATS_INTERVAL = 20;
static const int SAMP_INTERVAL = 8192;

void vocoder_impl::append_imbe_codeword(bit_vector& frame_body, int16_t frame_vector[], unsigned int& codeword_ct)
{
	voice_codeword cw(voice_codeword_sz);
	uint8_t obuf[P25_VOICE_FRAME_SIZE/2];
	// construct 144-bit codeword from 88 bits of parameters
	imbe_header_encode(cw, frame_vector[0], frame_vector[1], frame_vector[2], frame_vector[3], frame_vector[4], frame_vector[5], frame_vector[6], frame_vector[7]);

	// add codeword to voice data unit
	imbe_interleave(frame_body, cw, codeword_ct);

	// after the ninth and final codeword added, dispose of frame
	if (++codeword_ct >= nof_voice_codewords) {
		static const uint64_t hws[2] = { 0x293555ef2c653437LL, 0x293aba93bec26a2bLL };
                int ldu_type = frame_cnt & 1;	// set ldu_type = 0(LDU1) or 1(LDU2)
		const bool* ldu_preset = (ldu_type == 0) ? ldu1_preset : ldu2_preset;
		
		p25_setup_frame_header(frame_body, hws[ldu_type]);
		for (size_t i = 0; i < frame_body.size(); i++) {
			frame_body[i] = frame_body[i] | ldu_preset[i];
		}
		// finally, output the frame
		if (opt_udp_port > 0) {
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
			sendto(write_sock, obuf, obuf_ct, 0, (struct sockaddr*)&write_sock_addr, sizeof(write_sock_addr));
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

void vocoder_impl::rxchar(char c)
{
	int16_t snd[FRAME];
	int16_t frame_vector[8];
	int u[8];

	if (c < ' ') {
		if (c == '\n') {
			rxbuf[rxbufp] = 0;
			sscanf(rxbuf, "%x %x %x %x %x %x %x %x", &u[0], &u[1], &u[2], &u[3], &u[4], &u[5], &u[6], &u[7]);
			rxbufp = 0;
			// decode 88 bits, outputs 160 sound samples (8000 rate)
			if (d_software_imbe_decoder) {
				voice_codeword cw(voice_codeword_sz);
				imbe_header_encode(cw, u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7]);
				software_decoder.decode(cw);
				audio_samples *samples = software_decoder.audio();
				for (int i=0; i < FRAME; i++) {
					if (samples->size() > 0) {
						snd[i] = (int16_t)(samples->front() * 32768.0);
						samples->pop_front();
					} else {
						snd[i] = 0;
					}
				}
			} else {
				for (int i=0; i < 8; i++) {
					frame_vector[i] = u[i];
				}
		/* TEST*/	frame_vector[7] >>= 1;
				vocoder.imbe_decode(frame_vector, snd);
			}
			if (opt_udp_port > 0) {
				sendto(write_sock, snd, FRAME * sizeof(int16_t), 0, (struct sockaddr*)&write_sock_addr, sizeof(write_sock_addr));
			} else {
				// add generated samples to output queue
				for (int i = 0; i < FRAME; i++) {
					output_queue_decode.push_back(snd[i]);
				}
			}
		}
		return;
	}
	rxbuf[rxbufp++] = c;
	if (rxbufp >= RXBUF_MAX) {
		rxbufp = RXBUF_MAX - 1;
	}
}

void vocoder_impl::compress_frame(int16_t snd[])
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
			sendto(write_sock, write_buf, 288, 0, (struct sockaddr*)&write_sock_addr, sizeof(write_sock_addr));
			write_bufp = 0;
		}
		return;
	}
	append_imbe_codeword(f_body, frame_vector, codeword_ct);
}

void vocoder_impl::add_sample(int16_t samp)
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

void vocoder_impl::compress_samp(int16_t samp)
{
	// Apply sample rate slew to accomodate sound card rate discrepancy -
	// workaround for USRP underrun problem occurring when sound card
	// capture rate is slower than the correct rate

	// FIXME: autodetect proper value for opt_stretch_amt
	// perhaps by steering the LDU output rate to a 180.0 msec. rate

	stretch_count++;
	if (opt_stretch_amt != 0 && stretch_count >= opt_stretch_amt) {
		stretch_count = 0;
		if (opt_stretch_sign < 0)
			// spill this samp
			return;
		// repeat this samp
		add_sample(samp);
	}
	add_sample(samp);
}

void vocoder_impl::init_sock(char* udp_host, int udp_port)
{
        memset (&write_sock_addr, 0, sizeof(write_sock_addr));
        write_sock = socket(PF_INET, SOCK_DGRAM, 17);   // UDP socket
        if (write_sock < 0) {
                fprintf(stderr, "vocoder: socket: %d\n", errno);
                write_sock = 0;
		return;
        }
        if (!inet_aton(udp_host, &write_sock_addr.sin_addr)) {
                fprintf(stderr, "vocoder: bad IP address\n");
		close(write_sock);
		write_sock = 0;
		return;
	}
        write_sock_addr.sin_family = AF_INET;
        write_sock_addr.sin_port = htons(udp_port);
}

void
vocoder_impl::forecast(int nof_output_items, gr_vector_int &nof_input_items_reqd)
{
   /* When encoding, this block consumes 8000 symbols/s and produces 4800
    * samples/s. That's a sampling rate of 5/3 or 1.66667.
    *
    * When decoding, the block consumes one line of text per voice codeword.
    * Each line of text is exactly 32 bytes.  It outputs 160 samples for each 
    * codeword; the ratio is thus 32/160 = 0.2.
    *
    * Thanks to Matt Mills for catching a bug where this value wasn't set correctly
    */
   const size_t nof_inputs = nof_input_items_reqd.size();
   const int nof_samples_reqd = (opt_encode_flag) ? (1.66667 * nof_output_items) : (0.2 * nof_output_items);
   std::fill(&nof_input_items_reqd[0], &nof_input_items_reqd[nof_inputs], nof_samples_reqd);
}

int 
vocoder_impl::general_work_decode (int noutput_items,
			       gr_vector_int &ninput_items,
			       gr_vector_const_void_star &input_items,
			       gr_vector_void_star &output_items)
{
  const char *in = (const char *) input_items[0];

  for (int i = 0; i < ninput_items[0]; i++){
    rxchar(in[i]);
  }

  // Tell runtime system how many input items we consumed on
  // each input stream.

  consume_each (ninput_items[0]);

  uint16_t *out = reinterpret_cast<uint16_t*>(output_items[0]);
  const int n = std::min(static_cast<int>(output_queue_decode.size()), noutput_items);
  if(0 < n) {
     copy(output_queue_decode.begin(), output_queue_decode.begin() + n, out);
     output_queue_decode.erase(output_queue_decode.begin(), output_queue_decode.begin() + n);
  }
  // Tell runtime system how many output items we produced.
  return n;
}

int 
vocoder_impl::general_work_encode (int noutput_items,
			       gr_vector_int &ninput_items,
			       gr_vector_const_void_star &input_items,
			       gr_vector_void_star &output_items)
{
  const short *in = (const short *) input_items[0];

  for (int i = 0; i < ninput_items[0]; i++){
    compress_samp(in[i]);
  }

  // Tell runtime system how many input items we consumed on
  // each input stream.

  consume_each (ninput_items[0]);

  if (opt_udp_port > 0)		// in udp option, we are a gr sink only
    return 0;

  uint8_t *out = reinterpret_cast<uint8_t*>(output_items[0]);
  const int n = std::min(static_cast<int>(output_queue.size()), noutput_items);
  if(0 < n) {
     copy(output_queue.begin(), output_queue.begin() + n, out);
     output_queue.erase(output_queue.begin(), output_queue.begin() + n);
  }
  // Tell runtime system how many output items we produced.
  return n;
}

int 
vocoder_impl::general_work (int noutput_items,
			       gr_vector_int &ninput_items,
			       gr_vector_const_void_star &input_items,
			       gr_vector_void_star &output_items)
{
	if (opt_encode_flag)
		return general_work_encode(noutput_items, ninput_items, input_items, output_items);
	else
		return general_work_decode(noutput_items, ninput_items, input_items, output_items);
}

  } /* namespace op25_repeater */
} /* namespace gr */
