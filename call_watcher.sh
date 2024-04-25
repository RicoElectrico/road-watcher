#!/bin/bash

log_msg()
{
    echo "[`date +"%Y-%m-%d %H:%M:%S"`] $$ $1"
}

LOCK_FILE="/tmp/road_watcher.lock"

if [ -e "$LOCK_FILE" ]; then
    log_msg "Script is already running. Exiting."
    exit 1
fi

touch "$LOCK_FILE"

sleep $((RANDOM % 120))
#Random sleep so as to ease the load on Overpass server

cd "$(dirname "${BASH_SOURCE[0]}")"
source ./venv/bin/activate
log_msg "Road Watcher starting"
python watcher.py 2>&1
log_msg "Road Watcher finished"

rm -f "$LOCK_FILE"
