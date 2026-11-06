"""Read-only Linux cgroup/process profile; run via docker exec stdin."""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path


def counters(text: str) -> tuple[int, int]:
    fields = text.rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12]), int(fields[19])


def snapshot() -> dict:
    processes, threads = {}, {}
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            name = (process / "comm").read_text().strip()
            ticks, started = counters((process / "stat").read_text())
            processes[process.name] = {"name": name, "ticks": ticks, "started": started}
            for thread in (process / "task").iterdir():
                ticks, started = counters((thread / "stat").read_text())
                threads[f"{process.name}/{thread.name}"] = {
                    "name": (thread / "comm").read_text().strip(),
                    "process": name,
                    "ticks": ticks,
                    "started": started,
                }
        except (OSError, ValueError, IndexError) as _exc:
            continue
    group = Path("/sys/fs/cgroup")
    cpu = dict(line.split() for line in (group / "cpu.stat").read_text().splitlines())
    memory = dict(line.split() for line in (group / "memory.stat").read_text().splitlines())
    working_set = int((group / "memory.current").read_text()) - int(memory["inactive_file"])
    return {
        "clock": time.monotonic(),
        "cpuUsec": int(cpu["usage_usec"]),
        "workingSetMiB": working_set / 1048576,
        "processes": processes,
        "threads": threads,
    }


def profile(seconds: float, label: str) -> dict:
    start = snapshot()
    time.sleep(seconds)
    end = snapshot()
    elapsed = end["clock"] - start["clock"]
    hz = os.sysconf("SC_CLK_TCK")
    result = {
        "at": datetime.now(UTC).isoformat(),
        "label": label,
        "seconds": round(elapsed, 2),
        "cpuPercent": round((end["cpuUsec"] - start["cpuUsec"]) / elapsed / 10000, 2),
        "workingSetMiB": round(end["workingSetMiB"], 2),
    }
    for kind in ("processes", "threads"):
        rows = []
        for key, current in end[kind].items():
            previous = start[kind].get(key)
            if previous and previous["started"] == current["started"]:
                cpu = (current["ticks"] - previous["ticks"]) / hz / elapsed * 100
                rows.append(
                    {
                        "id": key,
                        "name": current["name"],
                        "process": current.get("process", current["name"]),
                        "cpuPercent": round(cpu, 2),
                    }
                )
        result[kind] = sorted(rows, key=lambda row: row["cpuPercent"], reverse=True)[:12]
        if kind == "threads":
            groups = {}
            for row in rows:
                group = groups.setdefault(row["name"], {"threads": 0, "cpuPercent": 0.0})
                group["threads"] += 1
                group["cpuPercent"] += row["cpuPercent"]
            result["threadGroups"] = {
                name: {"threads": group["threads"], "cpuPercent": round(group["cpuPercent"], 2)}
                for name, group in groups.items()
            }
    return result


if __name__ == "__main__":
    # Fields 14/15 are CPU ticks; field 22 identifies a recycled PID/TID.
    fixture = "17 (name with ) spaces) R " + " ".join(str(i) for i in range(4, 53))
    assert counters(fixture) == (29, 22)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    assert 1 <= args.seconds <= 60
    print(json.dumps(profile(args.seconds, args.label)), flush=True)
