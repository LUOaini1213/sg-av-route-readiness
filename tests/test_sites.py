"""Route-level site counts: a junction on a segment boundary is one site, not two."""
import networkx as nx
from shapely.geometry import LineString, Point

from avready import network, profile
from avready.common import scoring_config


def straight_road():
    """Nodes every 125 m along the x axis, eastbound, one way 1."""
    g = nx.DiGraph()
    xy = {i: (125.0 * i, 0.0) for i in range(5)}
    for a in range(4):
        g.add_edge(a, a + 1, length=125.0, weight=125.0, way=1, highway="primary")
    raw = {"ways": [{"id": 1, "tags": {"highway": "primary", "name": "Test Road"}}], "nodes": {}, "points": []}
    return network.Network(aoi="t", graph=g, xy=xy, raw=raw)


def empty_layers():
    return profile.Layers([], {}, [], [], [], [], [], [], [], [], [], [])


def features(net, layers):
    cfg = scoring_config()
    segs = profile.cut_segments(profile.path_edges([0, 1, 2, 3, 4], net), cfg["segment_length_m"])
    assert len(segs) == 2 and segs[0][-1]["v"] == 2 == segs[1][0]["u"]  # boundary at node 2 (x = 250 m)
    return [profile.segment_features(s, net, layers, cfg, set(), []) for s in segs]


def test_light_next_to_a_segment_boundary_counts_once():
    net = straight_road()
    layers = empty_layers()
    layers.lta_lights.append(Point(255.0, 5.0))      # 5 m from the boundary node: in both buffers
    layers.osm_node_tags[2] = {"highway": "traffic_signals"}  # the boundary node itself
    layers.bus_stops.append((Point(250.0, 6.0), "99999"))     # kerb side (left of eastbound)
    f = features(net, layers)
    # Each segment sees the site (exposure for the register) ...
    assert [x["signal_sites"] for x in f] == [1, 1]
    assert [x["signal_sites_lta"] for x in f] == [1, 1]
    assert [x["bus_stops"] for x in f] == [1, 1]
    # ... but the route has one site and one stop.
    t = profile.route_site_totals([x["_sites"] for x in f])
    assert t["signal_sites"] == 1
    assert t["signal_sites_lta"] == 1
    assert t["signal_sites_osm"] == 1
    assert t["bus_stops"] == 1


def test_distinct_sites_either_side_of_a_boundary_stay_distinct():
    net = straight_road()
    layers = empty_layers()
    layers.lta_lights += [Point(60.0, 5.0), Point(440.0, 5.0)]
    layers.lta_crossings.append(LineString([(250.0, -8.0), (250.0, 8.0)]))
    f = features(net, layers)
    assert [x["signal_sites"] for x in f] == [1, 1]
    t = profile.route_site_totals([x["_sites"] for x in f])
    assert t["signal_sites"] == 2
    assert t["crossings_lta"] == 1


def test_lights_of_one_junction_split_by_the_boundary_are_one_site():
    # Two different lights 36 m apart (under the 40 m cluster radius), one only in each segment.
    net = straight_road()
    layers = empty_layers()
    layers.lta_lights += [Point(232.0, 15.0), Point(268.0, 15.0)]
    f = features(net, layers)
    assert [x["signal_sites_lta"] for x in f] == [1, 1]
    assert profile.route_site_totals([x["_sites"] for x in f])["signal_sites"] == 1


def test_second_pass_in_a_later_segment_counts_again():
    a = profile.site_clusters([(("lta", 7), Point(0, 0))], 40)
    empty = profile.site_clusters([], 40)
    assert profile.route_site_count([a, a]) == 1          # adjacent: same site
    assert profile.route_site_count([a, empty, a]) == 2   # the vehicle comes back later
