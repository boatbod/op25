/* -*- c++ -*- */
/*
 * GNU Radio interface for Pavel Yazev's Project 25 IMBE Encoder/Decoder
 *
 * Copyright 2009 Pavel Yazev
 * Copyright 2009-2014 KA1RBI
 *
 * This file is based on the original OP25 voice encoder, with the
 * P25 LDU metadata generation adapted from p25craft.py.
 */

#define DEBUG_TX

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include "p25p1_voice_encode.h"

#include <gnuradio/io_signature.h>

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <algorithm>
#include <vector>

#include "ezpwd/rs"
#include "imbe_vocoder/imbe_vocoder.h"
#include "op25_imbe_frame.h"
#include "p25_frame.h"

#include "op25_golay.h"

namespace gr {
namespace op25_repeater {

static const int STATS_INTERVAL = 20;
static const int SAMP_INTERVAL = 8192;

/*
 * Clear a bit vector.
 */
void p25p1_voice_encode::clear_bits(bit_vector& v)
{
    for (size_t i = 0; i < v.size(); ++i)
        v[i] = false;
}

/*
 * Constructor.
 */
p25p1_voice_encode::p25p1_voice_encode(
    bool verbose_flag,
    int stretch_amt,
    op25_audio& udp,
    bool raw_vectors_flag,
    std::deque<uint8_t>& _output_queue,
    log_ts& logger,
    int debug,
    int msgq_id) :

