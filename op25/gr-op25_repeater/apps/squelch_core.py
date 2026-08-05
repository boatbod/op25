# -*- coding: utf-8 -*-
#
# OP25 Noise-Based Squelch Core (NBFM)
# Copyright 2026 W1JPI
#
# Squelch algorithms after Pieter-Tjerk de Boer, PA3FWM,
# "Squelch algorithms", https://www.pa3fwm.nl/technotes/tn16e.html
#
#   Primary method ("noise" mode): monitor audio frequencies above the
#   voice band at the FM discriminator output.  With no carrier present
#   the discriminator emits strong wideband noise; when a carrier is
#   received the high-frequency noise drops sharply (FM quieting), even
#   for signals too weak for a power squelch to detect reliably.
#
#   Optional refinement ("voice" mode): DB1NV's dual-band speech
#   detector.  Speech concentrates power at 200-600 Hz; broadband noise
#   and data signaling do not.  The ratio of 200-600 Hz power to
#   1000-1500 Hz power therefore separates voice from carrier-only or
#   data transmissions.
#
# This module is deliberately free of GNU Radio imports so the DSP and
# the squelch state machine can be unit-tested standalone (see
# squelch_core_test.py).  The GNU Radio wrapper lives in op25_squelch.py.
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

import numpy as np

# Measurement band for the noise squelch, chosen to sit above the voice
# band (<= 3 kHz plus splatter margin) and inside the narrowest channel
# filter feeding the nbfm block (+/-6.25 kHz legacy demod, +/-7.0 kHz
# dev demod in FDMA mode).
NOISE_BAND_LO   = 4000.0    # Hz
NOISE_BAND_HI   = 6000.0    # Hz
NOISE_BPF_TAPS  = 127

# No-carrier reference: mean power of a unit-gain discriminator
# (radians/sample) in the 4-6 kHz band at 24 kHz sampling, with the
# input noise band-limited by the channel filter.  Measured by
# simulation in squelch_core_test.py for the two demodulator channel
# filters seen in practice:
#     +/-7.0 kHz (dev demod, FDMA taps): 0.2703 rad^2 (-5.68 dB)
#     +/-9.6 kHz (dev demod, TDMA taps): 0.4145 rad^2 (-3.82 dB)
# The smaller value is used as the initial reference so start-up errs
# toward keeping the squelch closed; the runtime reference tracker
# (rise-only, see NoiseSquelch._track_reference) converges to the true
# level within ~200 ms of the first unsquelched noise.
REF_POWER_INIT  = 0.270     # rad^2/sample^2 in 4-6 kHz band (7 kHz IF filter)

VOICE_BAND_LO_1 =  200.0    # Hz  DB1NV speech band
VOICE_BAND_HI_1 =  600.0    # Hz
VOICE_BAND_LO_2 = 1000.0    # Hz  DB1NV comparison band
VOICE_BAND_HI_2 = 1500.0    # Hz
VOICE_BPF_TAPS  = 401       # narrow transitions need a longer filter

FRAME_MS        = 2.0       # decision granularity
POWER_TAU_MS    = 20.0      # smoothing time constant for power estimates
RAMP_MS         = 8.0       # audio gain ramp, click suppression
REF_TAU_MS      = 200.0     # reference tracker attack time constant

# Extra quieting required to return from HANG to OPEN, on top of the
# closing threshold.  Without it a signal sitting exactly at the closing
# threshold thrashes between the two states forever (see _frame_decision).
REHOLD_MARGIN_DB = 1.5


