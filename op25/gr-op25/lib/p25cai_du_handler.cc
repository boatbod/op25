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
 * or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
 * License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with OP25; see the file COPYING. If not, write to the Free
 * Software Foundation, Inc., 51 Franklin Street, Boston, MA
 * 02110-1301, USA.
 */

#include "p25cai_du_handler.h"

#include <arpa/inet.h>
#include <cstdio>
#include <cstring>
#include <errno.h>
#include <iomanip>
#include <netinet/in.h>
#include <sstream>
#include <sys/socket.h>
#include <sys/socket.h>

using namespace std;

p25cai_du_handler::p25cai_du_handler(data_unit_handler_sptr next, const char *addr, int port) :
   data_unit_handler(next),
   d_cai(-1),
   d_address("Unavailable")
{
	struct sockaddr_in sin;
	sin.sin_family = AF_INET;
	sin.sin_port = htons(port);
	inet_aton(addr, &sin.sin_addr);
	d_cai = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
	if(-1 != d_cai) {
      if(-1 != connect(d_cai, (struct sockaddr*) &sin, sizeof(sin))) {
         ostringstream address;
         address << addr << ":" << port;
         d_address = address.str();
      } else {
         printf("error %d: %s\n", errno, strerror(errno));
         perror("connect(d_tap, (struct sockaddr*) &sin, sizeof(sin))");
         close(d_cai);
         d_cai = -1;
      }
   } else {
		perror("socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)");
      d_cai = -1;
   }
}

p25cai_du_handler::~p25cai_du_handler()
{
   if(-1 != d_cai) {
      close(d_cai);
   }
}

const char*
p25cai_du_handler::destination() const
{
   return d_address.c_str();
}

void
p25cai_du_handler::handle(data_unit_sptr du)
{
   if(-1 != d_cai) {
      const size_t CAI_SZ = du->size();
      uint8_t cai[CAI_SZ];
      du->decode_frame(CAI_SZ, cai);
      if (write(d_cai, cai, CAI_SZ) < 0)
         printf("error %d: %s\n", errno, strerror(errno));
   }
   data_unit_handler::handle(du);
}
