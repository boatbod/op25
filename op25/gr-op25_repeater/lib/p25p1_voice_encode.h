/* -*- c++ -*- */
/*
 * Copyright 2009, 2010, 2011, 2012, 2013, 2014 Max H. Parke KA1RBI
 *
 * This is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 */

#ifndef INCLUDED_OP25_REPEATER_P25P1_VOICE_ENCODE_H
#define INCLUDED_OP25_REPEATER_P25P1_VOICE_ENCODE_H

#include <sys/time.h>
#include <stdint.h>

#include <deque>
#include <vector>

#include "op25_audio.h"
#include "imbe_vocoder/imbe_vocoder.h"

#include "imbe_decoder.h"
#include "software_imbe_decoder.h"

#include <stddef.h>

namespace gr {
namespace op25_repeater {

typedef std::vector<bool> bit_vector;

/*
 * Runtime P25 parameters corresponding to the values used by p25craft.py.
 */
struct p25_voice_params {
    uint16_t nac;
    uint8_t  status_symbol;

    uint64_t mi;
    uint8_t  mfid;
    uint8_t  algid;
    uint16_t kid;

    uint8_t  lco;
    uint8_t  svcopt;
    uint8_t  explicit_source;

    uint16_t tgid;
    uint32_t dst;
    uint32_t src;

    uint32_t lsd;

    p25_voice_params() :
        nac(0x293),
        status_symbol(0),
        mi(0),
        mfid(0),
        algid(0x80),
        kid(0),
        lco(0),
        svcopt(0),
        explicit_source(0),
        tgid(1),
        dst(1),
        src(1),
        lsd(0)
    {
    }
};

class p25p1_voice_encode
{
public:
    p25p1_voice_encode(
        bool verbose_flag,
        int stretch_amt,
        op25_audio& udp,
        bool raw_vectors_flag,
        std::deque<uint8_t>& output_queue);

    ~p25p1_voice_encode();

    void compress_samp(const int16_t* samp, int len);

    void set_gain_adjust(float gain_adjust);

    /*
     * Configure the metadata generated in LDU1 and LDU2 frames.
     */
    void set_voice_params(const p25_voice_params& params);

    /*
     * Individual setters are provided for callers that do not want to
     * construct a p25_voice_params object.
     */
    void set_nac(uint16_t nac);
    void set_status_symbol(uint8_t status_symbol);
    void set_mi(uint64_t mi);
    void set_mfid(uint8_t mfid);
    void set_algid(uint8_t algid);
    void set_kid(uint16_t kid);
    void set_lco(uint8_t lco);
    void set_svcopt(uint8_t svcopt);
    void set_explicit_source(uint8_t explicit_source);
    void set_tgid(uint16_t tgid);
    void set_destination(uint32_t dst);
    void set_source(uint32_t src);
    void set_lsd(uint32_t lsd);

private:
    static const int RXBUF_MAX = 80;

    int frame_cnt;
    int write_bufp;
    char write_buf[512];

    struct timeval tv;
    struct timezone tz;
    struct timeval oldtv;

    int peak_amplitude;
    int peak;
    int samp_ct;

    char rxbuf[RXBUF_MAX];

    unsigned int codeword_ct;
    int16_t sampbuf[FRAME];
    size_t sampbuf_ct;
    int stretch_count;

    bit_vector f_body;

    imbe_vocoder vocoder;
    op25_audio& op25audio;
    std::deque<uint8_t>& output_queue;

    bool opt_dump_raw_vectors;
    bool opt_verbose;

    int opt_stretch_amt;
    int opt_stretch_sign;
    
    bool hdu_sent;

    p25_voice_params voice_params;

private:
    static uint64_t bch_64_16_23_encode(uint16_t data);
    static uint64_t construct_nid(uint16_t nac, uint8_t duid);

    static uint8_t construct_lcf(
        uint8_t p,
        uint8_t sf,
        uint8_t lco);

    static void construct_lc(
        uint8_t lco,
        uint8_t mfid,
        uint8_t svcopt,
        uint8_t explicit_source,
        uint16_t tgid,
        uint32_t dst,
        uint32_t src,
        uint8_t lc[9]);

    static void construct_es(
        uint64_t mi,
        uint8_t algid,
        uint16_t kid,
        uint8_t es[12]);

    static uint16_t cyclic_16_8_5_encode(uint8_t data);
    static uint32_t ldu1_cyclic(uint32_t lsd);
    static uint32_t ldu2_cyclic(uint32_t lsd);

    static uint16_t hamming_10_6_3_encode(uint8_t data);

    static void bytes_to_6bit_symbols(
        const uint8_t* bytes,
        size_t byte_count,
        std::vector<uint8_t>& symbols);

    static void hamming_encode_rs_symbols(
        const std::vector<uint8_t>& rs_symbols,
        std::vector<uint16_t>& codewords);

    static int frame_bit_index(int logical_dibit);

    static void insert_dibit(
        bit_vector& frame_body,
        int logical_dibit,
        uint8_t dibit);

    static void insert_codeword_bits(
        bit_vector& frame_body,
        int logical_dibit_start,
        const std::vector<uint16_t>& codewords);

	static void insert_status_symbols(
		bit_vector& frame_body,
		uint8_t status_symbol,
		size_t status_count);

    void build_ldu1_metadata(bit_vector& frame_body);
    void build_ldu2_metadata(bit_vector& frame_body);

    void append_imbe_codeword(
        bit_vector& frame_body,
        int16_t frame_vector[],
        unsigned int& codeword_ct);

    void compress_frame(int16_t snd[]);
    void add_sample(int16_t samp);

    void output_frame(const bit_vector& frame_body);

    static void clear_bits(bit_vector& v);
    
    void emit_hdu();

	void output_frame(const bit_vector& frame_body,
		size_t frame_bits);

	static void insert_hdu_golay(bit_vector& frame_body,
		int logical_dibit_start,
		const std::vector<uint8_t>& rs_symbols);
};

} // namespace op25_repeater
} // namespace gr

#endif /* INCLUDED_OP25_REPEATER_P25P1_VOICE_ENCODE_H */
