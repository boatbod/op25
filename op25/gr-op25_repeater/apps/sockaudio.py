#!/usr/bin/env python

# Copyright 2017, 2018 Graham Norbury
# 
# Copyright 2011, 2012, 2013, 2014, 2015, 2016, 2017 Max H. Parke KA1RBI
# 
# This file is part of OP25
# 
# OP25 is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# OP25 is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
# License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with OP25; see the file COPYING. If not, write to the Free
# Software Foundation, Inc., 51 Franklin Street, Boston, MA
# 02110-1301, USA.

from ctypes import *
import sys
import time
import threading
import select
import socket
import errno
import struct

# OP25 defaults
PCM_RATE = 8000			# audio sample rate (Hz)
PCM_BUFFER_SIZE = 4000		# size of ALSA buffer in frames

MAX_SUPERFRAME_SIZE = 320	# maximum size of incoming UDP audio buffer

# Debug
LOG_AUDIO_XRUNS = True		# log audio underruns to stderr

# Alsa PCM constants
SND_PCM_FORMAT_S8 = c_int(0)
SND_PCM_FORMAT_U8 = c_int(1)
SND_PCM_FORMAT_S16_LE = c_int(2)
SND_PCM_FORMAT_S16_BE = c_int(3)
SND_PCM_FORMAT_U16_LE = c_int(4)
SND_PCM_FORMAT_U16_BE = c_int(5)
SND_PCM_FORMAT_S24_LE = c_int(6)
SND_PCM_FORMAT_S24_BE = c_int(7)
SND_PCM_FORMAT_U24_LE = c_int(8)
SND_PCM_FORMAT_U24_BE = c_int(9)
SND_PCM_FORMAT_S32_LE = c_int(10)
SND_PCM_FORMAT_S32_BE = c_int(11)
SND_PCM_FORMAT_U32_LE = c_int(12)
SND_PCM_FORMAT_U32_BE = c_int(13)
SND_PCM_FORMAT_FLOAT_LE = c_int(14)
SND_PCM_FORMAT_FLOAT_BE = c_int(15)
SND_PCM_FORMAT_FLOAT64_LE = c_int(16)
SND_PCM_FORMAT_FLOAT64_BE = c_int(17)
SND_PCM_FORMAT_IEC958_SUBFRAME_LE = c_int(18)
SND_PCM_FORMAT_IEC958_SUBFRAME_BE = c_int(19)
SND_PCM_FORMAT_MU_LAW = c_int(20)
SND_PCM_FORMAT_A_LAW = c_int(21)
SND_PCM_FORMAT_IMA_ADPCM = c_int(22)
SND_PCM_FORMAT_MPEG = c_int(23)
SND_PCM_FORMAT_GSM = c_int(24)
SND_PCM_FORMAT_SPECIAL = c_int(31)
SND_PCM_FORMAT_S24_3LE = c_int(32)
SND_PCM_FORMAT_S24_3BE = c_int(33)
SND_PCM_FORMAT_U24_3LE = c_int(34)
SND_PCM_FORMAT_U24_3BE = c_int(35)
SND_PCM_FORMAT_S20_3LE = c_int(36)
SND_PCM_FORMAT_S20_3BE = c_int(37)
SND_PCM_FORMAT_U20_3LE = c_int(38)
SND_PCM_FORMAT_U20_3BE = c_int(39)
SND_PCM_FORMAT_S18_3LE = c_int(40)
SND_PCM_FORMAT_S18_3BE = c_int(41)
SND_PCM_FORMAT_U18_3LE = c_int(42)
SND_PCM_FORMAT_U18_3BE = c_int(43)
SND_PCM_FORMAT_S16 = c_int(2)
SND_PCM_FORMAT_U16 = c_int(4)
SND_PCM_FORMAT_S24 = c_int(6)
SND_PCM_FORMAT_U24 = c_int(8)
SND_PCM_FORMAT_S32 = c_int(10)
SND_PCM_FORMAT_U32 = c_int(12)
SND_PCM_FORMAT_FLOAT = c_int(14)
SND_PCM_FORMAT_FLOAT64 = c_int(16)
SND_PCM_FORMAT_IEC958_SUBFRAME = c_int(18)
SND_PCM_FORMAT_LAST = SND_PCM_FORMAT_U18_3BE

SND_PCM_NORMAL = c_int(0x00000000)
SND_PCM_NONBLOCK = c_int(0x00000001)

SND_PCM_STREAM_PLAYBACK = c_int(0)
SND_PCM_STREAM_CAPTURE = c_int(1)
SND_PCM_STREAM_LAST = SND_PCM_STREAM_CAPTURE

