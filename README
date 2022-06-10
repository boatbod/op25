This is the boatbod fork of op25.  

Capabilities are broadly categorized into two lists - those supported by the legacy "rx.py" version
of the app and those by the newer "multi_rx.py" version.  I recommend using multi_rx where at all
possible as this is the focus of future development.

rx.py capabilities
------------------
P25 Conventional (single frequency)
P25 Trunking Phase 1, Phase 2 and TDMA Control Channel
P25 Phase 2 tone synthesis
Single SDR (dongle) tuning regardless of bandwidth
TGID Blacklist, Whitelist with dynamic reloading
TGID Priority with mid-call preemption
Multi-system scanning (switches between multiple systems sequentially)
TGID text tagging and metadata upload to Icecast server for streaming
Dynamically controllable real-time plots: FFT, Constellation, Symbol, Datascope, Mixer, Tuning
Dynamically controllable log level
Curses or HTTP based terminal
Demodulator symbol capture and replay
Voice Encryption detection and skipping (configurable behavior)
Automatic fine tune tracking using Frequency Locked Loop (FLL).

multi_rx.py capabilities
------------------------
P25 Conventional (multiple frequencies)
P25 Trunking Phase 1, Phase 2 and TDMA Control Channel
P25 Phase 2 tone synthesis
Motorola Smartzone Trunking (requires two dongles)
Motorola Connect+ TRBO DMR Trunking (experimental, requires two dongles)
DMR BS Mode (non-trunked)
NBFM analog (conventional or Smartzone trunked)
Multi-system/multi-channel concurrent operation (full time, not sequential)
Single, Multiple and Shared SDR devices (e.g. wideband devices such as Airspy etc)
TGID Blacklist, Whitelist with dynamic reloading
TGID Priority with mid-call preemption
TGID text tagging and metadata upload to Icecast server for streaming
RID text tagging
Dynamically controllable real-time plots: FFT, Constellation, Symbol, Datascope, Mixer, Tuning
Dynamically controllable log level
Curses or HTTP based terminal
JSON based configuration
DSD .wav and .iq file replay
Dynamic demodulator symbol capture and replay (commanded through terminal)
Voice Encryption detection and skipping (configurable behavior)
Automatic fine tune tracking using Frequency Locked Loop (FLL)

Roadmap (under development)
---------------------------
New HTTP GUI
Logging to GUI
Dynamic configuration

- * - * - * - * - * - * - * - * - * -

History
-------
Forked from git://git.osmocom.org/op25 "max" branch on 9/10/2017
Up to date with osmocom "max" branch as of 3/3/2018
Note: as of 2019, codebase has diverged too far to continue syncing with osmocom

Many changes:
- new DQPSK demodulator chain with automatic fine tuning & tracking
- udp python audio server sockaudio.py and remote player audio.py
- wireshark fixes (experimental)
- ability to configure NAC 0x000 in trunk.tsv and have system use first NAC decoded
- integrated N8UR logging changes to trunking.py
- ability to adjust fine tuning in real time (,./<> keys in terminal) 
- ability to dynamically resize the curses terminal
- ability to dunamically turn plots on and off from the terminal (keys 1-5)
- new 'mixer' and 'fll' output plots (terminal keys 5 & 6)
- reworked trunking hold/release logic that improves Phase 1 audio on some systems
- decoding and logging of encryption sync info ("ESS") at log level 10 (-v 10)
- ability to silence the playing of encrypted audio
- encrypted audio flag shown on terminal screen
- source radio id displayed on terminal screen (if available)
- supports IP addresses or host names for --wireshark-host (-W) parameter
- decode and pass voice channel sourced trunk signaling up to trunking module
- added optional trunk group priority parameter to end of tgid-tags.tsv file
- added ability to handle ranges of tgid in blacklist/whitelist files
- support for streaming metadata updates (both rx.py and multi_rx.py)
- support for MotoTrbo Connect+ and Motorola Smartnet/Smartzone trunking (multi_rx.py)
- enhanced multi_rx.py now supports P25, DMR, Smartnet trunking, terminal and built-in audio player

New command line options:
  --fine-tune      : sub-ppm tuning adjustment
  --wireshark-port : facilitates multiple instances of rx.py
  --udp-player     : enable built-in audio player
  --nocrypt        : silence encrypted audio

NOTE 1: using the --nocrypt command line option will silence encrypted audio, but the trunking logic will cause the application to remain on the active tgid until the transmission ends.  It is generally preferable to blacklist tgids that are always encrypted rather than simply silence them.  Use the --nocrypt functionality to silence occasional encrypted transmissions on mixed use tgids.

NOTE 2: trunk id to tag mapping file (tgid-tags.tsv) can contain an optional 3rd numeric parameter to be used as the trunk priority when simultaneous calls are present on the system being monitored.  Default priority is 3 if not explicitly specified.  Lower numeric value = higher priority.  Data columns are separated by a single TAB character.

e.g.
11501	TB FIRE DISP	2
11502	TB FIRE TAC2	3
11503	TB FIRE TAC3	3
11504	TB FIRE TAC4	4
11505	TB FIRE TAC5	3 
