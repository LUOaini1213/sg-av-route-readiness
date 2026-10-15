"""After `python -m avready.build`, check the rebuilt outputs against the committed ones.

Text outputs (CSV, Markdown, most JSON) must be byte-identical. Two files hold raw
coordinates converted through PROJ, whose last decimal can differ between platforms
(Windows build machine, Linux CI); those are compared numerically with a tolerance of
1e-6 degrees (about 0.1 m) instead.

    python tools/check_rebuild.py
"""
from __future__ import annotations

import gzip
import json
import subprocess
import sys

TOLERANT = {"data/derived/routes.json.gz", "docs/data/segments.geojson"}
TOL = 1e-6


def committed(path: str) -> bytes:
    return subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True, check=True).stdout


def load(path: str, raw: bytes):
    if path.endswith(".gz"):
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def close(a, b, where="") -> list[str]:
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) <= TOL:
            return []
        return [f"{where}: {a!r} != {b!r}"]
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return [f"{where}: keys differ"]
        return [m for k in a for m in close(a[k], b[k], f"{where}/{k}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{where}: length {len(a)} != {len(b)}"]
        return [m for i, (x, y) in enumerate(zip(a, b)) for m in close(x, y, f"{where}[{i}]")]
    return [] if a == b else [f"{where}: {a!r} != {b!r}"]


def main() -> int:
    changed = subprocess.run(["git", "diff", "--name-only"], capture_output=True, text=True, check=True).stdout.split()
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True,
                               check=True).stdout.split()
    problems = [f"new file not committed: {p}" for p in untracked]
    for path in changed:
        if path not in TOLERANT:
            problems.append(f"changed: {path}")
            continue
        with open(path, "rb") as f:
            diffs = close(load(path, committed(path)), load(path, f.read()), path)
        problems += diffs[:5]
        if not diffs:
            print(f"{path}: differs only within {TOL} (float rounding)")
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
