"""Geocode the stop anchors in config/routes.yaml with OneMap (Singapore Land Authority).

Uses OneMap's public search endpoint, which needs no token. Every query must return a
result whose name or address contains the query's block number (or name); otherwise the
script stops, so a wrong match cannot slip in silently. Results are cached in
`data/derived/anchors.csv` and committed.

    python -m avready.geocode
"""
from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request

from .common import DATA, routes_config

URL = "https://www.onemap.gov.sg/api/common/elastic/search?"


def search(q: str) -> list[dict]:
    for attempt in range(6):
        try:
            u = URL + urllib.parse.urlencode({"searchVal": q, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1})
            req = urllib.request.Request(u, headers={"User-Agent": "sg-av-route-readiness"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r).get("results", [])
        except Exception:  # rate limited: OneMap returns an empty body
            time.sleep(2 + 2 * attempt)
    raise RuntimeError(f"OneMap search failed for {q!r}")


def pick(q: str, results: list[dict]) -> dict:
    first = q.split()[0]
    road = " ".join(q.split()[1:])
    if first[0].isdigit():
        for r in results:
            if r["BLK_NO"] == first and road in r["ROAD_NAME"]:
                return r
    else:
        for test in (lambda r: q in (r["SEARCHVAL"], r["BUILDING"]),
                     lambda r: r["SEARCHVAL"].startswith(q) or r["BUILDING"].startswith(q)):
            for r in results:
                if test(r):
                    return r
    raise RuntimeError(f"no result for {q!r} matches the block/name: {[r['SEARCHVAL'] for r in results[:5]]}")


def main():
    cfg = routes_config()
    queries = []
    for r in cfg["routes"]:
        for s in r.get("stops", []):
            queries += s["anchors"]
    queries += [e["anchor"] for e in cfg.get("documented_events", [])]
    queries = sorted(set(queries))
    rows = []
    for q in queries:
        hit = pick(q, search(q))
        rows.append([q, hit["SEARCHVAL"], hit["BLK_NO"], hit["ROAD_NAME"], hit["POSTAL"], hit["LATITUDE"], hit["LONGITUDE"]])
        print(q, "->", hit["SEARCHVAL"], hit["POSTAL"])
        time.sleep(1.2)
    (DATA / "derived").mkdir(parents=True, exist_ok=True)
    with open(DATA / "derived" / "anchors.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["query", "onemap_searchval", "blk_no", "road_name", "postal", "lat", "lon"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
