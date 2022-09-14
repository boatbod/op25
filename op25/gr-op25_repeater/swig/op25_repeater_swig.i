/* -*- c++ -*- */

#define OP25_REPEATER_API

%include "gnuradio.i"  // the common stuff

//load generated python docstrings
%include "op25_repeater_swig_doc.i"

%{
#include "op25_repeater/vocoder.h"
#include "op25_repeater/gardner_cc.h"
#include "op25_repeater/costas_loop_cc.h"
#include "op25_repeater/p25_frame_assembler.h"
#include "op25_repeater/frame_assembler.h"
#include "op25_repeater/analog_udp.h"
#include "op25_repeater/iqfile_source.h"
#include "op25_repeater/rmsagc_ff.h"
#include "op25_repeater/fsk4_slicer_fb.h"
#include "op25_repeater/ambe_encoder_sb.h"
#include "op25_repeater/dmr_bs_tx_bb.h"
#include "op25_repeater/ysf_tx_sb.h"
#include "op25_repeater/dstar_tx_sb.h"
%}

%include "op25_repeater/ambe_encoder_sb.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, ambe_encoder_sb);

%include "op25_repeater/dmr_bs_tx_bb.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, dmr_bs_tx_bb);

%include "op25_repeater/ysf_tx_sb.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, ysf_tx_sb);

%include "op25_repeater/dstar_tx_sb.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, dstar_tx_sb);

%include "op25_repeater/vocoder.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, vocoder);

%include "op25_repeater/gardner_cc.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, gardner_cc);

%include "op25_repeater/costas_loop_cc.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, costas_loop_cc);

%include "op25_repeater/p25_frame_assembler.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, p25_frame_assembler);

%include "op25_repeater/frame_assembler.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, frame_assembler);

%include "op25_repeater/rmsagc_ff.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, rmsagc_ff);

%include "op25_repeater/analog_udp.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, analog_udp);

%include "op25_repeater/fsk4_slicer_fb.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, fsk4_slicer_fb);

%include "op25_repeater/iqfile_source.h"
GR_SWIG_BLOCK_MAGIC2(op25_repeater, iqfile_source);

