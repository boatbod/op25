#! /bin/sh

export OP25_HOME="${OP25_HOME:-`pwd`}"
export OP25_FREQ_CORR="${OP25_FREQ_CORR:-0}"
export OP25_WEBAPP_PORT="${OP25_WEBAPP_PORT:-8088}"

cd ${OP25_HOME}/op25/gr-op25_repeater/apps

./rx.py --args 'rtl' -N 'LNA:47' -S 960000 -x 2 -o 17e3 -q ${OP25_FREQ_CORR} -T trunk.tsv -V -2 -U -l http:0.0.0.0:${OP25_WEBAPP_PORT}
