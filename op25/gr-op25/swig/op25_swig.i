/* -*- c++ -*- */

#define OP25_API

%include "gnuradio.i"			// the common stuff

//load generated python docstrings
%include "op25_swig_doc.i"

%{
#include "op25/fsk4_demod_ff.h"
#include "op25/fsk4_slicer_fb.h"
#include "op25/decoder_ff.h"
#include "op25/decoder_bf.h"
#include "op25/pcap_source_b.h"
%}

%include "op25/fsk4_demod_ff.h"
GR_SWIG_BLOCK_MAGIC2(op25, fsk4_demod_ff);
%include "op25/fsk4_slicer_fb.h"
GR_SWIG_BLOCK_MAGIC2(op25, fsk4_slicer_fb);
%include "op25/decoder_ff.h"
GR_SWIG_BLOCK_MAGIC2(op25, decoder_ff);
%include "op25/decoder_bf.h"
GR_SWIG_BLOCK_MAGIC2(op25, decoder_bf);
%include "op25/pcap_source_b.h"
GR_SWIG_BLOCK_MAGIC2(op25, pcap_source_b);
