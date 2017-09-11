/* -*- c++ -*- */
/* 
 * Copyright 2017 Graham J Norbury, gnorbury@bondcar.com
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

#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

#include "op25_udp.h"

// constructor
op25_udp::op25_udp(const char* udp_host, int port, int debug) :
    d_udp_enabled(false),
    d_write_sock(0),
    d_debug(debug),
    d_write_port(port),
    d_audio_port(port),
    d_udp_host(udp_host)
{
    if ( port )
        open_socket();
}

// destructor
op25_udp::~op25_udp()
{
    close_socket();
}

// open socket and set up data structures
void op25_udp::open_socket()
{
    memset (&d_write_sock_addr, 0, sizeof(d_write_sock_addr));
    memset (&d_audio_sock_addr, 0, sizeof(d_audio_sock_addr));

    // open handle to socket
    d_write_sock = socket(PF_INET, SOCK_DGRAM, 17);   // UDP socket
    if ( d_write_sock < 0 )
    {
        fprintf(stderr, "op25_udp::open_socket(): error: %d\n", errno);
        d_write_sock = 0;
        return;
    }

    // set up data structure for generic udp host/port
    if ( !inet_aton(d_udp_host, &d_write_sock_addr.sin_addr) )
    {
        fprintf(stderr, "op25_udp::open_socket(): inet_aton: bad IP address\n");
        close(d_write_sock);
	d_write_sock = 0;
	return;
    }
    d_write_sock_addr.sin_family = AF_INET;
    d_write_sock_addr.sin_port = htons(d_write_port);

    // set up data structure for audio udp host/port
    if ( !inet_aton(d_udp_host, &d_audio_sock_addr.sin_addr) )
    {
        fprintf(stderr, "op25_udp::open_socket(): inet_aton: bad IP address\n");
        close(d_write_sock);
	d_write_sock = 0;
	return;
    }
    d_audio_sock_addr.sin_family = AF_INET;
    d_audio_sock_addr.sin_port = htons(d_audio_port);

    fprintf(stderr, "op25_udp::open_socket(): enabled udp host(%s), wireshark(%d), audio(%d)\n", d_udp_host, d_write_port, d_audio_port);
    d_udp_enabled = true;
}

// close socket
void op25_udp::close_socket()
{
    if ( d_udp_enabled )
    {
        close(d_write_sock);
        d_write_sock = 0;
        d_udp_enabled = false;
    }
}

// send generic data to destination
ssize_t op25_udp::send_to(const void *buf, size_t len) const
{
    ssize_t rc = 0;
    if (d_udp_enabled && (len > 0))
    {
        rc = sendto(d_write_sock, buf, len, 0, (struct sockaddr *)&d_write_sock_addr, sizeof(d_write_sock_addr));
        if (rc == -1)
        {
            fprintf(stderr, "op25_udp::send_to: error(%d): %s\n", errno, strerror(errno));
            rc = 0;
        }
    }
    return rc;
}

// send audio data to destination
ssize_t op25_udp::send_audio(const void *buf, size_t len) const
{
    ssize_t rc = 0;
    if (d_udp_enabled && (len > 0))
    {
        rc = sendto(d_write_sock, buf, len, 0, (struct sockaddr *)&d_audio_sock_addr, sizeof(d_audio_sock_addr));
        if (rc == -1)
        {
            fprintf(stderr, "op25_udp::send_audio: error(%d): %s\n", errno, strerror(errno));
            rc = 0;
        }
    }
    return rc;
}

// send flag to audio destination 
ssize_t op25_udp::send_audio_flag(const op25_udp::udpFlagEnumType udp_flag) const
{
    ssize_t rc = 0;
    if ( d_udp_enabled )
    {
        char audio_flag[2];
        // 16 bit little endian encoding
        audio_flag[0] = (udp_flag & 0x00ff);
        audio_flag[1] = ((udp_flag & 0xff00) >> 8);
        rc = sendto(d_write_sock, audio_flag, 2, 0, (struct sockaddr *)&d_audio_sock_addr, sizeof(d_audio_sock_addr));
        if (rc == -1)
        {
            fprintf(stderr, "op25_udp::send_audio_flag: error(%d): %s\n", errno, strerror(errno));
            rc = 0;
        }
    }
    return rc;
}
