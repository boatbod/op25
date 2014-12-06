/* -*- c++ -*- */
/* 
 * Copyright 2010,2011 Steve Glass
 * 
 * This file is part of OP25.
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
#include "pcap_source_b_impl.h"

#define PCAP_DONT_INCLUDE_PCAP_BPF_H
#include <pcap/pcap.h>

using namespace std;

namespace gr {
  namespace op25 {

    pcap_source_b::sptr
    pcap_source_b::make(const char *path, float delay)
    {
      return gnuradio::get_initial_sptr
        (new pcap_source_b_impl(path, delay));
    }

    /*
     * The private constructor
     */
    pcap_source_b_impl::pcap_source_b_impl(const char *path, float delay)
      : gr::sync_block("pcap_source_b",
              gr::io_signature::make(0, 0, 0),
              gr::io_signature::make(1, 1, sizeof(uint8_t))),
	loc_(0),
	octets_(/* delay * 1200, 0 */)
    {
      char err[PCAP_ERRBUF_SIZE];
      pcap_t *pcap = pcap_open_offline(path, err);
      if(pcap) {
	struct pcap_pkthdr hdr;
	for(const uint8_t *octets; (octets = pcap_next(pcap, &hdr));) {
	  const size_t ETHERNET_SZ = 14;
	  const size_t IP_SZ = 20;
	  const size_t UDP_SZ = 8;
	  const size_t P25CAI_OFS = ETHERNET_SZ + IP_SZ + UDP_SZ;
	  if(P25CAI_OFS < hdr.caplen) {
            const size_t FRAME_SZ = hdr.caplen - P25CAI_OFS;
#if 0
            // push some zero octets to separate frames
            const size_t SILENCE_OCTETS = 48;
            octets_.resize(octets_.size() + SILENCE_OCTETS, 0);
#endif
            // push octets from frame payload into local buffer
            octets_.reserve(octets_.size() + hdr.caplen - P25CAI_OFS);
            for(size_t i = 0; i < FRAME_SZ; ++i) {
	      octets_.push_back(octets[P25CAI_OFS + i]);
            }
	  }
	}
	pcap_close(pcap);
      } else {
	cerr << "error: failed to open " << path;
	cerr << " (" << err << ")" << endl;
	exit(EXIT_FAILURE);
      }
    }

    /*
     * Our virtual destructor.
     */
    pcap_source_b_impl::~pcap_source_b_impl()
    {
    }

    int
    pcap_source_b_impl::work(int noutput_items,
			  gr_vector_const_void_star &input_items,
			  gr_vector_void_star &output_items)
    {
      try {
	const size_t OCTETS_AVAIL = octets_.size();
	uint8_t *out = reinterpret_cast<uint8_t*>(output_items[0]);
	const int OCTETS_REQD = static_cast<size_t>(noutput_items);
	for(int i = 0; i < OCTETS_REQD; ++i) {
	  out[i] = octets_[loc_++];
	  loc_ %= OCTETS_AVAIL;
	}
	return OCTETS_REQD;
      } catch(const exception& x) {
	cerr << x.what() << endl;
	exit(EXIT_FAILURE);
      } catch(...) {
	cerr << "unhandled exception" << endl;
	exit(EXIT_FAILURE);
      }
    }
  } /* namespace op25 */
} /* namespace gr */

