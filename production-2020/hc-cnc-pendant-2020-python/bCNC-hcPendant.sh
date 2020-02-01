#!/bin/sh

# activate the venv for hcPendant, bCNC will invoke from python2 so separate from the venv
cd ~/hcPendant2020
. venv/bin/activate

# stdbuf to disable the pipe default 4k buffer
stdbuf -o0 -e0 python2 -m bCNC 2>&1 | python hc_cnc_pendant_2020.py pendant.ini ~/pendant-email.ini
