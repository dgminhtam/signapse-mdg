"""Configure an installed, clean MT5 terminal from runtime environment variables."""

import configparser
import io
import os
import re
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

DEFAULT_SYMBOLS = (
    "EURUSD,GBPUSD,USDJPY,AUDUSD,XAUUSD,XAGUSD,AAPL,TSLA,NVIDIA,MSFT,BTCUSD,ETHUSD,"
    "SPY,QQQ,USOUSD,UKOUSD,NG-Cr,Coffee-Cr,Sugar-Cr,Wheat-Cr,SP500.r,NAS100.r"
)
SERVICE_NAMES = ("MarketDataService", "CalendarService")


def read_ini(path: Path) -> str:
    data = path.read_bytes()
    text = data.decode("utf-16") if data.startswith(b"\xff\xfe") else data.decode("utf-8-sig")
    return text.replace("\r\n", "\n")


def private_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def configure(terminal_dir: Path, env: Mapping[str, str]) -> None:
    login = env.get("MT5_LOGIN", "")
    password = env.get("MT5_PASSWORD", "")
    server = env.get("MT5_SERVER", "VantageMarkets-Demo")
    token = env.get("MT5_TOKEN", "")
    symbols = [item.strip() for item in env.get("MT5_SYMBOLS", DEFAULT_SYMBOLS).split(",")]
    if not re.fullmatch(r"[0-9]{1,19}", login) or not 0 < int(login) < 2**63:
        raise ValueError("MT5_LOGIN must be a positive account number")
    if not password or any(character in password for character in "\r\n\x00"):
        raise ValueError("MT5_PASSWORD must be nonempty and single-line")
    if password != password.strip():
        raise ValueError("MT5_PASSWORD cannot have surrounding whitespace in an INI value")
    if server != "VantageMarkets-Demo":
        raise ValueError("Only the configured Vantage demo server is supported")
    if not re.fullmatch(r"[!-~]{32,256}", token):
        raise ValueError("MT5_TOKEN requires 32-256 printable non-whitespace ASCII characters")
    if len(set(symbols)) != len(symbols) or set(symbols) != set(DEFAULT_SYMBOLS.split(",")):
        raise ValueError("MT5_SYMBOLS must match all 22 gateway broker mappings exactly")

    common_path = terminal_dir / "Config" / "common.ini"
    common = configparser.ConfigParser(interpolation=None, strict=False)
    common.optionxform = str
    try:
        common.read_string(read_ini(common_path))
    except (OSError, UnicodeError, configparser.Error) as exc:
        raise ValueError("The clean MT5 image must contain a readable common.ini") from exc
    allowlist = common.get("Experts", "WebRequestUrl", fallback="")
    if common.get("Experts", "WebRequest", fallback="") != "1" or not re.fullmatch(
        r"(?:[A-Fa-f0-9]{2}){16,}", allowlist
    ):
        raise ValueError("The clean MT5 image must contain its encrypted TCP allowlist")
    for section, values in (
        (
            "Common",
            {"Login": login, "Password": password, "Server": server, "KeepPrivate": "0"},
        ),
        ("Experts", {"AllowLiveTrading": "0", "AllowDllImport": "0", "Enabled": "0"}),
    ):
        if not common.has_section(section):
            common.add_section(section)
        for key, value in values.items():
            common.set(section, key, value)
    common_text = io.StringIO()
    common.write(common_text, space_around_delimiters=False)

    services_path = terminal_dir / "Config" / "services.ini"
    services = read_ini(services_path) if services_path.exists() else ""
    for name in SERVICE_NAMES:
        services = re.sub(
            r"(?ms)^<service>\s*\n(?:(?!^</service>).)*?^name="
            + re.escape(name)
            + r"\s*\n(?:(?!^</service>).)*?^</service>\s*",
            "",
            services,
        )
    services = services.rstrip()
    for port, name in enumerate(SERVICE_NAMES, start=9001):
        services += (
            f"\n<service>\nname={name}\npath=Services\\{name}.ex5\nexpertmode=0\nenabled=1\n"
            f"<inputs>\nReceiverHost=mdg-tcp-smoke.test\nReceiverPort={port}\n"
            + ("PollMilliseconds=250\n" if name == "MarketDataService" else "")
            + "</inputs>\n</service>\n"
        )

    # Render every output before changing private state, so invalid inputs write nothing.
    outputs = {
        common_path: b"\xff\xfe" + common_text.getvalue().encode("utf-16le"),
        services_path: b"\xff\xfe" + services.encode("utf-16le"),
        terminal_dir / "MQL5" / "Files" / "MarketDataToken.txt": token.encode("ascii"),
        terminal_dir / "MQL5" / "Files" / "MarketDataSymbols.txt": ",".join(symbols).encode(
            "ascii"
        ),
    }
    for path, content in outputs.items():
        private_write(path, content)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: configure.py <terminal-directory>", file=sys.stderr)
        return 1
    try:
        configure(Path(sys.argv[1]), os.environ)
    except (OSError, UnicodeError) as _exc:
        print(
            "MT5 configuration failed: private configuration could not be written", file=sys.stderr
        )
        return 1
    except ValueError as exc:
        print(f"MT5 configuration failed: {exc}", file=sys.stderr)
        return 1
    print("MT5 runtime configuration prepared; automated trading remains disabled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
