# Copyright 2011,2012 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.

########################################################################
# Setup library
########################################################################
include(GrPlatform) #define LIB_SUFFIX

include_directories(${Boost_INCLUDE_DIR})
link_directories(${Boost_LIBRARY_DIRS})
list(APPEND op25_sources
    fsk4_demod_ff_impl.cc
    fsk4_slicer_fb_impl.cc
    decoder_bf_impl.cc
    decoder_ff_impl.cc
    abstract_data_unit.cc
    data_unit.cc
    hdu.cc
    ldu1.cc
    ldu2.cc
    pdu.cc
    tdu.cc
    tsbk.cc
    data_unit_handler.cc
    logfile_du_handler.cc
    p25cai_du_handler.cc
    snapshot_du_handler.cc
    imbe_decoder.cc
    imbe_decoder_factory.cc
    dummy_imbe_decoder.cc
    offline_imbe_decoder.cc
    voice_data_unit.cc
    voice_du_handler.cc
    pcap_source_b_impl.cc
    software_imbe_decoder.cc
    vc55_imbe_decoder.cc
    value_string.cc
    pickle.cc
    pcap_source_b_impl.cc
)

add_library(gnuradio-op25 SHARED ${op25_sources})
target_link_libraries(gnuradio-op25 ${Boost_LIBRARIES} ${GNURADIO_RUNTIME_LIBRARIES} itpp pcap)
set_target_properties(gnuradio-op25 PROPERTIES DEFINE_SYMBOL "gnuradio_op25_EXPORTS")

########################################################################
# Install built library files
########################################################################
install(TARGETS gnuradio-op25
    LIBRARY DESTINATION lib${LIB_SUFFIX} # .so/.dylib file
    ARCHIVE DESTINATION lib${LIB_SUFFIX} # .lib file
    RUNTIME DESTINATION bin              # .dll file
)

########################################################################
# Build and register unit test
########################################################################
include(GrTest)

include_directories(${CPPUNIT_INCLUDE_DIRS})

list(APPEND test_op25_sources
    ${CMAKE_CURRENT_SOURCE_DIR}/test_op25.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/qa_op25.cc
)

add_executable(test-op25 ${test_op25_sources})

target_link_libraries(
  test-op25
  ${GNURADIO_RUNTIME_LIBRARIES}
  ${Boost_LIBRARIES}
  ${CPPUNIT_LIBRARIES}
  gnuradio-op25
)

GR_ADD_TEST(test_op25 test-op25)
