"""Speed-band variability on the links along each route (local step; needs raw snapshots).

Input: LTA DataMall Traffic Speed Bands v4 snapshots (`sb_YYYYMMDD_HHMM.csv.gz`, SGT in
the name; columns LinkID, SpeedBand, MinimumSpeed, MaximumSpeed) from the candidate's
sg-bus-network-monitor collector (laptop archive and the public `data-collect` branch),
plus the link geometry file. Snapshots are read, never modified.

Output (committed): `data/derived/speedband_stats.csv` for links within 40 m of a route,
and `data/derived/speedband_manifest.csv` listing every snapshot used.

    python -m avready.speedbands --links LINKS.csv[.gz] SNAPSHOT_DIR [SNAPSHOT_DIR ...]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
from datetime import datetime, time
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Point

from .common import DATA, read_json_gz, scoring_config, to_xy

NAME = re.compile(r"sb_(\d{8})_(\d{4})\.csv(\.gz)?$")
# Singapore public holidays from 2026-09-01 to year end (MOM): Deepavali falls on Sunday
# 8 Nov 2026 with Monday 9 Nov off in lieu, and Christmas on 25 Dec. Earlier dates are
# rejected below rather than silently treated as working days.
SG_PUBLIC_HOLIDAYS = {"2026-11-08", "2026-11-09", "2026-12-25"}
HOLIDAY_TABLE_FROM = "2026-09-01"


def in_window(ts: datetime, win: dict) -> bool:
    day = ts.strftime("%Y-%m-%d")
    if day < HOLIDAY_TABLE_FROM:
        raise ValueError(f"no public-holiday table for {day}")
    if day in SG_PUBLIC_HOLIDAYS:
        return False
    h0, m0 = map(int, win["start"].split(":"))
    h1, m1 = map(int, win["end"].split(":"))
    return ts.weekday() in win["days"] and time(h0, m0) <= ts.time() <= time(h1, m1)


def band_speed(df: pd.DataFrame, band8: float) -> pd.Series:
    """Midpoint of each band's published range; band 8's open top (999) uses band8."""
    mid = (df["MinimumSpeed"] + df["MaximumSpeed"]) / 2
    return mid.where(df["SpeedBand"] != 8, band8)


def link_stats(speeds: dict[int, list[float]], slow_max_kmh: float) -> dict[int, dict]:
    out = {}
    for lid, v in speeds.items():
        a = np.asarray(v, float)
        if len(a) == 0:
            continue
        mean = float(a.mean())
        std = float(a.std(ddof=0))
        out[lid] = {"n_obs": len(a), "mean_kmh": round(mean, 2), "std_kmh": round(std, 2),
                    "cv": round(std / mean, 4) if mean > 0 else 0.0,
                    "p_slow": round(float((a < slow_max_kmh).mean()), 4)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", required=True)
    ap.add_argument("dirs", nargs="+")
    args = ap.parse_args(argv)
    cfg = scoring_config()["speedband"]
    slow_kmh = 10.0 * cfg["slow_band_max"]  # band b covers [10(b-1), 10b-1] km/h

    routes = read_json_gz(DATA / "derived" / "routes.json.gz")
    lines = [LineString([to_xy(a, b) for a, b in r["latlon"]]) for r in routes["routes"]]
    tree = shapely.STRtree(lines)

    links = pd.read_csv(args.links)
    keep = {}
    for r in links.itertuples(index=False):
        a, b = to_xy(r.StartLat, r.StartLon), to_xy(r.EndLat, r.EndLon)
        mid = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if len(tree.query(mid, predicate="dwithin", distance=40.0)):
            keep[int(r.LinkID)] = r
    print("candidate links", len(keep))

    files = sorted({p for d in args.dirs for p in Path(d).rglob("sb_*.csv*") if NAME.search(p.name)},
                   key=lambda p: p.name)
    speeds = {lid: [] for lid in keep}
    manifest = []
    seen_names = set()
    for p in files:
        m = NAME.search(p.name)
        ts = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M")
        dup = p.name in seen_names
        seen_names.add(p.name)
        use = in_window(ts, cfg["operating_window"]) and not dup
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest.append([p.name, ts.strftime("%Y-%m-%d %H:%M"), ts.strftime("%a"), int(use), int(dup), sha])
        if not use:
            continue
        df = pd.read_csv(p)
        df = df[df["LinkID"].isin(keep.keys())]
        df = df.assign(kmh=band_speed(df, cfg["band8_speed_kmh"]))
        for lid, v in zip(df["LinkID"], df["kmh"]):
            if not np.isnan(v):
                speeds[int(lid)].append(float(v))
    stats = link_stats(speeds, slow_kmh)
    used = sum(r[3] for r in manifest)
    print("snapshots", len(manifest), "in operating window", used)

    with open(DATA / "derived" / "speedband_stats.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["LinkID", "RoadName", "RoadCategory", "start_lat", "start_lon", "end_lat", "end_lon",
                    "n_obs", "mean_kmh", "std_kmh", "cv", "p_slow"])
        for lid in sorted(stats):
            r, s = keep[lid], stats[lid]
            w.writerow([lid, r.RoadName, r.RoadCategory, r.StartLat, r.StartLon, r.EndLat, r.EndLon,
                        s["n_obs"], s["mean_kmh"], s["std_kmh"], s["cv"], s["p_slow"]])
    with open(DATA / "derived" / "speedband_manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["file", "sgt", "weekday", "in_operating_window", "duplicate", "sha256"])
        w.writerows(manifest)


if __name__ == "__main__":
    main()
