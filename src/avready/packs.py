"""Human-readable outputs: route summaries, ODD checklists, the register digest, map data."""
from __future__ import annotations

import json
from collections import Counter

from .common import DOCS

SHUTTLE_SPEED_NOTE = ("Average schedule speed from the published length and duration "
                      "(includes stops and dwell): {v:.1f} km/h.")


def _sum(rows, k):
    return sum((r[k] or 0) for r in rows)


def route_summary(item: dict, cfg: dict, rows: list[dict], reg: list[dict], turns: list[dict]) -> dict:
    km = item["length_m"] / 1000
    ratings = Counter(r["rating"] for r in reg)
    covered = [r for r in rows if r["speed_links_matched"]]
    cov_len = sum(r["length_m"] for r in covered)
    w_cv = (sum(r["speed_cv"] * r["length_m"] for r in covered) / cov_len) if cov_len else None
    posted = Counter()
    for r in rows:
        posted[r["max_posted_kmh"] or "unknown"] += r["length_m"]
    return {
        "route_id": item["id"],
        "name": item["name"],
        "kind": item["kind"],
        "reconstructed_km": round(km, 2),
        "official_km": cfg.get("official_length_km"),
        "length_gap_pct": item["length_gap_pct"],
        "geometry_method": item["method"],
        "map_agreement_path": (item["map_agreement"] or {}).get("path_share_within_30m_of_map"),
        "map_agreement_map": (item["map_agreement"] or {}).get("map_share_within_30m_of_path"),
        "segments": len(rows),
        "signal_sites": _sum(rows, "signal_sites"),
        "signal_sites_per_km": round(_sum(rows, "signal_sites") / km, 2),
        "right_turns_unsignalised": _sum(rows, "right_turns_unsignalised"),
        "right_turns_signalised": _sum(rows, "right_turns_signalised"),
        "left_turns": _sum(rows, "left_turns"),
        "u_turns": _sum(rows, "u_turns"),
        "crossings_uncontrolled_osm": _sum(rows, "crossings_uncontrolled_osm"),
        "crossings_signalised_osm": _sum(rows, "crossings_signalised_osm"),
        "crossings_untyped_osm": _sum(rows, "crossings_untyped_osm"),
        "crossings_lta": _sum(rows, "crossings_lta"),
        "roundabouts": _sum(rows, "roundabouts"),
        "bus_stops": _sum(rows, "bus_stops"),
        "school_zone_m": round(_sum(rows, "school_zone_m")),
        "school_zones": "; ".join(sorted({z for r in rows for z in r["school_zones"].split("; ") if z})),
        "silver_zone_m": round(_sum(rows, "silver_zone_m")),
        "high_speed_m": round(_sum(rows, "high_speed_m")),
        "multi_lane_m": round(_sum(rows, "multi_lane_m")),
        "service_road_m": round(_sum(rows, "service_road_m")),
        "posted_known_share": round(sum(r["posted_known_share"] * r["length_m"] for r in rows) / item["length_m"], 3),
        "speedband_coverage_share": round(cov_len / item["length_m"], 3),
        "speed_cv_weighted": None if w_cv is None else round(w_cv, 3),
        "register_rows": len(reg),
        "very_high": ratings.get("Very high", 0),
        "high": ratings.get("High", 0),
        "medium": ratings.get("Medium", 0),
        "low": ratings.get("Low", 0),
        "risk_score_per_km": round(sum(r["risk_score"] for r in rows) / km, 1),
    }


def osm_vs_lta(segments: list[dict]) -> dict:
    """How far OSM alone would have under- or over-counted, per route, against LTA layers."""
    out = {}
    for rid in sorted({s["route_id"] for s in segments}):
        rows = [s for s in segments if s["route_id"] == rid]
        osm_x = (_sum(rows, "crossings_signalised_osm") + _sum(rows, "crossings_uncontrolled_osm")
                 + _sum(rows, "crossings_untyped_osm"))
        out[rid] = {
            "signal_sites_osm": _sum(rows, "signal_sites_osm"),
            "signal_sites_lta": _sum(rows, "signal_sites_lta"),
            "signal_sites_union": _sum(rows, "signal_sites"),
            "crossings_osm": osm_x,
            "crossings_lta": _sum(rows, "crossings_lta"),
            "segments_with_lta_crossing_but_no_osm_crossing": sum(
                1 for s in rows if s["crossings_lta"] and not (s["crossings_signalised_osm"] or s["crossings_uncontrolled_osm"]
                                                               or s["crossings_untyped_osm"])),
            "segments_with_osm_crossing_but_no_lta_crossing": sum(
                1 for s in rows if not s["crossings_lta"] and (s["crossings_signalised_osm"] or s["crossings_uncontrolled_osm"]
                                                               or s["crossings_untyped_osm"])),
        }
    return out


