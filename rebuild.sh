#!/bin/sh

usage()
{
  echo "Usage: $0 [-d|-r]"
  echo "  -d   Debug build"
  echo "  -r   Release build (default)"
  exit 2
}

BUILD_TYPE=""
while getopts 'dr?h' c
do
  case $c in
    d) BUILD_TYPE="-DCMAKE_BUILD_TYPE=Debug" ;;
    r) BUILD_TYPE="-DCMAKE_BUILD_TYPE=Release" ;;
    h|?) usage ;;
  esac
done

git pull
cd build
rm -rf *
cmake ../ $BUILD_TYPE 2>&1 | tee cmake.log
make                  2>&1 | tee make.log
sudo make install     2>&1 | tee install.log
sudo ldconfig
