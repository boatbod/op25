# dv_tx.py - OP25 Multiprotocol Digital Voice Transmitter

This script implements a multiprotocol digital voice transmitter ("DV TX") for the OP25 project.  
It is used to generate and transmit various digital voice protocols (P25, DMR, D-STAR, and YSF) using GNU Radio and SDR hardware or sound devices.

## Features

- Supports P25, DMR, D-STAR, and YSF digital voice protocols
- Can use either audio files, sound card, or symbol files as input
- Output to SDR hardware (e.g., HackRF, USRP, etc.) or standard sound card/file
- Configurable for wide variety of test and transmission scenarios

## Requirements

- Python 3
- GNU Radio (including `gnuradio`, `gnuradio-op25`, `gnuradio-op25_repeater`, and dependencies)
- `osmosdr` module (for SDR hardware output)
- OP25 libraries/components built and installed
- Appropriate configuration files for the selected protocol

## Usage

Run the script using Python 3:

```sh
./dv_tx.py [OPTIONS]
```

The following options are supported:

| Option                         | Description                                                                            |
|---------------------------------|----------------------------------------------------------------------------------------|
| `-a`, `--args`                 | Device arguments for SDR hardware (e.g. `"hackrf"`).                                 |
| `-A`, `--alt-modulator-rate`   | Alternative modulator rate (default: 50000).                                           |
| `-b`, `--bt`                   | Specify BT value for modulation characteristics (default: 0.5).                        |
| `-c`, `--config-file`          | Path to protocol-specific config file (**required for DMR, D-STAR, and YSF**).         |
| `-f`, `--file1`                | Input file for slot 1 (16-bit PCM short format).                                       |
| `-F`, `--file2`                | (DMR only) Input file for slot 2 (16-bit PCM short format).                            |
| `-g`, `--gain`                 | Input gain (default: 1.0).                                                             |
| `-i`, `--if-rate`              | Output sample rate to SDR (default: 480000).                                           |
| `-I`, `--audio-input`          | Audio input device name for PCM (e.g. `hw:0,0` or `/dev/dsp`).                        |
| `-k`, `--symbol-sink`          | Output file for writing generated symbols (optional).                                  |
| `-N`, `--gains`                | Set SDR gain(s) as comma-separated list of `name:value`.                               |
| `-O`, `--audio-output`         | Audio output device name (default: `default`).                                         |
| `-o`, `--output-file`          | Write output waveform to a file instead of hardware or soundcard.                      |
| `-p`, `--protocol`             | **Protocol to use: `dmr`, `dstar`, `p25`, `ysf` (required)**.                         |
| `-q`, `--frequency-correction` | PPM frequency correction.                                                              |
| `-Q`, `--frequency`            | Transmit frequency in Hz.                                                              |
| `-r`, `--repeat`               | Loop input file playback (default: False).                                             |
| `-R`, `--fullrate-mode`        | (YSF only) Enable fullrate mode.                                                       |
| `-s`, `--modulator-rate`       | Modulator sample rate (default: 48000).                                                |
| `-S`, `--alsa-rate`            | Sample rate for sound card input/output (default: 48000).                              |
| `-t`, `--test`                 | Test pattern symbol file as input (bypasses normal encoders).                          |
| `-v`, `--verbose`              | Verbosity level (default: 0).                                                          |

**Example:**  
Transmit a P25 digital voice signal using an audio file as input:

```sh
./dv_tx.py -p p25 --args 'hackrf' -i 10000000 -q 0  -v 11 -f ./file.wav -Q 145000000 -N 'RF:0,IF:24'
```

or using a microphone as input:

```sh
./dv_tx.py -p p25 --args 'hackrf' -i 10000000 -q 0 -v 11 -I hw:0,0 -Q 145000000 -N 'RF:0,IF:24'
```

## Protocol-Specific Requirements

- **YSF, DMR, and D-STAR:** The `-c/--config-file` option must be provided.
- **DMR:** If using two time slots, specify both `-f` (slot 1) and `-F` (slot 2).  
- **P25 and YSF:** Optionally, use `-R/--fullrate-mode` for fullrate YSF.

