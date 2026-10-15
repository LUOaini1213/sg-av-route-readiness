"""Turn segment profiles into a risk register (hazard x segment rows) and route summaries."""
from __future__ import annotations

import math

import numpy as np

# Which segment field measures exposure to each hazard.
EXPOSURE = {
    "unprotected_right_turn": "right_turns_unsignalised",
    "signal_controlled_site": "signal_sites",
    "uncontrolled_crossing": "crossings_uncontrolled_osm",
    "signalised_crossing": "crossings_signalised_osm",
    "school_zone": "school_zone_m",
    "silver_zone": "silver_zone_m",
    "roundabout": "roundabouts",
    "high_speed_road": "high_speed_m",
    "multi_lane": "multi_lane_m",
    "bus_stop_interaction": "bus_stops",
    "service_road": "service_road_m",
    "speed_variability": "speed_cv",
    "recorded_incident": "incidents_nearby",
}

# Proposed controls. They are written for use in a trial and have not been used.
MITIGATION = {
    "unprotected_right_turn": (
        "Validate unprotected right-turn behaviour at this junction in familiarisation runs (gap acceptance, "
        "creep, abort); consider a route variant that replaces the right turn with left turns, or ask the "
        "road authority about a signal-controlled turn.", "AV developer; road authority for any junction change"),
    "signal_controlled_site": (
        "Check traffic-light recognition at every approach in different light and rain; log stop-line overruns "
        "and late braking per junction; consider signal-phase data feed if available.", "AV developer"),
    "uncontrolled_crossing": (
        "Mandatory slow-down zone and yield logic validated with staged pedestrians; record near-misses per "
        "crossing; brief safety operators on this location.", "AV operator (safety lead)"),
    "signalised_crossing": (
        "Verify pedestrian-phase detection and late-crosser handling; include in familiarisation checklist.",
        "AV developer"),
    "school_zone": (
        "Reduce operating speed in school-zone hours; avoid scheduling trips at school arrival/dismissal peaks "
        "until performance is shown; notify the school.", "AV operator; Deployment Ops for school liaison"),
    "silver_zone": (
        "Lower speed cap and longer yield margins; notify the Town Council and community centre.",
        "AV operator; Deployment Ops for community liaison"),
    "roundabout": (
        "Validate entry gap acceptance and yielding to circulating traffic; define a takeover rule if the "
        "vehicle waits longer than a set time.", "AV developer"),
    "high_speed_road": (
        "Assess speed differential with following traffic; consider a minimum operating speed, hazard lights "
        "policy, or a route that avoids the section.", "Deployment Ops with AV operator"),
    "multi_lane": (
        "Plan lane position in advance of turns; validate merges and lane changes at peak-hour density.",
        "AV developer"),
    "bus_stop_interaction": (
        "Agree kerb-space rules with the bus operator; validate overtaking of stopped buses and pedestrian "
        "emergence from behind buses.", "Deployment Ops with bus operator"),
    "service_road": (
        "Confirm the service road is part of the approved route; geofence other service roads; watch for "
        "reversing and parked vehicles.", "AV operator; Deployment Ops for route approval"),
    "speed_variability": (
        "Build running-time buffers from observed speed spread; monitor on-time performance for this segment.",
        "AV operator (service planning)"),
    "recorded_incident": (
        "Review the recorded incident with the operator; confirm the corrective action is in the SOP and "
        "re-test the location.", "Deployment Ops with AV operator"),
}

EXISTING_CONTROL = ("Safety operator on board at all times (LTA news release, 20 Sep 2025); real-time monitoring "
                    "of all shuttles (same release)")


def likelihood(value, bands) -> int:
    """Number of band thresholds the exposure meets; 0 = hazard not present on the segment."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0
    return sum(1 for b in bands if value >= b)


def rating(score: int, rating_bands) -> str:
    label = "None"
    for threshold, name in rating_bands:
        if score >= threshold:
            label = name
    return label


def register_rows(route: dict, segments: list[dict], cfg: dict) -> list[dict]:
    rows = []
    for seg in segments:
        for hz, spec in cfg["hazards"].items():
            val = seg[EXPOSURE[hz]]
            L = likelihood(val, spec["bands"])
            if L == 0:
                continue
            S = spec["severity"]
            mit, owner = MITIGATION[hz]
            rows.append({
                "risk_id": f'{seg["segment_id"]}-{hz}',
                "route_id": route["id"],
                "segment_id": seg["segment_id"],
                "chainage_m": f'{seg["start_m"]:.0f}-{seg["end_m"]:.0f}',
                "location": seg["main_road"],
                "hazard": hz,
                "hazard_description": spec["label"],
                "exposure": val,
                "exposure_field": EXPOSURE[hz],
                "likelihood": L,
                "severity": S,
                "score": L * S,
                "rating": rating(L * S, cfg["rating_bands"]),
                "existing_control": EXISTING_CONTROL,
                "proposed_mitigation": mit,
                "owner": owner,
                "status": "Proposed (desk assessment, not field-verified)",
            })
    return rows


def segment_scores(segments: list[dict], cfg: dict, severity_mult=None, band_mult=None) -> np.ndarray:
    out = []
    for seg in segments:
        total = 0.0
        for hz, spec in cfg["hazards"].items():
            bands = spec["bands"] if band_mult is None else [b * band_mult[hz] for b in spec["bands"]]
            sev = spec["severity"] if severity_mult is None else spec["severity"] * severity_mult[hz]
            total += likelihood(seg[EXPOSURE[hz]], bands) * sev
        out.append(total)
    return np.asarray(out)


def _rank(a: np.ndarray) -> np.ndarray:
    order = np.argsort(-a, kind="stable")
    r = np.empty(len(a))
    r[order] = np.arange(len(a))
    return r


def sensitivity(segments: list[dict], cfg: dict, draws: int = 500, seed: int = 0, top: int = 10) -> dict:
    """Perturb every severity by x0.5-1.5 and every band threshold by x0.75-1.25 and see how
    the segment ranking moves (Spearman rho against the base ranking; overlap of the top-N)."""
    rng = np.random.default_rng(seed)
    base = segment_scores(segments, cfg)
    base_top = set(np.argsort(-base, kind="stable")[:top])
    rhos, overlaps = [], []
    hz = list(cfg["hazards"])
    for _ in range(draws):
        sm = dict(zip(hz, rng.uniform(0.5, 1.5, len(hz))))
        bm = dict(zip(hz, rng.uniform(0.75, 1.25, len(hz))))
        s = segment_scores(segments, cfg, sm, bm)
        rb, rs = _rank(base), _rank(s)
        rhos.append(float(np.corrcoef(rb, rs)[0, 1]))
        overlaps.append(len(base_top & set(np.argsort(-s, kind="stable")[:top])) / top)
    return {"draws": draws, "top_n": top, "spearman_median": round(float(np.median(rhos)), 3),
            "spearman_p05": round(float(np.percentile(rhos, 5)), 3),
            "top_overlap_median": round(float(np.median(overlaps)), 3),
            "top_overlap_p05": round(float(np.percentile(overlaps, 5)), 3)}