SND_PCM_ACCESS_MMAP_INTERLEAVED = c_int(0)
SND_PCM_ACCESS_MMAP_NONINTERLEAVED = c_int(1)
SND_PCM_ACCESS_MMAP_COMPLEX = c_int(2)
SND_PCM_ACCESS_RW_INTERLEAVED = c_int(3)
SND_PCM_ACCESS_RW_NONINTERLEAVED = c_int(4)
SND_PCM_ACCESS_LAST = SND_PCM_ACCESS_RW_NONINTERLEAVED

# Python CTypes wrapper to Alsa libasound2
class alsasound(object):
	def __init__(self):
		self.libasound = cdll.LoadLibrary("libasound.so.2")
		self.c_pcm = c_void_p()
		self.format = 0
		self.channels = 0
		self.rate = 0
		self.framesize = 0

	def open(self, hwdev):
		b_hwdev = create_string_buffer(str.encode(hwdev))
		c_stream = SND_PCM_STREAM_PLAYBACK
		err = self.libasound.snd_pcm_open(byref(self.c_pcm), b_hwdev, c_stream, SND_PCM_NORMAL)
		return err

	def close(self):
		if (self.c_pcm.value == None):
			return
		self.libasound.snd_pcm_close(self.c_pcm)
		self.c_pcm.value = None

	def setup(self, pcm_format, pcm_channels, pcm_rate, pcm_buffer_size):
		if (self.c_pcm.value == None):
			return

		self.format = pcm_format
		self.channels = pcm_channels
		self.rate = pcm_rate
		pcm_buf_sz = c_ulong(pcm_buffer_size)

		c_pars = (c_void_p * int(self.libasound.snd_pcm_hw_params_sizeof() / sizeof(c_void_p)))()
		err = self.libasound.snd_pcm_hw_params_any(self.c_pcm, c_pars)
		if err < 0:
			sys.stderr.write("hw_params_any failed: %d\n" % err)
			return err

		err = self.libasound.snd_pcm_hw_params_set_access(self.c_pcm, c_pars, SND_PCM_ACCESS_RW_INTERLEAVED)
		if err < 0:
			sys.stderr.write("set_access failed: %d\n" % err)
			return err
		err = self.libasound.snd_pcm_hw_params_set_format(self.c_pcm, c_pars, c_uint(self.format))
		if err < 0:
			sys.stderr.write("set_format failed: %d\n" % err)
			return err
		err = self.libasound.snd_pcm_hw_params_set_channels(self.c_pcm, c_pars, c_uint(self.channels))
		if err < 0:
			sys.stderr.write("set_channels failed: %d\n" % err)
			return err
		err = self.libasound.snd_pcm_hw_params_set_rate(self.c_pcm, c_pars, c_uint(self.rate), c_int(0))
		if err < 0:
			sys.stderr.write("set_rate failed: %d\n" % err)
			return err
		err = self.libasound.snd_pcm_hw_params_set_buffer_size_near(self.c_pcm, c_pars, byref(pcm_buf_sz))
		if err < 0:
			sys.stderr.write("set_buffer_size_near failed: %d\n" % err)
			return err
		if pcm_buf_sz.value != pcm_buffer_size:
			sys.stderr.write("set_buffer_size_near requested %d, but returned %d\n" % (pcm_buffer_size, pcm_buf_sz.value))
		err = self.libasound.snd_pcm_hw_params(self.c_pcm, c_pars)
		if err < 0:
			sys.stderr.write("hw_params failed: %d\n" % err)
			return err

		self.libasound.snd_pcm_hw_params_current(self.c_pcm, c_pars)
		c_bits =  self.libasound.snd_pcm_hw_params_get_sbits(c_pars)
		self.framesize = self.channels * c_bits/8

		c_sw_pars = (c_void_p * int(self.libasound.snd_pcm_sw_params_sizeof() / sizeof(c_void_p)))()
		err = self.libasound.snd_pcm_sw_params_current(self.c_pcm, c_sw_pars)
		if err < 0:
			sys.stderr.write("get_sw_params_current failed: %d\n" % err)
			return err
		pcm_start_threshold = int(pcm_buf_sz.value * 0.75)
		err = self.libasound.snd_pcm_sw_params_set_start_threshold(self.c_pcm, c_sw_pars, c_uint(pcm_start_threshold))
		if err < 0:
			sys.stderr.write("set_sw_params_start_threshold failed: %d\n" % err)
			return err
		err = self.libasound.snd_pcm_sw_params(self.c_pcm, c_sw_pars)
		if err < 0:
			sys.stderr.write("sw_params failed: %d\n" % err)
			return err

		ret = self.libasound.snd_pcm_prepare(self.c_pcm)
		#self.dump()
		return ret

	def write(self, pcm_data):
		datalen = len(pcm_data)
		n_frames = c_ulong(datalen / self.framesize)
		c_data = c_char_p(pcm_data)
		ret = 0

		if (self.c_pcm.value == None):
			sys.stderr.write("PCM device is closed\n")
			return -1

		ret = self.libasound.snd_pcm_writei(self.c_pcm, cast(c_data, POINTER(c_void_p)), n_frames)
		if (ret < 0):
			if (ret == -errno.EPIPE): # underrun
				if (LOG_AUDIO_XRUNS):
					sys.stderr.write("%f PCM underrun\n" % time.time())
				ret = self.libasound.snd_pcm_recover(self.c_pcm, ret, 1)
				if (ret >= 0):
					ret = self.libasound.snd_pcm_writei(self.c_pcm, cast(c_data, POINTER(c_void_p)), n_frames)
				else:
					ret = self.libasound.snd_pcm_prepare(self.c_pcm)
					ret = self.libasound.snd_pcm_writei(self.c_pcm, cast(c_data, POINTER(c_void_p)), n_frames)
			elif (ret == -errno.ESTRPIPE): # suspended
				while True:
					ret = self.libasound.snd_pcm_resume(self.c_pcm)
					if (ret != -errno.EAGAIN):
						break
					time.sleep(1)
				if (ret < 0):
					ret = self.libasound.snd_pcm_prepare(self.c_pcm)
			elif (ret < 0): # other error
				ret = self.libasound.snd_pcm_prepare(self.c_pcm)

		return ret

	def drain(self):
		ret = self.libasound.snd_pcm_drain(self.c_pcm)
		if (ret == -errno.ESTRPIPE): # suspended
			while True:
				ret = self.libasound.snd_pcm_resume(self.c_pcm)
				if (ret != -errno.EAGAIN):
					break
				time.sleep(1)
		ret = self.libasound.snd_pcm_prepare(self.c_pcm)
		return ret

	def drop(self):
		ret = self.libasound.snd_pcm_drop(self.c_pcm)
		if (ret == -errno.ESTRPIPE): # suspended
			while True:
				ret = self.libasound.snd_pcm_resume(self.c_pcm)
				if (ret != -errno.EAGAIN):
					break
				time.sleep(1)
		ret = self.libasound.snd_pcm_prepare(self.c_pcm)
		return ret

	def dump(self):
		if (self.c_pcm.value == None):
			return

		c_buf_p = c_void_p()
		c_str_p = c_char_p()
		c_strlen = c_uint(0)
		self.libasound.snd_output_buffer_open(byref(c_buf_p))
		self.libasound.snd_pcm_dump_setup(self.c_pcm, c_buf_p)
		c_strlen = self.libasound.snd_output_buffer_string(c_buf_p, byref(c_str_p))
		sys.stderr.write("%s\n" % c_str_p.value[0:c_strlen-1])
		self.libasound.snd_output_close(c_buf_p)

	def check(self):
		return 0

