/* -*- c++ -*- */
/* 
 * Copyright 2022 Graham J. Norbury
 * 
 * This is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * This software is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this software; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include "p25_crypt_algs.h"

p25_crypt_algs::p25_crypt_algs(int debug, int msgq_id) :
    d_debug(debug),
    d_msgq_id(msgq_id),
    d_fr_type(FT_UNK),
    d_algid(0x80),
    d_keyid(0),
    d_adp_position(0) {
}

p25_crypt_algs::~p25_crypt_algs() {
}

void p25_crypt_algs::prepare(uint8_t algid, uint16_t keyid, frame_type fr_type, uint8_t *MI) {
    d_algid = algid;
    switch (algid) {
        case 0xaa: // ADP RC4
            d_adp_position = 0;
            d_fr_type = fr_type;
            if (fr_type == FT_LDU1)
                adp_keystream_gen(keyid, MI);
            break;
    
        default:
            break;
    }
}

bool p25_crypt_algs::process(packed_codeword& PCW) {
    bool rc = false;

    switch (d_algid) {
        case 0xaa: // ADP RC4
            rc = adp_process(PCW);
            break;
    
        default:
            break;
    }

    return rc;
}

bool p25_crypt_algs::adp_process(packed_codeword& PCW) {
    bool rc = true;
    size_t offset = 0;

    switch (d_fr_type) {
        case FT_LDU1:
            offset = 0;
            break;
        case FT_LDU2:
            offset = 101;
            break;
        //TODO: TDMA 2V 4V bursts
        default:
            rc = false;
            break;
    }
    offset += (d_adp_position * 11) + 267 + ((d_adp_position < 8) ? 0 : 2);
    d_adp_position = (d_adp_position + 1) % 9;
    for (int j = 0; j < 11; ++j) {
        PCW[j] = adp_keystream[j + offset] ^ PCW[j];
    }

    return rc;
}

void p25_crypt_algs::adp_swap(uint8_t *S, uint32_t i, uint32_t j) {
    uint8_t temp = S[i];
    S[i] = S[j];
    S[j] = temp;
}

void p25_crypt_algs::adp_keystream_gen(uint8_t keyid, uint8_t *MI) {
    //TODO: multi-key support and loadable configuration
    uint8_t adp_key[13] = {0x70, 0x70, 0x70, 0x70, 0x70},
                          S[256], K[256];
    uint32_t i, j, k;
    j = 0;

    for (i = 5; i < 13; ++i) {
        adp_key[i] = MI[i - 5];
    }

    for (i = 0; i < 256; ++i) {
        K[i] = adp_key[i % 13];
    }

    for (i = 0; i < 256; ++i) {
        S[i] = i;
    }

    for (i = 0; i < 256; ++i) {
        j = (j + S[i] + K[i]) & 0xFF;
        adp_swap(S, i, j);
    }

    i = j = 0;

    for (k = 0; k < 469; ++k) {
        i = (i + 1) & 0xFF;
        j = (j + S[i]) & 0xFF;
        adp_swap(S, i, j);
        adp_keystream[k] = S[(S[i] + S[j]) & 0xFF];
    }
}

