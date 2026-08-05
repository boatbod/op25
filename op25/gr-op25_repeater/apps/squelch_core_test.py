#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Standalone validation for squelch_core.py (no GNU Radio required):
#     python3 squelch_core_test.py
#
# Simulates the op25 NBFM receive path feeding the noise squelch:
# complex AWGN channel -> channel IF filter (as p25_demodulator_dev
# builds it) -> quadrature discriminator -> squelch_core.NoiseSquelch,
# and exercises carrier appearance/disappearance, weak signals, hang
# bridging, impulse immunity, voice detection and streaming chunk
# invariance.  Also prints the no-carrier reference constants and the
# CNR -> quieting curve used to pick REF_POWER_INIT and the default
# opening threshold.
#
# This file is part of OP25
#

import sys
import numpy as np

import squelch_core

FS = 24000.0            # if_rate
DEVIATION = 4000.0      # matches op25_nbfm default
DISC_GAIN = FS / (4.0 * np.pi * DEVIATION)

IF_FILTERS = {          # p25_demodulator_dev if_filter variants
    'fdma7000': (7000.0, 1200.0),
    'tdma9600': (9600.0, 1200.0),
}


def design_lowpass(fc, trans, fs):
    """Hamming windowed-sinc LPF approximating filter.firdes.low_pass."""
    ntaps = int(3.3 * fs / trans)
    ntaps += (ntaps + 1) % 2
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc / fs * np.sinc(2.0 * fc / fs * n) * np.hamming(ntaps)
    return h / np.sum(h)


def channel(n, cnr_db, rng, if_filter='fdma7000', audio=None, fdev=DEVIATION):
    """Simulate the complex channel at if_rate.

    cnr_db: carrier-to-noise ratio in the IF filter bandwidth, or None
    for no carrier.  audio: modulating signal (+/-1 ~ +/-fdev Hz).
    """
    fc, trans = IF_FILTERS[if_filter]
    h = design_lowpass(fc, trans, FS)
    x = np.zeros(n, dtype=np.complex128)
    if cnr_db is not None:
        if audio is None:
            audio = np.zeros(n)
        phase = 2.0 * np.pi * np.cumsum(audio * fdev) / FS
        carrier = np.exp(1j * phase)
        noise_pow = 10.0 ** (-cnr_db / 10.0) / np.sum(h * h)
        x += carrier
    else:
        noise_pow = 1.0 / np.sum(h * h)   # level is arbitrary: the
        # discriminator is amplitude-invariant, only spectral shape matters
    x += np.sqrt(noise_pow / 2.0) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    x = np.convolve(x, h, mode='same')
    return x


def discriminate(x, gain=DISC_GAIN):
    d = np.angle(x[1:] * np.conj(x[:-1])) * gain
    return np.concatenate(([0.0], d)).astype(np.float32)


def voice(n, rng, fs=FS):
    """Speech-shaped test modulation: 300-3000 Hz noise, ~1 peak deviation."""
    w = rng.standard_normal(n)
    h = squelch_core.design_bandpass(401, 300.0, 3000.0, fs)
    v = np.convolve(w, h, mode='same')
    v /= 3.0 * np.std(v)
    return np.clip(v, -1.0, 1.0)


def tone(n, freq, fs=FS):
    return np.sin(2.0 * np.pi * freq * np.arange(n) / fs)


def band_power(disc_norm):
    """Mean power of unit-gain discriminator samples in the noise band."""
    h = squelch_core.design_bandpass(
        squelch_core.NOISE_BPF_TAPS, squelch_core.NOISE_BAND_LO,
        squelch_core.NOISE_BAND_HI, FS)
    y = np.convolve(disc_norm, h, mode='same')
    skip = len(h)
    return float(np.mean(y[skip:-skip] ** 2))


def run_squelch(disc, chunks=1000, **kw):
    """Run NoiseSquelch over a discriminator stream, return envelope."""
    sq = squelch_core.NoiseSquelch(input_rate=FS, deviation=DEVIATION, **kw)
    out = np.empty(len(disc), dtype=np.float32)
    pos = 0
    while pos < len(disc):
        n = min(chunks if np.isscalar(chunks) else int(next(chunks)), len(disc) - pos)
        out[pos:pos + n] = sq.process(disc[pos:pos + n])
        pos += n
    return out, sq


