#!/usr/bin/env bash
set -euo pipefail
umask 077
# This build step never receives account credentials or copies an existing Wine prefix.
test ! -d "$WINEPREFIX"
Xvfb "$DISPLAY" -screen 0 1440x900x24 -nolisten tcp >/tmp/build-xvfb.log 2>&1 &
display_pid=$!
trap 'wineserver -k >/dev/null 2>&1 || true; kill "$display_pid" 2>/dev/null || true' EXIT
for attempt in {1..50}; do
  if xdpyinfo >/dev/null 2>&1; then break; fi
  sleep 0.2
done
xdpyinfo >/dev/null
echo 'Initializing the account-free Wine prefix.'
WINEDLLOVERRIDES=mscoree=d timeout 180 wineboot -u >/tmp/build-wineboot.log 2>&1
curl --fail --location --retry 3 --max-time 600 \
  https://download.terminal.free/cdn/web/metaquotes.ltd/mt5/mt5setup.exe \
  --output "$WINEPREFIX/drive_c/mt5setup.exe"
echo 'Installing the official MT5 distribution (bounded to ten minutes).'
timeout 600 wine 'C:\mt5setup.exe' /auto >/tmp/build-mt5-install.log 2>&1 || true
terminal_dir="$WINEPREFIX/drive_c/Program Files/MetaTrader 5"
test -s "$terminal_dir/terminal64.exe"
editor=$(find "$terminal_dir" -maxdepth 1 -type f -iname metaeditor64.exe -print -quit)
test -n "$editor" && test -s "$editor"
if [[ "$editor" != "$terminal_dir/metaeditor64.exe" ]]; then
  mv "$editor" "$terminal_dir/metaeditor64.exe"
fi
wineserver -k
mkdir -p "$terminal_dir/Config"
# The following factory step adds the fixed receiver through MT5's own settings UI.
printf '\377\376' > "$terminal_dir/Config/common.ini"
iconv -f UTF-8 -t UTF-16LE /opt/mt5/factory-common.ini >> "$terminal_dir/Config/common.ini"
rm -f "$terminal_dir/Config/accounts.dat" "$WINEPREFIX/drive_c/mt5setup.exe"
echo 'Packaged clean MT5; runtime credentials are supplied by Compose.'
