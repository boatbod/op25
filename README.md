# This is the boatbod fork of op25. 
# V2 Development Repo - INCOMPLETE AND NOT GUARANTEED TO WORK!

## `rx.py`

Status : RETIRED
Please use either "gr310" (gnuradio-3.10 or later) or "gr38" (gnuradio-3.8 or earlier) branches

## `multi_rx.py`

P25 Wide Area Trunking : aggregate traffic across multiple sites into multiple destination streams

  P25-System
     |  |------> RFSS/STID (site 1) -----> RxCh-1.1 thru RxCh-1.n
     |  |------> RFSS/STID (site 2) -----> RxCh-2.1 thru RxCh-2.n
     |  |
     |  |------> RFSS/STID (site x) -----> RxCh-x.1 thru RxCh-x.n
     |
     |
     |---------> Audio Stream 1 (whitelist 1, destination 1)
     |---------> Audio Stream 2 (whitelist 2, destination 2)
     |
     |---------> Audio Stream Z (whitelist z, destination z)

1. A minimum of one receiver per rfss/site is needed in order to monitor that site's control
   channel. It can be either a single physical narrowband RTL device (1Mhz minimum  sample width)
   or a logic device sharing the spectrum of a wideband SDR e.g. Airspy, HydraSDR, SDRPlay.
   Receiver will be available for decoding voice traffic carried by that site.

2. You need at least as many logical receivers as required simultaneous audio streams.
   If site traffic volume is low, you can define more audio streams than receivers as long
   as you accept there may be times when no receiver is available to meet simultaneous
   streaming needs.

3. Physically distant sites generally best monitored with a directional antenna in order to
   achieve acceptable decode quality.  This is where it pays to utilize wide-band sdr hardware
   and dedicate one 6Mhz or 10Mhz SDR device attached to a directional antenna pointed at that
   site, then define multiple logical receiver channels for simultaneous voice decode.
   Additional logical receiver channels can be defined for receiving stronger local sites,
   sometimes with better results than obtained with an omni, due to reduced multipath distortion.

Getting Started
1. The simplest working configuration requires a single RTL device running with 1Mhz sample size.
   Use the file "p25_single_rtl_example.json" as a starting point.

   To get up and running you just need to enter your local control channel frequency in the
   "control_channel_list": parameter found in the trunking "sites" section.  

   Run the app:
                ./multi_rx.py -v 1 -c p25_single_rtl_example.json 2> stderr.2

   Open a web browser:
                http://127.0.0.1:8080

2. For a much more complex example of a four-site / five-stream system used to monitor four
   counties in the Maryland FiRST statewide system, see the file statewide_trunking_example.json

   The hardware runs on an old Intel NUC7 brick with an i5 four core processor.  SDRs are a pair of
   HydraSDR devices running at 10Mhz, each with their own directional antennas, one pointed north
   and the other south.

Notes
1. Limiting factors are going to be usb bandwidth, cpu abilities, and available memory.  While it
   will be more than feasible to run a small one or two dongle setup on an old RPi, don't expect
   miracles!  If you want to capture lots of traffic, be prepared to invest in a good cpu and
   one or more higher-end sdr devices.

2. Presently this experimental 'dev2' codebase works only for P25 Trunking.  I do intend to make
   P25 Conventional functional once again, but Smartzone, DMR, transmit, and rx.py all require
   you to drop back to the 'gr310' branch.

3. There are bugs and functionality omissions which I'm working on.  The only supported terminal is
   the new web interface.  While code for the old curses terminal still exists in the repo, there
   have been api changes so it simply won't operate and will probably just outright crash.

   Known issues: 
   - Scan/Hold/Lockout/GoTo and Preset buttons aren't yet working.
   - Subscriber affiliation tracking is functional, but it needs reworking and optimizing

