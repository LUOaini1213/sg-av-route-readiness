"""The numbers in README.md must match the committed outputs.

Every check builds the README phrase from the outputs and requires it verbatim, so a
hand-edited README number, or an output that changes without the README, fails here.
"""
import csv
import json
import re
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal

import pytest
from shapely.geometry import LineString, Point

from avready.common import DATA, OUTPUTS, RESULTS, ROOT, read_json_gz, routes_config, to_xy

README = (ROOT / "README.md").read_text(encoding="utf-8")
SHUTTLES = ("PG-R1", "PG-R2", "PG-R3")
FLAT = re.sub(r"\s+", " ", README)  # prose is wrapped; compare with single spaces


def has(phrase):
    assert re.sub(r"\s+", " ", phrase) in FLAT, f"README does not say: {phrase!r}"


def csv_rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def hu(x, nd=0):
    """Round half up, as the README does (80.5 -> 81); float formatting rounds half to even."""
    q = Decimal(1).scaleb(-nd)
    return str(Decimal(str(round(float(x), 9))).quantize(q, rounding=ROUND_HALF_UP))


def rng(values, nd=0, sep="-"):
    lo, hi = hu(min(values), nd), hu(max(values), nd)
    return lo if lo == hi else f"{lo}{sep}{hi}"


SUMMARY = {r["route_id"]: r for r in csv_rows(OUTPUTS / "route_summary.csv")}
VAL = json.loads((RESULTS / "validation.json").read_text(encoding="utf-8"))
SENS = json.loads((RESULTS / "sensitivity.json").read_text(encoding="utf-8"))
CFG = {r["id"]: r for r in routes_config()["routes"]}


def shortest_gaps():
    v = VAL["routes"]
    return [round(100 * (1 - v[r]["shortest_length_m"] / 1000 / v[r]["official_length_km"])) for r in SHUTTLES]


def speedband_days():
    rows = [r for r in csv_rows(DATA / "derived" / "speedband_manifest.csv")
            if r["in_operating_window"] == "1" and r["duplicate"] == "0"]
    return len(rows), sorted({r["sgt"][:10] for r in rows})


WORDS = {4: "four", 5: "five", 6: "six", 7: "seven"}


def test_table_matches_route_summary():
    reg = Counter((r["route_id"], r["rating"]) for r in csv_rows(OUTPUTS / "risk_register.csv"))
    lines = [ln for ln in README.splitlines() if ln.startswith("| PG-R") or ln.startswith("| BUS-")]
    table = {ln.split("|")[1].strip(): [c.strip() for c in ln.split("|")[2:-1]] for ln in lines
             if re.match(r"\| (PG-R\d|BUS-\d+) \| \d", ln)}
    assert set(table) == set(SUMMARY)
    for rid, s in SUMMARY.items():
        official = s["official_km"]
        expect = [
            f"{float(s['reconstructed_km']):.2f} ({official})",
            hu(s["signal_sites_per_km"], 1),
            f"{s['right_turns_signalised']} / {s['right_turns_unsignalised']}",
            s["crossings_uncontrolled_osm"],
            f"{int(s['school_zone_m']):,}",
            f"{int(s['high_speed_m']):,}",
            s["bus_stops"],
        ]
        if s["kind"] == "shuttle":
            expect.append(f"{s['register_rows']} ({reg[(rid, 'Very high')]} / {reg[(rid, 'High')]})")
            assert int(s["very_high"]) == reg[(rid, "Very high")] and int(s["high"]) == reg[(rid, "High")]
        else:
            expect.append("comparison only")
        assert table[rid] == expect, rid