# ------------------------------------------------------------------ ODD checklist

def _fmt_segs(rows, cond, limit=12):
    ids = [r["segment_id"].split("-")[-1] for r in rows if cond(r)]
    if not ids:
        return "none"
    more = f" (+{len(ids) - limit} more)" if len(ids) > limit else ""
    return ", ".join(ids[:limit]) + more


def odd_markdown(item: dict, cfg: dict, rows: list[dict], summ: dict, turns: list[dict]) -> str:
    km = item["length_m"] / 1000
    official = cfg.get("official_length_km")
    dur = cfg.get("official_duration_min")
    lines = [f"# ODD checklist: {item['name']} ({item['id']})", ""]
    lines += ["Generated by `python -m avready.build` from the segment profile. This is a desk checklist "
              "designed for use in a trial; it has not been used on a real deployment. Every count comes from "
              "public data (OSM, LTA DataMall) on a *reconstructed* route, so each item still needs checking on "
              "site.", ""]
    lines += ["## 1. Route as published", ""]
    lines += [f"- Operator: {cfg['operator']}", f"- Status: {cfg['status']}"]
    if official and dur:
        lines += [f"- Published round trip: about {official} km, about {dur} min. "
                  + SHUTTLE_SPEED_NOTE.format(v=official / (dur / 60))]
    elif official:
        lines += [f"- Published / DataMall route length: {official} km"]
    stops = [s for s in item["stops"] if not s["shape_point"]]
    lines += [f"- Stops ({len(stops)}): " + "; ".join(s["name"] for s in stops)]
    lines += ["- Published operating hours (secondary source): 09:30-17:30, Monday to Saturday, excluding public "
              "holidays." if item["kind"] == "shuttle" else "- Operating hours: as the public bus service."]
    lines += ["", "## 2. Geometry confidence", ""]
    ma = item["map_agreement"]
    lines += [f"- Reconstructed length {km:.2f} km vs published {official} km ({item['length_gap_pct']:+.1f}%)."]
    if ma:
        lines += [f"- {ma['path_share_within_30m_of_map']:.0%} of the reconstructed path lies within 30 m of the "
                  f"line traced from LTA's Annex A map; {ma['map_share_within_30m_of_path']:.0%} of the traced line "
                  "lies within 30 m of the path."]
    lines += ["- Stop snap distances (m, stop position to the road edge used): "
              + ", ".join(f"{s['snap_m']:.0f}" for s in stops)]
    lines += ["", "## 3. Road environment the ADS must handle (observed along the reconstructed path)", ""]
    lines += ["| Attribute | Observed | Segments |", "|---|---|---|"]
    posted = Counter()
    for r in rows:
        posted[r["max_posted_kmh"] or "not tagged"] += 1
    lines += [
        f"| Road classes | {', '.join(sorted({r['main_class'] for r in rows}))} | all |",
        f"| Posted speed limits (max per segment) | {', '.join(f'{k}: {v}' for k, v in sorted(posted.items(), key=str))} "
        f"(share of length with a tagged limit: {summ['posted_known_share']:.0%}) | |",
        f"| Length on roads posted 60 km/h or more | {summ['high_speed_m']} m | {_fmt_segs(rows, lambda r: r['high_speed_m'] > 0)} |",
        f"| Length with 3+ lanes in the travel direction | {summ['multi_lane_m']} m | {_fmt_segs(rows, lambda r: r['multi_lane_m'] > 0)} |",
        f"| Signal-controlled sites: junctions and signalised crossings (OSM signal nodes on the path, LTA lights within 20 m) | {summ['signal_sites']} ({summ['signal_sites_per_km']}/km) | {_fmt_segs(rows, lambda r: r['signal_sites'] > 0)} |",
        f"| Right turns without signals | {summ['right_turns_unsignalised']} | {_fmt_segs(rows, lambda r: r['right_turns_unsignalised'] > 0)} |",
        f"| Right turns at signals | {summ['right_turns_signalised']} | {_fmt_segs(rows, lambda r: r['right_turns_signalised'] > 0)} |",
        f"| Turnarounds in the reconstructed path (in-and-out spurs to a stop; confirm how the vehicle turns) | {summ['u_turns']} | {_fmt_segs(rows, lambda r: r['u_turns'] > 0)} |",
        f"| Crossings on the path tagged in OSM without a type | {summ['crossings_untyped_osm']} | {_fmt_segs(rows, lambda r: r['crossings_untyped_osm'] > 0)} |",
        f"| Pedestrian crossings without signals (OSM: zebra, marked, unmarked) | {summ['crossings_uncontrolled_osm']} | {_fmt_segs(rows, lambda r: r['crossings_uncontrolled_osm'] > 0)} |",
        f"| Signalised pedestrian crossings (OSM) | {summ['crossings_signalised_osm']} | {_fmt_segs(rows, lambda r: r['crossings_signalised_osm'] > 0)} |",
        f"| Road crossings in LTA's layer | {summ['crossings_lta']} | {_fmt_segs(rows, lambda r: r['crossings_lta'] > 0)} |",
        f"| Roundabouts | {summ['roundabouts']} | {_fmt_segs(rows, lambda r: r['roundabouts'] > 0)} |",
        f"| Public bus stops on the path | {summ['bus_stops']} | {_fmt_segs(rows, lambda r: r['bus_stops'] > 0)} |",
        f"| LTA School Zones | {summ['school_zone_m']} m ({summ['school_zones'] or 'none'}) | {_fmt_segs(rows, lambda r: r['school_zone_m'] > 0)} |",
        f"| LTA Silver Zones | {summ['silver_zone_m']} m | {_fmt_segs(rows, lambda r: r['silver_zone_m'] > 0)} |",
        f"| Service roads / car-park access | {summ['service_road_m']} m | {_fmt_segs(rows, lambda r: r['service_road_m'] > 0)} |",
        f"| Road humps (LTA) | {sum(r['road_humps_lta'] for r in rows)} | {_fmt_segs(rows, lambda r: r['road_humps_lta'] > 0)} |",
        f"| Speed-band coverage of the path | {summ['speedband_coverage_share']:.0%} | |",
        f"| Speed variability in operating hours (length-weighted CV) | {summ['speed_cv_weighted']} | |",
    ]
    lines += ["", "## 4. ODD items to confirm with the AV developer and operator", ""]
    items = [
        ("Maximum operating speed per segment, and behaviour where the posted limit is 60 km/h or more",
         summ["high_speed_m"] > 0),
        ("Unprotected right turns: gap acceptance, abort and takeover rule", summ["right_turns_unsignalised"] > 0),
        ("Traffic-light recognition at each signal-controlled site, day and in heavy rain", summ["signal_sites"] > 0),
        ("Yielding at crossings without signals, including late and partly hidden pedestrians",
         summ["crossings_uncontrolled_osm"] > 0),
        ("School-zone hours and speed; schedule against school arrival and dismissal", summ["school_zone_m"] > 0),
        ("Silver-zone behaviour (lower speed, longer yield)", summ["silver_zone_m"] > 0),
        ("Roundabout entry and yielding", summ["roundabouts"] > 0),
        ("Lane changes and merges on multi-lane roads", summ["multi_lane_m"] > 0),
        ("Interaction with public buses at shared stops", summ["bus_stops"] > 0),
        ("Which service roads are inside the approved route, and a geofence for the rest", summ["service_road_m"] > 0),
    ]
    disputed = [t for t in turns if t["signal_source"] in ("osm only", "lta only")]
    if disputed:
        items.append((f"Signal control disputed between OSM and LTA's traffic-light layer at {len(disputed)} turn(s): "
                      + "; ".join(f"{t['turn']} turn at {t['lat']:.5f},{t['lon']:.5f} ({t['signal_source']})"
                                  for t in disputed) + ". Check on site.", True))
    for text, present in items:
        if present:
            lines.append(f"- [ ] {text}")
    lines += [
        "- [ ] Weather limits: rainfall intensity at which service is suspended, and the data source used to "
        "decide (for example NEA rainfall readings)",
        "- [ ] Lighting: service within daylight hours only, or night operation evidence",
        "- [ ] Minimal risk manoeuvre: where on each segment the vehicle can stop safely",
        "- [ ] Transitions between autonomous and manual driving: procedure and training (reviewed by LTA and an "
        "operator after the 17 Jan 2026 incident; see SOURCES.md)",
        "- [ ] Remote monitoring: latency and coverage along the full route",
        "",
        "## 5. Data gaps",
        "",
        f"- Posted speed limit is tagged in OSM for {summ['posted_known_share']:.0%} of the path; the rest is "
        "untagged, not unlimited.",
        f"- Speed bands cover {summ['speedband_coverage_share']:.0%} of the path; estate roads are often not in the "
        "speed-band network.",
        "- Incident history: no public historical geolocated crash data exists; see README section 4.",
        "",
    ]
    return "\n".join(lines)


