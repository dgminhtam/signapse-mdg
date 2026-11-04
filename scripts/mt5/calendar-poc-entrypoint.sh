#!/usr/bin/env bash
set -euo pipefail
umask 077
cleanup() {
  # MT5 must save its writable configuration before Wine is terminated.
  window=$(xdotool search --onlyvisible --class terminal64.exe 2>/dev/null | head -n 1 || true)
  if [[ -n "$window" ]]; then
    xdotool windowactivate "$window" key --clearmodifiers alt+F4 2>/dev/null || true
    for attempt in {1..40}; do
      pgrep -f '[t]erminal64.exe' >/dev/null || break
      sleep 0.25
    done
  fi
  wineserver -k || true
  jobs -pr | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 0' TERM INT
Xvfb "$DISPLAY" -screen 0 1440x900x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
for attempt in {1..50}; do
  if xdpyinfo >/dev/null 2>&1; then break; fi
  sleep 0.2
done
xdpyinfo >/dev/null
openbox >/tmp/openbox.log 2>&1 &
# VNC stays inside the container; only its browser frontend is bound to host loopback.
x11vnc -display "$DISPLAY" -localhost -rfbport 5900 -nopw -forever -shared -o /tmp/x11vnc.log &
websockify --web=/usr/share/novnc 6080 localhost:5900 >/tmp/novnc.log 2>&1 &
terminal="$WINEPREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe"
if [[ ! -f "$terminal" ]]; then
  while [[ ! -s /opt/mt5/installers/mt5setup.exe ]]; do
    echo 'Waiting for the official installer at installers/mt5setup.exe; desktop is available.'
    sleep 15
  done
  echo 'Initializing Wine and the official MT5 installer.'
  WINEDLLOVERRIDES=mscoree=d wineboot -u >/tmp/wineboot.log 2>&1
  # The installer needs a writable Windows-side directory during extraction.
  cp /opt/mt5/installers/mt5setup.exe "$WINEPREFIX/drive_c/mt5setup.exe"
  wine 'C:\mt5setup.exe' /auto >/tmp/mt5-installer.log 2>&1 &
  installer_pid=$!
  for attempt in {1..240}; do
    if [[ -f "$terminal" ]] && ! kill -0 "$installer_pid" 2>/dev/null; then break; fi
    sleep 1
  done
  if [[ ! -f "$terminal" ]]; then
    echo 'Installer needs attention in the localhost desktop.'
    wait "$installer_pid"
  fi
  wineserver -k || true
fi
test -f "$terminal"
terminal_dir="$(dirname "$terminal")"
if [[ ! -f "$HOME/.mdg-writable-config" ]]; then
  # /config is read-only in MT5: GUI allowlist edits would be discarded on restart.
  test ! -f "$terminal_dir/Config/common.ini" || cp "$terminal_dir/Config/common.ini" "$HOME/common-before-mdg.ini"
  cp /run/secrets/terminal-login "$terminal_dir/Config/common.ini"
  chmod 600 "$terminal_dir/Config/common.ini"
  touch "$HOME/.mdg-writable-config"
fi
mkdir -p "$terminal_dir/MQL5/Services" "$terminal_dir/MQL5/Files"
cp /opt/mt5/mql5/*.mq5 "$terminal_dir/MQL5/Services/"
for service in MarketDataService CalendarService; do
  cp "$terminal_dir/MQL5/Services/$service.mq5" "$WINEPREFIX/drive_c/$service.mq5"
  rm -f "$WINEPREFIX/drive_c/$service.ex5" "$WINEPREFIX/drive_c/$service-compile.log"
  wine "$terminal_dir/metaeditor64.exe" /portable "/compile:C:\\$service.mq5" "/log:C:\\$service-compile.log" >"$HOME/$service-compile-runtime.log" 2>&1 || true
  test -s "$WINEPREFIX/drive_c/$service.ex5"
  cp "$WINEPREFIX/drive_c/$service.ex5" "$terminal_dir/MQL5/Services/$service.ex5"
done
echo 'Starting MT5 in portable mode; automated trading is disabled by config.'
wine "$terminal" /portable >/tmp/mt5-runtime.log 2>&1 &
wait $!
# Live Update replaces the launcher with another Wine process.
wineserver -w
