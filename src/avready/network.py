"""Road graph from the clipped OSM data and route reconstruction.

Route geometry is not published as data. It is rebuilt here as the shortest drivable
path through the announced stops, in order, closing the loop. The reconstruction is
checked against the published round-trip length (see `validation` in the outputs), and
the README reports the gap. Where the gap is large, the reconstruction is not the
operated path and every per-segment result should be read with that in mind.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from .common import DATA, read_json_gz, to_latlon, to_xy

DRIVABLE = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary",
    "secondary_link", "tertiary", "tertiary_link", "unclassified", "residential", "service",
    "living_street", "busway",
}
EXCLUDED_SERVICE = {"parking_aisle", "driveway", "drive-through", "emergency_access"}
# Shuttles do not use expressways. Buses keep them (service 400 runs on Marina Coastal Drive).
SHUTTLE_FORBIDDEN = {"motorway", "motorway_link", "trunk", "trunk_link"}
# Service roads are allowed (pick-up points sit on them) but cost more, so a path only uses
# one where it saves real distance. The 2026-01-17 incident happened on a service road that
# was not on the assigned route, which is why the penalty exists at all.
SERVICE_PENALTY = 3.0


@dataclass
class Network:
    aoi: str
    graph: nx.DiGraph
    xy: dict[int, tuple[float, float]]
    raw: dict = field(repr=False)


def load_osm(aoi: str) -> dict:
    return read_json_gz(DATA / "osm" / f"{aoi}.json.gz")


def _oneway(tags: dict) -> int:
    v = tags.get("oneway", "")
    if v in ("yes", "true", "1"):
        return 1
    if v == "-1":
        return -1
    if tags.get("junction") in ("roundabout", "circular") or tags.get("highway") in ("motorway", "motorway_link"):
        return 1
    return 0


def build(aoi: str, kind: str) -> Network:
    raw = load_osm(aoi)
    coords = {int(k): v for k, v in raw["nodes"].items()}
    xy = {n: to_xy(*coords[n]) for n in coords}
    g = nx.DiGraph()
    for w in raw["ways"]:
        t = w["tags"]
        hw = t.get("highway")
        if hw not in DRIVABLE or t.get("service") in EXCLUDED_SERVICE:
            continue
        if t.get("access") in ("no", "private") or t.get("motor_vehicle") in ("no", "private"):
            continue
        if kind == "shuttle" and hw in SHUTTLE_FORBIDDEN:
            continue
        ow = _oneway(t)
        pen = SERVICE_PENALTY if hw == "service" else 1.0
        nodes = w["nodes"]
        for a, b in zip(nodes[:-1], nodes[1:]):
            (x0, y0), (x1, y1) = xy[a], xy[b]
            length = math.hypot(x1 - x0, y1 - y0)
            attrs = dict(length=length, weight=length * pen, way=w["id"], highway=hw)
            if ow >= 0:
                g.add_edge(a, b, **attrs)
            if ow <= 0:
                g.add_edge(b, a, **attrs)
    # Keep the largest strongly connected component so every stop pair is routable.
    comp = max(nx.strongly_connected_components(g), key=len)
    g = g.subgraph(comp).copy()
    return Network(aoi=aoi, graph=g, xy=xy, raw=raw)


def snap(net: Network, lat: float, lon: float, avoid: set[str] | None = None) -> tuple[int, float]:
    """Nearest graph node to a point; returns (node, distance_m)."""
    x, y = to_xy(lat, lon)
    best, bd = None, float("inf")
    for n in net.graph.nodes:
        if avoid:
            hws = {net.graph.edges[e]["highway"] for e in net.graph.out_edges(n)}
            if hws and hws <= avoid:
                continue
        nx_, ny_ = net.xy[n]
        d = (nx_ - x) ** 2 + (ny_ - y) ** 2
        if d < bd:
            best, bd = n, d
    return best, math.sqrt(bd)


def _project(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    qx, qy = ax + t * dx, ay + t * dy
    return math.hypot(px - qx, py - qy), t


def snap_kerbside(net: Network, lat: float, lon: float, avoid: set[str] | None = None,
                  radius: float = 150.0, on_trace: set | None = None) -> tuple[tuple[int, int], float]:
    """Nearest directed edge that has the point on its LEFT (Singapore drives on the left,
    so a vehicle stops with the kerb, and the stop, on its left). Returns ((u, v), metres).
    Falls back to the nearest edge of either side if no left-side edge is within radius."""
    px, py = to_xy(lat, lon)
    best_left, best_any = (None, float("inf"), None), (None, float("inf"), None)
    for u, v, d in net.graph.edges(data=True):
        if avoid and d["highway"] in avoid:
            continue
        (ax, ay), (bx, by) = net.xy[u], net.xy[v]
        dist, _ = _project(px, py, ax, ay, bx, by)
        if dist > radius:
            continue
        cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
        # A stop sits on the published route line, so an edge on the traced line is
        # preferred over a nearer one off it (cost = distance + 100 m if off the line).
        cost = dist + (100.0 if on_trace is not None and (u, v) not in on_trace else 0.0)
        if cost < best_any[1]:
            best_any = ((u, v), cost, dist)
        if cross > 0 and cost < best_left[1]:
            best_left = ((u, v), cost, dist)
    pick = best_left if best_left[0] is not None else best_any
    if pick[0] is None:
        raise RuntimeError(f"no drivable edge within {radius} m of {lat},{lon}")
    return pick[0], pick[2]


def anchors() -> dict[str, tuple[float, float]]:
    with open(DATA / "derived" / "anchors.csv", encoding="utf-8") as f:
        return {r["query"]: (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)}


def bus_stops_for(service: str) -> list[dict]:
    with open(DATA / "lta" / "bus_stops.csv", encoding="utf-8") as f:
        stops = {r["BusStopCode"]: r for r in csv.DictReader(f)}
    with open(DATA / "lta" / "bus_routes.csv", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["ServiceNo"] == service and r["Direction"] == "1"]
    rows.sort(key=lambda r: int(r["StopSequence"]))
    out = []
    for r in rows:
        s = stops[r["BusStopCode"]]
        out.append({"name": f'{s["BusStopCode"]} {s["Description"]}', "lat": float(s["Latitude"]),
                    "lon": float(s["Longitude"]), "datamall_km": float(r["Distance"])})
    # A loop service lists its terminal twice; the loop closure re-adds it.
    if len(out) > 1 and out[0]["name"] == out[-1]["name"]:
        out = out[:-1]
    return out


def route_stops(route: dict) -> list[dict]:
    if route.get("datamall_service"):
        return bus_stops_for(route["datamall_service"])
    a = anchors()
    stops = []
    for s in route["stops"]:
        if s.get("shape_point"):
            lat, lon = to_latlon(*s["svy21"])
            stops.append({"name": s["name"], "lat": lat, "lon": lon, "shape_point": True})
            continue
        pts = [a[q] for q in s["anchors"]]
        stops.append({"name": s["name"], "lat": sum(p[0] for p in pts) / len(pts),
                      "lon": sum(p[1] for p in pts) / len(pts)})
    return stops


TRACE_RADIUS = 25.0      # an edge "follows the published map" if all of it is this close to the trace
OFF_TRACE_PENALTY = 5.0  # cost multiplier for edges away from the traced map line
SHAPE_RADIUS = 40.0      # search radius for the edge a shape point is placed on
TRACE_RAMP = 60.0        # metres over which the penalty ramps from 1x to OFF_TRACE_PENALTY x


def load_trace(route_id: str):
    p = DATA / "derived" / f"trace_{route_id}.csv"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return [(float(r["x_svy21"]), float(r["y_svy21"])) for r in csv.DictReader(f)]


def trace_weights(net: Network, trace) -> dict:
    """Edge -> weight, with edges off the traced line made OFF_TRACE_PENALTY times dearer."""
    from scipy.spatial import cKDTree

    tree = cKDTree(trace)
    w = {}
    for u, v, d in net.graph.edges(data=True):
        (x0, y0), (x1, y1) = net.xy[u], net.xy[v]
        n = max(2, int(d["length"] // 10) + 1)
        pts = [(x0 + (x1 - x0) * k / (n - 1), y0 + (y1 - y0) * k / (n - 1)) for k in range(n)]
        dist, _ = tree.query(pts)
        # 1x when the whole edge is within TRACE_RADIUS of the traced line, rising linearly
        # to OFF_TRACE_PENALTY x at TRACE_RADIUS + TRACE_RAMP (mean distance).
        excess = max(0.0, float(max(dist)) - TRACE_RADIUS, float(np.mean(dist)) - TRACE_RADIUS)
        w[(u, v)] = d["weight"] * (1.0 + (OFF_TRACE_PENALTY - 1.0) * min(1.0, excess / TRACE_RAMP))
    return w


def reconstruct(route: dict, net: Network, use_trace: bool = True) -> dict:
    stops = route_stops(route)
    trace = load_trace(route["id"]) if use_trace else None
    on_trace = None
    if trace:
        tw = trace_weights(net, trace)
        on_trace = {e for e, w in tw.items() if w == net.graph.edges[e]["weight"]}
        weight = lambda u, v, d: tw[(u, v)]  # noqa: E731
    else:
        weight = "weight"
    avoid = SHUTTLE_FORBIDDEN if route["kind"] == "shuttle" else None
    snapped = []
    for s in stops:
        if s.get("shape_point"):
            snapped.append(dict(s))  # placed below, once its neighbours are known
            continue
        (u, v), d = snap_kerbside(net, s["lat"], s["lon"], avoid, on_trace=on_trace)
        snapped.append({**s, "edge": [u, v], "snap_m": round(d, 1)})
    # A shape point has no kerb side. On a dual carriageway both directions are close to
    # it, so take the candidate edge within SHAPE_RADIUS that makes prev -> edge -> next
    # cheapest, i.e. the carriageway that runs the drawn direction.
    for i, s in enumerate(snapped):
        if not s.get("shape_point"):
            continue
        prev_v = snapped[i - 1]["edge"][1]
        nxt = snapped[(i + 1) % len(snapped)]
        px, py = to_xy(s["lat"], s["lon"])
        best = None
        for u, v, d in net.graph.edges(data=True):
            if avoid and d["highway"] in avoid:
                continue
            dist, _ = _project(px, py, *net.xy[u], *net.xy[v])
            if dist > SHAPE_RADIUS:
                continue
            try:
                c = (nx.shortest_path_length(net.graph, prev_v, u, weight=weight) + d["length"]
                     + nx.shortest_path_length(net.graph, v, nxt["edge"][0], weight=weight))
            except nx.NetworkXNoPath:
                continue
            if best is None or c < best[0]:
                best = (c, (u, v), dist)
        if best is None:
            raise RuntimeError(f"no edge within {SHAPE_RADIUS} m of {s['name']}")
        s["edge"], s["snap_m"] = list(best[1]), round(best[2], 1)
    seq = list(snapped)
    if route.get("loop", True):
        seq = seq + [seq[0]]
    # Each stop is served while traversing its kerbside edge u->v, so a leg runs from the
    # previous stop's v to this stop's u, then along u->v.
    path: list[int] = [seq[0]["edge"][1]] if route.get("loop", True) else list(seq[0]["edge"])
    leg_lengths = []
    for prev, cur in zip(seq[:-1], seq[1:]):
        a, (u, v) = prev["edge"][1], cur["edge"]
        p = nx.shortest_path(net.graph, a, u, weight=weight) + [v]
        leg_lengths.append(sum(net.graph.edges[x, y]["length"] for x, y in zip(p[:-1], p[1:])))
        path += p[1:]
    length = sum(net.graph.edges[u, v]["length"] for u, v in zip(path[:-1], path[1:]))
    return {"route_id": route["id"], "stops": snapped, "path": path, "length_m": length,
            "leg_lengths_m": leg_lengths, "method": "map-guided" if trace else "shortest"}
