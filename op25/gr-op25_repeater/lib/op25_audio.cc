/* -*- c++ -*- */
/* 
 * Copyright 2017-2025 Graham J Norbury, gnorbury@bondcar.com
 * from op25_audio; rewrite Nov 2017 Copyright 2017 Max H. Parke KA1RBI
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
#include <stdint.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <netdb.h>
#include <vector>
#include <algorithm>

#include "op25_audio.h"
#include "url_parser.h"

// convert hostname to ip address
static int hostname_to_ip(const char *hostname , char *ip)
{
    struct addrinfo hints, *servinfo, *p;
    struct sockaddr_in *h;
    int rv;
 
    memset(&hints, 0, sizeof hints);
    hints.ai_family = AF_UNSPEC; // use AF_INET6 to force IPv6
    hints.ai_socktype = SOCK_DGRAM;
 
    if ( (rv = getaddrinfo( hostname , NULL , &hints , &servinfo)) != 0) 
    {
        fprintf(stderr, "op25_audio::hostname_to_ip() getaddrinfo: %s\n", gai_strerror(rv));
        return -1;
    }
 
    // loop through all the results and connect to the first we can
    for(p = servinfo; p != NULL; p = p->ai_next) 
    {
        h = (struct sockaddr_in *) p->ai_addr;
        if (h->sin_addr.s_addr != 0)
        {
            strcpy(ip , inet_ntoa( h->sin_addr ) );
            break;
        }
    }
     
    freeaddrinfo(servinfo); // all done with this structure
    return 0;
}

// tokenize a string using a delimiter
void tokenize(std::string str, std::vector<std::string> &token_v, std::string delim)
{
    size_t start = str.find_first_not_of(delim), end=start;

    while (start != std::string::npos) {
        end = str.find(delim, start);
        token_v.push_back(str.substr(start, end-start));
        start = str.find_first_not_of(delim, end);
    }
}

// constructor (legacy p25_frame_assembler entry point)
op25_audio::op25_audio(const char* udp_host, int port, log_ts& logger, int debug, int msgq_id) :
    d_udp_enabled(false),
    d_debug(debug),
    d_msgq_id(msgq_id),
    d_write_port(port),
    d_audio_port(port),
    d_write_sock(0),
    d_file_enabled(false),
    logts(logger),
    d_ws_enabled(false),
    d_ws_port(port)
{
    d_ws_connections.clear();
    char ip[20];
    if (hostname_to_ip(udp_host, ip) == 0)
    {
        strncpy(d_udp_host, ip, sizeof(d_udp_host));
        d_udp_host[sizeof(d_udp_host)-1] = 0;
        if ( port )
            open_socket();
    }
}

// destructor
op25_audio::~op25_audio()
{
    if (d_file_enabled)
        close(d_write_sock);
    close_socket();
    ws_stop();
}

// constructor
op25_audio::op25_audio(const char* destination, log_ts& logger, int debug, int msgq_id) :
    d_udp_enabled(false),
    d_debug(debug),
    d_msgq_id(msgq_id),
    d_write_port(0),
    d_audio_port(23456),
    d_write_sock(0),
    d_file_enabled(false),
    logts(logger),
    d_ws_enabled(false),
    d_ws_port(9000)
{
    static const std::string P_UDP  = "udp";
    static const std::string P_FILE = "file";
    static const std::string P_WS   = "ws";
    d_ws_host.clear();
    d_ws_connections.clear();

    std::string dest_str(destination);
    std::vector<std::string> destinations;
    dest_str.erase(remove_if(dest_str.begin(), dest_str.end(), isspace), dest_str.end()); // first strip any whitespace
    tokenize(dest_str, destinations, ",");                                                // then split into individual destinations

    // TODO: the following block needs to be seriously cleaned up!
    for (auto & dest : destinations) {
        URLParser::HTTP_URL dest_url = URLParser::Parse(dest);
        fprintf(stderr, "%s op25_audio::op25_audio: destination: %s [schema: %s, host: %s, port: %s]\n",
                logts.get(d_msgq_id), dest.c_str(), dest_url.scheme.c_str(), dest_url.host.c_str(), dest_url.port.c_str());
        if (dest_url.scheme == P_UDP) {
            char ip[20];
            if (hostname_to_ip(dest_url.host.c_str(), ip) == 0) {
                strncpy(d_udp_host, ip, sizeof(d_udp_host)-1);
                d_udp_host[sizeof(d_udp_host)-1] = 0;
                d_write_port = d_audio_port = std::stoi(dest_url.port);
                open_socket();
            }
        } else if (dest_url.scheme == P_FILE) { //TODO: this block of code is broken
#if 0
            const char * filename = dest.c_str() + P_FILE.length() + 3;
            size_t l = strlen(filename);
            if (l > 4 && (strcmp(&filename[l-4], ".wav") == 0 || strcmp(&filename[l-4], ".WAV") == 0)) {
                fprintf(stderr, "Warning! Output file %s will be written, but in raw form ***without*** a WAV file header!\n", filename);
            }
            d_write_sock = open(filename, O_WRONLY | O_CREAT, 0644);
            if (d_write_sock < 0) {
                fprintf(stderr, "op25_audio::open file %s: error: %d (%s)\n", filename, errno, strerror(errno));
                d_write_sock = 0;
                return;
            }
            d_file_enabled = true;
#endif
        } else if (dest_url.scheme == P_WS) {
            // websocket initialization
            websocketpp::lib::error_code ec;
            d_ws_endpt.set_error_channels(websocketpp::log::elevel::all);
            d_ws_endpt.set_access_channels(websocketpp::log::alevel::all ^ websocketpp::log::alevel::frame_payload);
            d_ws_endpt.init_asio();
            d_ws_endpt.set_open_handler(std::bind(&op25_audio::ws_open_handler, this, std::placeholders::_1));
            d_ws_endpt.set_close_handler(std::bind(&op25_audio::ws_close_handler, this, std::placeholders::_1));
            d_ws_endpt.set_fail_handler(std::bind(&op25_audio::ws_fail_handler, this, std::placeholders::_1));
            d_ws_endpt.set_message_handler(std::bind(&op25_audio::ws_msg_handler, this, std::placeholders::_1, std::placeholders::_2));
            d_ws_host = dest_url.host;
            d_ws_port = std::stoi(dest_url.port);
            d_ws_endpt.listen(dest_url.host, dest_url.port, ec);
            if (ec) {
                fprintf(stderr, "%s op25_audio::op25_audio: port [%d], websocket listen error: %s\n", logts.get(d_msgq_id), d_ws_port, ec.message().c_str());
            } else
            {
                d_ws_endpt.start_accept();
                ws_start();
                d_ws_enabled = true;
            }
        }
    }
}
// open socket and set up data structures
void op25_audio::open_socket()
{
    memset (&d_sock_addr, 0, sizeof(d_sock_addr));

    // open handle to socket
    d_write_sock = socket(PF_INET, SOCK_DGRAM, 17);   // UDP socket
    if ( d_write_sock < 0 )
    {
        fprintf(stderr, "%s op25_audio::open_socket: error: %d\n", logts.get(d_msgq_id), errno);
        d_write_sock = 0;
        return;
    }

    // set up data structure for generic udp host/port
    if ( !inet_aton(d_udp_host, &d_sock_addr.sin_addr) )
    {
        fprintf(stderr, "%s op25_audio::open_socket: inet_aton: bad IP address\n", logts.get(d_msgq_id));
        close(d_write_sock);
	d_write_sock = 0;
	return;
    }
    d_sock_addr.sin_family = AF_INET;

    fprintf(stderr, "%s op25_audio::open_socket: enabled udp host(%s), wireshark(%d), audio(%d)\n", logts.get(d_msgq_id), d_udp_host, d_write_port, d_audio_port);
    d_udp_enabled = true;
}

// close socket
void op25_audio::close_socket()
{
        if (!d_udp_enabled)
            return;
        close(d_write_sock);
        d_write_sock = 0;
        d_udp_enabled = false;
}

ssize_t op25_audio::do_send(const void * buf, size_t len, int port, bool is_ctrl )
{
        ssize_t rc = 0;
        struct sockaddr_in tmp_sockaddr;
        if (len <= 0)
            return 0;
        if (d_udp_enabled) {
            memcpy(&tmp_sockaddr, &d_sock_addr, sizeof(struct sockaddr));
            tmp_sockaddr.sin_port = htons(port);
            rc = sendto(d_write_sock, buf, len, 0, (struct sockaddr *)&tmp_sockaddr, sizeof(struct sockaddr_in));
            if (rc == -1)
            {
                fprintf(stderr, "%s op25_audio::do_send: length:(%lu): error:(%d): %s\n", logts.get(d_msgq_id), len, errno, strerror(errno));
                rc = 0;
            }
        } else if (d_file_enabled && !is_ctrl) {
            size_t amt_written = 0;
            for (;;) {
                rc = write(d_write_sock, amt_written + (char*)buf, len - amt_written);
                if (rc < 0) {
                    fprintf(stderr, "%s op25_audio::write(length %lu): error(%d): %s\n", logts.get(d_msgq_id), len, errno, strerror(errno));
                    rc = 0;
                } else if (rc == 0) {
                    fprintf(stderr, "%s op25_audio::write(length %lu): error, write rc zero\n", logts.get(d_msgq_id), len);
                } else {
                    amt_written += rc;
                }
                if (rc <= 0 || amt_written >= len)
                    break;
            } /* end of for() */
            rc = amt_written;
        }
        return rc;
}

