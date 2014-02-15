#!/usr/bin/env python

from gnuradio import gr, gru, audio, eng_notation, analog, blocks, filter
from gnuradio.eng_option import eng_option
from optparse import OptionParser
import numpy as np

import op25_repeater
import lfsr

class app_top_block(gr.top_block):
    def __init__(self, options):
        gr.top_block.__init__(self, "mhp")

        self.lfsr = lfsr.p25p2_lfsr(options.nac, options.sysid, options.wacn)
        xor_mask = ''
        for c in self.lfsr.xorsyms:
            xor_mask += chr(c)

        IN = blocks.file_source(gr.sizeof_char, options.input_file)

        slotid = options.tdma_slotid
        FRAMER = op25_repeater.p25p2_frame(0, slotid)
        FRAMER.set_xormask(xor_mask)

        S2F = blocks.short_to_float()
        M = blocks.multiply_const_ff(1.0 / 32767.0)

        SINK = audio.sink(8000, 'plughw:0,0')
        
        self.connect(IN, FRAMER, S2F, M, SINK)

def main():
    parser = OptionParser(option_class=eng_option)
    parser.add_option("-v", "--verbose", action="store_true", default=False)
    parser.add_option("-i", "--input-file", type="string", default=None, help="input file name")
    parser.add_option("-n", "--nac", type="int", default=0, help="NAC")
    parser.add_option("-s", "--sysid", type="int", default=0, help="sysid")
    parser.add_option("-t", "--tdma-slotid", type="int", default=0, help="tdma-slotid (0 or 1)")
    parser.add_option("-w", "--wacn", type="int", default=0, help="WACN")
    (options, args) = parser.parse_args()
    if len(args) != 0:
        parser.print_help()
        sys.exit(1)

    assert options.tdma_slotid == 0 or options.tdma_slotid == 1
 
    tb = app_top_block(options)
    try:
        tb.run()
    except KeyboardInterrupt:
        tb.stop()

if __name__ == "__main__":
    main()
