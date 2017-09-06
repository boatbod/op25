#!/usr/bin/env python

# Copyright 2017 Graham Norbury
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
import socket
import errno

# OP25 defaults
PCM_RATE = 8000			# audio sample rate (Hz)
PCM_BUFFER_SIZE = 2000		# size of ALSA buffer in frames

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
		pcm_start_threshold = int(pcm_buffer_size * 0.75)

		c_pars = (c_void_p * int(self.libasound.snd_pcm_hw_params_sizeof() / sizeof(c_void_p)))()
		err = self.libasound.snd_pcm_hw_params_any(self.c_pcm, c_pars)
		if err < 0:
			sys.stderr.write("hw_params_any failed: %d\n" % err)
			return err

		err = self.libasound.snd_pcm_hw_params_set_access(self.c_pcm, c_pars, SND_PCM_ACCESS_RW_INTERLEAVED);
		if err < 0:
			sys.stderr.write("set_access failed: %d\n" % err)
			return err
		err = self.libasound.snd_pcm_hw_params_set_format(self.c_pcm, c_pars, c_uint(self.format));
		if err < 0:
			sys.stderr.write("set_format failed: %d\n" % err)
			return err
		err = self.libasound.snd_pcm_hw_params_set_channels(self.c_pcm, c_pars, c_uint(self.channels));
		if err < 0:
			sys.stderr.write("set_channels failed: %d\n" % err)
			return err
		err = self.libasound.snd_pcm_hw_params_set_rate(self.c_pcm, c_pars, c_uint(self.rate), c_int(0));
		if err < 0:
			sys.stderr.write("set_rate failed: %d\n" % err)
			return err
		err =  0 ########self.libasound.snd_pcm_hw_params_set_buffer_size(self.c_pcm, c_pars, c_ulong(pcm_buffer_size), c_int(0));
		if err < 0:
			sys.stderr.write("set_buffer_size failed: %d\n" % err)
			return err
		err = self.libasound.snd_pcm_hw_params(self.c_pcm, c_pars);
		if err < 0:
			sys.stderr.write("hw_params failed: %d\n" % err)
			return err

		self.libasound.snd_pcm_hw_params_current(self.c_pcm, c_pars)
		c_bits =  self.libasound.snd_pcm_hw_params_get_sbits(c_pars)
		self.framesize = self.channels * c_bits/8;

		c_sw_pars = (c_void_p * int(self.libasound.snd_pcm_sw_params_sizeof() / sizeof(c_void_p)))()
		err = self.libasound.snd_pcm_sw_params_current(self.c_pcm, c_sw_pars)
		if err < 0:
			sys.stderr.write("get_sw_params_current failed: %d\n" % err)
			return err
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
					sys.stderr.write("[%f] PCM underrun\n" % time.time())
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

# OP25 thread to receive UDP audio samples and send to Alsa driver
class socket_audio(threading.Thread):
	def __init__(self, udp_host, udp_port, pcm_device, **kwds):
		threading.Thread.__init__(self, **kwds)
		self.setDaemon(1)
		self.keep_running = True
		self.sock = None
		self.pcm = alsasound()
		self.setup_socket(udp_host, udp_port)
		self.setup_pcm(pcm_device)
		self.start()
		return

	def run(self):
		while self.keep_running:
			# Data received on the udp port is 320 bytes for an audio frame or 2 bytes for a flag
			#
			d = self.sock.recvfrom(MAX_SUPERFRAME_SIZE)	# recvfrom blocks until data becomes available
			if d[0]:
				d_len = len(d[0])
				if (d_len == 2):	# flag
					flag = ord(d[0][0]) + (ord(d[0][1]) << 8)	# 16 bit little endian
					if (flag == 0):					# 0x0000 = drain pcm buffer
						self.pcm.drain()
				else:			# audio data
					self.pcm.write(d[0])
			else:
				break

		self.close_socket()
		self.close_pcm()
		return

	def stop(self):
		self.keep_running = False
		return

	def setup_socket(self, udp_host, udp_port):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.bind((udp_host, udp_port))
		sys.stderr.write('setup_socket: %d\n' % udp_port)
		return

	def close_socket(self):
		self.sock.close()
		return

	def setup_pcm(self, hwdevice):
		sys.stderr.write('audio device: %s\n' % hwdevice)
		err = self.pcm.open(hwdevice)
		if err < 0:
			sys.stderr.write('failed to open audio device: %s\n' % hwdevice)
			self.pcm.dump()
			self.keep_running = False
			return

		err = self.pcm.setup(SND_PCM_FORMAT_S16_LE.value, 1, PCM_RATE, PCM_BUFFER_SIZE)
		if err < 0:
			sys.stderr.write('failed to set up pcm stream\n')
			self.keep_running = False
			return
		return

	def close_pcm(self):
		self.pcm.close()
		return

