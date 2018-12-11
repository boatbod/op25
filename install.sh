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
sudo apt-get install gnuradio gnuradio-dev gr-osmosdr librtlsdr-dev libuhd-dev  libhackrf-dev libitpp-dev libpcap-dev cmake git swig build-essential pkg-config doxygen python-numpy python-waitress python-requests

mkdir build
cd build
cmake ../
make
sudo make install
sudo ldconfig

echo ====== 
echo ====== NOTICE 
echo ====== 
echo ====== The gnuplot package is not installed by default here,
echo ====== as its installation requires numerous prerequisite packages
echo ====== that you may not want to install.
echo ====== 
echo ====== In order to do plotting in rx.py using the \-P option
echo ====== you must install gnuplot, e.g., manually as follows:
echo ====== 
echo ====== sudo apt-get install gnuplot-x11
echo ====== 