def register_digest(register: list[dict], summaries: list[dict]) -> str:
    lines = ["# Risk register digest", "",
             "Full register: [`outputs/risk_register.csv`](../outputs/risk_register.csv) (one row per hazard per "
             "segment). Scores are likelihood (1-5, from measured exposure) x severity (1-5, fixed per hazard), "
             "set in `config/scoring.yaml`. All rows are *proposed* and come from a desk assessment.", ""]
    for s in summaries:
        rows = [r for r in register if r["route_id"] == s["route_id"]]
        rows.sort(key=lambda r: (-r["score"], r["segment_id"], r["hazard"]))
        lines += [f"## {s['name']} ({s['route_id']})", "",
                  f"{s['register_rows']} rows: {s['very_high']} very high, {s['high']} high, {s['medium']} medium, "
                  f"{s['low']} low.", "",
                  "| Risk ID | Chainage (m) | Location | Hazard | L | S | Score | Owner |", "|---|---|---|---|---|---|---|---|"]
        for r in rows[:10]:
            lines.append(f"| {r['risk_id']} | {r['chainage_m']} | {r['location']} | {r['hazard_description']} | "
                         f"{r['likelihood']} | {r['severity']} | {r['score']} | {r['owner']} |")
        lines.append("")
    return "\n".join(lines)


