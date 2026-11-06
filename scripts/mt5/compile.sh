#!/usr/bin/env bash
set -euo pipefail
umask 077
Xvfb "$DISPLAY" -screen 0 1440x900x24 -nolisten tcp >/tmp/compile-xvfb.log 2>&1 &
trap 'wineserver -k >/dev/null 2>&1 || true; jobs -pr | xargs -r kill 2>/dev/null || true' EXIT
for attempt in {1..50}; do
  if xdpyinfo >/dev/null 2>&1; then break; fi
  sleep 0.2
done
xdpyinfo >/dev/null || { cat /tmp/compile-xvfb.log; exit 1; }
terminal_dir="$WINEPREFIX/drive_c/Program Files/MetaTrader 5"
mkdir -p /opt/mt5/services
for service in MarketDataService CalendarService FileSharingCheck; do
  cp "/opt/mt5/mql5/$service.mq5" "$WINEPREFIX/drive_c/$service.mq5"
  rm -f "$WINEPREFIX/drive_c/$service.ex5" "$WINEPREFIX/drive_c/$service-compile.log"
  timeout 180 wine "$terminal_dir/metaeditor64.exe" /portable "/compile:C:\\$service.mq5" "/log:C:\\$service-compile.log" >"/tmp/$service-compiler.log" 2>&1 || true
  test -s "$WINEPREFIX/drive_c/$service.ex5"
  iconv -f UTF-16LE -t UTF-8 "$WINEPREFIX/drive_c/$service-compile.log" | grep -F '0 errors, 0 warnings'
  cp "$WINEPREFIX/drive_c/$service.ex5" "/opt/mt5/services/$service.ex5"
  rm "$WINEPREFIX/drive_c/$service.mq5" "$WINEPREFIX/drive_c/$service.ex5" "$WINEPREFIX/drive_c/$service-compile.log"
done
wineserver -w
mkdir -p "$terminal_dir/MQL5/Services"
cp /opt/mt5/services/FileSharingCheck.ex5 "$terminal_dir/MQL5/Services/"
printf '\377\376' > "$terminal_dir/Config/services.ini"
printf '<service>\nname=FileSharingCheck\npath=Services\\FileSharingCheck.ex5\nexpertmode=0\nenabled=1\n</service>\n' | iconv -f UTF-8 -t UTF-16LE >> "$terminal_dir/Config/services.ini"
wine "$terminal_dir/terminal64.exe" /portable >/tmp/file-sharing-check.log 2>&1 &
result="$terminal_dir/MQL5/Files/MdgFileSharingCheck.json"
for attempt in {1..60}; do
  if [[ -s "$result" ]]; then break; fi
  sleep 1
done
python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); assert r == {"exclusiveBlocksSecondReader": True, "sharedAllowsBothReaders": True}; print(json.dumps(r))' "$result"
wineserver -k
rm /opt/mt5/services/FileSharingCheck.ex5
