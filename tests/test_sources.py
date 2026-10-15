"""Geocode matching, Annex A tracing/georeferencing, and route reconstruction on synthetic data."""
import math

import networkx as nx
import numpy as np
import pytest

from avready import geocode, network, trace
from avready.common import to_latlon


def r(searchval, blk, road, building="NIL"):
    return {"SEARCHVAL": searchval, "BLK_NO": blk, "ROAD_NAME": road, "BUILDING": building}


def test_geocode_pick_requires_block_and_road():
    res = [r("A", "234", "PUNGGOL FIELD"), r("B", "234", "SUMANG LANE")]
    assert geocode.pick("234 SUMANG LANE", res)["SEARCHVAL"] == "B"
    with pytest.raises(RuntimeError):
        geocode.pick("231 SUMANG LANE", res)


def test_geocode_pick_prefers_exact_name():
    res = [r("NKF DIALYSIS CENTRE ONE PUNGGOL", "1", "PUNGGOL DRIVE"), r("ONE PUNGGOL", "1", "PUNGGOL DRIVE")]
    assert geocode.pick("ONE PUNGGOL", res)["SEARCHVAL"] == "ONE PUNGGOL"
    res = [r("SAM KEE LRT STATION (PW1)", "10", "SENTUL CRESCENT")]
    assert geocode.pick("SAM KEE LRT STATION", res)["SEARCHVAL"].startswith("SAM KEE")


def test_route_pixels_drops_marker_discs_keeps_lines():
    img = np.full((200, 300, 3), 240, np.uint8)
    img[100:103, 20:280] = 0                       # 3 px line
    yy, xx = np.ogrid[:200, :300]
    img[(yy - 50) ** 2 + (xx - 150) ** 2 <= 17 ** 2] = 0   # marker disc
    img[:, 260:] = 0                                # legend panel area (dark), must be ignored
    pix = trace.route_pixels(img, panel_x=250)
    assert len(pix) > 0
    assert pix[:, 0].max() < 250                    # nothing from the panel
    assert not ((abs(pix[:, 0] - 150) < 10) & (abs(pix[:, 1] - 50) < 10)).any()   # disc removed
    assert ((pix[:, 1] >= 100) & (pix[:, 1] <= 102)).mean() > 0.95                 # line kept


def test_georeference_recovers_known_affine():
    rng = np.random.default_rng(3)
    # Roads: an L shape and a diagonal, in metres.
    t = np.linspace(0, 1, 400)
    roads = np.vstack([np.c_[t * 1000, 0 * t], np.c_[0 * t + 1000, t * 800], np.c_[t * 600, 200 + t * 500]])
    true = np.array([[4.8, 0.3], [-0.2, -4.9], [100.0, 4000.0]])        # pixel -> metres
    pix = (roads - true[2]) @ np.linalg.inv(true[:2])
    pix = pix + rng.normal(0, 0.3, pix.shape)
    markers = pix[[0, 399, 799, 1199]]
    stops = roads[[0, 399, 799, 1199]] + rng.normal(0, 40, (4, 2))       # stop positions 40 m off
    M, fit = trace.georeference(pix, markers, stops, roads)
    assert fit["icp_median_m"] < 3.0
    # Points can slide a little along straight roads (aperture problem), so check positions,
    # not parameters: pixels land within ~10 m of where they truly belong.
    err = np.linalg.norm(trace._apply(M, pix) - roads, axis=1)
    assert np.median(err) < 10.0 and err.max() < 15.0
    # ...and the road-matching step beats the marker-only fit it starts from.
    M0 = trace._affine_fit(markers, stops)
    err0 = np.linalg.norm(trace._apply(M0, pix) - roads, axis=1)
    assert np.median(err) < 0.5 * np.median(err0)


def test_reconstruct_loop_counts_each_edge_once():
    g = nx.DiGraph()
    xy = {1: (0, 0), 2: (100, 0), 3: (100, 100), 4: (0, 100)}
    for a, b in [(1, 2), (2, 3), (3, 4), (4, 1)]:       # one-way anticlockwise square
        L = math.dist(xy[a], xy[b])
        g.add_edge(a, b, length=L, weight=L, way=1, highway="residential")
    net = network.Network(aoi="t", graph=g, xy=xy, raw={"ways": [], "nodes": {}, "points": []})
    # stops on the left of travel: inside the square
    route = {"id": "SQ", "kind": "shuttle", "loop": True, "stops": []}
    stops = [{"name": "a", "lat": to_latlon(50, 5)[0], "lon": to_latlon(50, 5)[1]},
             {"name": "b", "lat": to_latlon(50, 95)[0], "lon": to_latlon(50, 95)[1]}]
    orig = network.route_stops
    network.route_stops = lambda route: stops
    try:
        rec = network.reconstruct(route, net, use_trace=False)
    finally:
        network.route_stops = orig
    assert rec["length_m"] == pytest.approx(400.0)
    assert rec["path"][0] == rec["path"][-1]


def test_oneway_rules():
    assert network._oneway({"oneway": "yes"}) == 1
    assert network._oneway({"oneway": "-1"}) == -1
    assert network._oneway({"junction": "roundabout"}) == 1
    assert network._oneway({"highway": "motorway"}) == 1
    assert network._oneway({"highway": "residential"}) == 0