def design_bandpass(ntaps, f_lo, f_hi, fs):
    """Hamming windowed-sinc bandpass, unity gain at band center.

    Self-contained equivalent of filter.firdes.band_pass() so the same
    taps are used inside GNU Radio and in the standalone tests.
    """
    if not (0.0 < f_lo < f_hi < fs / 2.0):
        raise ValueError("bad passband %f-%f at fs=%f" % (f_lo, f_hi, fs))
    n = np.arange(ntaps, dtype=np.float64) - (ntaps - 1) / 2.0
    def lp(fc):
        return 2.0 * fc / fs * np.sinc(2.0 * fc / fs * n)
    h = (lp(f_hi) - lp(f_lo)) * np.hamming(ntaps)
    f0 = 0.5 * (f_lo + f_hi)
    h /= np.abs(np.sum(h * np.exp(-2j * np.pi * (f0 / fs) * n)))
    return h.astype(np.float32)


class FirFilter(object):
    """Streaming FIR with inter-call state (causal, same length out as in)."""
    def __init__(self, taps):
        self.taps = np.asarray(taps, dtype=np.float32)
        self.tail = np.zeros(len(self.taps) - 1, dtype=np.float32)

    def process(self, x):
        x = np.asarray(x, dtype=np.float32)
        if len(x) == 0:
            return x
        buf = np.concatenate((self.tail, x))
        y = np.convolve(buf, self.taps, mode='valid')
        self.tail = buf[len(buf) - (len(self.taps) - 1):]
        return y.astype(np.float32)

    def reset(self):
        self.tail[:] = 0


# squelch gate states
ST_CLOSED  = 0
ST_OPENING = 1   # quieting seen, waiting out the attack delay
ST_OPEN    = 2
ST_HANG    = 3   # quieting lost, waiting out the hang delay