# Wrapper to emulate pcm writes of sound samples to stdout (for liquidsoap)
class stdout_wrapper(object): 
	def __init__(self):
		self.silence = chr(0) * 640
		pass

	def open(self, hwdev):
		return 0

	def close(self):
		return 0

	def setup(self, pcm_format, pcm_channels, pcm_rate, pcm_buffer_size):
		return 0

	def drain(self):
		try:
			sys.stdout.flush()
		except IOError:	# IOError means listener has terminated
			return -1
		return 0

	def drop(self):
		return 0

	def write(self, pcm_data):
		try:
			sys.stdout.write(pcm_data)
		except IOError:	# IOError means listener has terminated
			return -1
		return 0

	def check(self):
		rc = 0
		if (self.write(self.silence) < 0) or (self.drain() < 0): # write silence to check pipe connectivity 
			rc = -1
		return rc

	def dump(self):
		pass

# Main class that receives UDP audio samples and sends them to a PCM subsystem (currently ALSA or STDOUT)
class socket_audio(object):
	def __init__(self, udp_host, udp_port, pcm_device, two_channels = False, audio_gain = 1.0, dest_stdout = False, **kwds):
		self.keep_running = True
		self.two_channels = two_channels
		self.audio_gain = audio_gain
		self.dest_stdout = dest_stdout
		self.sock_a = None
		self.sock_b = None
                if dest_stdout:
			pcm_device = "stdout"
			self.pcm = stdout_wrapper()
		else:
			self.pcm = alsasound()
		self.setup_sockets(udp_host, udp_port)
		self.setup_pcm(pcm_device)

	def run(self):
		rc = 0
		while self.keep_running and (rc >= 0):
			readable, writable, exceptional = select.select( [self.sock_a, self.sock_b], [], [self.sock_a, self.sock_b], 5.0)
			in_a = None
			in_b = None
			data_a = ""
			data_b = ""
			flag_a = -1
			flag_b = -1

			# Check for select() polling timeout and pcm self-check
			if (not readable) and (not writable) and (not exceptional):
 				rc = self.pcm.check()
				continue

			# Data received on the udp port is 320 bytes for an audio frame or 2 bytes for a flag
			if self.sock_a in readable:
				in_a = self.sock_a.recvfrom(MAX_SUPERFRAME_SIZE)

			if self.sock_b in readable:
				in_b = self.sock_b.recvfrom(MAX_SUPERFRAME_SIZE)

			if in_a is not None:
				len_a = len(in_a[0])
				if len_a == 2:
					flag_a = ord(in_a[0][0]) + (ord(in_a[0][1]) << 8)	# 16 bit little endian
				elif len_a > 0:
					data_a = in_a[0]

			if in_b is not None:
				len_b = len(in_b[0])
				if len_b == 2:
					flag_b = ord(in_b[0][0]) + (ord(in_b[0][1]) << 8)	# 16 bit little endian
				elif len_b > 0:
					data_b = in_b[0]

			if (flag_a == 0) or (flag_b == 0):
				rc = self.pcm.drain()
				continue

			if (((flag_a == 1) and (flag_b == 1)) or
			    ((flag_a == 1) and (in_b is None)) or 
			    ((flag_b == 1) and (in_a is None))):
				rc = self.pcm.drop()
				continue

			if not self.two_channels:
				data_a = self.scale(data_a)
				rc = self.pcm.write(self.interleave(data_a, data_a))
			else:
				data_a = self.scale(data_a)
				data_b = self.scale(data_b)
				rc = self.pcm.write(self.interleave(data_a, data_b))

		self.close_sockets()
		self.close_pcm()
		return

	def scale(self, data):	# crude amplitude scaler (volume) for S16_LE samples
		scaled_data = ""
		d_len = len(data) / 2
		iter_d = iter(data)
		i = 0;
		while i < d_len:
			i += 1
			pcm_r = struct.unpack('<h', next(iter_d, chr(0)) + next(iter_d, chr(0)))[0]
			pcm_s = min(max((int)(pcm_r * self.audio_gain), -32768), 32767)
			scaled_data += struct.pack('<h', pcm_s)
		return scaled_data

	def interleave(self, data_a, data_b):
		combi_data = ""
		d_len = max(len(data_a), len(data_b))
		iter_a = iter(data_a)
		iter_b = iter(data_b)
		i = 0
		while i < d_len:
			i += 2
			combi_data += next(iter_a, chr(0))
			combi_data += next(iter_a, chr(0))
			combi_data += next(iter_b, chr(0))
			combi_data += next(iter_b, chr(0))
		return combi_data

	def stop(self):
		self.keep_running = False
		return

	def setup_sockets(self, udp_host, udp_port):
		self.sock_a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock_b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock_a.setblocking(0)
		self.sock_b.setblocking(0)
		self.sock_a.bind((udp_host, udp_port))
		self.sock_b.bind((udp_host, udp_port + 2))
		return

	def close_sockets(self):
		self.sock_a.close()
		self.sock_b.close()
		return

	def setup_pcm(self, hwdevice):
		sys.stderr.write('audio device: %s\n' % hwdevice)
		err = self.pcm.open(hwdevice)
		if err < 0:
			sys.stderr.write('failed to open audio device: %s\n' % hwdevice)
			self.pcm.dump()
			self.keep_running = False
			return

		err = self.pcm.setup(SND_PCM_FORMAT_S16_LE.value, 2, PCM_RATE, PCM_BUFFER_SIZE)
		if err < 0:
			sys.stderr.write('failed to set up pcm stream\n')
			self.keep_running = False
			return
		return

	def close_pcm(self):
		sys.stderr.write('audio closing\n')
		self.pcm.close()
		return

class audio_thread(threading.Thread):
	def __init__(self, udp_host, udp_port, pcm_device, two_channels = False, audio_gain = 1.0, dest_stdout = False, **kwds):
		threading.Thread.__init__(self, **kwds)
		self.setDaemon(True)
		self.keep_running = True
                self.sock_audio = socket_audio(udp_host, udp_port, pcm_device, two_channels, audio_gain, dest_stdout, **kwds)
		self.start()
		return

	def run(self):
		self.sock_audio.run()

	def stop(self):
		self.sock_audio.stop()

