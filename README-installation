How to Install OP25
----------------------------------------------------------------------
These high level instructions will lead you through installing op25
on Debian based Linux systems such as Ubuntu, Linux Mint and similar.

Note 1: op25 is currently tested against gnuradio-3.7/python2 with Ubuntu 16.04
and gnuradio-3.8/python3 with Ubuntu 20.04. Build environment automatically figures
out which version of gnuradio you have and therefore which version of python to use. 

Note 2: versions of cmake later than 3.10.3 have been known to cause dependency
issues while building the swig libraries on pyhton2. At the current time if you
experience build difficulties of this sort, try dropping back to cmake-3.10.3,
delete the contents of ~/op25/build/ and start over.

Note 3: There is also a ./rebuild.sh script that will (optionally) update & rebuild op25, local changes must be committed or reverted for update to happen.


1. Install op25
---------------
sudo apt-get install git
cd ~
git clone https://github.com/boatbod/op25
cd op25
./install.sh 

2. Configure op25
-----------------
cd ~/op25/op25/gr-op25_repeater/apps
<<<all configuration takes place in the 'apps' directory>>>

See "~/op25/op25/gr-op25_repeater/apps/README-configuration" for more information.

3. Run op25
-----------
cd ~/op25/op25/gr-op25_repeater/apps
./op25.sh
