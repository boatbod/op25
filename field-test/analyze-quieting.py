#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure FM quieting in a discriminator recording.

Turns a captured FM discriminator stream into an objective carrier-presence
trace, and reports the numbers needed to configure the noise squelch on a
particular receiver:

  * the measured no-carrier reference   -> nbfm_noise_squelch_ref
  * the distribution of quieting        -> nbfm_noise_squelch_db
  * the open/close timeline the real state machine would produce

Accepts either input:

  --format wav    16-bit mono WAV, e.g. `rtl_fm -M fm -s 24000` output or
                  a capture-diagnostic.sh raw-channel.wav
  --format raw    float32, op25's `nbfm_raw_output` at the channel if_rate

Because quieting is a power ratio, absolute recording level does not
matter: the reference is derived from the capture itself as a high
percentile of band power (any carrier only reduces it, so the upper tail
is the no-carrier floor).  This works on any FM-modulated capture,
including P25 C4FM: it will not decode voice, but it does distinguish
"nothing was transmitting" from "a carrier was present but not
decodable", which speaker audio alone cannot.

This file is part of OP25.
"""

import argparse
import os
import sys
import wave

import numpy as np

APPS_REL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "op25", "gr-op25_repeater", "apps")
if os.path.isdir(APPS_REL):
    sys.path.insert(0, APPS_REL)

try:
    import squelch_core
except ImportError:
    sys.stderr.write("Unable to import squelch_core.py; run from the field-test\n"
                     "directory of the op25 tree, or set PYTHONPATH to its apps dir.\n")
    raise

REF_PERCENTILE = 95.0      # upper tail of band power == no-carrier floor
BAR_WIDTH = 30
BAR_MAX_DB = 25.0


def load(path, fmt, rate):
    if fmt == "auto":
        fmt = "wav" if path.lower().endswith(".wav") else "raw"
    if fmt == "wav":
        with wave.open(path, "rb") as w:
            if w.getnchannels() != 1:
                raise SystemExit("expected mono WAV, got %d channels" % w.getnchannels())
            if w.getsampwidth() != 2:
                raise SystemExit("expected 16-bit WAV, got %d bytes/sample"
                                 % w.getsampwidth())
            rate = w.getframerate()
            raw = w.readframes(w.getnframes())
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    else:
        x = np.fromfile(path, dtype=np.float32).astype(np.float64)
        if rate is None:
            raise SystemExit("--rate is required for raw float32 input")
    if len(x) == 0:
        raise SystemExit("no samples read from %s" % path)
    return x, rate


def band_powers(x, rate, frame_ms):
    """Per-frame mean power in the squelch's noise measurement band."""
    hi = squelch_core.NOISE_BAND_HI
    if rate <= 2.0 * hi:
        raise SystemExit(
            "sample rate %d Hz cannot carry the %.0f-%.0f Hz measurement band;\n"
            "capture at 24000 Hz (rtl_fm -s 24000) or higher."
            % (rate, squelch_core.NOISE_BAND_LO, hi))
    taps = squelch_core.design_bandpass(
        squelch_core.NOISE_BPF_TAPS, squelch_core.NOISE_BAND_LO, hi, rate)
    y = np.convolve(x, taps, mode="same")
    skip = len(taps)
    if len(y) > 2 * skip:
        y = y[skip:-skip]
    n = max(1, int(round(rate * frame_ms * 1e-3)))
    usable = (len(y) // n) * n
    if usable == 0:
        raise SystemExit("capture is shorter than one %.0f ms frame" % frame_ms)
    return (y[:usable] ** 2).reshape(-1, n).mean(axis=1), n / float(rate)


def state_timeline(x, rate, deviation, ref_measured, open_db, hang_ms):
    """Run the production state machine over the capture, scaled so its
    calibrated reference matches what this recording actually shows."""
    disc_gain = rate / (4.0 * np.pi * deviation)
    # NoiseSquelch normalizes by disc_gain and compares against
    # REF_POWER_INIT; scale the input so the recording's own no-carrier
    # floor lands there, making its decisions match a live receiver's.
    scale = np.sqrt(squelch_core.REF_POWER_INIT / ref_measured) * disc_gain
    sq = squelch_core.NoiseSquelch(input_rate=rate, deviation=deviation,
                                   open_db=open_db, hang_ms=hang_ms,
                                   reference=squelch_core.REF_POWER_INIT)
    events = []
    audible_prev = False
    chunk = int(rate // 10)
    for pos in range(0, len(x), chunk):
        seg = (x[pos:pos + chunk] * scale).astype(np.float32)
        sq.process(seg)
        if sq.is_open() != audible_prev:
            audible_prev = sq.is_open()
            events.append((pos / float(rate), "open" if audible_prev else "close"))
    return events, sq


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("capture", help="WAV or raw float32 discriminator capture")
    p.add_argument("--format", choices=("auto", "wav", "raw"), default="auto")
    p.add_argument("--rate", type=int, help="sample rate for raw input")
    p.add_argument("--deviation", type=float, default=4000.0,
                   help="channel deviation in Hz (default 4000)")
    p.add_argument("--open-db", type=float, default=8.0,
                   help="threshold to evaluate (default 8)")
    p.add_argument("--hang-ms", type=float, default=250.0)
    p.add_argument("--frame-ms", type=float, default=100.0,
                   help="trace resolution (default 100 ms)")
    p.add_argument("--trace", action="store_true",
                   help="print the per-frame quieting trace")
    p.add_argument("--quiet", action="store_true", help="summary only")
    args = p.parse_args()

    x, rate = load(args.capture, args.format, args.rate)
    powers, frame_s = band_powers(x, rate, args.frame_ms)
    ref = float(np.percentile(powers, REF_PERCENTILE))
    if ref <= 0:
        raise SystemExit("measured reference is zero; capture may be silent/clipped")
    quieting = 10.0 * np.log10(ref / np.maximum(powers, 1e-20))

    disc_gain = rate / (4.0 * np.pi * args.deviation)
    ref_norm = ref / (disc_gain ** 2)      # unit-gain discriminator scale

    print("capture:      %s" % args.capture)
    print("samples:      %d at %d Hz (%.1f s)" % (len(x), rate, len(x) / float(rate)))
    print("band:         %.0f-%.0f Hz, %.0f ms frames"
          % (squelch_core.NOISE_BAND_LO, squelch_core.NOISE_BAND_HI, args.frame_ms))
    print("reference:    %.4g (p%.0f of band power)" % (ref, REF_PERCENTILE))
    print("              nbfm_noise_squelch_ref: %.4g  (deviation %.0f Hz, if_rate %d)"
          % (ref_norm, args.deviation, rate))
    print()
    print("quieting distribution (dB):")
    for label, val in (("min", np.min(quieting)), ("median", np.median(quieting)),
                       ("p90", np.percentile(quieting, 90)),
                       ("p99", np.percentile(quieting, 99)),
                       ("max", np.max(quieting))):
        print("  %-8s %6.1f" % (label, val))
    print()
    print("time above threshold:")
    for thr in (3.0, 5.0, 8.0, 12.0, 15.0):
        frac = float(np.mean(quieting >= thr))
        print("  >= %4.1f dB   %5.1f%%  (%6.1f s)" % (thr, 100.0 * frac,
                                                      frac * len(powers) * frame_s))

    events, sq = state_timeline(x, rate, args.deviation, ref,
                               args.open_db, args.hang_ms)
    print()
    print("squelch timeline at open_db=%.1f, hang=%.0f ms: %d gate changes"
          % (args.open_db, args.hang_ms, len(events)))
    if not events:
        verdict = ("gate never opened - no carrier detected above threshold"
                   if not sq.is_open() else "gate open for the entire capture")
        print("  %s" % verdict)
    else:
        for t, kind in events[:40]:
            print("  %8.2f s  %s" % (t, kind))
        if len(events) > 40:
            print("  ... %d more" % (len(events) - 40))
        opens = sum(1 for _, k in events if k == "open")
        if opens and len(events) / max(1.0, len(powers) * frame_s) > 1.0:
            print("  NOTE: more than one gate change per second on average;"
                  " consider raising --open-db or --hang-ms")

    if args.trace and not args.quiet:
        print()
        print("per-frame trace:")
        for i, q in enumerate(quieting):
            filled = int(round(BAR_WIDTH * min(1.0, max(0.0, q) / BAR_MAX_DB)))
            print("  %8.2f s  %6.1f dB  %s" % (i * frame_s, q,
                                               "#" * filled + "." * (BAR_WIDTH - filled)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
