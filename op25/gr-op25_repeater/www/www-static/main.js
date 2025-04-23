
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

// 04-21-2025  1818


var d_debug = 1;

// var http_req = new XMLHttpRequest();

var counter1 = 0;
var error_val = null;
var auto_tracking = null;
var fine_tune = null;
var current_tgid = null;
var capture_active = false;
var hold_tgid = 0;
var http_errors = 0;
var http_ok = 0;
var fetch_errors = 0;
var send_qfull = 0;
var send_queue = [];
var request_count = 0;
var SEND_QLIMIT = 5;
var c_freq = 0;
var c_ppm = null;
var c_system = null;
var c_tag = null;
var c_stream_url = null;
var c_srctag = "";
var c_srcaddr = 0;
var c_grpaddr = 0;
var c_encrypted = 0;
var c_emergency = 0;
var c_nac = 0;
var c_name = "";
var channel_list = [];
var channel_index = 0;
var default_channel = null;
var enc_sym = "&#216;";
var presets = [];
var lg_step = 1200;  // these are defaults, they are updated in term_config() if present.
var sm_step = 100;


const mediaQuery = window.matchMedia("(min-width: 1500px)");
mediaQuery.addEventListener("change", handleColumnLayoutChange);

document.addEventListener("DOMContentLoaded", function() {
    var displaySystem    = document.getElementById("displaySystem");
    var displayFreq      = document.getElementById("displayFreq");

    var displayTalkgroup = document.getElementById("displayTalkgroup");
    var displayTgid      = document.getElementById("displayTgid");

    var displaySource    = document.getElementById("displaySource");
    var displaySourceId  = document.getElementById("displaySourceId");

//     var displayMode      = document.getElementById("displayMode");
    var displayEnc       = document.getElementById("displayEnc");
    var displayEmg       = document.getElementById("displayEmg");    
    
    var displayChannel	 = document.getElementById("displayChannel");
    var displayService	 = document.getElementById("displayService");

	const heightInput = document.getElementById("callHeightControl");
	const scrollDiv = document.querySelector(".call-history-scroll");
	
	if (heightInput && scrollDiv) {
	heightInput.addEventListener("input", () => {
	  const newHeight = parseInt(heightInput.value, 10);
	  if (!isNaN(newHeight) && newHeight >= 200 && newHeight <= 1000) {
		scrollDiv.style.height = `${newHeight}px`;
	  }
	});
	}
	
    if (!configFile) {
    	document.getElementById("smartColorToggle").checked = false;
    }
    
    if (configFile) {
        presets = cfg_presets;
        update_presets();
	}
	
	loadSettingsFromLocalStorage();	
	
	const sizeInput = document.getElementById("plotSizeControl");
  
	sizeInput.addEventListener("input", () => {
	const newWidth = parseInt(sizeInput.value, 10);
	if (!isNaN(newWidth) && newWidth >= 100 && newWidth <= 1000) {
	  document.querySelectorAll(".plot-image").forEach(img => {
		img.style.width = `${newWidth}px`;
	  });
	}
	});
  
	handleColumnLayoutChange(mediaQuery);	
	  
	updatePlotButtonStyles();
	document.getElementById("callHistorySource").addEventListener("change", saveSettingsToLocalStorage);	
	document.getElementById("callHeightControl").addEventListener("input", saveSettingsToLocalStorage);
	document.getElementById("plotSizeControl").addEventListener("input", saveSettingsToLocalStorage);
	document.getElementById("smartColorToggle").addEventListener("change", saveSettingsToLocalStorage);
	document.getElementById("radioIdFreqTable").addEventListener("change", saveSettingsToLocalStorage);	
	
	document.getElementById("adjacentSitesToggle").addEventListener("change", function () {
	  const container = document.getElementById("adjacentSitesContainer");
	  const checked = this.checked;
	
	  if (container) {
		container.style.display = checked ? "" : "none";
	  }

	  saveSettingsToLocalStorage();
	});		
	
	document.getElementById("callHistoryToggle").addEventListener("change", function () {
	  const container = document.getElementById("callHistoryContainer");
	  const checked = this.checked;
	
	  if (container) {
		container.style.display = checked ? "" : "none";
	  }
	  
	  saveSettingsToLocalStorage();
	});		

});

function update_presets()
{
    presets.forEach(preset => {
        const btn = document.getElementById(`preset-btn-${preset.id}`);
        if (btn) {
            btn.textContent = `${preset.label}`;
        }
    });
}

function do_onload() {
    send_command("get_terminal_config", 0, 0);
    setInterval(do_update, 1000);
}

function find_parent(ele, tagname) {
    while (ele) {
        if (ele.nodeName == tagname)
            return (ele);
        else if (ele.nodeName == "HTML")
            return null;
        ele = ele.parentNode;
    }
    return null;
}

function f_command(ele, command) {
    var myrow = find_parent(ele, "TR");
    if (command == "delete") {
        var ok = confirm ("Confirm delete");
        if (ok)
            myrow.parentNode.removeChild(myrow);
    } else if (command == "clone") {
        var newrow = myrow.cloneNode(true);
        if (myrow.nextSibling)
            myrow.parentNode.insertBefore(newrow, myrow.nextSibling);
        else
            myrow.parentNode.appendChild(newrow);
    } else if (command == "new") {
        var mytbl = find_parent(ele, "TABLE");
        var newrow = null;
        if (mytbl.id == "chtable")
            newrow = document.getElementById("chrow").cloneNode(true);
        else if (mytbl.id == "devtable")
            newrow = document.getElementById("devrow").cloneNode(true);
        else
            return;
        mytbl.appendChild(newrow);
    }
}

function nav_update(command) {
	var names = ["b1", "b2", "b3"];
	var bmap = { "status": "b1", "plot": "b2", "about": "b3" };
	var id = bmap[command];
	for (var id1 in names) {
		b = document.getElementById(names[id1]);
		if (names[id1] == id) {
			b.className = "nav-button-active";
		} else {
			b.className = "nav-button";
		}
	}
}

function f_select(command) {

    var div_status = document.getElementById("div_status")
    var div_plot   = document.getElementById("div_plot")
    var div_about  = document.getElementById("div_about")
    var div_s1     = document.getElementById("div_s1")
    var div_s2     = document.getElementById("div_s2")
    var div_s3     = document.getElementById("div_s3")
    var ctl1 = document.getElementById("controls1");
    var ctl2 = document.getElementById("controls2");
    
    if (command == "status") {
        div_status.style['display'] = "";
        div_plot.style['display'] = "none";
        div_about.style['display'] = "none";
        div_s1.style['display'] = "";
        div_s2.style['display'] = "";
        div_s3.style['display'] = "";
        ctl1.style['display'] = "";
        ctl2.style['display'] = "none";
    }
    else if (command == "plot") {
        div_status.style['display'] = "";
        div_plot.style['display'] = "";
        div_about.style['display'] = "none";
        div_s1.style['display'] = "none";
        div_s2.style['display'] = "";
        div_s3.style['display'] = "none";
        ctl1.style['display'] = "none";
        ctl2.style['display'] = "";
    }
    else if (command == "about") {
        div_status.style['display'] = "none";
        div_plot.style['display'] = "none";
        div_about.style['display'] = "";
        ctl1.style['display'] = "none";
        ctl2.style['display'] = "none";
    }
    nav_update(command);
}

