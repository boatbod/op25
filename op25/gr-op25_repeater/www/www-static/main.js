
// Copyright 2017, 2018 Max H. Parke KA1RBI
// Copyright 2018, 2019 gnorbury@bondcar.com
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

var d_debug = 1;

var http_req = new XMLHttpRequest();
var counter1 = 0;
var error_val = null;
var fine_tune = null;
var current_tgid = null;
var send_busy = 0;
var send_qfull = 0;
var send_queue = [];
var req_cb_count = 0;
var request_count = 0;
var nfinal_count = 0;
var n200_count = 0;
var r200_count = 0;
var SEND_QLIMIT = 5;
var c_freq = 0;
var c_system = null;
var c_tag = null;
var c_srcaddr = 0;
var c_grpaddr = 0;
var c_encrypted = 0;
var c_nac = 0;

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
    var div_s2     = document.getElementById("div_s2")
    var div_s3     = document.getElementById("div_s3")
    var ctl1 = document.getElementById("controls1");
    var ctl2 = document.getElementById("controls2");
    if (command == "status") {
        div_status.style['display'] = "";
        div_plot.style['display'] = "none";
        div_about.style['display'] = "none";
        div_s2.style['display'] = "";
        div_s3.style['display'] = "";
        ctl1.style['display'] = "";
        ctl2.style['display'] = "none";
    }
    else if (command == "plot") {
        div_status.style['display'] = "";
        div_plot.style['display'] = "";
        div_about.style['display'] = "none";
        div_s2.style['display'] = "none";
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
    else {
        var img = document.getElementById("img0");
        img.style["display"] = "none";
    }
    error_val = d["error"];
    fine_tune = d['fine_tune'];
}

// frequency, system, and talkgroup display

function change_freq(d) {
    c_freq = d['freq'];
    c_system = d['system'];
    current_tgid = d['tgid'];
    c_tag = d['tag'];
    c_stream_url = d['stream_url'];
    channel_status();
}

function channel_status() {
    var html;
    var s2_freq = document.getElementById("s2_freq");
    var s2_tg = document.getElementById("s2_tg");
    var s2_grp = document.getElementById("s2_grp");
    var s2_src = document.getElementById("s2_src");

    html = "";
    if (c_stream_url != "") {
        html += "<a href=\"" + c_stream_url + "\">";
    }
    if (c_freq != 0) {
        html += "<span class=\"value\">" + c_freq / 1000000.0 + "</span>";
    }
    if (c_system != null)
    {
        html += "<span class=\"value\"> &nbsp;" + c_system + "</span>";
    }
    if (c_stream_url != "") {
        html += "</a>"
    }
    s2_freq.innerHTML = html

    html = "";
    if (current_tgid != null) {
        html += "<span class=\"value\">" + c_tag + "</span>";
        if (c_encrypted) {
            html += "<span class=\"label\">[ENCRYPTED]</span>";
        }
    }
    s2_tg.innerHTML = html;

    html = "";
    if (current_tgid != null)
        html += "<span class=\"value\">" + current_tgid + "</span>";
    else if (c_grpaddr != 0)
        html += "<span class=\"value\">" + c_grpaddr + "</span>";
    s2_grp.innerHTML = html;

    html = "";
    if ((c_srcaddr != 0) && (c_srcaddr != 0xffffff)) 
        html += "<span class=\"value\">" + c_srcaddr + "</span>";
    s2_src.innerHTML = html;
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
    var srcaddr = 0;
    var encrypted = 0;
    var html = "";

    if (d['nac'] != undefined)
        c_nac = d['nac']

    for (var nac in d) {
        if (!is_digit(nac.charAt(0)))
            continue;
        if (nac != c_nac)
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
            html += "<span class=\"label\">Frequency error: </span><span class=\"value\">" + error_val + " Hz. (approx) </span><br>";
        }
        if (fine_tune != null) {
            html += "<span class=\"label\">Fine tune offset: </span><span class=\"value\">" + fine_tune + "</span>";
        }

        var div_s1 = document.getElementById("div_s1");
        div_s1.innerHTML = html;

// system frequencies table
        html = ""
        html += "<div class=\"info\"><div class=\"system\">";
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

    if (d['srcaddr'] != undefined)
        c_srcaddr = d['srcaddr']
    if (d['grpaddr'] != undefined)
        c_grpaddr = d['grpaddr']
    if (d['encrypted'] != undefined)
        c_encrypted = d['encrypted']

    var div_s3 = document.getElementById("div_s3");
    div_s3.innerHTML = html;

    channel_status();
}


function http_req_cb() {
    req_cb_count += 1;
    s = http_req.readyState;
    if (s != 4) {
        nfinal_count += 1;
        return;
    }
    if (http_req.status != 200) {
        n200_count += 1;
        return;
    }
    r200_count += 1;
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
    f_debug();
}

function send_command(command, data) {
    request_count += 1;
    if (send_queue.length >= SEND_QLIMIT) {
        send_qfull += 1;
        send_queue.unshift();
    }
    send_queue.push( {"command": command, "data": data} );
    send_process();
}

function send_process() {
    s = http_req.readyState;
    if (s != 0 && s != 4) {
        send_busy += 1;
        return;
    }
    http_req.open("POST", "/");
    http_req.onreadystatechange = http_req_cb;
    http_req.setRequestHeader("Content-type", "application/json");
    cmd = JSON.stringify( send_queue );
    send_queue = [];
    http_req.send(cmd);
}

function f_tune_button(command) {
    send_command('adj_tune', command);
}

function f_plot_button(command) {
    send_command('toggle_plot', command);
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

    send_command(command, _tgid);
}

function f_debug() {
	if (!d_debug) return;
	var html = "busy " + send_busy;
	html += " qfull " + send_qfull;
	html += " sendq size " + send_queue.length;
	html += " requests " + request_count;
	html += "<br>callbacks:";
	html += " total=" + req_cb_count;
	html += " incomplete=" + nfinal_count;
	html += " error=" + n200_count;
	html += " OK=" + r200_count;
	html += "<br>";
	var div_debug = document.getElementById("div_debug");
	div_debug.innerHTML = html;
}
