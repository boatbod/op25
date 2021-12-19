#!/bin/bash
#
# This script gratuitously kills all rx.py and multi_rx.py processes
# It is intended to be invoked by a UDEV rule when a SDR device disconnects
#
kill $(pgrep -f rx.py)
