#!/usr/bin/bash

#
# Script to update librtlsdr0 driver to the latest version
# for compatibility with RTL-SDR Blog V4 hardware
#

# Script has no error checking, so if it blows up it may not
# fail gracefully and may leave your system in an unknown state
# Use at your own risk!

# First install required support tools
sudo apt update
sudo apt -y install libusb-1.0-0-dev debhelper
# Get latest RTL-SDR driver source
mkdir update-rtlsdr
cd update-rtlsdr
git clone https://github.com/rtlsdrblog/rtl-sdr-blog
# Build the packages
cd rtl-sdr-blog
libtoolize
autoreconf -i
dpkg-buildpackage -b --no-sign
cd ..
# Install the packages
sudo dpkg -i librtlsdr0_*.deb
sudo dpkg -i librtlsdr-dev_*.deb
sudo dpkg -i rtl-sdr_*.deb
cd ..
# Clean up
rm -rf update-rtlsdr
