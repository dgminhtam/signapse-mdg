#!/usr/bin/env bash
set -euo pipefail
umask 077
Xvfb "$DISPLAY" -screen 0 1440x900x24 -nolisten tcp >/tmp/factory-xvfb.log 2>&1 &
trap 'wineserver -k >/dev/null 2>&1 || true; jobs -pr | xargs -r kill 2>/dev/null || true' EXIT
for attempt in {1..50}; do
  if xdpyinfo >/dev/null 2>&1; then break; fi
  sleep 0.2
done
xdpyinfo >/dev/null
openbox >/tmp/factory-openbox.log 2>&1 &
python3 /opt/mt5/prepare_factory.py "$WINEPREFIX/drive_c/Program Files/MetaTrader 5"
