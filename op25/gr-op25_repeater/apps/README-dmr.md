DMR Support
-----------
This is experimental, use at your own risk and sanity!

Protocols currently supported:
- Tier II DMR
- TRBO Connect Plus

Protocols not yet supported:
- Simplex DMR
- TRBO Capacity Plus
- Tier III Trunked DMR

Background
----------
Tier II is a non-trunked TDMA voice protocol which can be handled by configuring multi_rx.py with the static frequency of a known base station (BS) repeater.

TRBO Connect Plus is a Motorola proprietary trunking protocol which operates using a series of pre-configured frequencies each assigned a logical identifier called an LCN. Each frequency can carry two voice channels or one control channel plus one voice channel.  At any given time the control channel may move to a different LCN (frequency) so the trunking logic has to search for it.

Unlike op25's Trunked P25 decoder, DMR trunking has been designed around continuously monitoring the control channel with one "receiver" while utilizing a separate "receiver" for the active voice channel.  In practice this either means you need to use one SDR device with a wide enough sample width to receive the full spectrum of the system you wish to monitor, or use two separate SDR devices with one dedicated for voice and one dedicated for signaling. 

Configuration
-------------
The DMR decoder is part of multi_rx.py, so configuration requires the creation of a .json file based on either cfg.json or dmr_rtl_example.json.  The latter is probably more useful as a starting point since it is solely focussed on trunking using commonly available RTL sdr hardware.

In the .json file, a "channel" is considered to the the receiver as it encapsulates demodulation, framing and decoding in one logical entity.  For a TRBO Connect Plus system there will therefore be two "channel" entries and either one or two "device" entries depending on the hardware you are using.  Each channel is associated with a device by specifying the device name inside the channel definition.  SDR hardware with a high sample rate can be shared between channels, but only if tuning is disabled (tunable=false).  Tunable devices have to have a one-to-one relationship with the channel to which they are assigned.

Trunking requires configuration of the appropriate trunking module name (currently only "tk_trbo.py") and all the logical channels (LCNs) which comprise the system being monitored. Each LCN has to have the correct numeric id along with the frequency to tune and optionally the color code (CC) expected. If color code is unknown or unused, set it to 0.  Failure to map the correct LCN id to frequency will cause trunking not to work reliably.

Startup
-------
Much like op25's rx.py, multi_rx.py is best started using a shell script.
     ./multi_rx.py -v 10 -c dmr_rtl_example.json 2> stderr.2

If you want to hear audio, you will also need to start an audio server in a separate terminal window.
     ./audio.py -u 23466

Known Issues & Limitations
--------------------------
At present, tk_trbo.py does not attempt to do any blacklisting, whitelisting or priority of group addresses (tgids).  It will attempt to stay on the same tgid for the duration of the voice call + 2 seconds 'hold time' even if a second voice grant appears while the first is still active.  Up to this point, most effort has focussed on implementing protocol decode building blocks, tuning logic and mapping of LCN addresses into physical frequencies.

TODO:
- beef up trunking code and handle missing features such as whilelist/blacklist/priority
- implement a terminal so you can see what is going on without needing to run the logs at high levels of debug
- improve the FSK4 demodulator so it can be used with TDMA simplex and TRBO Capacity Plus burst transmissions.