function is_digit(s) {
    if (s >= "0" && s <= "9")
        return true;
    else
        return false;
}

function term_config(d) {
    var lg_step = 1200;
    var sm_step = 100;
    var updated = 0;
	
	// Determine UI version required (rx.py => force to legacy terminal for compatibility reasons)
    if ((d["terminal_interface"] != undefined) && (d["terminal_interface"] == "legacy")) {
        window.location.replace("legacy-index.html");
    }

	// Update tuning step values if present	
    if ((d["tuning_step_large"] != undefined) && (d["tuning_step_large"] != lg_step)) {
        lg_step = d["tuning_step_large"];
    }
    if ((d["tuning_step_small"] != undefined) && (d["tuning_step_small"] != sm_step)) {
        sm_step = d["tuning_step_small"];
    }
    
    if ((d["default_channel"] != undefined) && (d["default_channel"] != "")) {
        default_channel = d["default_channel"];
    }

    if (d["presets"] != undefined) {
        presets = d["presets"];
        update_presets();
    }
}


function rx_update(d) {

	var plotsCount = d["files"].length;
	document.getElementById('plotsCount').innerText = plotsCount;

    plotfiles = [];
    
    if ((d["files"] != undefined) && (d["files"].length > 0)) {
        for (var i=0; i < d["files"].length; i++) {
            if (channel_list.length > 0) {
                expr = new RegExp("plot\-" + channel_list[channel_index] + "\-");
            }
            else {
                expr = new RegExp("plot\-0\-");
            }

            if (expr.test(d["files"][i])) {
                plotfiles.push(d["files"][i]);
            }
        }

        for (var i=0; i < 6; i++) {
            var img = document.getElementById("img" + i);
            if (i < plotfiles.length) {
                if (img['src'] != plotfiles[i]) {
                    img['src'] = plotfiles[i];
                    img.style["display"] = "";
                }
            }
            else {
                img.style["display"] = "none";
            }
        }
    }
    else {
        var img = document.getElementById("img0");
        img.style["display"] = "none";
    }
    
    updatePlotButtonStyles();
    
    if (d["error"] != undefined) {
        error_val = d["error"];
    } else {
        error_val = null;
    }
    
    if (d["fine_tune"] != undefined)
        fine_tune = d["fine_tune"];
}

// frequency, system, and talkgroup display

function change_freq(d) {

    c_freq = d['freq'];
    c_system = d['system'];
    current_tgid = d['tgid'];
    c_tag = d['tag'];
    displayTalkgroup.innerText = c_tag;
    c_stream_url = d['stream_url'];
    channel_status();
}

function channel_update(d) {
		
    var s2_c  = document.getElementById("s2_ch_lbl");
    var s2_d  = document.getElementById("s2_ch_txt");
    var s2_e  = document.getElementById("s2_ch_dn");
    var s2_f  = document.getElementById("s2_ch_dmp");
    var s2_g  = document.getElementById("s2_ch_up");
    var s2_hc = document.getElementById("s2_ch_cap");
    var s2_ht = document.getElementById("s2_ch_trk");

    if (d['channels'] != undefined) {
        channel_list = d['channels'];

        if (channel_list.length > 0) {
            // if this is the first update, find the default_channel if specified
            if (default_channel != null && default_channel != "") {
                for (ch_id = 0; ch_id < channel_list.length; ch_id++) {
                    if (d[ch_id]['name'] == default_channel) {
                        channel_index = ch_id;
                        break;
                    }
                }
                default_channel = null;
            }

            // display channel information
            var c_id = channel_list[channel_index];
            c_system = d[c_id]['system'];
            
            c_svcopts = d[c_id]['svcopts'];
            
            c_name = "" + c_id + ": ";
            if ((d[c_id]['name'] != undefined) && (d[c_id]['name'] != "")) {
                c_name += " " + d[c_id]['name'];
            }
            else {
                c_name += " " + c_system;
            }

            c_freq = d[c_id]['freq'];
			            
            c_ppm = d[c_id]['ppm'];
            if (d[c_id]['error'] != undefined) {
                error_val = d[c_id]['error'];
                document.getElementById('errorVal').innerText = error_val + " Hz";
            } else {
                document.getElementById('errorVal').innerText = " - ";
                error_val = null;
            }
            if (d[c_id]['auto_tracking'] != undefined)
                auto_tracking = d[c_id]['auto_tracking'];
                
            current_tgid = d[c_id]['tgid'];
            c_tag = d[c_id]['tag'];
            
            c_srcaddr = d[c_id]['srcaddr'];
            c_srctag = d[c_id]['srctag'];
            
            c_stream_url = d[c_id]['stream_url'];
            capture_active = d[c_id]['capture'];
            hold_tgid = d[c_id]['hold_tgid'];

// TODO: housekeeping here
            
        if (hold_tgid != 0) {

            document.getElementById("btn-hold").style.color = "red";
			// document.getElementById("btn-hold").textContent = hold_tgid;      // places the hold tgid in the hold button
		} else {
			document.getElementById("btn-hold").style.color = ""; // Resets to stylesheet
			document.getElementById("btn-hold").textContent = "HOLD";
			
		}
                
            c_encrypted = d[c_id]['encrypted'];
            c_emergency = d[c_id]['emergency'];

			// these are still used 
            s2_e.style['display'] = "";
            s2_f.style['display'] = "";
            s2_g.style['display'] = "";
            s2_hc.style['display'] = "";
            s2_ht.style['display'] = "";
                        
            c_tdma = d[c_id]['tdma'];
            
            displayChannel.innerText		= c_name;
            plotChannelDisplay.innerText	= c_name;
            
            displaySystem.innerText 		= c_system ? c_system : "-";
            
   			displayFreq.innerText 			= (parseInt(c_freq) / 1000000.0).toFixed(6);
            displayTalkgroup.innerText 		= c_tag ? c_tag : "Talkgroup " + current_tgid;
            
            displayTgid.innerText 			= current_tgid ? current_tgid : "-";
            displaySource.innerText 		= c_srctag ? c_srctag : "ID: " + c_srcaddr;
            
            applySmartColorToTgidSpan();
            
            if ( displaySource.innerText == "ID: 0")
            	 displaySource.innerText = " ";
            	 
            displaySourceId.innerText 	= c_srcaddr ? c_srcaddr : "-";
            
			// Encryption			
			if (!c_encrypted) displayEnc.innerText = "-";
			
			if (c_encrypted == 1) {
			  displayEnc.innerText = "Encrypted";
			  displayEnc.style.color = "red";
			  displayTalkgroup.innerHTML += " &nbsp;&nbsp;&nbsp; " + enc_sym;
			} else {
			  displayEnc.innerText = "-";
			  displayEnc.style.color = ""; // fallback to CSS default
			}
			
			if (c_encrypted == 0) {
			  displayEnc.innerText = "Clear";
			  displayEnc.style.color = ""; // fallback to CSS default
			}
			
			if (c_encrypted == undefined) displayEnc.innerText = "-";
			
			// Emergency
			if (c_emergency == 1) {
			  displayEmg.innerText = "EMERGENCY";
			  displayEmg.style.color = "red";
			} else {
			  displayEmg.innerText = "-";
			  displayEmg.style.color = ""; // fallback to CSS default
			}
            
            if (c_svcopts == 0) c_svcopts = "-";
            displayService.innerText = c_svcopts;
			
			// send voice display to call history table				
			if (current_tgid)      
				appendCallHistory(c_system.substring(0, 5), current_tgid, 0, displayTalkgroup.innerText, 0, displayFreq.innerText, displaySource.innerText, "", "display");
        }
        else {
            s2_c.style['display'] = "none";
            s2_d.style['display'] = "none";
            s2_e.style['display'] = "none";
            s2_f.style['display'] = "none";
            s2_g.style['display'] = "none";
            s2_hc.style['display'] = "none";
            s2_ht.style['display'] = "none";
            c_name = "";
            c_freq = 0.0;
            c_system = "";
            current_tgid = 0;
            c_tag = "";
            c_srcaddr = 0;
            c_srctag = "";
            c_stream_url = "";
            c_encrypted = 0;
            c_emergency = 0;
        }
        channel_status();
    }
}

