#!/bin/bash

progdir="$(cd $(dirname "$0") || exit; pwd)"/storage

python3 "${progdir}/main.py" > "${progdir}/log.txt" 2>&1
