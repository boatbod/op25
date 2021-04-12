/* -*- c++ -*- */
/* 
 * Copyright 2021 Graham Norbury - gnorbury@bondcar.com
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

#ifndef INCLUDED_OP25_REPEATER_IQFILE_SOURCE_IMPL_H
#define INCLUDED_OP25_REPEATER_IQFILE_SOURCE_IMPL_H

#include <op25_repeater/iqfile_source.h>

namespace gr {
namespace op25_repeater {

class iqfile_source_impl : public iqfile_source
{
public:
    iqfile_source_impl(size_t sizeof_stream_item);
    ~iqfile_source_impl() override;

    int work(int noutput_items,
             gr_vector_const_void_star& input_items,
             gr_vector_void_star& output_items) override;
};

} /* namespace op25_repeater */
} /* namespace gr */

#endif /* INCLUDED_OP25_REPEATER_IQFILE_SOURCE_IMPL_H */
