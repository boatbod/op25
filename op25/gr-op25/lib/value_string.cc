/* -*- C++ -*- */

/*
 * Copyright 2008 Steve Glass
 * Copyright 2018 Matt Ames
 * 
 * This file is part of OP25.
 * 
 * OP25 is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * OP25 is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public
 * License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with OP25; see the file COPYING.  If not, write to the Free
 * Software Foundation, Inc., 51 Franklin Street, Boston, MA
 * 02110-1301, USA.
 */

#include "value_string.h"

#include <iomanip>
#include <sstream>

using namespace std;

struct value_string {
	uint16_t value;
	const char *label;
};

string
lookup(uint16_t value, const value_string mappings[], size_t mappings_sz)
{
   for(size_t i = 0; i < mappings_sz; ++i) {
      if(mappings[i].value == value) {
         return mappings[i].label;
      }
   }
   ostringstream os;
   os << "Unknown (" << hex << showbase << value << ")";
   return os.str();
}

const value_string ALGIDS[] = {
   /* Type I */
   { 0x00, "ACCORDION 1.3" },
   { 0x01, "BATON (Auto Even)" },
   { 0x02, "FIREFLY Type 1" },
   { 0x03, "MAYFLY Type 1" },
   { 0x04, "SAVILLE" },
   { 0x05, "Motorola Assigned - PADSTONE" },
   { 0x41, "BATON (Auto Odd)" },
   /* Type III */
   { 0x80, "Unencrypted" },
   { 0x81, "DES-OFB, 56 bit key" },
   { 0x83, "3 key Triple DES, 168 bit key" },
   { 0x84, "AES-256" },
   { 0x85, "AES-128-ECB"},
   { 0x88, "AES-CBC"},
   /* Motorola proprietary - some of these have been observed over the air,
      some have been taken from firmware dumps on various devices, others
      have come from the TIA's FTP website while it was still public,
      from document "ALGID Guide 2015-04-15.pdf", and others have been
      have been worked out with a little bit of guesswork */
   { 0x9F, "Motorola DES-XL" },
   { 0xA0, "Motorola DVI-XL" },
   { 0xA1, "Motorola DVP-XL" },
   { 0xA2, "Motorola DVI-SPFL"},
   { 0xA3, "Motorola Assigned - Unknown" },
   { 0xA4, "Motorola Assigned - Unknown" },
   { 0xA5, "Motorola Assigned - Unknown" },
   { 0xA6, "Motorola Assigned - Unknown" },
   { 0xA7, "Motorola Assigned - Unknown" },
   { 0xA8, "Motorola Assigned - Unknown" },
   { 0xA9, "Motorola Assigned - Unknown" },
   { 0xAA, "Motorola ADP" },
   { 0xAB, "Motorola CFX-256" },
   { 0xAC, "Motorola Assigned - Unknown" },
   { 0xAD, "Motorola Assigned - Unknown" },
   { 0xAE, "Motorola Assigned - Unknown" },
   { 0xAF, "Motorola AES-256-GCM (possibly)" },
   { 0xB0, "Motorola DVP"},
};
const size_t ALGIDS_SZ = sizeof(ALGIDS) / sizeof(ALGIDS[0]);


const value_string MFIDS[] = {
   { 0x00, "Standard MFID (pre-2001)" },
   { 0x01, "Standard MFID (post-2001)" },
   { 0x09, "Aselsan Inc." },
   { 0x10, "Relm / BK Radio" },
   { 0x18, "EADS Public Safety Inc." },
   { 0x20, "Cycomm" },
   { 0x28, "Efratom Time and Frequency Products, Inc" },
   { 0x30, "Com-Net Ericsson" },
   { 0x34, "Etherstack" },
   { 0x38, "Datron" },
   { 0x40, "Icom" },
   { 0x48, "Garmin" },
   { 0x50, "GTE" },
   { 0x55, "IFR Systems" },
   { 0x5A, "INIT Innovations in Transportation, Inc" },
   { 0x60, "GEC-Marconi" },
   { 0x64, "Harris Corp." },
   { 0x68, "Kenwood Communications" },
   { 0x70, "Glenayre Electronics" },
   { 0x74, "Japan Radio Co." },
   { 0x78, "Kokusai" },
   { 0x7C, "Maxon" },
   { 0x80, "Midland" },
   { 0x86, "Daniels Electronics Ltd." },
   { 0x90, "Motorola" },
   { 0xA0, "Thales" },
   { 0xA4, "M/A-COM" },
   { 0xB0, "Raytheon" },
   { 0xC0, "SEA" },
   { 0xC8, "Securicor" },
   { 0xD0, "ADI" },
   { 0xD8, "Tait Electronics" },
   { 0xE0, "Teletec" },
   { 0xF0, "Transcrypt International" },
   { 0xF8, "Vertex Standard" },
   { 0xFC, "Zetron, Inc" },
};
const size_t MFIDS_SZ = sizeof(MFIDS) / sizeof(MFIDS[0]);

const value_string NACS[] = {
	{ 0x293, "Default NAC" },
	{ 0xF7E, "Receiver to open on any NAC" },
	{ 0xF7F, "Repeater to receive and retransmit any NAC" },
};
const size_t NACS_SZ = sizeof(NACS) / sizeof(NACS[0]);
