#!/usr/bin/env bash
set -euo pipefail
umask 077
cleanup() {
  # MT5 must save its writable configuration before Wine is terminated.
  python3 /opt/mt5/runtime_ui.py close >/tmp/mt5-close.log 2>&1 || true
  for attempt in {1..40}; do
    pgrep -f '[t]erminal64.exe' >/dev/null || break
    sleep 0.25
  done
  timeout 5 wineserver -k || true
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
terminal="$WINEPREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe"
test -f "$terminal"
terminal_dir="$(dirname "$terminal")"
startup_args=(/portable)
if [[ -n "${MT5_LOGIN:-}" ]]; then
  python3 /opt/mt5/configure.py "$terminal_dir"
  cp "$terminal_dir/Config/common.ini" "$WINEPREFIX/drive_c/mdg-start.ini"
  chmod 600 "$WINEPREFIX/drive_c/mdg-start.ini"
  startup_args+=(/config:C:\\mdg-start.ini)
elif [[ ! -f "$HOME/.mdg-writable-config" ]]; then
  # /config is read-only in MT5: GUI allowlist edits would be discarded on restart.
  test ! -f "$terminal_dir/Config/common.ini" || cp "$terminal_dir/Config/common.ini" "$HOME/common-before-mdg.ini"
  cp /run/secrets/terminal-login "$terminal_dir/Config/common.ini"
  chmod 600 "$terminal_dir/Config/common.ini"
  touch "$HOME/.mdg-writable-config"
fi
mkdir -p "$terminal_dir/MQL5/Services" "$terminal_dir/MQL5/Files"
for service in MarketDataService CalendarService; do
  test -s "/opt/mt5/services/$service.ex5"
  cp "/opt/mt5/services/$service.ex5" "$terminal_dir/MQL5/Services/$service.ex5"
done
services="$terminal_dir/Config/services.ini"
if ! test -s "$services"; then printf '\377\376' > "$services"; fi
if ! iconv -f UTF-16LE -t UTF-8 "$services" | grep -F 'name=CalendarService' >/dev/null; then
  printf '\n<service>\nname=CalendarService\npath=Services\\CalendarService.ex5\nexpertmode=0\nenabled=1\n<inputs>\nReceiverHost=mdg-tcp-smoke.test\nReceiverPort=9002\n</inputs>\n</service>\n' | iconv -f UTF-8 -t UTF-16LE >> "$services"
fi
echo 'Starting MT5 in portable mode; automated trading is disabled by config.'
wine "$terminal" "${startup_args[@]}" >/tmp/mt5-runtime.log 2>&1 &
terminal_pid=$!
python3 /opt/mt5/runtime_ui.py minimize >/tmp/mt5-minimize.log 2>&1 &
wait "$terminal_pid"
# Live Update replaces the launcher with another Wine process.
wineserver -w
