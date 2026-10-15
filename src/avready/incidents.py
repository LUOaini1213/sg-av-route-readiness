"""Collect the traffic-incident records available for the study areas (local step).

Singapore publishes no historical, geolocated crash dataset. LTA DataMall's Traffic
Incidents API returns only the incidents current at the moment of the call. The only
history available here is what has been polled and kept:

* the public `data-collect` branch of LUOaini1213/sg-bus-network-monitor, which stores
  each poll as `data/raw/incidents/YYYY-MM-DD/inc_*.jsonl.gz` (read over HTTPS, the
  repository is not touched);
* the one documented incident involving an autonomous shuttle in Punggol (config
  `documented_events`, geocoded to the block named in the reports).

Output (committed): `data/derived/incidents.csv` (incidents inside the study areas) and
`data/derived/incident_polls.csv` (every poll read, with its count island-wide).

    python -m avready.incidents
"""
from __future__ import annotations

import csv
import gzip
import json
import urllib.request

from .common import DATA, routes_config
from .network import anchors

REPO = "LUOaini1213/sg-bus-network-monitor"
BRANCH = "data-collect"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "sg-av-route-readiness"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def poll_files() -> list[str]:
    tree = json.loads(_get(f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"))
    return sorted(t["path"] for t in tree["tree"]
                  if t["path"].startswith("data/raw/incidents/") and t["path"].endswith(".jsonl.gz"))


def in_aoi(lat: float, lon: float, aois: dict) -> str | None:
    for a, (s, w, n, e) in aois.items():
        if s <= lat <= n and w <= lon <= e:
            return a
    return None


def main():
    cfg = routes_config()
    aois = cfg["aois"]
    rows, polls, seen = [], [], set()
    for path in poll_files():
        raw = gzip.decompress(_get(f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{path}"))
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            vals = rec.get("value", [])
            polls.append([path, rec.get("polled_at", ""), len(vals)])
            for v in vals:
                a = in_aoi(v["Latitude"], v["Longitude"], aois)
                key = (v["Type"], v["Message"])
                if a and key not in seen:
                    seen.add(key)
                    rows.append(["datamall-poll", rec.get("polled_at", ""), a, v["Type"], v["Latitude"],
                                 v["Longitude"], v["Message"]])
    anc = anchors()
    for ev in cfg.get("documented_events", []):
        lat, lon = anc[ev["anchor"]]
        rows.append(["documented", ev["date"], in_aoi(lat, lon, aois), "AV shuttle incident", lat, lon,
                     ev["id"] + ": " + " ".join(ev["summary"].split())])
    with open(DATA / "derived" / "incidents.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["source", "time", "aoi", "type", "lat", "lon", "message"])
        w.writerows(rows)
    with open(DATA / "derived" / "incident_polls.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["file", "polled_at", "incidents_islandwide"])
        w.writerows(polls)
    print("polls", len(polls), "incidents in study areas", len(rows))


if __name__ == "__main__":
    main()
