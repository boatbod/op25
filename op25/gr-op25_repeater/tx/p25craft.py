#!/usr/bin/python
#
# p25craft.py - utility for crafting APCO P25 packets
#
# version 1.0
#
# This is a command line tool for generating test vectors consisting of one or
# more P25 packets.  It produces text output similar to the test vectors
# presented in the P25 standards documents (TIA-102).  It can also produce
# binary output suitable for viewing with a hex editor or loading into a vector
# signal generator.
#
# The generated packets are intended to comply with the following standards:
#   TIA-102.BAAA-A Project 25 FDMA - Common Air Interface 
#   TIA-102.AABB-A Project 25 Trunking Control Channel Formats
#   TIA-102.AABC-C Project 25 Trunking Control Channel Messages
#   TIA-102.AABF-B Link Control Word Formats and Messages
#
# Testing has been done to verify agreement with test vectors listed in:
#   TIA-102.BAAB-B Project 25 Common Air Interface Conformance Test
#
# In addition to command line use, this can be used as a python module.
# example:
# $ python
# >>> from p25craft import *
# >>> construct_ext_fnct_cmd_check(0x293, 0x1, 0x000001, 0x000002)
# Special Packet: Extended Function Command - Radio Check
#	Extended Function:
#		Class     = 00
# . . .
#
# Copyright 2011 Michael Ossmann <mike@ossmann.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.

import sys, struct

quiet = False
outfile = ""
flip = 0x000
quiet = True
outfile = open('p25.out', 'w')


#####################
# utility functions #
#####################

def text_out(text):
	if not quiet:
		sys.stdout.write(text)

# Print a list of dibits.
def print_dibits(data):
	assert len(data) % 2 == 0
	for i in range(0, len(data), 2):
		nibble = (data[i] << 2) + data[i + 1]
		text_out("%01x" % nibble)
	text_out("\n")

# Print output similar to examples found in CAI conformance test specification.
# Input should be a list of dibits.
def print_spec(data):
	# we only support full microslots
	assert len(data) % 36 == 0

	microslot = 0
	text_out("\t\tMicroslot:  ___________0___________  ___________1___________")
	for i in range(0, len(data), 36):
		if microslot % 2 == 0:
			text_out("\n")
			text_out("\t\t" "%9d: " % microslot)
		text_out(" ")
		for j in range(0, 36, 6):
			dodectet = 0
			for k in range(6):
				dodectet |= data[i+j+k] << (10 - k*2)
			text_out("%03x " % (dodectet ^ flip))
		microslot += 1
	text_out("\n")
	text_out("\n")

	# also produce binary output if requested
	if outfile:
		for i in range(0, len(data), 4):
			byte = 0
			for j in range(4):
				byte |= data[i+j] << (6 - j*2)
			outfile.write(struct.pack('B1', (byte ^ flip & 0xff)))

# Split an integer into list of bytes.
def split_bytes(data, len):
	bytes = []
	for i in range((len - 1) * 8, -8, -8):
		bytes.append((data >> i) & 0xff)
	return bytes

# Split an integer into list of dibits.
# count should be set to the number of dibits to extract.
def split_dibits(data, count):
	dibits = []
	for i in range(count*2 - 2, -2, -2):
		dibits.append((data >> i) & 0x03)
	return dibits

# Split an integer into list of tribits.
# count should be set to the number of tribits to extract.
def split_tribits(data, count):
	dibits = []
	for i in range(count*3 - 3, -3, -3):
		dibits.append((data >> i) & 0x07)
	return dibits

# Insert status symbols.
# Arguments are lists of dibits.  Returns list of dibits.
def insert_status(data, ssyms):
	stats = list(ssyms)
	stats.reverse()
	i = 1
	syms = []
	for dibit in data:
		syms.append(dibit)
		if i % 35 == 0:
			if stats:
				syms.append(stats.pop())
			else:
				sys.stderr.write("error: ran out of status symbols\n")
		i += 1
	# pad to end of status symbols
	while stats:
		syms.append(0)
		if i % 35 == 0:
			syms.append(stats.pop())
			if stats:
				sys.stderr.write("warning: excess status symbols\n")
		i += 1
	return syms


########################
# error control coding #
########################

# (64,16,23) BCH encoder
# spec sometimes refers to this as (63,16,23) plus a parity bit
# argument is an integer
# returns an integer
def bch_64_16_23_encode(data):
	matrix = (
		0x8000cd930bdd3b2a, 0x4000ab5a8e33a6be,
		0x2000983e4cc4e874, 0x10004c1f2662743a,
		0x0800eb9c98ec0136, 0x0400b85d47ab3bb0,
		0x02005c2ea3d59dd8, 0x01002e1751eaceec,
		0x0080170ba8f56776, 0x0040c616dfa78890,
		0x0020630b6fd3c448, 0x00103185b7e9e224,
		0x000818c2dbf4f112, 0x0004c1f2662743a2,
		0x0002ad6a38ce9afb, 0x00019b2617ba7657)
	assert data < 2**16
	codeword = 0
	for i in range(16):
		if data & (0x8000 >> i):
			codeword ^= matrix[i]
	return codeword

# GF(2^6) multiply (for Reed-Solomon encoder)
def gf6mult(a, b):
	assert a < 2**6
	assert b < 2**6
	p = 0
	for i in range(6):
		if b & 1:
			p ^= a
		a <<= 1
		if a & 0x40:
			a ^= 0x43 # primitive polynomial: x^6 + x + 1
		b >>= 1
	return p

# (36,20,17) shortened Reed-Solomon encoder
# argument is an integer
# returns an integer
def rs_36_20_17_encode(data):
	matrix = (
		(1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,074,037,034,006,002,007,044,064,026,014,026,044,054,013,077,005),
		(0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,004,017,050,024,011,005,030,057,033,003,002,002,015,016,025,026),
		(0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,007,023,037,046,056,075,043,045,055,021,050,031,045,027,071,062),
		(0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,026,005,007,063,063,027,063,040,006,004,040,045,047,030,075,007),
		(0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,023,073,073,041,072,034,021,051,067,016,031,074,011,021,012,021),
		(0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,024,051,025,023,022,041,074,066,074,065,070,036,067,045,064,001),
		(0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,052,033,014,002,020,006,014,025,052,023,035,074,075,075,043,027),
		(0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,055,062,056,025,073,060,015,030,013,017,020,002,070,055,014,047),
		(0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,054,051,032,065,077,012,054,013,035,032,056,012,075,001,072,063),
		(0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,074,041,030,041,043,022,051,006,064,033,003,047,027,012,055,047),
		(0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,054,070,011,003,013,022,016,057,003,045,072,031,030,056,035,022),
		(0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,051,007,072,030,065,054,006,021,036,063,050,061,064,052,001,060),
		(0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,001,065,032,070,013,044,073,024,012,052,021,055,012,035,014,072),
		(0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,011,070,005,010,065,024,015,077,022,024,024,074,007,044,007,046),
		(0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,006,002,065,011,041,020,045,042,046,054,035,012,040,064,065,033),
		(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,034,031,001,015,044,064,016,024,052,016,006,062,020,013,055,057),
		(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,063,043,025,044,077,063,017,017,064,014,040,074,031,072,054,006),
		(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,071,021,070,044,056,004,030,074,004,023,071,070,063,045,056,043),
		(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,002,001,053,074,002,014,052,074,012,057,024,063,015,042,052,033),
		(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,034,035,002,023,021,027,022,033,064,042,005,073,051,046,073,060))
	assert data < 2**120
	codeword = [0,] * 36
	for i in range(36):
		for j in range(20):
			hexbit = (data >> ((19 - j) * 6)) & 0x3f
			codeword[i] ^= gf6mult(hexbit, matrix[j][i])
	return codeword

# (24,12,13) shortened Reed-Solomon encoder
# argument is an integer
# returns an integer
def rs_24_12_13_encode(data):
	matrix = (
		(1,0,0,0,0,0,0,0,0,0,0,0,062,044,003,025,014,016,027,003,053,004,036,047),
		(0,1,0,0,0,0,0,0,0,0,0,0,011,012,011,011,016,064,067,055,001,076,026,073),
		(0,0,1,0,0,0,0,0,0,0,0,0,003,001,005,075,014,006,020,044,066,006,070,066),
		(0,0,0,1,0,0,0,0,0,0,0,0,021,070,027,045,016,067,023,064,073,033,044,021),
		(0,0,0,0,1,0,0,0,0,0,0,0,030,022,003,075,015,015,033,015,051,003,053,050),
		(0,0,0,0,0,1,0,0,0,0,0,0,001,041,027,056,076,064,021,053,004,025,001,012),
		(0,0,0,0,0,0,1,0,0,0,0,0,061,076,021,055,076,001,063,035,030,013,064,070),
		(0,0,0,0,0,0,0,1,0,0,0,0,024,022,071,056,021,035,073,042,057,074,043,076),
		(0,0,0,0,0,0,0,0,1,0,0,0,072,042,005,020,043,047,033,056,001,016,013,076),
		(0,0,0,0,0,0,0,0,0,1,0,0,072,014,065,054,035,025,041,016,015,040,071,026),
		(0,0,0,0,0,0,0,0,0,0,1,0,073,065,036,061,042,022,017,004,044,020,025,005),
		(0,0,0,0,0,0,0,0,0,0,0,1,071,005,055,003,071,034,060,011,074,002,041,050))
	assert data < 2**72
	codeword = [0,] * 24
	for i in range(24):
		for j in range(12):
			hexbit = (data >> ((11 - j) * 6)) & 0x3f
			codeword[i] ^= gf6mult(hexbit, matrix[j][i])
	return codeword

