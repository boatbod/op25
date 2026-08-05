# NBFM Noise-Squelch Field Test Kit

Live-antenna test equipment for the PA3FWM noise squelch on this branch
(`nbfm-noise-squelch`).  Target: Ubuntu 22.04 or 24.04 with an RTL-SDR.

Receive only.  Nothing here transmits, and nothing decrypts anything.
Monitoring rules vary by jurisdiction; comply with the ones that apply to
you and to anything you record.

## Quick start

```bash
sudo ./deploy.sh
```
```bash
./run-field-test.sh --check noaa
```
```bash
./run-field-test.sh noise noaa
```

`deploy.sh` installs GNU Radio 3.10 and dependencies, patches OP25's CMake
policies for CMake 4, builds and installs, verifies the GNU Radio Python
modules import, and runs both self-test suites (expect 21/21 and 9/9).

Nothing needs hand-editing: `run-field-test.sh` renders the config for each
run from `template-nbfm.json` and saves it alongside the results.

Do **not** use `rtl_test -t` to check the dongle — it is an E4000-only
benchmark that reports "No E4000 tuner found" on R820T/R820T2 hardware.
`--check` performs a tuned sample read instead.

## What a run produces

Each run writes a timestamped directory under `results/`:

| File | What it is |
|---|---|
| `gated-audio.wav` | 8 kHz mono audio that passed the squelch, gate timeline preserved |
| `audio-levels.tsv` | per-second RMS, peak, and gate state |
| `op25.log` | OP25 diagnostics including squelch transitions |
| `op25.json` | the exact configuration that produced this run |
| `run-metadata.txt` | frequency, gain, ppm, thresholds, host, commit, timings |
| `discriminator.raw` | raw discriminator, if `NBFM_RAW_OUTPUT=on` |

At verbosity 2 (the default) OP25 prints one line per audible change:

```text
noise squelch opened quieting=14.7dB
noise squelch closed quieting=4.8dB
```

The live meter shows what is reaching the audio device, including whether
the gate is open — the NBFM path streams PCM continuously and the squelch
gates it to zero, so the monitor recovers the gate timeline from the audio
itself:

```text
AUDIO [##########..............] RMS  -31.4 dBFS  peak  -12.8 dBFS  gate open      open   42.0s /  115.0s
```

When the run stops, `summarize-run.py` prints a verdict and flags chatter,
never-opened, never-closed, and threshold flapping. Status UI while running:
`http://127.0.0.1:8080` (remote: `ssh -L 8080:127.0.0.1:8080 user@host`).

## Choosing a target

`./run-field-test.sh --list` prints the built-in profiles.

| Profile | Why |
|---|---|
| `noaa`, `noaa2`…`noaa7` | NOAA weather radio: a permanent carrier with real voice. The best first-light check, and the right place to measure your receiver's reference. |
| `murs1`…`murs5` | MURS: sporadic short transmissions, legal to monitor. |
| `ham2m` | 146.520 MHz FM simplex: key-up/unkey behavior with a handheld. |
| `custom` | `NBFM_FREQUENCY_HZ=154935000 ./run-field-test.sh noise custom` |

## Test matrix

1. **Empty channel** — tune somewhere quiet. The gate must stay closed for
   minutes. Any false open is a finding; keep `op25.log`.
2. **Constant carrier** (`noaa`) — opens within ~100 ms and stays open with
   no chatter. `summarize-run.py` will report NEVER CLOSED, which is
   correct here.
3. **Intermittent traffic** (`ham2m`, `murs*`) — prompt open on key-up, no
   mid-transmission dropouts, closes about `NBFM_HANG_MS` after unkey.
4. **Weak signal** — a distant repeater, or attenuate the antenna. The
   default 8 dB threshold should open at roughly "weak but readable".
5. **A/B against the legacy squelch** — `./run-field-test.sh power noaa`
   runs the same channel with the original absolute-power squelch. The
   claim under test is that noise mode needs no per-device threshold
   hunting; note which mode opens on signals the other misses.
