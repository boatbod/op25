#! /bin/sh

# op25 install script for debian based systems
# including ubuntu 14/16 and raspbian

if [ ! -d op25/gr-op25 ]; then
	echo ====== error, op25 top level directories not found
	echo ====== you must change to the op25 top level directory
	echo ====== before running this script
	exit
fi

#sudo apt-get update

GR_VER=$(dpkg-query -f '${Version}\n' --show gnuradio | sed  s/\.[0123456789]*\.[^.]*$//g)
if [ ${GR_VER} = "3.8" ]; then
    echo "Installing for GNURadio 3.8"
    cat gr3.8.patch | patch -N -p1 -r -
    sudo sed -i -- 's/^# *deb-src/deb-src/' /etc/apt/sources.list
    sudo apt-get build-dep gnuradio
    sudo apt-get install gnuradio gnuradio-dev gr-osmosdr librtlsdr-dev libuhd-dev  libhackrf-dev libitpp-dev libpcap-dev cmake git swig build-essential pkg-config doxygen python3-numpy python3-waitress python3-requests gnuplot-x11

    if [ ! -x /usr/bin/python ]; then
	    echo ====== installing python-is-python3
	    sudo apt-get install python-is-python3
    fi
else
    echo "Installing for GNURadio 3.7"
    sudo apt-get build-dep gnuradio
    sudo apt-get install gnuradio gnuradio-dev gr-osmosdr librtlsdr-dev libuhd-dev  libhackrf-dev libitpp-dev libpcap-dev cmake git swig build-essential pkg-config doxygen python-numpy python-waitress python-requests gnuplot-x11

fi

if [ ! -f /etc/modprobe.d/blacklist-rtl.conf ]; then
	echo ====== installing blacklist-rtl.conf
	echo ====== please reboot before running op25
	sudo install -m 0644 ./blacklist-rtl.conf /etc/modprobe.d/
fi

exit

mkdir build
cd build
cmake ../
make
sudo make install
sudo ldconfig

