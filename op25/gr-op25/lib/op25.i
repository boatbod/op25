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
#include "op25_fsk4_slicer_fb.h"
#include "op25_decoder_bf.h"
#include "op25_pcap_source_b.h"
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

/*
 * This does some behind-the-scenes magic so we can invoke
 * op25_make_slicer_fb from python as op25.slicer_fbf.
 */
GR_SWIG_BLOCK_MAGIC(op25, fsk4_slicer_fb);

/*
 * Publicly-accesible default constuctor function for op25_decoder_bf.
 */
op25_fsk4_slicer_fb_sptr op25_make_fsk4_slicer_fb(const std::vector<float> &slice_levels);

/*
 * The op25_fsk4_slicer block. Takes a series of float samples and
 * partitions them into dibit symbols according to the slices_levels
 * provided to the constructor.
 */
class op25_fsk4_slicer_fb : public gr_sync_block
{
private:
   op25_fsk4_slicer_fb (const std::vector<float> &slice_levels);
};

// ----------------------------------------------------------------

/*
 * This does some behind-the-scenes magic so we can invoke
 * op25_make_decoder_bsf from python as op25.decoder_bf.
 */
GR_SWIG_BLOCK_MAGIC(op25, decoder_bf);

/*
 * Publicly-accesible default constuctor function for op25_decoder_bf.
 */
op25_decoder_bf_sptr op25_make_decoder_bf();

/**
 * The op25_decoder_bf block. Accepts a stream of dibit symbols and
 * produces an 8KS/s audio stream.
 */
class op25_decoder_bf : public gr_block
{
private:
   op25_decoder_bf();
public:
   const char *destination() const;
   gr::msg_queue::sptr get_msgq() const;
   void set_msgq(gr::msg_queue::sptr msgq);
};

// ----------------------------------------------------------------

/*
 * This does some behind-the-scenes magic so we can invoke
 * op25_make_pcap_source_b from python as op25.pcap_source_b.
 */
GR_SWIG_BLOCK_MAGIC(op25, pcap_source_b);

/*
 * Publicly-accesible constuctor function for op25_pcap_source.
 */
op25_pcap_source_b_sptr op25_make_pcap_source_b(const char *path, float delay);

/*
 * The op25_pcap_source block. Reads symbols from a tcpdump-formatted
 * file and produces a stream of symbols of the appropriate size.
 */
class op25_pcap_source_b : public gr_sync_block
{
private:
   op25_pcap_source_b(const char *path, float delay);
};

// ----------------------------------------------------------------