def test_first_screen():
    reg_rows = len(csv_rows(OUTPUTS / "risk_register.csv"))
    gaps = [abs(VAL["routes"][r]["length_gap_pct"]) for r in SHUTTLES]
    hi_km = [int(SUMMARY[r]["high_speed_m"]) / 1000 for r in SHUTTLES]
    osm = [VAL["osm_vs_lta"][r]["signal_sites_osm"] for r in SHUTTLES]
    lta = [VAL["osm_vs_lta"][r]["signal_sites_lta"] for r in SHUTTLES]
    n, days = speedband_days()
    assert all(int(SUMMARY[r]["right_turns_unsignalised"]) == 0 for r in SHUTTLES)
    has(f"(within {hu(max(gaps), 1)}% of the published lengths)")
    has(f"into a {reg_rows}-row risk register")
    has(f"published routes are {rng(shortest_gaps())}% longer than shortest paths")
    has("every shuttle right turn is at a signal")
    has(f"each route has {rng(hi_km, 1)} km on roads posted 60 km/h or more")
    has(f"OSM alone finds {rng(osm)} signal-controlled sites per route where LTA's layer finds {rng(lta)}.")
    has(f"rests on {n} snapshots from {WORDS[len(days)]} weekdays")


def test_finding_1_route_lengths():
    g = shortest_gaps()
    has(f"come out {g[0]}%, {g[1]}% and {g[2]}% shorter than the published lengths")
    p = [VAL["routes"][r]["length_gap_pct"] for r in SHUTTLES]
    has(f"brings the gap to {p[0]:+.1f}%, {p[1]:+.1f}% and {p[2]:+.1f}%")


def test_finding_2_turns():
    s = SUMMARY
    has(f"have {s['PG-R1']['right_turns_signalised']}, {s['PG-R2']['right_turns_signalised']} and "
        f"{s['PG-R3']['right_turns_signalised']} right turns at signals and none without")
    assert s["BUS-400"]["right_turns_unsignalised"] == s["BUS-191"]["right_turns_unsignalised"] == "1"
    turns = [t for t in csv_rows(OUTPUTS / "turns.csv")
             if t["route_id"] in SHUTTLES and t["signal_source"] == "osm only"]
    right = [t for t in turns if t["turn"] == "right"]
    left = {(t["lat"], t["lon"]) for t in turns if t["turn"] == "left"}
    right_sites = {(t["lat"], t["lon"]) for t in right}
    has(f"At {len(right_sites)} of these right-turn junctions ({len(right)} turns, as Routes 1 and 3 share one) "
        f"and at {len(left)} signalised left turns, OSM tags a signal")
    has(f"The ODD checklists list these {len(right_sites | left)} locations")
    assert all(t["signalised"] == "1" for t in turns)


def test_finding_3_and_speeds():
    hi_km = [int(SUMMARY[r]["high_speed_m"]) / 1000 for r in SHUTTLES]
    has(f"Each shuttle route spends {rng(hi_km, 1)} km on roads posted 60 km/h or more")
    v = [CFG[r]["official_length_km"] / (CFG[r]["official_duration_min"] / 60) for r in SHUTTLES]
    has(f"the shuttles average {rng(v)} km/h including stops")


def test_finding_4_school_zones():
    s = SUMMARY
    has(f"Route 1 has {s['PG-R1']['school_zone_m']} m inside LTA School Zones")
    r23 = [int(s["PG-R2"]["school_zone_m"]), int(s["PG-R3"]["school_zone_m"])]
    assert abs(r23[0] - 480) <= 10 and abs(r23[1] - 480) <= 10, r23
    assert all(int(s[r]["silver_zone_m"]) == 0 for r in SHUTTLES)
    for name in ("Greendale", "Horizon", "Punggol Green"):
        assert name in s["PG-R1"]["school_zones"]


def test_finding_5_osm_vs_lta():
    v = VAL["osm_vs_lta"]
    untyped = [int(SUMMARY[r]["crossings_untyped_osm"]) for r in SHUTTLES]
    has(f"find {rng([v[r]['signal_sites_osm'] for r in SHUTTLES])} signal-controlled sites per shuttle route. "
        f"LTA's traffic-light layer finds {rng([v[r]['signal_sites_lta'] for r in SHUTTLES])}.")
    has(f"OSM also has {rng(untyped)} crossings per route with no crossing type.")