// send generic data to destination
ssize_t op25_audio::send_to(const void *buf, size_t len)
{
    return do_send(buf, len, d_write_port, false);
}

// send audio data to destination
ssize_t op25_audio::send_audio(const void *buf, size_t len)
{
    ws_send_audio(buf, len);
    return do_send(buf, len, d_audio_port, false);
}

// send audio data on specifed channel to destination
ssize_t op25_audio::send_audio_channel(const void *buf, size_t len, ssize_t slot_id)
{
    return do_send(buf, len, d_audio_port + slot_id*2, false);
}

// send flag to audio destination 
ssize_t op25_audio::send_audio_flag_channel(const udpFlagEnumType udp_flag, ssize_t slot_id)
{
        char audio_flag[2];
        // 16 bit little endian encoding
        audio_flag[0] = (udp_flag & 0x00ff);
        audio_flag[1] = ((udp_flag & 0xff00) >> 8);
        return do_send(audio_flag, 2, d_audio_port + slot_id*2, true);
}

ssize_t op25_audio::send_audio_flag(const op25_audio::udpFlagEnumType udp_flag)
{
        return send_audio_flag_channel(udp_flag, 0);
}

// websocket message handler callback
void op25_audio::ws_msg_handler(websocketpp::connection_hdl hdl, websocketpp::server<websocketpp::config::asio>::message_ptr msg)
{
    d_ws_endpt.send(hdl, msg->get_payload(), msg->get_opcode()); //simple echo server for debugging
}