def envelope_of(disc, **kw):
    gated, sq = run_squelch(disc, **kw)
    src = np.where(np.abs(disc) > 1e-9, disc, 1.0)
    env = np.where(np.abs(disc) > 1e-9, gated / src, np.nan)
    return gated, sq, env


results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print("%-58s %s %s" % (name, "PASS" if cond else "FAIL", detail))


def main():
    rng = np.random.default_rng(1)

    # ------------------------------------------------------------------
    # reference constants: no-carrier noise power in the 4-6 kHz band of
    # a unit-gain discriminator, per channel filter
    print("== no-carrier reference (unit-gain discriminator, 4-6 kHz) ==")
    refs = {}
    for name in IF_FILTERS:
        d = discriminate(channel(int(20 * FS), None, rng, name), gain=1.0)
        refs[name] = band_power(d.astype(np.float64))
        print("  %-10s ref = %.4f rad^2 (%.2f dB)" %
              (name, refs[name], 10 * np.log10(refs[name])))
    ref_min = min(refs.values())
    print("  REF_POWER_INIT should be ~%.4f (currently %.4f)" %
          (ref_min, squelch_core.REF_POWER_INIT))
    check("REF_POWER_INIT matches simulated minimum within 0.5 dB",
          abs(10 * np.log10(ref_min / squelch_core.REF_POWER_INIT)) < 0.5)

    # ------------------------------------------------------------------
    # quieting curve: how much the noise band drops vs CNR
    print("== quieting vs CNR (fdma filter, voice modulated) ==")
    quieting = {}
    for cnr in (0, 3, 6, 9, 12, 15, 20):
        v = voice(int(6 * FS), rng)
        d = discriminate(channel(int(6 * FS), cnr, rng, 'fdma7000', audio=v), gain=1.0)
        q = 10 * np.log10(refs['fdma7000'] / band_power(d.astype(np.float64)))
        quieting[cnr] = q
        print("  CNR %2d dB -> quieting %5.1f dB" % (cnr, q))
    check("quieting monotonic in CNR",
          all(quieting[a] < quieting[b] + 0.5 for a, b in
              zip((0, 3, 6, 9, 12, 15), (3, 6, 9, 12, 15, 20))))
    check("default open threshold (8 dB) falls between CNR 3 and CNR 9",
          quieting[3] < 8.0 < quieting[9])

    # ------------------------------------------------------------------
    # functional: no carrier, squelch must stay closed
    d = discriminate(channel(int(5 * FS), None, rng))
    gated, sq, env = envelope_of(d)
    settle = int(0.3 * FS)
    check("no carrier: gate stays closed",
          np.nanmax(env[settle:]) < 0.01,
          "(max env %.4f)" % np.nanmax(env[settle:]))

    # ------------------------------------------------------------------
    # functional: carrier appears at 2s, disappears at 6s (CNR 15 dB)
    n_pre, n_sig, n_post = int(2 * FS), int(4 * FS), int(2 * FS)
    v = voice(n_sig, rng)
    d = np.concatenate([
        discriminate(channel(n_pre, None, rng)),
        discriminate(channel(n_sig, 15, rng, audio=v)),
        discriminate(channel(n_post, None, rng))])
    gated, sq, env = envelope_of(d)
    t_open = np.argmax(env > 0.99)
    open_delay_ms = (t_open - n_pre) / FS * 1e3
    check("carrier: opens promptly", 0 < open_delay_ms < 150,
          "(%.0f ms)" % open_delay_ms)
    mid = env[n_pre + int(0.3 * FS):n_pre + n_sig - int(0.05 * FS)]
    check("carrier: no dropouts during 4 s of voice", np.nanmin(mid) > 0.99,
          "(min env %.3f)" % np.nanmin(mid))
    after = env[n_pre + n_sig:]
    t_close = np.argmax(after < 0.01)
    close_delay_ms = t_close / FS * 1e3
    check("carrier drop: closes within hang + 200 ms",
          0 < close_delay_ms < 250 + 200, "(%.0f ms)" % close_delay_ms)
    check("carrier drop: stays closed",
          np.nanmax(after[t_close + int(0.1 * FS):]) < 0.01)

    # ------------------------------------------------------------------
    # weak-carrier opening point with the default 8 dB threshold
    open_cnr = None
    for cnr in np.arange(0.0, 12.5, 1.0):
        d = discriminate(channel(int(3 * FS), cnr, rng,
                                 audio=voice(int(3 * FS), rng)))
        _, sq2 = run_squelch(d)
        if sq2.is_open():
            open_cnr = cnr
            break
    check("weak carrier: opens between CNR 3 and 9 dB",
          open_cnr is not None and 3.0 <= open_cnr <= 9.0,
          "(opens at CNR %s dB)" % open_cnr)

    # ------------------------------------------------------------------
    # impulse immunity: 5 ms wideband burst must not open the gate
    d = discriminate(channel(int(3 * FS), None, rng))
    hit = int(1.5 * FS)
    d2 = d.copy()
    d2[hit:hit + int(0.005 * FS)] = np.pi * DISC_GAIN  # full-scale impulse
    gated, sq, env = envelope_of(d2)
    check("impulse: 5 ms burst does not open gate",
          np.nanmax(env[settle:]) < 0.01)

    # ------------------------------------------------------------------
    # hang: 100 ms dropout mid-call must be bridged
    n_a, n_gap, n_b = int(2 * FS), int(0.1 * FS), int(2 * FS)
    d = np.concatenate([
        discriminate(channel(n_a, 15, rng, audio=voice(n_a, rng))),
        discriminate(channel(n_gap, None, rng)),
        discriminate(channel(n_b, 15, rng, audio=voice(n_b, rng)))])
    gated, sq, env = envelope_of(d)
    gap = env[n_a:n_a + n_gap + int(0.05 * FS)]
    check("hang: 100 ms dropout bridged", np.nanmin(gap) > 0.9,
          "(min env %.3f)" % np.nanmin(gap))

    # ------------------------------------------------------------------
    # voice mode: speech opens, carrier-with-tone does not
    n = int(4 * FS)
    d = discriminate(channel(n, 15, rng, audio=voice(n, rng)))
    _, sq_v = run_squelch(d, voice_detect=True)
    check("voice mode: speech opens gate", sq_v.is_open())
    d = discriminate(channel(n, 15, rng, audio=0.8 * tone(n, 1200.0)))
    _, sq_t = run_squelch(d, voice_detect=True)
    check("voice mode: 1.2 kHz tone stays closed", not sq_t.is_open())
    d = discriminate(channel(n, 15, rng, audio=0.8 * tone(n, 1200.0)))
    _, sq_t2 = run_squelch(d)
    check("noise mode: same tone signal opens (sanity)", sq_t2.is_open())

    # ------------------------------------------------------------------
    # regression: a signal parked exactly at the closing threshold must
    # not oscillate OPEN<->HANG, and must still be able to close.
    # Observed on air (WMUR-EDGE1, 2026-08-03): dozens of
    # open->hang->open transitions per second at quieting=5.0dB with the
    # hang timer reset by each one, so the squelch never closed.
    def park_at(sq, db, jitter_db, seconds, rng):
        """Hold the measured quieting near db (+/- jitter) and count churn."""
        transitions = []
        sq.log_cb = transitions.append
        sq.debug = 10                               # log every transition
        for _ in range(int(seconds * FS / sq.frame_len)):
            offset = rng.uniform(-jitter_db, jitter_db)
            sq.noise_power = sq.reference / (10.0 ** ((db + offset) / 10.0))
            sq._frame_decision()
        return sum(1 for m in transitions
                   if 'open->hang' in m or 'hang->open' in m)

    def opened_squelch(rng):
        d = discriminate(channel(int(2 * FS), 15, rng, audio=voice(int(2 * FS), rng)))
        sq = squelch_core.NoiseSquelch(input_rate=FS, deviation=DEVIATION, debug=0)
        sq.process(d)                               # open on a solid signal
        assert sq.is_open()
        return sq

    sq = opened_squelch(rng)
    flaps = park_at(sq, sq.close_db, 0.4, 10.0, rng)   # jitter across the line
    check("threshold jitter: no OPEN<->HANG thrash", flaps <= 2,
          "(%d flap transitions in 10 s)" % flaps)
    check("threshold jitter: squelch still closes", not sq.is_open())

    # holding steady *at* the hold threshold should keep the gate open --
    # that is correct behavior, not the bug above
    sq = opened_squelch(rng)
    park_at(sq, sq.close_db + 0.05, 0.0, 3.0, rng)
    check("at hold threshold: gate stays open", sq.is_open())

    # ------------------------------------------------------------------
    # regression: a receiver that starts up on a carrier learns its
    # no-carrier reference from brief signal dropouts, even when the hang
    # timer keeps the gate open across them.  Tracking only while CLOSED
    # (the original code) could never calibrate here, leaving quieting
    # under-reported by the filter mismatch -- 1.9 dB on the TDMA taps,
    # which is what pushed the on-air signal down onto the threshold.
    # No carrier ever drops => no information => nothing to learn, so the
    # dropout is what makes calibration possible at all.
    n_a, n_gap, n_b = int(3 * FS), int(0.2 * FS), int(3 * FS)   # gap < hang
    d = np.concatenate([
        discriminate(channel(n_a, 15, rng, 'tdma9600', audio=voice(n_a, rng))),
        discriminate(channel(n_gap, None, rng, 'tdma9600')),
        discriminate(channel(n_b, 15, rng, 'tdma9600', audio=voice(n_b, rng)))])
    _, sq2 = run_squelch(d)
    true_ref = refs['tdma9600']
    err_init = abs(10 * np.log10(true_ref / squelch_core.REF_POWER_INIT))
    err_now = abs(10 * np.log10(true_ref / sq2.reference))
    check("start-up on carrier: dropout calibrates the reference",
          sq2.reference > squelch_core.REF_POWER_INIT * 1.15 and err_now < err_init,
          "(ref %.3f, %.1f dB from true, was %.1f dB off)" %
          (sq2.reference, err_now, err_init))
    check("start-up on carrier: gate held through the 200 ms dropout",
          sq2.is_open())

    # ------------------------------------------------------------------
    # log volume: an operator at -v 2 sees one line per audible change
    msgs = []
    d = np.concatenate([
        discriminate(channel(int(1 * FS), None, rng)),
        discriminate(channel(int(2 * FS), 15, rng, audio=voice(int(2 * FS), rng))),
        discriminate(channel(int(1 * FS), None, rng))])
    sq3 = squelch_core.NoiseSquelch(input_rate=FS, deviation=DEVIATION,
                                    debug=2, log_cb=msgs.append)
    sq3.process(d)
    check("logging at -v 2: one line per audible change", len(msgs) == 2,
          "(%d lines: %s)" % (len(msgs), "; ".join(m.split('quieting')[0].strip()
                                                   for m in msgs)))

    # ------------------------------------------------------------------
    # streaming: envelope independent of chunking
    n = int(3 * FS)
    v = voice(int(1 * FS), rng)
    d = np.concatenate([
        discriminate(channel(int(1 * FS), None, rng)),
        discriminate(channel(int(1 * FS), 15, rng, audio=v)),
        discriminate(channel(int(1 * FS), None, rng))])
    out_a, _ = run_squelch(d, chunks=len(d))
    sizes = iter(list(rng.integers(1, 700, size=len(d))) + [len(d)])
    out_b, _ = run_squelch(d, chunks=sizes)
    check("streaming: chunk-size invariant",
          np.max(np.abs(out_a - out_b)) < 1e-4,
          "(max diff %.2e)" % np.max(np.abs(out_a - out_b)))

    # ------------------------------------------------------------------
    print()
    failed = [n for n, ok in results if not ok]
    print("%d/%d checks passed" % (len(results) - len(failed), len(results)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
