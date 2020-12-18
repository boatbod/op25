#! /bin/sh

# op25 install script for debian based systems
# including ubuntu 14/16 and raspbian

if [ ! -d op25/gr-op25 ]; then
	echo ====== error, op25 top level directories not found
	echo ====== you must change to the op25 top level directory
	echo ====== before running this script
	exit
fi

echo "Updating packages list"
sudo apt-get update

GR_VER=$(apt list gnuradio 2>/dev/null | grep -m 1 gnuradio | cut -d' ' -f2 | cut -d'.' -f1,2)
if [ ${GR_VER} = "3.8" ]; then
    echo "Installing for GNURadio 3.8"
    cat gr3.8.patch | patch -N -p1 -r -
    sudo sed -i -- 's/^# *deb-src/deb-src/' /etc/apt/sources.list
    sudo apt-get build-dep gnuradio
    sudo apt-get install gnuradio gnuradio-dev gr-osmosdr librtlsdr-dev libuhd-dev  libhackrf-dev libitpp-dev libpcap-dev cmake git swig build-essential pkg-config doxygen python3-numpy python3-waitress python3-requests gnuplot-x11

    # Tell op25 to use python3
    echo "/usr/bin/python3" > op25/gr-op25_repeater/apps/op25_python

else
    echo "Installing for GNURadio 3.7"
    sudo apt-get build-dep gnuradio
    sudo apt-get install gnuradio gnuradio-dev gr-osmosdr librtlsdr-dev libuhd-dev  libhackrf-dev libitpp-dev libpcap-dev cmake git swig build-essential pkg-config doxygen python-numpy python-waitress python-requests gnuplot-x11

    # Tell op25 to use python2
    echo "/usr/bin/python" > op25/gr-op25_repeater/apps/op25_python

fi

if [ ! -f /etc/modprobe.d/blacklist-rtl.conf ]; then
	echo ====== installing blacklist-rtl.conf
	echo ====== please reboot before running op25
	sudo install -m 0644 ./blacklist-rtl.conf /etc/modprobe.d/
fi

mkdir build
cd build
cmake ../
make
sudo make install
sudo ldconfig

