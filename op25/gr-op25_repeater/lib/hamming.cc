/*
 *   Copyright (C) 2015,2016 by Jonathan Naylor G4KLX
 *
 *   Modifications of original code to work with OP25
 *   Copyright (C) 2019 by Graham J. Norbury
 *
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU General Public License as published by
 *   the Free Software Foundation; either version 2 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License
 *   along with this program; if not, write to the Free Software
 *   Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include "hamming.h"

#include <cstdio>
#include <cassert>

 // Hamming (15,11,3) check a boolean data array
int CHamming::decode15113_1(bit_vector& d, int s)
{
	if (d.size() < (s + 15))
		return -2;

	// Calculate the parity it should have
	bool c0 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+3] ^ d[s+4] ^ d[s+5] ^ d[s+6];
	bool c1 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+3] ^ d[s+7] ^ d[s+8] ^ d[s+9];
	bool c2 = d[s+0] ^ d[s+1] ^ d[s+4] ^ d[s+5] ^ d[s+7] ^ d[s+8] ^ d[s+10];
	bool c3 = d[s+0] ^ d[s+2] ^ d[s+4] ^ d[s+6] ^ d[s+7] ^ d[s+9] ^ d[s+10];

	unsigned int n = 0;
	n |= (c0 != d[s+11]) ? 0x01 : 0x00;
	n |= (c1 != d[s+12]) ? 0x02 : 0x00;
	n |= (c2 != d[s+13]) ? 0x04 : 0x00;
	n |= (c3 != d[s+14]) ? 0x08 : 0x00;

	switch (n)
	{
		// Parity bit errors
		case 0x01: d[s+11] = !d[s+11]; return 1;
		case 0x02: d[s+12] = !d[s+12]; return 1;
		case 0x04: d[s+13] = !d[s+13]; return 1;
		case 0x08: d[s+14] = !d[s+14]; return 1;

		// Data bit errors
		case 0x0F: d[s+0]  = !d[s+0];  return 1;
		case 0x07: d[s+1]  = !d[s+1];  return 1;
		case 0x0B: d[s+2]  = !d[s+2];  return 1;
		case 0x03: d[s+3]  = !d[s+3];  return 1;
		case 0x0D: d[s+4]  = !d[s+4];  return 1;
		case 0x05: d[s+5]  = !d[s+5];  return 1;
		case 0x09: d[s+6]  = !d[s+6];  return 1;
		case 0x0E: d[s+7]  = !d[s+7];  return 1;
		case 0x06: d[s+8]  = !d[s+8];  return 1;
		case 0x0A: d[s+9]  = !d[s+9];  return 1;
		case 0x0C: d[s+10] = !d[s+10]; return 1;

		// No bit errors
		default: return 0;
	}
}

#if 0
void CHamming::encode15113_1(bool* d)
{
	assert(d != NULL);

	// Calculate the checksum this row should have
	d[11] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[5] ^ d[6];
	d[12] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[7] ^ d[8] ^ d[9];
	d[13] = d[0] ^ d[1] ^ d[4] ^ d[5] ^ d[7] ^ d[8] ^ d[10];
	d[14] = d[0] ^ d[2] ^ d[4] ^ d[6] ^ d[7] ^ d[9] ^ d[10];
}
#endif

// Hamming (15,11,3) check a boolean data array
int CHamming::decode15113_2(bit_vector& d, int s)
{
	if (d.size() < (s + 15))
		return -2;

	// Calculate the checksum this row should have
	bool c0 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+3] ^ d[s+5] ^ d[s+7] ^ d[s+8];
	bool c1 = d[s+1] ^ d[s+2] ^ d[s+3] ^ d[s+4] ^ d[s+6] ^ d[s+8] ^ d[s+9];
	bool c2 = d[s+2] ^ d[s+3] ^ d[s+4] ^ d[s+5] ^ d[s+7] ^ d[s+9] ^ d[s+10];
	bool c3 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+4] ^ d[s+6] ^ d[s+7] ^ d[s+10];

	unsigned int n = 0x00;
	n |= (c0 != d[s+11]) ? 0x01 : 0x00;
	n |= (c1 != d[s+12]) ? 0x02 : 0x00;
	n |= (c2 != d[s+13]) ? 0x04 : 0x00;
	n |= (c3 != d[s+14]) ? 0x08 : 0x00;

	switch (n) {
		// Parity bit errors
		case 0x01: d[s+11] = !d[s+11]; return 1;
		case 0x02: d[s+12] = !d[s+12]; return 1;
		case 0x04: d[s+13] = !d[s+13]; return 1;
		case 0x08: d[s+14] = !d[s+14]; return 1;

		// Data bit errors
		case 0x09: d[s+0]  = !d[s+0];  return 1;
		case 0x0B: d[s+1]  = !d[s+1];  return 1;
		case 0x0F: d[s+2]  = !d[s+2];  return 1;
		case 0x07: d[s+3]  = !d[s+3];  return 1;
		case 0x0E: d[s+4]  = !d[s+4];  return 1;
		case 0x05: d[s+5]  = !d[s+5];  return 1;
		case 0x0A: d[s+6]  = !d[s+6];  return 1;
		case 0x0D: d[s+7]  = !d[s+7];  return 1;
		case 0x03: d[s+8]  = !d[s+8];  return 1;
		case 0x06: d[s+9]  = !d[s+9];  return 1;
		case 0x0C: d[s+10] = !d[s+10]; return 1;

		// No bit errors
		default: return 0;
	}
}

#if 0
void CHamming::encode15113_2(bool* d)
{
	assert(d != NULL);

	// Calculate the checksum this row should have
	d[11] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[5] ^ d[7] ^ d[8];
	d[12] = d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[6] ^ d[8] ^ d[9];
	d[13] = d[2] ^ d[3] ^ d[4] ^ d[5] ^ d[7] ^ d[9] ^ d[10];
	d[14] = d[0] ^ d[1] ^ d[2] ^ d[4] ^ d[6] ^ d[7] ^ d[10];
}
#endif

// Hamming (13,9,3) check a boolean data array
int CHamming::decode1393(bit_vector& d, int s)
{
	if (d.size() < (s + 13))
		return -2;

	// Calculate the checksum this column should have
	bool c0 = d[s+0] ^ d[s+1] ^ d[s+3] ^ d[s+5] ^ d[s+6];
	bool c1 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+4] ^ d[s+6] ^ d[s+7];
	bool c2 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+3] ^ d[s+5] ^ d[s+7] ^ d[s+8];
	bool c3 = d[s+0] ^ d[s+2] ^ d[s+4] ^ d[s+5] ^ d[s+8];
	
	unsigned int n = 0x00;
	n |= (c0 != d[s+9])  ? 0x01 : 0x00;
	n |= (c1 != d[s+10]) ? 0x02 : 0x00;
	n |= (c2 != d[s+11]) ? 0x04 : 0x00;
	n |= (c3 != d[s+12]) ? 0x08 : 0x00;

	switch (n) {
		// Parity bit errors
		case 0x01: d[s+9]  = !d[s+9];  return 1;
		case 0x02: d[s+10] = !d[s+10]; return 1;
		case 0x04: d[s+11] = !d[s+11]; return 1;
		case 0x08: d[s+12] = !d[s+12]; return 1;

		// Data bit erros
		case 0x0F: d[s+0] = !d[s+0]; return 1;
		case 0x07: d[s+1] = !d[s+1]; return 1;
		case 0x0E: d[s+2] = !d[s+2]; return 1;
		case 0x05: d[s+3] = !d[s+3]; return 1;
		case 0x0A: d[s+4] = !d[s+4]; return 1;
		case 0x0D: d[s+5] = !d[s+5]; return 1;
		case 0x03: d[s+6] = !d[s+6]; return 1;
		case 0x06: d[s+7] = !d[s+7]; return 1;
		case 0x0C: d[s+8] = !d[s+8]; return 1;

		// No bit errors
		default: return 0;
	}
}

#if 0
void CHamming::encode1393(bool* d)
{
	assert(d != NULL);

	// Calculate the checksum this column should have
	d[9]  = d[0] ^ d[1] ^ d[3] ^ d[5] ^ d[6];
	d[10] = d[0] ^ d[1] ^ d[2] ^ d[4] ^ d[6] ^ d[7];
	d[11] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[5] ^ d[7] ^ d[8];
	d[12] = d[0] ^ d[2] ^ d[4] ^ d[5] ^ d[8];
}
#endif

// Hamming (10,6,3) check a boolean data array
int CHamming::decode1063(bit_vector& d, int s)
{
	if (d.size() < (s + 10))
		return -2;

	// Calculate the checksum this column should have
	bool c0 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+5];
	bool c1 = d[s+0] ^ d[s+1] ^ d[s+3] ^ d[s+5];
	bool c2 = d[s+0] ^ d[s+2] ^ d[s+3] ^ d[s+4];
	bool c3 = d[s+1] ^ d[s+2] ^ d[s+3] ^ d[s+4];

	unsigned int n = 0x00;
	n |= (c0 != d[s+6]) ? 0x01 : 0x00;
	n |= (c1 != d[s+7]) ? 0x02 : 0x00;
	n |= (c2 != d[s+8]) ? 0x04 : 0x00;
	n |= (c3 != d[s+9]) ? 0x08 : 0x00;

	switch (n) {
		// Parity bit errors
		case 0x01: d[s+6] = !d[s+6]; return 1;
		case 0x02: d[s+7] = !d[s+7]; return 1;
		case 0x04: d[s+8] = !d[s+8]; return 1;
		case 0x08: d[s+9] = !d[s+9]; return 1;

		// Data bit erros
		case 0x07: d[s+0] = !d[s+0]; return 1;
		case 0x0B: d[s+1] = !d[s+1]; return 1;
		case 0x0D: d[s+2] = !d[s+2]; return 1;
		case 0x0E: d[s+3] = !d[s+3]; return 1;
		case 0x0C: d[s+4] = !d[s+4]; return 1;
		case 0x03: d[s+5] = !d[s+5]; return 1;

		// No bit errors
		default: return 0;
	}
}

#if 0
void CHamming::encode1063(bool* d)
{
	assert(d != NULL);

	// Calculate the checksum this column should have
	d[6] = d[0] ^ d[1] ^ d[2] ^ d[5];
	d[7] = d[0] ^ d[1] ^ d[3] ^ d[5];
	d[8] = d[0] ^ d[2] ^ d[3] ^ d[4];
	d[9] = d[1] ^ d[2] ^ d[3] ^ d[4];
}
#endif

// A Hamming (16,11,4) Check
int CHamming::decode16114(bit_vector& d, int s)
{
	if (d.size() < (s + 16))
		return -2;

	// Calculate the checksum this column should have
	bool c0 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+3] ^ d[s+5] ^ d[s+7] ^ d[s+8];
	bool c1 = d[s+1] ^ d[s+2] ^ d[s+3] ^ d[s+4] ^ d[s+6] ^ d[s+8] ^ d[s+9];
	bool c2 = d[s+2] ^ d[s+3] ^ d[s+4] ^ d[s+5] ^ d[s+7] ^ d[s+9] ^ d[s+10];
	bool c3 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+4] ^ d[s+6] ^ d[s+7] ^ d[s+10];
	bool c4 = d[s+0] ^ d[s+2] ^ d[s+5] ^ d[s+6] ^ d[s+8] ^ d[s+9] ^ d[s+10];

	// Compare these with the actual bits
	unsigned int n = 0x00;
	n |= (c0 != d[s+11]) ? 0x01 : 0x00;
	n |= (c1 != d[s+12]) ? 0x02 : 0x00;
	n |= (c2 != d[s+13]) ? 0x04 : 0x00;
	n |= (c3 != d[s+14]) ? 0x08 : 0x00;
	n |= (c4 != d[s+15]) ? 0x10 : 0x00;

	switch (n) {
		// Parity bit errors
		case 0x01: d[s+11] = !d[s+11]; return 1;
		case 0x02: d[s+12] = !d[s+12]; return 1;
		case 0x04: d[s+13] = !d[s+13]; return 1;
		case 0x08: d[s+14] = !d[s+14]; return 1;
		case 0x10: d[s+15] = !d[s+15]; return 1;

		// Data bit errors
		case 0x19: d[s+0]  = !d[s+0];  return 1;
		case 0x0B: d[s+1]  = !d[s+1];  return 1;
		case 0x1F: d[s+2]  = !d[s+2];  return 1;
		case 0x07: d[s+3]  = !d[s+3];  return 1;
		case 0x0E: d[s+4]  = !d[s+4];  return 1;
		case 0x15: d[s+5]  = !d[s+5];  return 1;
		case 0x1A: d[s+6]  = !d[s+6];  return 1;
		case 0x0D: d[s+7]  = !d[s+7];  return 1;
		case 0x13: d[s+8]  = !d[s+8];  return 1;
		case 0x16: d[s+9]  = !d[s+9];  return 1;
		case 0x1C: d[s+10] = !d[s+10]; return 1;

		// No bit errors
		case 0x00: return 0;

		// Unrecoverable errors
		default: return -1;
	}
}

#if 0
void CHamming::encode16114(bool* d)
{
	assert(d != NULL);

	d[11] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[5] ^ d[7] ^ d[8];
	d[12] = d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[6] ^ d[8] ^ d[9];
	d[13] = d[2] ^ d[3] ^ d[4] ^ d[5] ^ d[7] ^ d[9] ^ d[10];
	d[14] = d[0] ^ d[1] ^ d[2] ^ d[4] ^ d[6] ^ d[7] ^ d[10];
	d[15] = d[0] ^ d[2] ^ d[5] ^ d[6] ^ d[8] ^ d[9] ^ d[10];
}
#endif

// A Hamming (17,12,3) Check
int CHamming::decode17123(bit_vector& d, int s)
{
	if (d.size() < (s + 17))
		return -2;

	// Calculate the checksum this column should have
	bool c0 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+3] ^ d[s+6] ^ d[s+7] ^ d[s+9];
	bool c1 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+3] ^ d[s+4] ^ d[s+7] ^ d[s+8] ^ d[s+10];
	bool c2 = d[s+1] ^ d[s+2] ^ d[s+3] ^ d[s+4] ^ d[s+5] ^ d[s+8] ^ d[s+9] ^ d[s+11];
	bool c3 = d[s+0] ^ d[s+1] ^ d[s+4] ^ d[s+5] ^ d[s+7] ^ d[s+10];
	bool c4 = d[s+0] ^ d[s+1] ^ d[s+2] ^ d[s+5] ^ d[s+6] ^ d[s+8] ^ d[s+11];

	// Compare these with the actual bits
	unsigned int n = 0x00;
	n |= (c0 != d[s+12]) ? 0x01 : 0x00;
	n |= (c1 != d[s+13]) ? 0x02 : 0x00;
	n |= (c2 != d[s+14]) ? 0x04 : 0x00;
	n |= (c3 != d[s+15]) ? 0x08 : 0x00;
	n |= (c4 != d[s+16]) ? 0x10 : 0x00;

	switch (n) {
		// Parity bit errors
		case 0x01: d[s+12] = !d[s+12]; return 1;
		case 0x02: d[s+13] = !d[s+13]; return 1;
		case 0x04: d[s+14] = !d[s+14]; return 1;
		case 0x08: d[s+15] = !d[s+15]; return 1;
		case 0x10: d[s+16] = !d[s+16]; return 1;

		// Data bit errors
		case 0x1B: d[s+0]  = !d[s+0];  return 1;
		case 0x1F: d[s+1]  = !d[s+1];  return 1;
		case 0x17: d[s+2]  = !d[s+2];  return 1;
		case 0x07: d[s+3]  = !d[s+3];  return 1;
		case 0x0E: d[s+4]  = !d[s+4];  return 1;
		case 0x1C: d[s+5]  = !d[s+5];  return 1;
		case 0x11: d[s+6]  = !d[s+6];  return 1;
		case 0x0B: d[s+7]  = !d[s+7];  return 1;
		case 0x16: d[s+8]  = !d[s+8];  return 1;
		case 0x05: d[s+9]  = !d[s+9];  return 1;
		case 0x0A: d[s+10] = !d[s+10]; return 1;
		case 0x14: d[s+11] = !d[s+11]; return 1;

		// No bit errors
		case 0x00: return 0;

		// Unrecoverable errors
		default: return -1;
	}
}

#if 0
void CHamming::encode17123(bool* d)
{
	assert(d != NULL);

	d[12] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[6] ^ d[7] ^ d[9];
	d[13] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[7] ^ d[8] ^ d[10];
	d[14] = d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[5] ^ d[8] ^ d[9] ^ d[11];
	d[15] = d[0] ^ d[1] ^ d[4] ^ d[5] ^ d[7] ^ d[10];
	d[16] = d[0] ^ d[1] ^ d[2] ^ d[5] ^ d[6] ^ d[8] ^ d[11];
}
#endif
