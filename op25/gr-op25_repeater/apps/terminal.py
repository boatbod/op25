#!/usr/bin/env python

# Copyright 2008-2011 Steve Glass
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

import sys
import curses
import curses.textpad
import time
import json
import threading
import traceback
import socket

from gnuradio import gr

KEEPALIVE_TIME = 3.0   # no data received in (seconds)

class q_watcher(threading.Thread):
    def __init__(self, msgq,  callback, **kwds):
        threading.Thread.__init__ (self, **kwds)
        self.setDaemon(1)
        self.msgq = msgq
        self.callback = callback
        self.keep_running = True
        self.start()

    def run(self):
        while(self.keep_running):
            msg = self.msgq.delete_head()
            self.callback(msg)

class curses_terminal(threading.Thread):
    def __init__(self, input_q,  output_q, sock=None, **kwds):
        threading.Thread.__init__ (self, **kwds)
        self.setDaemon(1)
        self.input_q = input_q
        self.output_q = output_q
        self.keep_running = True
        self.last_update = 0
        self.auto_update = True
        self.current_nac = None
        self.maxx = 0
        self.maxy = 0
        self.sock = sock
        self.start()

    def setup_curses(self):
        self.stdscr = curses.initscr()
        self.maxy, self.maxx = self.stdscr.getmaxyx()
        if (self.maxy < 6) or (self.maxx < 60):
            sys.stderr.write("Terminal window too small! Minimum size [70 x 6], actual [%d x %d]\n" % (self.maxx, self.maxy))
            print "Terminal window too small! Minimum size [70 x 6], actual [%d x %d]\n" % (self.maxx, self.maxy)
            self.keep_running = False
            return

        curses.noecho()
        curses.halfdelay(1)

        self.title_bar = curses.newwin(1, self.maxx, 0, 0)
        self.help_bar = curses.newwin(1, self.maxx, self.maxy-1, 0)
        self.top_bar = curses.newwin(1, self.maxx, 1, 0)
        self.freq_list = curses.newwin(self.maxy-5, self.maxx, 2, 0)
        self.active1 = curses.newwin(1, self.maxx-15, self.maxy-3, 0)
        self.active2 = curses.newwin(1, self.maxx-15, self.maxy-2, 0)
        self.status1 = curses.newwin(1, 15, self.maxy-3, self.maxx-15)
        self.status2 = curses.newwin(1, 15, self.maxy-2, self.maxx-15)
        self.prompt = curses.newwin(1, 10, self.maxy-1, 0)
        self.text_win = curses.newwin(1, 11, self.maxy-1, 10)
        self.textpad = curses.textpad.Textbox(self.text_win)
        self.stdscr.refresh()

        self.title_help()

    def resize_curses(self):
        self.maxy, self.maxx = self.stdscr.getmaxyx()
 
        if (self.maxx < 60) or (self.maxy < 6):	# do not resize if window is now too small
            return 

        self.stdscr.erase()

        self.title_bar.resize(1, self.maxx)
        self.help_bar.resize(1, self.maxx)
        self.help_bar.mvwin(self.maxy-1, 0)
        self.top_bar.resize(1, self.maxx)
        self.freq_list.resize(self.maxy-5, self.maxx)
        self.active1.resize(1, self.maxx-15)
        self.active1.mvwin(self.maxy-3, 0)
        self.active2.resize(1, self.maxx-15)
        self.active2.mvwin(self.maxy-2, 0)
        self.status1.resize(1, 15)
        self.status1.mvwin(self.maxy-3, self.maxx-15)
        self.status2.resize(1, 15)
        self.status2.mvwin(self.maxy-2, self.maxx-15)
        self.stdscr.refresh()

        self.title_help()

    def end_terminal(self):
        try:
            curses.endwin()
        except:
            pass

    def title_help(self):
        title_str = "OP25"
        help_str = "(f)req (h)old (s)kip (l)ock (q)uit (1-5)plot (,.<>)tune"
        self.title_bar.erase()
        self.help_bar.erase()
        self.title_bar.addstr(0, 0, title_str.center(self.maxx-1, " "), curses.A_REVERSE)
        self.help_bar.addstr(0, 0, help_str.center(self.maxx-1, " "), curses.A_REVERSE)
        self.title_bar.refresh()
        self.help_bar.refresh()
        self.stdscr.move(1,0)
        self.stdscr.refresh()

    def do_auto_update(self):
        UPDATE_INTERVAL = 0.5	# sec.
        if not self.auto_update:
            return False
        if self.last_update + UPDATE_INTERVAL > time.time():
            return False
        self.last_update = time.time()
        return True

    def process_terminal_events(self):
        # return true signifies end of main event loop
        if curses.is_term_resized(self.maxy, self.maxx) is True:
            self.resize_curses()

        _ORD_S = ord('s')
        _ORD_L = ord('l')
        _ORD_H = ord('h')
        COMMANDS = {_ORD_S: 'skip', _ORD_L: 'lockout', _ORD_H: 'hold'}
        c = self.stdscr.getch()
        if c == ord('u') or self.do_auto_update():
            self.send_command('update', 0)
        if c in COMMANDS.keys():
            self.send_command(COMMANDS[c], 0)
        elif c == ord('q'):
		return True
        elif c == ord('t'):
            if self.current_nac:
                self.send_command('add_default_config', int(self.current_nac))
        elif c == ord('f'):
            self.prompt.addstr(0, 0, 'Frequency')
            self.prompt.refresh()
            self.text_win.erase()
            response = self.textpad.edit()
            self.prompt.erase()
            self.prompt.refresh()
            self.text_win.erase()
            self.text_win.refresh()
            self.title_help()
            try:
                freq = float(response)
                if freq < 10000:
                    freq *= 1000000.0
            except:
                freq = None
            if freq:
                self.send_command('set_freq', freq)
        elif c == ord('H'):
            self.prompt.addstr(0, 0, 'Hold tgid')
            self.prompt.refresh()
            self.text_win.erase()
            response = self.textpad.edit()
            self.prompt.erase()
            self.prompt.refresh()
            self.text_win.erase()
            self.text_win.refresh()
            self.title_help()
            try:
                tgid = int(response)
                if (tgid < 0) or (tgid > 65535):
                    tgid = 0
            except:
                tgid = 0
            self.send_command('hold', tgid)
 
        elif c == ord(','):
            self.send_command('adj_tune', -100)
        elif c == ord('.'):
            self.send_command('adj_tune', 100)
        elif c == ord('<'):
            self.send_command('adj_tune', -1200)
        elif c == ord('>'):
            self.send_command('adj_tune', 1200)
        elif (c >= ord('1') ) and (c <= ord('5')):
            self.send_command('toggle_plot', (c - ord('0')))
        elif c == ord('d'):
            self.send_command('dump_tgids', 0)
        elif c == ord('x'):
            assert 1 == 0
        return False

    def process_json(self, js):
        # return true signifies end of main event loop
        msg = json.loads(js)
        if msg['json_type'] == 'trunk_update':
            nacs = [x for x in msg.keys() if x.isnumeric() ]
            if not nacs:
                return
            if msg.get('nac'):
                current_nac = str(msg['nac'])
            else:
                times = {msg[nac]['last_tsbk']:nac for nac in nacs}
                current_nac = times[ sorted(times.keys(), reverse=True)[0] ]
            self.current_nac = current_nac
            s = 'NAC 0x%x' % (int(current_nac))
            s += ' WACN 0x%x' % (msg[current_nac]['wacn'])
            s += ' SYSID 0x%x' % (msg[current_nac]['sysid'])
            # Modified to clarify what these frequencies are on the control channel (e.g. send or receive)
            s += ' RX %f' % (msg[current_nac]['rxchan']/ 1000000.0)  
            s += ' | TX %f' % (msg[current_nac]['txchan']/ 1000000.0)
            # As a lowly Technician-class ham (KD8VAX), I didn't know what a tsbks was and it 
            # kinda bugged me.  It's not an easy answer to find, so let's tell the user something
            # a *little* more English-like.
            s += ' trnk sig blks %d' % (msg[current_nac]['tsbks'])
            freqs = sorted(msg[current_nac]['frequencies'].keys())
            s = s[:(self.maxx - 1)]
            self.top_bar.erase()
            self.top_bar.addstr(0, 0, s)
            self.top_bar.refresh()
            self.freq_list.erase()
            for i in xrange(len(freqs)):
                if i > (self.maxy - 6):
                    break
                s=msg[current_nac]['frequencies'][freqs[i]]
                s = s[:(self.maxx - 1)]
                self.freq_list.addstr(i, 0, s)
            self.freq_list.refresh()
            self.status1.erase()
            if 'srcaddr' in msg:
                srcaddr = msg['srcaddr']
                if (srcaddr != 0) and (srcaddr != 0xffffff):
                    s = '%d' % (srcaddr)
                    s = s[:14]
                    self.status1.addstr(0, (14-len(s)), s)
            self.status1.refresh()
            self.status2.erase()
            if 'encrypted' in msg:
                encrypted = msg['encrypted']
                if encrypted != 0:
                    s = 'ENCRYPTED'
                    self.status2.addstr(0, (14-len(s)), s, curses.A_REVERSE)
            self.status2.refresh()
            self.stdscr.refresh()
        elif msg['json_type'] == 'change_freq':
            s = 'Frequency %f' % (msg['freq'] / 1000000.0)
            if msg['fine_tune'] is not None:
                s +='(%d)' % msg['fine_tune']
            if msg['tgid'] is not None:
                s += ' Talkgroup ID %s' % (msg['tgid'])
                if msg['tdma'] is not None:
                    s += ' TDMA Slot %s' % msg['tdma']
            s = s[:(self.maxx - 16)]
            self.active1.erase()
            self.active2.erase()
            self.active1.addstr(0, 0, s)
            self.active1.refresh()
            if msg['tag']:
                s = msg['tag']
                s = s[:(self.maxx - 16)]
                self.active2.addstr(0, 0, s)
            self.active2.refresh()
            self.stdscr.refresh()
        return False

    def process_q_events(self):
        # return true signifies end of main event loop
        while True:
            if curses.is_term_resized(self.maxy, self.maxx) is True:
                self.resize_curses()
            if self.input_q.empty_p():
                break
            msg = self.input_q.delete_head_nowait()
            if msg.type() == -4:
                return self.process_json(msg.to_string())
        return False

    def send_command(self, command, data):
        if self.sock:
            self.sock.send(json.dumps({'command': command, 'data': data}))
        else:
            msg = gr.message().make_from_string(command, -2, data, 0)
            self.output_q.insert_tail(msg)

    def run(self):
        try:
            self.setup_curses()

            while(self.keep_running):
                if self.process_terminal_events():
                    break
                if self.process_q_events():
                    break
        except:
            sys.stderr.write('terminal: exception occurred (%d, %d)\n' % (self.maxx, self.maxy))
            sys.stderr.write('terminal: exception:\n%s\n' % traceback.format_exc())
        finally:
            self.end_terminal()
            self.keep_running = False
        self.send_command('quit', 0)

