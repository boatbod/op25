/* -*- c++ -*- */
/* 
 * Copyright 2021 Graham J. Norbury - gnorbury@bondcar.com
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
#include "iqfile_source_impl.h"
#include <cstring>

namespace gr {
namespace op2_repeater {

iqfile_source::sptr iqfile_source::make(size_t sizeof_stream_item)
{
    return gnuradio::make_block_sptr<iqfile_source_impl>(sizeof_stream_item);
}

iqfile_source_impl::iqfile_source_impl(size_t sizeof_stream_item)
    : sync_block("iqfile_source",
                 io_signature::make(0, 0, 0),
                 io_signature::make(1, -1, sizeof_stream_item))
{
}

iqfile_source_impl::~iqfile_source_impl() {}

int iqfile_source_impl::work(int noutput_items,
                           gr_vector_const_void_star& input_items,
                           gr_vector_void_star& output_items)
{
    void* optr;
    for (size_t n = 0; n < input_items.size(); n++) {
        optr = (void*)output_items[n];
        memset(optr, 0, noutput_items * output_signature()->sizeof_stream_item(n));
    }
    return noutput_items;
}

} /* namespace op25_repeater */
} /* namespace gr */
