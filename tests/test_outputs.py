"""Checks on the committed outputs: internal consistency and the geometry validation."""
import csv
import json

import pytest

from avready.common import DATA, OUTPUTS, RESULTS, read_json_gz, routes_config


def rows(name):
    with open(OUTPUTS / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_shuttle_reconstruction_within_ten_percent_of_published_length():
    val = json.loads((RESULTS / "validation.json").read_text(encoding="utf-8"))["routes"]
    for rid in ("PG-R1", "PG-R2", "PG-R3"):
        assert abs(val[rid]["length_gap_pct"]) <= 10, rid
        assert val[rid]["method"] == "map-guided"
        assert val[rid]["map_agreement"]["path_share_within_30m_of_map"] >= 0.75, rid


def test_segments_tile_each_route():
    routes = {r["id"]: r for r in read_json_gz(DATA / "derived" / "routes.json.gz")["routes"]}
    segs = rows("segments.csv")
    for rid, r in routes.items():
        mine = [s for s in segs if s["route_id"] == rid]
        assert sum(float(s["length_m"]) for s in mine) == pytest.approx(r["length_m"], abs=1.0)
        ends = [(float(s["start_m"]), float(s["end_m"])) for s in mine]
        for (a0, a1), (b0, b1) in zip(ends[:-1], ends[1:]):
            assert b0 == pytest.approx(a1, abs=0.2)


def test_summary_matches_segments():
    """Turns are route events assigned to one segment each, so they add up. Point sites
    (signals, crossings, bus stops) near a segment boundary appear in both segments, so
    the route counts them once: at most the segment sum, at least the largest segment."""
    segs = rows("segments.csv")
    val = json.loads((RESULTS / "validation.json").read_text(encoding="utf-8"))["osm_vs_lta"]
    for s in rows("route_summary.csv"):
        mine = [x for x in segs if x["route_id"] == s["route_id"]]
        for k in ("right_turns_unsignalised", "right_turns_signalised", "left_turns"):
            assert int(s[k]) == sum(int(x[k]) for x in mine), (s["route_id"], k)
        for k in ("signal_sites", "crossings_uncontrolled_osm", "crossings_lta", "bus_stops", "roundabouts"):
            col = [int(x[k]) for x in mine]
            assert max(col) <= int(s[k]) <= sum(col), (s["route_id"], k)
        assert int(s["signal_sites"]) == val[s["route_id"]]["signal_sites_union"]
        assert int(s["crossings_lta"]) == val[s["route_id"]]["crossings_lta"]
        km = float(s["reconstructed_km"])
        assert float(s["signal_sites_per_km"]) == pytest.approx(int(s["signal_sites"]) / km, abs=0.01)
    # The fix is visible in the committed data: boundary junctions exist on every route.
    for s in rows("route_summary.csv"):
        mine = [x for x in segs if x["route_id"] == s["route_id"]]
        assert int(s["signal_sites"]) < sum(int(x["signal_sites"]) for x in mine), s["route_id"]


def test_register_rows_are_complete_and_consistent():
    reg = rows("risk_register.csv")
    assert reg
    for r in reg:
        assert int(r["score"]) == int(r["likelihood"]) * int(r["severity"])
        assert 1 <= int(r["likelihood"]) <= 5 and 1 <= int(r["severity"]) <= 5
        assert r["owner"] and r["proposed_mitigation"]


def test_documented_incident_is_near_routes_1_and_2_only():
    reg = rows("risk_register.csv")
    hit = {r["route_id"] for r in reg if r["hazard"] == "recorded_incident"}
    assert hit == {"PG-R1", "PG-R2"}


def test_every_route_in_config_has_outputs():
    ids = {r["id"] for r in routes_config()["routes"]}
    assert ids == {s["route_id"] for s in rows("route_summary.csv")}


@pytest.mark.parametrize("rid", ["PG-R1", "PG-R2", "PG-R3"])
def test_reconstruction_from_committed_inputs(rid):
    """Rebuild a shuttle route from the committed OSM clip and Annex A trace (R2 and R3 also
    use shape points) and check it against the published length and the traced map."""
    from avready import build, network

    route = next(r for r in routes_config()["routes"] if r["id"] == rid)
    net = network.build("punggol", "shuttle")
    rec = network.reconstruct(route, net)
    assert abs(rec["length_m"] / 1000 / route["official_length_km"] - 1) <= 0.10
    agree = build.trace_agreement([net.xy[n] for n in rec["path"]], network.load_trace(rid))
    assert agree["path_share_within_30m_of_map"] >= 0.78
    shortest = network.reconstruct(route, net, use_trace=False)
    assert shortest["length_m"] <= rec["length_m"] + 1e-6
