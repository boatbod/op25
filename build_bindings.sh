#!/bin/bash
echo "Building bindings for gr-op25"
(cd op25/gr-op25
 for module in include/gnuradio/op25/*.h; do
    module=$(basename $module .h)
    test "$module" = "api" && continue 
    gr_modtool bind $module
 done)
echo "Building bindings for gr-op25_repeater"
(cd op25/gr-op25_repeater
 for module in include/gnuradio/op25_repeater/*.h; do
    module=$(basename $module .h)
    test "$module" = "api" && continue 
    gr_modtool bind $module
 done)

