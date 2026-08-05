#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a multi_rx config for an NBFM squelch field-test run.

Takes the base template plus a squelch mode, a frequency and any
environment overrides, and writes the exact configuration used for a run
into that run's results directory.  Nothing is hand-edited, and every
run keeps a copy of the config that produced it.

Also renders replay sources, which need no radio at all:
  --iq-file FILE    an IQ recording, played through op25's iqsrc device
  --raw-file FILE   a float32 discriminator capture (nbfm_raw_input),
                    the cleanest way to A/B squelch modes on identical
                    input

This file is part of OP25.
"""

import argparse
import json
import sys


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--template", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--mode", choices=("power", "noise", "voice"), default="noise")
    p.add_argument("--frequency-hz", type=int)
    p.add_argument("--label", default="nbfm test")
    p.add_argument("--device", default="0")
    p.add_argument("--gain", default="32")
    p.add_argument("--ppm", type=float, default=0.0)
    p.add_argument("--sample-rate", type=int, default=960000)
    p.add_argument("--if-rate", type=int, default=24000)
    p.add_argument("--deviation", type=int, default=4000)
    p.add_argument("--squelch-db", type=float, default=8.0)
    p.add_argument("--hang-ms", type=int, default=250)
    p.add_argument("--squelch-ref", type=float, default=0.0,
                   help="explicit no-carrier reference (0 = auto-calibrate)")
    p.add_argument("--power-threshold", type=float, default=-60.0)
    p.add_argument("--power-gain", type=float, default=0.0015)
    p.add_argument("--audio-port", type=int, default=23456,
                   help="where op25 sends PCM (the audio monitor listens here)")
    p.add_argument("--playback-port", type=int, default=23458,
                   help="where the monitor forwards PCM for sockaudio")
    p.add_argument("--audio", choices=("on", "off"), default="on")
    p.add_argument("--terminal", default="http:127.0.0.1:8080")
    p.add_argument("--raw-output", default="")
    p.add_argument("--iq-file")
    p.add_argument("--raw-file")
    p.add_argument("--print", dest="show", action="store_true",
                   help="also print the rendered config")
    return p.parse_args()


def main():
    args = parse_args()
    with open(args.template, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if len(cfg.get("channels", [])) != 1 or len(cfg.get("devices", [])) != 1:
        sys.exit("template must define exactly one channel and one device")
    chan = cfg["channels"][0]
    dev = cfg["devices"][0]

    replaying = bool(args.iq_file or args.raw_file)
    if not replaying and args.frequency_hz is None:
        sys.exit("--frequency-hz is required unless replaying a file")

    chan["name"] = args.label
    chan["if_rate"] = args.if_rate
    chan["nbfm_deviation"] = args.deviation
    chan["destination"] = "udp://127.0.0.1:%d" % args.audio_port
    chan["nbfm_squelch_mode"] = args.mode
    chan["nbfm_raw_output"] = args.raw_output

    # keep only the keys that apply to the selected squelch mode, so the
    # saved config is an honest record of what was in effect
    for key in ("nbfm_squelch_threshold", "nbfm_squelch_gain",
                "nbfm_noise_squelch_db", "nbfm_noise_squelch_hang",
                "nbfm_noise_squelch_ref", "nbfm_raw_input"):
        chan.pop(key, None)
    if args.mode == "power":
        chan["nbfm_squelch_threshold"] = args.power_threshold
        chan["nbfm_squelch_gain"] = args.power_gain
    else:
        chan["nbfm_noise_squelch_db"] = args.squelch_db
        chan["nbfm_noise_squelch_hang"] = args.hang_ms
        if args.squelch_ref > 0:
            chan["nbfm_noise_squelch_ref"] = args.squelch_ref

    if args.raw_file:
        # Discriminator replay: op25_nbfm reads the floats straight into
        # the squelch and null-sinks the channel input, so the device only
        # has to exist and stay in step.  iqfile_source has no float32
        # mode, but at 2 bytes per component one complex item is 4 bytes,
        # exactly one float32 -- so it consumes the same file at the same
        # item rate and reaches EOF together with the audio path.
        chan["nbfm_raw_input"] = args.raw_file
        chan["frequency"] = args.frequency_hz or 162400000
        dev.update({"args": "iqsrc", "iq_file": args.raw_file, "iq_size": 2,
                    "iq_signed": True, "iq_seek": 0, "gains": "",
                    "rate": args.if_rate, "ppm": 0.0, "tunable": False,
                    "frequency": chan["frequency"]})
    elif args.iq_file:
        chan["frequency"] = args.frequency_hz or 162400000
        dev.update({"args": "iqsrc", "iq_file": args.iq_file, "iq_size": 2,
                    "iq_signed": True, "iq_seek": 0, "gains": "",
                    "rate": args.sample_rate, "ppm": 0.0, "tunable": False,
                    "frequency": chan["frequency"]})
    else:
        chan["frequency"] = args.frequency_hz
        dev.update({"args": "rtl=%s" % args.device,
                    "frequency": args.frequency_hz,
                    # op25's device parser wants an integer gain; the RTL
                    # driver then snaps to its nearest supported step
                    "gains": "LNA:%d" % int(round(float(args.gain))),
                    "gain_mode": False, "ppm": args.ppm,
                    "rate": args.sample_rate, "tunable": False})
        dev.pop("iq_file", None)

    if args.audio == "off":
        cfg.pop("audio", None)
    else:
        cfg["audio"]["instances"][0]["udp_port"] = args.playback_port
    cfg["terminal"]["terminal_type"] = args.terminal

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)
        f.write("\n")

    source = args.raw_file or args.iq_file or ("%d Hz" % args.frequency_hz)
    detail = ("threshold %.0f dB, hang %d ms" % (args.squelch_db, args.hang_ms)
              if args.mode != "power" else "threshold %.0f dB" % args.power_threshold)
    print("rendered %s: mode=%s source=%s %s" % (args.output, args.mode, source, detail))
    if args.show:
        print(json.dumps(cfg, indent=4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
