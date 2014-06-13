#!/usr/bin/env python
from gnuradio import gr, gru, audio, eng_notation, blocks
from gnuradio.eng_option import eng_option
from optparse import OptionParser

class app_top_block(gr.top_block):
    def __init__(self, options):
        gr.top_block.__init__(self)

        IN = blocks.file_source(gr.sizeof_char, options.input_file)
        bits_per_symbol = 2
        UNPACK = blocks.packed_to_unpacked_bb(bits_per_symbol, gr.GR_MSB_FIRST)
        OUT = blocks.file_sink(gr.sizeof_char, options.output)

        self.connect(IN, UNPACK, OUT)

def main():
    parser = OptionParser(option_class=eng_option)
    parser.add_option("-i", "--input-file", type="string", default="in.dat", help="specify the input file")
    parser.add_option("-o", "--output", type="string", default="out.dat", help="specify the output file")

    (options, args) = parser.parse_args()
 
    tb = app_top_block(options)
    try:
        tb.run()
    except KeyboardInterrupt:
        tb.stop()

if __name__ == "__main__":
    main()
