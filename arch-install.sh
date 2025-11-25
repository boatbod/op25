#!/bin/sh
# Arch Linux Boatbod OP25 Installer

# Check for presence of yay and install if needed
sudo pacman -S --needed base-devel git
if ! [ -x "$(command -v yay)" ]; then
	(git clone https://aur.archlinux.org/yay yay_tmp; cd yay_tmp; makepkg -si; cd ..; rm -rf yay_tmp)
fi

#
# Install required packages
#
sudo pacman -S --needed --noconfirm gnuradio gnuradio-osmosdr rtl-sdr libuhd cmake cppunit doxygen boost orc base-devel clang pkgconf python-thrift pybind11 python-numpy python-waitress python-setuptools gnuplot libsndfile spdlog hackrf
yay -S --noconfirm castxml python-pygccxml

#
# Check and fix missing libthrift-0.17.0.so (currently required for gnuradio modtool)
#
if ! [ -f /usr/lib/libthrift-0.17.0.so ]; then
	sudo ln /usr/lib/libthrift-0.18.0.so /usr/lib/libthrift-0.17.0.so
fi

#
# Build the python/c++ bindings
#
./build_bindings.sh

#
# Build op25
#
mkdir build
cd build
cmake -DCMAKE_INSTALL_PREFIX="/usr" ../
make
sudo make install
