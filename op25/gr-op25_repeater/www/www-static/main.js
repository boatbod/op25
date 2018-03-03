
// Copyright 2017, 2018 Max H. Parke KA1RBI
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
    var div_list = ["status", "plot", "about"];
    for (var i=0; i<div_list.length; i++) {
        var ele = document.getElementById("div_" + div_list[i]);
        if (command == div_list[i])
            ele.style['display'] = "";
        else
            ele.style['display'] = "none";
    }
    var ctl = document.getElementById("controls");
    if (command == "status")
        ctl.style['display'] = "";
    else
        ctl.style['display'] = "none";
    nav_update(command);
}

var http_req = new XMLHttpRequest();

var counter1 = 0;
var error_val = null;
var current_tgid = null;

function is_digit(s) {
    if (s >= "0" && s <= "9")
        return true;
    else
        return false;
}

function rx_update(d) {
    if (d["files"].length > 0) {
        for (var i=0; i<d["files"].length; i++) {
            var img = document.getElementById("img" + i);
            if (img['src'] != d["files"][i]) {
                img['src'] = d["files"][i];
                img.style["display"] = "";
            }
        }
    }
    error_val = d["error"];
}

// frequency, system, and talkgroup display

function change_freq(d) {
    var html = "<span class=\"label\">Frequency: </span><span class=\"value\">" + d['freq'] / 1000000.0;
    html += "</span> <span class=\"systgid\"> &nbsp;" + d['system'] + " </span> ";
    if (d['tgid'] != null) {
        html += "<span class=\"label\">Talkgroup ID: </span><span class=\"value\"> " + d['tgid'];
        html += "</span> <span class=\"systgid\"> &nbsp;" + d['tag'] + " </span>";
    }
    html += "<br>";
    var div_s2 = document.getElementById("div_s2");
    div_s2.innerHTML = html;
    div_s2.style["display"] = "";
    if (d['tgid'] != null)
        current_tgid = d['tgid'];
    if (current_tgid != null) {
        var div_s3 = document.getElementById("div_s3");
        div_s3.style["display"] = "";
    }
}

// adjacent sites table

function adjacent_data(d) {
    if (Object.keys(d).length < 1) {
        var html = "</div>";
        return html;
    }
    var html = "<div class=\"adjacent\">";
    html += "<table border=1 borderwidth=0 cellpadding=0 cellspacing=0 width=100%>";
    html += "<tr><th colspan=99 style=\"align: center\">Adjacent Sites</th></tr>";
    html += "<tr><th>Frequency</th><th>RFSS</th><th>Site</th><th>Uplink</th></tr>";
    var ct = 0;
    for (var freq in d) {
        var color = "#d0d0d0";
        if ((ct & 1) == 0)
            color = "#c0c0c0";
        ct += 1;
        html += "<tr style=\"background-color: " + color + ";\"><td>" + freq / 1000000.0 + "</td><td>" + d[freq]["rfid"] + "</td><td>" + d[freq]["stid"] + "</td><td>" + (d[freq]["uplink"] / 1000000.0) + "</td></tr>";
    }
    html += "</table></div></div><br><br>";

// end adjacent sites table

    return html;
}

// additional system info: wacn, sysID, rfss, site id, secondary control channels, freq error

function trunk_update(d) {
    var do_hex = {"syid":0, "sysid":0, "wacn": 0};
    var do_float = {"rxchan":0, "txchan":0};
    var html = "";
    for (var nac in d) {
        if (!is_digit(nac.charAt(0)))
            continue;
        html += "<span class=\"nac\">";
        html += "NAC " + "0x" + parseInt(nac).toString(16) + " ";
        html += d[nac]['rxchan'] / 1000000.0;
        html += " / ";
        html += d[nac]['txchan'] / 1000000.0;
        html += " tsbks " + d[nac]['tsbks'];
        html += "</span><br>";

        html += "<span class=\"label\">WACN: </span>" + "<span class=\"value\">0x" + parseInt(d[nac]['wacn']).toString(16) + " </span>";
        html += "<span class=\"label\">System ID: </span>" + "<span class=\"value\">0x" + parseInt(d[nac]['sysid']).toString(16) + " </span>";
        html += "<span class=\"label\">RFSS ID: </span><span class=\"value\">" + d[nac]['rfid'] + " </span>";
        html += "<span class=\"label\">Site ID: </span><span class=\"value\">" + d[nac]['stid'] + "</span><br>";
        if (d[nac]["secondary"].length) {
            html += "<span class=\"label\">Secondary control channel(s): </span><span class=\"value\"> ";
            for (i=0; i<d[nac]["secondary"].length; i++) {
                html += d[nac]["secondary"][i] / 1000000.0;
                html += " ";
            }
            html += "</span><br>";
        }
        if (error_val != null) {
            html += "<span class=\"label\">Frequency error: </span><span class=\"value\">" + error_val + " Hz. (approx) </span>";
        }

// system frequencies table

        html += "<p><div class=\"info\"><div class=\"system\">";
        html += "<table border=1 borderwidth=0 cellpadding=0 cellspacing=0 width=100%>"; // was width=350
        html += "<tr><th colspan=99 style=\"align: center\">System Frequencies</th></tr>";
        html += "<tr><th>Frequency</th><th>Last Seen</th><th colspan=2>Talkgoup ID</th><th>Count</th></tr>";
        var ct = 0;
        for (var freq in d[nac]['frequency_data']) {
            tg2 = d[nac]['frequency_data'][freq]['tgids'][1];
            if (tg2 == null)
                tg2 = "&nbsp;";
            var color = "#d0d0d0";
            if ((ct & 1) == 0)
                color = "#c0c0c0";
            ct += 1;
            html += "<tr style=\"background-color: " + color + ";\"><td>" + parseInt(freq) / 1000000.0 + "</td><td>" + d[nac]['frequency_data'][freq]['last_activity'] + "</td><td>" + d[nac]['frequency_data'][freq]['tgids'][0] + "</td><td>" + tg2 + "</td><td>" + d[nac]['frequency_data'][freq]['counter'] + "</td></tr>";
        }
        html += "</table></div>";

// end system freqencies table

        html += adjacent_data(d[nac]['adjacent_data']);
    }
    var div_s1 = document.getElementById("div_s1");
    div_s1.innerHTML = html;
}


function http_req_cb() {
    s = http_req.readyState;
    if (s != 4)
        return;
    if (http_req.status != 200)
        return;
    var dl = JSON.parse(http_req.responseText);
    var dispatch = {'trunk_update': trunk_update, 'change_freq': change_freq, 'rx_update': rx_update}
    for (var i=0; i<dl.length; i++) {
        var d = dl[i];
        if (!("json_type" in d))
            continue;
        if (!(d["json_type"] in dispatch))
            continue;
        dispatch[d["json_type"]](d);
    }
}

function do_onload() {
    var ele = document.getElementById("div_status");
    ele.style["display"] = "";
    setInterval(do_update, 1000);
    b = document.getElementById("b1");
    b.className = "nav-button-active";
}

function do_update() {
    send_command("update", 0);
}

function send_command(command, data) {
    s = http_req.readyState;
    if (s != 0 && s != 4) {
        return;
    }
    http_req.open("POST", "/");
    http_req.onreadystatechange = http_req_cb;
    http_req.setRequestHeader("Content-type", "application/json");
    cmd = JSON.stringify( {"command": command, "data": data} );
    http_req.send(cmd);
}

function f_scan_button(command) {
    if (current_tgid == null)
        send_command(command, -1);
    else
        send_command(command, current_tgid);
}
