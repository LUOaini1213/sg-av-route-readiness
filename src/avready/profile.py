"""Cut each reconstructed route into segments and measure the road environment along them."""
from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass

import shapely
from shapely.geometry import LineString, Point, Polygon

from .common import DATA, bearing_deg, read_json_gz, to_xy, turn_angle
from .network import Network


# ---------------------------------------------------------------- path helpers

def path_edges(path: list[int], net: Network) -> list[dict]:
    ways = {w["id"]: w["tags"] for w in net.raw["ways"]}
    out = []
    for u, v in zip(path[:-1], path[1:]):
        d = net.graph.edges[u, v]
        out.append({"u": u, "v": v, "length": d["length"], "highway": d["highway"], "tags": ways[d["way"]]})
    return out


def cut_segments(edges: list[dict], target_m: float) -> list[list[dict]]:
    """Group consecutive edges into segments of about target_m (a segment closes at the
    first edge end at or past target_m). The last short remainder joins the previous
    segment if it is under half the target."""
    segs, cur, acc = [], [], 0.0
    for e in edges:
        cur.append(e)
        acc += e["length"]
        if acc >= target_m:
            segs.append(cur)
            cur, acc = [], 0.0
    if cur:
        if segs and acc < target_m / 2:
            segs[-1].extend(cur)
        else:
            segs.append(cur)
    return segs