# (24,16,9) shortened Reed-Solomon encoder
# argument is an integer
# returns an integer
def rs_24_16_9_encode(data):
	matrix = (
		(1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,051,045,067,015,064,067,052,012),
		(0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,057,025,063,073,071,022,040,015),
		(0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,005,001,031,004,016,054,025,076),
		(0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,073,007,047,014,041,077,047,011),
		(0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,075,015,051,051,017,067,017,057),
		(0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,020,032,014,042,075,042,070,054),
		(0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,002,075,043,005,001,040,012,064),
		(0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,024,074,015,072,024,026,074,061),
		(0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,042,064,007,022,061,020,040,065),
		(0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,032,032,055,041,057,066,021,077),
		(0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,065,036,025,007,050,016,040,051),
		(0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,064,006,054,032,076,046,014,036),
		(0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,062,063,074,070,005,027,037,046),
		(0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,055,043,034,071,057,076,050,064),
		(0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,024,023,023,005,050,070,042,023),
		(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,067,075,045,060,057,024,006,026))
	assert data < 2**96
	codeword = [0,] * 24
	for i in range(24):
		for j in range(16):
			hexbit = (data >> ((15 - j) * 6)) & 0x3f
			codeword[i] ^= gf6mult(hexbit, matrix[j][i])
	return codeword

# (24,12,8) extended Golay encoder
# argument is an integer
# returns an integer
def golay_24_12_8_encode(data):
	matrix = (040006165, 020003073, 010007550, 04003664, 02001732,
		01006631, 0403315, 0201547, 0106706, 045227, 024476, 014353)
	assert data < 2**12
	codeword = 0
	for i in range(12):
		if data & (04000 >> i):
			codeword ^= matrix[i]
	return codeword

# (23,12,7) Golay encoder
# argument is an integer
# returns an integer
def golay_23_12_8_encode(data):
	return golay_24_12_8_encode(data) >> 1

# (18,6,8) shortened Golay encoder
# argument is an integer
# returns an integer
def golay_18_6_8_encode(data):
	assert data < 2**6
	return golay_24_12_8_encode(data)

# (16,8,5) shortened cyclic encoder
# argument is an integer
# returns an integer
def cyclic_16_8_5_encode(data):
	matrix = (0x804e, 0x4027, 0x208f, 0x10db,
		0x08f1, 0x04e4, 0x0272, 0x0139)
	assert data < 2**8
	codeword = 0
	for i in range(8):
		if data & (0x80 >> i):
			codeword ^= matrix[i]
	return codeword

# (10,6,3) shortened Hamming encoder
# argument is an integer
# returns an integer
def hamming_10_6_3_encode(data):
	matrix = (0x20e, 0x10d, 0x08b, 0x047, 0x023, 0x01c)
	assert data < 2**6
	codeword = 0
	for i in range(6):
		if data & (0x20 >> i):
			codeword ^= matrix[i]
	return codeword

# (15,11,3) Hamming encoder
# argument is an integer
# returns an integer
def hamming_15_11_3_encode(data):
	matrix = (0x400f, 0x200e, 0x100d, 0x080c, 0x040b,
		0x020a, 0x0109, 0x0087, 0x0046, 0x0025, 0x0013)
	assert data < 2**11
	codeword = 0
	for i in range(11):
		if data & (0x400 >> i):
			codeword ^= matrix[i]
	return codeword

# sequence of cyclic encodings for LDU1
# argument is an integer
# returns an integer
def ldu1_cyclic(lsd):
	word = cyclic_16_8_5_encode((lsd >> 24) & 0xff)
	word <<= 16
	word |= cyclic_16_8_5_encode((lsd >> 16) & 0xff)
	return word

# sequence of cyclic encodings for LDU2
# argument is an integer
# returns an integer
def ldu2_cyclic(lsd):
	word = cyclic_16_8_5_encode((lsd >> 8) & 0xff)
	word <<= 16
	word |= cyclic_16_8_5_encode(lsd & 0xff)
	return word

# sequence of golay encodings for HDU
# argument is an integer
# returns an integer
def header_golay(rs_codeword):
	out = 0
	for i in range(36):
		out <<= 18
		out |= golay_18_6_8_encode(rs_codeword[i])
	return out

# sequence of hamming encodings for LDU1 and LDU2
# argument is an integer
# returns an integer
def ldu_hamming(rs_codeword):
	out = 0
	for i in range(24):
		out <<= 10
		out |= hamming_10_6_3_encode(rs_codeword[i])
	return out

# sequence of golay encodings for xTDU
# argument is an integer
# returns an integer
def xtdu_golay(rs_codeword):
	out = 0
	for i in range(0, 24, 2):
		out <<= 24
		data = (rs_codeword[i] << 6) + rs_codeword[i+1]
		out |= golay_24_12_8_encode(data)
	return out

# interleave a sequence of 98 symbols (for trellis encoded data)
# argument is list of dibits
# returns list of dibits
def data_interleave(input):
	assert len(input) == 98
	output = []
	for j in range(0,97,8):
			output.extend(input[j:j+2])
	for i in range(2,7,2):
		for j in range(0,89,8):
			output.extend(input[i+j:i+j+2])
	return output

# 1/2 rate trellis encode a sequence of dibits
# argument is list of dibits
# returns list of dibits
def trellis_1_2_encode(input):
	# append flushing dibit
	input = list(input)
	input.append(0)

	output = []
	state = 0

	# state transition table, including constellation to dibit pair mapping
	table = (
		((0, 2), (3, 0), (0, 1), (3, 3)),
		((3, 2), (0, 0), (3, 1), (0, 3)),
		((2, 1), (1, 3), (2, 2), (1, 0)),
		((1, 1), (2, 3), (1, 2), (2, 0)))

	for i in range(len(input)):
		output.extend(table[state][input[i]])
		state = input[i]

	# return dibits
	return output

# 3/4 rate trellis encode a sequence of tribits
# argument is list of tribits
# returns list of dibits
def trellis_3_4_encode(input):
	# append flushing tribit
	input = list(input)
	input.append(0)

	output = []
	state = 0

	# state transition table, including constellation to dibit pair mapping
	table = (
		((0, 2), (3, 1), (3, 2), (0, 1), (1, 3), (2, 0), (2, 3), (1, 0)),
		((3, 2), (0, 1), (1, 3), (2, 0), (2, 3), (1, 0), (0, 2), (3, 1)),
		((2, 2), (1, 1), (1, 2), (2, 1), (3, 3), (0, 0), (0, 3), (3, 0)),
		((1, 2), (2, 1), (3, 3), (0, 0), (0, 3), (3, 0), (2, 2), (1, 1)),
		((3, 3), (0, 0), (0, 3), (3, 0), (2, 2), (1, 1), (1, 2), (2, 1)),
		((0, 3), (3, 0), (2, 2), (1, 1), (1, 2), (2, 1), (3, 3), (0, 0)),
		((1, 3), (2, 0), (2, 3), (1, 0), (0, 2), (3, 1), (3, 2), (0, 1)),
		((2, 3), (1, 0), (0, 2), (3, 1), (3, 2), (0, 1), (1, 3), (2, 0)))

	for i in range(len(input)):
		output.extend(table[state][input[i]])
		state = input[i]

	# return dibits
	return output

# 16 bit CRC_CCITT over 80 data bits
# argument is an integer
# returns an integer
def crc_ccitt(data):
	assert data >= 0
	assert data <= 0xffffffffffffffffffffL
	g = (1 << 12) | (1 << 5) | 1
	crc = 0;
	for i in range(79, -1, -1):
		crc <<= 1
		if (((crc >> 16) ^ (data >> i)) & 1):
			crc ^= g
	crc = (crc & 0xffff) ^ 0xffff
	return crc

# 32 bit CRC over variable number of data bits
# arguments are integers
# returns an integer
def crc_32(data, length):
	assert length >= 0
	assert length <= 4096
	assert data >= 0
	assert data < 2**length
	g = 0x04c11db7
	crc = 0;
	for i in range(length - 1, -1, -1):
		crc <<= 1
		if (((crc >> 32) ^ (data >> i)) & 1):
			crc ^= g
	crc = (crc & 0xffffffff) ^ 0xffffffff
	return crc

# 9 bit CRC over 7 bit serial number and 128 data bits
# arguments are integers
# returns an integer
def crc_9(serial, data):
	assert serial >= 0
	assert serial <= 0x7f
	assert data >= 0
	assert data <= 0xffffffffffffffffffffffffffffffffL
	data |= (serial << 128)
	g = (1 << 6) | (1 << 4) | (1 << 3) | 1
	crc = 0;
	for i in range(134, -1, -1):
		crc <<= 1
		if (((crc >> 9) ^ (data >> i)) & 1):
			crc ^= g
	crc = (crc & 0x1ff) ^ 0x1ff
	return crc


##############################
# construct parts of packets #
##############################

# arguments are integers
# returns list of dibits
def start_packet(nac, duid):
	assert nac <= 0xfff
	assert duid <= 0xf

	symbols = []

	# every packet gets a frame sync
	fs = 0x5575f5ff77ff
	symbols.extend(split_dibits(fs, 24))

	# add NID codeword
	nid = bch_64_16_23_encode((nac << 4) | duid)
	symbols.extend(split_dibits(nid, 32))

	return symbols