function channel_status() {

	// TODO: housekeeping in this section.  some of this html is no longer needed.

    var html;
    var s2_freq = document.getElementById("s2_freq");
    var s2_tg = document.getElementById("s2_tg");
    var s2_grp = document.getElementById("s2_grp");
    var s2_src = document.getElementById("s2_src");
    var s2_ch_txt = document.getElementById("s2_ch_txt");
    var s2_cap = document.getElementById("cap_bn");
    var s2_trk = document.getElementById("trk_bn");
    
    // the speaker icon in the main display and the url in the Settings div
    var streamButton = document.getElementById("streamButton");
	var streamURL = document.getElementById("streamURL");
		
    html = "";

    if (c_stream_url != undefined) {
//         html += "<a href=\"" + c_stream_url + "\">";
        var streamHTML = "<a a href='" + c_stream_url + "' target='_blank'>&#128264;</a>";
        streamButton.innerHTML = streamHTML;
        streamURL.innerHTML = streamHTML + " " + c_stream_url    
    }
    
    html += "<span class=\"value\">" + (c_freq / 1000000.0).toFixed(6) + "</span>";
    if (c_stream_url != "") {
        html += "</a>"
    }

	// TODO: c_ppm is not displayed anywhere in the new UI. What is it?
	if (c_ppm != null) {
        html += "<span class=\"value\"> (" + c_ppm.toFixed(3) + ")</span>";
    }


    html = "";
	
    if (capture_active)
        document.getElementById('cap_bn').innerText = "Stop Capture";
    else
        document.getElementById('cap_bn').innerText = "Start Capture";
        
    if (auto_tracking)
        document.getElementById('trk_bn').innerText = "Tracking Off";
    else
        document.getElementById('trk_bn').innerText = "Tracking On";
        
}

// patches table

function patches(d) {
    if (d['patch_data'] == undefined || Object.keys(d['patch_data']).length < 1) {
    	document.getElementById('patchesContainer').style.display = "none";
        return "";
    }

	document.getElementById('patchesContainer').style.display = "";
	
    var is_p25 = (d['type'] == 'p25');
    var is_smartnet = (d['type'] == 'smartnet');

    // Only supported on P25 and Type II currently
    if (!is_p25 && !is_smartnet) {
    	document.getElementById('patchesContainer').style.display = "none";
        return;
    }

    var html = "<table class=compact-table>";
    html += "<tr><th colspan=99 class='th-section'>Patches</th></tr>";
    if (is_p25) {
        html += "<tr><th>Supergroup</th><th>Group</th></tr>";
    } else if (is_smartnet) {
        html += "<tr><th colspan=2>TG</th><th colspan=2>Sub TG</th><th>Mode</th></tr>";
    }
    var ct = 0;
    for (var tgid in d['patch_data']) {
        var color = "";  // "#d0d0d0";
        if ((ct & 1) == 0)
            color = "";  // "#c0c0c0";
        ct += 1;

        num_sub_tgids = Object.keys(d['patch_data'][tgid]).length
        var row_num = 0;
        for (var sub_tgid in d['patch_data'][tgid]) {
            if (++row_num == 1) {
                html += "<tr style=\"background-color: " + color + ";\">";
                if (is_p25) {
                    html += "<td rowspan=" + num_sub_tgids + ">" + d['patch_data'][tgid][sub_tgid]['sg'] + " - " + d['patch_data'][tgid][sub_tgid]['sgtag'] + "</td>";
                } else if (is_smartnet) {
                    html += "<td rowspan=" + num_sub_tgids + ">" + d['patch_data'][tgid][sub_tgid]['tgid_dec'] + "</td><td rowspan=" + num_sub_tgids + ">" + d['patch_data'][tgid][sub_tgid]['tgid_hex'] + "</td>";
                }
            } else {
                html += "<tr style=\"background-color: " + color + ";\">";
            }
            if (is_p25) {
                html += "<td>" + d['patch_data'][tgid][sub_tgid]['ga'] + " - " + d['patch_data'][tgid][sub_tgid]['gatag'] + "</td>";
            } else if (is_smartnet) {
                html += "<td>" + d['patch_data'][tgid][sub_tgid]['sub_tgid_dec'] + "</td><td>" + d['patch_data'][tgid][sub_tgid]['sub_tgid_hex'] + "</td>";
                html += "<td>" + d['patch_data'][tgid][sub_tgid]['mode'] + "</td>";
            }
            html += "</tr>";
        }
    }
    html += "</table>";

// end patch table

	document.getElementById('patchesTable').innerHTML = html;
	
	return;
}

// adjacent sites table