class http_terminal(threading.Thread):
    def __init__(self, input_q,  output_q, endpoint, **kwds):
        from http import http_server

        threading.Thread.__init__ (self, **kwds)
        self.setDaemon(1)
        self.input_q = input_q
        self.output_q = output_q
        self.endpoint = endpoint
        self.keep_running = True
        self.server = http_server(self.input_q, self.output_q, self.endpoint)

        self.start()

    def end_terminal(self):
        self.keep_running = False

    def run(self):
        self.server.run()

class udp_terminal(threading.Thread):
    def __init__(self, input_q,  output_q, port, **kwds):
        threading.Thread.__init__ (self, **kwds)
        self.setDaemon(1)
        self.input_q = input_q
        self.output_q = output_q
        self.keep_running = True
        self.port = port
        self.remote_ip = '127.0.0.1'
        self.remote_port = 0
        self.keepalive_until = 0

        self.setup_socket(port)
        self.q_handler = q_watcher(self.input_q, self.process_qmsg)
        self.start()

    def setup_socket(self, port):
        self.sock =  socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', port))

    def process_qmsg(self, msg):
        if time.time() >= self.keepalive_until:
            return
        s = msg.to_string()
        if msg.type() == -4 and self.remote_port > 0:
            self.sock.sendto(s, (self.remote_ip, self.remote_port))

    def end_terminal(self):
        self.keep_running = False

    def run(self):
        while self.keep_running:
            data, addr = self.sock.recvfrom(2048)
            data = json.loads(data)
            if data['command'] == 'quit':
                self.keepalive_until = 0
                continue
            msg = gr.message().make_from_string(str(data['command']), -2, data['data'], 0)
            self.output_q.insert_tail(msg)
            self.remote_ip = addr[0]
            self.remote_port = addr[1]
            self.keepalive_until = time.time() + KEEPALIVE_TIME

