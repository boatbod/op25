The script "update-rtlsdr.sh" can be used to update the librtlsdr0 driver
used by generic rtl-sdr dongles, including newer RTL-SDR Blog V4 hardware
which may not be supported by the driver installed from your default
package repository.

Building the driver using this script has proven to be somewhat hit-or-miss,
so I suggest you try running the default version first, and if it works, keep
using it. Don't say I didn't warn you if things go wrong and you end up with
no driver installed!

If you are really sure you want to proceed, run this command:
./update-rtlsdr.sh
