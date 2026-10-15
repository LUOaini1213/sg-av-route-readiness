"""Geometry primitives: headings, turn sign (left-hand traffic), kerb side, segmenting."""
import math

import networkx as nx
import pytest
from shapely.geometry import LineString, Point

from avready.common import bearing_deg, to_latlon, to_xy, turn_angle
from avready import network, profile


def test_bearing_compass_convention():
    assert bearing_deg(0, 0, 0, 10) == pytest.approx(0.0)      # north
    assert bearing_deg(0, 0, 10, 0) == pytest.approx(90.0)     # east
    assert bearing_deg(0, 0, 0, -10) == pytest.approx(180.0)   # south
    assert bearing_deg(0, 0, -10, 0) == pytest.approx(270.0)   # west


def test_turn_angle_right_is_positive():
    # Heading north then east is a right turn (clockwise): +90.
    assert turn_angle(0, 90) == pytest.approx(90)
    assert turn_angle(0, 270) == pytest.approx(-90)
    assert turn_angle(350, 20) == pytest.approx(30)
    assert turn_angle(20, 350) == pytest.approx(-30)


def test_svy21_roundtrip_and_scale():
    x, y = to_xy(1.4, 103.9)
    lat, lon = to_latlon(x, y)
    assert lat == pytest.approx(1.4, abs=1e-9) and lon == pytest.approx(103.9, abs=1e-9)
    # 0.001 deg of latitude is about 110.6 m near the equator.
    x2, y2 = to_xy(1.401, 103.9)
    assert math.hypot(x2 - x, y2 - y) == pytest.approx(110.6, abs=0.5)


def test_left_of_kerb_side():
    line = LineString([(0, 0), (0, 100)])          # travelling north
    assert profile.left_of(line, Point(-5, 50))    # west = left
    assert not profile.left_of(line, Point(5, 50))


def _edges(lengths):
    return [{"u": i, "v": i + 1, "length": L, "highway": "residential", "tags": {}} for i, L in enumerate(lengths)]


def test_cut_segments_groups_and_merges_short_tail():
    segs = profile.cut_segments(_edges([100, 100, 100, 100, 100, 40]), 250)
    # 300 closes the first, then 200+40 < 250 left over and >= 125 -> its own segment.
    assert [sum(e["length"] for e in s) for s in segs] == [300, 240]
    segs = profile.cut_segments(_edges([100, 100, 100, 50]), 250)
    # remainder 50 < 125 merges into the previous segment
    assert [sum(e["length"] for e in s) for s in segs] == [350]
    segs = profile.cut_segments(_edges([100, 100, 100, 100]), 250)
    # remainder 100 is under half the target (125), so it merges too
    assert [sum(e["length"] for e in s) for s in segs] == [400]


def test_direction_lanes_and_speed_parsing():
    assert profile.direction_lanes({"lanes": "3", "oneway": "yes"}) == 3
    assert profile.direction_lanes({"lanes": "4"}) == 2
    assert profile.direction_lanes({"lanes": "5", "lanes:forward": "3"}) == 3
    assert profile.direction_lanes({"lanes": "1"}) == 1
    assert profile.direction_lanes({}) is None
    assert profile.posted_speed({"maxspeed": "60"}) == 60
    assert profile.posted_speed({"maxspeed": "SG:urban"}) is None


def test_crossing_kind():
    assert profile.crossing_kind({"highway": "crossing", "crossing": "traffic_signals"}) == "signalised"
    assert profile.crossing_kind({"highway": "crossing", "crossing": "zebra"}) == "uncontrolled"
    assert profile.crossing_kind({"highway": "crossing", "crossing": "unmarked"}) == "uncontrolled"
    assert profile.crossing_kind({"highway": "crossing"}) == "untyped"
    assert profile.crossing_kind({"highway": "crossing", "crossing": "no"}) is None
    assert profile.crossing_kind({"highway": "bus_stop"}) is None


def test_cluster_count_chains():
    pts = [Point(0, 0), Point(30, 0), Point(60, 0), Point(200, 0)]
    assert profile.cluster_count(pts, 40) == 2
    assert profile.cluster_count(pts, 25) == 4
    assert profile.cluster_count([], 40) == 0