function adjacent_sites(d) {

    if (d['adjacent_data'] == undefined || Object.keys(d['adjacent_data']).length < 1) {
        return;
    }

    var is_p25 = (d['type'] == 'p25');
    var is_smartnet = (d['type'] == 'smartnet');

    // Only supported on P25 and Type II currently
    if (!is_p25 && !is_smartnet) {
    	document.getElementById('adjacentSitesContainer').style.display = "none";
        return;
    }

    var html = "<table class='compact-table'";
    html += "<tr><th colspan=99 class='th-section'>Adjacent Sites</th></tr>";
    if (is_p25) {
        html += "<tr><th>System</th><th>Site Name<th>RFSS</th><th>Site</th><th>Frequency</th><th>Uplink</th></tr>";
        var ct = 0;
        // Ordered by RFSS then site number
        var adjacent_by_rfss = {};
        for (var freq in d['adjacent_data']) {
            var rfss = d['adjacent_data'][freq]["rfid"];
            var site = d['adjacent_data'][freq]["stid"];
            if (!(rfss in adjacent_by_rfss)) {
                adjacent_by_rfss[rfss] = {};
            }
            if (!(site in adjacent_by_rfss[rfss])) {
                adjacent_by_rfss[rfss][site] = {};
            }
            adjacent_by_rfss[rfss][site]['cc_rx_freq'] = (freq / 1000000.0).toFixed(6);
            adjacent_by_rfss[rfss][site]['cc_tx_freq'] = (d['adjacent_data'][freq]["uplink"] / 1000000.0).toFixed(6);
        }
        
       
        for (var rfss in adjacent_by_rfss) {
            for (var site in adjacent_by_rfss[rfss]) {
                var color = "";
                if ((ct & 1) == 0)
                    color = "";
                ct += 1;
  				
                displaySiteName = getSiteAlias(d['sysid'], rfss, site);
  
                html += "<tr style=\"background-color: " + color + ";\"><td>" + d['sysid'].toString(16).toUpperCase() + "<td style=text-align:left;>" + displaySiteName + "</td><td>" + rfss + "</td><td>" + site + "</td><td>" + adjacent_by_rfss[rfss][site]["cc_rx_freq"] + "</td><td>" + adjacent_by_rfss[rfss][site]["cc_tx_freq"] + "</td></tr>";
            }
        }
    } else if (is_smartnet) {
        html += "<tr><th>Site</th><th>Frequency</th><th>Uplink</th></tr>";
        var ct = 0;
        // Ordered by site number
        var adjacent_by_site = {};
        for (var freq in d['adjacent_data']) {
            var site = d['adjacent_data'][freq]["stid"];
            adjacent_by_site[site] = {};
            adjacent_by_site[site]['cc_rx_freq'] = (freq / 1000000.0).toFixed(6);
            adjacent_by_site[site]['cc_tx_freq'] = (d['adjacent_data'][freq]["uplink"] / 1000000.0).toFixed(6);
        }
        for (var site in adjacent_by_site) {
            var color = "#d0d0d0";
            if ((ct & 1) == 0)
                color = "#c0c0c0";
            ct += 1;
            html += "<tr style=\"background-color: " + color + ";\"><td>" + site + "</td><td>" + adjacent_by_site[site]["cc_rx_freq"] + "</td><td>" + adjacent_by_site[site]["cc_tx_freq"] + "</td></tr>";
        }
    }
    html += "</table><br>";

// end adjacent sites table

	document.getElementById('adjacentSitesTable').innerHTML = html;
    return html;
}

// additional system info: wacn, sysID, rfss, site id, secondary control channels, freq error

