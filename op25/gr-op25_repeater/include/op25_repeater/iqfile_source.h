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

#ifndef INCLUDED_OP25_IQFILE_SOURCE_H
#define INCLUDED_OP25_IQFILE_SOURCE_H

#include <op25_repeater/api.h>
#include <gnuradio/block.h>

namespace gr {
namespace op25_repeater {

/*!
 * \brief IQ file source block
 * \ingroup op25_repeater
 */
class OP25_REPEATER_API iqfile_source : virtual public gr::block
{
public:
    typedef std::shared_ptr<iqfile_source> sptr;

    /*!
     * Build a source block.
     *
     * \param sizeof_stream_item size of the stream items in bytes.
     */
    static sptr make(size_t sizeof_stream_item);
};

} /* namespace op25_repeater */
} /* namespace gr */

#endif /* INCLUDED_OP25_IQFILE_SOURCE_H */
