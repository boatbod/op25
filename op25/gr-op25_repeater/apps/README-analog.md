`multi_rx.py` now supports a simple narrowband fm analog demodulator.  It piggybacks alongside the regular digital voice channel object defined in `cfg.json` and can either be controled by trunking (e.g. for SmartNet/SmartZone monitoring) or turned on and used as a stand-alone nbfm receiver.

```
    "channels": [
        {
            "name": "voice channel", 
            "device": "rtl1",
            "destination": "udp://127.0.0.1:23456", 
            "frequency": 859000000,
            "enable_analog": "auto",
            "nbfm_deviation": 4000,
            "nbfm_squelch": -60,
            "demod_type": "fsk4", 
            "filter_type": "widepulse", 
            "excess_bw": 0.2, 
            "if_rate": 24000, 
            "symbol_rate": 4800,
            "plot": ""
        }
```

Parameters of relevance to the NBFM module are:
```
    enable_analog: "off","on" or "auto" - auto is the default for use with trunking
    nbfm_deviation: 4000                - deviation in Hz; will affect output volume
    nbfm_squelch:   -60                 - approx avg power (in dB) required to open squelch
```

