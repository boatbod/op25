/* -*- c++ -*- */

#define OP25_REPEATER_API

%include "gnuradio.i"			// the common stuff

//load generated python docstrings
%include "op25_repeater_swig_doc.i"

%{
#include "op25_repeater/vocoder.h"
#include "op25_repeater/gardner_costas_cc.h"
#include "op25_repeater/p25_frame_assembler.h"
#include "op25_repeater/fsk4_slicer_fb.h"
%}

%include "op25_repeater/vocoder.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, vocoder);

%include "op25_repeater/gardner_costas_cc.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, gardner_costas_cc);
%include "op25_repeater/p25_frame_assembler.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, p25_frame_assembler);

%include "op25_repeater/fsk4_slicer_fb.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, fsk4_slicer_fb);
