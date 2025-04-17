// Copyright 2017, 2018 Max H. Parke KA1RBI
// Copyright 2018, 2019, 2020, 2021 gnorbury@bondcar.com
// JavaScript UI Updates, Michael Rose, 2025
//
// This file is part of OP25
//
// OP25 is free software; you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by
// the Free Software Foundation; either version 3, or (at your option)
// any later version.
//
// OP25 is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
// or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
// License for more details.
//
// You should have received a copy of the GNU General Public License
// along with OP25; see the file COPYING. If not, write to the Free
// Software Foundation, Inc., 51 Franklin Street, Boston, MA
// 02110-1301, USA.

// OP25 - config.js

const configFile = true;

// Define the preset buttons
// No more than 6 allowed

const MAX_HISTORY_ROWS 		= 10; // number of rows to consider "recent" and duplicate by appendCallHistory
const MAX_HISTORY_SECONDS 	= 5; //// number of rows to consider "recent" and duplicate by appendCallHistory
const MAX_TG_CHARS 			= 20; // max number of characters for talkgroup tags in freq table


const presets = [
  { id: 1, tgid: 7305, label: "Martinez PD" },
  { id: 2, tgid: 7712, label: "CCSO Central" },
  { id: 3, tgid: 6052, label: "ConFire B1" },
  { id: 4, tgid: 6006, label: "ConFire B2" },
  { id: 5, tgid: 6007, label: "ConFire B3" },
  { id: 6, tgid: 6008, label: "ConFire B4" }
];


// Define the smartColors, first match wins

const smartColors = [

    {
        keywords: ["Talkgroup", "EBRCS"],
        color: "#0f0"
    },   
    {
        keywords: ["Martinez", "CCSO Central"],
        color: "#ffe680" // soft yellow
    },
    {
        keywords: ["oakland"],
        color: "#c39cff" // soft purple
    },
    
    {
        keywords: ["fire", "fd"],
        color: "#ff5c5c" // soft red
    },    

    {
        keywords: ["pd", "police", "sheriff", "so"],
        color: "#66aaff" // soft blue
    },
    {
        keywords: ["zzz"],
        color: "#99ffcc" // soft lime green
    },
	{
		keywords: ["ems", "med", "amr", "ambulance"],
		color: "#ffb84d" // soft orange
	}
];

// Define site aliases, decimal system id, decimal rfss, decimal site

const siteAliases = {
  "497": {
    "1": {
      "1": { alias: "ALCO Southwest" },
      "2": { alias: "ALCO East" },
      "3": { alias: "CCCO West" },
      "4": { alias: "ALCO Northwest" },
      "5": { alias: "CCCO Central" },
      "6": { alias: "CCCO East" },
      "7": { alias: "ALCO Crane Ridge" },
      "8": { alias: "CCCO Marsh Creek" },
      "9": { alias: "Vallejo Courthouse" },
      "10": { alias: "Vallejo Hiddenbrooke" }
    }
  },
  "944": {
    "1": {
      "1": { alias: "B271" },
      "2": { alias: "B313" },
      "3": { alias: "B849 - 3" },
      "4": { alias: "B849 - 4" },
      "5": { alias: "Crane Ridge" },
      "6": { alias: "Mt. Diablo" },
      "7": { alias: "LBNL" },
      "9": { alias: "Presidio" },
      "10": { alias: "Mt. Tam" },
      "11": { alias: "Montara" }
    }
  }
};