# arguments are integers
# returns an integer
def construct_lcf(p, sf, lco):
	text_out("\t\tLink Control Format:\n")

	assert p   <= 0x1
	assert sf  <= 0x1
	assert lco <= 0x3f

	lcf = p << 7
	lcf |= sf << 6
	lcf |= lco

	text_out("\t\t\tP   = %01x\n" % p)
	text_out("\t\t\tSF  = %01x\n" % sf)
	text_out("\t\t\tLCO = %02x\n" % lco)
	text_out("\t\t\tLCF = %02x\n" % lcf)
	return lcf

# arguments are integers
# returns an integer
def construct_svcopt(e, p, d, m, r, pri):
	text_out("\t\tService Options:\n")

	assert e   <= 0x1
	assert p   <= 0x1
	assert d   <= 0x1
	assert m   <= 0x1
	assert r   <= 0x1
	assert pri <= 0x7

	so = e << 7
	so |= p << 6
	so |= d << 5
	so |= m << 4
	so |= pri

	text_out("\t\t\tE      = %01x\n" % e)
	text_out("\t\t\tP      = %01x\n" % p)
	text_out("\t\t\tD      = %01x\n" % d)
	text_out("\t\t\tM      = %01x\n" % m)
	text_out("\t\t\tR      = %01x\n" % 0)
	text_out("\t\t\tPri    = %02x\n" % pri)
	text_out("\t\t\tSvcOpt = %02x\n" % so)
	return so

# arguments are integers
# returns an integer
def construct_lc(lco, mfid, svcopt, s, tgid, dst, src):
	text_out("\tLink Control Word:\n")

	assert lco    <= 0xff
	assert mfid   <= 0xff
	assert svcopt <= 0xff
	assert s      <= 0x1
	assert tgid   <= 0xffff
	assert dst    <= 0xffffff
	assert src    <= 0xffffff

	lcf = construct_lcf(0, 0, lco)
	lc = lcf << 64

	text_out("\t\tMFID  = %02x\n" % mfid)
	lc |= mfid << 56
	lc |= svcopt << 48

	# We only implement the formats listed in the Common Air Interface
	# specification.  For other formats, see TIA-102.AABF-B.
	if lco == 0:
		# group call
		# s = explicit source ID required
		text_out("\t\tS     = %01x\n" % s)
		lc |= s << 32
		text_out("\t\tTGID  = %04x\n" % tgid)
		lc |= tgid << 24
	elif lco == 3:
		# individual call
		text_out("\t\tTUID  = %06x\n" % dst)
		lc |= dst << 24
	else:
		sys.stderr.write("error: --lco must be 0 or 3\n")
		sys.exit(1)

	text_out("\t\tSUID  = %06x\n" % src)
	lc |= src

	text_out("\t\tLCW   = %018x\n" % lc)
	return lc

# arguments are integers
# returns an integer
def construct_es(mi, algid, kid):
	text_out("\tEncryption Sync Word:\n")

	assert mi    <= 0xffffffffffffffffffL
	assert algid <= 0xff
	assert kid   <= 0xffff

	es = mi << 24
	es |= algid << 16
	es |= kid

	text_out("\t\tMI    = %018x\n" % mi)
	text_out("\t\tALGID = %02x\n" % algid)
	text_out("\t\tKID   = %04x\n" % kid)
	text_out("\t\tESW   = %024x\n" % es)
	return es

# arguments are integers
# returns an integer
def construct_tsbk(lb, p, opcode, mfid, arg):
	text_out("\tTrunking Signaling Block:\n")

	assert lb     <= 0x1
	assert p      <= 0x1
	assert opcode <= 0x3f
	assert mfid   <= 0xff
	assert arg    <= 0xffffffffffffffffL

	tsbk = lb      << 95
	tsbk |= p      << 94
	tsbk |= opcode << 88
	tsbk |= mfid   << 80
	tsbk |= arg    << 16

	crc = crc_ccitt(tsbk >> 16)
	tsbk |= crc

	text_out("\t\tLB        = %01x\n" % lb)
	text_out("\t\tP         = %01x\n" % p)
	text_out("\t\tOpcode    = %02x\n" % opcode)
	text_out("\t\tMFID      = %02x\n" % mfid)
	text_out("\t\tArguments = %016x\n" % arg)
	text_out("\t\tCRC       = %04x\n" % crc)
	text_out("\t\tTSBK      = %024x\n" % tsbk)
	return tsbk

# arguments are integers
# returns an integer
def construct_cpduh(an, io, sapid, mfid, llid, fmf,
		btf, poc, syn, ns, fsnf, dho):
	text_out("\tConfirmed Packet Data Unit Header:\n")

	assert an    <= 0x1
	assert io    <= 0x1
	assert sapid <= 0x3f
	assert mfid  <= 0xff
	assert llid  <= 0xffffff
	assert fmf   <= 0x1
	assert btf   <= 0x7f
	assert poc   <= 0x1f
	assert syn   <= 0x1
	assert ns    <= 0x7
	assert fsnf  <= 0xf
	assert dho   <= 0x3f

	duformat = 0x16

	hdr = an        << 94 # 1 indicates confirmation desired
	hdr |= io       << 93 # 1 for outbound, 0 for inbound
	hdr |= duformat << 88
	hdr |= 0x3      << 86
	hdr |= sapid    << 80 # SAP Identifier
	hdr |= mfid     << 72
	hdr |= llid     << 48 # Logical Link ID
	hdr |= fmf      << 47 # Full Message Flag
	hdr |= btf      << 40 # blocks to follow
	hdr |= poc      << 32 # pad octet count
	hdr |= syn      << 31
	hdr |= ns       << 28 # N(S) sequence number
	hdr |= fsnf     << 24 # Fragment Sequence Number Field
	hdr |= dho      << 16 # Data Header Offset

	crc = crc_ccitt(hdr >> 16)
	hdr |= crc

	text_out("\t\tA/N    = %01x\n" % an)
	text_out("\t\tI/O    = %01x\n" % io)
	text_out("\t\tFormat = %02x\n" % duformat)
	text_out("\t\tSAP    = %02x\n" % sapid)
	text_out("\t\tMFID   = %02x\n" % mfid)
	text_out("\t\tLLID   = %06x\n" % llid)
	text_out("\t\tFMF    = %01x\n" % fmf)
	text_out("\t\tBTF    = %02x\n" % btf)
	text_out("\t\tPOC    = %02x\n" % poc)
	text_out("\t\tSyn    = %01x\n" % syn)
	text_out("\t\tN(S)   = %01x\n" % ns)
	text_out("\t\tFSNF   = %01x\n" % fsnf)
	text_out("\t\tDHO    = %02x\n" % dho)
	text_out("\t\tCRC    = %04x\n" % crc)
	text_out("\t\tHeader = %024x\n" % hdr)
	return hdr

# arguments are integers
# returns an integer
def construct_rpduh(io, rclass, rtype, rstatus, mfid, llid, x, btf, sllid):
	text_out("\tResponse Packet Data Unit Header:\n")

	assert io      <= 0x1
	assert rclass  <= 0x3
	assert rtype   <= 0x7
	assert rstatus <= 0x7
	assert mfid    <= 0xff
	assert llid    <= 0xffffff
	assert btf     <= 0x7f
	assert sllid   <= 0xffffff
	if x:
		assert sllid == 0

	duformat = 0x3

	hdr = io        << 93 # 1 for outbound, 0 for inbound
	hdr |= duformat << 88
	hdr |= rclass   << 86 # response class
	hdr |= rtype    << 83 # response types
	hdr |= rstatus  << 80 # response status
	hdr |= mfid     << 72
	hdr |= llid     << 48 # Logical Link ID
	hdr |= x        << 47 # X
	hdr |= btf      << 40 # blocks to follow
	hdr |= sllid    << 16 # Source Logical Link ID

	crc = crc_ccitt(hdr >> 16)
	hdr |= crc

	text_out("\t\tI/O    = %01x\n" % io)
	text_out("\t\tFormat = %02x\n" % duformat)
	text_out("\t\tClass  = %01x\n" % rclass)
	text_out("\t\tType   = %01x\n" % rtype)
	text_out("\t\tStatus = %01x\n" % rstatus)
	text_out("\t\tMFID   = %02x\n" % mfid)
	text_out("\t\tLLID   = %06x\n" % llid)
	text_out("\t\tX      = %01x\n" % x)
	text_out("\t\tBTF    = %02x\n" % btf)
	text_out("\t\tSLLID  = %06x\n" % sllid)
	text_out("\t\tCRC    = %04x\n" % crc)
	text_out("\t\tHeader = %024x\n" % hdr)
	return hdr