    frame_cnt(0),
    write_bufp(0),
    peak_amplitude(0),
    peak(0),
    samp_ct(0),
    codeword_ct(0),
    sampbuf_ct(0),
    stretch_count(0),
    f_body(P25_VOICE_FRAME_SIZE),
    op25audio(udp),
    output_queue(_output_queue),
    opt_dump_raw_vectors(raw_vectors_flag),
    opt_verbose(verbose_flag),
    opt_stretch_amt(0),
    opt_stretch_sign(1),
    hdu_sent(false),
    voice_params(),
    d_crypt_algs(logger, debug, msgq_id)
{
    memset(write_buf, 0, sizeof(write_buf));
    memset(rxbuf, 0, sizeof(rxbuf));
    memset(sampbuf, 0, sizeof(sampbuf));

    memset(&tv, 0, sizeof(tv));
    memset(&oldtv, 0, sizeof(oldtv));
    memset(&tz, 0, sizeof(tz));

    if (stretch_amt < 0) {
        opt_stretch_sign = -1;
        opt_stretch_amt = -stretch_amt;
    } else {
        opt_stretch_sign = 1;
        opt_stretch_amt = stretch_amt;
    }
    
    clear_bits(f_body);
}

/*
 * Destructor.
 */
p25p1_voice_encode::~p25p1_voice_encode()
{
}

/*
 * Configure all P25 metadata parameters.
 */
void p25p1_voice_encode::set_voice_params(const p25_voice_params& params)
{
    voice_params = params;

    voice_params.nac &= 0x0fff;
    voice_params.status_symbol &= 0x03;
    voice_params.mfid &= 0xff;
    voice_params.algid &= 0xff;
    voice_params.kid &= 0xffff;
    voice_params.key &= 0xffffffffffffffff;
    voice_params.lco &= 0x3f;
    voice_params.svcopt &= 0xff;
    voice_params.explicit_source &= 0x01;
    voice_params.tgid &= 0xffff;
    voice_params.dst &= 0x00ffffff;
    voice_params.src &= 0x00ffffff;
    voice_params.verbosity &= 0xFF;
}

/*
 * Individual parameter setters.
 */
void p25p1_voice_encode::set_nac(uint16_t nac)
{
    voice_params.nac = nac & 0x0fff;
}

void p25p1_voice_encode::set_status_symbol(uint8_t status_symbol)
{
    voice_params.status_symbol = status_symbol & 0x03;
}

void p25p1_voice_encode::set_mi(uint64_t mi)
{
    voice_params.mi = mi & 0xffffffffffffffffULL;
}

void p25p1_voice_encode::set_mfid(uint8_t mfid)
{
    voice_params.mfid = mfid;
}

void p25p1_voice_encode::set_algid(uint8_t algid)
{
    voice_params.algid = algid;
}

void p25p1_voice_encode::set_kid(uint16_t kid)
{
    voice_params.kid = kid;
}

void p25p1_voice_encode::set_key(const std::vector<uint8_t>& key)
{
    d_crypt_algs.key(voice_params.kid, voice_params.algid, key);
}

void p25p1_voice_encode::set_crypt_key(uint16_t kid, uint8_t algid, const std::vector<uint8_t>& key)
{
    d_crypt_algs.key(kid, algid, key);
    voice_params.kid = kid;
    voice_params.algid = algid;
}

void p25p1_voice_encode::set_lco(uint8_t lco)
{
    voice_params.lco = lco & 0x3f;
}

void p25p1_voice_encode::set_svcopt(uint8_t svcopt)
{
    voice_params.svcopt = svcopt;
}

void p25p1_voice_encode::set_explicit_source(uint8_t explicit_source)
{
    voice_params.explicit_source = explicit_source & 0x01;
}

void p25p1_voice_encode::set_tgid(uint16_t tgid)
{
    voice_params.tgid = tgid;
}

void p25p1_voice_encode::set_destination(uint32_t dst)
{
    if (dst > 0x00ffffff) {
        voice_params.dst = 0;
        return;
    }

    voice_params.dst = dst;
}

void p25p1_voice_encode::set_source(uint32_t src)
{
    if (src > 0x00ffffff) {
        voice_params.src = 0;
        return;
    }

    voice_params.src = src;
}

void p25p1_voice_encode::set_lsd(uint32_t lsd)
{
    voice_params.lsd = lsd;
}

void p25p1_voice_encode::set_verbosity(uint8_t verb)
{
    voice_params.verbosity = verb;
}

/*
 * Equivalent of p25craft.py's print_spec().
 *
 * frame_body holds individual bits; p25craft.py's "data" list holds
 * dibits (0-3), so each dibit here is reconstructed from a pair of bits.
 */
void p25p1_voice_encode::print_spec(const bit_vector& frame_body, uint16_t flip)
{
    std::vector<uint8_t> dibits;
    dibits.reserve(frame_body.size() / 2);

    for (size_t i = 0; i + 1 < frame_body.size(); i += 2) {
        dibits.push_back(static_cast<uint8_t>((frame_body[i] << 1) | frame_body[i + 1]));
    }

    // we only support full microslots
    if (dibits.size() % 36 != 0) {
        fprintf(stderr, "print_spec: dibit count %zu is not a multiple of 36\n", dibits.size());
        return;
    }

    int microslot = 0;

    fprintf(stderr, "Microslot:  ___________0___________  ___________1___________");

    for (size_t i = 0; i < dibits.size(); i += 36) {
        if ((microslot % 2) == 0) {
            fprintf(stderr, "\n");
            fprintf(stderr, "%9d: ", microslot);
        }

        fprintf(stderr, " ");

        for (int j = 0; j < 36; j += 6) {
            uint16_t dodectet = 0;

            for (int k = 0; k < 6; ++k) {
                dodectet |= static_cast<uint16_t>(dibits[i + j + k]) << (10 - k * 2);
            }

            fprintf(stderr, "%03x ", static_cast<unsigned>(dodectet ^ flip));
        }

        ++microslot;
    }

    fprintf(stderr, "\n\n");
}

/*
 * Translate p25craft.py's bch_64_16_23_encode().
 */
uint64_t p25p1_voice_encode::bch_64_16_23_encode(uint16_t data)
{
    static const uint64_t matrix[16] = {
        0x8000cd930bdd3b2aULL,
        0x4000ab5a8e33a6beULL,
        0x2000983e4cc4e874ULL,
        0x10004c1f2662743aULL,
        0x0800eb9c98ec0136ULL,
        0x0400b85d47ab3bb0ULL,
        0x02005c2ea3d59dd8ULL,
        0x01002e1751eaceecULL,
        0x0080170ba8f56776ULL,
        0x0040c616dfa78890ULL,
        0x0020630b6fd3c448ULL,
        0x00103185b7e9e224ULL,
        0x000818c2dbf4f112ULL,
        0x0004c1f2662743a2ULL,
        0x0002ad6a38ce9afbULL,
        0x00019b2617ba7657ULL
    };

    uint64_t codeword = 0;

    for (int i = 0; i < 16; ++i) {
        if (data & (0x8000 >> i))
            codeword ^= matrix[i];
    }

    return codeword;
}

/*
 * Equivalent of p25craft.py's start_packet():
 *
 *     nid = bch_64_16_23_encode((nac << 4) | duid)
 */
uint64_t p25p1_voice_encode::construct_nid(uint16_t nac, uint8_t duid)
{
    return bch_64_16_23_encode(
        static_cast<uint16_t>(((nac & 0x0fff) << 4) | (duid & 0x0f)));
}

/*
 * Equivalent of p25craft.py's construct_lcf().
 */
uint8_t p25p1_voice_encode::construct_lcf(
    uint8_t p,
    uint8_t sf,
    uint8_t lco)
{
    return static_cast<uint8_t>(
        ((p & 0x01) << 7) |
        ((sf & 0x01) << 6) |
        (lco & 0x3f));
}

void p25p1_voice_encode::insert_hdu_golay(
    bit_vector& frame_body,
    int logical_dibit_start,
    const std::vector<uint8_t>& rs_symbols)
{
    int logical_dibit = logical_dibit_start;

    /*
     * The HDU contains 36 six-bit RS symbols.
     *
     * Each symbol is encoded as an 18-bit shortened Golay codeword.
     * Each 18-bit codeword occupies nine dibits.
     *
     * 36 * 18 = 648 bits = 324 dibits.
     */
    for (size_t i = 0; i < rs_symbols.size(); ++i) {
        const uint32_t codeword = golay_24_encode(rs_symbols[i] & 0x3f) & 0x3ffff;

        for (int j = 0; j < 9; ++j) {
            const int shift = (8 - j) * 2;
            const uint8_t dibit = static_cast<uint8_t>((codeword >> shift) & 0x03);

            insert_dibit(frame_body, logical_dibit++, dibit);
        }
    }
}

void p25p1_voice_encode::emit_hdu()
{
    /*
     * p25craft.py's construct_hdu() creates:
     *
     *   24 dibits  frame sync
     *   32 dibits  NID
     *   324 dibits Golay-coded HDU payload
     *
     * Before status insertion:
     *
     *   24 + 32 + 324 = 380 data dibits
     *
     * With eleven status dibits and five padding dibits:
     *
     *   380 + 5 + 11 = 396 dibits
     *   396 * 2 = 792 bits
     */
    static const size_t HDU_BITS = 792;
    static const size_t HDU_STATUS_COUNT = 11;

    bit_vector hdu(HDU_BITS);
    clear_bits(hdu);

    /*
     * p25craft.py builds the 120-bit HDU payload:
     *
     *   MI     : 72 bits
     *   MFID    8 bits
     *   ALGID   8 bits
     *   KID    16 bits
     *   TGID   16 bits
     *
     * The current C++ interface stores MI as uint64_t, so the
     * low eight MI bits are zero and the high 64 bits are emitted.
     */
    uint8_t hdu_payload[15];
    memset(hdu_payload, 0, sizeof(hdu_payload));

    /*
     * Nine-byte MI field:
     *
     *   hdu_payload[0:8]  = uint64_t MI, big endian
     *   hdu_payload[9]    = low eight, 0
     */
    for (int i = 0; i < 8; ++i) {
        hdu_payload[i] = static_cast<uint8_t>((voice_params.mi >> ((7 - i) * 8)) & 0xff);
    }

    hdu_payload[9] = voice_params.mfid;
    hdu_payload[10] = voice_params.algid;
    hdu_payload[11] = static_cast<uint8_t>((voice_params.kid >> 8) & 0xff);
    hdu_payload[12] = static_cast<uint8_t>(voice_params.kid & 0xff);
    hdu_payload[13] = static_cast<uint8_t>((voice_params.tgid >> 8) & 0xff);
    hdu_payload[14] = static_cast<uint8_t>(voice_params.tgid & 0xff);

    if(voice_params.verbosity >= 1) {
		fprintf(stderr, "HDU: ");
		
		if(voice_params.verbosity >= 2) {
        fprintf(stderr, "%02x %02x %02x %02x %02x %02x %02x "
			"%02x %02x %02x %02x %02x %02x %02x %02x | ",
			hdu_payload[0], hdu_payload[1], hdu_payload[2],
			hdu_payload[3], hdu_payload[4], hdu_payload[5],
			hdu_payload[6], hdu_payload[7], hdu_payload[8],
			hdu_payload[9], hdu_payload[10],hdu_payload[11],
			hdu_payload[12], hdu_payload[13], hdu_payload[14]);
		}
		
		fprintf(stderr, "MI=%016llx MFID=%02x ALGID=%02X KID=%04x TGID=%u\n",
			static_cast<unsigned long long>(voice_params.mi),
			static_cast<unsigned int>(voice_params.mfid),
			static_cast<unsigned int>(voice_params.algid),
			static_cast<unsigned int>(voice_params.kid),
			static_cast<unsigned int>(voice_params.tgid));
    }

    /*
     * Convert 120 payload bits into twenty six-bit symbols.
     */
    std::vector<uint8_t> rs_symbols;

    bytes_to_6bit_symbols(hdu_payload, sizeof(hdu_payload), rs_symbols);

    if (rs_symbols.size() != 20) {
#ifdef DEBUG_TX
        fprintf(stderr, "HDU error: expected 20 payload symbols, got %zu\n", rs_symbols.size());
#endif
        return;
    }

    /*
     * RS(36,20,17) in p25craft.py corresponds to the repository's
     * shortened GF(64) codec:
     *
     *   ezpwd::RS<63,47>
     *
     * It appends sixteen parity symbols to the twenty payload symbols.
     */
    ezpwd::RS<63, 47> rs_hdu;
    rs_hdu.encode(rs_symbols);

    if (rs_symbols.size() != 36) {
#ifdef DEBUG_TX
        fprintf(stderr, "HDU error: expected 36 RS symbols, got %zu\n", rs_symbols.size());
#endif
        return;
    }

    /*
     * p25craft.py's start_packet() uses DUID 0x0 for HDU.
     */
    const uint64_t nid = construct_nid(voice_params.nac, 0x00);

    /*
     * Insert frame sync and NID into physical positions.
     */
    p25_setup_frame_header(hdu, nid);

    /*
     * The frame's first 56 logical data dibits are:
     *
     *   logical dibits 0..23 : frame sync
     *   logical dibits 24..55: NID
     *
     * Therefore the Golay-coded HDU payload starts at logical dibit 56.
     */
    insert_hdu_golay(hdu, 56, rs_symbols);

    /*
     * HDU has eleven status symbols.
     * The remaining unused data positions are already zero-filled,
     * matching p25craft.py's padding behavior.
     */
    insert_status_symbols(hdu, voice_params.status_symbol, HDU_STATUS_COUNT);

    output_frame(hdu, HDU_BITS);
    
    if (voice_params.verbosity >= 5) {
		print_spec(hdu);
	}
}

/*
 * Construct the 72-bit Link Control Word as nine bytes.
 *
 * This follows p25craft.py:
 *
 *     lcf   << 64
 *     mfid  << 56
 *     svcopt << 48
 *     s     << 32
 *     tgid  << 24
 *     src
 *
 * For individual calls, dst replaces the TGID field.
 */
void p25p1_voice_encode::construct_lc(
    uint8_t lco,
    uint8_t mfid,
    uint8_t svcopt,
    uint8_t s,
    uint16_t tgid,
    uint32_t dst,
    uint32_t src,
    uint8_t lc[9])
{
    /*
     * LCW layout from p25craft.py:
     *
     *     lc = lcf << 64
     *     lc |= mfid << 56
     *     lc |= svcopt << 48
     *     lc |= s << 32
     *     lc |= tgid << 24
     *     lc |= src
     *
     * Byte layout:
     *
     *     lc[0] : LCF
     *     lc[1] : MFID
     *     lc[2] : Service Options
     *     lc[3] : reserved / destination high byte for LCO 3
     *     lc[4] : TGID high byte, plus S in bit 0
     *     lc[5] : TGID low byte
     *     lc[6] : SRC high byte
     *     lc[7] : SRC middle byte
     *     lc[8] : SRC low byte
     */

    memset(lc, 0, 9);

    lc[0] = construct_lcf(0, 0, lco);
    lc[1] = mfid;
    lc[2] = svcopt;

    if (lco == 0) {
        /*
         * Group Voice Channel User:
         *
         *     s    << 32
         *     tgid << 24
         *
         * TGID occupies exactly lc[4] and lc[5].
         */
        lc[4] = static_cast<uint8_t>(((tgid >> 8) & 0xff) | ((s & 0x01) << 0));
        lc[5] = static_cast<uint8_t>(tgid & 0xff);
    } else if (lco == 3) {
        /*
         * Individual Voice Channel User:
         *
         *     dst << 24
         *
         * Destination occupies lc[3], lc[4], and lc[5].
         */
        lc[3] = static_cast<uint8_t>((dst >> 16) & 0xff);
        lc[4] = static_cast<uint8_t>((dst >> 8) & 0xff);
        lc[5] = static_cast<uint8_t>(dst & 0xff);
    } else {
        /*
         * p25craft.py only defines the group-call and individual-call
         * layouts in construct_lc(). Do not allow unsupported layouts
         * to overlap the source ID.
         */
        lc[3] = static_cast<uint8_t>((dst >> 16) & 0xff);
        lc[4] = static_cast<uint8_t>((dst >> 8) & 0xff);
        lc[5] = static_cast<uint8_t>(dst & 0xff);
    }

    /*
     * Source ID is always the final 24 bits.
     *
     * Use assignment, not |=, so no previous field can contaminate
     * the source bytes.
     */
    lc[6] = static_cast<uint8_t>((src >> 16) & 0xff);
    lc[7] = static_cast<uint8_t>((src >> 8) & 0xff);
    lc[8] = static_cast<uint8_t>(src & 0xff);
}

/*
 * Equivalent of p25craft.py's construct_es().
 *
 * ES is:
 *
 *     mi << 24
 *     algid << 16
 *     kid
 *
 * The resulting value is 12 bytes / 96 bits.
 */
void p25p1_voice_encode::construct_es(
    uint64_t mi,
    uint8_t algid,
    uint16_t kid,
    uint8_t es[12])
{
    memset(es, 0, 12);

    /*
     * Message Indicator is 72 bits in the P25 format. The current
     * interface stores the low 64 bits, which are placed in the low
     * eight bytes of the MI field.
     */
    for (int i = 0; i < 8; ++i) {
        es[i] = static_cast<uint8_t>((mi >> ((7 - i) * 8)) & 0xff);
    }

    es[8]  = 0;
    es[9]  = algid;
    es[10] = static_cast<uint8_t>((kid >> 8) & 0xff);
    es[11] = static_cast<uint8_t>(kid & 0xff);
}

/*
 * Equivalent of p25craft.py's cyclic_16_8_5_encode().
 */
uint16_t p25p1_voice_encode::cyclic_16_8_5_encode(uint8_t data)
{
    static const uint16_t matrix[8] = {
        0x804e,
        0x4027,
        0x208f,
        0x10db,
        0x08f1,
        0x04e4,
        0x0272,
        0x0139
    };

    uint16_t codeword = 0;

    for (int i = 0; i < 8; ++i) {
        if (data & (0x80 >> i))
            codeword ^= matrix[i];
    }

    return codeword;
}

/*
 * Equivalent of p25craft.py's ldu1_cyclic().
 */
uint32_t p25p1_voice_encode::ldu1_cyclic(uint32_t lsd)
{
    uint32_t word = 0;

    word |= static_cast<uint32_t>(cyclic_16_8_5_encode(static_cast<uint8_t>((lsd >> 24) & 0xff))) << 16;
    word |= static_cast<uint32_t>(cyclic_16_8_5_encode(static_cast<uint8_t>((lsd >> 16) & 0xff)));

    return word;
}

/*
 * Equivalent of p25craft.py's ldu2_cyclic().
 */
uint32_t p25p1_voice_encode::ldu2_cyclic(uint32_t lsd)
{
    uint32_t word = 0;

    word |= static_cast<uint32_t>(cyclic_16_8_5_encode(static_cast<uint8_t>((lsd >> 8) & 0xff))) << 16;
    word |= static_cast<uint32_t>(cyclic_16_8_5_encode(static_cast<uint8_t>(lsd & 0xff)));

    return word;
}

/*
 * Equivalent of p25craft.py's hamming_10_6_3_encode().
 */
uint16_t p25p1_voice_encode::hamming_10_6_3_encode(uint8_t data)
{
    static const uint16_t matrix[6] = {
        0x20e,
        0x10d,
        0x08b,
        0x047,
        0x023,
        0x01c
    };

    uint16_t codeword = 0;

    for (int i = 0; i < 6; ++i) {
        if (data & (0x20 >> i))
            codeword ^= matrix[i];
    }

    return codeword;
}

/*
 * Convert a big-endian byte sequence into six-bit symbols.
 *
 * p25craft.py's Reed-Solomon routines operate on six-bit symbols.
 */
void p25p1_voice_encode::bytes_to_6bit_symbols(
    const uint8_t* bytes,
    size_t byte_count,
    std::vector<uint8_t>& symbols)
{
    symbols.clear();
    symbols.reserve((byte_count * 8) / 6);

    uint32_t accumulator = 0;
    int bits = 0;

    for (size_t i = 0; i < byte_count; ++i) {
        accumulator = (accumulator << 8) | bytes[i];
        bits += 8;

        while (bits >= 6) {
            bits -= 6;
            symbols.push_back(static_cast<uint8_t>((accumulator >> bits) & 0x3f));
        }
    }

    if (bits > 0) {
        symbols.push_back(static_cast<uint8_t>((accumulator << (6 - bits)) & 0x3f));
    }
}

/*
 * Hamming encode every six-bit Reed-Solomon symbol.
 */
void p25p1_voice_encode::hamming_encode_rs_symbols(
    const std::vector<uint8_t>& rs_symbols,
    std::vector<uint16_t>& codewords)
{
    codewords.clear();
    codewords.reserve(rs_symbols.size());

    for (size_t i = 0; i < rs_symbols.size(); ++i) {
        codewords.push_back(hamming_10_6_3_encode(rs_symbols[i] & 0x3f));
    }
}

/*
 * Convert a logical dibit position used by p25craft.py into a physical
 * bit position in a 1728-bit P25 frame.
 *
 * p25craft.py inserts one status dibit after every 35 data dibits.
 */
int p25p1_voice_encode::frame_bit_index(int logical_dibit)
{
    return (logical_dibit * 2) + ((logical_dibit / 35) * 2);
}

/*
 * Insert one logical dibit into the physical frame.
 */
void p25p1_voice_encode::insert_dibit(
    bit_vector& frame_body,
    int logical_dibit,
    uint8_t dibit)
{
    const int bit = frame_bit_index(logical_dibit);

    if (bit < 0 || bit + 1 >= static_cast<int>(frame_body.size()))
        return;

    frame_body[bit + 0] = (dibit >> 1) & 0x01;
    frame_body[bit + 1] = dibit & 0x01;
}

/*
 * Insert 24 ten-bit Hamming codewords as 120 dibits.
 */
void p25p1_voice_encode::insert_codeword_bits(
    bit_vector& frame_body,
    int logical_dibit_start,
    const std::vector<uint16_t>& codewords)
{
    int logical_dibit = logical_dibit_start;

    for (size_t i = 0; i < codewords.size(); ++i) {
        const uint16_t codeword = codewords[i] & 0x03ff;

        /*
         * Each ten-bit Hamming word occupies five dibits,
         * transmitted most-significant dibit first.
         */
        for (int j = 0; j < 5; ++j) {
            const int shift = (4 - j) * 2;
            const uint8_t dibit = static_cast<uint8_t>((codeword >> shift) & 0x03);

            insert_dibit(frame_body, logical_dibit++, dibit);
        }
    }
}

/*
 * Insert status dibits at all P25 status-symbol positions.
 */
void p25p1_voice_encode::insert_status_symbols(
    bit_vector& frame_body,
    uint8_t status_symbol,
    size_t status_count)
{
    const uint8_t dibit = status_symbol & 0x03;

    /*
     * Status positions are defined in op25_imbe_frame.h.
     *
     * The HDU uses 11 status symbols.
     * An LDU uses 24 status symbols.
     */
    const size_t available =
        sizeof(imbe_ldu_status_bits) /
        sizeof(imbe_ldu_status_bits[0]);

    const size_t count =
        std::min(status_count, available);

    for (size_t i = 0; i < count; ++i) {
        const int bit =
            static_cast<int>(imbe_ldu_status_bits[i]);

        if (bit < 0 ||
            bit + 1 >= static_cast<int>(frame_body.size())) {
            continue;
        }

        frame_body[bit + 0] = (dibit >> 1) & 0x01;
        frame_body[bit + 1] = dibit & 0x01;
    }
}

/*
 * Build LDU1 metadata.
 *
 * p25craft.py layout:
 *
 *   frame sync/NID
 *   IMBE
 *   IMBE
 *   LCW[0:20]
 *   IMBE
 *   LCW[20:40]
 *   IMBE
 *   LCW[40:60]
 *   IMBE
 *   LCW[60:80]
 *   IMBE
 *   LCW[80:100]
 *   IMBE
 *   LCW[100:120]
 *   IMBE
 *   LSD
 *   IMBE
 */
void p25p1_voice_encode::build_ldu1_metadata(
    bit_vector& frame_body)
{
    uint8_t lc[9];

    construct_lc(
        voice_params.lco,
        voice_params.mfid,
        voice_params.svcopt,
        voice_params.explicit_source,
        voice_params.tgid,
        voice_params.dst,
        voice_params.src,
        lc);

    if(voice_params.verbosity >= 1) {
		fprintf(stderr, "LDU 1: ");
		
		if(voice_params.verbosity >= 2){
			fprintf(stderr,"%02x %02x %02x %02x %02x %02x %02x %02x %02x | ",
			lc[0], lc[1], lc[2], lc[3], lc[4], lc[5], lc[6], lc[7], lc[8]);
		}
		
		fprintf(stderr, "LCO=%u MFID=%u SVCOPT=%u TGID=%u DST=%u SRC=%u\n",
		voice_params.lco, voice_params.mfid, voice_params.svcopt,
		voice_params.tgid, voice_params.dst, voice_params.src);
    }

    /*
     * LCW is 9 bytes = 12 six-bit symbols.
     * RS<63,51> adds 12 parity symbols, resulting in 24 symbols.
     */
    std::vector<uint8_t> lc_symbols;
    bytes_to_6bit_symbols(lc, 9, lc_symbols);

    if (lc_symbols.size() != 12)
        return;

    ezpwd::RS<63, 51> rs_lcw;
    rs_lcw.encode(lc_symbols);

    std::vector<uint16_t> hamming_words;
    hamming_encode_rs_symbols(lc_symbols, hamming_words);

    if (hamming_words.size() != 24)
        return;

    /*
     * The LCW occupies six 20-dibit sections.
     */
    static const int lc_starts[6] = {
        200, 292, 384, 476, 568, 660
    };

    for (int section = 0; section < 6; ++section) {
        std::vector<uint16_t> section_words;

        const int first_word = section * 4;

        for (int i = 0; i < 4; ++i)
            section_words.push_back(hamming_words[first_word + i]);

        insert_codeword_bits(frame_body, lc_starts[section], section_words);
    }

    /*
     * LDU1 LSD occupies 16 dibits beginning at logical dibit 752.
     */
    const uint32_t lsd = ldu1_cyclic(voice_params.lsd);

    for (int i = 0; i < 16; ++i) {
        const int shift = (15 - i) * 2;
        const uint8_t dibit =
            static_cast<uint8_t>((lsd >> shift) & 0x03);

        insert_dibit(frame_body, 752 + i, dibit);
    }
}

/*
 * Build LDU2 metadata.
 *
 * The LDU2 encrypted synchronization field uses:
 *
 *   MI << 24
 *   ALGID << 16
 *   KID
 */
void p25p1_voice_encode::build_ldu2_metadata(
    bit_vector& frame_body)
{
    uint8_t es[12];

    construct_es(voice_params.mi, voice_params.algid, voice_params.kid, es);
        
    if(voice_params.verbosity >= 1) {
		fprintf(stderr, "LDU 2: ");
		if(voice_params.verbosity >= 2) {
			fprintf(stderr, "%02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x | ",
					es[0], es[1], es[2], es[3], es[4], es[5], es[6], es[7], es[8], es[9], es[10], es[11]);
		}
		
		fprintf(stderr, "MI=%016llx ALGID=%02X KID=%04x\n",
		static_cast<unsigned long long>(voice_params.mi),
		static_cast<unsigned int>(voice_params.algid),
		static_cast<unsigned int>(voice_params.kid));	
    }
	
    std::vector<uint8_t> es_symbols;
    bytes_to_6bit_symbols(es, 12, es_symbols);

    if (es_symbols.size() != 16)
        return;

    /*
     * ES is 16 payload symbols with eight parity symbols,
     * producing 24 six-bit symbols.
     */
    ezpwd::RS<63, 55> rs_es;
    rs_es.encode(es_symbols);

    std::vector<uint16_t> hamming_words;
    hamming_encode_rs_symbols(es_symbols, hamming_words);

    if (hamming_words.size() != 24)
        return;

    static const int es_starts[6] = {
        200, 292, 384, 476, 568, 660
    };

    for (int section = 0; section < 6; ++section) {
        std::vector<uint16_t> section_words;

        const int first_word = section * 4;

        for (int i = 0; i < 4; ++i)
            section_words.push_back(hamming_words[first_word + i]);

        insert_codeword_bits(frame_body, es_starts[section], section_words);
    }

    /*
     * LDU2 LSD occupies 16 dibits beginning at logical dibit 752.
     */
    const uint32_t lsd = ldu2_cyclic(voice_params.lsd);

    for (int i = 0; i < 16; ++i) {
        const int shift = (15 - i) * 2;
        const uint8_t dibit = static_cast<uint8_t>((lsd >> shift) & 0x03);

        insert_dibit(frame_body, 752 + i, dibit);
    }
}

/*
 * Output one complete 1728-bit frame.
 */
void p25p1_voice_encode::output_frame(
    const bit_vector& frame_body,
    size_t frame_bits)
{
    if (frame_bits == 0 ||
        frame_bits > frame_body.size() || (frame_bits % 2) != 0) {
        return;
    }

    if (op25audio.enabled()) {
        /*
         * Maximum frame size is the normal 1728-bit LDU.
         */
        uint8_t obuf[P25_VOICE_FRAME_SIZE / 8];
        size_t obuf_ct = 0;

        for (size_t i = 0; i < frame_bits; i += 8) {
            uint8_t b = 0;

            const size_t remaining = frame_bits - i;

            if (remaining >= 8) {
                b =
                    static_cast<uint8_t>(
                        (frame_body[i + 0] << 7) |
                        (frame_body[i + 1] << 6) |
                        (frame_body[i + 2] << 5) |
                        (frame_body[i + 3] << 4) |
                        (frame_body[i + 4] << 3) |
                        (frame_body[i + 5] << 2) |
                        (frame_body[i + 6] << 1) |
                        (frame_body[i + 7]));
            }

            obuf[obuf_ct++] = b;
        }

        op25audio.send_to(obuf, obuf_ct);
    } else {
        for (size_t i = 0; i < frame_bits; i += 2) {
            const uint8_t dibit = static_cast<uint8_t>(
                    (frame_body[i + 0] << 1) |
                    frame_body[i + 1]);

            output_queue.push_back(dibit);
        }
    }
}

/*
 * Add one IMBE voice codeword to the LDU.
 */
void p25p1_voice_encode::append_imbe_codeword(
    bit_vector& frame_body,
    int16_t frame_vector[],
    unsigned int& codeword_ct)
{
    voice_codeword cw(voice_codeword_sz);
    
    packed_codeword pcw;
    imbe_pack(pcw, frame_vector[0], frame_vector[1], frame_vector[2], frame_vector[3],
              frame_vector[4], frame_vector[5], frame_vector[6], frame_vector[7]);
     
     if((voice_params.verbosity >= 3) || ((voice_params.algid == 0x80) && (voice_params.verbosity >= 2))) {
		fprintf(stderr,"(PT) IMBE: %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x\n",
				pcw[0], pcw[1], pcw[2], pcw[3], pcw[4], pcw[5],
				pcw[6], pcw[7], pcw[8], pcw[9], pcw[10]);
     }
    
/* CRYPTO START */
    if (voice_params.algid != ALG_UNENCRYPTED) {
        uint32_t u[8];
        const bool ldu2_now = ((frame_cnt & 1) != 0);

        if (!ldu2_now && codeword_ct == 0) {
            uint8_t mi[9] = {0};
            for (int i = 0; i < 8; ++i)
                mi[i] = (voice_params.mi >> (56 - 8 * i)) & 0xFF;

            d_crypt_algs.prepare(voice_params.algid, voice_params.kid, PT_P25_PHASE1, mi);

            op25_crypt_algs::cycle_p25_mi(mi);     // advance MI for next pair

            voice_params.mi = 0;
            for (int i = 0; i < 8; ++i)
                voice_params.mi |= static_cast<uint64_t>(mi[i]) << (56 - 8 * i);
        }
		
		d_crypt_algs.process(pcw, ldu2_now ? FT_LDU2 : FT_LDU1, 0);

        
        if(voice_params.verbosity >= 2) {
		    fprintf(stderr,"(CT) IMBE: %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x\n",
				pcw[0], pcw[1], pcw[2], pcw[3], pcw[4], pcw[5],
				pcw[6], pcw[7], pcw[8], pcw[9], pcw[10]);
        }

        imbe_unpack(pcw, u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7]);
        for (int i = 0; i < 8; i++)
            frame_vector[i] = static_cast<int16_t>(u[i]);
    }