# ------------------------------------------------------------- synthetic road network

def grid_network():
    """A plus-shaped junction at (0,0) with arms 200 m long, two-way, plus a one-way arm."""
    g = nx.DiGraph()
    xy = {0: (0, 0), 1: (0, -200), 2: (0, 200), 3: (200, 0), 4: (-200, 0), 5: (0, -100), 6: (100, 0),
          7: (-100, 0), 8: (0, 100)}
    def add(a, b, hw="residential", way=1):
        L = math.dist(xy[a], xy[b])
        g.add_edge(a, b, length=L, weight=L, way=way, highway=hw)
    for a, b, w in [(1, 5, 10), (5, 0, 10), (0, 8, 11), (8, 2, 11), (4, 7, 12), (7, 0, 12), (0, 6, 13), (6, 3, 13)]:
        add(a, b, way=w)
        add(b, a, way=w)
    return network.Network(aoi="t", graph=g, xy=xy, raw={"ways": [], "nodes": {}, "points": []})


def test_snap_kerbside_prefers_left_side_edge():
    net = grid_network()
    # A point 5 m east of the north arm: travelling south (8->0) has it on the left.
    lat, lon = to_latlon(5, 50)
    (u, v), d = network.snap_kerbside(net, lat, lon)
    assert (u, v) == (8, 0)
    assert d == pytest.approx(5, abs=1e-6)
    lat, lon = to_latlon(-5, 50)
    (u, v), _ = network.snap_kerbside(net, lat, lon)
    assert (u, v) == (0, 8)


def test_route_turns_right_unsignalised_and_left():
    net = grid_network()
    layers = profile.Layers([], {}, [], [], [], [], [], [], [], [], [], [])
    cfg = {"turn_deg": 45, "buffers_m": {"junction_signal": 35}}
    junctions = profile.junction_nodes(net)
    assert 0 in junctions
    # South arm heading north, then turn east: right turn across oncoming traffic.
    turns = profile.route_turns([1, 5, 0, 6, 3], net, layers, cfg, junctions)
    assert [t["kind"] for t in turns] == ["right"]
    assert turns[0]["signalised"] is False
    assert turns[0]["angle"] == pytest.approx(90, abs=1)
    turns = profile.route_turns([1, 5, 0, 7, 4], net, layers, cfg, junctions)
    assert [t["kind"] for t in turns] == ["left"]
    # A light 20 m from the junction makes it signalised.
    layers.lta_lights.append(Point(20, 0))
    turns = profile.route_turns([1, 5, 0, 6, 3], net, layers, cfg, junctions)
    assert turns[0]["signalised"] is True and turns[0]["signal_source"] == "lta only"
    # Straight through: no turn.
    assert profile.route_turns([1, 5, 0, 8, 2], net, layers, cfg, junctions) == []


def test_heading_change_uses_window():
    xy = [(0, 0), (0, 10), (0, 20), (10, 20), (20, 20)]
    assert profile.heading_change(xy, 2, 15) == pytest.approx(90)
    assert profile.heading_change(xy, 0, 15) == 0.0


def test_bend_without_junction_is_not_a_turn():
    g = nx.DiGraph()
    xy = {1: (0, 0), 2: (0, 100), 3: (100, 100)}
    for a, b in [(1, 2), (2, 3)]:
        L = math.dist(xy[a], xy[b])
        g.add_edge(a, b, length=L, weight=L, way=1, highway="residential")
        g.add_edge(b, a, length=L, weight=L, way=1, highway="residential")
    net = network.Network(aoi="t", graph=g, xy=xy, raw={"ways": [], "nodes": {}, "points": []})
    layers = profile.Layers([], {}, [], [], [], [], [], [], [], [], [], [])
    cfg = {"turn_deg": 45, "buffers_m": {"junction_signal": 35}}
    assert profile.junction_nodes(net) == set()
    assert profile.route_turns([1, 2, 3], net, layers, cfg, set()) == []