# arguments are integers
# returns an integer
def construct_upduh(io, sapid, mfid, llid, btf, poc, dho):
	text_out("\tUnconfirmed Packet Data Unit Header:\n")

	assert io    <= 0x1
	assert sapid <= 0x3f
	assert mfid  <= 0xff
	assert llid  <= 0xffffff
	assert btf   <= 0x7f
	assert poc   <= 0x1f
	assert dho   <= 0x3f

	duformat = 0x15

	hdr = io        << 93 # 1 for outbound, 0 for inbound
	hdr |= duformat << 88
	hdr |= 0x3      << 86
	hdr |= sapid    << 80 # SAP Identifier
	hdr |= mfid     << 72
	hdr |= llid     << 48 # Logical Link ID
	hdr |= 0x1      << 47
	hdr |= btf      << 40 # blocks to follow
	hdr |= poc      << 32 # pad octet count
	hdr |= dho      << 16 # Data Header Offset

	crc = crc_ccitt(hdr >> 16)
	hdr |= crc

	text_out("\t\tI/O    = %01x\n" % io)
	text_out("\t\tFormat = %02x\n" % duformat)
	text_out("\t\tSAP    = %02x\n" % sapid)
	text_out("\t\tMFID   = %02x\n" % mfid)
	text_out("\t\tLLID   = %06x\n" % llid)
	text_out("\t\tBTF    = %02x\n" % btf)
	text_out("\t\tPOC    = %02x\n" % poc)
	text_out("\t\tDHO    = %02x\n" % dho)
	text_out("\t\tCRC    = %04x\n" % crc)
	text_out("\t\tHeader = %024x\n" % hdr)
	return hdr

# arguments are integers
# returns an integer
def construct_ambth(io, sapid, mfid, llid, btf, opcode, dbtm):
	text_out("\tAlternate Multiple Block Trunking Header:\n")

	assert io     <= 0x1
	assert sapid  <= 0x3f
	assert mfid   <= 0xff
	assert llid   <= 0xffffff
	assert btf    <= 0x7f
	assert opcode <= 0x3f
	assert dbtm   <= 0xffff

	duformat = 0x17

	hdr = io        << 93 # 1 for outbound, 0 for inbound
	hdr |= duformat << 88
	hdr |= 0x3      << 86
	hdr |= sapid    << 80 # SAP Identifier
	hdr |= mfid     << 72
	hdr |= llid     << 48 # Logical Link ID
	hdr |= 0x1      << 47
	hdr |= btf      << 40 # blocks to follow
	hdr |= opcode   << 32
	hdr |= dbtm     << 16 # defined by trunking messages

	crc = crc_ccitt(hdr >> 16)
	hdr |= crc

	text_out("\t\tI/O    = %01x\n" % io)
	text_out("\t\tFormat = %02x\n" % duformat)
	text_out("\t\tSAP    = %02x\n" % sapid)
	text_out("\t\tMFID   = %02x\n" % mfid)
	text_out("\t\tLLID   = %06x\n" % llid)
	text_out("\t\tBTF    = %02x\n" % btf)
	text_out("\t\tOpcode = %02x\n" % opcode)
	text_out("\t\tDBTM   = %04x\n" % dbtm)
	text_out("\t\tCRC    = %04x\n" % crc)
	text_out("\t\tHeader = %024x\n" % hdr)
	return hdr

# arguments are integers
# returns an integer
def construct_ef(efclass, operand, arguments):
	text_out("\tExtended Function:\n")
	
	assert efclass   <= 0xff
	assert operand   <= 0xff
	assert arguments <= 0xffffff

	ef = efclass  << 32
	ef |= operand << 24
	ef |= arguments

	text_out("\t\tClass     = %02x\n" % efclass)
	text_out("\t\tOperand   = %02x\n" % operand)
	text_out("\t\tArguments = %06x\n" % arguments)
	return ef


##############################
# construct complete packets #
##############################

# Header Data Unit
def construct_hdu(nac, ss, mi, mfid, algid, kid, tgid):
	text_out("Header Data Unit:\n")

	assert nac   <= 0xfff
	assert ss    <= 0x3
	assert mi    <= 0xffffffffffffffffffL
	assert algid <= 0xff
	assert kid   <= 0xffff
	assert tgid  <= 0xffff

	duid  = 0x0

	ssyms = (ss,) * 11

	symbols = start_packet(nac, duid)

	# HDU codeword
	hdr = 0
	hdr |= mi    << 48
	hdr |= mfid  << 40
	hdr |= algid << 32
	hdr |= kid   << 16
	hdr |= tgid

	rs_codeword = rs_36_20_17_encode(hdr)
	symbols.extend(split_dibits(header_golay(rs_codeword), 324))

	text_out("\tDUID  = %01x\n" % duid)
	text_out("\tNAC   = %03x\n" % nac)
	text_out("\tSSym  = %d %d %d %d %d %d %d %d %d %d %d\n" % ssyms)
	text_out("\tMI    = %018x\n" % mi)
	text_out("\tMFID  = %02x\n" % mfid)
	text_out("\tALGID = %02x\n" % algid)
	text_out("\tKID   = %04x\n" % kid)
	text_out("\tTGID  = %04x\n" % tgid)
	text_out("\tSymbol data:\n")
	print_spec(insert_status(symbols, ssyms))

# Logical Link Data Unit 1
def construct_ldu1(nac, ss, imbe, lsd, lco, mfid, svcopt, s, tgid, dst, src):
	text_out("Logical Link Data Unit 1:\n")

	assert nac    <= 0xfff
	assert ss     <= 0x3
	assert imbe   <= 0xffffffffffffffffffffffffffffffffffffL
	assert lsd    <= 0xffffffff
	assert lco    <= 0xff
	assert mfid   <= 0xff
	assert svcopt <= 0xff
	assert s      <= 0x1
	assert tgid   <= 0xffff
	assert dst    <= 0xffffff
	assert src    <= 0xffffff

	duid  = 0x5

	ssyms = (ss,) * 24

	text_out("\tDUID  = %01x\n" % duid)
	text_out("\tNAC   = %03x\n" % nac)
	text_out("\tSSym  = %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d\n" % ssyms)
	#text_out("\tIMBE  = %023x\n" % imbe)
	text_out("\tIMBE  = %036x\n" % imbe)
	text_out("\tLSD   = %08x\n" % lsd)

	symbols = start_packet(nac, duid)

	# Link Control Word
	lc = construct_lc(lco, mfid, svcopt, s, tgid, dst, src)
	rs_codeword = rs_24_12_13_encode(lc)
	lcw_syms = split_dibits(ldu_hamming(rs_codeword), 120)

	# Low Speed Data
	lsd_syms = split_dibits(ldu1_cyclic(lsd), 16)

	symbols.extend(split_dibits(imbe, 72))
	symbols.extend(split_dibits(imbe ^ 2, 72)) # flipping sync bit
	symbols.extend(lcw_syms[0:20])
	symbols.extend(split_dibits(imbe, 72))
	symbols.extend(lcw_syms[20:40])
	symbols.extend(split_dibits(imbe ^ 2, 72))
	symbols.extend(lcw_syms[40:60])
	symbols.extend(split_dibits(imbe, 72))
	symbols.extend(lcw_syms[60:80])
	symbols.extend(split_dibits(imbe ^ 2, 72))
	symbols.extend(lcw_syms[80:100])
	symbols.extend(split_dibits(imbe, 72))
	symbols.extend(lcw_syms[100:120])
	symbols.extend(split_dibits(imbe ^ 2, 72))
	symbols.extend(lsd_syms)
	symbols.extend(split_dibits(imbe, 72))

	text_out("\tSymbol data:\n")
	print_spec(insert_status(symbols, ssyms))

# Logical Link Data Unit 2
def construct_ldu2(nac, ss, imbe, lsd, mi, algid, kid):
	text_out("Logical Link Data Unit 2:\n")

	assert nac   <= 0xfff
	assert ss    <= 0x3
	assert imbe  <= 0xffffffffffffffffffffffffffffffffffffL
	assert lsd   <= 0xffffffff
	assert mi    <= 0xffffffffffffffffffL
	assert algid <= 0xff
	assert kid   <= 0xffff

	duid  = 0xa

	ssyms = (ss,) * 24

	text_out("\tDUID  = %01x\n" % duid)
	text_out("\tNAC   = %03x\n" % nac)
	text_out("\tSSym  = %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d\n" % ssyms)
	text_out("\tIMBE  = %036x\n" % imbe)
	text_out("\tLSD   = %08x\n" % lsd)

	symbols = start_packet(nac, duid)

	# Encryption Sync Word
	es = construct_es(mi, algid, kid)
	rs_codeword = rs_24_16_9_encode(es)
	es_syms = split_dibits(ldu_hamming(rs_codeword), 120)

	# Low Speed Data
	lsd_syms = split_dibits(ldu2_cyclic(lsd), 16)

	symbols.extend(split_dibits(imbe ^ 2, 72)) # flipping sync bit
	symbols.extend(split_dibits(imbe, 72))
	symbols.extend(es_syms[0:20])
	symbols.extend(split_dibits(imbe ^ 2, 72))
	symbols.extend(es_syms[20:40])
	symbols.extend(split_dibits(imbe, 72))
	symbols.extend(es_syms[40:60])
	symbols.extend(split_dibits(imbe ^ 2, 72))
	symbols.extend(es_syms[60:80])
	symbols.extend(split_dibits(imbe, 72))
	symbols.extend(es_syms[80:100])
	symbols.extend(split_dibits(imbe ^ 2, 72))
	symbols.extend(es_syms[100:120])
	symbols.extend(split_dibits(imbe, 72))
	symbols.extend(lsd_syms)
	symbols.extend(split_dibits(imbe ^ 2, 72))

	text_out("\tSymbol data:\n")
	print_spec(insert_status(symbols, ssyms))

