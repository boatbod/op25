#!/bin/bash
#
# Record bounded FM discriminator audio straight from the dongle, before
# op25 sees it.  This is the evidence file for "was anything actually on
# the air?" -- feed it to analyze-quieting.py, which measures carrier
# presence objectively instead of relying on how the hiss sounds.
#
#   ./capture-diagnostic.sh [profile] [duration]
#   ./capture-diagnostic.sh noaa 2m
#   NBFM_FREQUENCY_HZ=154935000 ./capture-diagnostic.sh custom 15m
#
# Deliberately captures with no de-emphasis and no squelch: the point is
# the unprocessed discriminator output.  Output is 24 kHz mono WAV, which
# is what analyze-quieting.py expects.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=sdr-common.sh
source "$ROOT/sdr-common.sh"

PROFILE="${1:-noaa}"
DURATION="${2:-2m}"
DEVICE="${NBFM_DEVICE:-0}"
GAIN="${NBFM_GAIN:-32}"
PPM="${NBFM_PPM:-0}"
RATE="${NBFM_CAPTURE_RATE:-24000}"
DEEMPHASIS="${NBFM_DEEMPHASIS:-off}"

if [[ "$PROFILE" == "-h" || "$PROFILE" == "--help" ]]; then
    sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    list_profiles
    exit 0
fi

FREQUENCY="${NBFM_FREQUENCY_HZ:-}"
[[ -n "$FREQUENCY" ]] || FREQUENCY="$(profile_frequency "$PROFILE")"
if [[ -z "$FREQUENCY" ]]; then
    echo "Unknown profile '$PROFILE'; set NBFM_FREQUENCY_HZ or pick one of:" >&2
    list_profiles >&2
    exit 2
fi
if [[ ! "$DURATION" =~ ^[1-9][0-9]*[smhd]?$ ]]; then
    echo "Duration must be a value timeout(1) accepts, e.g. 300, 2m, 1h." >&2
    exit 2
fi
if [[ ! "$RATE" =~ ^[0-9]+$ ]] || (( RATE < 13000 )); then
    echo "NBFM_CAPTURE_RATE must be >= 13000 Hz to carry the 4-6 kHz" >&2
    echo "measurement band that analyze-quieting.py needs." >&2
    exit 2
fi

require_commands rtl_fm ffmpeg ffprobe timeout flock sha256sum
check_sdr_services
check_busy_processes
lock_device "$DEVICE"

RUN_ID="$(date -u +%Y%m%d-%H%M%S)"
RUN_DIR="$ROOT/results/$RUN_ID-capture-$PROFILE"
WAV="$RUN_DIR/raw-channel.wav"
PART="$WAV.partial"
META="$RUN_DIR/capture-metadata.txt"
RTL_LOG="$RUN_DIR/rtl-fm.log"
FFMPEG_LOG="$RUN_DIR/ffmpeg.log"
mkdir -p "$RUN_DIR"

{
    echo "profile=$PROFILE"
    echo "label=$(profile_label "$PROFILE")"
    echo "frequency_hz=$FREQUENCY"
    echo "duration_request=$DURATION"
    echo "sample_rate_hz=$RATE"
    echo "device=$DEVICE"
    echo "gain=$GAIN"
    echo "ppm=$PPM"
    echo "deemphasis=$DEEMPHASIS"
    echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "host=$(hostname)"
    echo "kernel=$(uname -r)"
} > "$META"

echo "Discriminator capture"
echo "Channel:   $(profile_label "$PROFILE") ($FREQUENCY Hz)"
echo "Duration:  $DURATION at $RATE Hz"
echo "Output:    $WAV"
echo

echo "Preflight: tuned sample read..."
if ! check_dongle "$DEVICE" "$FREQUENCY"; then
    echo "capture_status=preflight_failed" >> "$META"
    exit 1
fi

cmd=(rtl_fm -d "$DEVICE" -f "$FREQUENCY" -M fm -s "$RATE" -r "$RATE"
     -g "$GAIN" -p "$PPM" -E dc)
[[ "$DEEMPHASIS" == "on" ]] && cmd+=(-E deemp)

echo "Recording for $DURATION; no output until it finishes."
set +e
timeout --foreground --signal=INT --kill-after=5s "$DURATION" "${cmd[@]}" 2>"$RTL_LOG" |
    ffmpeg -nostdin -hide_banner -loglevel warning -f s16le -ar "$RATE" -ac 1 \
           -i pipe:0 -c:a pcm_s16le -f wav -y "$PART" 2>"$FFMPEG_LOG"
statuses=("${PIPESTATUS[@]}")
set -e

{
    echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "rtl_fm_status=${statuses[0]}"
    echo "ffmpeg_status=${statuses[1]}"
} >> "$META"

# 124/130 are the expected timeout/interrupt exits for a bounded capture
if [[ "${statuses[0]}" != "0" && "${statuses[0]}" != "124" && "${statuses[0]}" != "130" ]]; then
    echo "rtl_fm failed (${statuses[0]}); see $RTL_LOG" >&2
    echo "capture_status=rtl_fm_failed" >> "$META"
    exit "${statuses[0]}"
fi
if [[ "${statuses[1]}" != "0" ]] || [[ ! -s "$PART" ]]; then
    echo "ffmpeg failed (${statuses[1]}); see $FFMPEG_LOG" >&2
    echo "capture_status=ffmpeg_failed" >> "$META"
    exit 1
fi

duration_s="$(ffprobe -v error -show_entries format=duration \
              -of default=nk=1:nw=1 "$PART" 2>/dev/null || true)"
if [[ -z "$duration_s" ]]; then
    echo "Capture could not be validated by ffprobe." >&2
    echo "capture_status=invalid_wav" >> "$META"
    exit 1
fi
mv "$PART" "$WAV"
{
    echo "wav_duration_seconds=$duration_s"
    echo "wav_bytes=$(stat -c '%s' "$WAV")"
    echo "wav_sha256=$(sha256sum "$WAV" | awk '{print $1}')"
    echo "capture_status=complete"
} >> "$META"

echo
echo "Capture complete: $WAV ($duration_s s)"
echo
python3 "$ROOT/analyze-quieting.py" "$WAV" --deviation "${NBFM_DEVIATION:-4000}" || true