def test_finding_6_speed_variability():
    cv = [float(SUMMARY[r]["speed_cv_weighted"]) for r in SHUTTLES]
    has(f"speed-band speed is {rng(cv, 2)} on the shuttle routes, against "
        f"{hu(SUMMARY['BUS-191']['speed_cv_weighted'], 2)} on BUS-191 and "
        f"{hu(SUMMARY['BUS-400']['speed_cv_weighted'], 2)} on BUS-400")
    n, days = speedband_days()
    has(f"This rests on {n} snapshots from {WORDS[len(days)]} weekdays")
    has(f"Speed bands cover only {n} snapshots on {WORDS[len(days)]} weekdays (28-29 Sep, 1-2 Oct and 15 Oct)")
    assert days == ["2026-09-28", "2026-09-29", "2026-10-01", "2026-10-02", "2026-10-15"]
    early = [d for d in days if d < "2026-10-10"]
    rows = [r for r in csv_rows(DATA / "derived" / "speedband_manifest.csv")
            if r["in_operating_window"] == "1" and r["sgt"][:10] in early]
    has(f"The {len(rows)} snapshots up to 3 Oct come from a private laptop archive")


def test_finding_7_incident_distance():
    routes = {r["id"]: r for r in read_json_gz(DATA / "derived" / "routes.json.gz")["routes"]}
    inc = next(r for r in csv_rows(DATA / "derived" / "incidents.csv") if r["source"] == "documented")
    p = Point(*to_xy(float(inc["lat"]), float(inc["lon"])))
    d = {rid: LineString([to_xy(a, b) for a, b in routes[rid]["latlon"]]).distance(p) for rid in SHUTTLES}
    assert round(d["PG-R1"]) == round(d["PG-R2"])
    has(f"Its location is {round(d['PG-R1'])} m from the Route 1 and Route 2 paths")
    assert d["PG-R3"] > 500


def test_finding_8_sensitivity():
    s = SENS["punggol_shuttles"]
    has(f"over {s['draws']} draws")
    has(f"is {hu(s['spearman_median'], 2)} (5th percentile {hu(s['spearman_p05'], 2)})")
    n = s["top_n"]
    has(f"The top-{n} segments keep a median {round(s['top_overlap_median'] * n)} of {n}, "
        f"with a 5th percentile of {round(s['top_overlap_p05'] * n)}.")


def test_method_numbers():
    v = VAL["routes"]
    ag = [f"{hu(100 * v[r]['map_agreement']['path_share_within_30m_of_map'])}/"
          f"{hu(100 * v[r]['map_agreement']['map_share_within_30m_of_path'])}%" for r in SHUTTLES]
    has(f"Agreement between path and map is {ag[0]} (R1), {ag[1]} (R2) and {ag[2]} (R3).")
    has(f"within {v['BUS-400']['length_gap_pct']:+.1f}% and {v['BUS-191']['length_gap_pct']:+.1f}% of DataMall's")
    snaps = [x for r in SHUTTLES for x in VAL["stop_snap_m"][r]]
    has(f"Snap distances are {rng(snaps)} m for shuttle stops")
    fit = json.loads((RESULTS / "trace_fit.json").read_text(encoding="utf-8"))
    has(f"The median residual is {rng([fit[r]['icp_median_m'] for r in SHUTTLES])} m.")
    has(f"The p90 is {rng([fit[r]['icp_p90_m'] for r in ('PG-R1', 'PG-R3')])} m on Routes 1 and 3 and "
        f"{hu(fit['PG-R2']['icp_p90_m'])} m on Route 2.")
    known = [100 * float(SUMMARY[r]["posted_known_share"]) for r in SHUTTLES]
    has(f"OSM posted-speed tags cover {rng(known)}% of the shuttle paths")


def test_run_it_counts(request):
    m = json.loads((RESULTS / "mutation.json").read_text(encoding="utf-8"))
    files = {p.name for p in (ROOT / "tests").glob("test_*.py")}
    collected = {item.path.name for item in request.session.items}
    if collected == files:  # only a full run sees every test
        has(f"python -m pytest -q # {len(request.session.items)} tests")
    has(f"python tools/mutation_check.py # {m['mutants']} deliberate bugs")
    has(f"The current run kills {m['killed']} of {m['mutants']}")
    assert m["killed"] == m["mutants"]
    # results/mutation.json must come from the current mutant list
    import importlib.util
    spec = importlib.util.spec_from_file_location("mutation_check", ROOT / "tools" / "mutation_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert [r["mutant"] for r in m["results"]] == [x[3] for x in mod.MUTANTS]
