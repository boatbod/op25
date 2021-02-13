#!/bin/sh
git pull
cd build
rm -rf *
cmake ../         2>&1 | tee cmake.log
make              2>&1 | tee make.log
sudo make install 2>&1 | tee install.log
sudo ldconfig
