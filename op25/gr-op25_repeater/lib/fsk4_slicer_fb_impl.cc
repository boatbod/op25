/* -*- c++ -*- */
/* 
 * Copyright 2010, 2011, 2012, 2013 KA1RBI 
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

#include <stdio.h>
#include <gnuradio/io_signature.h>
#include "fsk4_slicer_fb_impl.h"
#include "check_frame_sync.h"

namespace gr {
  namespace op25_repeater {

fsk4_slicer_fb::sptr
fsk4_slicer_fb::make(const int msgq_id, const int debug, const std::vector<float> &slice_levels)
{
   return gnuradio::get_initial_sptr(new fsk4_slicer_fb_impl(msgq_id, debug, slice_levels));
}

static const int MIN_IN = 1;	// mininum number of input streams
static const int MAX_IN = 1;	// maximum number of input streams
static const int MIN_OUT = 1;	// minimum number of output streams
static const int MAX_OUT = 1;	// maximum number of output streams

/*
 * The private constructor
 */
fsk4_slicer_fb_impl::fsk4_slicer_fb_impl(const int msgq_id, const int debug, const std::vector<float> &slice_levels)
    : gr::sync_block("fsk4_slicer_fb",
                     gr::io_signature::make (MIN_IN, MAX_IN, sizeof (float)),
                     gr::io_signature::make (MIN_OUT, MAX_OUT, sizeof (unsigned char))),
    d_msgq_id(msgq_id),
    d_debug(debug),
    d_accum(0),
    p25dibit(debug, msgq_id)
{
    d_slice_levels[0] = slice_levels[0];
    d_slice_levels[1] = slice_levels[1];
    d_slice_levels[2] = slice_levels[2];
    d_slice_levels[3] = slice_levels[3];
}

/*
 * Our virtual destructor.
 */
fsk4_slicer_fb_impl::~fsk4_slicer_fb_impl()
{
}

int 
fsk4_slicer_fb_impl::work (int noutput_items,
                           gr_vector_const_void_star &input_items,
                           gr_vector_void_star &output_items)
{
    const float *in = (const float *) input_items[0];
    unsigned char *out = (unsigned char *) output_items[0];

    for (int i = 0; i < noutput_items; i++) {
        uint8_t dibit;
        float sym = in[i];
        if (d_slice_levels[3] < 0) {
            dibit = 1;
            if (d_slice_levels[3] <= sym && sym < d_slice_levels[0])
                dibit = 3;
        } else {
            dibit = 3;
            if (d_slice_levels[2] <= sym && sym < d_slice_levels[3])
                dibit = 1;
        }

        if (d_slice_levels[0] <= sym && sym < d_slice_levels[1])
            dibit = 2;
        if (d_slice_levels[1] <= sym && sym < d_slice_levels[2])
            dibit = 0;

        // look for rotated dibits
        d_accum <<= 2;
        d_accum |= dibit;
        if(((d_accum & P25_FRAME_SYNC_MASK) ^ P25_FRAME_SYNC_MAGIC) == 0) {
            p25dibit.set_fs_index(P25_FRAME_SYNC_MAGIC);
        }
        else if(((d_accum & P25P2_FRAME_SYNC_MASK) ^ P25P2_FRAME_SYNC_MAGIC) == 0) {
            p25dibit.set_fs_index(P25P2_FRAME_SYNC_MAGIC);
        }
        else if(((d_accum & P25_FRAME_SYNC_MASK) ^ P25_FRAME_SYNC_REV_P) == 0) {
            p25dibit.set_fs_index(P25_FRAME_SYNC_REV_P);
        }
        else if(((d_accum & P25P2_FRAME_SYNC_MASK) ^ P25P2_FRAME_SYNC_REV_P) == 0) {
            p25dibit.set_fs_index(P25P2_FRAME_SYNC_REV_P);
        }
        else if(((d_accum & P25_FRAME_SYNC_MASK) ^ P25_FRAME_SYNC_N1200) == 0) {
            p25dibit.set_fs_index(P25_FRAME_SYNC_N1200);
        }
        else if(((d_accum & P25P2_FRAME_SYNC_MASK) ^ P25P2_FRAME_SYNC_N1200) == 0) {
            p25dibit.set_fs_index(P25P2_FRAME_SYNC_N1200);
        }
        else if(((d_accum & P25_FRAME_SYNC_MASK) ^ P25_FRAME_SYNC_P1200) == 0) {
            p25dibit.set_fs_index(P25_FRAME_SYNC_P1200);
        }
        else if(((d_accum & P25P2_FRAME_SYNC_MASK) ^ P25P2_FRAME_SYNC_P1200) == 0) {
            p25dibit.set_fs_index(P25P2_FRAME_SYNC_P1200);
        }
        else if(((d_accum & P25_FRAME_SYNC_MASK) ^ P25_FRAME_SYNC_X2400) == 0) {
            p25dibit.set_fs_index(P25_FRAME_SYNC_X2400);
        }
        else if(((d_accum & P25P2_FRAME_SYNC_MASK) ^ P25P2_FRAME_SYNC_X2400) == 0) {
            p25dibit.set_fs_index(P25P2_FRAME_SYNC_X2400);
        }
        // de-rotate output
        out[i] = p25dibit.dibit_map()[dibit];
    }

    // Tell runtime system how many output items we produced.
    return noutput_items;
}

  } /* namespace op25_repeater */
} /* namespace gr */