function trunk_update(d) {
    var do_hex = {"syid":0, "sysid":0, "wacn": 0};
    var do_float = {"rxchan":0, "txchan":0};
    var srcaddr = 0;
    var encrypted = 0;
    var html = "";

    if (d['nac'] != undefined)
        c_nac = d['nac']

    for (var nac in d) {
        if (!is_digit(nac.charAt(0)))
            continue;

        // If 'system' name is defined, use it to correlate system info with channel currently selected
        // used by multi_rx.py trunking
        if (d[nac]['system'] != undefined) {
            if (d[nac]['system'] != c_system) {
                continue;
            }
            else {
                c_nac = d['nac'];
            }
        }
        // Otherwise use c_nac which is derived from "current_nac" parameter in 'change_freq' message
        // used by legacy rx.py trunking
        else if (nac != c_nac) {
            continue;
        }

        var is_p25 = (d[nac]['type'] == 'p25');
        var is_smartnet = (d[nac]['type'] == 'smartnet');
        
// system information and frequencies table

		var displaySystemName = d[nac]['system'] !== undefined ? d[nac]['system'] : "-";
		var topLine = d[nac]['top_line'] !== undefined ? d[nac]['top_line'] : "-";
		var displayCallSign = d[nac]['callsign'] !== undefined ? d[nac]['callsign'] : "-";
		var totalTsbk = topLine !== "-" ? comma(extractLastNumber(topLine)) : "-";
		var tsbkTime = d[nac]['last_tsbk'] !== undefined ? d[nac]['last_tsbk'] : "-";
		var displayWacn = d[nac]['wacn'] !== undefined ? d[nac]['wacn'] : "-";
		var displayNac = d[nac]['nac'] !== undefined ? d[nac]['nac'] : "-";
		var displaySystemId = d[nac]['sysid'] !== undefined ? d[nac]['sysid'] : "-";
		var displayType = d[nac]['type'] !== undefined ? d[nac]['type'] : "-";
		var displayRfss = d[nac]['rfid'] !== undefined ? d[nac]['rfid'] : "-";
		var displaySiteId = d[nac]['stid'] !== undefined ? d[nac]['stid'] : "-";		
		var displaySiteName = getSiteAlias(displaySystemId, displayRfss, displaySiteId);

		if (displayCallSign.length < 2)
			displayCallSign = "-";
		
		
		// this HTML is used in new UI
		
        html = "<table class='compact-table'>";
        
        html += "<tr><th colspan=99 class='th-section'>" + displaySiteName + "</th></tr>";
    

		// System Information table (above frequency display)
		// removed error, placed in channel update block 		  { label: "Error", value: `${error_val} Hz` },
		const trunkFields = [
		  { label: "Callsign", value: hex(displayCallSign) },
		  { label: "Type", value: hex(displayType) },
		  { label: "System ID", value: hex(displaySystemId) },
		  { label: "WACN", value: hex(displayWacn) },
		  { label: "NAC", value: hex(displayNac) },
		  { label: "RFSS", value: hex(displayRfss) },
		  { label: "Site", value: hex(displaySiteId) },
		  { label: "TSBK", value: totalTsbk },
		  { label: "Last TSBK", value: getTime(tsbkTime), colspan: 2 }
		];
		
		let htmlParts = ["<tr>"];
		
		trunkFields.forEach(field => {
		  const colspan = field.colspan ? ` colspan="${field.colspan}"` : "";
		  htmlParts.push(
			`<td style="text-align:center;"${colspan}><span class="trunk-label">${field.label}</span><br><span class="trunk-value">${field.value}</span></td>`
		  );
		});

		html += htmlParts.join("");
        html += "</tr></table>"
   
    	// HTML for frequency table
    
        html += "<div class=\"info\"><div class=\"system\">";
        html += "<table id='frequencyTable' class='compact-table'>";
        html += "<colgroup>";
        html += "<col span=\"1\" style=\"width:20%;\">";
        html += "<col span=\"1\" style=\"width:12.5%;\">";
        html += "<col span=\"1\" style=\"width:20%;\">";
        html += "<col span=\"1\" style=\"width:20%;\">";
        html += "<col span=\"1\" style=\"width:15%;\">";
        html += "<col span=\"1\" style=\"width:12.5%;\">";
        html += "</colgroup>";
        html += "<tr><th>Frequency</th><th>Last</th><th colspan=2>Active Talkgoup&nbspID</th><th>Mode</th><th>Voice Count</th></tr>";
        
        var radioIdFreqTable = document.getElementById('radioIdFreqTable').checked;
                
        for (var freq in d[nac]['frequency_data']) {
        
            chan_type = d[nac]['frequency_data'][freq]['type'];
            last_activity = d[nac]['frequency_data'][freq]['last_activity'];
            tg1 = d[nac]['frequency_data'][freq]['tgids'][0];
            tg2 = d[nac]['frequency_data'][freq]['tgids'][1];
            
		
			let tag1 = (tg1 != null && tg1 !== "")
			  ? (d[nac]?.frequency_data?.[freq]?.tags?.[0] || `Talkgroup ${tg1}`)
			  : " ";
			
			let tag2 = (tg2 != null && tg2 !== "")
			  ? (d[nac]?.frequency_data?.[freq]?.tags?.[1] || `Talkgroup ${tg2}`)
			  : " ";

            let src1 = d[nac]['frequency_data'][freq]['srcaddrs'][0];
            let src2 = d[nac]['frequency_data'][freq]['srcaddrs'][1];
            
            let srctag1 = d[nac]['frequency_data'][freq]['srctags'][0];
			let srctag2 = d[nac]['frequency_data'][freq]['srctags'][1];
			
			
			let source1 = (srctag1 != null && srctag1 !== "")
				? srctag1
				: (src1 != null && src1 !== "" && src1 !== 0)
					? `ID: ${src1}`
					: null;
			
			let source2 = (srctag2 != null && srctag2 !== "")
				? srctag2
				: (src2 != null && src2 !== "" && src2 !== 0)
					? `ID: ${src2}`
					: null;

			dispSrc1 = (source1 == null) ? "-" : source1;
			dispSrc2 = (source2 == null) ? "-" : source2;
			
			if (radioIdFreqTable) {
				var contentId1 = "<br>" + dispSrc1 + "</td>";
				var contentId2 = "<br>" + dispSrc2 + "</td>";
			} else {
				var contentId1 = "</td>";
				var contentId2 = "</td>";						
			}

            mode = d[nac]['frequency_data'][freq]['mode'];
            count = d[nac]['frequency_data'][freq]['counter'];
            			
            var mode_str = "<td></td>"
            
            // Do alternate first because active TGs will deliberately overwrite the mode
            if (chan_type == 'alternate') {
                if (is_p25)
                    mode_str = "<td style=\"text-align:center;\">Sec CC</td>"
                else if (is_smartnet)
                    mode_str = "<td style=\"text-align:center;\">Alt CC</td>"
                else
                    mode_str = "<td style=\"text-align:center;\">Alt CC</td>"
            }

            var achMode = "-";  // not used right now
            
            // Now actually handle the appropriate channel type if not alternate
            if (chan_type == 'control') {
                tg_str = "<td style=\"text-align:center; color:gray;\" colspan=2>Control</td>";
                // Deliberately 6 or 8 characters wide, to ensure the column stays the right width without flickering
                // when call status flags come and go with calls
                if (is_p25)
                    mode_str = "<td style=\"text-align:center;\">&nbsp;&nbsp;CC&nbsp;&nbsp;</td>"
                else if (is_smartnet)
                    mode_str = "<td style=\"text-align:center;\">&nbsp;&nbsp;&nbsp;CC&nbsp;&nbsp;&nbsp;</td>"
                else
                    mode_str = "<td style=\"text-align:center;\">CC</td>"
                count = "";
            }
            else {
                if (is_smartnet && (tg1 != null || tg2 != null))
                    mode_str = "<td style=\"text-align:center;\">" + mode + "</td>"

                if (tg1 == null && tg2 == null) {
                    tg_str = "<td style=\"text-align:center;\" colspan=2>&nbsp&nbsp-&nbsp&nbsp</td>";
                }
                else if (tg1 == tg2) {
                    if (is_p25) {
                        mode_str = "<td style=\"text-align:center;\">FDMA</td>";
                        achMode = "FDMA";
                    }
                    tg_str = "<td style=\"text-align:center;white-space: nowrap;\" colspan=2>" + tg1 + " &nbsp; " + tag1.substring(0, MAX_TG_CHARS) + contentId1;
                }
                else {
                    if (is_p25) {
                        mode_str = "<td style=\"text-align:center;\">TDMA</td>";
                        achMode = "TDMA";
					}                    
                    if (tg1 == null)
                        tg1 = "&nbsp&nbsp-&nbsp&nbsp";
                    if (tg2 == null)
                        tg2 = "&nbsp&nbsp-&nbsp&nbsp";
                    tg_str = "<td style=\"text-align:center;white-space: nowrap;\">" + tg2 + " &nbsp; " + tag2.substring(0, MAX_TG_CHARS) + contentId2 + "<td style=\"text-align:center;white-space: nowrap;\">" + tg1 + " &nbsp; " + tag1.substring(0, MAX_TG_CHARS) + contentId1;
                }
            }

			// Append Call History
        	if (d[nac]['sysid'] !== undefined && (tg1 !== undefined || tg2 !== undefined)) {
				appendCallHistory(d[nac]['sysid'], tg1, tg2, tag1, tag2, (parseInt(freq) / 1000000.0).toFixed(6), source1, source2, "frequency");
			}          

            html += "<tr>";
            html += "<td class='freqData'>" + (parseInt(freq) / 1000000.0).toFixed(6) + "</td>";

            html += "<td style=\"text-align:center;\">" + last_activity + "</td>";
            html += tg_str;
            html += mode_str;
            html += "<td style=\"text-align:right;\">" + comma(count) + "</td>";
            html += "</tr>";
        }
        
        html += "</table></div>";

		document.getElementById("frequenciesTable").innerHTML = html; 
		
		
		if (radioIdFreqTable) {
			document.querySelectorAll('td.freqData').forEach(td => {
			  td.style.height = '46px';  // make the row height tall enough for 2 rows of text, avoids the ui bounding up and down
			});
		} else {
			document.querySelectorAll('td.freqData').forEach(td => {
			  td.style.height = '';
			});
		}

// end system freqencies table

		// finish up
		
		applySmartColorsToFrequencyTable();
        patches(d[nac]);
        adjacent_sites(d[nac]);
        
        
    }


    if (d['srcaddr'] != undefined)
        c_srcaddr = d['srcaddr']
    if (d['grpaddr'] != undefined)
        c_grpaddr = d['grpaddr']
    if (d['encrypted'] != undefined)
        c_encrypted = d['encrypted']
    if (d['emergency'] != undefined)
        c_emergency = d['emergency']

    channel_status();
}

function plot(d) {
    //TODO: implement local plot rendering using json data
}

