"""Risk scoring, speed-band statistics and KPI formulas, checked against hand-computed values."""
import math
from datetime import datetime

import pandas as pd
import pytest

from avready import kpi, risk, speedbands
from avready.common import scoring_config

CFG = scoring_config()


# ---------------------------------------------------------------- risk

def test_likelihood_counts_thresholds_met():
    bands = [0.5, 1, 2, 3, 4]
    assert risk.likelihood(0, bands) == 0
    assert risk.likelihood(1, bands) == 2
    assert risk.likelihood(2.5, bands) == 3
    assert risk.likelihood(4, bands) == 5
    assert risk.likelihood(None, bands) == 0
    assert risk.likelihood(float("nan"), bands) == 0


def test_rating_bands_boundaries():
    rb = CFG["rating_bands"]
    assert risk.rating(4, rb) == "Low"
    assert risk.rating(5, rb) == "Medium"
    assert risk.rating(9, rb) == "Medium"
    assert risk.rating(10, rb) == "High"
    assert risk.rating(16, rb) == "High"
    assert risk.rating(17, rb) == "Very high"
    assert risk.rating(0, rb) == "None"


def _segment(**over):
    base = {k: 0 for k in risk.EXPOSURE.values()}
    base["speed_cv"] = None
    base.update(segment_id="X-S01", start_m=0.0, end_m=250.0, main_road="Test Road")
    base.update(over)
    return base


def test_register_rows_only_for_present_hazards_with_owner():
    seg = _segment(right_turns_unsignalised=1, school_zone_m=180.0)
    rows = risk.register_rows({"id": "X"}, [seg], CFG)
    by = {r["hazard"]: r for r in rows}
    assert set(by) == {"unprotected_right_turn", "school_zone"}
    assert by["unprotected_right_turn"]["likelihood"] == 2 and by["unprotected_right_turn"]["severity"] == 4
    assert by["unprotected_right_turn"]["score"] == 8 and by["unprotected_right_turn"]["rating"] == "Medium"
    # 180 m in a school zone meets thresholds 1, 50, 100, 175 -> L4, S5 -> 20 Very high
    assert by["school_zone"]["score"] == 20 and by["school_zone"]["rating"] == "Very high"
    for r in rows:
        assert r["owner"] and r["proposed_mitigation"] and r["status"].startswith("Proposed")


def test_segment_scores_sum_over_hazards():
    seg = _segment(right_turns_unsignalised=1, school_zone_m=180.0, speed_cv=0.3)
    # 8 (right turn) + 20 (school zone) + speed cv 0.3 -> thresholds 0.15, 0.25 met -> L2 x S2 = 4
    assert risk.segment_scores([seg], CFG)[0] == 32


def test_sensitivity_identical_segments_are_stable():
    segs = [_segment(segment_id=f"S{i}", right_turns_unsignalised=i % 3, school_zone_m=60.0 * i) for i in range(12)]
    out = risk.sensitivity(segs, CFG, draws=50, seed=1, top=3)
    assert 0.0 < out["spearman_median"] <= 1.0
    assert out["draws"] == 50


# ---------------------------------------------------------------- speed bands

def test_band_speed_midpoints_and_band8():
    df = pd.DataFrame({"SpeedBand": [1, 3, 8], "MinimumSpeed": [0, 20, 70], "MaximumSpeed": [9, 29, 999]})
    out = speedbands.band_speed(df, 75.0).tolist()
    assert out == [4.5, 24.5, 75.0]


def test_link_stats_cv_and_slow_share():
    s = speedbands.link_stats({7: [10.0, 30.0, 30.0, 30.0]}, 20.0)[7]
    assert s["n_obs"] == 4
    assert s["mean_kmh"] == 25.0
    assert s["std_kmh"] == pytest.approx(math.sqrt(75), abs=0.01)
    assert s["cv"] == pytest.approx(math.sqrt(75) / 25, abs=1e-4)
    assert s["p_slow"] == 0.25


