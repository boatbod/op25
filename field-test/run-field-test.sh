#!/bin/bash
#
# Launch an NBFM squelch field test: render the config, tap the audio,
# run op25, and summarize what the squelch did.
#
#   ./run-field-test.sh [mode] [profile]
#   ./run-field-test.sh --check [profile]
#   ./run-field-test.sh --list
#
#   mode     noise (default) | power | voice
#   profile  noaa (default) | noaa2..7 | murs1..5 | ham2m | custom
#
# Overrides:
#   NBFM_FREQUENCY_HZ  explicit frequency (required for profile 'custom')
#   NBFM_GAIN          LNA gain, integer (default 32)
#   NBFM_PPM           dongle frequency correction (default 0)
#   NBFM_DEVIATION     channel deviation in Hz (default 4000)
#   NBFM_SQUELCH_DB    quieting required to open (default 8)
#   NBFM_HANG_MS       hang time in ms (default 250)
#   NBFM_SQUELCH_REF   explicit no-carrier reference (default 0 = auto)
#   NBFM_VERBOSITY     op25 verbosity (default 2: one line per gate change)
#   NBFM_DEVICE        dongle index (default 0)
#   NBFM_AUDIO         on|off  local ALSA playback (default on)
#   NBFM_RECORD        on|off  record gated audio (default on)
#   NBFM_METER         on|off  live level meter (default on)
#   NBFM_RAW_OUTPUT    on|off  also save the raw discriminator (default off)
#   NBFM_IQ_FILE       replay an IQ recording instead of using the radio
#   NBFM_RAW_FILE      replay a float32 discriminator capture
#   NBFM_DURATION      stop after this long and summarize, e.g. 15m (default:
#                      run until Ctrl+C)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=sdr-common.sh
source "$ROOT/sdr-common.sh"

MODE="${1:-noise}"
PROFILE="${2:-noaa}"
DEVICE="${NBFM_DEVICE:-0}"
GAIN="${NBFM_GAIN:-32}"
PPM="${NBFM_PPM:-0}"
DEVIATION="${NBFM_DEVIATION:-4000}"
SQUELCH_DB="${NBFM_SQUELCH_DB:-8}"
HANG_MS="${NBFM_HANG_MS:-250}"
SQUELCH_REF="${NBFM_SQUELCH_REF:-0}"
VERBOSITY="${NBFM_VERBOSITY:-2}"
AUDIO="${NBFM_AUDIO:-on}"
RECORD="${NBFM_RECORD:-on}"
METER="${NBFM_METER:-on}"
RAW_OUTPUT="${NBFM_RAW_OUTPUT:-off}"
IQ_FILE="${NBFM_IQ_FILE:-}"
RAW_FILE="${NBFM_RAW_FILE:-}"
DURATION="${NBFM_DURATION:-}"
AUDIO_PORT=23456
PLAYBACK_PORT=23458

if [[ "$MODE" == "--list" ]]; then
    echo "Squelch modes: noise (default), power (legacy baseline), voice"
    echo "Profiles:"
    list_profiles
    exit 0
fi

FREQUENCY="${NBFM_FREQUENCY_HZ:-}"
if [[ "$MODE" == "--check" ]]; then
    PROFILE="${2:-noaa}"
    [[ -n "$FREQUENCY" ]] || FREQUENCY="$(profile_frequency "$PROFILE")"
    if [[ -z "$FREQUENCY" ]]; then
        echo "Unknown profile '$PROFILE'; set NBFM_FREQUENCY_HZ or pick one of:" >&2
        list_profiles >&2
        exit 2
    fi
    lock_device "$DEVICE"
    check_dongle "$DEVICE" "$FREQUENCY"
    exit $?
fi

case "$MODE" in
    noise|power|voice) ;;
    *) echo "Unknown mode '$MODE' (expected noise, power or voice)" >&2; exit 2 ;;
esac
for name in AUDIO RECORD METER RAW_OUTPUT; do
    val="${!name}"
    if [[ "$val" != "on" && "$val" != "off" ]]; then
        echo "NBFM_$name must be 'on' or 'off'" >&2
        exit 2
    fi
done

if [[ -n "$DURATION" && ! "$DURATION" =~ ^[1-9][0-9]*[smhd]?$ ]]; then
    echo "NBFM_DURATION must be a value timeout(1) accepts, e.g. 300, 15m, 2h." >&2
    exit 2
fi

REPLAY=""
if [[ -n "$RAW_FILE" ]]; then
    [[ -f "$RAW_FILE" ]] || { echo "No such raw capture: $RAW_FILE" >&2; exit 2; }
    REPLAY="raw"
elif [[ -n "$IQ_FILE" ]]; then
    [[ -f "$IQ_FILE" ]] || { echo "No such IQ file: $IQ_FILE" >&2; exit 2; }
    REPLAY="iq"
fi

if [[ -z "$REPLAY" ]]; then
    [[ -n "$FREQUENCY" ]] || FREQUENCY="$(profile_frequency "$PROFILE")"
    if [[ -z "$FREQUENCY" ]]; then
        echo "Unknown profile '$PROFILE'; set NBFM_FREQUENCY_HZ or pick one of:" >&2
        list_profiles >&2
        exit 2
    fi
fi

require_commands python3
verify_op25_installed
if [[ -z "$REPLAY" ]]; then
    check_sdr_services
    check_busy_processes
    lock_device "$DEVICE"
fi