def direction_lanes(tags: dict) -> int | None:
    def num(v):
        m = re.match(r"\s*(\d+)", v or "")
        return int(m.group(1)) if m else None

    if tags.get("oneway") in ("yes", "true", "1", "-1") or tags.get("junction") == "roundabout":
        return num(tags.get("lanes"))
    fwd = num(tags.get("lanes:forward"))
    if fwd:
        return fwd
    total = num(tags.get("lanes"))
    return max(1, total // 2) if total else None


def posted_speed(tags: dict) -> int | None:
    m = re.match(r"\s*(\d+)", tags.get("maxspeed", "") or "")
    return int(m.group(1)) if m else None


def heading_change(xy: list[tuple[float, float]], i: int, window: float = 20.0) -> float:
    """Signed heading change at vertex i, measured between the points `window` metres
    before and after it along the polyline (robust to short curve vertices)."""
    def walk(step):
        j, acc = i, 0.0
        while 0 <= j + step < len(xy) and acc < window:
            acc += math.dist(xy[j], xy[j + step])
            j += step
        return j

    a, b = walk(-1), walk(1)
    if a == i or b == i:
        return 0.0
    return turn_angle(bearing_deg(*xy[a], *xy[i]), bearing_deg(*xy[i], *xy[b]))


# ---------------------------------------------------------------- context layers

@dataclass
class Layers:
    osm_signals: list            # Points (all OSM traffic_signals nodes, used for junction control)
    osm_node_tags: dict          # node id -> tags, for signal/crossing nodes that sit on roads
    osm_mini_roundabouts: list
    osm_schools: list
    bus_stops: list
    lta_lights: list
    lta_crossings: list          # LineStrings
    lta_humps: list
    school_zones: list           # (Polygon, name)
    silver_zones: list
    incidents: list              # (Point, label)
    speed_links: list            # (LineString, bearing, stats dict)


def _pt(lat, lon):
    return Point(*to_xy(lat, lon))


def _line(parts):
    return [LineString([to_xy(a, b) for a, b in part]) for part in parts if len(part) >= 2]


def _poly(parts):
    return [Polygon([to_xy(a, b) for a, b in part]) for part in parts if len(part) >= 3]


def crossing_kind(tags: dict) -> str | None:
    """signalised / uncontrolled (zebra, marked or unmarked) / untyped; None if not a crossing.
    Untyped crossing nodes (highway=crossing with no crossing=*) are common in OSM and are
    kept apart rather than guessed."""
    hw, c = tags.get("highway"), tags.get("crossing")
    if hw != "crossing" and not c:
        return None
    if c == "no":
        return None
    if c in ("traffic_signals", "pedestrian_signals") or tags.get("crossing_ref") in ("pelican", "toucan", "puffin"):
        return "signalised"
    if c in ("zebra", "uncontrolled", "marked", "unmarked", "informal") or tags.get("crossing_ref") == "zebra":
        return "uncontrolled"
    return "untyped"


def load_layers(aoi: str, raw_osm: dict) -> Layers:
    sig, node_tags, mini = [], {}, []
    for p in raw_osm["points"]:
        t = p["tags"]
        hw = t.get("highway")
        node_tags[p["id"]] = t
        if hw == "traffic_signals":
            sig.append(_pt(p["lat"], p["lon"]))
        if hw == "mini_roundabout":
            mini.append(_pt(p["lat"], p["lon"]))
    schools = [(_pt(s["lat"], s["lon"]), s["name"]) for s in raw_osm["schools"]]

    with open(DATA / "lta" / "bus_stops.csv", encoding="utf-8") as f:
        stops = [(_pt(float(r["Latitude"]), float(r["Longitude"])), r["BusStopCode"]) for r in csv.DictReader(f)]

    geo = read_json_gz(DATA / "lta" / f"geo_{aoi}.json.gz")["layers"]
    lights = [_pt(*f["parts"][0][0]) for f in geo["TrafficLight"]["features"] if f["parts"] and f["parts"][0]]
    lcross = [ln for f in geo["RoadCrossing"]["features"] for ln in _line(f["parts"])]
    humps = [ln for f in geo["RoadHump"]["features"] for ln in _line(f["parts"])]
    sz = [(pg, f["attrs"].get("SITENAME", "")) for f in geo["SchoolZone"]["features"] for pg in _poly(f["parts"])]
    slz = [(pg, f["attrs"].get("SITENAME", "")) for f in geo["SilverZone"]["features"] for pg in _poly(f["parts"])]

    incidents = []
    p = DATA / "derived" / "incidents.csv"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                incidents.append((_pt(float(r["lat"]), float(r["lon"])), f'{r["type"]} ({r["source"]})'))

    links = []
    p = DATA / "derived" / "speedband_stats.csv"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                a, b = to_xy(float(r["start_lat"]), float(r["start_lon"])), to_xy(float(r["end_lat"]), float(r["end_lon"]))
                if a == b:
                    continue
                stats = {k: float(r[k]) for k in ("n_obs", "mean_kmh", "std_kmh", "cv", "p_slow")}
                links.append((LineString([a, b]), bearing_deg(*a, *b), stats))
    return Layers(sig, node_tags, mini, schools, stops, lights, lcross, humps, sz, slz, incidents, links)


def left_of(line: LineString, p: Point) -> bool:
    """True if p is on the left of the line's direction of travel at its nearest point
    (the kerb side in Singapore)."""
    d = line.project(p)
    a = line.interpolate(max(0.0, d - 5))
    b = line.interpolate(min(line.length, d + 5))
    if a.equals(b):
        return False
    return (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x) > 0


def cluster_count(points: list[Point], radius: float) -> int:
    """Number of groups when points closer than `radius` are chained together."""
    pts = [(p.x, p.y) for p in points]
    seen, groups = set(), 0
    for i in range(len(pts)):
        if i in seen:
            continue
        groups += 1
        stack = [i]
        seen.add(i)
        while stack:
            k = stack.pop()
            for j in range(len(pts)):
                if j not in seen and math.dist(pts[k], pts[j]) < radius:
                    seen.add(j)
                    stack.append(j)
    return groups


# ---------------------------------------------------------------- per-segment features

def segment_features(seg: list[dict], net: Network, layers: Layers, cfg: dict, route_stops_nodes: set,
                     turns: list[dict]) -> dict:
    B = cfg["buffers_m"]
    xy = [net.xy[seg[0]["u"]]] + [net.xy[e["v"]] for e in seg]
    line = LineString(xy)
    length = sum(e["length"] for e in seg)

    def near(points, d):
        return [p for p in points if line.distance(p) <= d]

    path_nodes = [seg[0]["u"]] + [e["v"] for e in seg]
    # OSM signal and crossing nodes count only when they are vertices of the path itself,
    # i.e. the vehicle drives over them; nodes on side roads are not on the route.
    on_path = [(Point(net.xy[n]), layers.osm_node_tags[n]) for n in path_nodes if n in layers.osm_node_tags]
    sig_osm = [p for p, t in on_path if t.get("highway") == "traffic_signals"]
    sig_lta = near(layers.lta_lights, B["signal"])
    signal_pts = sig_osm + sig_lta
    kinds = [(p, crossing_kind(t)) for p, t in on_path]
    cross_sig = [p for p, k in kinds if k == "signalised"]
    cross_unc = [p for p, k in kinds if k == "uncontrolled"]
    cross_unt = [p for p, k in kinds if k == "untyped"]
    # LTA crossings are drawn across the carriageway, so they must touch the path line.
    lta_cross = [ln for ln in layers.lta_crossings if line.distance(ln) <= B["crossing_touch"]]
    humps = [ln for ln in layers.lta_humps if line.distance(ln) <= B["crossing_touch"]]
    stops = [p for p, _ in layers.bus_stops if line.distance(p) <= B["bus_stop"] and left_of(line, p)]
    schools_osm = [n for p, n in layers.osm_schools if line.distance(p) <= B["school_osm"]]
    sz = [(pg, n) for pg, n in layers.school_zones if line.intersects(pg)]
    slz = [(pg, n) for pg, n in layers.silver_zones if line.intersects(pg)]
    sz_len = sum(line.intersection(pg).length for pg, _ in sz)
    slz_len = sum(line.intersection(pg).length for pg, _ in slz)
    inc = [lab for p, lab in layers.incidents if line.distance(p) <= B["incident"]]

    right_unprot = sum(1 for t in turns if t["kind"] == "right" and not t["signalised"])
    right_sig = sum(1 for t in turns if t["kind"] == "right" and t["signalised"])
    left = sum(1 for t in turns if t["kind"] == "left")
    uturns = sum(1 for t in turns if t["kind"] == "u_turn")

    roundabout_ways = {id(e["tags"]) for e in seg if e["tags"].get("junction") in ("roundabout", "circular")}
    mini = near(layers.osm_mini_roundabouts, B["signal"])

    hi_speed = sum(e["length"] for e in seg if (posted_speed(e["tags"]) or 0) >= 60)
    multi = sum(e["length"] for e in seg if (direction_lanes(e["tags"]) or 0) >= 3)
    service = sum(e["length"] for e in seg if e["highway"] == "service")
    speeds = [posted_speed(e["tags"]) for e in seg]
    known = [(s, e["length"]) for s, e in zip(speeds, seg) if s]

    # Speed bands: links running the same way, close to the path.
    tol = cfg["speedband"]["bearing_tol_deg"]
    matched = []
    for ln, brg, st in layers.speed_links:
        if line.distance(ln.interpolate(0.5, normalized=True)) > B["speedband_match"]:
            continue
        proj = line.project(ln.interpolate(0.5, normalized=True))
        p0 = line.interpolate(max(0.0, proj - 5))
        p1 = line.interpolate(min(line.length, proj + 5))
        if p0.equals(p1):
            continue
        if abs(turn_angle(bearing_deg(p0.x, p0.y, p1.x, p1.y), brg)) <= tol:
            matched.append((ln.length, st))
    if matched:
        w = sum(l for l, _ in matched)
        cv = sum(l * s["cv"] for l, s in matched) / w
        mean_kmh = sum(l * s["mean_kmh"] for l, s in matched) / w
        p_slow = sum(l * s["p_slow"] for l, s in matched) / w
    else:
        cv = mean_kmh = p_slow = float("nan")

    names = {}
    for e in seg:
        nm = e["tags"].get("name") or f'({e["highway"]})'
        names[nm] = names.get(nm, 0.0) + e["length"]
    road = max(names, key=names.get)
    hwc = {}
    for e in seg:
        hwc[e["highway"]] = hwc.get(e["highway"], 0.0) + e["length"]

    mid = line.interpolate(0.5, normalized=True)
    return {
        "length_m": round(length, 1),
        "main_road": road,
        "roads": "; ".join(sorted(names, key=lambda k: -names[k])[:3]),
        "main_class": max(hwc, key=hwc.get),
        "max_posted_kmh": max((s for s, _ in known), default=None),
        "posted_known_share": round(sum(l for _, l in known) / length, 3) if length else 0.0,
        "max_dir_lanes": max((direction_lanes(e["tags"]) or 0 for e in seg), default=0) or None,
        "signal_sites_osm": cluster_count(sig_osm, B["signal_cluster"]),
        "signal_sites_lta": cluster_count(sig_lta, B["signal_cluster"]),
        "signal_sites": cluster_count(signal_pts, B["signal_cluster"]),
        "crossings_signalised_osm": cluster_count(cross_sig, B["crossing_cluster"]),
        "crossings_uncontrolled_osm": cluster_count(cross_unc, B["crossing_cluster"]),
        "crossings_untyped_osm": cluster_count(cross_unt, B["crossing_cluster"]),
        "crossings_lta": cluster_count([ln.interpolate(0.5, normalized=True) for ln in lta_cross], B["crossing_cluster"]),
        "road_humps_lta": len(humps),
        "roundabouts": len(roundabout_ways) + cluster_count(mini, B["signal_cluster"]),
        "right_turns_unsignalised": right_unprot,
        "right_turns_signalised": right_sig,
        "left_turns": left,
        "u_turns": uturns,
        "bus_stops": len(stops),
        "school_zone_m": round(sz_len, 1),
        "school_zones": "; ".join(sorted({n for _, n in sz})),
        "silver_zone_m": round(slz_len, 1),
        "silver_zones": "; ".join(sorted({n for _, n in slz})),
        "schools_osm_150m": len(set(schools_osm)),
        "high_speed_m": round(hi_speed, 1),
        "multi_lane_m": round(multi, 1),
        "service_road_m": round(service, 1),
        "pudo_on_segment": int(any(n in route_stops_nodes for n in path_nodes)),
        "incidents_nearby": len(inc),
        "incident_labels": "; ".join(sorted(set(inc))),
        "speed_links_matched": len(matched),
        "speed_mean_kmh": None if math.isnan(mean_kmh) else round(mean_kmh, 1),
        "speed_cv": None if math.isnan(cv) else round(cv, 3),
        "speed_p_slow": None if math.isnan(p_slow) else round(p_slow, 3),
        "mid_lat_lon": None,  # filled by caller
        "_mid_xy": (mid.x, mid.y),
        "_xy": xy,
    }


def route_turns(path: list[int], net: Network, layers: Layers, cfg: dict, junctions: set) -> list[dict]:
    """Turn events along the whole route.

    Heading change is measured at every vertex over +-30 m. Consecutive vertices whose
    change exceeds turn_deg are one event if they lie within 40 m of each other (a turn
    on a dual carriageway or a slip road spreads over several vertices); the event's
    angle is the heading change from 30 m before its first vertex to 30 m after its last.
    An event is a junction turn if a junction node lies within 25 m. Positive angle =
    clockwise = right turn, which in Singapore (left-hand traffic) crosses the oncoming
    lanes. |angle| >= 150 is reported as a U-turn/reversal. A turn is signalised when an
    OSM signal node or LTA light lies within junction_signal metres."""
    xy = [net.xy[n] for n in path]
    jpts = [Point(net.xy[n]) for n in junctions]
    jtree = shapely.STRtree(jpts) if jpts else None
    cand = [i for i in range(1, len(path) - 1) if abs(heading_change(xy, i, 30.0)) >= cfg["turn_deg"]]
    groups = []
    for i in cand:
        if groups and math.dist(xy[groups[-1][-1]], xy[i]) < 40.0:
            groups[-1].append(i)
        else:
            groups.append([i])
    out = []
    for g in groups:
        first, last = g[0], g[-1]
        # bearing 30 m before the first vertex and 30 m after the last one
        def walk(i, step):
            j, acc = i, 0.0
            while 0 <= j + step < len(xy) and acc < 30.0:
                acc += math.dist(xy[j], xy[j + step])
                j += step
            return j
        a, b = walk(first, -1), walk(last, 1)
        if a == first or b == last:
            continue
        ang = turn_angle(bearing_deg(*xy[a], *xy[first]), bearing_deg(*xy[last], *xy[b]))
        if abs(ang) < cfg["turn_deg"]:
            continue
        k = max(g, key=lambda i: abs(heading_change(xy, i, 30.0)))
        pk = Point(xy[k])
        at_junction = jtree is not None and len(jtree.query(pk, predicate="dwithin", distance=25.0)) > 0
        if not at_junction and abs(ang) < 150:
            continue  # a bend in the road, not a turn
        rad = cfg["buffers_m"]["junction_signal"]
        osm_sig = any(pk.distance(p) <= rad for p in layers.osm_signals)
        lta_sig = any(pk.distance(p) <= rad for p in layers.lta_lights)
        signalised = osm_sig or lta_sig
        source = "both" if osm_sig and lta_sig else ("osm only" if osm_sig else ("lta only" if lta_sig else "none"))
        hws = {net.graph.edges[path[i], path[i + 1]]["highway"] for i in range(max(0, first - 1), min(len(path) - 1, last + 1))}
        kind = "u_turn" if abs(ang) >= 150 else ("right" if ang > 0 else "left")
        out.append({"i": k, "node": path[k], "angle": round(ang, 1), "kind": kind, "signalised": signalised,
                    "signal_source": source, "access": "service" in hws, "xy": xy[k]})
    return out


def junction_nodes(net: Network) -> set:
    """Nodes where three or more road edges meet, counting service-road entrances (a right
    turn into a car park crosses oncoming traffic just like one into a side road)."""
    ways_at: dict[int, set] = {}
    deg: dict[int, set] = {}
    for u, v, d in net.graph.edges(data=True):
        ways_at.setdefault(u, set()).add(d["way"])
        ways_at.setdefault(v, set()).add(d["way"])
        deg.setdefault(u, set()).add(v)
        deg.setdefault(v, set()).add(u)
    return {n for n, nb in deg.items() if len(nb) >= 3 and len(ways_at.get(n, ())) >= 2}
