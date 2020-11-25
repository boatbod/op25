#!/usr/bin/liquidsoap

# Example liquidsoap streaming from op25 to icecast
# (c) 2019, 2020 gnorbury@bondcar.com, wllmbecks@gmail.com
#

set("log.stdout", true)
set("log.file", false)
set("log.level", 1)

# Make the native sample rate compatible with op25
set("frame.audio.samplerate", 8000)

input = mksafe(input.external(buffer=0.02, channels=2, samplerate=8000, restart_on_error=false, "./audio.py -x 2 -s"))
# Consider increasing the buffer value on slow systems such as RPi3. e.g. buffer=0.25
# Longer buffer results in less choppy audio but at the expense of increased latency.



# OPTIONAL AUDIO SIGNAL PROCESSING BLOCKS 
# Uncomment to enable
#
# High pass filter
#input = filter.iir.butterworth.high(frequency = 200.0, order = 4, input)

# Low pass filter
#input = filter.iir.butterworth.low(frequency = 3250.0, order = 4, input)

# Normalization
#input = normalize(input, gain_max = 3.0, gain_min = -3.0, target = -16.0, threshold = -40.0)



# LOCAL AUDIO OUTPUT
# Uncomment the appropriate line below to enable local sound
#
# Default audio subsystem
out (input)
#
# PulseAudio
#output.pulseaudio(input)
#
# ALSA
#output.alsa(input)



# ICECAST STREAMING
# Uncomment to enable output to an icecast server
# Change the "host", "password", and "mount" strings appropriately first!
# For metadata to work properly, the host address given here MUST MATCH the address in op25's meta.json file
#
#output.icecast(%mp3(bitrate=16, samplerate=22050, stereo=false), description="op25", genre="Public Safety", url="", fallible=false, icy_metadata="false", host="localhost", port=8000, mount="mountpoint", password="hackme", mean(input))

