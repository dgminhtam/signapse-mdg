"""Prepare MT5's public broker catalog and native allowlist without an account."""

import configparser
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

RECEIVER_URL = "http://mdg-tcp-smoke.test"


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=10).strip()


def geometry(output: str) -> dict[str, int]:
    labels = {
        "x": "Absolute upper-left X",
        "y": "Absolute upper-left Y",
        "width": "Width",
        "height": "Height",
    }
    result = {}
    for key, label in labels.items():
        match = re.search(r"^\s*" + label + r":\s*(-?\d+)\s*$", output, re.MULTILINE)
        if match is None:
            raise ValueError("Could not read the native window client geometry")
        result[key] = int(match.group(1))
    return result


def windows() -> list[dict[str, object]]:
    try:
        identifiers = command("xdotool", "search", "--onlyvisible", "--class", "terminal64.exe")
    except subprocess.CalledProcessError:
        return []
    result = []
    for identifier in identifiers.splitlines():
        try:
            result.append(
                {
                    "id": identifier,
                    "title": command("xdotool", "getwindowname", identifier),
                    **geometry(command("xwininfo", "-id", identifier)),
                }
            )
        except subprocess.CalledProcessError:
            continue
    return result


def wait_window(kind: str, timeout: float = 30) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for window in windows():
            title, width, height = window["title"], window["width"], window["height"]
            if (
                (kind == "main" and str(title).startswith("MetaTrader 5") and int(width) > 1000)
                or (kind == "options" and title == "Options")
                or (kind == "broker" and 680 <= int(width) <= 710 and 500 <= int(height) <= 540)
            ):
                return window
        time.sleep(0.3)
    raise RuntimeError(f"Timed out waiting for the native {kind} window")


def activate(window: dict[str, object]) -> None:
    command("xdotool", "windowactivate", "--sync", str(window["id"]))
    time.sleep(0.3)


def click(window: dict[str, object], x: int, y: int, repeat: int = 1) -> None:
    command(
        "xdotool",
        "mousemove",
        str(int(window["x"]) + x),
        str(int(window["y"]) + y),
        "click",
        "--repeat",
        str(repeat),
        "--delay",
        "100",
        "1",
    )
    time.sleep(0.3)


def read_common(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-16")
    return parser


def require_no_account(directory: Path) -> None:
    config = directory / "Config"
    common = read_common(config / "common.ini")
    if (
        common.get("Common", "Login", fallback="0") not in ("", "0")
        or common.get("Common", "Password", fallback="")
        or (config / "accounts.dat").exists()
        or any(os.environ.get(key) for key in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_TOKEN"))
    ):
        raise ValueError(
            "Factory preparation requires a clean terminal without account credentials"
        )


def factory_common(path: Path, allowlist: str = "") -> None:
    text = (
        "[Common]\nKeepPrivate=0\nNewsEnable=0\n\n[Experts]\n"
        "AllowLiveTrading=0\nAllowDllImport=0\nEnabled=0\nWebRequest=1\n"
        f"WebRequestUrl={allowlist}\n\n[Charts]\nMaxBars=100000\n"
    )
    path.write_bytes(b"\xff\xfe" + text.encode("utf-16le"))
    path.chmod(0o600)


def close_terminal(main: dict[str, object]) -> None:
    activate(main)
    command("xdotool", "key", "--clearmodifiers", "alt+F4")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if not any(str(w["title"]).startswith("MetaTrader 5") for w in windows()):
            subprocess.run(["wineserver", "-w"], check=True, timeout=30)
            return
        time.sleep(0.3)
    raise RuntimeError("Native MT5 did not finish its clean shutdown")


def prepare(directory: Path) -> dict[str, object]:
    require_no_account(directory)
    config = directory / "Config"
    common_path = config / "common.ini"
    # Copied allowlists failed fresh-install tests; let MT5 serialize the factory's own list.
    factory_common(common_path)
    with Path("/tmp/mt5-factory.log").open("wb") as log:
        subprocess.Popen(
            ["wine", str(directory / "terminal64.exe"), "/portable"], stdout=log, stderr=log
        )
    main = wait_window("main", timeout=90)
    try:
        broker = wait_window("broker", timeout=5)
    except RuntimeError:
        activate(main)
        command("xdotool", "key", "--clearmodifiers", "alt+f")
        time.sleep(0.3)
        click(main, 95, 313)
        broker = wait_window("broker")
    # shortcut: English MT5 dialogs at 1440x900; recheck positions when the terminal UI changes.
    activate(broker)
    click(broker, 185, 90)
    command("xdotool", "key", "--clearmodifiers", "ctrl+a")
    command("xdotool", "type", "--clearmodifiers", "--delay", "100", "Vantage")
    click(broker, 610, 90)
    # Search populates a public catalog only; never advance to account creation or login.
    time.sleep(8)
    click(broker, 640, 495)
    activate(main)
    command("xdotool", "key", "--clearmodifiers", "ctrl+o")
    options = wait_window("options")
    activate(options)
    click(options, 170, 14)
    click(options, 120, 235, repeat=2)
    command("xdotool", "type", "--clearmodifiers", "--delay", "60", RECEIVER_URL)
    command("xdotool", "key", "Return")
    time.sleep(0.3)
    click(options, 415, 369)
    close_terminal(main)
    require_no_account(directory)
    common = read_common(common_path)
    allowlist = common.get("Experts", "WebRequestUrl", fallback="")
    if not re.fullmatch(r"(?:[A-Fa-f0-9]{2}){16,}", allowlist):
        raise RuntimeError("MT5 did not persist the native receiver allowlist")
    catalog = config / "servers.dat"
    if not catalog.is_file() or catalog.stat().st_size == 0:
        raise RuntimeError("MT5 did not persist its public broker catalog")
    factory_common(common_path, allowlist)
    require_no_account(directory)
    return {
        "accountFree": True,
        "brokerCatalogBytes": catalog.stat().st_size,
        "nativeAllowlistCharacters": len(allowlist),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: prepare_factory.py <terminal-directory>", file=sys.stderr)
        return 1
    try:
        print(json.dumps(prepare(Path(sys.argv[1]))))
    except Exception as exc:
        print(
            f"Factory preparation failed ({type(exc).__name__}); inspect account-free build UI.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