// websocket open connection callback
void op25_audio::ws_open_handler(websocketpp::connection_hdl hdl)
{
    fprintf(stderr, "%s op25_audio::op25_audio: websocket connection opened\n", logts.get(d_msgq_id));
    d_ws_connections.push_back(hdl);
}

// websocket close connection callback
void op25_audio::ws_close_handler(websocketpp::connection_hdl hdl)
{
    auto it = std::find_if(d_ws_connections.begin(), d_ws_connections.end(), [&hdl](const websocketpp::connection_hdl& ptr1) {
        return ptr1.lock() == hdl.lock();
    } );
    
    if (it != d_ws_connections.end()) {
        d_ws_connections.erase(it);
    }
}

// websocket close connection callback
void op25_audio::ws_fail_handler(websocketpp::connection_hdl hdl)
{
    auto it = std::find_if(d_ws_connections.begin(), d_ws_connections.end(), [&hdl](const websocketpp::connection_hdl& ptr1) {
        return ptr1.lock() == hdl.lock();
    } );
    
    if (it != d_ws_connections.end()) {
        d_ws_connections.erase(it);
    }
}

// websocket send audio message to clients
void op25_audio::ws_send_audio(const void *buf, size_t len)
{
    websocketpp::lib::error_code ec;
    for (auto & hdl : d_ws_connections) {
        if ( hdl.expired() )
            continue;
        d_ws_endpt.send(hdl, buf, len, websocketpp::frame::opcode::binary, ec);
        if (ec) {
            fprintf(stderr, "%s op25_audio::ws_send_audio: port [%d], websocket error: %s\n", logts.get(d_msgq_id), d_ws_port, ec.message().c_str());
        }
    }
}

// websocket server thread
void op25_audio::ws_start()
{
    ws_thread = std::thread([this]() { this->d_ws_endpt.run(); });
    ws_thread.detach();
    d_ws_enabled = true;
    fprintf(stderr, "%s op25_audio::op25_audio: Started websocket server on port %d\n", logts.get(d_msgq_id), d_ws_port);
}

// websocket graceful shutdown
void op25_audio::ws_stop()
{
    fprintf(stderr, "%s op25_audio::op25_audio: Shutting down websocket server on port %d\n", logts.get(d_msgq_id), d_ws_port);
    d_ws_endpt.stop_listening();
    for (auto & hdl : d_ws_connections) {
        if ( hdl.expired() )
            continue;
        d_ws_endpt.close(hdl, 1001, "Shutting down");
    }
    ws_thread.join();
}
