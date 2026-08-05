#!/bin/bash
#
# Shared RTL-SDR preflight helpers for the NBFM squelch field-test kit.
# Sourced by run-field-test.sh and capture-diagnostic.sh.
#
# Only one process can own a dongle, so every entry point checks for the
# usual suspects (ADS-B daemons, another op25, a stray rtl_* tool) and
# takes an advisory lock before touching the hardware.

# shellcheck shell=bash

FIELD_TEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$FIELD_TEST_ROOT")"
APPS_DIR="$REPO_ROOT/op25/gr-op25_repeater/apps"

# NBFM test targets.  NOAA weather radio is the best first-light check:
# a permanent carrier with real voice on it.
profile_frequency() {
    case "$1" in
        noaa|noaa1|wx)  echo 162400000 ;;
        noaa2)          echo 162425000 ;;
        noaa3)          echo 162450000 ;;
        noaa4)          echo 162475000 ;;
        noaa5)          echo 162500000 ;;
        noaa6)          echo 162525000 ;;
        noaa7)          echo 162550000 ;;
        murs1)          echo 151820000 ;;
        murs2)          echo 151880000 ;;
        murs3)          echo 151940000 ;;
        murs4)          echo 154570000 ;;
        murs5)          echo 154600000 ;;
        ham2m)          echo 146520000 ;;   # 2 m FM national simplex
        custom)         echo "${NBFM_FREQUENCY_HZ:-}" ;;
        *)              echo "" ;;
    esac
}

profile_label() {
    case "$1" in
        noaa|noaa1|wx)  echo "NOAA Weather Radio 162.400" ;;
        noaa2)          echo "NOAA Weather Radio 162.425" ;;
        noaa3)          echo "NOAA Weather Radio 162.450" ;;
        noaa4)          echo "NOAA Weather Radio 162.475" ;;
        noaa5)          echo "NOAA Weather Radio 162.500" ;;
        noaa6)          echo "NOAA Weather Radio 162.525" ;;
        noaa7)          echo "NOAA Weather Radio 162.550" ;;
        murs[1-5])      echo "MURS channel" ;;
        ham2m)          echo "2 m FM simplex 146.520" ;;
        custom)         echo "Custom frequency" ;;
        *)              echo "Unknown" ;;
    esac
}

list_profiles() {
    echo "  noaa noaa2..noaa7   NOAA weather radio (constant carrier - best first test)"
    echo "  murs1..murs5        MURS channels"
    echo "  ham2m               146.520 MHz 2 m FM simplex"
    echo "  custom              set NBFM_FREQUENCY_HZ=<hz>"
}

require_commands() {
    local missing=0 c
    for c in "$@"; do
        if ! command -v "$c" >/dev/null 2>&1; then
            echo "Missing required command: $c" >&2
            missing=1
        fi
    done
    if (( missing )); then
        echo "Run 'sudo ./deploy.sh' to install the expected tools." >&2
        return 2
    fi
}

check_sdr_services() {
    local service
    for service in dump1090-mutability dump1090-fa dump1090 readsb dump978-fa; do
        if command -v systemctl >/dev/null 2>&1 &&
           systemctl is-active --quiet "$service" 2>/dev/null; then
            echo "$service is using the RTL-SDR. Stop it first:" >&2
            echo "  sudo systemctl stop $service" >&2
            return 2
        fi
    done
}

check_busy_processes() {
    local busy
    busy="$(pgrep -af 'multi_rx\.py|rtl_(fm|sdr|power|tcp)|dump1090|readsb' || true)"
    if [[ -n "$busy" ]]; then
        echo "Another SDR process already holds the dongle:" >&2
        echo "$busy" >&2
        return 2
    fi
}

# Advisory lock; the caller keeps fd 9 open for the life of the run.
lock_device() {
    local device="$1"
    local lock="${XDG_RUNTIME_DIR:-/tmp}/op25-nbfm-field-test-rtl-${device}.lock"
    exec 9>"$lock"
    if ! flock -n 9; then
        echo "RTL-SDR device $device is locked by another field-test process." >&2
        return 2
    fi
}

# A tuned sample read: unlike `rtl_test -t`, this works on R820T/R820T2
# dongles.  `rtl_test -t` is an E4000-only tuner benchmark and reports
# "No E4000 tuner found" on current hardware, which looks like a fault
# but is not one.
check_dongle() {
    local device="$1" frequency="$2"
    require_commands rtl_sdr || return 2
    check_sdr_services || return 2
    check_busy_processes || return 2
    echo "Reading 250k samples at $frequency Hz from device $device..."
    if ! timeout --foreground --signal=INT --kill-after=5s 15s \
         rtl_sdr -d "$device" -f "$frequency" -s 1000000 -n 250000 /dev/null; then
        echo >&2
        echo "Dongle check failed. If this is 'usb_claim_interface error -6', the" >&2
        echo "DVB kernel driver owns the dongle; deploy.sh installs the blacklist," >&2
        echo "so reboot once and retry." >&2
        return 1
    fi
    echo "Dongle OK."
}

verify_op25_installed() {
    if [[ ! -f "$APPS_DIR/multi_rx.py" ]]; then
        echo "multi_rx.py not found under $APPS_DIR" >&2
        echo "Run 'sudo ./deploy.sh' first." >&2
        return 2
    fi
    if ! python3 -c 'import gnuradio.op25, gnuradio.op25_repeater' >/dev/null 2>&1; then
        echo "OP25 is present but its GNU Radio Python modules are not importable." >&2
        echo "The build did not install; re-run 'sudo ./deploy.sh'." >&2
        return 2
    fi
}
