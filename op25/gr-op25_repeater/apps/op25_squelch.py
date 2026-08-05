# -*- coding: utf-8 -*-
#
# OP25 Noise Squelch Block (NBFM)
# Copyright 2026 W1JPI
#
# GNU Radio wrapper around squelch_core.NoiseSquelch, a noise-based
# squelch after PA3FWM (https://www.pa3fwm.nl/technotes/tn16e.html).
# Sits between the FM discriminator and the deemphasis/audio filters in
# op25_nbfm; passes discriminator samples through gated by a click-free
# envelope.  All DSP and the state machine live in squelch_core.py so
# they can be tested without GNU Radio.
#
# This file is part of OP25
#
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# It is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#

import sys
import numpy as np
from gnuradio import gr

import squelch_core
from log_ts import log_ts


class noise_squelch_ff(gr.sync_block):
    """float in (discriminator), float out (gated discriminator)"""

    def __init__(self, input_rate, deviation,
                 open_db=8.0, hyst_db=3.0, hang_ms=250.0,
                 voice_detect=False, voice_ratio_db=-3.0, reference=0.0,
                 debug=0, msgq_id=0):
        gr.sync_block.__init__(self,
                               name="noise_squelch_ff",
                               in_sig=[np.float32],
                               out_sig=[np.float32])
        self.debug = debug
        self.msgq_id = msgq_id
        self.core = squelch_core.NoiseSquelch(
            input_rate=input_rate,
            deviation=deviation,
            open_db=open_db,
            hyst_db=hyst_db,
            hang_ms=hang_ms,
            voice_detect=voice_detect,
            voice_ratio_db=voice_ratio_db,
            reference=reference,
            debug=debug,
            log_cb=self._log)

    def _log(self, msg):
        sys.stderr.write("%s [%d] %s\n" % (log_ts.get(), self.msgq_id, msg))

    def work(self, input_items, output_items):
        in0 = input_items[0]
        output_items[0][:len(in0)] = self.core.process(in0)
        return len(in0)

    def set_debug(self, dbglvl):
        self.debug = dbglvl
        self.core.debug = dbglvl

    def reset(self):
        # called when trunking re-enables the channel so stale gate
        # state from the previous voice call does not leak through
        self.core.reset()

    def is_open(self):
        return self.core.is_open()

    def quieting_db(self):
        return self.core.quieting_db()
