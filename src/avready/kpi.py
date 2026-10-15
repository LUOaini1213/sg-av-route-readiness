"""KPI calculations for AV trial operations, as specified in docs/KPI_DASHBOARD_SPEC.md.

Pure functions over two tables an operator would log (schemas in the spec):

trips:  trip_id, route_id, service_date, status ("operated" | "cancelled"),
        scheduled_departure, actual_departure (ISO datetimes, actual empty if cancelled),
        km_autonomous, km_manual, boardings, seats
events: event_id, trip_id, type ("disengagement" | "incident" | "remote_assist"),
        category (disengagement: "safety_critical" | "precautionary" | "planned";
                  incident: "1".."4", see the spec), initiated_by

No real trial data is used anywhere in this repository; tests use small hand-made tables.
"""
from __future__ import annotations

from datetime import datetime

OTP_EARLY_MIN = -1.0   # departure up to 1 min early ...
OTP_LATE_MIN = 3.0     # ... or up to 3 min late counts as on time (proposed; agree with the operator)


def _minutes(a: str, b: str) -> float:
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 60.0


def disengagements_per_100km(trips: list[dict], events: list[dict], include_planned: bool = False) -> float | None:
    """Unplanned disengagements per 100 km driven in autonomous mode."""
    km = sum(float(t["km_autonomous"]) for t in trips if t["status"] == "operated")
    if km <= 0:
        return None
    n = sum(1 for e in events if e["type"] == "disengagement" and (include_planned or e["category"] != "planned"))
    return 100.0 * n / km


def safety_critical_per_100km(trips: list[dict], events: list[dict]) -> float | None:
    km = sum(float(t["km_autonomous"]) for t in trips if t["status"] == "operated")
    if km <= 0:
        return None
    n = sum(1 for e in events if e["type"] == "disengagement" and e["category"] == "safety_critical")
    return 100.0 * n / km


def km_between_disengagements(trips: list[dict], events: list[dict]) -> float | None:
    km = sum(float(t["km_autonomous"]) for t in trips if t["status"] == "operated")
    n = sum(1 for e in events if e["type"] == "disengagement" and e["category"] != "planned")
    return None if n == 0 else km / n


def on_time_performance(trips: list[dict], early: float = OTP_EARLY_MIN, late: float = OTP_LATE_MIN) -> float | None:
    """Share of operated trips whose departure deviation is within [early, late] minutes."""
    ops = [t for t in trips if t["status"] == "operated" and t.get("actual_departure")]
    if not ops:
        return None
    ok = sum(1 for t in ops if early <= _minutes(t["scheduled_departure"], t["actual_departure"]) <= late)
    return ok / len(ops)


def availability(trips: list[dict]) -> float | None:
    """Operated trips / scheduled trips."""
    return None if not trips else sum(1 for t in trips if t["status"] == "operated") / len(trips)


def manual_km_share(trips: list[dict]) -> float | None:
    ops = [t for t in trips if t["status"] == "operated"]
    auto = sum(float(t["km_autonomous"]) for t in ops)
    man = sum(float(t["km_manual"]) for t in ops)
    return None if auto + man == 0 else man / (auto + man)


def incidents_by_severity(events: list[dict]) -> dict[str, int]:
    out = {"1": 0, "2": 0, "3": 0, "4": 0}
    for e in events:
        if e["type"] == "incident":
            out[str(e["category"])] += 1
    return out


def incidents_per_10k_km(trips: list[dict], events: list[dict]) -> float | None:
    ops = [t for t in trips if t["status"] == "operated"]
    km = sum(float(t["km_autonomous"]) + float(t["km_manual"]) for t in ops)
    if km <= 0:
        return None
    return 10000.0 * sum(1 for e in events if e["type"] == "incident") / km


def ridership(trips: list[dict]) -> dict:
    ops = [t for t in trips if t["status"] == "operated"]
    boardings = sum(int(t["boardings"]) for t in ops)
    seats = sum(int(t["seats"]) for t in ops)
    days = {t["service_date"] for t in ops}
    return {
        "boardings": boardings,
        "boardings_per_operated_trip": None if not ops else boardings / len(ops),
        "boardings_per_service_day": None if not days else boardings / len(days),
        "seat_occupancy": None if seats == 0 else boardings / seats,
    }


def kpi_table(trips: list[dict], events: list[dict]) -> dict:
    """All headline KPIs for one reporting period."""
    return {
        "disengagements_per_100km": disengagements_per_100km(trips, events),
        "safety_critical_per_100km": safety_critical_per_100km(trips, events),
        "km_between_disengagements": km_between_disengagements(trips, events),
        "on_time_performance": on_time_performance(trips),
        "availability": availability(trips),
        "manual_km_share": manual_km_share(trips),
        "incidents_by_severity": incidents_by_severity(events),
        "incidents_per_10k_km": incidents_per_10k_km(trips, events),
        **ridership(trips),
    }
