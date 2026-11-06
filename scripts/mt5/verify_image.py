"""Run through stdin inside the final image, without mounting private state."""

import configparser
import hashlib
import json
import os
import shutil
from pathlib import Path

home = Path.home()
terminal = home / ".wine/drive_c/Program Files/MetaTrader 5"
common = configparser.ConfigParser(interpolation=None)
common.read(terminal / "Config/common.ini", encoding="utf-16")
assert common.get("Common", "Login", fallback="0") in ("", "0")
assert not common.get("Common", "Password", fallback="")
assert not (terminal / "Config/accounts.dat").exists()
assert not (terminal / "MQL5/Files/MarketDataToken.txt").exists()
assert not (home / ".wine/drive_c/mdg-start.ini").exists()
assert not any(os.environ.get(key) for key in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_TOKEN"))
assert all(
    common.get("Experts", key) == "0" for key in ("AllowLiveTrading", "AllowDllImport", "Enabled")
)
assert common.get("Experts", "WebRequest") == "1"
assert common.get("Experts", "WebRequestUrl")
assert (terminal / "terminal64.exe").is_file()
assert all(shutil.which(name) for name in ("wine", "Xvfb", "python3"))
assert all(shutil.which(name) is None for name in ("x11vnc", "websockify", "novnc"))
assert not Path("/usr/share/novnc").exists()
assert not any(path.is_file() for path in home.rglob("*[Mm]eta[Ee]ditor*"))
assert {p.name for p in Path("/opt/mt5/services").iterdir()} == {
    "MarketDataService.ex5",
    "CalendarService.ex5",
}
assert not (terminal / "MQL5/Files/MdgFileSharingCheck.json").exists()
services = {}
for name in ("MarketDataService", "CalendarService"):
    binary = Path(f"/opt/mt5/services/{name}.ex5").read_bytes()
    assert len(binary) > 1000
    services[name] = {"bytes": len(binary), "sha256": hashlib.sha256(binary).hexdigest()}
print(json.dumps({"accountFree": True, "leanRuntime": True, "services": services}))
