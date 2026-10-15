# KPI dashboard spec: AV trial operations

A specification for the dashboard a deployment team would watch during a trial. The
formulas are implemented and tested in [`src/avready/kpi.py`](../src/avready/kpi.py).
No trial data is used in this repository, and the amber/red levels below are starting
points to agree with the operator, not LTA targets.

## Input tables (logged by the operator)

**trips**: one row per scheduled trip.

| Field | Type | Notes |
|---|---|---|
| trip_id | text | |
| route_id | text | e.g. `PG-R1` |
| service_date | date | |
| status | `operated` / `cancelled` | |
| scheduled_departure, actual_departure | datetime | first stop; actual empty if cancelled |
| km_autonomous, km_manual | number | from the vehicle log, per trip |
| boardings | integer | |
| seats | integer | passenger seats on the vehicle used |

**events**: one row per event.

| Field | Type | Notes |
|---|---|---|
| event_id, trip_id | text | |
| type | `disengagement` / `incident` / `remote_assist` | |
| category | disengagement: `safety_critical` / `precautionary` / `planned`; incident: tier `1`-`4` (see readiness checklist) | |
| initiated_by | `system` / `safety_operator` / `remote` | |
| segment_id | text | from `outputs/segments.csv`, so events map to the risk register |

## Headline KPIs

| KPI | Formula | Why | Amber / red (proposed) |
|---|---|---|---|
| Disengagements per 100 km | unplanned disengagements / autonomous km x 100 | System maturity on this route | rising 3 weeks running / any week above 2x the familiarisation baseline |
| Safety-critical disengagements per 100 km | safety-critical only | The subset that matters for safety | any increase / any week above familiarisation baseline |
| Autonomous km between disengagements | autonomous km / unplanned disengagements | Same, easier to explain to non-specialists | |
| On-time performance | operated trips departing between 1 min early and 3 min late / operated trips with an actual time | Reliability as riders see it; window is a parameter | below 90% / below 80% |
| Availability | operated trips / scheduled trips | Cancelled trips hide behind good OTP | below 95% / below 90% |
| Manual km share | manual km / all km | How much of the service is not autonomous | |
| Incidents by tier | count per tier | Safety outcomes | any tier 2+ is red |
| Incidents per 10,000 km | incidents / all km x 10,000 | Comparable across routes | |
| Boardings per service day | boardings / days with service | Demand | |
| Boardings per operated trip; boardings per seat-trip | | Load, and whether vehicle size fits | |

## Panels

1. **Today**: trips operated vs scheduled, current OTP, open incidents, vehicles in service.
2. **Safety trend** (weekly): disengagements per 100 km, split safety-critical / precautionary;
   incidents by tier.
3. **Where**: disengagements and incidents per segment on the route map, coloured by the
   segment's risk-register score, so repeat locations stand out against the desk
   assessment.
4. **Reliability**: OTP and availability by route and hour of day; running time against
   the schedule per segment.
5. **Demand**: boardings per day and per stop; unique riders if the booking system
   provides a rider key.
6. **Actions**: open risk-register actions with owner and due date.

## Data quality rules

- A trip with `status = operated` must have an actual departure and km > 0.
- Disengagements must have `category`; `planned` ones (e.g. a manual depot move) are kept
  but excluded from the headline rate.
- Each event carries a `segment_id`, so the dashboard and the risk register share keys.
