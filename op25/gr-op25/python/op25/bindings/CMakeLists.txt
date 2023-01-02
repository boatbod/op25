# Copyright 2020 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

########################################################################
# Check if there is C++ code at all
########################################################################
if(NOT op25_sources)
    MESSAGE(STATUS "No C++ sources... skipping python bindings")
    return()
endif(NOT op25_sources)

########################################################################
# Check for pygccxml
########################################################################
GR_PYTHON_CHECK_MODULE_RAW(
    "pygccxml"
    "import pygccxml"
    PYGCCXML_FOUND
    )

include(GrPybind)

########################################################################
# Python Bindings
########################################################################

list(APPEND op25_python_files
    decoder_bf_python.cc
    decoder_ff_python.cc
    fsk4_demod_ff_python.cc
    fsk4_slicer_fb_python.cc
    pcap_source_b_python.cc
    python_bindings.cc)

GR_PYBIND_MAKE_OOT(op25
   ../../..
   gr::op25
   "${op25_python_files}")

# copy in bindings .so file for use in QA test module
add_custom_target(
  copy_bindings_for_tests ALL
  COMMAND
    ${CMAKE_COMMAND} -E copy "${CMAKE_CURRENT_BINARY_DIR}/*.so"
    ${CMAKE_BINARY_DIR}/test_modules/gnuradio/op25/
  DEPENDS op25_python)

install(TARGETS op25_python DESTINATION ${GR_PYTHON_DIR}/gnuradio/op25 COMPONENT pythonapi)