function call_log(d) {

	const configuredSource = document.getElementById("callHistorySource").value;
	if (configuredSource !== "voice") {
	  return;
	}
	
	if (d['log'].length == 0)
		return;   		// nothing to do
	
	const logs = d['log'];

	const titleTh = document.getElementById("callHistoryTableTitle");
	titleTh.innerText = "Call History - Voice Grants";
	
	const tableBody = document.getElementById("callHistoryBody");
	
		logs.forEach(log => {
			// Convert epoch time to Date
			const dateObj = new Date(log.time * 1000);
		
			// Format to HH:MM:SS
			const hh = String(dateObj.getHours()).padStart(2, '0');
			const mm = String(dateObj.getMinutes()).padStart(2, '0');
			const ss = String(dateObj.getSeconds()).padStart(2, '0');
			const time = `${hh}:${mm}:${ss}`;
		
			// Assign remaining fields to variables
			const sysid = log.sysid.toString(16).toUpperCase().padStart(3, '0');
			const tgid = log.tgid;
			const tgtag = log.tgtag;
			  var rid = log.rid;
			const rtag = log.rtag;
			const rcvr = log.rcvr;
			const prio = log.prio;
			const rcvrtag = log.rcvrtag.substring(0, 10) || "";
			const freq = (log.freq / 1000000.0).toFixed(6);
			  var slot = log.slot;
				
			if (rid == 0)
				rid = "-";
			
			displayRtag = (rtag !== "") ? rtag : "ID: " + rid;
			displayTtag = (tgtag !== "") ? tgtag : "Talkgroup " + tgid;
			
			if (slot == null)
				slot = "-";
			
			displayReceiver = freq + " &nbsp;&nbsp;<font color=#aaa>" + rcvr + ": " + rcvrtag + "</font> &nbsp;&nbsp;S" + slot + "<font color=#aaa> &nbsp;&nbsp;P" + prio;			
			
			const newRow = document.createElement("tr");
			newRow.innerHTML = `
				<td>${time}</td>
				<td>${sysid}</td>
				<td>${displayReceiver} &nbsp;&nbsp;</td>
				<td>${tgid}</td>
				<td style="text-align: left;">${displayTtag}</td>
				<td style="text-align: left;">${displayRtag}</td>
			`;
			
			tableBody.insertBefore(newRow, tableBody.firstChild);
			
		});
	
	applySmartColorsToCallHistory();
	
	const table = document.getElementById("callHistoryContainer");
	
	if (table) {
	  const headerRow = table.querySelector("thead tr");
	  if (headerRow && headerRow.cells.length > 2) {
		headerRow.cells[2].innerText = "Frequency / Receiver / Slot / Prio";
	  }
	}
	
	return;
	
}

function handle_response(dl) {
	// formerly known as function http_req_cb()
    const dispatch = {
        call_log: call_log,
        trunk_update: trunk_update,
        change_freq: change_freq,
        channel_update: channel_update,
        rx_update: rx_update,
        terminal_config: term_config,
        plot: plot
    };

    for (let i = 0; i < dl.length; i++) {
        const d = dl[i];
        if (!("json_type" in d)) continue;
        if (!(d.json_type in dispatch)) continue;
        dispatch[d.json_type](d);
    }
}

function do_update() {
    if (channel_list.length == 0) {
        send_command("update", 0, 0);
    }
    else {
        send_command("update", 0, Number(channel_list[channel_index]));
    }
    f_debug();
}

function send_command(command, arg1 = 0, arg2 = 0) {

    request_count += 1;
    if (send_queue.length >= SEND_QLIMIT) {
        send_qfull += 1;
        send_queue.unshift();
    }
    send_queue.push( {"command": command, "arg1": arg1, "arg2": arg2} );
    send_process();
}


function send_process() {

    const cmd = JSON.stringify(send_queue);
    send_queue = [];
    
    const wbox = document.getElementById('warning-box');
    const wtxt = document.getElementById('warning-text');

    fetch("/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: cmd
    })
    .then(response => {
        if (!response.ok) {
			http_errors += 1;
            wbox.style.display = "flex";
            wtxt.innerText = "HTTP Error: ", response.status;
            return;
        }
        http_ok += 1;
        return response.json();
    })
    .then(dl => {
        if (!dl) return;
        wbox.style.display = "none";
        handle_response(dl);
    })
    .catch(error => {
			fetch_errors += 1;
            wbox.style.display = "flex";
            wtxt.innerText = "Fetch error in send_process: Network error when attempting to fetch resource. Check server.";      
    });
}

function f_chan_button(command) {
    channel_index += command;
    if (channel_index < 0) {
        channel_index = channel_list.length - 1;
    }
    else if (channel_index >= channel_list.length) {
        channel_index = 0;
    }
}

function f_dump_button(command) {
    send_command('dump_tgids', 0, Number(channel_list[channel_index]));
    send_command('dump_tracking', 0, Number(channel_list[channel_index]));
}

function f_dump_buffer(command) {
    send_command('dump_buffer', command, Number(channel_list[channel_index]));
    alert("OP25 buffers written to server")
}

function f_cap_button(command) {
    send_command('capture', 0, Number(channel_list[channel_index]));
}

function f_trk_button(command) {
    send_command('set_tracking', command, Number(channel_list[channel_index]));
}

function f_tune_button(command) {

	let step = 0;
	
	switch (command) {
	  case "ld": // large down
		_tune = -lg_step;
		break;
	  case "sd": // small down
		_tune = -sm_step;
		break;
	  case "su": // small up
		_tune = sm_step;
		break;
	  case "lu": // large up
		_tune = lg_step;
		break;
	  default:
		console.warn("Unknown tune command:", command);
		_tune = 0;
	}

    if (channel_list.length == 0) {
        send_command('adj_tune', _tune, 0);
    }
    else {
        send_command('adj_tune', _tune, Number(channel_list[channel_index]));
    }
}

function f_plot_button(command) {
    if (channel_list.length == 0) {
        send_command('toggle_plot', command, 0);
    }
    else {
        send_command('toggle_plot', command, Number(channel_list[channel_index]));
    }
    
    updatePlotButtonStyles();
}

function f_preset(i) {

	// TODO - this doesn't care about more than 1 channel_index	

	const preset = presets.find(p => p.id === i);
	
	if (!preset) {
		console.warn(`No preset found for ID ${i}`);
		return;
	}

	const command = "hold";

	_tgid = preset.tgid;

	if (isNaN(_tgid) || (_tgid < 0) || (_tgid > 65535))
		_tgid = 0;

    if (channel_list.length == 0) {
    
       	if (command == "hold")
    		send_command("whitelist", _tgid);
    
        send_command(command, _tgid);

        
    } else {
    
    	if (command == "hold")
    		send_command("whitelist", _tgid, Number(channel_list[channel_index]));

        send_command(command, _tgid, Number(channel_list[channel_index]));
    }
}

