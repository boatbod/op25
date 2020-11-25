#!/bin/sh
git pull
cd build
rm -rf *
cmake ../
make
sudo make install
sudo ldconfig
