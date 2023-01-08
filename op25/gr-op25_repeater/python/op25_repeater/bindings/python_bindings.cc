/*
 * Copyright 2020 Free Software Foundation, Inc.
 *
 * This file is part of GNU Radio
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 */

#include <pybind11/pybind11.h>

#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>

namespace py = pybind11;

// Headers for binding functions
/**************************************/
// The following comment block is used for
// gr_modtool to insert function prototypes
// Please do not delete
/**************************************/
// BINDING_FUNCTION_PROTOTYPES(
    void bind_ambe_encoder_sb(py::module& m);
    void bind_analog_udp(py::module& m);
    void bind_costas_loop_cc(py::module& m);
    void bind_dmr_bs_tx_bb(py::module& m);
    void bind_dstar_tx_sb(py::module& m);
    void bind_frame_assembler(py::module& m);
    void bind_fsk4_slicer_fb(py::module& m);
    void bind_gardner_cc(py::module& m);
    void bind_iqfile_source(py::module& m);
    void bind_p25_frame_assembler(py::module& m);
    void bind_rmsagc_ff(py::module& m);
    void bind_vocoder(py::module& m);
    void bind_ysf_tx_sb(py::module& m);
    void bind_message(py::module&);
    void bind_msg_queue(py::module&);
    void bind_msg_handler(py::module&);
// ) END BINDING_FUNCTION_PROTOTYPES


// We need this hack because import_array() returns NULL
// for newer Python versions.
// This function is also necessary because it ensures access to the C API
// and removes a warning.
void* init_numpy()
{
    import_array();
    return NULL;
}

PYBIND11_MODULE(op25_repeater_python, m)
{
    // Initialize the numpy C API
    // (otherwise we will see segmentation faults)
    init_numpy();

    // Allow access to base block methods
    py::module::import("gnuradio.gr");

    /**************************************/
    // The following comment block is used for
    // gr_modtool to insert binding function calls
    // Please do not delete
    /**************************************/
    // BINDING_FUNCTION_CALLS(
        bind_ambe_encoder_sb(m);
        bind_analog_udp(m);
        bind_costas_loop_cc(m);
        bind_dmr_bs_tx_bb(m);
        bind_dstar_tx_sb(m);
        bind_frame_assembler(m);
        bind_fsk4_slicer_fb(m);
        bind_gardner_cc(m);
        bind_iqfile_source(m);
        bind_p25_frame_assembler(m);
        bind_rmsagc_ff(m);
        bind_vocoder(m);
        bind_ysf_tx_sb(m);
        bind_message(m);
        bind_msg_handler(m);
        bind_msg_queue(m);
    // ) END BINDING_FUNCTION_CALLS
}