# Simple Terminator Data Unit
def construct_stdu(nac, ss):
	text_out("Simple Terminator Data Unit:\n")

	assert nac <= 0xfff
	assert ss  <= 0x3

	duid  = 0x3

	ssyms = (ss,) * 2

	symbols = start_packet(nac, duid)

	text_out("\tDUID  = %01x\n" % duid)
	text_out("\tNAC   = %03x\n" % nac)
	text_out("\tSSym  = %d %d\n" % ssyms)
	text_out("\tSymbol data:\n")
	print_spec(insert_status(symbols, ssyms))

# Terminator Data Unit with Link Control
#
# aka Extended Terminator Data Unit
def construct_xtdu(nac, ss, lco, mfid, svcopt, s, tgid, dst, src):
	text_out("Terminator Data Unit with Link Control:\n")

	assert nac    <= 0xfff
	assert ss     <= 0x3
	assert lco    <= 0xff
	assert mfid   <= 0xff
	assert svcopt <= 0xff
	assert s      <= 0x1
	assert tgid   <= 0xffff
	assert dst    <= 0xffffff
	assert src    <= 0xffffff

	duid  = 0xf

	ssyms = (ss,) * 6

	text_out("\tDUID  = %01x\n" % duid)
	text_out("\tNAC   = %03x\n" % nac)
	text_out("\tSSym  = %d %d %d %d %d %d\n" % ssyms)

	symbols = start_packet(nac, duid)

	lc = construct_lc(lco, mfid, svcopt, s, tgid, dst, src)
	rs_codeword = rs_24_12_13_encode(lc)
	symbols.extend(split_dibits(xtdu_golay(rs_codeword), 144))

	text_out("\tSymbol data:\n")
	print_spec(insert_status(symbols, ssyms))

# Trunking Signaling Data Unit
#
# The standards variously refer to this packet type as "Trunking Signaling Data
# Unit" or "TSBK" or "abbreviated format" or, perhaps most often, "single block
# format" even though it may consist of as many as three actual Trunking
# Signaling Blocks (TSBKs).
def construct_tsdu(nac, ss, blocks, mfid, opcode, arg):
	text_out("Trunking Signaling Data Unit:\n")

	assert nac    <= 0xfff
	assert ss     <= 0x3
	assert blocks <= 0x3
	assert mfid   <= 0xff
	assert opcode <= 0x3f
	assert arg    <= 0xffffffffffffffffL

	duid  = 0x7

	numss = (56 + (blocks * 98) + 34) / 35
	ssyms = (ss,) * numss

	text_out("\tDUID  = %01x\n" % duid)
	text_out("\tNAC   = %03x\n" % nac)
	text_out("\tSSym  =")
	for i in range(numss):
		text_out(" %d" % ssyms[i])
	text_out("\n")

	symbols = start_packet(nac, duid)

	# append TSBKs
	for i in range(blocks):
		last_block = (i == (blocks - 1))
		tsbk = construct_tsbk(last_block, 0, opcode, mfid, arg)
		symbols.extend(data_interleave(trellis_1_2_encode(split_dibits(tsbk, 48))))

	text_out("\tSymbol data:\n")
	print_spec(insert_status(symbols, ssyms))

# Trunking Signaling Data Unit
#
# The standards variously refer to this packet type as "Trunking Signaling Data
# Unit" or "TSBK" or "abbreviated format" or, perhaps most often, "single block
# format" even though it may consist of as many as three actual Trunking
# Signaling Blocks (TSBKs).
#
##### build tsdu with 3 separate tsbk's
def construct_tsdu3(nac, ss, blocks, mfid, opcodes, args):
	text_out("Trunking Signaling Data Unit:\n")

	assert nac    <= 0xfff
	assert ss     <= 0x3
	assert blocks <= 0x3
	assert mfid   <= 0xff

	assert len(opcodes) == blocks
	assert len(args) == blocks
	for opcode in opcodes:
		assert opcode <= 0x3f
	for arg in args:
		assert arg    <= 0xffffffffffffffffL

	duid  = 0x7

	numss = (56 + (blocks * 98) + 34) / 35
	ssyms = (ss,) * numss

	text_out("\tDUID  = %01x\n" % duid)
	text_out("\tNAC   = %03x\n" % nac)
	text_out("\tSSym  =")
	for i in range(numss):
		text_out(" %d" % ssyms[i])
	text_out("\n")

	symbols = start_packet(nac, duid)

	# append TSBKs
	for i in range(blocks):
		last_block = (i == (blocks - 1))
		tsbk = construct_tsbk(last_block, 0, opcodes[i], mfid, args[i])
		symbols.extend(data_interleave(trellis_1_2_encode(split_dibits(tsbk, 48))))

	text_out("\tSymbol data:\n")
	print_spec(insert_status(symbols, ssyms))

# Confirmed Packet Data Unit
def construct_cpdu(nac, ss, data, length, an, io, sapid,
		mfid, llid, ns, fsnf, dho):
	text_out("Confirmed Packet Data Unit:\n")

	assert nac   <= 0xfff
	assert ss    <= 0x3
	assert an    <= 0x1
	assert io    <= 0x1
	assert sapid <= 0x3f
	assert mfid  <= 0xff
	assert llid  <= 0xffffff
	assert ns    <= 0x7
	assert fsnf  <= 0xf
	assert dho   <= 0x3f
	assert data.bit_length() <= (length * 8)

	duid = 0xc

	symbols = start_packet(nac, duid)

	# account for length of packet CRC appended to data
	length += 4
	blocks = (length + 15) / 16
	assert blocks <= 127

	# account for padding to end of next full block
	pad_octets = (blocks * 16) - length
	length += pad_octets

	# add padding
	data <<= (pad_octets * 8)

	# I'm assuming the packet CRC should be part of the data used to compute
	# the block CRC below, but the specification is unclear on this point.
	packet_crc = crc_32(data, (length - 4) * 8)
	data <<= (4 * 8)
	data |= packet_crc

	numss = (56 + ((blocks + 1) * 98) + 34) / 35
	ssyms = (ss,) * numss

	text_out("\tDUID = %01x\n" % duid)
	text_out("\tNAC  = %03x\n" % nac)
	text_out("\tSSym =")
	for i in range(numss):
		text_out(" %d" % ssyms[i])
	text_out("\n")
	text_out("\tCRC  = %08x\n" % packet_crc)
	text_out("\tData = %x\n" % data)

	# Certain cases may require more sophisticated handling of FMF and Syn
	# flags than we support.
	fmf = 1
	syn = 0
	header = construct_cpduh(an, io, sapid, mfid, llid, fmf,
			blocks, pad_octets, syn, ns, fsnf, dho)
	
	symbols.extend(data_interleave(trellis_1_2_encode(
			split_dibits(header, 48))))

	for i in range(blocks):
		text_out("\tConfirmed Packet Data Unit Block:\n")
		cpdu_block = (data >> (16 * 8 *
				(blocks - i - 1))) & 0xffffffffffffffffffffffffffffffffL

		# More sophisticated serial number generation required
		# for retransmissions.
		serial = i
		block_crc = crc_9(serial, cpdu_block)

		text_out("\t\tSerial = %02x\n" % serial)
		text_out("\t\tCRC    = %03x\n" % block_crc)
		text_out("\t\tData   = %032x\n" % cpdu_block)

		cpdu_block |= serial    << 137
		cpdu_block |= block_crc << 128

		symbols.extend(data_interleave(trellis_3_4_encode(
				split_tribits(cpdu_block, 48))))

	text_out("\tSymbol data:\n")
	print_spec(insert_status(symbols, ssyms))

# Response Packet Data Unit
def construct_rpdu(nac, ss, data, length, io, rclass, rtype,
		rstatus, mfid, llid, x, sllid):
	text_out("Response Packet Data Unit:\n")

	assert nac     <= 0xfff
	assert ss      <= 0x3
	assert io      <= 0x1
	assert rclass  <= 0x3
	assert rtype   <= 0x7
	assert rstatus <= 0x7
	assert mfid    <= 0xff
	assert llid    <= 0xffffff
	if x:
		assert sllid == 0
	assert sllid   <= 0xffffff
	assert data.bit_length() <= (length * 8)
	# We only support zero or one data blocks.  The specification
	# says there can be two, but the construction of a two block
	# response packet is unclear.
	assert (length == 0) or (length == 8)

	duid = 0xc

	symbols = start_packet(nac, duid)

	if (length > 0):
		# account for length of packet CRC appended to data
		length += 4
		blocks = (length + 11) / 12

		packet_crc = crc_32(data, (length - 4) * 8)
		data <<= (4 * 8)
		data |= packet_crc
	else:
		blocks = 0

	numss = (56 + ((blocks + 1) * 98) + 34) / 35
	ssyms = (ss,) * numss

	text_out("\tDUID = %01x\n" % duid)
	text_out("\tNAC  = %03x\n" % nac)
	text_out("\tSSym =")
	for i in range(numss):
		text_out(" %d" % ssyms[i])
	text_out("\n")
	if (blocks > 0):
		text_out("\tCRC  = %08x\n" % packet_crc)
		text_out("\tData = %x\n" % data)

	header = construct_rpduh(io, rclass, rtype, rstatus, mfid,
			llid, x, blocks, sllid)
	
	symbols.extend(data_interleave(trellis_1_2_encode(
			split_dibits(header, 48))))

	for i in range(blocks):
		text_out("\tResponse Packet Data Unit Block:\n")
		rpdu_block = (data >> (12 * 8 *
				(blocks - i - 1))) & 0xffffffffffffffffffffffffL
		text_out("\t\tData   = %024x\n" % rpdu_block)

		# I'm assuming 1/2 rate trellis encoding based on the length
		# of the block.  The specification doesn't say.
		symbols.extend(data_interleave(trellis_1_2_encode(
				split_dibits(rpdu_block, 48))))

	text_out("\tSymbol data:\n")
	print_spec(insert_status(symbols, ssyms))

