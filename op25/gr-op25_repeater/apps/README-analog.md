`multi_rx.py` now supports a simple narrowband fm analog demodulator.  It piggybacks alongside the regular digital voice channel object defined in `cfg.json` and can either be controled by trunking (e.g. for SmartNet/SmartZone monitoring) or turned on and used as a stand-alone nbfm receiver.

```
    "channels": [
        {
            "name": "voice channel", 
            "device": "rtl1",
            "destination": "udp://127.0.0.1:23456", 
            "frequency": 859000000,
            "enable_analog": "auto",
            "nbfm_deviation": 4000,
            "nbfm_squelch": -60,
            "demod_type": "fsk4", 
            "filter_type": "widepulse", 
            "excess_bw": 0.2, 
            "if_rate": 24000, 
            "symbol_rate": 4800,
            "plot": ""
        }
```

Parameters of relevance to the NBFM module are:
```
    enable_analog: "off","on" or "auto"   - auto is the default for use with trunking
    nbfm_deviation: 4000                  - deviation in Hz; will affect output volume
    nbfm_squelch_threshold: -60           - approx avg power (in dB) required to open squelch ("power" mode)
    nbfm_squelch_gain: 0.0015             - power averaging constant ("power" mode)
    nbfm_squelch_mode: "power"            - "power", "noise" or "voice" (see below)
    nbfm_noise_squelch_db: 8              - quieting (dB) required to open ("noise"/"voice" modes)
    nbfm_noise_squelch_hang: 250          - hang time in ms before closing ("noise"/"voice" modes)
    nbfm_noise_squelch_ref: 0             - explicit no-carrier reference; 0 auto-calibrates
```

## Squelch modes

Squelch algorithms follow PA3FWM's overview (https://www.pa3fwm.nl/technotes/tn16e.html).

`"power"` (default) is the original behavior: `analog.simple_squelch_cc` compares
average channel power against `nbfm_squelch_threshold`.  The threshold is an
absolute level, so the right value depends on SDR hardware, gain settings and
antenna, and usually needs manual calibration per installation.

`"noise"` is a classic FM noise squelch.  It measures noise power at 4-6 kHz --
above the voice band -- at the discriminator output.  With no carrier the
discriminator produces strong high-frequency noise; any carrier suppresses it
(FM quieting).  Because the discriminator is amplitude-invariant, the no-carrier
noise level is a known constant and `nbfm_noise_squelch_db` is expressed in dB
of quieting rather than absolute power: no per-device calibration is needed.
The default of 8 dB opens at roughly 6-7 dB CNR (weak but readable voice);
raise it toward 12-15 dB to open only on solid signals, or lower it toward 5 dB
to chase noisy ones.  Opening takes ~80 ms; closing is delayed by
`nbfm_noise_squelch_hang` so brief fades and mobile flutter do not chop audio.
Gain transitions are ramped over 8 ms to avoid clicks, and returning from the
hang state needs slightly more quieting than leaving it did, so a signal
sitting exactly on the closing threshold cannot oscillate.

The no-carrier reference is calibrated at run time by a tracker that can only
raise it, so noise is never mistaken for signal.  The built-in starting value
matches the demodulator's +/-7 kHz FDMA taps; `multi_rx` leaves the wider
+/-9.6 kHz TDMA taps selected unless trunking narrows them, and that noise
floor is about 1.9 dB hotter, so quieting reads up to 1.9 dB low until the
squelch observes actual channel noise (a receiver started on a live carrier
learns from its first dropout).  Set `nbfm_noise_squelch_ref` to pin a
measured value and skip calibration; `field-test/analyze-quieting.py` reports
the correct number for a given receiver from a noise-only capture.

`"voice"` is `"noise"` plus DB1NV's dual-band speech detector: opening
additionally requires the 200-600 Hz band to dominate the 1000-1500 Hz band,
which is characteristic of speech but not of noise, data bursts or steady
tones.  Once open, quieting alone holds the gate so speech pauses do not chop
the audio.  Useful for channels that carry telemetry or MDC/data bursts you do
not want to hear; experimental otherwise.

In `"noise"` and `"voice"` modes the power squelch is bypassed entirely and
`nbfm_squelch_threshold`/`nbfm_squelch_gain` are ignored.

The DSP core is in `squelch_core.py` and can be validated without GNU Radio or
radio hardware by running `python3 squelch_core_test.py`, which simulates the
receive chain (channel noise, IF filtering, discriminator) and prints a
CNR-to-quieting table along with pass/fail functional checks.  With GNU Radio
and op25 built, `python3 squelch_gr_test.py` additionally verifies the
flowgraph integration: gating under scheduler-driven buffer chunking matches
the core bit-for-bit, and `op25_nbfm_c` builds and runs in all three modes.

