#!/bin/sh

# activate the venv for hcPendant, bCNC will invoke from python2 so separate from the venv
cd ~/hcPendant2020
. venv/bin/activate

python2 -m bCNC | python hc_cnc_pendant_2020.py

