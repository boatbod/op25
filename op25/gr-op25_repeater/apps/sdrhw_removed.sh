#!/bin/bash
#
# This script gratuitously kills all rx.py and multi_rx.py processes
# It is intended to be invoked by a UDEV rule when a SDR device disconnects
#
LOG=/var/log/$(basename $0 | sed 's/[.]sh$/.log/')
echo "$(date): $(basename $0): killing op25, cmd args: $@" >> ${LOG}
kill $(pgrep -f rx.py)
