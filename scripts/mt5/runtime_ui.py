"""Keep the unattended terminal minimized and restore it for a clean shutdown."""

import subprocess
import sys
import time


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=5).strip()


def main_window() -> str | None:
    try:
        identifiers = command("xdotool", "search", "--class", "terminal64.exe").split()
    except subprocess.CalledProcessError:
        return None
    candidates = []
    for identifier in identifiers:
        try:
            geometry = dict(
                line.split("=", 1)
                for line in command(
                    "xdotool", "getwindowgeometry", "--shell", identifier
                ).splitlines()
            )
            width, height = int(geometry["WIDTH"]), int(geometry["HEIGHT"])
        except (subprocess.SubprocessError, KeyError, ValueError) as _exc:
            continue
        # Wine has many invisible 1px helper windows; only manage the main frame.
        if width >= 640 and height >= 480:
            candidates.append((width * height, identifier))
    return max(candidates)[1] if candidates else None


def control(action: str) -> None:
    deadline = time.monotonic() + (120 if action == "minimize" else 5)
    while True:
        identifier = main_window()
        if identifier is not None:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("Main terminal window was not found")
        time.sleep(0.5)
    if action == "minimize":
        command("xdotool", "windowminimize", identifier)
    else:
        command("xdotool", "windowmap", identifier)
        command("xdotool", "windowactivate", "--sync", identifier)
        time.sleep(0.3)
        command("xdotool", "key", "--clearmodifiers", "alt+F4")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("minimize", "close"):
        raise SystemExit("Usage: runtime_ui.py minimize|close")
    try:
        control(sys.argv[1])
    except Exception as exc:
        print(f"Terminal window control failed ({type(exc).__name__})", file=sys.stderr)
        raise SystemExit(1) from None
