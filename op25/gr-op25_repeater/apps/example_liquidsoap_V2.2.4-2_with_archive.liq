#!/usr/bin/liquidsoap

#Liquidsoap v2.2.4-1 streaming from op25 to icecast + local audio archive
# (c) 2019-2026 gnorbury@bondcar.com, wllmbecks@gmail.com
#

settings.log.stdout.set(true)
settings.log.file.set(false)
settings.log.file.path.set("/logfile_path/liquidsoap.log")
settings.log.level.set(3)
settings.log.file.append.set(false)


# Make the native sample rate compatible with op25
settings.frame.audio.size.set(8000)

input = input.external.rawaudio(buffer=0.25, channels=2, samplerate=8000, restart_on_error=false, "./audio.py -u 23450 -x 1.35 -s")



# OPTIONAL AUDIO SIGNAL PROCESSING BLOCKS 
# Uncomment to enable
#
# High pass filter
#input = filter.iir.butterworth.high(frequency = 200.0, order = 4, input)

# Low pass filter
#input = filter.iir.butterworth.low(frequency = 3250.0, order = 4, input)

# Compression
input = compress(input, attack = 15.0, gain = 2.0, knee = 1.0, ratio = 3.0, release = 60.0, threshold = -24.0)

# Normalization
input = normalize(input, gain_max = 6.0, gain_min = -6.0, target = -16.0, threshold = -40.0)

# Optimize  mp3 arhive recording level
mp3_audio = amplify(0.65,input)

# Create infallible local speaker and streaming audio
input_safe = mksafe(input)



# LOCAL AUDIO OUTPUT
# Uncomment the appropriate line below to enable local sound
#
# Default audio subsystem
#out (input)
#
# PulseAudio
#output.pulseaudio(input_safe)
#
# ALSA
#output.alsa(input_safe)


# Dump mp3 audio files to Apache web server
# Define mp3 encoder format
# stereo=true by default
# samplerate=44100 by default
MP3_FORMAT = %mp3(bitrate=128)

output.file(
  MP3_FORMAT,
  {time.string("/var/www/html/op25/MPSCS-%Y-%m-%d/hour-%H.mp3")},
  mp3_audio,
  fallible=true,
  reopen_when={0m},
  append=true,
)


# ICECAST STREAMING
# Uncomment to enable output to an icecast server
# Change the "host", "password", and "mount" strings appropriately first!
# For metadata to work properly, the host address given here MUST MATCH the address in op25's meta.json file
#
output.icecast(%mp3(bitrate=16, samplerate=44100, stereo=true, internal_quality=0), description="op25", genre="Public Safety",
url="", fallible=false, host="localhost", port=8000, mount="op25", name="Ubuntu 24.04 LTS", password="hackme",(input_safe))