    /*
     * Construct the 144-bit IMBE codeword from the eight
     * 16-bit/11-bit IMBE parameter values.
     */
    imbe_header_encode(
        cw,
        frame_vector[0],
        frame_vector[1],
        frame_vector[2],
        frame_vector[3],
        frame_vector[4],
        frame_vector[5],
        frame_vector[6],
        frame_vector[7]);

    /*
     * Place the codeword in the P25 LDU interleave.
     */
    imbe_interleave(frame_body, cw, codeword_ct);

    ++codeword_ct;

    if (codeword_ct < nof_voice_codewords)
        return;

    /*
     * The original encoder alternates LDU1 and LDU2.
     */
    const bool ldu2 = ((frame_cnt & 1) != 0);
    const uint8_t duid = ldu2 ? 0x0a : 0x05;

    /*
     * Dynamically generate LDU metadata.
     */
    if (ldu2)
        build_ldu2_metadata(frame_body);
    else
        build_ldu1_metadata(frame_body);

    /*
     * Generate the runtime NID from NAC and DUID.
     */
    const uint64_t nid =
        construct_nid(voice_params.nac, duid);

    /*
     * Insert sync and NID.
     */
    p25_setup_frame_header(frame_body, nid);
    
    if (voice_params.verbosity >= 5)
		print_spec(frame_body);