def test_operating_window():
    win = CFG["speedband"]["operating_window"]
    assert speedbands.in_window(datetime(2026, 10, 3, 9, 30), win)        # Saturday 09:30
    assert not speedbands.in_window(datetime(2026, 10, 4, 12, 0), win)    # Sunday
    assert speedbands.in_window(datetime(2026, 9, 28, 17, 30), win)       # Monday 17:30
    assert not speedbands.in_window(datetime(2026, 9, 28, 17, 31), win)
    assert not speedbands.in_window(datetime(2026, 9, 28, 9, 29), win)
    assert not speedbands.in_window(datetime(2026, 11, 9, 12, 0), win)    # Deepavali holiday (Mon)
    with pytest.raises(ValueError):
        speedbands.in_window(datetime(2026, 8, 3, 12, 0), win)


# ---------------------------------------------------------------- KPIs

TRIPS = [
    # trip, status, sched, actual, km_auto, km_manual, boardings, seats, date
    ("T1", "operated", "2026-01-05T10:00", "2026-01-05T10:02", 9.0, 1.0, 3, 5, "2026-01-05"),
    ("T2", "operated", "2026-01-05T11:00", "2026-01-05T11:05", 10.0, 0.0, 5, 5, "2026-01-05"),
    ("T3", "operated", "2026-01-06T10:00", "2026-01-06T09:58", 6.0, 4.0, 0, 5, "2026-01-06"),
    ("T4", "cancelled", "2026-01-06T11:00", "", 0.0, 0.0, 0, 5, "2026-01-06"),
]
TRIPS = [dict(zip(["trip_id", "status", "scheduled_departure", "actual_departure", "km_autonomous", "km_manual",
                   "boardings", "seats", "service_date"], t), route_id="R") for t in TRIPS]
EVENTS = [
    {"event_id": "E1", "trip_id": "T1", "type": "disengagement", "category": "safety_critical", "initiated_by": "safety_operator"},
    {"event_id": "E2", "trip_id": "T2", "type": "disengagement", "category": "precautionary", "initiated_by": "safety_operator"},
    {"event_id": "E3", "trip_id": "T3", "type": "disengagement", "category": "planned", "initiated_by": "system"},
    {"event_id": "E4", "trip_id": "T3", "type": "incident", "category": "1", "initiated_by": ""},
]


def test_kpis_hand_computed():
    # autonomous km on operated trips = 9 + 10 + 6 = 25; unplanned disengagements = 2
    assert kpi.disengagements_per_100km(TRIPS, EVENTS) == pytest.approx(8.0)
    assert kpi.disengagements_per_100km(TRIPS, EVENTS, include_planned=True) == pytest.approx(12.0)
    assert kpi.safety_critical_per_100km(TRIPS, EVENTS) == pytest.approx(4.0)
    assert kpi.km_between_disengagements(TRIPS, EVENTS) == pytest.approx(12.5)
    # deviations +2 (on time), +5 (late), -2 (early beyond -1) -> 1/3
    assert kpi.on_time_performance(TRIPS) == pytest.approx(1 / 3)
    assert kpi.on_time_performance(TRIPS, early=-2, late=5) == pytest.approx(1.0)
    assert kpi.availability(TRIPS) == pytest.approx(0.75)
    assert kpi.manual_km_share(TRIPS) == pytest.approx(5 / 30)
    assert kpi.incidents_by_severity(EVENTS) == {"1": 1, "2": 0, "3": 0, "4": 0}
    assert kpi.incidents_per_10k_km(TRIPS, EVENTS) == pytest.approx(10000 / 30)
    r = kpi.ridership(TRIPS)
    assert r["boardings"] == 8
    assert r["boardings_per_operated_trip"] == pytest.approx(8 / 3)
    assert r["boardings_per_service_day"] == pytest.approx(4.0)
    assert r["seat_occupancy"] == pytest.approx(8 / 15)


def test_kpis_empty_inputs_are_none():
    assert kpi.disengagements_per_100km([], []) is None
    assert kpi.on_time_performance([]) is None
    assert kpi.availability([]) is None
    assert kpi.km_between_disengagements(TRIPS, []) is None
