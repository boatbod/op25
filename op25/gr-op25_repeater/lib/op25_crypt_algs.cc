/* -*- c++ -*- */
/* 
 * Copyright 2025 Graham J. Norbury
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

#include <vector>
#include <string>

#include "op25_crypt.h"
#include "op25_crypt_algs.h"
#include "op25_crypt_adp.h"
#include "op25_crypt_des.h"

#include "op25_msg_types.h"

// constructor
op25_crypt_algs::op25_crypt_algs(log_ts& logger, int debug, int msgq_id) :
    logts(logger),
    d_debug(debug),
    d_msgq_id(msgq_id),
    d_key_iter(d_keys.end()),
    d_alg_iter(d_algs.end()) {
}

// destructor
op25_crypt_algs::~op25_crypt_algs() {
    // clean up dynamically allocated decryption algorithm objects
    d_alg_iter = d_algs.begin();
    while (d_alg_iter != d_algs.end()) {
        delete d_alg_iter->second;
        d_algs.erase(d_alg_iter);
    }
}

// remove all stored keys
void op25_crypt_algs::reset(void) {
    d_keys.clear();
}

// add or update a key
void op25_crypt_algs::key(uint16_t keyid, uint8_t algid, const std::vector<uint8_t> &key) {
    if ((keyid == 0) || (algid == 0x80))
        return;

    d_key_iter = d_keys.find(keyid);
    if (d_key_iter != d_keys.end())
        return; // key has been previously loaded

    d_alg_iter = d_algs.find(algid);
    if (d_alg_iter == d_algs.end()) {
        switch (algid) {
            case ALG_DES_OFB:
                d_alg_iter = d_algs.insert({algid, new op25_crypt_des(logts, d_debug, d_msgq_id)}).first;
                break;
            case ALG_ADP_RC4:
                d_alg_iter = d_algs.insert({algid, new op25_crypt_adp(logts, d_debug, d_msgq_id)}).first;
                break;
        }
        if (d_alg_iter == d_algs.end()) {
            return; // d_algs insert failed
        }
    }
    if (d_alg_iter->second->key(keyid, algid, key) == algid) {
        d_keys[keyid] = key_info(algid, key);
        if (d_debug >= 10) {
            fprintf(stderr, "%s op25_crypt_algs::key: loaded key keyId:%04x, algId:%02x\n", logts.get(d_msgq_id), keyid, algid);
        }
    }
}

// generic entry point to prepare for decryption
bool op25_crypt_algs::prepare(uint8_t algid, uint16_t keyid, protocol_type pr_type, uint8_t *MI) {
    d_key_iter = d_keys.find(keyid);
    if (d_key_iter == d_keys.end()) {
        if (d_debug >= 10) {
            fprintf(stderr, "%s p25_crypt_algs::prepare: keyid[0x%x] not found\n", logts.get(d_msgq_id), keyid);
        }
        return false;
    }
    if (d_debug >= 10) {
        fprintf(stderr, "%s p25_crypt_algs::prepare: keyid[0x%x] found\n", logts.get(d_msgq_id), keyid);
    }

    d_alg_iter = d_algs.find(algid);
    if (d_alg_iter == d_algs.end()) {
        if (d_debug >= 10) {
            fprintf(stderr, "%s p25_crypt_algs::prepare: algid[0x%x] algorithm module not found\n", logts.get(d_msgq_id), keyid);
        }
        return false;
    }

    return d_alg_iter->second->prepare(keyid, pr_type, MI);
}

// generic entry point to perform decryption
bool op25_crypt_algs::process(packed_codeword& PCW, frame_type fr_type, int voice_subframe) {
    if ((d_key_iter == d_keys.end()) || (d_alg_iter == d_algs.end())) {
        if (d_debug >= 10) {
            fprintf(stderr, "%s p25_crypt_algs::process: internal error\n", logts.get(d_msgq_id));
        }
        return false;
    }

    return d_alg_iter->second->process(PCW, fr_type, voice_subframe);
}