function f_scan_button(command) {

    var _tgid = 0;

    if (command == "goto") {

        command = "hold"
        if (current_tgid != null)
           _tgid = current_tgid;
        _tgid = parseInt(prompt("Enter tgid to hold", _tgid));
            
        if (isNaN(_tgid) || (_tgid < 0) || (_tgid > 65535))
            _tgid = 0;
    }
    
    else if ((command == "lockout") && (current_tgid == null)) {
        _tgid = parseInt(prompt("Enter tgid to blacklist", _tgid));
        if (isNaN(_tgid) || (_tgid <= 0) || (_tgid > 65534))
            return;
    }
    else if (command == "whitelist") {
        _tgid = parseInt(prompt("Enter tgid to whitelist", _tgid));
        if (isNaN(_tgid) || (_tgid <= 0) || (_tgid > 65534))
            return;
    }
    else if (command == "set_debug") {
        _tgid = parseInt(prompt("Enter logging level", _tgid));
        if (isNaN(_tgid) || (_tgid < 0) )
            return;
    }

    if (channel_list.length == 0) {
    
       	if (command == "hold" && _tgid != 0)             
    		send_command("whitelist", _tgid);
    
        send_command(command, _tgid);
    }
    else {
    
    	if (command == "hold" && _tgid != 0)
    		send_command("whitelist", _tgid, Number(channel_list[channel_index]));

        send_command(command, _tgid, Number(channel_list[channel_index]));
    }
}

function f_debug() {
	if (!d_debug) return;
	
	var html = "Requests from send_command: " + request_count;
	html += "<br>HTTP 200 OK: " + http_ok;
	html += "&nbsp;&nbsp;&nbsp;&nbsp;HTTP Errors: " + http_errors;
	html += "<br>Fetch Errors: " + fetch_errors;
	html += "<br>Send Queue Size " + send_queue.length;
	html += "&nbsp;&nbsp;&nbsp;&nbsp;Queue Full " + send_qfull;	

// 	html += " error=" + n200_count;
// 	html += " OK=" + r200_count;
	html += "<br>";
	var div_debug = document.getElementById("div_debug");
	div_debug.innerHTML = html;
}


// new functions

function comma(x) {
    // add comma formatting to whatever you give it (xx,xxxx,xxxx)
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}


function getTime(ts) {
    const date = new Date(ts * 1000); // convert to milliseconds
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
}

function extractLastNumber(str) {
    const match = str.match(/(\d+)(?!.*\d)/);
    return match ? parseInt(match[0], 10) : null;
}

function appendCallHistory(sysid, tg1, tg2, tag1, tag2, freq, sourceId1, sourceId2, dataSource) {

	// dataSource is one of 'frequency' or 'voice' 

	// appends the call history table only when the current call is not already there
	// or is older than 5 seconds.
	// called by trunk_update()

	const configuredSource = document.getElementById("callHistorySource").value;
	if (dataSource !== configuredSource) {
	  return;
	}

	// title the call history table
	const titleTh = document.getElementById("callHistoryTableTitle");
	if (configuredSource === "display") {
	titleTh.innerText = "Call History - Display";
	} else if (configuredSource === "frequency") {
	titleTh.innerText = "Call History - Frequency Data";
	} 


	// populate the table
    const tableBody = document.getElementById("callHistoryBody");
    const now = new Date();
    const timestamp = now.toTimeString().split(' ')[0]; // "HH:MM:SS"
    const epoch = now.getTime(); // current time in ms
    const sysHex = sysid.toString(16).toUpperCase().padStart(3, '0');
    const slot = "S"; // Placeholder for slot

    // Helper to check if a similar row already exists
		function isDuplicate(tgid, sourceId) {
			const recentRows = tableBody.querySelectorAll("tr");
		
			for (let i = 0; i < Math.min(MAX_HISTORY_ROWS, recentRows.length); i++) {
				const cells = recentRows[i].querySelectorAll("td");
				if (cells.length < 6) continue;
		
				const rowTime   = cells[0].textContent.trim();
				const rowSys    = cells[1].textContent.trim();
				const rowTgid   = cells[3].textContent.trim();
				const rowSrcId  = cells[5].textContent.trim(); // <-- updated to index 5
		
				if (rowSys === sysHex && rowTgid === String(tgid) && rowSrcId === String(sourceId)) {
					const rowDate = new Date();
					const [hours, minutes, seconds] = rowTime.split(':').map(Number);
					rowDate.setHours(hours, minutes, seconds, 0);
		
					const rowEpochSec = Math.floor(rowDate.getTime() / 1000);
					const nowSec = Math.floor(epoch / 1000);
					const delta = Math.abs(nowSec - rowEpochSec);
		
					if (delta <= MAX_HISTORY_SECONDS) {
						return true;
					}
				}
			}
		
			return false;
		}

    // Helper to add a row
    	// TODO: src
		function addRow(tgid, tag, sourceId) {
				
			// Only proceed if tgid is defined and its string length > 2
			if (tgid === undefined || String(tgid).length <= 2) return;
		
			const tgEntry = tag;
			const tgName = tgEntry;
		
			const newRow = document.createElement("tr");
			
			// TODO: src
			newRow.innerHTML = `
				<td>${timestamp}</td>
				<td>${sysHex}</td>
				<td>${freq}</td>
				<td>${tgid}</td>
				<td style="text-align: left;">${tgName}</td>
				<td style="text-align: left;">${sourceId}</td>
			`;
		
			tableBody.insertBefore(newRow, tableBody.firstChild);
		}

    // Process single or both entries, don't log entries where source id is not present.
	if (tg1 !== undefined) {
		if (!isDuplicate(tg1, sourceId1) && sourceId1) {
			addRow(tg1, tag1, sourceId1);
		}
	}
	
	if (tg2 !== undefined && tg2 !== tg1) {
		if (!isDuplicate(tg2, sourceId2) && sourceId2) {
			addRow(tg2, tag2, sourceId2);
		}
	}
	
	applySmartColorsToCallHistory();
	
	const table = document.getElementById("callHistoryContainer");

	if (table) {
	  const headerRow = table.querySelector("thead tr");
	  if (headerRow && headerRow.cells.length > 2) {
		headerRow.cells[2].innerText = "Frequency";
	  }
	}
}

function applySmartColorsToCallHistory() {
  if (!document.getElementById("smartColorToggle").checked) return;

  const rows = document.querySelectorAll("#callHistoryBody tr");

  rows.forEach(row => {
    const cells = row.querySelectorAll("td");
    if (cells.length < 5) return;

    const tgidCell = cells[3];
    const sourceCell = cells[4];
    const sourceIdCell = cells[5];
    
    const cellText = sourceCell.textContent.toLowerCase();

    let matched = false;

    for (const colorGroup of smartColors) {
      if (colorGroup.keywords.some(keyword => cellText.includes(keyword.toLowerCase()))) {
        tgidCell.style.color = colorGroup.color;
        sourceCell.style.color = colorGroup.color;
        sourceIdCell.style.color = colorGroup.color;
        matched = true;
        break;
      }
    }

    if (!matched) {
      tgidCell.style.color = "";
      sourceCell.style.color = "";
      sourceIdCell.style.color = "";
    }
  });
}


