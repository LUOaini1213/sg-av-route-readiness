"""Fetch LTA DataMall inputs and clip them to the study areas.

Needs a DataMall AccountKey in the environment variable LTA_KEY. The key is never
written to disk or printed. Outputs are committed so CI never needs a key.

    python -m avready.fetch_lta geo        # GeospatialWholeIsland layers -> data/lta/geo_<aoi>.json.gz
    python -m avready.fetch_lta bus PATH   # BusRoutes/BusStops JSON dir -> data/lta/bus_routes.csv, bus_stops.csv

Layers used (DataMall "Geospatial Whole Island" dataset): SchoolZone, SilverZone,
TrafficLight, RoadCrossing, RoadHump. The shapefiles are in SVY21 (EPSG:3414).
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

from .common import DATA, routes_config, to_latlon, write_json_gz

LAYERS = ["SchoolZone", "SilverZone", "TrafficLight", "RoadCrossing", "RoadHump"]
API = "https://datamall2.mytransport.sg/ltaodataservice/GeospatialWholeIsland?ID={}"


def _get(url: str, key: str | None = None) -> bytes:
    headers = {"accept": "application/json", "User-Agent": "sg-av-route-readiness"}
    if key:
        headers["AccountKey"] = key
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r:
        return r.read()


def _shapes(zbytes: bytes):
    import shapefile  # pyshp; only needed for this fetch step

    z = zipfile.ZipFile(io.BytesIO(zbytes))
    shp = [n for n in z.namelist() if n.lower().endswith(".shp")]
    if len(shp) != 1:
        raise RuntimeError(f"expected one .shp, got {shp}")
    base = shp[0][:-4]
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")),
                         shx=io.BytesIO(z.read(base + ".shx")))
    fields = [f[0] for f in r.fields[1:]]
    for sr in r.iterShapeRecords():
        yield sr.shape, dict(zip(fields, sr.record))


def fetch_geo():
    key = os.environ.get("LTA_KEY")
    if not key:
        sys.exit("set LTA_KEY")
    aois = routes_config()["aois"]
    out = {a: {"layers": {}} for a in aois}
    for layer in LAYERS:
        link = json.loads(_get(API.format(layer), key))["value"][0]["Link"]
        zb = _get(link)  # pre-signed S3 URL; not stored anywhere
        n_all = 0
        per = {a: [] for a in aois}
        for shape, rec in _shapes(zb):
            n_all += 1
            pts = [to_latlon(x, y) for x, y in shape.points]
            if not pts:
                continue
            lats = [p[0] for p in pts]
            lons = [p[1] for p in pts]
            parts = (list(shape.parts) or [0]) + [len(pts)]
            rings = [[[round(lat, 7), round(lon, 7)] for lat, lon in pts[parts[i]:parts[i + 1]]]
                     for i in range(len(parts) - 1)]
            rec = {k: (v if isinstance(v, (int, float, str)) or v is None else str(v)) for k, v in rec.items()}
            for a, (s, w, n, e) in aois.items():
                if max(lats) >= s and min(lats) <= n and max(lons) >= w and min(lons) <= e:
                    per[a].append({"type": shape.shapeTypeName, "parts": rings, "attrs": rec})
        for a in aois:
            out[a]["layers"][layer] = {"n_island": n_all, "features": per[a]}
        print(layer, "island", n_all, {a: len(per[a]) for a in aois})
    for a in aois:
        out[a]["meta"] = {"source": "LTA DataMall GeospatialWholeIsland", "crs_source": "EPSG:3414",
                          "licence": "Singapore Open Data Licence v1.0", "retrieved": os.environ.get("RETRIEVED", "")}
        write_json_gz(DATA / "lta" / f"geo_{a}.json.gz", out[a])


def extract_bus(src_dir: str):
    src = Path(src_dir)
    routes_file = sorted(src.glob("BusRoutes_*.json"))[-1]
    stops_file = sorted(src.glob("BusStops_*.json"))[-1]
    rr = json.loads(routes_file.read_text(encoding="utf-8"))
    rr = rr["value"] if isinstance(rr, dict) else rr
    ss = json.loads(stops_file.read_text(encoding="utf-8"))
    ss = ss["value"] if isinstance(ss, dict) else ss
    services = {r["datamall_service"] for r in routes_config()["routes"] if r.get("datamall_service")}
    rows = sorted([r for r in rr if r["ServiceNo"] in services], key=lambda r: (r["ServiceNo"], r["Direction"], r["StopSequence"]))
    (DATA / "lta").mkdir(parents=True, exist_ok=True)
    with open(DATA / "lta" / "bus_routes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["ServiceNo", "Direction", "StopSequence", "BusStopCode", "Distance", "source_file"])
        for r in rows:
            w.writerow([r["ServiceNo"], r["Direction"], r["StopSequence"], r["BusStopCode"], r["Distance"], routes_file.name])
    aois = routes_config()["aois"]
    with open(DATA / "lta" / "bus_stops.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["BusStopCode", "RoadName", "Description", "Latitude", "Longitude", "source_file"])
        for s in sorted(ss, key=lambda s: s["BusStopCode"]):
            if any(b[0] - 0.004 <= s["Latitude"] <= b[2] + 0.004 and b[1] - 0.004 <= s["Longitude"] <= b[3] + 0.004
                   for b in aois.values()):
                w.writerow([s["BusStopCode"], s["RoadName"], s["Description"], s["Latitude"], s["Longitude"], stops_file.name])


if __name__ == "__main__":
    if sys.argv[1] == "geo":
        fetch_geo()
    elif sys.argv[1] == "bus":
        extract_bus(sys.argv[2])
    else:
        sys.exit(__doc__)
