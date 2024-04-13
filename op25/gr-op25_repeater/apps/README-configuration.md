The following steps need to be taken by users wishing to configure OP25 to monitor a P25 Trunked system.  More complex setups are supported, but this is the base starting point.

All instructions below assume you are in the `apps` directory.
```
cd ~/op25/op25/gr-op25_repeater/apps
```

1. Set up the control channel frequencies in `trunk.tsv`:
```
./setTrunkFreq.sh 773.84375
```

If you need multiple frequencies because your control channel moves around, place them in a comma separated list as follows (with no whitespace)
```
./setTrunkFreq.sh 773.84375,774.19375
```

2. Use the startup script `op25.sh` to run the application (`rx.py`). This can be customized, but the defaults should be appropriate for most stand-alone systems.  If you need streaming or multiple instances you'll need to dig more deeply into the command line options for port numbers.
```
./op25.sh
```

3. Once the application starts it will attempt to lock the control channel and make small tuning adjustments automatically. If you have an old sdr hardware that does not have a temp-compensated crytal oscillator (TXCO) you may need to adjust the ppm correction using the `-q` parameter in the `op25.sh` startup script.

