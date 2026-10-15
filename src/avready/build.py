"""Offline pipeline: committed inputs -> route geometry, segment profiles, risk register,
ODD checklists, map data. Deterministic; CI runs it and checks the outputs are unchanged.

    python -m avready.build            # everything
    python -m avready.build routes     # only the route reconstruction (needed by speedbands)
"""
from __future__ import annotations

import csv
import json
import math
import sys

import numpy as np
from scipy.spatial import cKDTree

from . import network, packs, profile, risk
from .common import DATA, OUTPUTS, RESULTS, read_json_gz, routes_config, scoring_config, to_latlon, write_json_gz


def _r(x, nd=1):
    return None if x is None else round(float(x), nd)


def trace_agreement(xy_path, trace) -> dict:
    pts = []
    for (x0, y0), (x1, y1) in zip(xy_path[:-1], xy_path[1:]):
        n = max(2, int(math.dist((x0, y0), (x1, y1)) // 5) + 1)
        pts += [(x0 + (x1 - x0) * k / (n - 1), y0 + (y1 - y0) * k / (n - 1)) for k in range(n)]
    P, T = np.asarray(pts), np.asarray(trace)
    dp, _ = cKDTree(T).query(P)
    dt, _ = cKDTree(P).query(T)
    return {"path_share_within_30m_of_map": round(float((dp < 30).mean()), 3),
            "map_share_within_30m_of_path": round(float((dt < 30).mean()), 3)}


def stage_routes() -> dict:
    cfg = routes_config()
    nets, out = {}, []
    for r in cfg["routes"]:
        key = (r["aoi"], r["kind"])
        if key not in nets:
            nets[key] = network.build(*key)
        net = nets[key]
        rec = network.reconstruct(r, net)
        # Baseline: shortest drivable path through the announced stops only (no map trace,
        # no shape points), to show how far the published routes are from shortest paths.
        stops_only = {**r, "stops": [s for s in r.get("stops", []) if not s.get("shape_point")]}
        short = network.reconstruct(stops_only, net, use_trace=False)
        xy = [net.xy[n] for n in rec["path"]]
        item = {
            "id": r["id"], "name": r["name"], "kind": r["kind"], "aoi": r["aoi"], "method": rec["method"],
            "path": rec["path"], "latlon": [list(map(lambda v: round(v, 7), to_latlon(*p))) for p in xy],
            "stops": [{"name": s["name"], "lat": round(s["lat"], 7), "lon": round(s["lon"], 7),
                       "snap_m": s["snap_m"], "edge": s["edge"], "shape_point": bool(s.get("shape_point"))}
                      for s in rec["stops"]],
            "length_m": round(rec["length_m"], 1),
            "shortest_length_m": round(short["length_m"], 1),
            "official_length_km": r.get("official_length_km"),
        }
        item["length_gap_pct"] = round(100 * (item["length_m"] / 1000 / r["official_length_km"] - 1), 1)
        trace = network.load_trace(r["id"])
        item["map_agreement"] = trace_agreement(xy, trace) if trace else None
        out.append(item)
        print(r["id"], item["method"], item["length_m"], "official", r["official_length_km"], "km",
              item["map_agreement"])
    obj = {"routes": out}
    write_json_gz(DATA / "derived" / "routes.json.gz", obj)
    return obj


def stage_profile(routes: dict) -> None:
    cfg_r = {r["id"]: r for r in routes_config()["routes"]}
    sc = scoring_config()
    nets, layers_cache, junc_cache = {}, {}, {}
    all_segments, register, summaries, turns_out = [], [], [], []
    seg_features_by_route = {}
    for item in routes["routes"]:
        key = (item["aoi"], item["kind"])
        if key not in nets:
            nets[key] = network.build(*key)
        net = nets[key]
        if item["aoi"] not in layers_cache:
            layers_cache[item["aoi"]] = profile.load_layers(item["aoi"], net.raw)
        if key not in junc_cache:
            junc_cache[key] = profile.junction_nodes(net)
        layers = layers_cache[item["aoi"]]
        edges = profile.path_edges(item["path"], net)
        segs = profile.cut_segments(edges, sc["segment_length_m"])
        stop_nodes = {n for s in item["stops"] if not s["shape_point"] for n in s["edge"]}
        turns = profile.route_turns(item["path"], net, layers, sc, junc_cache[key])
        for t in turns:
            lat, lon = to_latlon(*t["xy"])
            turns_out.append({"route_id": item["id"], "path_index": t["i"], "lat": round(lat, 6),
                              "lon": round(lon, 6), "angle_deg": t["angle"],
                              "turn": t["kind"], "signalised": int(t["signalised"]), "signal_source": t["signal_source"],
                              "service_road_access": int(t["access"])})
        start, idx, rows = 0.0, 0, []
        for k, seg in enumerate(segs):
            n_edges = len(seg)
            seg_turns = [t for t in turns if idx < t["i"] <= idx + n_edges]
            f = profile.segment_features(seg, net, layers, sc, stop_nodes, seg_turns)
            idx += n_edges
            mid = to_latlon(*f.pop("_mid_xy"))
            xy = f.pop("_xy")
            f["mid_lat_lon"] = f"{mid[0]:.6f},{mid[1]:.6f}"
            row = {"route_id": item["id"], "segment_id": f'{item["id"]}-S{k + 1:02d}',
                   "start_m": round(start, 1), "end_m": round(start + f["length_m"], 1), **f}
            start += f["length_m"]
            row["_latlon"] = [[round(a, 6), round(b, 6)] for a, b in (to_latlon(*p) for p in xy)]
            rows.append(row)
        scores = risk.segment_scores(rows, sc)
        for row, s in zip(rows, scores):
            row["risk_score"] = int(s)
        # The deployment pack (register, ODD checklist) is for the shuttle routes only; the
        # bus services are profiled for comparison.
        reg = risk.register_rows(cfg_r[item["id"]], rows, sc)
        if item["kind"] == "shuttle":
            register += reg
        seg_features_by_route[item["id"]] = rows
        all_segments += rows
        summaries.append(packs.route_summary(item, cfg_r[item["id"]], rows, reg, turns))

    seg_fields = [k for k in all_segments[0] if not k.startswith("_")]
    OUTPUTS.mkdir(exist_ok=True)
    with open(OUTPUTS / "segments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=seg_fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(all_segments)
    with open(OUTPUTS / "risk_register.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(register[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(register, key=lambda r: (r["route_id"], -r["score"], r["segment_id"], r["hazard"])))
    with open(OUTPUTS / "turns.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(turns_out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(turns_out)
    with open(OUTPUTS / "route_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summaries[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(summaries)

    RESULTS.mkdir(exist_ok=True)
    shuttle_segs = [s for s in all_segments if s["route_id"].startswith("PG-")]
    sens = {"all_routes": risk.sensitivity(all_segments, sc), "punggol_shuttles": risk.sensitivity(shuttle_segs, sc)}
    (RESULTS / "sensitivity.json").write_text(json.dumps(sens, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validation = {"routes": {r["id"]: {k: r[k] for k in ("method", "length_m", "shortest_length_m",
                                                         "official_length_km", "length_gap_pct", "map_agreement")}
                             for r in routes["routes"]},
                  "stop_snap_m": {r["id"]: [s["snap_m"] for s in r["stops"] if not s["shape_point"]]
                                  for r in routes["routes"]},
                  "osm_vs_lta": packs.osm_vs_lta(all_segments)}
    (RESULTS / "validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    packs.write_packs(routes, cfg_r, seg_features_by_route, register, summaries, turns_out, sens)


def main(argv):
    stage = argv[1] if len(argv) > 1 else "all"
    if stage in ("routes", "all"):
        routes = stage_routes()
    else:
        routes = read_json_gz(DATA / "derived" / "routes.json.gz")
    if stage in ("profile", "all"):
        stage_profile(routes)


if __name__ == "__main__":
    main(sys.argv)
