"""Clip an OpenStreetMap extract of Singapore to the study areas.

Input: an `.osm.gz` (OSM XML) extract, e.g. BBBike's Singapore extract
(https://download.bbbike.org/osm/bbbike/Singapore/). Overpass was tried first and
returned 5xx on every public endpoint on 2026-10-15, so the pipeline reads a file.

Output: `data/osm/<aoi>.json.gz`, one per AOI, holding the drivable-road ways, the
nodes they use, point features (signals, crossings, bus stops ...) and schools.
The output is committed so the rest of the pipeline and CI run offline.

    python -m avready.fetch_osm path/to/Singapore.osm.gz --source-url URL --last-modified "..."
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

from .common import DATA, routes_config, write_json_gz

WAY_TAGS = {
    "highway", "oneway", "lanes", "lanes:forward", "lanes:backward", "maxspeed", "junction",
    "name", "service", "access", "motor_vehicle", "ref", "bridge", "tunnel", "footway",
}
POINT_HIGHWAY = {"traffic_signals", "crossing", "bus_stop", "give_way", "stop", "mini_roundabout"}
POINT_TAGS = {"highway", "crossing", "crossing_ref", "traffic_signals", "name", "traffic_calming",
              "amenity", "railway", "public_transport", "bus"}
SCHOOL_AMENITY = {"school", "kindergarten", "childcare", "college"}
MARGIN = 0.004  # degrees (~440 m) so routes near an AOI edge still see nearby features


def _in(b, lat, lon):
    s, w, n, e = b
    return s - MARGIN <= lat <= n + MARGIN and w - MARGIN <= lon <= e + MARGIN


def clip(osm_path: Path, aois: dict[str, list[float]]) -> dict[str, dict]:
    coords: dict[int, tuple[float, float]] = {}
    node_aois: dict[int, list[str]] = {}
    points = {a: [] for a in aois}
    ways = {a: [] for a in aois}
    schools = {a: [] for a in aois}

    opener = gzip.open if str(osm_path).endswith(".gz") else open
    with opener(osm_path, "rb") as f:
        for _, el in ET.iterparse(f, events=("end",)):
            tag = el.tag
            if tag == "node":
                lat, lon = float(el.get("lat")), float(el.get("lon"))
                hit = [a for a, b in aois.items() if _in(b, lat, lon)]
                if hit:
                    nid = int(el.get("id"))
                    coords[nid] = (round(lat, 7), round(lon, 7))
                    node_aois[nid] = hit
                    tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
                    keep = {k: v for k, v in tags.items() if k in POINT_TAGS}
                    is_point = (tags.get("highway") in POINT_HIGHWAY
                                or tags.get("crossing") is not None
                                or tags.get("traffic_calming") is not None)
                    for a in hit:
                        if is_point:
                            points[a].append({"id": nid, "lat": coords[nid][0], "lon": coords[nid][1], "tags": keep})
                        if tags.get("amenity") in SCHOOL_AMENITY:
                            schools[a].append({"id": f"n{nid}", "lat": coords[nid][0], "lon": coords[nid][1],
                                               "amenity": tags["amenity"], "name": tags.get("name", "")})
                el.clear()
            elif tag == "way":
                refs = [int(nd.get("ref")) for nd in el.findall("nd")]
                tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
                present = [r for r in refs if r in coords]
                if present:
                    hit = set()
                    for r in present:
                        hit.update(node_aois[r])
                    if "highway" in tags:
                        keep = {k: v for k, v in tags.items() if k in WAY_TAGS}
                        for a in hit:
                            ways[a].append({"id": int(el.get("id")), "nodes": refs, "tags": keep})
                    if tags.get("amenity") in SCHOOL_AMENITY:
                        lat = sum(coords[r][0] for r in present) / len(present)
                        lon = sum(coords[r][1] for r in present) / len(present)
                        for a in hit:
                            schools[a].append({"id": f"w{el.get('id')}", "lat": round(lat, 7), "lon": round(lon, 7),
                                               "amenity": tags["amenity"], "name": tags.get("name", "")})
                el.clear()
            elif tag == "relation":
                el.clear()

    out = {}
    for a in aois:
        used = {r for w in ways[a] for r in w["nodes"] if r in coords}
        # Ways crossing the clip edge keep only their in-area nodes.
        for w in ways[a]:
            w["nodes"] = [r for r in w["nodes"] if r in coords]
        ways_a = sorted([w for w in ways[a] if len(w["nodes"]) >= 2], key=lambda w: w["id"])
        out[a] = {
            "bbox": aois[a],
            "nodes": {str(n): coords[n] for n in sorted(used)},
            "ways": ways_a,
            "points": sorted(points[a], key=lambda p: p["id"]),
            "schools": sorted(schools[a], key=lambda s: s["id"]),
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("osm")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--last-modified", required=True)
    args = ap.parse_args(argv)
    p = Path(args.osm)
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    clipped = clip(p, routes_config()["aois"])
    for a, obj in clipped.items():
        obj["meta"] = {"source_url": args.source_url, "last_modified": args.last_modified,
                       "sha256": sha, "licence": "ODbL 1.0, (c) OpenStreetMap contributors"}
        write_json_gz(DATA / "osm" / f"{a}.json.gz", obj)
        print(a, "ways", len(obj["ways"]), "nodes", len(obj["nodes"]), "points", len(obj["points"]),
              "schools", len(obj["schools"]))


if __name__ == "__main__":
    main()