    /*
     * Override all status symbols with the configured value.
     */
    insert_status_symbols(frame_body, voice_params.status_symbol, 24);

    output_frame(frame_body, P25_VOICE_FRAME_SIZE);
    
    codeword_ct = 0;
    ++frame_cnt;

    if (opt_verbose && ((frame_cnt % STATS_INTERVAL) == 0)) {
        gettimeofday(&tv, &tz);

        int seconds = tv.tv_sec - oldtv.tv_sec;
        int useconds = tv.tv_usec - oldtv.tv_usec;

        if (useconds < 0) {
            useconds += 1000000;
            --seconds;
        }

        float elapsed = static_cast<float>(useconds) / 1000000.0f;
        elapsed += static_cast<float>(seconds);

        fprintf(stderr,"time %f peak %5d\n",
        elapsed / STATS_INTERVAL, peak_amplitude);

        oldtv = tv;
    }

    clear_bits(frame_body);
}

/*
 * Encode one 160-sample audio frame.
 */
void p25p1_voice_encode::compress_frame(int16_t snd[])
{
    if (!hdu_sent) {
		emit_hdu();
		hdu_sent = true;
	}
    
    int16_t frame_vector[8];

    vocoder.imbe_encode(frame_vector, snd);
    
    if (opt_dump_raw_vectors) {
        char s[128];

        snprintf(s, sizeof(s), "%03x %03x %03x %03x %03x %03x %03x %03x\n",
            frame_vector[0],
            frame_vector[1],
            frame_vector[2],
            frame_vector[3],
            frame_vector[4],
            frame_vector[5],
            frame_vector[6],
            frame_vector[7]);

        const size_t len = strlen(s);

        if (write_bufp + static_cast<int>(len) < static_cast<int>(sizeof(write_buf))) {
            memcpy(&write_buf[write_bufp], s, len);
            write_bufp += static_cast<int>(len);
        }

        if (write_bufp >= 288) {
            op25audio.send_to(write_buf, 288);
            write_bufp = 0;
        }

        return;
    }

    append_imbe_codeword(f_body, frame_vector, codeword_ct);
}

/*
 * Add one audio sample.
 */
void p25p1_voice_encode::add_sample(int16_t samp)
{
    sampbuf[sampbuf_ct++] = samp;

    if (sampbuf_ct >= FRAME) {
        compress_frame(sampbuf);
        sampbuf_ct = 0;
    }

    const int16_t asamp =
        (samp < 0) ? static_cast<int16_t>(-samp) : samp;

    if (asamp > peak)
        peak = asamp;

    ++samp_ct;

    if (samp_ct >= SAMP_INTERVAL) {
        peak_amplitude = peak;
        peak = 0;
        samp_ct = 0;
    }
}

/*
 * Apply sample-rate stretch or compression.
 */
void p25p1_voice_encode::compress_samp(
    const int16_t* samp,
    int len)
{
    for (int i = 0; i < len; ++i) {
        ++stretch_count;

        if (opt_stretch_amt != 0 &&
            stretch_count >= opt_stretch_amt) {

            stretch_count = 0;

            if (opt_stretch_sign < 0) {
                /*
                 * Drop one sample.
                 */
                continue;
            }

            /*
             * Repeat one sample.
             */
            add_sample(samp[i]);
        }

        add_sample(samp[i]);
    }
}

/*
 * Set vocoder gain adjustment.
 */
void p25p1_voice_encode::set_gain_adjust(float gain_adjust)
{
    vocoder.set_gain_adjust(gain_adjust);
}

} // namespace op25_repeater
} // namespace gr