def write_packs(routes, cfg_r, segs_by_route, register, summaries, turns, sens) -> None:
    odd_dir = DOCS / "odd"
    odd_dir.mkdir(parents=True, exist_ok=True)
    summ_by = {s["route_id"]: s for s in summaries}
    for item in routes["routes"]:
        if item["kind"] != "shuttle":
            continue
        md = odd_markdown(item, cfg_r[item["id"]], segs_by_route[item["id"]], summ_by[item["id"]],
                          [t for t in turns if t["route_id"] == item["id"]])
        (odd_dir / f"{item['id']}.md").write_text(md, encoding="utf-8")
    shuttle_summ = [s for s in summaries if s["kind"] == "shuttle"]
    (DOCS / "RISK_REGISTER.md").write_text(register_digest(register, shuttle_summ), encoding="utf-8")

    # Map data for the static page.
    feats = []
    for item in routes["routes"]:
        for r in segs_by_route[item["id"]]:
            feats.append({"type": "Feature",
                          "geometry": {"type": "LineString", "coordinates": [[b, a] for a, b in r["_latlon"]]},
                          "properties": {k: r[k] for k in ("route_id", "segment_id", "main_road", "length_m",
                                                           "risk_score", "signal_sites", "right_turns_unsignalised",
                                                           "crossings_uncontrolled_osm", "school_zone_m",
                                                           "bus_stops", "speed_cv", "max_posted_kmh")}})
        for s in item["stops"]:
            if not s["shape_point"]:
                feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                              "properties": {"route_id": item["id"], "stop": s["name"]}})
    (DOCS / "data").mkdir(exist_ok=True)
    (DOCS / "data" / "segments.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                                                               separators=(",", ":")), encoding="utf-8")
    (DOCS / "data" / "summary.json").write_text(json.dumps(summaries, indent=1), encoding="utf-8")
