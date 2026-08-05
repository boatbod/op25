#!/bin/bash
#
# One-shot deployment of the W1JPI op25 fork (PA3FWM NBFM noise squelch)
# on a Ubuntu 22.04 / 24.04 host.  Installs GNU Radio 3.10 and build
# dependencies, builds and installs op25, then runs the squelch self-tests.
#
#     sudo ./deploy.sh
#
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "error: run as root (sudo ./deploy.sh)" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
APPS="$REPO/op25/gr-op25_repeater/apps"
if [ ! -d "$REPO/op25/gr-op25_repeater" ]; then
    echo "error: op25 tree not found above $SCRIPT_DIR" >&2
    exit 1
fi

GR_VER=$(apt list gnuradio 2>/dev/null | grep -m 1 gnuradio | cut -d' ' -f2 | cut -d'.' -f1,2 || true)
echo "== apt offers GNURadio ${GR_VER:-unknown}"
if [ "$GR_VER" != "3.10" ]; then
    echo "error: this branch needs GNURadio 3.10 (Ubuntu 22.04/24.04)" >&2
    exit 1
fi

echo "== enabling source repositories (for apt build-dep)"
if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then
    # Ubuntu 24.04+ deb822 format
    sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources
else
    sed -i -- 's/^# *deb-src/deb-src/' /etc/apt/sources.list
fi

echo "== installing dependencies (this is the slow part)"
apt-get update -qq
apt-get build-dep -y -qq gnuradio
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    gnuradio gnuradio-dev gr-osmosdr librtlsdr-dev libuhd-dev \
    libhackrf-dev liborc-dev cmake git build-essential pkg-config \
    python3-pybind11 python3-numpy python3-waitress python3-requests \
    libsndfile1-dev libspdlog-dev rtl-sdr alsa-utils ffmpeg

echo "/usr/bin/python3" > "$APPS/op25_python"

if [ ! -f /etc/modprobe.d/blacklist-rtl.conf ]; then
    echo "== blacklisting rtl28xx DVB kernel drivers"
    install -m 0644 "$REPO/blacklist-rtl.conf" /etc/modprobe.d/
    rmmod dvb_usb_rtl28xxu 2>/dev/null || true
fi

# CMake 4 removed the OLD behavior of CMP0026 and CMP0045, which op25
# still requests explicitly, so CMAKE_POLICY_VERSION_MINIMUM alone cannot
# carry the build.  Harmless on the 3.2x cmake in 22.04/24.04.
if grep -q 'cmake_policy(SET CMP0026 OLD)' "$REPO/CMakeLists.txt" 2>/dev/null; then
    echo "== applying CMake 4 policy compatibility"
    sed -i \
        -e 's/^cmake_policy(SET CMP0026 OLD)$/cmake_policy(SET CMP0026 NEW)/' \
        -e 's/^cmake_policy(SET CMP0045 OLD)$/cmake_policy(SET CMP0045 NEW)/' \
        "$REPO/CMakeLists.txt"
fi

CMAKE_EXTRA=()
if [[ "$(cmake --version)" =~ ^cmake\ version\ ([0-9]+)\.([0-9]+) ]] &&
   (( BASH_REMATCH[1] > 3 || (BASH_REMATCH[1] == 3 && BASH_REMATCH[2] >= 24) )); then
    CMAKE_EXTRA+=(--fresh)
fi

echo "== building op25"
cd "$REPO"
rm -rf build
mkdir build
cmake "${CMAKE_EXTRA[@]}" -S "$REPO" -B "$REPO/build" \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
      > build/cmake.log 2>&1
cmake --build "$REPO/build" --parallel "$(nproc)" > build/make.log 2>&1
cmake --install "$REPO/build" > build/install.log 2>&1
ldconfig

if ! python3 -c 'import gnuradio.op25, gnuradio.op25_repeater' >/dev/null 2>&1; then
    echo "error: op25 built but its GNU Radio Python modules are not importable." >&2
    echo "Check $REPO/build/install.log before running the receiver." >&2
    exit 1
fi

echo "== running squelch self-tests"
cd "$APPS"
python3 squelch_core_test.py
python3 squelch_gr_test.py

cat <<'EOF'

== deploy complete ==

Next steps (from the field-test directory, as a normal user):
  1. check the dongle:      ./run-field-test.sh --check noaa
  2. listen:                ./run-field-test.sh noise noaa
  3. see the modes/targets: ./run-field-test.sh --list

Do NOT use `rtl_test -t` to check the dongle: it is an E4000-only tuner
benchmark and prints "No E4000 tuner found" on R820T/R820T2 hardware,
which looks like a failure but is not one.  `--check` does a tuned read.

If the dongle reports usb_claim_interface error -6, the DVB kernel driver
owns it; the blacklist is installed, so reboot once.

See field-test/README.md for the test plan and tuning guidance.
EOF