## Output Options

- By default, output is sent to an SDR if `-a/--args` is specified. Otherwise, output goes to the sound card or to a file if `-o` is given.
- Use `-O/--audio-output` to select audio device or `-o/--output-file` to save the modulated signal as a file.


# p25craft.py

**p25craft.py** is a command-line utility and Python module for crafting and generating APCO P25 test packets. The output can be used to create test vectors similar to those in TIA-102 standards documentation, or produce binary packet streams for analysis and hardware testing.

## Features

- Create a variety of APCO Project 25 (P25) packet types:
  - Header Data Unit (HDU)
  - Logical Link Data Unit 1/2 (LDU1/LDU2)
  - Simple & Extended Terminator Data Units (TDU, xTDU)
  - Trunking Signaling Data Unit (TSDU/TSBK)
  - Confirmed, Response, & Unconfirmed Packet Data Units (CPDU/RPDU/UPDU)
  - Alternate MBT Control Packet
  - Special control channel and service request/reply packets (inhibit, radio check, affiliation, registration, etc.)
- Generates both human-readable text (TIA-102 spec style) and binary output.
- Utility and error control coding functions for conformance with P25 standards.
- Can be used interactively as a Python module.

## Usage

Run the script with the desired options to craft specific packet types.

```bash
./p25craft.py [options]
```

- Output is printed to STDOUT by default.
- Binary packet data is saved to `p25.out` unless another file is provided.

#### Common Options

| Option           | Description                                            | Default         |
|------------------|-------------------------------------------------------|-----------------|
| `--hdu`          | Construct Header Data Unit                            |                 |
| `--ldu1`         | Construct Logical Link Data Unit 1                    |                 |
| `--ldu2`         | Construct Logical Link Data Unit 2                    |                 |
| `--stdu`         | Construct Simple Terminator Data Unit                 |                 |
| `--xtdu`         | Construct Terminator Data Unit with Link Control      |                 |
| `--tsdu`         | Construct Trunking Signaling Data Unit                |                 |
| `--cpdu`         | Construct Confirmed Packet Data Unit                  |                 |
| `--rpdu`         | Construct Response Packet Data Unit                   |                 |
| `--updu`         | Construct Unconfirmed Packet Data Unit                |                 |
| `--ambt`         | Alternative MBT Control Packet                        |                 |
| `--inhibit`      | Special Packet: Inhibit                               |                 |
| `--uninhibit`    | Special Packet: Uninhibit                             |                 |
| `--rum`          | Special Packet: Radio Unit Monitor Command            |                 |
| `--quiet`        | Suppress text output                                  | `False`         |
| `--output-file`  | Write binary output to specified file                 | `p25.out`       |
| See the script for full list of options and their descriptions.           |                 |

### Example
#### Crafting

Craft a 1011 Hz tone packet for a specific talkgroup during 3.6 s (10 superframes * 360 ms/superframe):

```bash
./p25craft.py --superframes 10 --nac 0x293 --mi 0 --kid 0 --algid 0x80 --tgid 1 --src 1 --mfid 0 --lco 0 --svcopt 0 --dst 1 --1011
```

#### Unpacking

Unpack the constructed packet using `unpack.py` script:

```bash
./unpack.py -i p25.out -o p25.dat
```

#### Transmitting

Transmit the packet with `dv_tx.py`:

```bash
./dv_tx.py -p p25 --args 'hackrf' -i 10000000 -q 0 -v 11 -t ./p25.dat -Q 145000000 -N 'RF:0,IF:24'
```

### As a Python Module

```python
from p25craft import construct_ext_fnct_cmd_check

# Example: Radio Check command packet construction
construct_ext_fnct_cmd_check(0x293, 0x1, 0x000001, 0x000002)
```

## Output

- **Text (default)**: TIA-102-style tabular printout of packet symbol data.
- **Binary**: Write to `p25.out` or file specified via `--output-file` for machine/hex-editor use.
