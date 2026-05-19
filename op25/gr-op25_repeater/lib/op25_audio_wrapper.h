/* -*- c++ -*- */
/* 
 * Copyright 2026 Graham J Norbury, gnorbury@bondcar.com
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

#ifndef INCLUDED_OP25_AUDIO_WRAPPER_H
#define INCLUDED_OP25_AUDIO_WRAPPER_H

#include <mutex>
#include <thread>
#include <vector>

/*
 * Wrappers the op25_audio class into a singleton and provides access
 * to shared op25_audio instances.
 */

#include "log_ts.h"
#include "op25_audio.h"

#include <map>
#include <memory>
#include <mutex>

// Singleton class
class op25_audio_wrapper {
public:
    // Deleted copy/move constructors and assignment operators
    op25_audio_wrapper(const op25_audio_wrapper&) = delete;
    op25_audio_wrapper& operator=(const op25_audio_wrapper&) = delete;
    op25_audio_wrapper(op25_audio_wrapper&&) = delete;
    op25_audio_wrapper& operator=(const op25_audio_wrapper&&) = delete;

    op25_audio_wrapper() { }
    ~op25_audio_wrapper() { }

    static op25_audio_wrapper& instance() {
        static op25_audio_wrapper instance;     // Meyers’ Singleton, std c++11 and later
        return instance;
    }

    op25_audio& get_audio(const char* options, log_ts& logger, int debug, int msgq_id) {
        // threadsafety guard
        std::lock_guard<std::mutex> lock(mutex_);

        // map.emplace() will either return iterator to an existing object, or create a new object
        auto const [it, created] = audioMap.try_emplace(msgq_id, options, logger, debug, msgq_id);
        if (debug >= 10) {
            if (created) {
                fprintf(stderr, "%s op25_audio_wrapper::get_op25_audio: created new op25_audio object\n", logger.get(msgq_id));
            } else {
                fprintf(stderr, "%s op25_audio_wrapper::get_op25_audio: using existing op25_audio object\n", logger.get(msgq_id));
            }
        }

        return it->second;
    }

private:
    std::map<int, op25_audio> audioMap;
    std::mutex mutex_;

}; // class op25_audio_wrapper

#endif /* INCLUDED_OP25_AUDIO_WRAPPER_H */