# Unconfirmed Packet Data Unit
def construct_updu(nac, ss, data, length, io, sapid, mfid, llid, dho):
	text_out("Unconfirmed Packet Data Unit:\n")

	assert nac   <= 0xfff
	assert ss    <= 0x3
	assert io    <= 0x1
	assert sapid <= 0x3f
	assert mfid  <= 0xff
	assert llid  <= 0xffffff
	assert dho   <= 0x3f
	assert data.bit_length() <= (length * 8)

	duid = 0xc

	symbols = start_packet(nac, duid)

	# account for length of packet CRC appended to data
	length += 4
	blocks = (length + 11) / 12
	assert blocks <= 127

	# account for padding to end of next full block
	pad_octets = (blocks * 12) - length
	length += pad_octets

	# add padding
	data <<= (pad_octets * 8)

	packet_crc = crc_32(data, (length - 4) * 8)
	data <<= (4 * 8)
	data |= packet_crc

	numss = (56 + ((blocks + 1) * 98) + 34) / 35
	ssyms = (ss,) * numss

	text_out("\tDUID = %01x\n" % duid)
	text_out("\tNAC  = %03x\n" % nac)
	text_out("\tSSym =")
	for i in range(numss):
		text_out(" %d" % ssyms[i])
	text_out("\n")
	text_out("\tCRC  = %08x\n" % packet_crc)
	text_out("\tData = %x\n" % data)

	header = construct_upduh(io, sapid, mfid, llid, blocks, pad_octets, dho)
	
	symbols.extend(data_interleave(trellis_1_2_encode(
			split_dibits(header, 48))))

	for i in range(blocks):
		text_out("\tUnconfirmed Packet Data Unit Block:\n")
		updu_block = (data >> (12 * 8 *
				(blocks - i - 1))) & 0xffffffffffffffffffffffffL
		text_out("\t\tData   = %024x\n" % updu_block)
		symbols.extend(data_interleave(trellis_1_2_encode(
				split_dibits(updu_block, 48))))

	text_out("\tSymbol data:\n")
	print_spec(insert_status(symbols, ssyms))

# Alternate Multiple Block Trunking (MBT) Control Packet
#
# This is sometimes called things like "multiblock trunking control" and is a
# variation of the Unconfirmed Packet Data Unit.
def construct_ambt(nac, ss, data, length, io, sapid, mfid, llid, opcode, dbtm):
	text_out("Alternate Multiple Block Trunking (MBT) Control Packet:\n")

	assert nac   <= 0xfff
	assert ss    <= 0x3
	assert io    <= 0x1
	assert sapid <= 0x3f
	assert mfid  <= 0xff
	assert llid  <= 0xffffff
	assert opcode <= 0x3f
	assert dbtm   <= 0xffff
	assert data.bit_length() <= (length * 8)
	assert (sapid == 0x3d) or (sapid == 0x3f)

	duid = 0xc

	symbols = start_packet(nac, duid)

	# account for length of packet CRC appended to data
	length += 4
	blocks = (length + 11) / 12
	assert blocks <= 3

	# make sure the data fill the blocks
	extra = (blocks * 12) - length
	assert extra == 0

	packet_crc = crc_32(data, (length - 4) * 8)
	data <<= (4 * 8)
	data |= packet_crc

	numss = (56 + ((blocks + 1) * 98) + 34) / 35
	ssyms = (ss,) * numss

	text_out("\tDUID = %01x\n" % duid)
	text_out("\tNAC  = %03x\n" % nac)
	text_out("\tSSym =")
	for i in range(numss):
		text_out(" %d" % ssyms[i])
	text_out("\n")
	text_out("\tCRC  = %08x\n" % packet_crc)
	text_out("\tData = %x\n" % data)

	header = construct_ambth(io, sapid, mfid, llid, blocks, opcode, dbtm)
	
	symbols.extend(data_interleave(trellis_1_2_encode(
			split_dibits(header, 48))))

	for i in range(blocks):
		text_out("\tMultiple Block Trunking Block:\n")
		ambt_block = (data >> (12 * 8 *
				(blocks - i - 1))) & 0xffffffffffffffffffffffffL
		text_out("\t\tData   = %024x\n" % ambt_block)
		symbols.extend(data_interleave(trellis_1_2_encode(
				split_dibits(ambt_block, 48))))

	text_out("\tSymbol data:\n")
	print_spec(insert_status(symbols, ssyms))


#############################
# construct special packets #
#############################

# These functions for specific control channel packets are provided to serve as
# an example of how this software may be extended to support the crafting of
# various data packets.  Limited testing has been done for most of these
# because the specifications do not include test vectors for them.  Those that
# have been given command line options and include example usage in the
# comments below have been tested successfully as conventional control messages
# (see TIA-102.AABG) in live operation.

# Radio Unit Monitor example usage:
#   p25craft.py --rum --src 0xfffffd --dst 0x000001 --ss 1
def construct_rad_mon_cmd(nac, ss, src, dst):
	text_out("Special Packet: Radio Unit Monitor Command\n")

	opcode = 0x1d # Radio Unit Monitor Command
	txtime = 0x00 # transmit time in seconds
	sm = 0        # silent mode
	txmult = 0x3  # multiply radio's configured tx duration
	args = txtime  << 56
	args |= sm     << 55
	args |= txmult << 48
	args |= src    << 24
	args |= dst
	construct_tsdu(nac, ss, 1, 0x00, opcode, args)

def construct_ack_rsp_fne(nac, ss, svctype, src, dst):
	text_out("Special Packet: Acknowledge Response - FNE\n")

	# hard coded example parameters
	aiv = 0
	ex = 0
	wacnid = 0x00000
	sysid = 0x000

	opcode = 0x20 # Acknowledge Response - FNE

	if ex == 1:
		addtlinfo = wacnid << 12
		addtlinfo |= sysid
	else:
		addtlinfo = src

	args = aiv        << 63 # Additional Information Valid Flag 
	args |= ex        << 62 # extended address
	args |= svctype   << 56
	args |= addtlinfo << 24
	args |= dst
	construct_tsdu(nac, ss, 1, 0x00, opcode, args)

def construct_ack_rsp_u(nac, ss, src, dst):
	text_out("Special Packet: Acknowledge Response - Unit\n")

	opcode = 0x20 # Acknowledge Response - Unit
	args = svctype << 56
	args |= dst    << 24
	args |= src
	construct_tsdu(nac, ss, 1, 0x00, opcode, args)

def construct_rad_mon_req(nac, ss, src, dst):
	text_out("Special Packet: Radio Unit Monitor Request\n")

	opcode = 0x1d # Radio Unit Monitor Request
	txtime = 0x00 # transmit time in seconds
	sm = 0        # silent mode
	txmult = 0x3  # multiply radio's configured tx duration
	args = txtime  << 56
	args |= sm     << 55
	args |= txmult << 48
	args |= dst    << 24
	args |= src
	construct_tsdu(nac, ss, 1, 0x00, opcode, args)

def construct_call_alrt_req(nac, ss, src, dst):
	text_out("Special Packet: Call Alert Request\n")

	opcode = 0x1f # Call Alert Request
	args = dst << 24
	args |= src
	construct_tsdu(nac, ss, 1, 0x00, opcode, args)

def construct_can_srv_req(nac, ss, svctype, src, dst):
	text_out("Special Packet: Cancel Service Request\n")

	# hard coded example parameters
	aiv = 1
	reason = 0x00 # no reason code
	addtlinfo = dst

	opcode = 0x23 # Cancel Service Request
	args = aiv        << 63 # Additional Information Valid Flag 
	args |= svctype   << 56
	args |= reason    << 48
	args |= addtlinfo << 24
	args |= src
	construct_tsdu(nac, ss, 1, 0x00, opcode, args)

def construct_emrg_alrm_req(nac, ss, src, tgid):
	text_out("Special Packet: Emergency Alarm Request\n")

	opcode = 0x27 # Emergency Alarm Request
	args = tgid << 24
	args |= src
	construct_tsdu(nac, ss, 1, 0x00, opcode, args)

# It seems to make more sense to use EXT_FNCT_RSP for the following command
# ACKs, but they are included here in EXT_FNCT_CMD form as well because the
# spec appears to allow it.

def construct_ext_fnct_cmd_class0(nac, ss, operand, src, dst):
	ef = construct_ef(0x00, operand, src)
	opcode = 0x24 # Extended Function Command
	arg = ef << 24
	arg |= dst
	construct_tsdu(nac, ss, 1, 0x00, opcode, arg)