function applySmartColorsToFrequencyTable() {
  if (!document.getElementById("smartColorToggle").checked) return;

  const rows = document.querySelectorAll("#frequencyTable tr");

  rows.forEach(row => {
    const cells = row.querySelectorAll("td");
    if (cells.length < 3) return;

    const talkgroupCells = [cells[2]];
    if (cells.length > 3 && cells[3].cellIndex === 3) {
      talkgroupCells.push(cells[3]);
    }

    talkgroupCells.forEach(cell => {
      const cellText = cell.textContent.toLowerCase();
      let matched = false;

      // Skip TDMA/FDMA mode cells
      if (cellText === "fdma" || cellText === "tdma") return;

      for (const colorGroup of smartColors) {
        if (colorGroup.keywords.some(keyword => cellText.includes(keyword.toLowerCase()))) {
          cell.style.color = colorGroup.color;
          matched = true;
          break;
        }
      }

      if (!matched) {
        cell.style.color = "";
      }
    });
  });
}


function applySmartColorToTgidSpan() {
  if (!document.getElementById("smartColorToggle").checked) return;

	const el = document.getElementById("displayTalkgroup");
	if (!el) return;
	
	const source = document.getElementById("displaySource");

  const cellText = el.textContent.toLowerCase();

  for (const colorGroup of smartColors) {
    if (colorGroup.keywords.some(keyword => cellText.includes(keyword.toLowerCase()))) {
      el.style.color = colorGroup.color;
      source.style.color = colorGroup.color;
      return;
    }
  }

  el.style.color = "";
}



function getSiteAlias(sysid, rfss, site) {
	// as defined in config.js
  try {
    const alias = siteAliases?.[sysid]?.[rfss]?.[site]?.alias;
    return alias ?? `Site ${site}`;
  } catch (err) {
    console.warn("Error looking up site alias:", err);
    return `Site ${site}`;
  }
}

function toggleDivById(divId, buttonId) {
  const el = document.getElementById(divId);
  const btn = document.getElementById(buttonId);
  if (!el || !btn) return;

  const isVisible = el.style.display !== "none";

  if (isVisible) {
    el.style.display = "none";
    btn.style.color = ""; // reset to default
  } else {
    el.style.display = "";
    btn.style.color = "red";
  }
}

function updatePlotButtonStyles() {
  // First clear all button borders
  const buttonIds = ['fft', 'constellation', 'symbol', 'eye', 'mixer', 'fll'];
  buttonIds.forEach(type => {
    const btn = document.getElementById(`pb-${type}`);
    if (btn) btn.classList.remove("plot-active");
  });

  // Now check each image to see which plots are currently active
  for (let i = 0; i < 6; i++) {
    const img = document.getElementById(`img${i}`);
    if (!img || img.style.display === "none") continue;

    const src = img.getAttribute("src") || "";
    buttonIds.forEach(type => {
      if (src.includes(type)) {
        const btn = document.getElementById(`pb-${type}`);
        if (btn) btn.classList.add("plot-active");
      }
    });
  }
}

function isNumber(value) {
  return typeof value === "number" && !isNaN(value);
}

function handleColumnLayoutChange(e) {
  const secondCol = document.getElementById("second-column");
  if (!secondCol) return;

  if (e.matches) {
    // 2-column layout active
    secondCol.style.marginLeft = "10px";
  } else {
    // stacked layout (1 column)
    secondCol.style.marginLeft = "";
  }
}


function saveSettingsToLocalStorage() {
  localStorage.setItem("callHeight", document.getElementById("callHeightControl").value);
  localStorage.setItem("plotWidth", document.getElementById("plotSizeControl").value);
  localStorage.setItem("smartColors", document.getElementById("smartColorToggle").checked);
  localStorage.setItem("adjacentSitesToggle", document.getElementById("adjacentSitesToggle").checked);
  localStorage.setItem("callHistorySource", document.getElementById("callHistorySource").value);
  localStorage.setItem("radioIdFreqTable", document.getElementById("radioIdFreqTable").checked);
}

function loadSettingsFromLocalStorage() {
  const callHeight = localStorage.getItem("callHeight") || "600";
  const plotWidth = localStorage.getItem("plotWidth") || "300";
  const smartColors = localStorage.getItem("smartColors");
  const adjacentSites = localStorage.getItem("adjacentSitesToggle");
  const callHistorySource = localStorage.getItem("callHistorySource") || "frequency";
  const radioIdFreqTable = localStorage.getItem("radioIdFreqTable");

  document.getElementById("radioIdFreqTable").checked = radioIdFreqTable === "true";
  
  document.getElementById("callHeightControl").value = callHeight;
  document.querySelector(".call-history-scroll").style.height = `${callHeight}px`;

  document.getElementById("plotSizeControl").value = plotWidth;
  document.querySelectorAll(".plot-image").forEach(img => {
    img.style.width = `${plotWidth}px`;
  });

  const smartColorEnabled = smartColors === null ? true : smartColors === "true";
  document.getElementById("smartColorToggle").checked = smartColorEnabled;

  const adjacentSitesEnabled = adjacentSites === null ? true : adjacentSites === "true";
  document.getElementById("adjacentSitesToggle").checked = adjacentSitesEnabled;
  const container = document.getElementById("adjacentSitesContainer");
  if (container) {
    container.style.display = adjacentSitesEnabled ? "" : "none";
  }

  document.getElementById("callHistorySource").value = callHistorySource;
}

function showHome() {
  const settings = document.getElementById("settings-container");
  const about = document.getElementById("about-container");

  if (settings) settings.style.display = "none";
  if (about) about.style.display = "none";

  const btnSettings = document.getElementById("btn-settings");
  const btnAbout = document.getElementById("btn-about");

  if (btnSettings) btnSettings.style.color = "";
  if (btnAbout) btnAbout.style.color = "";
}

function hex(val) {
  return val.toString(16).toUpperCase();
}


function csvTable() {
	// save the call history table to csv
	
    const table_id = "callHistoryContainer";
    const separator = ',';

    const rows = document.querySelectorAll(`table#${table_id} tr`);
    const csv = [];

    // First valid header row is at index 1
    const headerRow = rows[1]?.querySelectorAll('th');
    if (headerRow && headerRow.length > 0) {
        const headers = Array.from(headerRow).map(cell => {
            let data = cell.innerText.trim().replace(/(\r\n|\n|\r)/gm, '').replace(/\s+/g, ' ');
            data = data.replace(/"/g, '""');
            return `"${data}"`;
        });
        csv.push(headers.join(separator));
    }

    // Data rows from index 2 onward
    for (let i = 2; i < rows.length; i++) {
        const cols = rows[i].querySelectorAll('td');
        if (cols.length === 0) continue;  // Skip empty or non-data rows

        const row = Array.from(cols).map(cell => {
            let data = cell.innerText.trim().replace(/(\r\n|\n|\r)/gm, '').replace(/\s+/g, ' ');
            data = data.replace(/"/g, '""');
            return `"${data}"`;
        });
        csv.push(row.join(separator));
    }

    const csv_string = csv.join('\n');
    const filename = `export_${table_id}_${new Date().toLocaleDateString().replace(/\//g, '-')}.csv`;

    const link = document.createElement('a');
    link.style.display = 'none';
    link.setAttribute('href', 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv_string));
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
