#!/usr/bin/liquidsoap

# Example liquidsoap streaming from op25 to icecast
# (c) 2019, 2020 gnorbury@bondcar.com, wllmbecks@gmail.com
#

set("log.stdout", true)
set("log.file.path", "/home/pi/op25/op25/gr-op25_repeater/apps/liquidsoap.log")
set("log.file", true)
set("log.level", 3)

# Make the native sample rate compatible with op25
set("frame.audio.samplerate", 8000)

# SOURCE INPUT BLOCK OPTIONS
# Mono and stereo input sources are mutually exclusive. Choose type.		

# Mono input source
input = mksafe(input.external(buffer=0.25, channels=2, samplerate=8000, restart_on_error=false, "./audio.py -x 2 -s")) 
# Consider increasing the buffer value on slow systems such as RPi3. e.g. buffer=0.25
# Longer buffer results in less choppy audio but at the expense of increased latency.

# Left channel input source and audio summing for two-slot protocols 
#left = input.external(buffer=0.25, channels=2, samplerate=8000, restart_on_error=false, "./audio.py -u 23450 -x 2 -s")
#left = audio_to_stereo(left)
#left = stereo.pan(pan=1., left)

# Right channel input source and audio summing for two-slot protocols
#right = input.external(buffer=0.25, channels=2, samplerate=8000, restart_on_error=false, "./audio.py -u 23460 -x 2 -s")
#right = audio_to_stereo(right)
#right = stereo.pan(pan=-1., right)

# OPTIONAL AUDIO SIGNAL PROCESSING BLOCKS
# Uncomment to enable
#
# High pass filter mono
input = filter.iir.butterworth.high(frequency = 200.0, order = 4, input)

# High pass filter stereo
#left = filter.iir.butterworth.high(frequency = 200.0, order = 4, left)
#right = filter.iir.butterworth.high(frequency = 200.0, order = 4, right)

# Low pass filter mono
input = filter.iir.butterworth.low(frequency = 3250.0, order = 4, input)

# Low pass filter stereo
#left = filter.iir.butterworth.low(frequency = 3250.0, order = 4, left)
#right = filter.iir.butterworth.low(frequency = 3250.0, order = 4, right)

# Normalization mono
input = normalize(input, gain_max = 3.0, gain_min = -3.0, target = -16.0, threshold = -40.0)

# Normalization stereo -- Note -- Adjust target gains independently to achieve left/right balance 
#left = normalize(left, gain_max = 3.0, gain_min = -3.0, target = -16.0, threshold = -40.0)
#right = normalize(right, gain_max = 3.0, gain_min = -3.0, target = -16.0, threshold = -40.0)

# Commnent out the line below for "non-stereo" (mono) output 
#input = mksafe(add(normalize=false, [left,right]))

# LOCAL AUDIO OUTPUT
# Uncomment the line below to enable local sound
#output.ao(input)

# ICECAST STREAMING
# Uncomment to enable output to an icecast server
# Change the "host", "password", and "mount" strings appropriately first!
# For metadata to work properly, the host address given here MUST MATCH the address in op25's meta.json file
#
# Mono Stream
output.icecast(%mp3(bitrate=16, samplerate=22050, stereo=false), description="op25", genre="Public Safety", url="", fallible=false, icy_metadata="false", host="localhost", port=8000, mount="op25", password="hackme", mean(input))
#
# Stereo Stream
#output.icecast(%mp3(bitrate=16, samplerate=22050, stereo=true), description="op25", genre="Public Safety", url="", fallible=false, icy_metadata="false", host="localhost", port=8000, mount="op25", password="hackme", input)