# Inhibit example usage:
#   p25craft.py --inhibit --src 0xfffffd --dst 0x000001 --ss 1
def construct_ext_fnct_cmd_inhibit(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Inhibit\n")
	operand = 0x7f # Radio Inhibit
	construct_ext_fnct_cmd_class0(nac, ss, operand, src, dst)

def construct_ext_fnct_cmd_inhibit_ack(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Inhibit ACK\n")
	operand = 0xff # Radio Inhibit ACK
	construct_ext_fnct_cmd_class0(nac, ss, operand, src, dst)

# Uninhibit example usage:
#   p25craft.py --uninhibit --src 0xfffffd --dst 0x000001 --ss 1
def construct_ext_fnct_cmd_uninhibit(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Uninhibit\n")
	operand = 0x7e # Radio Uninhibit
	construct_ext_fnct_cmd_class0(nac, ss, operand, src, dst)

def construct_ext_fnct_cmd_uninhibit_ack(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Uninhibit ACK\n")
	operand = 0xfe # Radio Uninhibit ACK
	construct_ext_fnct_cmd_class0(nac, ss, operand, src, dst)

def construct_ext_fnct_cmd_check(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Radio Check\n")
	operand = 0x00 # Radio Check
	construct_ext_fnct_cmd_class0(nac, ss, operand, src, dst)

def construct_ext_fnct_cmd_check_ack(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Radio Check ACK\n")
	operand = 0x80 # Radio Check ACK
	construct_ext_fnct_cmd_class0(nac, ss, operand, src, dst)

# It seems to make more sense to use EXT_FNCT_CMD for the following commands,
# but they are included here in EXT_FNCT_RSP form as well because the spec
# appears to allow it.

def construct_ext_fnct_rsp_class0(nac, ss, operand, src, dst):
	ef = construct_ef(0x00, operand, dst)
	opcode = 0x24 # Extended Function Response
	arg = ef << 24
	arg |= src
	construct_tsdu(nac, ss, 1, 0x00, opcode, arg)

def construct_ext_fnct_rsp_inhibit(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Inhibit\n")
	operand = 0x7f # Radio Inhibit
	construct_ext_fnct_rsp_class0(nac, ss, operand, src, dst)

def construct_ext_fnct_rsp_inhibit_ack(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Inhibit ACK\n")
	operand = 0xff # Radio Inhibit ACK
	construct_ext_fnct_rsp_class0(nac, ss, operand, src, dst)

def construct_ext_fnct_rsp_uninhibit(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Uninhibit\n")
	operand = 0x7e # Radio Uninhibit
	construct_ext_fnct_rsp_class0(nac, ss, operand, src, dst)

def construct_ext_fnct_rsp_uninhibit_ack(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Uninhibit ACK\n")
	operand = 0xfe # Radio Uninhibit ACK
	construct_ext_fnct_rsp_class0(nac, ss, operand, src, dst)

def construct_ext_fnct_rsp_check(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Radio Check\n")
	operand = 0x00 # Radio Check
	construct_ext_fnct_rsp_class0(nac, ss, operand, src, dst)

def construct_ext_fnct_rsp_check_ack(nac, ss, src, dst):
	text_out("Special Packet: Extended Function Command - Radio Check ACK\n")
	operand = 0x80 # Radio Check ACK
	construct_ext_fnct_rsp_class0(nac, ss, operand, src, dst)

def format_rfss_status_broadcast(lra, r, a, system_id, subsystem_id, site_id, channel, ssclass):
	assert lra       <= 0xff
	assert r         <= 1
	assert a         <= 1
	assert system_id <= 0xfff
	assert site_id   <= 0xff
	assert channel   <= 0xffff
	assert ssclass     <= 0xff

	opcode = 0x3a
	args = lra
	args = (args << 16) + (r << 13) + (a << 12) + system_id
	args = (args << 8) + subsystem_id
	args = (args << 8) + site_id
	args = (args << 16) + channel
	args = (args << 8) + ssclass
	return opcode, args

def format_network_status_broadcast(lra, wacn, system_id, channel, ssclass):
	assert lra       <= 0xff
	assert wacn      <= 0xfffff
	assert system_id <= 0xfff
	assert channel   <= 0xffff
	assert ssclass     <= 0xff

	opcode = 0x3b
	args = lra
	args = (args << 20) + wacn
	args = (args << 12) + system_id
	args = (args << 16) + channel
	args = (args << 8) + ssclass
	return opcode, args

def format_iden_up(identifier, bw, tx_offset, spacing, frequency):
	assert identifier <= 0xf
	assert bw         <= 0x1ff
	assert tx_offset  <= 0x1ff
	assert spacing    <= 0x3ff
	assert frequency  <= 0xffffffff

	opcode = 0x3d
	args = identifier
	args = (args << 9) + bw
	args = (args << 9) + tx_offset
	args = (args << 10) + spacing
	args = (args << 32) + frequency
	return opcode, args

def format_group_voice_channel_grant_update(ch1, ga1, ch2, ga2):
	assert ch1 <= 0xffff
	assert ga1 <= 0xffff
	assert ch2 <= 0xffff
	assert ga2 <= 0xffff
	opcode = 2
	args = ch1
	args = (args << 16) + ga1
	args = (args << 16) + ch2
	args = (args << 16) + ga2
	return opcode, args

def make_fakecc_tsdu(params):
	opcodes = []
	args = []
	op, arg = format_iden_up(0,
		int(12.5 / 0.125),
		(25 * 4),
		int(12.5 / 0.125),
		902012500/5)
	opcodes.append(op)
	args.append(arg)
	op, arg = format_network_status_broadcast(
		0,
		params['wacn'],
		params['system_id'],
		(params['cc_freq'] - 902012500) / 12500,
		0x70)
	opcodes.append(op)
	args.append(arg)
	op, arg = format_rfss_status_broadcast(
		0, 1, 1,
		params['system_id'],
		params['subsystem_id'],
		params['site_id'],
		(params['cc_freq'] - 902012500) / 12500,
		0x70)
	opcodes.append(op)
	args.append(arg)
	nac = params['nac']
	ss = 2
	blocks = 3
	mfid = 0
	construct_tsdu3(nac, ss, blocks, mfid, opcodes, args)
	ga = 666
	ch = (params['vc_freq'] - 902012500) / 12500
	opcode, args = format_group_voice_channel_grant_update(ch, ga, ch, ga)
	construct_tsdu (nac, ss, blocks, mfid, opcode, args)

########
# main #
########

if __name__ == "__main__":

	from optparse import OptionParser
	parser = OptionParser()
	parser.add_option("--hdu", action="store_true", dest="hdu",
		default=False, help="Construct Header Data Unit")
	parser.add_option("--ldu1", action="store_true", dest="ldu1",
		default=False, help="Construct Logical Link Data Unit 1")
	parser.add_option("--ldu2", action="store_true", dest="ldu2",
		default=False, help="Construct Logical Link Data Unit 2")
	parser.add_option("--stdu", action="store_true", dest="stdu",
		default=False, help="Construct Simple Terminator Data Unit")
	parser.add_option("--xtdu", action="store_true", dest="xtdu",
		default=False, help="Construct Terminator Data Unit with Link Control")
	parser.add_option("--tsdu", action="store_true", dest="tsdu",
		default=False, help="Construct Trunking Signaling Data Unit")
	parser.add_option("--cpdu", action="store_true", dest="cpdu",
		default=False, help="Construct Confirmed Packet Data Unit")
	parser.add_option("--rpdu", action="store_true", dest="rpdu",
		default=False, help="Construct Response Packet Data Unit")
	parser.add_option("--updu", action="store_true", dest="updu",
		default=False, help="Construct Unconfirmed Packet Data Unit")
	parser.add_option("--ambt", action="store_true", dest="ambt",
		default=False,
		help="Construct Alternative Multiple Block Trunking Conrtol Packet")
	parser.add_option("--inhibit", action="store_true", dest="inhibit",
		default=False, help="Special packet: Inhibit")
	parser.add_option("--uninhibit", action="store_true", dest="uninhibit",
		default=False, help="Special packet: Uninhibit")
	parser.add_option("--rum", action="store_true", dest="rum",
		default=False, help="Special packet: Radio Unit Monitor")
	parser.add_option("--superframes", type="int", default=0,
		help="Number of superframes to construct (Default: 0)")
	parser.add_option("--sqtail", type="string", default="0:0:0",
		help="Squelch tail (Default: 0:0:0)")
	parser.add_option("--nac", type="int", default=0x293,
		help="Network Access Code (Default: 0x293)")
	parser.add_option("--ss", type="int", default=0,
		help="Status Symbol (one value to be repeated) (Default: 0)")
	parser.add_option("--mi", type="int", default=0,
		help="Message Indicator (Default: 0x000000000000000000)")
	parser.add_option("--mfid", type="int", default=0,
		help="Manufacturer ID (Default: 0x00)")
	parser.add_option("--algid", type="int", default=0x80,
		help="Algorithm ID (Default: 0x80)")
	parser.add_option("--kid", type="int", default=0,
		help="Key ID (Default: 0x0000)")
	parser.add_option("--tgid", type="int", default=1,
		help="Talk Group ID (Default: 0x0001)")
	parser.add_option("--lco", type="int", default=0,
		help="Link Control Opcode (Default: 0x00)")
	parser.add_option("--src", type="int", default=1,
		help="Source ID (Default: 0x000001)")
	parser.add_option("--dst", type="int", default=1,
		help="Destination ID (Default: 0x000001)") 
	parser.add_option("--lsd", type="int", default=0,
		help="Entire Low Speed Data Word (Default: 0x00000000)")
	parser.add_option("--lsd1", type="int", default=None,
		help="Low Speed Data high word for LDU1 (Default: use --lsd)") 
	parser.add_option("--lsd2", type="int", default=None,
		help="Low Speed Data low word for LDU2 (Default: use --lsd)")
	parser.add_option("--ntsbk", type="int", default=1,
		help="Number of TSBKs per TSDU (Default: 1)") 
	parser.add_option("--data", type="int", default=0,
		help="Packet data (Default: 0x0000000000000000)")
	parser.add_option("--length", type="int", default=0,
		help="Packet data length in bytes (Default: auto)")
	parser.add_option("--sapid", type="int", default=0,
		help="SAP ID (Default: 0x00)")
	parser.add_option("--opcode", type="int", default=0,
		help="Opcode (Default: 0x00)")
	parser.add_option("--dbtm", type="int", default=0,
		help="Defined By Trunking Message AMBT field (Default: 0x0000)")
	parser.add_option("--dho", type="int", default=0,
		help="Data Header Offset (Default: 0x00)")
	parser.add_option("--rclass", type="int", default=0,
		help="Response Class (Default: 0x0)")
	parser.add_option("--rtype", type="int", default=0,
		help="Response Type (Default: 0x0)")
	parser.add_option("--rstatus", type="int", default=0,
		help="Response Status (Default: 0x0)")
	parser.add_option("--ns", type="int", default=0,
		help="N(S) sequence number (Default: 0x0)")
	parser.add_option("--arg", type="int", default=0,
		help="Trunking Control Opcode Argument (Default: 0x0000000000000000)")
	parser.add_option("--svcopt", type="int", default=None,
		help="Service Options byte (Default: use --pri, --emerg, etc.)")
	parser.add_option("-e", "--emerg", action="store_true", dest="emerg",
		default=False, help="Emergency Bit (Default: false)")
	parser.add_option("-p", "--protected", action="store_true",
		dest="protected", default=False, help="Protected Bit (Default: false)")
	parser.add_option("-d", "--duplex", action="store_true", dest="duplex",
		default=False, help="Duplex Bit (Default: false)")
	parser.add_option("-m", "--mode", action="store_true", dest="mode",
		default=False, help="Mode Bit (Default: false)")
	parser.add_option("-r", "--reserved", action="store_true",
		dest="reserved", default=False, help="Reserved Bit (Default: false)")
	parser.add_option("--pri", type="int", default=0,
		help="Priority Level (Default: 0")
	parser.add_option("-t", "--1011", action="store_true", dest="hz1011",
		default=False, help="1011 Hz test tone (Default: false)")
	parser.add_option("-s", "--silence", action="store_true", dest="silence",
		default=False, help="audio silence (Default: false)")
	parser.add_option("-o", "--output-file", type="string", default=None,
		help="Binary output file (Default: None)")
	parser.add_option("-q", "--quiet", action="store_true", dest="quiet",
		default=False, help="Supress text output (Default: false)")
	parser.add_option("-f", "--flip", action="store_true", dest="flip",
		default=False, help="invert frequency deviations (Default: false)")
	parser.add_option("-l", "--late-entry", action="store_true", dest="late",
		default=False, help="Simulate late receiver entry (Default: false)")
	parser.add_option("-i", "--inbound", action="store_true", dest="inbound",
		default=False, help="Inbound packet (Default: false (outbound))")

	(options, args) = parser.parse_args()

	assert options.nac     <= 0xfff
	assert options.ss      <= 0b11
	assert options.mi      <= 0xffffffffffffffffffL
	assert options.mfid    <= 0xff
	assert options.algid   <= 0xff
	assert options.kid     <= 0xffff
	assert options.tgid    <= 0xffff
	assert options.lco     <= 0x3f
	assert options.src     <= 0xffffff
	assert options.dst     <= 0xffffff
	assert options.lsd     <= 0xffffffff
	assert options.lsd1    <= 0xffff
	assert options.lsd2    <= 0xffff
	assert options.pri     <= 0x7
	assert options.svcopt  <= 0xff
	assert options.ntsbk   >= 1
	assert options.ntsbk   <= 3
	assert options.sapid   <= 0x3f
	assert options.opcode  <= 0x3f
	assert options.dbtm    <= 0xffff
	assert options.dho     <= 0x3f
	assert options.rclass  <= 0x3
	assert options.rtype   <= 0x7
	assert options.rstatus <= 0x7
	assert options.ns      <= 0x7
	assert options.arg     <= 0xffffffffffffffffL

	if options.quiet:
		quiet = True

	if options.output_file:
		if options.output_file == '-':
			outfile = sys.stdout
			quiet = True
		else:
			outfile = open(options.output_file, 'w')

	# set up inversion of frequency deviations
	if options.flip:
		flip = 0xaaa

	# squelch tail argument is in the form M:N:K
	# M = number of sTDUs to prepend
	# N = number of xTDUs to append
	# K = number of sTDUs to append
	sqtail = options.sqtail.split(':')
	if len(sqtail) != 3:
		sys.stderr.write("--sqtail must be in the form M:N:K\n")
		sys.exit(1)
	sq_m = int(sqtail[0])
	sq_n = int(sqtail[1])
	sq_k = int(sqtail[2])

	# The Logical Link ID field should be set to the source address for inbound
	# packets and the destination address for outbound packets.
	if options.inbound:
		llid = options.src
	else:
		llid = options.dst

	# Auto-detect the length in bytes of --data.  The --length option overrides
	# this, which is useful when you want leading zeros.
	if (options.data > 0) and (options.length == 0):
		options.length = (options.data.bit_length() + 7) / 8

	# make sure we have IMBE data if we need it
	if options.ldu1 or options.ldu2 or options.superframes:
		if options.hz1011:
			options.imbe = 0x38928490d433c0be1b91844ff058a589d839
		elif options.silence:
			options.imbe = 0x6c42e85de2e8269363d981f9be23b18ae004
		else:
			sys.stderr.write("error: must specify --1011 or --silence\n")
			sys.exit(1)

	# handle alternative way Low Speed Data may be specified
	if options.lsd1:
		options.lsd &= 0x0000ffff
		options.lsd |= options.lsd1 << 16
	if options.lsd2:
		options.lsd &= 0xffff0000
		options.lsd |= options.lsd2

	# Build the Service Options field first so that it can be used in
	# various places.
	if options.superframes or options.ldu1 or options.xtdu or sq_n > 0:
		if not options.svcopt:
			options.svcopt = construct_svcopt(options.emerg, options.protected,
			options.duplex, options.mode, options.reserved, options.pri)

	# prepend sTDUs (see sqtail)
	for i in range(sq_m):
		construct_stdu(options.nac, 1)

	if options.superframes:
		if not options.late:
			construct_hdu(options.nac, options.ss, options.mi, options.mfid,
					options.algid, options.kid, options.tgid)
		for i in range(options.superframes):
			construct_ldu1(options.nac, options.ss, options.imbe,
					options.lsd, options.lco, options.mfid,
					options.svcopt, 0, options.tgid,
					options.dst, options.src)
			construct_ldu2(options.nac, options.ss, options.imbe,
					options.lsd, options.mi, options.algid,
					options.kid)
		construct_stdu(options.nac, options.ss)
	else:
		if options.hdu:
			construct_hdu(options.nac, options.ss, options.mi,
					options.mfid, options.algid, options.kid,
					options.tgid)
		elif options.ldu1:
			construct_ldu1(options.nac, options.ss, options.imbe,
					options.lsd, options.lco, options.mfid,
					options.svcopt, 0, options.tgid,
					options.dst, options.src)
		elif options.ldu2:
			construct_ldu2(options.nac, options.ss, options.imbe,
					options.lsd, options.mi, options.algid,
					options.kid)
		elif options.stdu:
			construct_stdu(options.nac, options.ss)
		elif options.xtdu:
			construct_xtdu(options.nac, options.ss, options.lco,
					options.mfid, options.svcopt, 0,
					options.tgid, options.dst, options.src)
		elif options.tsdu:
			construct_tsdu(options.nac, options.ss, options.ntsbk,
					options.mfid, options.opcode, options.arg)
		elif options.cpdu:
			construct_cpdu(options.nac, options.ss, options.data,
					options.length, 1, options.inbound, options.sapid,
					options.mfid, llid, options.ns, 8, options.dho)
		elif options.rpdu:
			construct_rpdu(options.nac, options.ss, options.data,
					options.length, options.inbound, options.rclass,
					options.rtype, options.rstatus, options.mfid, llid, 1, 0)
		elif options.updu:
			construct_updu(options.nac, options.ss, options.data,
					options.length, options.inbound, options.sapid,
					options.mfid, llid, options.dho)
		elif options.ambt:
			construct_ambt(options.nac, options.ss, options.data,
					options.length, options.inbound, options.sapid,
					options.mfid, llid, options.opcode, options.dbtm)
		elif options.inhibit:
			construct_ext_fnct_cmd_inhibit(options.nac, options.ss,
					options.src, options.dst)
		elif options.uninhibit:
			construct_ext_fnct_cmd_uninhibit(options.nac, options.ss,
					options.src, options.dst)
		elif options.rum:
			construct_rad_mon_cmd(options.nac, options.ss,
					options.src, options.dst)
		else:
			sys.stderr.write("error: must specify packet type or number of superframes (try -h or --help)\n")

	# append xTDUs (see sqtail)
	for i in range(sq_n):
		construct_xtdu(options.nac, 3, options.lco, options.mfid,
				options.svcopt, 0, options.tgid,
				options.dst, options.src)

	# append sTDUs (see sqtail)
	for i in range(sq_k):
		construct_stdu(options.nac, 3)

	if outfile:
		outfile.close()
