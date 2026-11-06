import ast
import configparser
import importlib.util
import stat
from pathlib import Path

import pytest

from scripts.seed_mt5_local import MAPPINGS

SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "mt5" / "configure.py"
SPEC = importlib.util.spec_from_file_location("mt5_configure", SOURCE)
assert SPEC is not None and SPEC.loader is not None
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def test_helper_syntax_runs_on_the_wine_image_python_312():
    ast.parse(SOURCE.read_text(encoding="utf-8"), feature_version=(3, 12))


def test_default_broker_symbols_match_the_gateway_seed():
    assert bootstrap.DEFAULT_SYMBOLS.split(",") == list(MAPPINGS.values())


@pytest.fixture
def terminal(tmp_path):
    config = tmp_path / "Config"
    config.mkdir()
    (config / "common.ini").write_text(
        "[Common]\nLogin=1\n[Experts]\nWebRequest=1\nWebRequestUrl="
        + "AB" * 32
        + "\nAllowLiveTrading=1\nAllowDllImport=1\nEnabled=1\n",
        encoding="utf-16",
    )
    return tmp_path


@pytest.fixture
def env():
    return {"MT5_LOGIN": "123456", "MT5_PASSWORD": "test-ä%#;=[]", "MT5_TOKEN": "t" * 40}


def test_configures_credentials_both_services_and_private_files(terminal, env):
    bootstrap.configure(terminal, env)
    common_path = terminal / "Config" / "common.ini"
    assert common_path.read_bytes().startswith(b"\xff\xfe")
    common = configparser.ConfigParser(interpolation=None)
    common.read_string(bootstrap.read_ini(common_path))
    assert common["Common"]["Password"] == env["MT5_PASSWORD"]
    assert common["Common"]["Server"] == "VantageMarkets-Demo"
    assert common["Common"]["KeepPrivate"] == "0"
    assert common["Experts"]["WebRequestUrl"] == "AB" * 32
    for field in ("AllowLiveTrading", "AllowDllImport", "Enabled"):
        assert common["Experts"][field] == "0"
    services = bootstrap.read_ini(terminal / "Config" / "services.ini")
    assert "ReceiverPort=9001" in services and "ReceiverPort=9002" in services
    files = terminal / "MQL5" / "Files"
    assert (files / "MarketDataToken.txt").read_text() == env["MT5_TOKEN"]
    assert len((files / "MarketDataSymbols.txt").read_text().split(",")) == 20
    for path in (common_path, terminal / "Config" / "services.ini", *files.iterdir()):
        if __import__("os").name != "nt":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_accepts_the_exact_symbol_set_in_another_order(terminal, env):
    symbols = list(reversed(bootstrap.DEFAULT_SYMBOLS.split(",")))
    env["MT5_SYMBOLS"] = ", ".join(symbols)
    bootstrap.configure(terminal, env)
    path = terminal / "MQL5" / "Files" / "MarketDataSymbols.txt"
    assert path.read_text().split(",") == symbols


def test_service_configuration_is_idempotent_and_keeps_unrelated_records(terminal, env):
    unrelated = (
        "<service>\nname=OtherService\npath=Services\\OtherService.ex5\nenabled=1\n</service>\n"
    )
    path = terminal / "Config" / "services.ini"
    path.write_text(unrelated, encoding="utf-16")
    bootstrap.configure(terminal, env)
    first = path.read_bytes()
    bootstrap.configure(terminal, env)
    assert path.read_bytes() == first
    text = bootstrap.read_ini(path)
    assert unrelated in text
    for name in bootstrap.SERVICE_NAMES:
        assert text.count(f"name={name}\n") == 1
    assert not list(terminal.rglob("tmp*"))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("MT5_LOGIN", "123\nsecret"),
        ("MT5_PASSWORD", "secret\n[Experts]\nAllowLiveTrading=1"),
        ("MT5_PASSWORD", ""),
        ("MT5_PASSWORD", " surrounded "),
        ("MT5_SERVER", "OtherServer"),
        ("MT5_TOKEN", "short"),
        ("MT5_TOKEN", "t" * 40 + "\n"),
        ("MT5_SYMBOLS", "EURUSD,EURUSD"),
        ("MT5_SYMBOLS", "EURUSD,../secret"),
        ("MT5_SYMBOLS", "EURUSD"),
        ("MT5_SYMBOLS", bootstrap.DEFAULT_SYMBOLS + ",EXTRA"),
    ],
)
def test_rejects_invalid_input_without_writing_or_exposing_values(terminal, env, key, value):
    before = {p.relative_to(terminal): p.read_bytes() for p in terminal.rglob("*") if p.is_file()}
    env[key] = value
    with pytest.raises(ValueError) as caught:
        bootstrap.configure(terminal, env)
    assert "secret" not in str(caught.value)
    assert {
        p.relative_to(terminal): p.read_bytes() for p in terminal.rglob("*") if p.is_file()
    } == before


def test_requires_prepared_encrypted_allowlist_before_writing(terminal, env):
    path = terminal / "Config" / "common.ini"
    path.write_text("[Experts]\nWebRequest=1\nWebRequestUrl=http://receiver\n", encoding="utf-16")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="encrypted TCP allowlist"):
        bootstrap.configure(terminal, env)
    assert path.read_bytes() == before and not (terminal / "MQL5").exists()


def test_cli_failure_does_not_emit_credentials(terminal, env, monkeypatch, capsys):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("MT5_PASSWORD", "sensitive\npassword")
    monkeypatch.setattr(bootstrap.sys, "argv", ["configure.py", str(terminal)])
    assert bootstrap.main() == 1
    captured = capsys.readouterr()
    assert "sensitive" not in captured.err and env["MT5_TOKEN"] not in captured.err
