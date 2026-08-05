#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tap, meter, record and forward the PCM audio OP25 emits over UDP.

Sits between op25's analog_udp output and the sockaudio player: every
datagram is forwarded unchanged for playback, then inspected locally for
a live level meter, a WAV recording and a per-interval TSV log.

Unlike the digital voice path, the NBFM analog path emits PCM
continuously and the squelch gates it to zero, so this monitor can
recover the exact gate timeline from the audio itself: a datagram of all
zero samples means the squelch was closed.  That timeline is the primary
evidence for judging whether a squelch behaved on live RF.

This file is part of OP25.
"""

import argparse
import math
import os
import signal
import socket
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PCM_RATE = 8000            # op25 analog_udp emits 8 kHz S16LE mono
PCM_WIDTH = 2
PCM_CHANNELS = 1
FLAG_BYTES = 2             # op25 sends 2-byte DRAIN/DROP control flags
DBFS_FLOOR = -120.0
BAR_FLOOR = -60.0
BAR_WIDTH = 24


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def dbfs(amplitude):
    if amplitude <= 0:
        return DBFS_FLOOR
    return max(DBFS_FLOOR, 20.0 * math.log10(amplitude / 32768.0))


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--listen-host", default="127.0.0.1")
    p.add_argument("--listen-port", type=int, default=23456)
    p.add_argument("--forward-host")
    p.add_argument("--forward-port", type=int)
    p.add_argument("--wav", help="record received PCM to this WAV file")
    p.add_argument("--wav-mode", choices=("all", "open"), default="all",
                   help="'all' preserves the gate timeline (default); "
                        "'open' omits squelched silence to save space")
    p.add_argument("--level-log", required=True, help="per-interval TSV output")
    p.add_argument("--ready-file", required=True,
                   help="touched once the socket is bound, removed on exit")
    p.add_argument("--meter", choices=("on", "off"), default="on")
    p.add_argument("--interval", type=float, default=1.0)
    args = p.parse_args()
    if not 1 <= args.listen_port <= 65535:
        p.error("--listen-port out of range")
    if (args.forward_host is None) != (args.forward_port is None):
        p.error("--forward-host and --forward-port must be given together")
    if not 0.1 <= args.interval <= 60.0:
        p.error("--interval must be 0.1-60 s")
    return args


class Monitor(object):
    def __init__(self, args):
        self.args = args
        self.running = True
        self.sock = None
        self.fwd = None
        self.wav = None
        self.levels = None
        self.ready_path = Path(args.ready_file)
        self.wav_path = Path(args.wav) if args.wav else None
        self.level_path = Path(args.level_log)

        self.p_sumsq = 0.0     # per-interval accumulators
        self.p_peak = 0
        self.p_samples = 0
        self.p_open = 0        # samples emitted with the gate open
        self.p_packets = 0
        self.t_samples = 0
        self.t_open = 0
        self.t_packets = 0
        self.t_flags = 0
        self.t_odd = 0
        self.transitions = 0
        self.gate = None       # None until the first audio datagram
        self.bar_width_last = 0

    def stop(self, *_):
        self.running = False

    def say(self, msg, end="\n"):
        try:
            print(msg, end=end, flush=True)
        except BrokenPipeError:
            self.args.meter = "off"

    def open(self):
        self.level_path.parent.mkdir(parents=True, exist_ok=True)
        self.levels = self.level_path.open("w", encoding="utf-8", buffering=1)
        self.levels.write("timestamp_utc\tstatus\tgate\trms_dbfs\tpeak_dbfs"
                          "\topen_fraction\tpackets\topen_seconds\ttotal_seconds\n")

        if self.wav_path is not None:
            self.wav_path.parent.mkdir(parents=True, exist_ok=True)
            self.wav = wave.open(str(self.wav_path), "wb")
            self.wav.setnchannels(PCM_CHANNELS)
            self.wav.setsampwidth(PCM_WIDTH)
            self.wav.setframerate(PCM_RATE)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
        self.sock.bind((self.args.listen_host, self.args.listen_port))
        self.sock.settimeout(min(0.25, self.args.interval))
        if self.args.forward_host is not None:
            self.fwd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # the launcher waits for this before starting op25, so no early
        # datagrams are lost to an unbound socket
        self.ready_path.parent.mkdir(parents=True, exist_ok=True)
        self.ready_path.touch()

        fwd_txt = ("%s:%d" % (self.args.forward_host, self.args.forward_port)
                   if self.fwd is not None else "disabled")
        self.say("Audio monitor: UDP %s:%d  playback=%s  wav=%s (%s)" % (
            self.args.listen_host, self.args.listen_port, fwd_txt,
            self.wav_path if self.wav_path else "off", self.args.wav_mode))

    def close(self):
        if self.args.meter == "on" and sys.stdout.isatty():
            self.say("")
        for closer in (self.wav, self.levels, self.sock, self.fwd):
            if closer is not None:
                try:
                    closer.close()
                except Exception:
                    pass
        self.wav = self.levels = self.sock = self.fwd = None
        try:
            self.ready_path.unlink()
        except OSError:
            pass
        self.say("Audio monitor stopped: packets=%d audio=%.1fs open=%.1fs "
                 "gate_transitions=%d flags=%d unexpected=%d" % (
                     self.t_packets, self.t_samples / PCM_RATE,
                     self.t_open / PCM_RATE, self.transitions,
                     self.t_flags, self.t_odd))

    def process(self, payload):
        # forward the byte stream verbatim first, flags included, so the
        # normal sockaudio player sees exactly what op25 sent
        if self.fwd is not None:
            try:
                self.fwd.sendto(payload,
                                (self.args.forward_host, self.args.forward_port))
            except OSError as e:
                print("forward failed: %s" % e, file=sys.stderr)

        if not payload:
            return
        if len(payload) == FLAG_BYTES:
            self.t_flags += 1
            return
        if len(payload) % PCM_WIDTH:
            self.t_odd += 1
            if self.t_odd <= 5:
                print("ignoring odd-sized packet (%d bytes)" % len(payload),
                      file=sys.stderr)
            return

        pcm = np.frombuffer(payload, dtype="<i2")
        peak = int(np.max(np.abs(pcm))) if pcm.size else 0
        gate_open = peak > 0        # squelch closed => gated to exact zero
        if self.gate is not None and gate_open != self.gate:
            self.transitions += 1
        self.gate = gate_open

        if self.wav is not None and (self.args.wav_mode == "all" or gate_open):
            try:
                # writeframes patches the RIFF sizes as it goes, so an
                # abrupt kill still leaves a playable file
                self.wav.writeframes(payload)
            except Exception as e:
                print("recording disabled: %s" % e, file=sys.stderr)
                try:
                    self.wav.close()
                except Exception:
                    pass
                self.wav = None

        self.p_sumsq += float(np.dot(pcm.astype(np.float64), pcm.astype(np.float64)))
        self.p_peak = max(self.p_peak, peak)
        self.p_samples += pcm.size
        self.p_packets += 1
        self.t_samples += pcm.size
        self.t_packets += 1
        if gate_open:
            self.p_open += pcm.size
            self.t_open += pcm.size

    def report(self):
        ts = utc_now()
        open_s = self.t_open / PCM_RATE
        total_s = self.t_samples / PCM_RATE
        if self.p_samples:
            frac = self.p_open / float(self.p_samples)
            rms_db = dbfs(math.sqrt(self.p_sumsq / self.p_samples))
            peak_db = dbfs(self.p_peak)
            gate = "open" if frac > 0.5 else ("partial" if frac > 0 else "closed")
            status = "active"
            norm = (max(BAR_FLOOR, rms_db) - BAR_FLOOR) / -BAR_FLOOR
            filled = min(BAR_WIDTH, max(0, int(round(norm * BAR_WIDTH))))
            line = ("AUDIO [%s] RMS %6.1f dBFS  peak %6.1f dBFS  gate %-7s "
                    "open %6.1fs / %6.1fs" % ("#" * filled + "." * (BAR_WIDTH - filled),
                                              rms_db, peak_db, gate, open_s, total_s))
            rms_txt, peak_txt, frac_txt = "%.2f" % rms_db, "%.2f" % peak_db, "%.3f" % frac
        else:
            status, gate = "idle", ""
            rms_txt = peak_txt = frac_txt = ""
            line = ("AUDIO [%s] idle - no PCM from op25          open %6.1fs / %6.1fs"
                    % ("." * BAR_WIDTH, open_s, total_s))

        if self.levels is not None:
            try:
                self.levels.write("%s\t%s\t%s\t%s\t%s\t%s\t%d\t%.3f\t%.3f\n" % (
                    ts, status, gate, rms_txt, peak_txt, frac_txt,
                    self.p_packets, open_s, total_s))
            except OSError as e:
                print("level log disabled: %s" % e, file=sys.stderr)
                self.levels = None

        if self.args.meter == "on":
            if sys.stdout.isatty():
                pad = " " * max(0, self.bar_width_last - len(line))
                self.say("\r" + line + pad, end="")
                self.bar_width_last = len(line)
            else:
                self.say(line)

        self.p_sumsq = 0.0
        self.p_peak = self.p_samples = self.p_open = self.p_packets = 0

    def run(self):
        try:
            self.open()
            nxt = time.monotonic() + self.args.interval
            while self.running:
                try:
                    payload, _ = self.sock.recvfrom(65535)
                except socket.timeout:
                    payload = None
                except InterruptedError:
                    continue
                if payload is not None:
                    self.process(payload)
                now = time.monotonic()
                if now >= nxt:
                    self.report()
                    while nxt <= now:
                        nxt += self.args.interval
        finally:
            if self.p_samples:
                self.report()
            self.close()


def main():
    args = parse_args()
    mon = Monitor(args)
    signal.signal(signal.SIGINT, mon.stop)
    signal.signal(signal.SIGTERM, mon.stop)
    try:
        mon.run()
    except OSError as e:
        print("Audio monitor failed: %s" % e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        mon.stop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