def op25_terminal(input_q,  output_q, terminal_type):
        if terminal_type == 'curses':
            return curses_terminal(input_q, output_q)
        elif terminal_type[0].isdigit():
            port = int(terminal_type)
            return udp_terminal(input_q, output_q, port)
        elif terminal_type.startswith('http:'):
            return http_terminal(input_q, output_q, terminal_type.replace('http:', ''))
        else:
            sys.stderr.write('warning: unsupported terminal type: %s\n' % terminal_type)
            return None

class terminal_client(object):
    def __init__(self):
        self.input_q = gr.msg_queue(10)
        self.keep_running = True
        self.terminal = None

        ip_addr = sys.argv[1]
        port = int(sys.argv[2])

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.connect((ip_addr, port))
        self.sock.settimeout(0.1)

        self.terminal = curses_terminal(self.input_q, None, sock=self.sock)

    def run(self): 
        while self.keep_running:
            try:
                js, addr = self.sock.recvfrom(2048)
                msg = gr.message().make_from_string(js, -4, 0, 0)
                self.input_q.insert_tail(msg)
            except socket.timeout:
                pass
            except:
                raise
            if not self.terminal.keep_running:
                self.keep_running = False

if __name__ == '__main__':
    terminal = None
    try:
        terminal = terminal_client()
        terminal.run()
    except:
        sys.stderr.write('terminal: exception occurred\n')
        sys.stderr.write('terminal: exception:\n%s\n' % traceback.format_exc())
    finally:
        if terminal is not None and terminal.terminal is not None:
            terminal.terminal.end_terminal()
