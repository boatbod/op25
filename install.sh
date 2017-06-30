#! /bin/sh

# op25 install script for debian based systems
# including ubuntu 14/16 and raspbian

if [ ! -d op25/gr-op25 ]; then
	echo ====== error, op25 top level directories not found
	echo ====== you must change to the op25 top level directory
	echo ====== before running this script
	exit
fi

sudo apt-get update
sudo apt-get build-dep gnuradio
sudo apt-get install gnuradio gnuradio-dev gr-osmosdr librtlsdr-dev libuhd-dev  libhackrf-dev libitpp-dev libpcap-dev

mkdir build
cd build
cmake ../
make
sudo make install
sudo ldconfig
