# Motorola Type II SmartNet/SmartZone Support

This is experimental, use at your own risk and sanity!

## Configuration

The SmartNet decoder is part of `multi_rx.py`, so configuration requires the creation of a .json file based on `smartnet_example.json`.  The latter is probably more useful as a starting point since it is solely focused on trunking using commonly available RTL sdr hardware.

In the .json file, a "channel" is considered to be the receiver as it encapsulates demodulation, framing, and decoding in one logical entity.  For a SmartNet system there will be a minimum of two "channel" entries and either one or two "device" entries depending on the hardware you are using.  Each channel is associated with a device by specifying the device name inside the channel definition.  SDR hardware with a high sample rate can be shared between channels, but only if tuning is disabled (tunable=false).  Tunable devices have to have a one-to-one relationship with the channel to which they are assigned.

Trunking requires configuration of the appropriate trunking module name (`tk_smartnet.py`), the control channel list, and bandplan. Valid values for the `bandplan` parameter are:  `800_reband`, `800_standard`, `800_splinter`, `900`, and `OBT`.  VHF/UHF trunking is considered OBT (other-band-trunking) and requires additional configuration of the `bp_` parameters (see "Bandplan" section below).

## Blacklist/whitelist

Control over which TGIDs are candidates for monitoring is via the `blacklist` and `whitelist` parameters associated with each of the voice channel(s).  These parameters take the name of a file which contains TGIDs in the same format as used by the rx.py blacklist/whitelist: either a single numeric TGID per line, or a pair of TGIDs separated by a <tab> character, denoting the start and end of a range.  Each voice channel would normally have its own non-overlapping blacklist/whitelist definitions to avoid the same audio being played simultaneously.

## Audio Player

`multi_rx.py` has support for enabling a built-in audio player. See the "audio" section of the `smartnet-example.json` file for configuration parameter syntax.  Note that the `instance_name` must be specified for the player to be enabled.  Leaving this parameter absent or blank will cause the player to be disabled.  Consistent configuration of the `udp_port` parameter is required between the audio player and the channel destinations.  Default port is 23456.

## Bandplan

Motorola Type II SmartNet/SmartZone systems send a channel identifier command in their group voice grant messaging to identify the actual voice frequency being used.  Translation of this numeric ID to an actual frequency depends on the setting of the `bandplan` trunking parameter.

### Standard configuration

In the USA, most legacy 800 MHz systems should be configured with `bandplan` set to `800_reband` with no further information necessary.

### Supported bandplans

Several standard bandplans (and `bandplan` settings) exist and are supported:

- 800 MHz
    - Standard (`800_standard`)
    - Splinter (`800_splinter`)
    - Rebanded (`800_reband`)
- 900 MHz (`900`)
- VHF/UHF Other Band Trunking (`OBT`)

### Other Band Trunking (OBT)

#### Required configuration

VHF and UHF systems are considered "Other Band Trunking" (OBT), and require `bandplan` set to `OBT` in conjunction with additional configuration in the nine associated `bp_` parameters:

- Base frequency
    - `bp_base`
    - `bp_mid`
    - `bp_high`
- Channel spacing
    - `bp_base_spacing`
    - `bp_mid_spacing`
    - `bp_high_spacing`
- Channel number offset
    - `bp_base_offset`
    - `bp_mid_offset`
    - `bp_high_offset`

These can usually be found on the RadioReference wiki as "Custom Frequency Tables" or "Custom Band Plan".

#### Optional configuration

OBT systems may optionally have the nine `bp_tx_` parameters set as well; if not set they default to values based on the `bp_` parameters.  These behave identically to the `bp_` parameters but are used to translate subscriber transmit (uplink) numeric IDs to actual frequencies.

This is not required for simply listening to a system; the functionality is added for more involved debugging of outbound service words (OSWs) as may be necessary for a system admin.  Transmit frequencies are logged to `stderr` along with detailed OSW meanings when verbosity is set to at least 11, or full raw OSWs can be logged with a verbosity of at least 13.

## Examples

### 800 MHz system, rebanded bandplan

#### [Anne Arundel County](https://www.radioreference.com/db/sid/187)

```
    "control_channel_list": "854.3375,854.4125,854.8125,855.1625",
    "bandplan": "800_reband"
```

### OBT (VHF) system with receive-only parameters populated

#### [Bell FleetNet Ontario](https://www.radioreference.com/db/sid/861)

| Range    | Base freq   | Spacing | Offset |
|----------|-------------|---------|--------|
| **Low**  | 141.015 MHz | 15 kHz  | 380    |
| **Mid**  | 151.730 MHz | 15 kHz  | 579    |
| **High** | 154.320 MHz | 15 kHz  | 632    |

```
    "control_channel_list": "142.500",
    "bandplan": "OBT",
    "bp_base": 141.015,
    "bp_base_spacing": 0.015,
    "bp_base_offset": 380,
    "bp_mid": 151.730,
    "bp_mid_spacing": 0.015,
    "bp_mid_offset": 579,
    "bp_high": 154.320,
    "bp_high_spacing": 0.015,
    "bp_high_offset": 632
```

### OBT (UHF) system with subscriber uplink parameters populated

#### [Federal Medical Center Devens](https://www.radioreference.com/db/sid/6990)

| Range       | Base freq | Spacing  | Offset |
|-------------|-----------|----------|--------|
| **Rx Low**  | 406.0 MHz | 12.5 kHz | 380    |
| **Rx Mid**  | 409.0 MHz | 12.5 kHz | 744    |
| **Tx Low**  | 415.0 MHz | 12.5 kHz | 0      |
| **Tx Mid**  | 418.0 MHz | 12.5 kHz | 364    |

```
    "control_channel_list": "406.8125,407.4125,408.25,409.0125,409.4125",
    "bandplan": "OBT",
    "bp_base": 406.0,
    "bp_base_spacing": 0.0125,
    "bp_base_offset": 380,
    "bp_mid": 409.0,
    "bp_mid_spacing": 0.0125,
    "bp_mid_offset": 744,
    "bp_tx_base": 415.0,
    "bp_tx_base_spacing": 0.0125,
    "bp_tx_base_offset": 0,
    "bp_tx_mid": 418.0,
    "bp_tx_mid_spacing": 0.0125,
    "bp_tx_mid_offset": 364
```

## Startup

Much like op25's `rx.py`, `multi_rx.py` is best started using a shell script.
```
./multi_rx.py -v 9 -c smartnet_example.json 2> stderr.2
```

## Known Issues & Limitations

There is currently no support for `f` or `t` terminal commands