class NoiseSquelch(object):
    """PA3FWM noise squelch (optionally with DB1NV voice detect).

    Feed it raw FM discriminator samples via process(); it returns the
    same samples gated by a click-free 0..1 envelope.  All decisions are
    made on 'quieting': how far the 4-6 kHz noise power has fallen below
    the no-carrier reference level.

        quieting_db = 10*log10(reference / measured)

    open_db is the quieting required to open (default 8 dB); the squelch
    closes when quieting falls below open_db - hyst_db for longer than
    hang_ms.  Thresholds are referenced to the discriminator's own
    no-carrier noise level, so they are independent of device gain,
    which is the chief weakness of a fixed power squelch (PA3FWM
    algorithm 1, currently analog.simple_squelch_cc in op25_nbfm).
    """

    def __init__(self, input_rate, deviation,
                 open_db=8.0, hyst_db=3.0, hang_ms=250.0,
                 voice_detect=False, voice_ratio_db=-3.0, voice_hold_ms=1500.0,
                 attack_ms=30.0, reference=0.0, debug=0, log_cb=None):
        self.input_rate = float(input_rate)
        # same gain expression as op25_nbfm's quadrature_demod_cf; used to
        # normalize measured power to a unit-gain (radians/sample) scale
        self.disc_gain = self.input_rate / (4.0 * np.pi * float(deviation))
        self.open_db = float(open_db)
        self.close_db = float(open_db) - float(hyst_db)
        self.rehold_db = self.close_db + REHOLD_MARGIN_DB
        self.voice_detect = bool(voice_detect)
        self.voice_ratio_db = float(voice_ratio_db)
        # An explicit no-carrier reference skips run-time calibration.
        # REF_POWER_INIT matches the demodulator's +/-7 kHz FDMA taps; the
        # +/-9.6 kHz TDMA taps (which multi_rx leaves selected unless
        # trunking narrows them) sit 1.9 dB hotter, so quieting reads that
        # much low until a signal dropout lets the tracker calibrate.
        # Measure the right value for a given receiver with
        # analyze-quieting.py over a noise-only capture.
        self.ref_fixed = float(reference) > 0.0
        self.ref_init = float(reference) if self.ref_fixed else REF_POWER_INIT
        self.debug = debug
        self.log_cb = log_cb        # optional callable(str) for logging

        self.frame_len = max(8, int(round(self.input_rate * FRAME_MS * 1e-3)))
        frame_s = self.frame_len / self.input_rate
        self.attack_frames = max(1, int(round(attack_ms * 1e-3 / frame_s)))
        self.hang_frames = max(1, int(round(hang_ms * 1e-3 / frame_s)))
        self.voice_hold_frames = max(1, int(round(voice_hold_ms * 1e-3 / frame_s)))
        self.ramp_step = frame_s * 1e3 / RAMP_MS / self.frame_len  # per sample
        self.power_alpha = 1.0 - np.exp(-FRAME_MS / POWER_TAU_MS)
        self.ref_alpha = 1.0 - np.exp(-FRAME_MS / REF_TAU_MS)

        self.noise_filt = FirFilter(design_bandpass(
            NOISE_BPF_TAPS, NOISE_BAND_LO, NOISE_BAND_HI, self.input_rate))
        if self.voice_detect:
            self.voice_filt_lo = FirFilter(design_bandpass(
                VOICE_BPF_TAPS, VOICE_BAND_LO_1, VOICE_BAND_HI_1, self.input_rate))
            self.voice_filt_hi = FirFilter(design_bandpass(
                VOICE_BPF_TAPS, VOICE_BAND_LO_2, VOICE_BAND_HI_2, self.input_rate))

        self.reset()

    def reset(self):
        self.state = ST_CLOSED
        self.state_frames = 0
        self.noise_power = self.ref_init     # start pessimistic: no quieting
        self.reference = self.ref_init
        self.envelope = 0.0
        self.gate_target = 0.0
        self.voice_p_lo = 1e-9
        self.voice_p_hi = 1e-9
        self.voice_timer = 0
        self._acc_sum = 0.0                 # partial-frame accumulators
        self._acc_vlo = 0.0
        self._acc_vhi = 0.0
        self._acc_n = 0
        self.noise_filt.reset()
        if self.voice_detect:
            self.voice_filt_lo.reset()
            self.voice_filt_hi.reset()

    def quieting_db(self):
        return 10.0 * np.log10(self.reference / max(self.noise_power, 1e-12))

    def is_open(self):
        return self.state in (ST_OPEN, ST_HANG)

    def _log(self, msg):
        if self.log_cb is not None:
            self.log_cb(msg)

    def _track_reference(self, p):
        # The no-carrier level is the physical maximum of discriminator
        # noise (any signal only quiets it), so measured power above the
        # current reference proves the reference is too low -- whatever
        # the gate is doing.  Tracking therefore rises in every state:
        # gating this to the closed state alone deadlocks a receiver that
        # starts up on an active carrier, because it can never observe
        # the noise floor it needs in order to close.  Rising on the
        # smoothed estimate (with a 200 ms attack) keeps impulse noise
        # from dragging the reference up.  REF_POWER_INIT deliberately
        # underestimates, so quieting reads low until calibration and
        # start-up errs toward keeping the squelch closed.
        if not self.ref_fixed and p > self.reference:
            self.reference += (p - self.reference) * self.ref_alpha

    def _voice_present(self):
        ratio_db = 10.0 * np.log10(
            max(self.voice_p_lo, 1e-12) / max(self.voice_p_hi, 1e-12))
        return ratio_db >= self.voice_ratio_db

    def _frame_decision(self):
        """Advance the squelch state machine by one frame."""
        q = self.quieting_db()
        carrier_open = q >= self.open_db
        carrier_hold = q >= self.close_db
        carrier_rehold = q >= self.rehold_db

        if self.voice_detect:
            if self._voice_present():
                self.voice_timer = self.voice_hold_frames
            elif self.voice_timer > 0:
                self.voice_timer -= 1
            carrier_open = carrier_open and (self.voice_timer > 0)
            # once open, quieting alone holds the gate; the voice hold
            # timer only gates the initial opening so pauses in speech
            # do not chop up a transmission mid-call

        prev = self.state
        self.state_frames += 1
        self._track_reference(self.noise_power)
        if self.state == ST_CLOSED:
            if carrier_open:
                self.state = ST_OPENING
        elif self.state == ST_OPENING:
            if not carrier_open:
                self.state = ST_CLOSED
            elif self.state_frames >= self.attack_frames:
                self.state = ST_OPEN
        elif self.state == ST_OPEN:
            if not carrier_hold:
                self.state = ST_HANG
        elif self.state == ST_HANG:
            # Returning to OPEN needs more quieting than leaving it did.
            # A signal decaying to exactly close_db would otherwise
            # oscillate OPEN<->HANG on adjacent frames, and because each
            # transition restarts the hang timer the squelch could never
            # close at all -- observed on air as an endless burst of
            # open->hang->open transitions at the threshold.
            if carrier_rehold:
                self.state = ST_OPEN
            elif self.state_frames >= self.hang_frames:
                self.state = ST_CLOSED

        if self.state != prev:
            self.state_frames = 0
            was_audible = prev in (ST_OPEN, ST_HANG)
            now_audible = self.state in (ST_OPEN, ST_HANG)
            self.gate_target = 1.0 if now_audible else 0.0
            names = {ST_CLOSED: 'closed', ST_OPENING: 'opening',
                     ST_OPEN: 'open', ST_HANG: 'hang'}
            if self.debug >= 10:
                self._log("noise squelch %s->%s quieting=%.1fdB" %
                          (names[prev], names[self.state], q))
            elif self.debug >= 2 and was_audible != now_audible:
                # only report changes an operator can hear; OPEN<->HANG is
                # internal bookkeeping and would otherwise flood the log
                self._log("noise squelch %s quieting=%.1fdB" %
                          ("opened" if now_audible else "closed", q))

    def process(self, x):
        """Gate a chunk of discriminator samples; returns same-length array."""
        x = np.asarray(x, dtype=np.float32)
        n = len(x)
        if n == 0:
            return x

        # normalized measurement paths (unit-gain discriminator scale)
        xn = x / self.disc_gain
        nb = self.noise_filt.process(xn)
        nb2 = nb * nb
        if self.voice_detect:
            vlo = self.voice_filt_lo.process(xn)
            vhi = self.voice_filt_hi.process(xn)
            vlo2 = vlo * vlo
            vhi2 = vhi * vhi

        env = np.empty(n, dtype=np.float32)
        pos = 0
        while pos < n:
            take = min(n - pos, self.frame_len - self._acc_n)
            seg = slice(pos, pos + take)

            self._acc_sum += float(np.sum(nb2[seg]))
            if self.voice_detect:
                self._acc_vlo += float(np.sum(vlo2[seg]))
                self._acc_vhi += float(np.sum(vhi2[seg]))
            self._acc_n += take

            # envelope slews linearly toward the gate target, bounded 0..1
            e0 = self.envelope
            tgt = self.gate_target
            if e0 == tgt:
                env[seg] = e0
            else:
                step = self.ramp_step if tgt > e0 else -self.ramp_step
                ramp = e0 + step * np.arange(1, take + 1, dtype=np.float32)
                np.clip(ramp, min(e0, tgt), max(e0, tgt), out=ramp)
                env[seg] = ramp
                self.envelope = float(ramp[-1])

            if self._acc_n >= self.frame_len:
                p = self._acc_sum / self._acc_n
                self.noise_power += (p - self.noise_power) * self.power_alpha
                if self.voice_detect:
                    plo = self._acc_vlo / self._acc_n
                    phi = self._acc_vhi / self._acc_n
                    self.voice_p_lo += (plo - self.voice_p_lo) * self.power_alpha
                    self.voice_p_hi += (phi - self.voice_p_hi) * self.power_alpha
                self._acc_sum = self._acc_vlo = self._acc_vhi = 0.0
                self._acc_n = 0
                self._frame_decision()

            pos += take

        return x * env
