#! /bin/sh

# op25 install script for debian based systems
# including ubuntu 14/16 and raspbian

if [ ! -d op25/gr-op25 ]; then
	echo ====== error, op25 top level directories not found
	echo ====== you must change to the op25 top level directory
	echo ====== before running this script
	exit
fi

# Initialize variables
FORCE=false

# Parse command-line arguments
while getopts ":f" opt; do
  case $opt in
    f)
      FORCE=true
      ;;
    *)
      ;;
  esac
done

GR_VER=$(apt list gnuradio 2>/dev/null | grep -m 1 gnuradio | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Identified GNURadio version ${GR_VER}"
if [ ${GR_VER} = "3.10" ]; then
    echo "Installing for GNURadio 3.10"
    sudo sed -i -- 's/^# *deb-src/deb-src/' /etc/apt/sources.list
    echo "Updating packages list"
    sudo apt-get update
    echo "Installing dependencies"
    sudo apt-get build-dep gnuradio $([ "$FORCE" = true ] && echo "-y")
    sudo apt-get install gnuradio gnuradio-dev gr-osmosdr librtlsdr-dev libuhd-dev libhackrf-dev libitpp-dev libpcap-dev liborc-dev cmake git build-essential pkg-config doxygen clang-format python3-pybind11 python3-numpy python3-waitress python3-requests gnuplot-x11 libsndfile1-dev libspdlog-dev $([ "$FORCE" = true ] && echo "-y")

    # Tell op25 to use python3
    echo "/usr/bin/python3" > op25/gr-op25_repeater/apps/op25_python
else
    echo "Installing for GNURadio ${GR_VER} is not supported by this version of op25"
    echo "Please use git branch \"gr38\" for GNURadio-3.8 or earlier"
    exit 1
fi

# blacklist rtl dtv drivers
if [ ! -f /etc/modprobe.d/blacklist-rtl.conf ]; then
	echo ====== installing blacklist-rtl.conf
	echo ====== please reboot before running op25
	sudo install -m 0644 ./blacklist-rtl.conf /etc/modprobe.d/
fi

# fix borked airspy udev rule to allow used of airspy device when running headless
if [ -f /lib/udev/rules.d/60-libairspy0.rules ]; then
    echo ====== fixing libairspy0 udev rule
	echo ====== please reboot before running op25
    sudo sed -i 's^TAG+="uaccess"^MODE="660", GROUP="plugdev"^g' /lib/udev/rules.d/60-libairspy0.rules
fi

rm -rf build
mkdir build
cd build
cmake ../         2>&1 | tee cmake.log
make              2>&1 | tee make.log
sudo make install 2>&1 | tee install.log
sudo ldconfig

