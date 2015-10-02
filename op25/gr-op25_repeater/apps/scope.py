#!/usr/bin/env python

# Copyright 2008-2011 Steve Glass
# 
# Copyright 2011, 2012, 2013, 2014, 2015 Max H. Parke KA1RBI
# 
# Copyright 2003,2004,2005,2006 Free Software Foundation, Inc.
#         (from radiorausch)
# 
# This file is part of OP25 and part of GNU Radio
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

import os
import pickle
import sys
import threading
import wx
import wx.html
import wx.wizard
import math
import numpy
import time
import re
try:
    import Hamlib
except:
    pass

try:
    import Numeric
except:
    pass

from gnuradio import audio, eng_notation, gr, gru, filter, blocks, fft, analog, digital
from gnuradio.eng_option import eng_option
from gnuradio.wxgui import stdgui2, fftsink2, scopesink2, form
from math import pi
from optparse import OptionParser

import op25
import op25_repeater

import gnuradio.wxgui.plot as plot

import trunking

import p25_demodulator
import p25_decoder

sys.path.append('tdma')
import lfsr

#speeds = [300, 600, 900, 1200, 1440, 1800, 1920, 2400, 2880, 3200, 3600, 3840, 4000, 4800, 6000, 6400, 7200, 8000, 9600, 14400, 19200]
speeds = [4800, 6000]

os.environ['IMBE'] = 'soft'

WIRESHARK_PORT = 23456

msg_wxDATA_EVENT = wx.NewEventType()

def msg_EVT_DATA_EVENT(win, func):
    win.Connect(-1, -1, msg_wxDATA_EVENT, func)

class msg_DataEvent(wx.PyEvent):
    def __init__(self, data):
        wx.PyEvent.__init__(self)
        self.SetEventType (msg_wxDATA_EVENT)
        self.data = data

    def Clone (self): 
        self.__class__ (self.GetId())

# The P25 receiver
#
class p25_rx_block (stdgui2.std_top_block):

    # Initialize the P25 receiver
    #
    def __init__(self, frame, panel, vbox, argv):

        stdgui2.std_top_block.__init__(self, frame, panel, vbox, argv)

        # command line argument parsing
        parser = OptionParser(option_class=eng_option)
        parser.add_option("--args", type="string", default="", help="device args")
        parser.add_option("--antenna", type="string", default="", help="select antenna")
        parser.add_option("-a", "--audio", action="store_true", default=False, help="use direct audio input")
        parser.add_option("-A", "--audio-if", action="store_true", default=False, help="soundcard IF mode (use --calibration to set IF freq)")
        parser.add_option("-I", "--audio-input", type="string", default="", help="pcm input device name.  E.g., hw:0,0 or /dev/dsp")
        parser.add_option("-i", "--input", default=None, help="input file name")
        parser.add_option("-b", "--excess-bw", type="eng_float", default=0.2, help="for RRC filter", metavar="Hz")
        parser.add_option("-c", "--calibration", type="eng_float", default=0.0, help="USRP offset or audio IF frequency", metavar="Hz")
        parser.add_option("-C", "--costas-alpha", type="eng_float", default=0.04, help="value of alpha for Costas loop", metavar="Hz")
        parser.add_option("-f", "--frequency", type="eng_float", default=0.0, help="USRP center frequency", metavar="Hz")
        parser.add_option("-F", "--ifile", type="string", default=None, help="read input from complex capture file")
        parser.add_option("-H", "--hamlib-model", type="int", default=None, help="specify model for hamlib")
        parser.add_option("-s", "--seek", type="int", default=0, help="ifile seek in K")
        parser.add_option("-L", "--logfile-workers", type="int", default=None, help="number of demodulators to instantiate")
        parser.add_option("-S", "--sample-rate", type="int", default=320e3, help="source samp rate")
        parser.add_option("-t", "--tone-detect", action="store_true", default=False, help="use experimental tone detect algorithm")
        parser.add_option("-T", "--trunk-conf-file", type="string", default=None, help="trunking config file name")
        parser.add_option("-v", "--verbosity", type="int", default=10, help="message debug level")
        parser.add_option("-V", "--vocoder", action="store_true", default=False, help="voice codec")
        parser.add_option("-o", "--offset", type="eng_float", default=0.0, help="tuning offset frequency [to circumvent DC offset]", metavar="Hz")
        parser.add_option("-p", "--pause", action="store_true", default=False, help="block on startup")
        parser.add_option("-w", "--wireshark", action="store_true", default=False, help="output data to Wireshark")
        parser.add_option("-W", "--wireshark-host", type="string", default="127.0.0.1", help="Wireshark host")
        parser.add_option("-r", "--raw-symbols", type="string", default=None, help="dump decoded symbols to file")
        parser.add_option("-R", "--rx-subdev-spec", type="subdev", default=(0, 0), help="select USRP Rx side A or B (default=A)")
        parser.add_option("-g", "--gain", type="eng_float", default=None, help="set USRP gain in dB (default is midpoint) or set audio gain")
        parser.add_option("-G", "--gain-mu", type="eng_float", default=0.025, help="gardner gain")
        parser.add_option("-N", "--gains", type="string", default=None, help="gain settings")
        #parser.add_option("-O", "--audio-output", type="string", default="plughw:0,0", help="audio output device name")
        parser.add_option("-O", "--audio-output", type="string", default="default", help="audio output device name")
        parser.add_option("-q", "--freq-corr", type="eng_float", default=0.0, help="frequency correction")
        parser.add_option("-2", "--phase2-tdma", action="store_true", default=False, help="enable phase2 tdma decode")
        (options, args) = parser.parse_args()
        if len(args) != 0:
            parser.print_help()
            sys.exit(1)

        self.channel_rate = 0
        self.baseband_input = False
        self.rtl_found = False
        self.channel_rate = options.sample_rate

        self.src = None
        if not options.input:
            # check if osmocom is accessible
            try:
                import osmosdr
                self.src = osmosdr.source(options.args)
            except Exception:
                print "osmosdr source_c creation failure"
                ignore = True
 
            if "rtl" in options.args.lower():
                #print "'rtl' has been found in options.args (%s)" % (options.args)
                self.rtl_found = True

            gain_names = self.src.get_gain_names()
            for name in gain_names:
                range = self.src.get_gain_range(name)
                print "gain: name: %s range: start %d stop %d step %d" % (name, range[0].start(), range[0].stop(), range[0].step())
            if options.gains:
                for tuple in options.gains.split(","):
                    name, gain = tuple.split(":")
                    gain = int(gain)
                    print "setting gain %s to %d" % (name, gain)
                    self.src.set_gain(gain, name)

            rates = self.src.get_sample_rates()
            try:
                print 'supported sample rates %d-%d step %d' % (rates.start(), rates.stop(), rates.step())
            except:
                pass	# ignore

            if options.freq_corr:
                self.src.set_freq_corr(options.freq_corr)

        if options.audio:
            self.channel_rate = 48000
            self.baseband_input = True

        if options.audio_if:
            self.channel_rate = 96000

        if options.ifile:
            self.channel_rate = 96000	# TODO: fixme

        # setup (read-only) attributes
        self.symbol_rate = 4800
        self.symbol_deviation = 600.0
        self.basic_rate = 48000
        _default_speed = 4800

        # keep track of flow graph connections
        self.cnxns = []

        self.datascope_raw_input = False
        self.data_scope_connected = False

        self.constellation_scope_connected = False

        self.options = options

        for i in xrange(len(speeds)):
            if speeds[i] == _default_speed:
                self.current_speed = i
                self.default_speed_idx = i

        if options.hamlib_model:
            self.hamlib_attach(options.hamlib_model)

        # initialize the UI
        # 
        self.__init_gui(frame, panel, vbox)

        # wait for gdb
        if options.pause:
            print 'Ready for GDB to attach (pid = %d)' % (os.getpid(),)
            raw_input("Press 'Enter' to continue...")

        # configure specified data source
        if options.input:
            self.open_file(options.input)
        elif options.frequency:
            self._set_state("CAPTURING")
            self.open_usrp()
        elif options.audio_if:
            self._set_state("CAPTURING")
            self.open_audio_c(self.channel_rate, options.gain, options.audio_input)
        elif options.audio:
            self._set_state("CAPTURING")
            self.open_audio(self.channel_rate, options.gain, options.audio_input)
            # skip past unused FFT spectrum plot
            self.notebook.AdvanceSelection()
        elif options.ifile:
            self._set_state("CAPTURING")
            self.open_ifile(self.channel_rate, options.gain, options.ifile, options.seek)
        else:
            self._set_state("STOPPED")

    # setup common flow graph elements
    #
    def __build_graph(self, source, capture_rate):
        global speeds
        global WIRESHARK_PORT
        # tell the scope the source rate
        self.spectrum.set_sample_rate(capture_rate)

        self.rx_q = gr.msg_queue(100)
        msg_EVT_DATA_EVENT(self.frame, self.msg_data)
        udp_port = 0
        if self.options.wireshark:
            udp_port = WIRESHARK_PORT

        self.tdma_state = False
        self.xor_cache = {}

        self.fft_state  = False
        self.c4fm_state = False
        self.fscope_state = False
        self.corr_state = False
        self.fac_state = False
        self.fsk4_demod_connected = False
        self.psk_demod_connected = False
        self.fsk4_demod_mode = False
        self.corr_i_chan = False

        if self.baseband_input:
            self.demod = p25_demodulator.p25_demod_fb(input_rate=capture_rate)
            self.set_connection(c4fm=1)
        else:	# complex input
            # local osc
            self.lo_freq = self.options.offset
            if self.options.audio_if or self.options.ifile or self.options.input:
                self.lo_freq += self.options.calibration
            self.demod = p25_demodulator.p25_demod_cb( input_rate = capture_rate,
                                                       demod_type = 'cqpsk',		### FIXME
                                                       relative_freq = self.lo_freq,
                                                       offset = self.options.offset,
                                                       if_rate = 48000,
                                                       gain_mu = self.options.gain_mu,
                                                       costas_alpha = self.options.costas_alpha,
                                                       symbol_rate = self.symbol_rate)
            self.set_connection(fft=1)
            self.connect_demods()

        udp_port = 0
        if self.options.wireshark:
            udp_port = WIRESHARK_PORT

        num_ambe = 0
        if self.options.phase2_tdma:
            num_ambe = 1

        self.decoder = p25_decoder.p25_decoder_sink_b(dest='audio', do_imbe=True, num_ambe=num_ambe, wireshark_host=self.options.wireshark_host, udp_port=udp_port, do_msgq = True, msgq=self.rx_q, audio_output=self.options.audio_output, debug=self.options.verbosity)

        # connect it all up
        self.connect(source, self.demod, self.decoder)

        if self.options.raw_symbols:
            self.sink_sf = blocks.file_sink(gr.sizeof_char, self.options.raw_symbols)
            self.connect(self.demod, self.sink_sf)

        logfile_workers = []
        if self.options.phase2_tdma:
            num_ambe = 2
        if self.options.logfile_workers:
            for i in xrange(self.options.logfile_workers):
                demod = p25_demodulator.p25_demod_cb(input_rate=capture_rate,
                                                     demod_type='cqpsk',	### FIXME
                                                     offset=self.options.offset)
                decoder = p25_decoder.p25_decoder_sink_b(debug = self.options.verbosity, do_imbe = self.options.vocoder, num_ambe=num_ambe)
                logfile_workers.append({'demod': demod, 'decoder': decoder, 'active': False})
                self.connect(source, demod, decoder)

        self.trunk_rx = trunking.rx_ctl(frequency_set = self.change_freq, debug = self.options.verbosity, conf_file = self.options.trunk_conf_file, logfile_workers=logfile_workers)

        self.du_watcher = du_queue_watcher(self.rx_q, self.trunk_rx.process_qmsg)

    # Connect up the flow graph
    #
    def __connect(self, cnxns):
        for l in cnxns:
            for b in l:
                if b == l[0]:
                    p = l[0]
                else:
                    self.connect(p, b)
                    p = b
        self.cnxns.extend(cnxns)

    # Disconnect the flow graph
    #
    def __disconnect(self):
        for l in self.cnxns:
            for b in l:
                if b == l[0]:
                    p = l[0]
                else:
                    self.disconnect(p, b)
                    p = b
        self.cnxns = []

    def msg_data(self, evt):
        params = evt.data
        freq = params['freq']
        self.myform['freq'].set_value('%s' % (freq / 1000000.0))
        talkgroup = params['tgid']
        tag = params['tag']
        if not talkgroup:
            talkgroup = 0
        if not tag:
            tag = ''
        tg = '%s (%d)' % (tag, talkgroup)
        if talkgroup == 0 and tag == '':
            tg = ''
        self.myform['talkgroup'].set_value(tg)
        nac = params['nac']
        system = params['system']
        self.myform['system'].set_value('%X:%s' % (nac, system))
        if 'tdma' in params and params['tdma'] is not None:
            self.myform['tdma'].set_value('TDMA Slot %d' % (params['tdma']))
        else:
            self.myform['tdma'].set_value('')

    def set_speed(self, new_speed):
     # assumes that lock is held, or that we are in init
        self.disconnect_demods()
        self.current_speed = new_speed
        self.connect_fsk4_demod()

    def set_connection(self,
                         fscope=False,
                         fft=False,
                         corr=False,
                         fac=False,
                         c4fm=False):
     # assumes that lock is held, or that we are in init
        if fac != self.fac_state:
            self.fac_state = fac
            if fac:
                self.demod.connect_complex('mixer', self.fac_scope)
            else:
                self.demod.disconnect_complex()
        if corr != self.corr_state:
            self.corr_state = corr
            if corr:
                if self.corr_i_chan:
                    self.connect(self.arb_resampler, self.to_real, self.real_amp, self.correlation_scope)
                else:
                    self.demod.connect_bb('symbol_filter', self.correlation_scope)
            else:
                if self.corr_i_chan:
                    self.disconnect(self.arb_resampler, self.to_real, self.real_amp, self.correlation_scope)
                else:
                    self.demod.disconnect_bb()

        if fscope != self.fscope_state:
            self.fscope_state = fscope
            if fscope == 0:
                self.demod.disconnect_float()
            else:
                self.demod.connect_float(self.float_scope)

        if fft != self.fft_state:
            self.fft_state = fft
            if fft == 0:
                self.demod.disconnect_complex()
            else:
                self.demod.connect_complex('mixer', self.spectrum)

        if c4fm != self.c4fm_state:
            self.c4fm_state = c4fm
            if c4fm == 0:
                self.demod.disconnect_bb()
            else:
                self.demod.connect_bb('symbol_filter', self.signal_scope)

    def notebook_changed(self, evt):
        sel = self.notebook.GetSelection()
        self.lock()
        self.disconnect_data_scope()
        if not self.baseband_input:
            self.disconnect_constellation_scope()
        if sel == 0:   # spectrum
            if not self.baseband_input:
                self.set_connection(fft=1)
                self.connect_demods()
        elif sel == 1:   # c4fm
            self.set_connection(c4fm=1)
            self.connect_fsk4_demod()
        elif sel == 2:   # datascope
            self.set_connection()
            self.connect_fsk4_demod()
            self.connect_data_scope()
        elif sel == 3:   # constellation (complex)
            if not self.baseband_input:
                self.set_connection()
                self.connect_psk_demod()
                self.connect_constellation_scope()
        elif sel == 4:   # demodulated symbols
            self.connect_demods()
            self.set_connection(fscope=1)
        elif sel == 5:   # traffic pane
            self.connect_demods()
            self.set_connection(fscope=1)
            self.update_traffic(None)
        elif sel == 6:   # correlation
            self.disconnect_demods()
            self.current_speed = self.default_speed_idx # reset speed for corr
            self.data_scope.win.radio_box_speed.SetSelection(self.current_speed)
            self.connect_fsk4_demod()
            self.set_connection(corr=1)
        elif sel == 7:   # fac - fast auto correlation
            if not self.baseband_input:
                self.set_connection(fac=1)
                self.connect_demods()
        self.unlock()

    # initialize the UI
    # 
    def __init_gui(self, frame, panel, vbox):

        def _form_set_freq(kv):
            return self.set_freq(kv['freq'])

        self.frame = frame
        self.frame.CreateStatusBar()
        self.panel = panel
        self.vbox = vbox
        
        # setup the menu bar
        menubar = self.frame.GetMenuBar()

        # setup the "File" menu
        file_menu = menubar.GetMenu(0)
        self.file_new = file_menu.Insert(0, wx.ID_NEW)
        self.frame.Bind(wx.EVT_MENU, self._on_file_new, self.file_new)
        self.file_open = file_menu.Insert(1, wx.ID_OPEN)
        self.frame.Bind(wx.EVT_MENU, self._on_file_open, self.file_open)
        file_menu.InsertSeparator(2)
        self.file_properties = file_menu.Insert(3, wx.ID_PROPERTIES)
        self.frame.Bind(wx.EVT_MENU, self._on_file_properties, self.file_properties)
        file_menu.InsertSeparator(4)
        self.file_close = file_menu.Insert(5, wx.ID_CLOSE)
        self.frame.Bind(wx.EVT_MENU, self._on_file_close, self.file_close)

        # setup the "Edit" menu
        edit_menu = wx.Menu()
        self.edit_undo = edit_menu.Insert(0, wx.ID_UNDO)
        self.frame.Bind(wx.EVT_MENU, self._on_edit_undo, self.edit_undo)
        self.edit_redo = edit_menu.Insert(1, wx.ID_REDO)
        self.frame.Bind(wx.EVT_MENU, self._on_edit_redo, self.edit_redo)
        edit_menu.InsertSeparator(2)
        self.edit_cut = edit_menu.Insert(3, wx.ID_CUT)
        self.frame.Bind(wx.EVT_MENU, self._on_edit_cut, self.edit_cut)
        self.edit_copy = edit_menu.Insert(4, wx.ID_COPY)
        self.frame.Bind(wx.EVT_MENU, self._on_edit_copy, self.edit_copy)
        self.edit_paste = edit_menu.Insert(5, wx.ID_PASTE)
        self.frame.Bind(wx.EVT_MENU, self._on_edit_paste, self.edit_paste)
        self.edit_delete = edit_menu.Insert(6, wx.ID_DELETE)
        self.frame.Bind(wx.EVT_MENU, self._on_edit_delete, self.edit_delete)
        edit_menu.InsertSeparator(7)
        self.edit_select_all = edit_menu.Insert(8, wx.ID_SELECTALL)
        self.frame.Bind(wx.EVT_MENU, self._on_edit_select_all, self.edit_select_all)
        edit_menu.InsertSeparator(9)
        self.edit_prefs = edit_menu.Insert(10, wx.ID_PREFERENCES)
        self.frame.Bind(wx.EVT_MENU, self._on_edit_prefs, self.edit_prefs)
        menubar.Append(edit_menu, "&Edit"); # ToDo use wx.ID_EDIT stuff

        # setup the toolbar
        if True:
            self.toolbar = wx.ToolBar(frame, -1, style = wx.TB_DOCKABLE | wx.TB_HORIZONTAL)
            frame.SetToolBar(self.toolbar)
            icon_size = wx.Size(24, 24)
