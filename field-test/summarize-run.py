#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Summarize an NBFM squelch field-test run and flag misbehavior.

Correlates the squelch transitions op25 logged with the gate timeline the
audio monitor recovered from the PCM, then reports the verdict.  Checks
for the failure modes that matter on air:

  * chatter        - many gate changes per minute
  * never opened   - no audio passed at all
  * never closed   - gate stuck open for the whole run
  * flapping       - open/hang churn at the threshold (the state machine
                     should prevent this; if it appears, the hysteresis
                     margin is too small for this signal)

Usage: summarize-run.py results/<run-dir>

This file is part of OP25.
"""

import os
import re
import sys

LOG_OPEN = re.compile(r"noise squelch (opened|closed) quieting=(-?[\d.]+)dB")
LOG_INTERNAL = re.compile(r"noise squelch (\w+)->(\w+) quieting=(-?[\d.]+)dB")
CHATTER_PER_MIN = 12.0


def read_metadata(path):
    meta = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if "=" in line:
                    k, v = line.rstrip("\n").split("=", 1)
                    meta[k] = v
    return meta


def read_levels(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == len(header):
                rows.append(dict(zip(header, parts)))
    return rows


def read_log(path):
    audible, internal = [], []
    if not os.path.exists(path):
        return audible, internal
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LOG_OPEN.search(line)
            if m:
                audible.append((m.group(1), float(m.group(2))))
                continue
            m = LOG_INTERNAL.search(line)
            if m:
                internal.append((m.group(1), m.group(2), float(m.group(3))))
    return audible, internal


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: summarize-run.py results/<run-dir>")
    run = sys.argv[1]
    if not os.path.isdir(run):
        sys.exit("not a directory: %s" % run)

    meta = read_metadata(os.path.join(run, "run-metadata.txt"))
    levels = read_levels(os.path.join(run, "audio-levels.tsv"))
    audible, internal = read_log(os.path.join(run, "op25.log"))

    total_s = float(levels[-1].get("total_seconds") or 0.0) if levels else 0.0
    open_s = float(levels[-1].get("open_seconds") or 0.0) if levels else 0.0
    minutes = max(total_s / 60.0, 1e-9)

    print("=== squelch field test summary ===")
    print("run:        %s" % os.path.basename(run))
    print("mode:       %s  profile: %s" % (meta.get("mode", "?"),
                                           meta.get("profile", "?")))
    if meta.get("mode") != "power":
        print("settings:   open %s dB, hang %s ms, ref %s"
              % (meta.get("squelch_db", "?"), meta.get("hang_ms", "?"),
                 meta.get("squelch_ref", "0")))
    print("duration:   %.1f s of PCM, gate open %.1f s (%.1f%%)"
          % (total_s, open_s, 100.0 * open_s / total_s if total_s else 0.0))

    opens = sum(1 for kind, _ in audible if kind == "opened")
    closes = sum(1 for kind, _ in audible if kind == "closed")
    print("gate:       %d opens, %d closes (%.1f changes/min)"
          % (opens, closes, (opens + closes) / minutes))
    if audible:
        oq = [q for k, q in audible if k == "opened"]
        cq = [q for k, q in audible if k == "closed"]
        if oq:
            print("            opened at quieting %.1f..%.1f dB" % (min(oq), max(oq)))
        if cq:
            print("            closed at quieting %.1f..%.1f dB" % (min(cq), max(cq)))
    if internal:
        flaps = sum(1 for a, b, _ in internal
                    if {a, b} == {"open", "hang"})
        print("internal:   %d transitions logged (%d open<->hang)"
              % (len(internal), flaps))

    findings = []
    if total_s <= 0:
        findings.append("NO PCM: op25 sent no audio. Check that the channel is "
                        "enabled ('enable_analog') and the device is producing "
                        "samples; see op25.log.")
    else:
        if open_s == 0:
            findings.append("NEVER OPENED: no audio passed the squelch. Either "
                            "nothing was transmitting, or the threshold is too "
                            "high - lower NBFM_SQUELCH_DB, or capture the "
                            "discriminator (NBFM_RAW_OUTPUT=on) and run "
                            "analyze-quieting.py to see the real quieting.")
        elif open_s >= total_s - 0.5 and closes == 0:
            findings.append("NEVER CLOSED: the gate was open for the whole run. "
                            "Expected on a constant carrier like NOAA; on an "
                            "intermittent channel raise NBFM_SQUELCH_DB.")
        if (opens + closes) / minutes > CHATTER_PER_MIN:
            findings.append("CHATTER: %.1f gate changes/min. Raise NBFM_HANG_MS "
                            "to ride through fades, or raise NBFM_SQUELCH_DB if "
                            "it is opening on noise."
                            % ((opens + closes) / minutes))
        if internal:
            flaps = sum(1 for a, b, _ in internal if {a, b} == {"open", "hang"})
            if flaps > 20:
                findings.append("FLAPPING: %d open<->hang transitions. The signal "
                                "is parked at the closing threshold; the rehold "
                                "margin should prevent this, so please keep "
                                "op25.log and the discriminator capture." % flaps)

    print()
    if findings:
        print("findings:")
        for f in findings:
            print("  - %s" % f)
    else:
        print("findings:   none - squelch behaved as configured")

    wav = os.path.join(run, "gated-audio.wav")
    raw = os.path.join(run, "discriminator.raw")
    print()
    print("artifacts:")
    for path, note in ((wav, "gated audio, listen to judge quality"),
                       (raw, "raw discriminator, replay with NBFM_RAW_FILE= or "
                             "analyze with analyze-quieting.py"),
                       (os.path.join(run, "audio-levels.tsv"), "per-second levels"),
                       (os.path.join(run, "op25.log"), "op25 diagnostics"),
                       (os.path.join(run, "op25.json"), "exact config used")):
        if os.path.exists(path):
            print("  %-28s %s (%.1f KB)"
                  % (os.path.basename(path), note, os.path.getsize(path) / 1024.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