RUN_ID="$(date -u +%Y%m%d-%H%M%S)"
RUN_DIR="$ROOT/results/$RUN_ID-$MODE-${REPLAY:-$PROFILE}"
CONFIG="$RUN_DIR/op25.json"
LOG="$RUN_DIR/op25.log"
LEVELS="$RUN_DIR/audio-levels.tsv"
WAV="$RUN_DIR/gated-audio.wav"
RAW="$RUN_DIR/discriminator.raw"
META="$RUN_DIR/run-metadata.txt"
READY="$RUN_DIR/monitor.ready"
mkdir -p "$RUN_DIR"

render=(--template "$ROOT/template-nbfm.json" --output "$CONFIG"
        --mode "$MODE" --device "$DEVICE" --gain "$GAIN" --ppm "$PPM"
        --deviation "$DEVIATION" --squelch-db "$SQUELCH_DB" --hang-ms "$HANG_MS"
        --squelch-ref "$SQUELCH_REF" --audio "$AUDIO"
        --audio-port "$AUDIO_PORT" --playback-port "$PLAYBACK_PORT")
if [[ "$REPLAY" == "raw" ]]; then
    render+=(--raw-file "$RAW_FILE" --label "replay $(basename "$RAW_FILE")")
elif [[ "$REPLAY" == "iq" ]]; then
    render+=(--iq-file "$IQ_FILE" --label "replay $(basename "$IQ_FILE")")
else
    render+=(--frequency-hz "$FREQUENCY" --label "$(profile_label "$PROFILE")")
fi
[[ "$RAW_OUTPUT" == "on" ]] && render+=(--raw-output "$RAW")
python3 "$ROOT/render-config.py" "${render[@]}"

{
    echo "run_id=$RUN_ID"
    echo "mode=$MODE"
    echo "profile=${REPLAY:-$PROFILE}"
    echo "label=$(profile_label "$PROFILE")"
    echo "frequency_hz=${FREQUENCY:-replay}"
    echo "replay=${RAW_FILE:-${IQ_FILE:-none}}"
    echo "device=$DEVICE"
    echo "gain=$GAIN"
    echo "ppm=$PPM"
    echo "deviation_hz=$DEVIATION"
    echo "squelch_db=$SQUELCH_DB"
    echo "hang_ms=$HANG_MS"
    echo "squelch_ref=$SQUELCH_REF"
    echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "host=$(hostname)"
    echo "kernel=$(uname -r)"
    echo "op25_commit=$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
} > "$META"

echo
echo "NBFM squelch field test"
echo "Mode:      $MODE"
if [[ -n "$REPLAY" ]]; then
    echo "Source:    replay ${RAW_FILE:-$IQ_FILE}"
else
    echo "Channel:   $(profile_label "$PROFILE") ($FREQUENCY Hz, gain $GAIN, ppm $PPM)"
fi
[[ "$MODE" != "power" ]] && echo "Squelch:   open at $SQUELCH_DB dB quieting, hang $HANG_MS ms"
echo "Results:   $RUN_DIR"
echo "UI:        http://127.0.0.1:8080  (tunnel: ssh -L 8080:127.0.0.1:8080 user@host)"
if [[ -n "$DURATION" ]]; then
    echo "Duration:  $DURATION, then a summary (Ctrl+C stops early)"
else
    echo "Press Ctrl+C to stop and print the summary."
fi
echo

MONITOR_PID=""
cleanup() {
    if [[ -n "$MONITOR_PID" ]] && kill -0 "$MONITOR_PID" 2>/dev/null; then
        kill -TERM "$MONITOR_PID" 2>/dev/null || true
        wait "$MONITOR_PID" 2>/dev/null || true
    fi
    rm -f "$READY"
}
trap cleanup EXIT

monitor=(--listen-host 127.0.0.1 --listen-port "$AUDIO_PORT"
         --level-log "$LEVELS" --ready-file "$READY" --meter "$METER")
[[ "$RECORD" == "on" ]] && monitor+=(--wav "$WAV")
[[ "$AUDIO" == "on" ]] && monitor+=(--forward-host 127.0.0.1 --forward-port "$PLAYBACK_PORT")
python3 "$ROOT/audio-monitor.py" "${monitor[@]}" &
MONITOR_PID=$!

# wait for the socket to be bound so no early PCM is lost
for _ in $(seq 1 100); do
    [[ -f "$READY" ]] && break
    if ! kill -0 "$MONITOR_PID" 2>/dev/null; then
        echo "Audio monitor exited before op25 started." >&2
        exit 1
    fi
    sleep 0.05
done
if [[ ! -f "$READY" ]]; then
    echo "Audio monitor never bound UDP $AUDIO_PORT." >&2
    exit 1
fi

cd "$APPS_DIR"
op25=(python3 ./multi_rx.py -c "$CONFIG" -v "$VERBOSITY")
[[ -n "$DURATION" ]] && op25=(timeout --foreground --signal=INT --kill-after=10s
                              "$DURATION" "${op25[@]}")
set +e
"${op25[@]}" 2> >(tee -a "$LOG" >&2)
status=$?
set -e
# a bounded run ending on its own timer is a normal finish
if [[ -n "$DURATION" && ( "$status" == "124" || "$status" == "130" ) ]]; then
    status=0
fi

echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$META"
echo "op25_exit=$status" >> "$META"
cleanup
trap - EXIT

echo
python3 "$ROOT/summarize-run.py" "$RUN_DIR" || true
exit "$status"