6. **Voice mode** — `./run-field-test.sh voice ...` additionally requires
   speech to open, so it stays shut for data bursts and steady tones.

## Deterministic A/B on one recording

The cleanest comparison uses identical input for every mode. Capture the
discriminator once, then replay it through each squelch:

```bash
NBFM_RAW_OUTPUT=on ./run-field-test.sh noise ham2m
```
```bash
NBFM_RAW_FILE=results/<run>/discriminator.raw ./run-field-test.sh power
```

Add `NBFM_DURATION=15m` to any run to stop on a timer and print the summary
automatically, which is what you want for an unattended soak test or a
bounded replay.

No radio is needed for the replay, and both modes see exactly the same
samples. `NBFM_IQ_FILE=` replays an IQ recording the same way.

## Measuring your receiver instead of guessing

`capture-diagnostic.sh` records unprocessed discriminator audio straight
from the dongle, then analyzes it:

```bash
./capture-diagnostic.sh noaa 2m
```

`analyze-quieting.py` reports the measured no-carrier reference, the
distribution of quieting, how much time sat above each candidate
threshold, and the open/close timeline the real state machine would
produce. Run it on any FM discriminator capture, including P25 C4FM: it
will not decode voice, but it does separate "nothing was transmitting"
from "a carrier was present but not decodable" — which speaker audio
alone cannot.

```bash
./analyze-quieting.py results/<run>/raw-channel.wav --trace
```

Capture on a **quiet** channel and the reported
`nbfm_noise_squelch_ref` is the correct no-carrier reference for that
receiver, antenna and gain setting. Pin it with `NBFM_SQUELCH_REF=` to
skip run-time calibration entirely.

The timeline the analyzer prints is produced by the same state machine the
receiver runs, scaled to the recording's own noise floor, so it matches
what OP25 would have done live — verified against a full replay run. That
makes threshold selection a desk exercise: capture once, then try
thresholds offline instead of standing at the antenna.

## Tuning

| Symptom | Adjust |
|---|---|
| Opens on noise, flutter, or distant intermod | raise `NBFM_SQUELCH_DB` toward 12 |
| Misses weak-but-readable signals | lower `NBFM_SQUELCH_DB` toward 5 |
| Tail chops syllables on fading mobiles | raise `NBFM_HANG_MS` |
| Quieting reads a couple of dB low right after start-up | expected; see below |

**Why quieting can read low at start-up.** The threshold is measured
against the receiver's no-carrier noise floor, which the squelch
calibrates at run time. The built-in starting value matches the
demodulator's ±7 kHz filter, but `multi_rx` leaves the wider ±9.6 kHz
taps selected unless trunking narrows them, and that floor sits about
1.9 dB hotter. Calibration is deliberately one-way (it can only raise the
reference, so noise never gets mistaken for signal), so until the squelch
observes actual noise, quieting reads up to ~1.9 dB low. A receiver
started on a live carrier learns from the first dropout. To remove the
uncertainty, measure the reference with `capture-diagnostic.sh` on a quiet
channel and pin it with `NBFM_SQUELCH_REF=`.

## Troubleshooting

- `usb_claim_interface error -6`: the DVB kernel driver owns the dongle.
  `deploy.sh` installs the blacklist; reboot once.
- "Another SDR process already holds the dongle": only one process can own
  an RTL-SDR. Stop `dump1090`/`readsb`/another op25 first; the scripts
  name what they found.
- No audio: check `aplay -l`, then set the audio `device_name` in
  `template-nbfm.json` (e.g. `hw:1,0`, or `pulse` on a desktop).
  `NBFM_AUDIO=off` keeps metering and recording without local playback.
- `vmcircbuf` warnings at start-up are normal GNU Radio first-run noise.
- Audio present but off-pitch or garbled: set `NBFM_PPM` for your dongle.
- Meter says "idle - no PCM from op25": OP25 is not emitting audio at all,
  which is different from the squelch being closed. Check `op25.log`.
