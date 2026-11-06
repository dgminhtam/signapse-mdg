import ast
import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "scripts/mt5/runtime_ui.py"
SPEC = importlib.util.spec_from_file_location("mt5_runtime_ui", SOURCE)
assert SPEC is not None and SPEC.loader is not None
ui = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ui)


def test_helper_runs_on_runtime_python312():
    ast.parse(SOURCE.read_text(), feature_version=(3, 12))
    profiler = SOURCE.with_name("profile_runtime.py")
    ast.parse(profiler.read_text(), feature_version=(3, 12))


def test_selects_main_frame_even_when_minimized_and_helpers_appear_first(monkeypatch):
    def command(*args):
        if args[1] == "search":
            return "11\n12\n13"
        sizes = {"11": (1, 1), "12": (1432, 866), "13": (620, 389)}
        width, height = sizes[args[-1]]
        return f"WIDTH={width}\nHEIGHT={height}"

    monkeypatch.setattr(ui, "command", command)
    assert ui.main_window() == "12"


@pytest.mark.parametrize("action", ["minimize", "close"])
def test_window_control_only_targets_main_frame_and_maps_before_close(monkeypatch, action):
    calls = []
    monkeypatch.setattr(ui, "main_window", lambda: "12")
    monkeypatch.setattr(ui, "command", lambda *args: calls.append(args))
    monkeypatch.setattr(ui.time, "sleep", lambda _: None)
    ui.control(action)
    if action == "minimize":
        assert calls == [("xdotool", "windowminimize", "12")]
    else:
        assert calls == [
            ("xdotool", "windowmap", "12"),
            ("xdotool", "windowactivate", "--sync", "12"),
            ("xdotool", "key", "--clearmodifiers", "alt+F4"),
        ]