#           new_icon = wx.ArtProvider.GetBitmap(wx.ART_NEW, wx.ART_TOOLBAR, icon_size)
#           toolbar_new = self.toolbar.AddSimpleTool(wx.ID_NEW, new_icon, "New Capture")
#           open_icon = wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN, wx.ART_TOOLBAR, icon_size)
#           toolbar_open = self.toolbar.AddSimpleTool(wx.ID_OPEN, open_icon, "Open")
            
            self.toolbar.Realize()
        else:
            self.toolbar = None

        # setup the notebook
        self.notebook = wx.Notebook(self.panel)
        self.vbox.Add(self.notebook, 1, wx.EXPAND)       
        # add spectrum scope
        #self.spectrum = fftsink2.fft_sink_c(self.notebook, sample_rate = self.channel_rate, fft_size=512, fft_rate=2, average=False, peak_hold=False)
        self.spectrum = fftsink2.fft_sink_c(self.notebook, sample_rate = self.channel_rate, fft_size=1024, fft_rate=10, avg_alpha=0.35, ref_level=0, average=True, peak_hold=False)
        try:
            self.spectrum_plotter = self.spectrum.win.plotter
        except:
            self.spectrum_plotter = self.spectrum.win.plot
        #self.spectrum_plotter.enable_point_label(False)
        self.spectrum_plotter.Bind(wx.EVT_LEFT_DOWN, self._on_spectrum_left_click)
        self.notebook.AddPage(self.spectrum.win, "Spectrum")
        # add C4FM scope
        self.signal_scope = scopesink2.scope_sink_f(self.notebook, sample_rate = self.basic_rate, v_scale=5, t_scale=0.001)
        try:
            self.signal_plotter = self.signal_scope.win.plotter
        except:
            self.signal_plotter = self.signal_scope.win.graph
        self.notebook.AddPage(self.signal_scope.win, "C4FM")
        # add datascope
        self.data_scope = datascope_sink_f(self.notebook, samples_per_symbol = 10, num_plots = 100)
        self.data_plotter = self.data_scope.win.graph
        wx.EVT_RADIOBOX(self.data_scope.win.radio_box, 11103, self.filter_select)
        wx.EVT_RADIOBOX(self.data_scope.win.radio_box_speed, 11104, self.speed_select)
        self.data_scope.win.radio_box_speed.SetSelection(self.current_speed)
        self.notebook.AddPage(self.data_scope.win, "Datascope")
        # add complex scope
        self.complex_scope = constellation_plot_c(self.notebook, title="Constellation", num_plots=250)
        self.notebook.AddPage(self.complex_scope.win, "Constellation")
        wx.EVT_RADIOBOX(self.complex_scope.win.radio_box_source, 11108, self.source_select)
        # add float scope
        self.float_scope = scopesink2.scope_sink_f(self.notebook, frame_decim=1, sample_rate=self.symbol_rate, v_scale=1, t_scale=0.05)
        try:	#gl
            self.float_plotter = self.float_scope.win.plotter
            self.float_scope.win['marker_1'] = 3.0	# set type = large dots
        except:	#nongl
            self.float_plotter = self.float_scope.win.graph
            self.float_scope.win.set_format_plus()
        self.notebook.AddPage(self.float_scope.win, "Symbols")
        # Traffic snapshot
        self.traffic = TrafficPane(self.notebook, trunk_traffic=True)
        self.notebook.AddPage(self.traffic, "Traffic")
        wx.EVT_BUTTON (self.traffic, 11109, self.update_traffic)
        # add corr scope
        self.correlation_scope = correlation_plot_f(self.notebook, frame_decim=4, sps=10, v_scale=1, t_scale=0.05)
        # self.correlation_plotter = self.correlation_scope.win.plotter
        wx.EVT_RADIOBOX(self.correlation_scope.win.radio_box_corr, 11105, self.corr_select)
        self.notebook.AddPage(self.correlation_scope.win, "Correlation")
        # add fac scope
        self.fac_scope = fac_sink_c(self.notebook, fac_size=32768, sample_rate=self.channel_rate, title="Auto Correlation")
        self.notebook.AddPage(self.fac_scope.win, "FAC")
        # Setup the decoder and report the TUN/TAP device name
        msgq = gr.msg_queue(2)
        # self.decode_watcher = decode_watcher(msgq, self.traffic)
        # self.p25_decoder = op25.decoder_ff(msgq)
        # self.frame.SetStatusText("TUN/TAP: " + self.p25_decoder.device_name())

        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.notebook_changed)

        self.myform = myform = form.form()
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        vbox_form = wx.BoxSizer(wx.VERTICAL)
        myform['system'] = form.static_text_field(
            parent=self.panel, sizer=vbox_form, label="System", weight=0)
        myform['system'].set_value("........................................")
        myform['talkgroup'] = form.static_text_field(
            parent=self.panel, sizer=vbox_form, label="Talkgroup", weight=0)
        myform['talkgroup'].set_value("........................................")

        if self.baseband_input:
            min_gain = 0
            max_gain = 200
            initial_val = 50
        else:
            if self.rtl_found:
                min_gain = 0
                max_gain = 49
                initial_val = self.src.get_gain('LNA')
            else:
                min_gain = 0
                max_gain = 25
                initial_val = 10
            if self.options.trunk_conf_file:
                myform['freq'] = form.static_text_field(
                    parent=self.panel, sizer=vbox_form, label="Frequency", weight=0)
                myform['freq'].set_value('%s' % self.options.frequency)
            else:
                myform['freq'] = form.float_field(
                    parent=self.panel, sizer=vbox_form, label="Frequency", weight=0,
                    callback=myform.check_input_and_call(_form_set_freq, self._set_status_msg))
                myform['freq'].set_value(self.options.frequency)
        myform['tdma'] = form.static_text_field(
            parent=self.panel, sizer=vbox_form, label=None, weight=0)
        myform['tdma'].set_value("")

        hbox.Add(vbox_form, 0, 0)

        vbox_buttons = wx.BoxSizer(wx.VERTICAL)
        skip_button = form.button_with_callback(
            parent=self.panel, label="Skip",
            callback=self.form_skip)
        vbox_buttons.Add(skip_button, 0, 0)
        lockout_button = form.button_with_callback(
            parent=self.panel, label="Lockout",
            callback=self.form_lockout)
        vbox_buttons.Add(lockout_button, 0, 0)
        myform['hold'] = form.checkbox_field(
            parent=self.panel, sizer=vbox_buttons, label="Hold", weight=0,
            callback=myform.check_input_and_call(self.form_hold))
        hbox.Add(vbox_buttons, 0, 0)

        vbox_sliders = wx.BoxSizer(wx.VERTICAL)
        myform['signal_gain'] = form.slider_field(parent=self.panel, sizer=vbox_sliders, label="Signal Gain",
            weight=0,
            min=min_gain, max=max_gain,
            callback=self.set_gain)
        self.myform['signal_gain'].set_value(initial_val)
        if not self.baseband_input:
            myform['freq_tune'] = form.slider_field(parent=self.panel, sizer=vbox_sliders, label="Fine Tune",
                weight=0,
                min=-3000, max=3000,
                callback=self.set_freq_tune)
            if not self.options.trunk_conf_file:
                myform['demod_type'] = form.radiobox_field(parent=self.panel, sizer=hbox, label="Demod",
                    weight=0, choices=['FSK4','PSK'], specify_rows=True,
                    callback=self.demod_type_chg)

        hbox.Add(vbox_sliders, 0, 0)

        vbox_sliders = wx.BoxSizer(wx.VERTICAL)
        if self.options.vocoder or self.options.phase2_tdma:
            myform['volume'] = form.slider_field(parent=self.panel, sizer=vbox_sliders, label="Volume",
                weight=0, min=0, max=20, value=15,
                callback=self.set_audio_scaler)
        if self.rtl_found:
            myform['ppm'] = form.slider_field(parent=self.panel, sizer=vbox_sliders, label="PPM",
                weight=0, min=0, max=120, value=self.options.freq_corr,
                callback=self.set_rtl_ppm)
        if (self.options.vocoder or self.options.phase2_tdma) or self.rtl_found:
            hbox.Add(vbox_sliders, 0, 0)

        vbox.Add(hbox, 0, 0)

    def configure_tdma(self, params):
        if params['tdma'] is not None and not self.options.phase2_tdma:
            print '***TDMA request for frequency %d failed- phase2_tdma option not enabled' % params['freq']
            return
        set_tdma = False
        if params['tdma'] is not None:
            set_tdma = True
        if set_tdma == self.tdma_state:
            return	# already in desired state
        self.tdma_state = set_tdma
        if set_tdma:
            self.decoder.set_slotid(params['tdma'])
            hash = '%x%x%x' % (params['nac'], params['sysid'], params['wacn'])
            if hash not in self.xor_cache:
                self.xor_cache[hash] = lfsr.p25p2_lfsr(params['nac'], params['sysid'], params['wacn']).xor_chars
            self.decoder.set_xormask(self.xor_cache[hash], hash)
            sps = self.basic_rate / 6000
        else:
            sps = self.basic_rate / 4800
        self.demod.clock.set_omega(float(sps))

    def change_freq(self, params):
        freq = params['freq']
        offset = params['offset']
        center_freq = params['center_frequency']

        if self.options.hamlib_model:
            self.hamlib.set_freq(freq)
        elif params['center_frequency']:
            relative_freq = center_freq - freq
            if abs(relative_freq + self.options.offset) > self.channel_rate / 2:
                print '***unable to tune Local Oscillator to offset %d Hz' % (relative_freq + self.options.offset)
                print '***limit is one half of sample-rate %d = %d' % (self.channel_rate, self.channel_rate / 2)
                print '***request for frequency %d rejected' % freq
                
            self.lo_freq = self.options.offset + relative_freq 
            self.demod.set_relative_frequency(self.lo_freq + self.myform['freq_tune'].get_value())
            self.set_freq(center_freq + offset)
            #self.spectrum.set_baseband_freq(center_freq)
        else:
            self.set_freq(freq + offset)

        self.configure_tdma(params)

        # send msg as event to avoid thread safety problems updating form
        evt = msg_DataEvent(params)
        wx.PostEvent(self.frame, evt)

    def hamlib_attach(self, model):
        Hamlib.rig_set_debug (Hamlib.RIG_DEBUG_NONE)	# RIG_DEBUG_TRACE

        self.hamlib = Hamlib.Rig (model)
        self.hamlib.set_conf ("serial_speed","9600")
        self.hamlib.set_conf ("retry","5")

        self.hamlib.open ()

    def q_action(self, action):
        msg = gr.message().make_from_string(action, -2, 0, 0)
        self.rx_q.insert_tail(msg)

    def form_hold(self, kv):
        if kv['hold']:
            cmd = 'set_hold'
        else:
            cmd = 'unset_hold'
        self.q_action(cmd)

    def form_skip(self):
        self.q_action('skip')

    def form_lockout(self):
        self.q_action('lockout')

    def update_traffic(self, evt):
        s = self.trunk_rx.to_string()
        t = {}
	t['string'] = s
        self.traffic.update(t)

    def set_gain(self, gain):
        if self.rtl_found:
            self.src.set_gain(gain, 'LNA')
            if self.options.verbosity:
                print 'RTL Gain of %d set to: %.1f' % (gain, self.src.get_gain('LNA'))
        else:
            if self.baseband_input:
                f = 1.0
            else:
                f = 0.1
            self.demod.set_baseband_gain(float(gain) * f)

    def set_audio_scaler(self, vol):
        #print 'audio scaler: %f' % ((1 / 32768.0) * (vol * 0.1))
        self.decoder.set_scaler_k((1 / 32768.0) * (vol * 0.1))

    def set_rtl_ppm(self, ppm):
        self.src.set_freq_corr(ppm)

    def set_freq_tune(self, val):
        self.myform['freq_tune'].set_value(val)
        self.demod.set_relative_frequency(val + self.lo_freq)

    def set_freq(self, target_freq):
        """
        Set the center frequency we're interested in.

        @param target_freq: frequency in Hz
        @rypte: bool

        Tuning is a two step process.  First we ask the front-end to
        tune as close to the desired frequency as it can.  Then we use
        the result of that operation and our target_frequency to
        determine the value for the digital down converter.
        """
        if not self.src:
            return False
        tune_freq = target_freq + self.options.calibration + self.options.offset
        r = self.src.set_center_freq(tune_freq)
        
        if r:
            #self.myform['freq'].set_value(target_freq)     # update displayed va
            #if self.show_debug_info:
            #    self.myform['baseband'].set_value(r.baseband_freq)
            #    self.myform['ddc'].set_value(r.dxc_freq)
            return True

        return False

    def demod_type_chg(self, val):
        if val == 'FSK4':
            new_demod_mode = True
        else:
            new_demod_mode = False
        if self.fsk4_demod_mode == new_demod_mode:
            return
        self.fsk4_demod_mode = new_demod_mode
        self.lock()
        self.disconnect_demods()
        notebook_sel = self.notebook.GetSelection()
        if notebook_sel == 0 or notebook_sel == 4:	# spectrum or demod symbols
             self.connect_demods()
        elif notebook_sel == 1 or notebook_sel == 2 or notebook_sel == 6:
             self.connect_fsk4_demod()
        elif notebook_sel == 3:	# constellation
             self.connect_psk_demod()

        self.unlock()

    def _set_status_msg(self, msg):
        self.frame.GetStatusBar().SetStatusText(msg, 0)

    # read capture file properties (decimation etc.)
    #
    def __read_file_properties(self, filename):
        f = open(filename, "r")
        self.info = pickle.load(f)
        ToDo = True
        f.close()

    # setup to rx from file
    #
    def __set_rx_from_file(self, filename, capture_rate):
        file = blocks.file_source(gr.sizeof_gr_complex, filename, True)
        gain = blocks.multiply_const_cc(self.options.gain)
        throttle = blocks.throttle(gr.sizeof_gr_complex, capture_rate)
        self.__connect([[file, gain, throttle]])
        self.__build_graph(throttle, capture_rate)

    # setup to rx from Audio
    #
    def __set_rx_from_audio(self, capture_rate):
        self.__build_graph(self.source, capture_rate)

    # setup to rx from USRP
    #
    def __set_rx_from_osmosdr(self):
        # setup osmosdr
        capture_rate = self.src.set_sample_rate(self.options.sample_rate)
        if self.options.antenna:
            self.src.set_antenna(self.options.antenna)
        self.info["capture-rate"] = capture_rate
        self.src.set_bandwidth(capture_rate)
        r = self.src.set_center_freq(self.options.frequency + self.options.calibration+ self.options.offset)
        print 'set_center_freq: %d' % r
        if not r:
            raise RuntimeError("failed to set USRP frequency")
        # capture file
        # if preserve:
        if 0:
            try:
                self.capture_filename = os.tmpnam()
            except RuntimeWarning:
                ignore = True
            capture_file = blocks.file_sink(gr.sizeof_gr_complex, self.capture_filename)
            self.__connect([[self.usrp, capture_file]])
        else:
            self.capture_filename = None
        # everything else
        self.__build_graph(self.src, capture_rate)

    # Change the UI state
    #
    def _set_state(self, new_state):
        self.state = new_state
        if "STOPPED" == self.state:
            # menu items
            can_capture = False # self.usrp is not None
            self.file_new.Enable(can_capture)
            self.file_open.Enable(True)
            self.file_properties.Enable(False)
            self.file_close.Enable(False)
            # toolbar
            if self.toolbar:
                self.toolbar.EnableTool(wx.ID_NEW, can_capture)
                self.toolbar.EnableTool(wx.ID_OPEN, True)
            # Visually reflect "no file"
            self.frame.SetStatusText("", 1)
            self.frame.SetStatusText("", 2)
            self.spectrum_plotter.ClearBackground()
            self.signal_plotter.ClearBackground()
            # self.symbol_plotter.ClearBackground()
            # self.traffic.clear()
        elif "RUNNING" == self.state:
            # menu items
            self.file_new.Enable(False)
            self.file_open.Enable(False)
            self.file_properties.Enable(True)
            self.file_close.Enable(True)
            # toolbar
            if self.toolbar:
                self.toolbar.EnableTool(wx.ID_NEW, False)
                self.toolbar.EnableTool(wx.ID_OPEN, False)
        elif "CAPTURING" == self.state:
            # menu items
            self.file_new.Enable(False)
            self.file_open.Enable(False)
            self.file_properties.Enable(True)
            self.file_close.Enable(True)
            # toolbar
            if self.toolbar:
                self.toolbar.EnableTool(wx.ID_NEW, False)
                self.toolbar.EnableTool(wx.ID_OPEN, False)


    # Append filename to default title bar
    #
    def _set_titlebar(self, filename):
        ToDo = True

    # Write capture file properties
    #
    def __write_file_properties(self, filename):
        f = open(filename, "w")
        pickle.dump(self.info, f)
        f.close()

    # Adjust the channel offset
    #
    def adjust_channel_offset(self, delta_hz):
        max_delta_hz = 12000.0
        delta_hz *= self.symbol_deviation      
        delta_hz = max(delta_hz, -max_delta_hz)
        delta_hz = min(delta_hz, max_delta_hz)
        self.channel_filter.set_center_freq(self.channel_offset - delta_hz+ self.options.offset)

    # Close an open file
    #
    def _on_file_close(self, event):
        self.stop()
        self.wait()
        self.__disconnect()
        if "CAPTURING" == self.state and self.capture_filename:
            dialog = wx.MessageDialog(self.frame, "Save capture file before closing?", style=wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
            if wx.ID_YES == dialog.ShowModal():
                save_dialog = wx.FileDialog(self.frame, "Save capture file as:", wildcard="*.dat", style=wx.SAVE|wx.OVERWRITE_PROMPT)
                if save_dialog.ShowModal() == wx.ID_OK:
                    path = str(save_dialog.GetPath())
                    save_dialog.Destroy()
                    os.rename(self.capture_filename, path)
                    self.__write_file_properties(path + ".info")
            else:
                os.remove(self.capture_filename)
        self.capture_filename = None
        self._set_state("STOPPED")

    # New capture from USRP 
    #
    def _on_file_new(self, event):
#         wizard = wx.wizard.Wizard(self.frame, -1, "New Capture from USRP")
#         page1 = wizard_intro_page(wizard)
#         page2 = wizard_details_page(wizard)
#         page3 = wizard_preserve_page(wizard)
#         page4 = wizard_finish_page(wizard)
#         wx.wizard.WizardPageSimple_Chain(page1, page2)
#         wx.wizard.WizardPageSimple_Chain(page2, page3)
#         wx.wizard.WizardPageSimple_Chain(page3, page4)
#         wizard.FitToPage(page1)
#         if wizard.RunWizard(page1):
        self.stop()
        self.wait()
        # ToDo: get open_usrp() arguments from wizard
        self.open_usrp((0,0), 200, None, 434.08e06, True)  # Test freq
        self.start()

    # Open an existing capture
    #
    def _on_file_open(self, event):
        dialog = wx.FileDialog(self.frame, "Choose a capture file:", wildcard="*.dat", style=wx.OPEN)
        if dialog.ShowModal() == wx.ID_OK:
            file = str(dialog.GetPath())
            dialog.Destroy()
            self.stop()
            self.wait()
            self.open_file(file)
            self.start()

    # Present file properties dialog
    #
    def _on_file_properties(self, event):
        # ToDo: show what info we have about the capture file (name,
        # capture source, capture rate, date(?), size(?),)
        todo = True

    # Undo the last edit
    #
    def _on_edit_undo(self, event):
        todo = True

    # Redo the edit
    #
    def _on_edit_redo(self, event):
        todo = True

    # Cut the current selection
    #
    def _on_edit_cut(self, event):
        todo = True

    # Copy the current selection
    #
    def _on_edit_copy(self, event):
        todo = True

    # Paste into the current sample
    #
    def _on_edit_paste(self, event):
        todo = True

    # Delete the current selection
    #
    def _on_edit_delete(self, event):
        todo = True

    # Select all
    #
    def _on_edit_select_all(self, event):
        todo = True

    # Open the preferences dialog
    #
    def _on_edit_prefs(self, event):
        todo = True


    # Set channel offset and RF squelch threshold
    #
    def _on_spectrum_left_click(self, event):
        if "STOPPED" != self.state:
            # set frequency
            x,y = self.spectrum_plotter.GetXY(event)
            xmin, xmax = self.spectrum_plotter.GetXCurrentRange()
            x = min(x, xmax)
            x = max(x, xmin)
            scale_factor = self.spectrum.win._scale_factor
            chan_width = 6.25e3
            x /= scale_factor
            x += chan_width / 2
            x  = (x // chan_width) * chan_width
            self.set_channel_offset(x, scale_factor, self.spectrum.win._units)
            # set squelch threshold
            ymin, ymax = self.spectrum_plotter.GetYCurrentRange()
            y = min(y, ymax)
            y = max(y, ymin)
            squelch_increment = 5
            y += squelch_increment / 2
            y = (y // squelch_increment) * squelch_increment
            self.set_squelch_threshold(int(y))

    # Open an existing capture file
    #
    def open_file(self, capture_file):
        try:
            capture_rate = self.options.sample_rate
            self.__set_rx_from_file(capture_file, capture_rate)
            self._set_titlebar(capture_file)
            self._set_state("RUNNING")
        except Exception, x:
            wx.MessageBox("Cannot open capture file: " + x.message, "File Error", wx.CANCEL | wx.ICON_EXCLAMATION)

    def open_ifile(self, capture_rate, gain, input_filename, file_seek):
        speed = 96000 # TODO: fixme
        ifile = blocks.file_source(gr.sizeof_gr_complex, input_filename, 1)
        if file_seek > 0:
            rc = ifile.seek(file_seek*1024, gr.SEEK_SET)
            assert rc == True
            #print "seek: %d, rc = %d" % (file_seek, rc)
        throttle = blocks.throttle(gr.sizeof_gr_complex, speed)
        self.source = blocks.multiply_const_cc(gain)
        self.connect(ifile, throttle, self.source)
        self.__set_rx_from_audio(speed)
        self._set_titlebar("Playing")
        self._set_state("PLAYING")

    def open_audio_c(self, capture_rate, gain, audio_input_filename):
        self.info = {
                "capture-rate": capture_rate,
                "center-freq": 0,
                "source-dev": "AUDIO",
                "source-decim": 1 }
        self.audio_source = audio.source(capture_rate, audio_input_filename)
        self.audio_cvt = blocks.float_to_complex()
        self.connect((self.audio_source, 0), (self.audio_cvt, 0))
        self.connect((self.audio_source, 1), (self.audio_cvt, 1))
        self.source = blocks.multiply_const_cc(gain)
        self.connect(self.audio_cvt, self.source)
        self.__set_rx_from_audio(capture_rate)
        self._set_titlebar("Capturing")
        self._set_state("CAPTURING")

    def open_audio(self, capture_rate, gain, audio_input_filename):
            self.info = {
                "capture-rate": capture_rate,
                "center-freq": 0,
                "source-dev": "AUDIO",
                "source-decim": 1 }
            self.source = audio.source(capture_rate, audio_input_filename)
            self.__set_rx_from_audio(capture_rate)
            self._set_titlebar("Capturing")
            self._set_state("CAPTURING")

    # Open the USRP
    #
    def open_usrp(self):
        # try:
            self.info = {
                "capture-rate": "unknown",
                "center-freq": self.options.frequency,
                "source-dev": "USRP",
                "source-decim": 1 }
            self.__set_rx_from_osmosdr()
            self._set_titlebar("Capturing")
            self._set_state("CAPTURING")
        # except Exception, x:
        #     wx.MessageBox("Cannot open USRP: " + x.message, "USRP Error", wx.CANCEL | wx.ICON_EXCLAMATION)

    # Set the channel offset
    #
    def set_channel_offset(self, offset_hz, scale, units):
        self.channel_offset = -offset_hz
        self.channel_filter.set_center_freq(self.channel_offset+ self.options.offset)
        self.frame.SetStatusText("Channel offset: " + str(offset_hz * scale) + units, 1)

    # Set the RF squelch threshold level
    #
    def set_squelch_threshold(self, squelch_db):
        self.squelch.set_threshold(squelch_db)
        self.frame.SetStatusText("Squelch: " + str(squelch_db) + "dB", 2)

    def disconnect_demods(self):
# assumes lock held or init
        if self.baseband_input:
            return
        self.demod.disconnect_chain()

    def connect_psk_demod(self):
# assumes lock held or init
        if self.baseband_input:
            return
        self.demod.connect_chain('cqpsk')

    def connect_fsk4_demod(self):
# assumes lock held or init
        if self.baseband_input:
            return
        self.demod.connect_chain('fsk4')

    def connect_demods(self):
        if self.baseband_input:
            self.connect_fsk4_demod()
        else:
            if self.fsk4_demod_mode:
                self.connect_fsk4_demod()
            else:
                self.connect_psk_demod()

    def disconnect_constellation_scope(self):
        self.demod.disconnect_complex()

    def connect_constellation_scope(self):
        sel = self.complex_scope.win.radio_box_source.GetSelection()
        if sel:
            self.demod.connect_complex('diffdec', self.complex_scope)
        else:
            self.demod.connect_complex('clock', self.complex_scope)

    def disconnect_data_scope(self):
        self.demod.disconnect_bb()

    def connect_data_scope(self):
        sel = self.data_scope.win.radio_box.GetSelection()
        if sel:
            self.demod.connect_bb('symbol_filter', self.data_scope)
        else:
            self.demod.connect_bb('baseband_amp', self.data_scope)

    # for datascope, choose monitor viewpoint
    def filter_select(self, evt):
        self.lock()
        self.connect_data_scope()
        self.unlock()

    def corr_select(self, evt):
        new_corr = self.correlation_scope.win.radio_box_corr.GetSelection()
        self.correlation_scope.win.correlation = self.correlation_scope.win.signatures[new_corr]
        if self.baseband_input:
            return
        self.lock()
        self.set_connection()
        if new_corr == len(self.correlation_scope.win.signatures) - 1:
            # special iden mode
            self.corr_i_chan = True
        else:
            self.corr_i_chan = False
        self.set_connection(corr=True)
        self.unlock()

    def source_select(self, evt):
        self.lock()
        self.connect_constellation_scope()
        self.unlock()

    def speed_select(self, evt):
        new_speed = self.data_scope.win.radio_box_speed.GetSelection()
        self.lock()
        self.set_speed(new_speed)
        self.unlock()

class window_with_ctlbox(wx.Panel):
    def __init__(self, parent, id = -1):
        wx.Panel.__init__(self, parent, id)

    def make_control_box (self):
        global speeds
        ctrlbox = wx.BoxSizer (wx.HORIZONTAL)

        ctrlbox.Add ((5,0) ,0)

        run_stop = wx.Button (self, 11102, "Run/Stop")
        run_stop.SetToolTipString ("Toggle Run/Stop mode")
        wx.EVT_BUTTON (self, 11102, self.run_stop)
        ctrlbox.Add (run_stop, 0, wx.EXPAND)

        self.radio_box = wx.RadioBox(self, 11103, "Viewpoint", style=wx.RA_SPECIFY_ROWS,
                        choices = ["Raw", "Filtered"] )
        self.radio_box.SetToolTipString("Viewpoint Before Or After Symbol Filter")
        self.radio_box.SetSelection(1)
        ctrlbox.Add (self.radio_box, 0, wx.EXPAND)

        ctrlbox.Add ((5, 0) ,0)            # stretchy space

	speed_str = []
	for speed in speeds:
		speed_str.append("%d" % speed)

        self.radio_box_speed = wx.RadioBox(self, 11104, "Symbol Rate", style=wx.RA_SPECIFY_ROWS, majorDimension=2, choices = speed_str)
        self.radio_box_speed.SetToolTipString("Symbol Rate")
        ctrlbox.Add (self.radio_box_speed, 0, wx.EXPAND)
        ctrlbox.Add ((10, 0) ,1)            # stretchy space

        return ctrlbox

# A snapshot of important fields in current traffic
#
class TrafficPane(wx.Panel):

    # Initializer
    #
    def __init__(self, parent, trunk_traffic=False, voice_traffic=False, update_callback=None):

        wx.Panel.__init__(self, parent)
        sizer = wx.GridBagSizer(hgap=10, vgap=10)
        self.fields = {}

        if trunk_traffic:
            #label = wx.StaticText(self, -1, "DUID:")
            #sizer.Add(label, pos=(1,1))
            self.update_b = wx.Button (self, 11109, "Update")
            sizer.Add(self.update_b, pos=(1,1))
            field = wx.TextCtrl(self, -1, "", size=(500,400), style=wx.TE_MULTILINE+wx.TE_READONLY)
            sizer.Add(field, pos=(1,2))
            self.fields["string"] = field;

        if voice_traffic:
            label = wx.StaticText(self, -1, "DUID:")
            sizer.Add(label, pos=(1,1))
            field = wx.TextCtrl(self, -1, "", size=(72, -1), style=wx.TE_READONLY)
            sizer.Add(field, pos=(1,2))
            self.fields["duid"] = field;

            label = wx.StaticText(self, -1, "NAC:")
            sizer.Add(label, pos=(2,1))
            field = wx.TextCtrl(self, -1, "", size=(175, -1), style=wx.TE_READONLY)
            sizer.Add(field, pos=(2,2))
            self.fields["nac"] = field;

            label = wx.StaticText(self, -1, "Source:")
            sizer.Add(label, pos=(3,1))
            field = wx.TextCtrl(self, -1, "", size=(175, -1), style=wx.TE_READONLY)
            sizer.Add(field, pos=(3,2))
            self.fields["source"] = field;

            label = wx.StaticText(self, -1, "Destination:")
            sizer.Add(label, pos=(4,1))
            field = wx.TextCtrl(self, -1, "", size=(175, -1), style=wx.TE_READONLY)
            sizer.Add(field, pos=(4,2))
            self.fields["dest"] = field;

#        label = wx.StaticText(self, -1, "ToDo:")
#        sizer.Add(label, pos=(5,1))
#        field = wx.TextCtrl(self, -1, "", size=(175, -1), style=wx.TE_READONLY)
#        sizer.Add(field, pos=(5,2))
#        self.fields["nid"] = field;

            label = wx.StaticText(self, -1, "MFID:")
            sizer.Add(label, pos=(1,4))
            field = wx.TextCtrl(self, -1, "", size=(175, -1), style=wx.TE_READONLY)
            sizer.Add(field, pos=(1,5))
            self.fields["mfid"] = field;

            label = wx.StaticText(self, -1, "ALGID:")
            sizer.Add(label, pos=(2,4))
            field = wx.TextCtrl(self, -1, "", size=(175, -1), style=wx.TE_READONLY)
            sizer.Add(field, pos=(2,5))
            self.fields["algid"] = field;

            label = wx.StaticText(self, -1, "KID:")
            sizer.Add(label, pos=(3,4))
            field = wx.TextCtrl(self, -1, "", size=(72, -1), style=wx.TE_READONLY)
            sizer.Add(field, pos=(3,5))
            self.fields["kid"] = field;

            label = wx.StaticText(self, -1, "MI:")
            sizer.Add(label, pos=(4,4))
            field = wx.TextCtrl(self, -1, "", size=(216, -1), style=wx.TE_READONLY)
            sizer.Add(field, pos=(4,5))
            self.fields["mi"] = field;

            label = wx.StaticText(self, -1, "TGID:")
            sizer.Add(label, pos=(5,4))
            field = wx.TextCtrl(self, -1, "", size=(72, -1), style=wx.TE_READONLY)
            sizer.Add(field, pos=(5,5))
            self.fields["tgid"] = field;

        self.SetSizer(sizer)
        self.Fit()

    # Clear the field values
    #
    def clear(self):
        for v in self.fields.values():
            v.Clear()

    # Update the field values
    #
    def update(self, field_values):
        for k,v in self.fields.items():
            f = field_values.get(k, None)
            if f:
                v.SetValue(f)
            else:
                v.SetValue("")


# Introduction page for USRP capture wizard
#
class wizard_intro_page(wx.wizard.WizardPageSimple):

    # Initializer
    #
    def __init__(self, parent):
        wx.wizard.WizardPageSimple.__init__(self, parent)
        html = wx.html.HtmlWindow(self)
        html.SetPage('''
	<html>
	 <body>
         <h1>Capture from USRP</h1>
	 <p>
	  We will guide you through the process of capturing a sample from the USRP.
	  Please ensure that the USRP is switched on and connected to this computer.
	 </p>
	 </body>
	</html>
	''')
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)
        sizer.Add(html, 1, wx.ALIGN_CENTER | wx.EXPAND | wx.FIXED_MINSIZE)


# USRP wizard details page
#
class wizard_details_page(wx.wizard.WizardPageSimple):

    # Initializer
    #
    def __init__(self, parent):
        wx.wizard.WizardPageSimple.__init__(self, parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

    # Return a tuple containing the subdev_spec, gain, frequency, decimation factor
    #
    def get_details(self):
        ToDo = True


# data unit receive queue
#
class du_queue_watcher(threading.Thread):

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

# Frequency tracker
#
class demod_watcher(threading.Thread):

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
            frequency_correction = msg.arg1()
            self.callback(frequency_correction)


# Decoder watcher
#
class decode_watcher(threading.Thread):

    def __init__(self, msgq, traffic_pane, **kwds):
        threading.Thread.__init__ (self, **kwds)
        self.setDaemon(1)
        self.msgq = msgq
        self.traffic_pane = traffic_pane
        self.keep_running = True
        self.start()

    def run(self):
        while(self.keep_running):
            msg = self.msgq.delete_head()
            pickled_dict = msg.to_string()
            attrs = pickle.loads(pickled_dict)
            self.traffic_pane.update(attrs)

############################################################################
# following code modified from GNURadio sources

default_scopesink_size = (640, 240)
default_v_scale = 1000
default_frame_decim = gr.prefs().get_long('wxgui', 'frame_decim', 1)

class datascope_sink_f(gr.hier_block2):
    def __init__(self, parent, title='', sample_rate=1,
                 size=default_scopesink_size, frame_decim=default_frame_decim,
                 samples_per_symbol=10, num_plots=100,
                 v_scale=default_v_scale, t_scale=None, num_inputs=1, **kwargs):

        gr.hier_block2.__init__(self, "datascope_sink_f",
                                gr.io_signature(num_inputs, num_inputs, gr.sizeof_float),
                                gr.io_signature(0,0,0))

        msgq = gr.msg_queue(2)         # message queue that holds at most 2 messages
        self.st = blocks.message_sink(gr.sizeof_float, msgq, 1)
        self.connect((self, 0), self.st)

        self.win = datascope_window(datascope_win_info (msgq, sample_rate, frame_decim,
                                          v_scale, t_scale, None, title), parent, samples_per_symbol=samples_per_symbol, num_plots=num_plots)

    def set_sample_rate(self, sample_rate):
        self.guts.set_sample_rate(sample_rate)
        self.win.info.set_sample_rate(sample_rate)

# ========================================================================

wxDATA_EVENT = wx.NewEventType()

def EVT_DATA_EVENT(win, func):
    win.Connect(-1, -1, wxDATA_EVENT, func)

class datascope_DataEvent(wx.PyEvent):
    def __init__(self, data):
        wx.PyEvent.__init__(self)
        self.SetEventType (wxDATA_EVENT)
        self.data = data

    def Clone (self): 
        self.__class__ (self.GetId())

class datascope_win_info (object):
    __slots__ = ['msgq', 'sample_rate', 'frame_decim', 'v_scale', 
                 'scopesink', 'title',
                 'time_scale_cursor', 'v_scale_cursor', 'marker', 'xy',
                 'autorange', 'running']

    def __init__ (self, msgq, sample_rate, frame_decim, v_scale, t_scale,
                  scopesink, title = "Oscilloscope", xy=False):
        self.msgq = msgq
        self.sample_rate = sample_rate
        self.frame_decim = frame_decim
        self.scopesink = scopesink
        self.title = title;

        self.marker = 'line'
        self.xy = xy
        self.autorange = not v_scale
        self.running = True

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
        
    def get_sample_rate (self):
        return self.sample_rate

    def get_decimation_rate (self):
        return 1.0

    def set_marker (self, s):
        self.marker = s

    def get_marker (self):
        return self.marker


class datascope_input_watcher (threading.Thread):
    def __init__ (self, msgq, event_receiver, frame_decim, num_plots, samples_per_symbol, **kwds):
        threading.Thread.__init__ (self, **kwds)
        self.setDaemon (1)
        self.msgq = msgq
        self.event_receiver = event_receiver
        self.frame_decim = frame_decim
        self.samples_per_symbol = samples_per_symbol
        self.num_plots = num_plots
        self.iscan = 0
        self.keep_running = True
        self.skip = 0
        self.totsamp = 0
        self.skip_samples = 0
        self.start ()
        self.msg_string = ""

    def run (self):
        # print "datascope_input_watcher: pid = ", os.getpid ()
        while (self.keep_running):
            msg = self.msgq.delete_head()   # blocking read of message queue
            nchan = int(msg.arg1())    # number of channels of data in msg
            nsamples = int(msg.arg2()) # number of samples in each channel
            self.totsamp += nsamples
            if self.skip_samples >= nsamples:
               self.skip_samples -= nsamples
               continue

            self.msg_string += msg.to_string()      # body of the msg as a string

            bytes_needed = (self.num_plots*self.samples_per_symbol) * gr.sizeof_float
            if (len(self.msg_string) < bytes_needed):
                continue

            records = []
            # start = self.skip * gr.sizeof_float
            start = 0
            chan_data = self.msg_string[start:start+bytes_needed]
            rec = numpy.fromstring (chan_data, numpy.float32)
            records.append (rec)
            self.msg_string = ""

            unused = nsamples - (self.num_plots*self.samples_per_symbol)
            unused -= (start/gr.sizeof_float)
            self.skip = self.samples_per_symbol - (unused % self.samples_per_symbol)
            # print "reclen = %d totsamp %d appended %d skip %d start %d unused %d" % (nsamples, self.totsamp, len(rec), self.skip, start/gr.sizeof_float, unused)

            de = datascope_DataEvent (records)
            wx.PostEvent (self.event_receiver, de)
            records = []
            del de

            # lower values = more frequent plots, but higher CPU usage
            self.skip_samples = self.num_plots * self.samples_per_symbol * 20

class datascope_window (window_with_ctlbox):

    def __init__ (self, info, parent, id = -1,
                  samples_per_symbol=10, num_plots=100,
                  pos = wx.DefaultPosition, size = wx.DefaultSize, name = ""):
        window_with_ctlbox.__init__ (self, parent, -1)
        self.info = info

        vbox = wx.BoxSizer (wx.VERTICAL)

        self.graph = datascope_graph_window (info, self, -1, samples_per_symbol=samples_per_symbol, num_plots=num_plots)

        vbox.Add (self.graph, 1, wx.EXPAND)
        vbox.Add (self.make_control_box(), 0, wx.EXPAND)
        vbox.Add (self.make_control2_box(), 0, wx.EXPAND)

        self.sizer = vbox
        self.SetSizer (self.sizer)
        self.SetAutoLayout (True)
        self.sizer.Fit (self)
        

    # second row of control buttons etc. appears BELOW control_box
    def make_control2_box (self):
        ctrlbox = wx.BoxSizer (wx.HORIZONTAL)

        ctrlbox.Add ((5,0) ,0) # left margin space

        return ctrlbox
    
    def run_stop (self, evt):
        self.info.running = not self.info.running

class datascope_graph_window (plot.PlotCanvas):

    def __init__ (self, info, parent, id = -1,
                  pos = wx.DefaultPosition, size = (140, 140),
                  samples_per_symbol=10, num_plots=100,
                  style = wx.DEFAULT_FRAME_STYLE, name = ""):
        plot.PlotCanvas.__init__ (self, parent, id, pos, size, style, name)

        self.SetXUseScopeTicks (True)
        self.SetEnableGrid (False)
        self.SetEnableZoom (True)
        self.SetEnableLegend(True)
        # self.SetBackgroundColour ('black')
        
        self.info = info;

        self.total_points = 0

        self.samples_per_symbol = samples_per_symbol
        self.num_plots = num_plots

        EVT_DATA_EVENT (self, self.format_data)

        self.input_watcher = datascope_input_watcher (info.msgq, self, info.frame_decim, self.samples_per_symbol, self.num_plots)

    def format_data (self, evt):
        if not self.info.running:
            return
        
        info = self.info
        records = evt.data
        nchannels = len (records)
        npoints = len (records[0])
        self.total_points += npoints

        x_vals = numpy.arange (0, self.samples_per_symbol)

        self.SetXUseScopeTicks (True)   # use 10 divisions, no labels

        objects = []
        colors = ['red','orange','yellow','green','blue','violet','cyan','magenta','brown','black']

        r = records[0]  # input data
        for i in range(self.num_plots):
            points = []
            for j in range(self.samples_per_symbol):
                p = [ j, r[ i*self.samples_per_symbol + j ] ]
                points.append(p)
            objects.append (plot.PolyLine (points, colour=colors[i % len(colors)], legend=('')))

        graphics = plot.PlotGraphics (objects,
                                      title='Data Scope',
                                      xLabel = 'Time', yLabel = 'Amplitude')

        x_range = (0., 0. + (self.samples_per_symbol-1)) # ranges are tuples!
        self.y_range = (-4., 4.) # for standard -3/-1/+1/+3
        # self.y_range = (-10., 10.) # for standard -3/-1/+1/+3
        self.Draw (graphics, xAxis=x_range, yAxis=self.y_range)
############################################################################
class constellation_plot_c(gr.hier_block2):
    def __init__(self, parent, title='', sample_rate=1,
                 frame_decim=10,
                 num_plots=100,
                 num_inputs=1, **kwargs):

        gr.hier_block2.__init__(self, "constellation_plot_c",
                                gr.io_signature(num_inputs, num_inputs, gr.sizeof_gr_complex),
                                gr.io_signature(0,0,0))

        msgq = gr.msg_queue(2)         # message queue that holds at most 2 messages
        self.st = blocks.message_sink(gr.sizeof_gr_complex, msgq, 1)
        self.connect((self, 0), self.st)

        self.win = constellation_plot_window(constellation_plot_win_info (msgq, sample_rate, frame_decim, None, title), parent, num_plots=num_plots)

    def set_sample_rate(self, sample_rate):
        self.guts.set_sample_rate(sample_rate)
        self.win.info.set_sample_rate(sample_rate)

# ========================================================================

wxDATA_EVENT = wx.NewEventType()

def EVT_DATA_EVENT(win, func):
    win.Connect(-1, -1, wxDATA_EVENT, func)

class constellation_plot_DataEvent(wx.PyEvent):
    def __init__(self, data):
        wx.PyEvent.__init__(self)
        self.SetEventType (wxDATA_EVENT)
        self.data = data

    def Clone (self): 
        self.__class__ (self.GetId())

class constellation_plot_win_info (object):
    __slots__ = ['msgq', 'sample_rate', 'frame_decim',
                 'scopesink', 'title',
                 'time_scale_cursor', 'marker', 'xy',
                 'autorange', 'running']

    def __init__ (self, msgq, sample_rate, frame_decim,
                  scopesink, title = "Oscilloscope", xy=True):
        self.msgq = msgq
        self.sample_rate = sample_rate
        self.frame_decim = frame_decim
        self.scopesink = scopesink
        self.title = title;

        self.marker = 'line'
        self.xy = xy
        self.autorange = False
        self.running = True

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
        
    def get_sample_rate (self):
        return self.sample_rate

    def get_decimation_rate (self):
        return 1.0

    def set_marker (self, s):
        self.marker = s

    def get_marker (self):
        return self.marker


class constellation_plot_input_watcher (threading.Thread):
    def __init__ (self, msgq, event_receiver, frame_decim, num_plots, **kwds):
        threading.Thread.__init__ (self, **kwds)
        self.setDaemon (1)
        self.msgq = msgq
        self.event_receiver = event_receiver
        self.frame_decim = frame_decim
        self.num_plots = num_plots
        self.iscan = 0
        self.keep_running = True
        self.skip = 0
        self.totsamp = 0
        self.skip_samples = 0
        self.start ()
        self.msg_string = ""
        self.skip_mode = False

    def run (self):
        # print "constellation_plot_input_watcher: pid = ", os.getpid ()
        time.sleep(1)
        while (self.keep_running):
            bytes_needed = self.num_plots * gr.sizeof_float * 2
            if self.skip_mode:
                bytes_needed = 500 * gr.sizeof_float * 2

            if len(self.msg_string) < bytes_needed:
                msg = self.msgq.delete_head()   # blocking read of message queue
                nchan = int(msg.arg1())    # number of channels of data in msg
                nsamples = int(msg.arg2()) # number of samples in each channel
                self.totsamp += nsamples

                self.msg_string += msg.to_string()      # body of the msg as a string
                continue

            chan_data = self.msg_string[:bytes_needed]
            self.msg_string = self.msg_string[bytes_needed:]

            if self.skip_mode:
                self.skip_mode = False
                continue

            records = []
            # start = self.skip * gr.sizeof_gr_complex
            # start = 0
            # chan_data = self.msg_string[start:start+bytes_needed]
            rec = numpy.fromstring (chan_data, numpy.float32)
            records.append (rec)
            # self.msg_string = ""

            # unused = nsamples - self.num_plots
            # unused -= (start/gr.sizeof_gr_complex)
            # print "reclen = %d totsamp %d appended %d skip %d start %d unused %d" % (nsamples, self.totsamp, len(rec), self.skip, start/gr.sizeof_float, unused)

            de = constellation_plot_DataEvent (records)
            wx.PostEvent (self.event_receiver, de)
            records = []
            del de

            # lower values = more frequent plots, but higher CPU usage
            # self.skip_samples = 5000
            self.skip_mode = True

class constellation_plot_window (wx.Panel):

    constellation_window_size = wx.DefaultSize
    def __init__ (self, info, parent, id = -1,
                  num_plots=100,
                  pos = wx.DefaultPosition, size = constellation_window_size, name = ""):
        wx.Panel.__init__ (self, parent, -1)
        self.info = info

        hbox = wx.BoxSizer (wx.HORIZONTAL)

        self.graph = constellation_plot_graph_window (info, self, -1, num_plots=num_plots)

        hbox.Add (self.graph, 1, wx.SHAPED)
        hbox.Add (self.make_control_box(), 0, wx.EXPAND)
        hbox.Add (self.make_control2_box(), 0, wx.EXPAND)

        self.sizer = hbox
        self.SetSizer (self.sizer)
        self.SetAutoLayout (True)
        self.sizer.Fit (self)
        

    # second row of control buttons etc. appears BELOW control_box
    def make_control2_box (self):
        ctrlbox = wx.BoxSizer (wx.HORIZONTAL)

        ctrlbox.Add ((5,0) ,0) # left margin space

        return ctrlbox

    def make_control_box (self):
        ctrlbox = wx.BoxSizer (wx.HORIZONTAL)

        ctrlbox.Add ((5,0) ,0)

        run_stop = wx.Button (self, 11102, "Run/Stop")
        run_stop.SetToolTipString ("Toggle Run/Stop mode")
        wx.EVT_BUTTON (self, 11102, self.run_stop)
        ctrlbox.Add (run_stop, 0, wx.EXPAND)

        # self.radio_box.SetToolTipString("Viewpoint Before Or After Symbol Filter")

        self.radio_box_mode = wx.RadioBox(self, 11106, "Mode", style=wx.RA_SPECIFY_ROWS,
                        choices = ["Standard", "Population"] )
        ctrlbox.Add (self.radio_box_mode, 0, wx.EXPAND)

        self.radio_box_color = wx.RadioBox(self, 11107, "Color", style=wx.RA_SPECIFY_ROWS,
                        choices = ["Mono", "2 Color"] )
        ctrlbox.Add (self.radio_box_color, 0, wx.EXPAND)
        wx.EVT_RADIOBOX(self.radio_box_color, 11107, self.color_select)

        self.radio_box_source = wx.RadioBox(self, 11108, "Source", style=wx.RA_SPECIFY_ROWS,
                        choices = ["Direct", "Differential"] )
        ctrlbox.Add (self.radio_box_source, 0, wx.EXPAND)

        ctrlbox.Add ((10, 0) ,1)            # stretchy space

        return ctrlbox
    
    def run_stop (self, evt):
        self.info.running = not self.info.running

    def color_select(self, evt):
        sel = self.radio_box_color.GetSelection()
        if sel:
            self.graph.color1 = 'red'
            self.graph.color2 = 'green'
        else:
            self.graph.color1 = 'blue'
            self.graph.color2 = 'blue'

class constellation_plot_graph_window (plot.PlotCanvas):

    def __init__ (self, info, parent, id = -1,
                  pos = wx.DefaultPosition, size = (140, 140),
                  num_plots=100,
                  style = wx.DEFAULT_FRAME_STYLE, name = ""):
        plot.PlotCanvas.__init__ (self, parent, id, pos, size, style, name)

        self.SetXUseScopeTicks (True)
        self.SetEnableGrid (False)
        self.SetEnableZoom (True)
        self.SetEnableLegend(True)
        # self.SetBackgroundColour ('black')
        
        self.info = info;
        self.plot_window = parent

        self.total_points = 0

        self.num_plots = num_plots

        EVT_DATA_EVENT (self, self.format_data)

        self.input_watcher = constellation_plot_input_watcher (info.msgq, self, info.frame_decim, self.num_plots)

        self.flag = False

        self.color1 = 'blue'
        self.color2 = 'blue'

    def format_data (self, evt):
        if not self.info.running:
            return
        if self.plot_window.radio_box_mode.GetSelection():
            self.format_data_pop(evt)
        else:
            self.format_data_std(evt)

    def format_data_std (self, evt):
        info = self.info
        records = evt.data
        nchannels = len (records)
        npoints = len (records[0])
        self.total_points += npoints

        self.SetXUseScopeTicks (True)   # use 10 divisions, no labels

        objects = []

        r = records[0]  # input data
        l = len(r) / 2
        p0 = []
        p1 = []
        for i in range(l):
            p = [ r[ i*2 ], r[ i*2+1 ] ]
            if self.flag:
                p1.append(p)
            else:
                p0.append(p)
            self.flag = not self.flag

        objects.append (plot.PolyMarker (p0, marker='plus', colour=self.color1))
        objects.append (plot.PolyMarker (p1, marker='plus', colour=self.color2))

        graphics = plot.PlotGraphics (objects,
                                      title='Constellation',
                                      xLabel = 'I', yLabel = 'Q')

        x_range = (-1.0, 1.0)
        y_range = (-1.0, 1.0)
        self.Draw (graphics, xAxis=x_range, yAxis=y_range)

    def format_data_pop (self, evt):
        if not self.info.running:
            return

        info = self.info
        records = evt.data
        nchannels = len (records)
        npoints = len (records[0])
        self.total_points += npoints

        self.SetXUseScopeTicks (True)   # use 10 divisions, no labels

        objects = []

        r = records[0]  # input data
        l = len(r) / 2
        b0 = []
        b1 = []
        max_buckets = 6.0
        m = int(2 * pi * max_buckets)
        for i in range(m+1):
            b0.append(0)
            b1.append(0)
        for i in range(l):
            # p = [ r[ i*2 ], r[ i*2+1 ] ]
            # if self.flag:
            #     p1.append(p)
            # else:
            #     p0.append(p)
            theta = math.atan2 ( r[ i*2 ], r[ i*2+1 ] )
            bucket = int((theta + pi) * max_buckets)
            if 1:
                if self.flag:
                    b0[bucket] += 1
                else:
                    b1[bucket] += 1
            self.flag = not self.flag

        # determine avg. "power" - for later rescaling of the values 
        tot = ct = 0
        for b in b0+b1:
            tot += b
            ct += 1
        avg = float(tot) / float(ct)

        p0 = []
        p1 = []
        r = len(b0)
        for i in range(r):
            theta = ((float(i)/ r) * 2 * pi) - pi
            abs = 0.5 * b0[i] / avg
            p = [ abs * math.cos(theta), abs * math.sin(theta) ]
            if i == 0:
                sp = p
            p0.append(p)
        p0.append(sp)
        r = len(b1)
        for i in range(r):
            theta = ((float(i) / r) * 2 * pi) - pi
            abs = 0.5 * b1[i] / avg
            p = [ abs * math.cos(theta), abs * math.sin(theta) ]
            if i == 0:
                sp = p
            p1.append(p)
        p1.append(sp)
        objects.append (plot.PolyLine (p0, colour=self.color1, legend=''))
        objects.append (plot.PolyLine (p1, colour=self.color2, legend=''))

        graphics = plot.PlotGraphics (objects,
                                      title='Constellation',
                                      xLabel = 'I', yLabel = 'Q')

        x_range = (-2.5, 2.5)
        y_range = (-2.5, 2.5)
        self.Draw (graphics, xAxis=x_range, yAxis=y_range)
############################################################################
class correlation_plot_f(gr.hier_block2):
    def __init__(self, parent, title='', sps=10,
                 frame_decim=4,
                 num_inputs=1, **kwargs):

        gr.hier_block2.__init__(self, "correlation_plot_f",
                                gr.io_signature(num_inputs, num_inputs, gr.sizeof_float),
                                gr.io_signature(0,0,0))

        msgq = gr.msg_queue(2)         # message queue that holds at most 2 messages
        self.st = blocks.message_sink(gr.sizeof_float, msgq, 1)
        self.connect((self, 0), self.st)

        self.win = correlation_plot_window(correlation_plot_win_info (msgq, sps, frame_decim, None, title), parent, sps=sps)

# ========================================================================

wxDATA_EVENT = wx.NewEventType()

def EVT_DATA_EVENT(win, func):
    win.Connect(-1, -1, wxDATA_EVENT, func)

class correlation_plot_DataEvent(wx.PyEvent):
    def __init__(self, data):
        wx.PyEvent.__init__(self)
        self.SetEventType (wxDATA_EVENT)
        self.data = data

    def Clone (self): 
        self.__class__ (self.GetId())

class correlation_plot_win_info (object):
    __slots__ = ['msgq', 'sps', 'frame_decim',
                 'scopesink', 'title',
                 'time_scale_cursor', 'marker', 'xy',
                 'autorange', 'running']

    def __init__ (self, msgq, sps, frame_decim,
                  scopesink, title = "Oscilloscope", xy=True):
        self.msgq = msgq
        self.sps = sps
        self.frame_decim = frame_decim
        self.scopesink = scopesink
        self.title = title;

        self.marker = 'line'
        self.xy = xy
        self.autorange = False
        self.running = True

    def get_decimation_rate (self):
        return 1.0

    def set_marker (self, s):
        self.marker = s

    def get_marker (self):
        return self.marker

class correlation_plot_input_watcher (threading.Thread):
    def __init__ (self, msgq, event_receiver, frame_decim, **kwds):
        threading.Thread.__init__ (self, **kwds)
        self.setDaemon (1)
        self.msgq = msgq
        self.event_receiver = event_receiver
        self.frame_decim = frame_decim
        self.iscan = 0
        self.keep_running = True
        self.skip = 0
        self.totsamp = 0
        self.skip_samples = 0
        self.start ()
        self.msg_string = ""
        self.skip_mode = False

    def run (self):
        # print "correlation_plot_input_watcher: pid = ", os.getpid ()
        time.sleep(1)
        while (self.keep_running):
            bytes_needed = 24000 * gr.sizeof_float

            if len(self.msg_string) < bytes_needed:
                msg = self.msgq.delete_head()   # blocking read of message queue
                nchan = int(msg.arg1())    # number of channels of data in msg
                nsamples = int(msg.arg2()) # number of samples in each channel
                self.totsamp += nsamples

                self.msg_string += msg.to_string()      # body of the msg as a string
                continue

            chan_data = self.msg_string[:bytes_needed]
            self.msg_string = self.msg_string[bytes_needed:]

#           if self.skip_mode:
#               self.skip_mode = False
#               continue

            records = []
            # start = self.skip * gr.sizeof_gr_complex
            # start = 0
            # chan_data = self.msg_string[start:start+bytes_needed]
            rec = numpy.fromstring (chan_data, numpy.float32)
            records.append (rec)
            # self.msg_string = ""

            # unused = nsamples - self.num_plots
            # unused -= (start/gr.sizeof_gr_complex)
            # print "reclen = %d totsamp %d appended %d skip %d start %d unused %d" % (nsamples, self.totsamp, len(rec), self.skip, start/gr.sizeof_float, unused)

            de = correlation_plot_DataEvent (records)
            wx.PostEvent (self.event_receiver, de)
            records = []
            del de

            # lower values = more frequent plots, but higher CPU usage
            # self.skip_samples = 5000
#           self.skip_mode = True

class correlation_plot_window (wx.Panel):

    def __init__ (self, info, parent, id = -1,
                  sps=10,
                  pos = wx.DefaultPosition, size = wx.DefaultSize, name = ""):
        wx.Panel.__init__ (self, parent, -1)
        self.info = info

        vbox = wx.BoxSizer (wx.HORIZONTAL)

        self.graph = correlation_plot_graph_window (info, self, -1, sps=sps)

        vbox.Add (self.graph, 1, wx.EXPAND)
        vbox.Add (self.make_control_box(), 0, wx.EXPAND)
#       vbox.Add (self.make_control2_box(), 0, wx.EXPAND)

        self.sizer = vbox
        self.SetSizer (self.sizer)
        self.SetAutoLayout (True)
        self.sizer.Fit (self)
        

    # second row of control buttons etc. appears BELOW control_box
    def make_control2_box (self):
        ctrlbox = wx.BoxSizer (wx.HORIZONTAL)

        ctrlbox.Add ((5,0) ,0) # left margin space

        return ctrlbox

    def make_control_box (self):
        # 48k iden sync sig
        iden_frame_sync = [0.131053, 0.762875, 0.985880, 0.692932, 0.021247, -0.509172, -0.436476, 0.121728, 0.574703, 0.545912, 0.008813, -0.676659, -0.920639, -0.490609, 0.182287, 0.632788, 0.737212, 0.681760, 0.737237, 0.937172, 1.009479, 0.794382, 0.339788, 0.026356, 0.178487, 0.627079, 0.902744, 0.742624, 0.165377, -0.442614, -0.691702, -0.454418, -0.135002]
        ctrlbox = wx.BoxSizer (wx.HORIZONTAL)

        ctrlbox.Add ((5,0) ,0)

        # read directory of correlation signatures
        ents = []
        self.signatures = []
        r = re.compile(r'^[13]+$')
        path = "corr"
        # another hack, add support for 6000 symbol rate in correlation sigs
        sps_6k = int((self.info.sps * 4800) / 6000)
        for fn in os.listdir(path):
            sps = self.info.sps
            fn_check = fn
            if fn.endswith("-6k"):
                sps = sps_6k
                fn_check = fn_check.replace("-6k", "")
            if not r.match(fn_check):
                continue
            f = open("%s/%s" % (path, fn))
            line = f.readline()
            f.close()
            ents.append(line.strip())

            frame_sync = []
            for c in fn:
                if c == '1':
                    frame_sync.append(1)
                else:	# 3
                    frame_sync.append(-1)
	    correlation = []
            for symbol in frame_sync:
                for i in xrange(sps):
                    correlation.append(symbol)
            correlation.reverse()	# reverse order for convolve()
            self.signatures.append(correlation)

        #special final entry for iden
        ents.append('iDEN')
        correlation = iden_frame_sync
        correlation.reverse()	# reverse order for convolve()
        self.signatures.append(correlation)

        self.radio_box_corr = wx.RadioBox(self, 11105, "Sync Signature", style=wx.RA_SPECIFY_COLS,
                        majorDimension=2, choices = ents )
        self.radio_box_corr.SetToolTipString("Signatures of Known Signal Types")

        ctrlbox.Add (self.radio_box_corr, 0, wx.EXPAND)

        ctrlbox.Add ((10, 0) ,1)            # stretchy space

        return ctrlbox
    
    def run_stop (self, evt):
        self.info.running = not self.info.running

class correlation_plot_graph_window (plot.PlotCanvas):

    def __init__ (self, info, parent, id = -1,
                  pos = wx.DefaultPosition, size = (140, 140),
                  sps=10,
                  style = wx.DEFAULT_FRAME_STYLE, name = ""):
        plot.PlotCanvas.__init__ (self, parent, id, pos, size, style, name)

        self.SetXUseScopeTicks (True)
        self.SetEnableGrid (False)
        self.SetEnableZoom (True)
        self.SetEnableLegend(True)
        # self.SetBackgroundColour ('black')
#        self.Zoom([0, 0], [1.0, 1.0])
        
        self.info = info;
        self.parent = parent;

        self.total_points = 0

        EVT_DATA_EVENT (self, self.format_data)

        self.input_watcher = correlation_plot_input_watcher (info.msgq, self, info.frame_decim)

    def format_data (self, evt):
        if not self.info.running:
            return

        info = self.info
        records = evt.data
        nchannels = len (records)
        npoints = len (records[0])
        self.total_points += npoints

        self.SetXUseScopeTicks (True)   # use 10 divisions, no labels

        objects = []

        r = records[0]  # input data

        sig = self.parent.signatures[self.parent.radio_box_corr.GetSelection()]
	res = numpy.convolve(r, sig, mode='valid')
        p0 = []
        i = 0
        for p in res:
            p0.append([i, p])
            i += 1

        objects.append (plot.PolyLine (p0, colour='blue'))

        graphics = plot.PlotGraphics (objects,
                                      title='Correlation',
                                      xLabel = '', yLabel = '')

        x_range = (0, len(res))
        y_range = (-800.0, 800.0)
        self.Draw (graphics, xAxis=x_range, yAxis=y_range)

#
# following code copied from radiorausch file facsink.py
# source: http://sites.google.com/site/radiorausch/
#
# KA1RBI modified Jul. 2011 to current GR (to fix error messages)
#
# Copyright 2003,2004,2005,2006 Free Software Foundation, Inc.
# 
# This file is part of GNU Radio
# 
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

# default_facsink_size = (640,240)
default_facsink_size = wx.DefaultSize
default_fac_rate = gr.prefs().get_long('wxgui', 'fac_rate', 3) # was 15

class fac_sink_base(object):
    def __init__(self, input_is_real=False, baseband_freq=0, y_per_div=10, ref_level=50,
                 sample_rate=1, fac_size=512,	
                 fac_rate=default_fac_rate,
                 average=False, avg_alpha=None, title='', peak_hold=False):

        # initialize common attributes
        self.baseband_freq = baseband_freq
        self.y_divs = 8
        self.y_per_div=y_per_div
        self.ref_level = ref_level
        self.sample_rate = sample_rate
        self.fac_size = fac_size
        self.fac_rate = fac_rate
        self.average = average
        if avg_alpha is None:
            self.avg_alpha = 0.20 / fac_rate	# averaging needed to be slowed down for very slow rates
        else:
            self.avg_alpha = avg_alpha
        self.title = title
        self.peak_hold = peak_hold
        self.input_is_real = input_is_real
        self.msgq = gr.msg_queue(2)         # queue that holds a maximum of 2 messages

    def set_y_per_div(self, y_per_div):
        self.y_per_div = y_per_div

    def set_ref_level(self, ref_level):
        self.ref_level = ref_level

    def set_average(self, average):
        self.average = average
        if average:
            self.avg.set_taps(self.avg_alpha)
            self.set_peak_hold(False)
        else:
            self.avg.set_taps(1.0)

    def set_peak_hold(self, enable):
        self.peak_hold = enable
        if enable:
            self.set_average(False)
        self.win.set_peak_hold(enable)

    def set_avg_alpha(self, avg_alpha):
        self.avg_alpha = avg_alpha

    def set_baseband_freq(self, baseband_freq):
        self.baseband_freq = baseband_freq

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
        self._set_n()

    def _set_n(self):
        self.one_in_n.set_n(max(1, int(self.sample_rate/self.fac_size/self.fac_rate)))
        

class fac_sink_f(gr.hier_block2, fac_sink_base):
    def __init__(self, parent, baseband_freq=0,
                 y_per_div=10, ref_level=50, sample_rate=1, fac_size=512,
                 fac_rate=default_fac_rate, 
                 average=False, avg_alpha=None,
                 title='', size=default_facsink_size, peak_hold=False):

        fac_sink_base.__init__(self, input_is_real=True, baseband_freq=baseband_freq,
                               y_per_div=y_per_div, ref_level=ref_level,
                               sample_rate=sample_rate, fac_size=fac_size,
                               fac_rate=fac_rate,  
                               average=average, avg_alpha=avg_alpha, title=title,
                               peak_hold=peak_hold)
                               
        s2p = gr.stream_to_vector(gr.sizeof_float, self.fac_size)
        self.one_in_n = gr.keep_one_in_n(gr.sizeof_float * self.fac_size,
                                         max(1, int(self.sample_rate/self.fac_size/self.fac_rate)))


	# windowing removed... 

        fac = gr.fft_vfc(self.fac_size, True, ())
            
        c2mag = gr.complex_to_mag(self.fac_size)
        self.avg = gr.single_pole_iir_filter_ff(1.0, self.fac_size)

	#
	fac_fac   = gr.fft_vfc(self.fac_size, True, ())
        fac_c2mag = gr.complex_to_mag(fac_size)


        # FIXME  We need to add 3dB to all bins but the DC bin
        log = gr.nlog10_ff(20, self.fac_size,
                           -20*math.log10(self.fac_size) )
        sink = gr.message_sink(gr.sizeof_float * self.fac_size, self.msgq, True)

        self.connect(self, s2p, self.one_in_n, fac, c2mag,  fac_fac, fac_c2mag, self.avg, log, sink)
        # gr.hier_block.__init__(self, fg, s2p, sink)
        gr.hier_block2.__init__(self, "fac_sink_f", 
            gr.io_signature(1, 1, gr.sizeof_float),
            gr.io_signature(0, 0, 0))

        self.win = fac_window(self, parent, size=size)
        self.set_average(self.average)



class fac_sink_c(gr.hier_block2, fac_sink_base):
    def __init__(self, parent, baseband_freq=0,
                 y_per_div=10, ref_level=90, sample_rate=1, fac_size=512,
                 fac_rate=default_fac_rate, 
                 average=False, avg_alpha=None,
                 title='', size=default_facsink_size, peak_hold=False):

        fac_sink_base.__init__(self, input_is_real=False, baseband_freq=baseband_freq,
                               y_per_div=y_per_div, ref_level=ref_level,
                               sample_rate=sample_rate, fac_size=fac_size,
                               fac_rate=fac_rate, 
                               average=average, avg_alpha=avg_alpha, title=title,
                               peak_hold=peak_hold)
        gr.hier_block2.__init__(self, "fac_sink_c", 
            gr.io_signature(1, 1, gr.sizeof_gr_complex),
            gr.io_signature(0, 0, 0))

        s2p = blocks.stream_to_vector(gr.sizeof_gr_complex, self.fac_size)
        #s2p = repeater.s2v(gr.sizeof_gr_complex, self.fac_size)
        self.one_in_n = blocks.keep_one_in_n(gr.sizeof_gr_complex * self.fac_size,
                                         max(1, int(self.sample_rate/self.fac_size/self.fac_rate)))


	# windowing removed ...
     
        fac = fft.fft_vcc(self.fac_size, True, ())
        c2mag = blocks.complex_to_mag(fac_size)

        # Things go off into the weeds if we try for an inverse FFT so a forward FFT will have to do...
	fac_fac   = fft.fft_vfc(self.fac_size, True, ())
        fac_c2mag = blocks.complex_to_mag(fac_size)


        self.avg = filter.single_pole_iir_filter_ff(1.0, fac_size)

        log = blocks.nlog10_ff(20, self.fac_size, 
                           -20*math.log10(self.fac_size)  ) #  - 20*math.log10(norm) ) # - self.avg[0] )
        sink = blocks.message_sink(gr.sizeof_float * fac_size, self.msgq, True)

        self.connect(self, s2p, self.one_in_n, fac, c2mag,  fac_fac, fac_c2mag, self.avg)
	self.connect(self.avg, log, sink)

        # gr.hier_block.__init__(self, fg, s2p, sink)

        self.win = fac_window(self, parent, size=size)
        self.set_average(self.average)


# ------------------------------------------------------------------------

fac_myDATA_EVENT = wx.NewEventType()
fac_EVT_DATA_EVENT = wx.PyEventBinder (fac_myDATA_EVENT, 0)


class fac_DataEvent(wx.PyEvent):
    def __init__(self, data):
        wx.PyEvent.__init__(self)
        self.SetEventType (fac_myDATA_EVENT)
        self.data = data

    def Clone (self): 
        self.__class__ (self.GetId())


class fac_input_watcher (threading.Thread):
    def __init__ (self, msgq, fac_size, event_receiver, **kwds):
        threading.Thread.__init__ (self, **kwds)
        self.setDaemon (1)
        self.msgq = msgq
        self.fac_size = fac_size
        self.event_receiver = event_receiver
        self.keep_running = True
        self.start ()

    def run (self):
        while (self.keep_running):
            msg = self.msgq.delete_head()  # blocking read of message queue
            itemsize = int(msg.arg1())
            nitems = int(msg.arg2())

            s = msg.to_string()            # get the body of the msg as a string

            # There may be more than one fac frame in the message.
            # If so, we take only the last one
            if nitems > 1:
                start = itemsize * (nitems - 1)
                s = s[start:start+itemsize]

            complex_data = Numeric.fromstring (s, Numeric.Float32)
            de = fac_DataEvent (complex_data)
            wx.PostEvent (self.event_receiver, de)
            del de
    

class fac_window (plot.PlotCanvas):
    def __init__ (self, facsink, parent, id = -1,
                  pos = wx.DefaultPosition, size = wx.DefaultSize,
                  style = wx.DEFAULT_FRAME_STYLE, name = ""):
        plot.PlotCanvas.__init__ (self, parent, id, pos, size, style, name)

        self.y_range = None
        self.facsink = facsink
        self.peak_hold = False
        self.peak_vals = None

        self.SetEnableGrid (True)
        # self.SetEnableZoom (True)
        # self.SetBackgroundColour ('black')
        
        self.build_popup_menu()
        
        fac_EVT_DATA_EVENT (self, self.set_data)
        wx.EVT_CLOSE (self, self.on_close_window)
        self.Bind(wx.EVT_RIGHT_UP, self.on_right_click)

        self.input_watcher = fac_input_watcher(facsink.msgq, facsink.fac_size, self)


    def on_close_window (self, event):
        print "fac_window:on_close_window"
        self.keep_running = False


    def set_data (self, evt):
        dB = evt.data
        L = len (dB)

        if self.peak_hold:
            if self.peak_vals is None:
                self.peak_vals = dB
            else:
                self.peak_vals = Numeric.maximum(dB, self.peak_vals)
                dB = self.peak_vals

        x = max(abs(self.facsink.sample_rate), abs(self.facsink.baseband_freq))
        sf = 1000.0
        units = "ms"

        x_vals = ((Numeric.arrayrange (L/2)
                       * ( (sf / self.facsink.sample_rate  ) )) )
        points = Numeric.zeros((len(x_vals), 2), Numeric.Float64)
        points[:,0] = x_vals
        points[:,1] = dB[0:L/2]


        lines = plot.PolyLine (points, colour='DARKRED')


        graphics = plot.PlotGraphics ([lines],
                                      title=self.facsink.title,
                                      xLabel = units, yLabel = "dB")

        self.Draw (graphics, xAxis=None, yAxis=self.y_range)
        self.update_y_range ()

    def set_peak_hold(self, enable):
        self.peak_hold = enable
        self.peak_vals = None

    def update_y_range (self):
        ymax = self.facsink.ref_level
        ymin = self.facsink.ref_level - self.facsink.y_per_div * self.facsink.y_divs
        self.y_range = self._axisInterval ('min', ymin, ymax)

    def on_average(self, evt):
        # print "on_average"
        self.facsink.set_average(evt.IsChecked())

    def on_peak_hold(self, evt):
        # print "on_peak_hold"
        self.facsink.set_peak_hold(evt.IsChecked())

    def on_incr_ref_level(self, evt):
        # print "on_incr_ref_level"
        self.facsink.set_ref_level(self.facsink.ref_level
                                   + self.facsink.y_per_div)

    def on_decr_ref_level(self, evt):
        # print "on_decr_ref_level"
        self.facsink.set_ref_level(self.facsink.ref_level
                                   - self.facsink.y_per_div)

    def on_incr_y_per_div(self, evt):
        # print "on_incr_y_per_div"
        self.facsink.set_y_per_div(next_up(self.facsink.y_per_div, (1,2,5,10,20)))

    def on_decr_y_per_div(self, evt):
        # print "on_decr_y_per_div"
        self.facsink.set_y_per_div(next_down(self.facsink.y_per_div, (1,2,5,10,20)))

    def on_y_per_div(self, evt):
        # print "on_y_per_div"
        Id = evt.GetId()
        if Id == self.id_y_per_div_1:
            self.facsink.set_y_per_div(1)
        elif Id == self.id_y_per_div_2:
            self.facsink.set_y_per_div(2)
        elif Id == self.id_y_per_div_5:
            self.facsink.set_y_per_div(5)
        elif Id == self.id_y_per_div_10:
            self.facsink.set_y_per_div(10)
        elif Id == self.id_y_per_div_20:
            self.facsink.set_y_per_div(20)

        
    def on_right_click(self, event):
        menu = self.popup_menu
        for id, pred in self.checkmarks.items():
            item = menu.FindItemById(id)
            item.Check(pred())
        self.PopupMenu(menu, event.GetPosition())


    def build_popup_menu(self):
        self.id_incr_ref_level = wx.NewId()
        self.id_decr_ref_level = wx.NewId()
        self.id_incr_y_per_div = wx.NewId()
        self.id_decr_y_per_div = wx.NewId()
        self.id_y_per_div_1 = wx.NewId()
        self.id_y_per_div_2 = wx.NewId()
        self.id_y_per_div_5 = wx.NewId()
        self.id_y_per_div_10 = wx.NewId()
        self.id_y_per_div_20 = wx.NewId()
        self.id_average = wx.NewId()
        self.id_peak_hold = wx.NewId()

        self.Bind(wx.EVT_MENU, self.on_average, id=self.id_average)
        self.Bind(wx.EVT_MENU, self.on_peak_hold, id=self.id_peak_hold)
        self.Bind(wx.EVT_MENU, self.on_incr_ref_level, id=self.id_incr_ref_level)
        self.Bind(wx.EVT_MENU, self.on_decr_ref_level, id=self.id_decr_ref_level)
        self.Bind(wx.EVT_MENU, self.on_incr_y_per_div, id=self.id_incr_y_per_div)
        self.Bind(wx.EVT_MENU, self.on_decr_y_per_div, id=self.id_decr_y_per_div)
        self.Bind(wx.EVT_MENU, self.on_y_per_div, id=self.id_y_per_div_1)
        self.Bind(wx.EVT_MENU, self.on_y_per_div, id=self.id_y_per_div_2)
        self.Bind(wx.EVT_MENU, self.on_y_per_div, id=self.id_y_per_div_5)
        self.Bind(wx.EVT_MENU, self.on_y_per_div, id=self.id_y_per_div_10)
        self.Bind(wx.EVT_MENU, self.on_y_per_div, id=self.id_y_per_div_20)


        # make a menu
        menu = wx.Menu()
        self.popup_menu = menu
        menu.AppendCheckItem(self.id_average, "Average")
        menu.AppendCheckItem(self.id_peak_hold, "Peak Hold")
        menu.Append(self.id_incr_ref_level, "Incr Ref Level")
        menu.Append(self.id_decr_ref_level, "Decr Ref Level")
        # menu.Append(self.id_incr_y_per_div, "Incr dB/div")
        # menu.Append(self.id_decr_y_per_div, "Decr dB/div")
        menu.AppendSeparator()
        # we'd use RadioItems for these, but they're not supported on Mac
        menu.AppendCheckItem(self.id_y_per_div_1, "1 dB/div")
        menu.AppendCheckItem(self.id_y_per_div_2, "2 dB/div")
        menu.AppendCheckItem(self.id_y_per_div_5, "5 dB/div")
        menu.AppendCheckItem(self.id_y_per_div_10, "10 dB/div")
        menu.AppendCheckItem(self.id_y_per_div_20, "20 dB/div")

        self.checkmarks = {
            self.id_average : lambda : self.facsink.average,
            self.id_peak_hold : lambda : self.facsink.peak_hold,
            self.id_y_per_div_1 : lambda : self.facsink.y_per_div == 1,
            self.id_y_per_div_2 : lambda : self.facsink.y_per_div == 2,
            self.id_y_per_div_5 : lambda : self.facsink.y_per_div == 5,
            self.id_y_per_div_10 : lambda : self.facsink.y_per_div == 10,
            self.id_y_per_div_20 : lambda : self.facsink.y_per_div == 20,
            }


def next_up(v, seq):
    """
    Return the first item in seq that is > v.
    """
    for s in seq:
        if s > v:
            return s
    return v

def next_down(v, seq):
    """
    Return the last item in seq that is < v.
    """
    rseq = list(seq[:])
    rseq.reverse()

    for s in rseq:
        if s < v:
            return s
    return v


# ----------------------------------------------------------------
#          	      Deprecated interfaces
# ----------------------------------------------------------------

# returns (block, win).
#   block requires a single input stream of float
#   win is a subclass of wxWindow

def make_fac_sink_f(fg, parent, title, fac_size, input_rate, ymin = 0, ymax=50):
    
    block = fac_sink_f(fg, parent, title=title, fac_size=fac_size, sample_rate=input_rate,
                       y_per_div=(ymax - ymin)/8, ref_level=ymax)
    return (block, block.win)

# returns (block, win).
#   block requires a single input stream of gr_complex
#   win is a subclass of wxWindow

def make_fac_sink_c(fg, parent, title, fac_size, input_rate, ymin=0, ymax=50):
    block = fac_sink_c(fg, parent, title=title, fac_size=fac_size, sample_rate=input_rate,
                       y_per_div=(ymax - ymin)/8, ref_level=ymax)
    return (block, block.win)


# ----------------------------------------------------------------
# Standalone test app - deleted
# ----------------------------------------------------------------


############################################################################

# Start the receiver
#
if '__main__' == __name__:
    app = stdgui2.stdapp(p25_rx_block, "APCO P25 Receiver", 3)
    app.MainLoop()
