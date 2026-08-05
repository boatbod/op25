#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# GNU Radio integration test for the NBFM noise squelch.  Requires
# gnuradio 3.10 and a built/installed gr-op25_repeater; run from the
# apps directory:
#     python3 squelch_gr_test.py
#
# Complements squelch_core_test.py (which tests the DSP with no GNU
# Radio dependency) by verifying the pieces only a real flowgraph can:
#   1. noise_squelch_ff produces output identical to squelch_core when
#      driven by the GR scheduler's arbitrary buffer chunking
#   2. op25_nbfm_c constructs and runs in all three squelch modes
#   3. end-to-end through op25_nbfm_c: channel noise keeps the gate
#      closed, a carrier opens it
#
# This file is part of OP25
#

import sys
import numpy as np

from gnuradio import gr, blocks
import op25_squelch
import squelch_core

FS = 24000
DEVIATION = 4000
DISC_GAIN = FS / (4 * np.pi * DEVIATION)

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print("%-58s %s %s" % (name, "PASS" if cond else "FAIL", detail))


def synth_disc(n, carrier, rng):
    """Synthesize a discriminator stream: quieted voice or raw noise."""
    if carrier:
        h = squelch_core.design_bandpass(401, 300.0, 3000.0, FS)
        v = np.convolve(rng.standard_normal(n), h, mode='same')
        v /= 3.0 * np.std(v)
        return (np.clip(v, -1, 1) * 0.8 + 0.02 * rng.standard_normal(n)).astype(np.float32)
    # no-carrier noise: uniform random phase steps through the discriminator
    dphi = rng.uniform(-np.pi, np.pi, n)
    return (dphi * DISC_GAIN).astype(np.float32)


def run_block_ff(samples, **kw):
    """Push float samples through noise_squelch_ff in a flowgraph."""
    tb = gr.top_block()
    src = blocks.vector_source_f(samples.tolist(), False)
    sq = op25_squelch.noise_squelch_ff(input_rate=FS, deviation=DEVIATION, **kw)
    snk = blocks.vector_sink_f()
    tb.connect(src, sq, snk)
    tb.run()
    return np.array(snk.data(), dtype=np.float32), sq


def fm_mod(audio, fdev=3000.0):
    phase = 2.0 * np.pi * np.cumsum(audio * fdev) / FS
    return np.exp(1j * phase).astype(np.complex64)


def run_nbfm(mode, iq, rng):
    """Instantiate the full op25_nbfm_c hier block and stream iq through."""
    import op25_nbfm
    config = {
        'if_rate': FS,
        'nbfm_deviation': DEVIATION,
        'nbfm_squelch_mode': mode,
    }
    msg_q = gr.msg_queue(20)
    tb = gr.top_block()
    nbfm = op25_nbfm.op25_nbfm_c("udp://127.0.0.1:23450", 0, config, 0, msg_q)
    nbfm.control(True)      # what trunking does when a voice call starts
    src = blocks.vector_source_c(iq.tolist(), False)
    tb.connect(src, nbfm)
    tb.run()
    return nbfm


def main():
    rng = np.random.default_rng(7)

    # ------------------------------------------------------------------
    # 1. wrapper parity: GR-scheduled output == direct core output
    n = 4 * FS
    stream = np.concatenate([
        synth_disc(FS, False, rng),
        synth_disc(2 * FS, True, rng),
        synth_disc(FS, False, rng)])
    out_gr, sq_blk = run_block_ff(stream)
    core = squelch_core.NoiseSquelch(input_rate=FS, deviation=DEVIATION)
    out_direct = core.process(stream)
    diff = float(np.max(np.abs(out_gr - out_direct)))
    check("wrapper: GR output matches squelch_core exactly",
          len(out_gr) == n and diff < 1e-4, "(max diff %.2e)" % diff)
    check("wrapper: gate opened on quieted segment",
          bool(np.any(np.abs(out_gr[int(1.5 * FS):2 * FS]) > 0)))
    check("wrapper: gate closed on noise tail",
          float(np.max(np.abs(out_gr[int(3.6 * FS):]))) == 0.0)

    # ------------------------------------------------------------------
    # 2/3. full op25_nbfm_c graph in every mode
    n = 2 * FS
    noise_iq = ((rng.standard_normal(n) + 1j * rng.standard_normal(n))
                * np.float32(0.05)).astype(np.complex64)
    audio = 0.5 * np.sin(2 * np.pi * 800.0 * np.arange(n) / FS)
    carrier_iq = fm_mod(audio)

    for mode in ('power', 'noise', 'voice'):
        try:
            nbfm = run_nbfm(mode, noise_iq, rng)
            ok = True
        except Exception as e:
            ok = False
            print("  exception: %s" % e)
        check("op25_nbfm_c ('%s'): builds and runs" % mode, ok)
        if ok and mode != 'power':
            check("op25_nbfm_c ('%s'): noise input keeps gate closed" % mode,
                  not nbfm.noise_squelch.is_open(),
                  "(quieting %.1f dB)" % nbfm.noise_squelch.quieting_db())

    nbfm = run_nbfm('noise', carrier_iq, rng)
    check("op25_nbfm_c ('noise'): carrier input opens gate",
          nbfm.noise_squelch.is_open(),
          "(quieting %.1f dB)" % nbfm.noise_squelch.quieting_db())

    # ------------------------------------------------------------------
    print()
    failed = [nm for nm, ok in results if not ok]
    print("%d/%d checks passed" % (len(results) - len(failed), len(results)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
