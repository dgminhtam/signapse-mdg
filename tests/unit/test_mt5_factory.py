import ast
import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "mt5" / "prepare_factory.py"
SPEC = importlib.util.spec_from_file_location("mt5_factory", SOURCE)
assert SPEC is not None and SPEC.loader is not None
factory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(factory)


def test_factory_helper_runs_on_python312_and_uses_client_not_wm_frame_origin():
    ast.parse(SOURCE.read_text(encoding="utf-8"), feature_version=(3, 12))
    assert factory.geometry(
        "  Absolute upper-left X: 424\n  Absolute upper-left Y: 328\n"
        "  Relative upper-left X: 1\n  Relative upper-left Y: 20\n"
        "  Width: 620\n  Height: 389\n"
    ) == {"x": 424, "y": 328, "width": 620, "height": 389}


def test_factory_ini_contains_safe_settings_and_only_generated_allowlist(tmp_path):
    path = tmp_path / "common.ini"
    factory.factory_common(path, "AB" * 32)
    common = factory.read_common(path)
    assert not common.has_option("Common", "Login")
    assert not common.has_option("Common", "Password")
    assert common.get("Common", "KeepPrivate") == "0"
    assert common.get("Experts", "WebRequestUrl") == "AB" * 32
    assert all(
        common.get("Experts", key) == "0"
        for key in ("AllowLiveTrading", "AllowDllImport", "Enabled")
    )


@pytest.mark.parametrize("credential", ["MT5_LOGIN", "MT5_PASSWORD", "MT5_TOKEN"])
def test_factory_refuses_runtime_credentials_without_mutation(tmp_path, monkeypatch, credential):
    config = tmp_path / "Config"
    config.mkdir()
    path = config / "common.ini"
    factory.factory_common(path)
    before = path.read_bytes()
    monkeypatch.setenv(credential, "sensitive")
    with pytest.raises(ValueError) as error:
        factory.require_no_account(tmp_path)
    assert "sensitive" not in str(error.value)
    assert path.read_bytes() == before


def test_factory_refuses_existing_account_database(tmp_path):
    config = tmp_path / "Config"
    config.mkdir()
    factory.factory_common(config / "common.ini")
    (config / "accounts.dat").write_bytes(b"private-account-state")
    with pytest.raises(ValueError):
        factory.require_no_account(tmp_path)
