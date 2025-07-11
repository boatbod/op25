/* -*- C++ -*- */

%feature("autodoc", "1");

%{
#include <stddef.h>
%}

%include "exception.i"
%import "gnuradio.i"

%{
#include "gnuradio/swig/gnuradio_swig_bug_workaround.h"
#include "op25_fsk4_demod_ff.h"
%}

// ----------------------------------------------------------------

/*
 * This does some behind-the-scenes magic so we can
 * access fsk4_square_ff from python as fsk4.square_ff
 */
GR_SWIG_BLOCK_MAGIC(op25, fsk4_demod_ff);

/*
 * Publicly-accesible default constuctor function for op25_fsk4_demod_bf.
 */
op25_fsk4_demod_ff_sptr op25_make_fsk4_demod_ff(gr::msg_queue::sptr queue, float sample_rate, float symbol_rate);

class op25_fsk4_demod_ff : public gr_block
{
private:
  op25_fsk4_demod_ff(gr::msg_queue::sptr queue, float sample_rate, float symbol_rate);
};

// ----------------------------------------------------------------

