#!/usr/bin/liquidsoap

# Example liquidsoap streaming from op25 to icecast
# (c) 2019, gnorbury@bondcar.com
#

set("log.stdout", true)
set("log.file", false)
set("log.level", 1)

# Make the native sample rate compatible with op25
set("frame.audio.samplerate", 8000)

input = mksafe(input.external(buffer=0.02, channels=2, samplerate=8000, restart_on_error=false, "./audio.py -s"))


# LOCAL AUDIO
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

