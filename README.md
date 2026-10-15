# sg-av-route-readiness

An independent desk assessment of the roads along Singapore's announced autonomous
shuttle routes in Punggol, and a deployment-operations pack built from it: a
segment-level risk register, an ODD checklist per route, a deployment readiness
checklist, and a KPI dashboard spec for trial operations.

Everything here comes from public data: LTA and MOT announcements, LTA DataMall,
OneMap and OpenStreetMap. I have no involvement in these deployments and no operational
data from them. Route paths are reconstructed from LTA's published maps, not surveyed.
The checklists and register are designed for use in a trial; none of them has been used
on a real deployment.

Map: https://luoaini1213.github.io/sg-av-route-readiness/ (segments coloured by risk score).

## Routes assessed

| ID | Route | Operator (platform) | Status (sources in [SOURCES.md](SOURCES.md)) |
|---|---|---|---|
| PG-R1 | Punggol West to East, ~10 km round trip, ~35 min | Grab (WeRide) | Public rides since 1 Apr 2026 |
| PG-R2 | Punggol East to North, ~12 km, ~55 min | ComfortDelGro (Pony.ai) | By-invite, then a shorter public variant (secondary source) |
| PG-R3 | Punggol West to North, ~12 km, ~40 min | Grab (WeRide) | Public rides since 1 Apr 2026 |
| BUS-400, BUS-191 | Public bus services named for LTA's autonomous bus pilot | SBS Transit (manned) | LTA said in Oct 2026 the pilot will not proceed on these services; kept as a comparison only, no pack |

**Tengah:** no published route was found. LTA's Sep 2025 release names Tengah only as a
town where similar shuttles may follow, so nothing in Tengah is assessed.

## Findings

1. **The published routes are not shortest paths, and the gap matters for risk.**
   Shortest paths through the announced stops come out 7%, 16% and 27% shorter than the
   published lengths. Tracing the route lines on LTA's Annex A maps and routing along them
   brings the gap to +4.1%, -5.5% and -5.4%. On Route 3 the traced route uses Punggol
   Way (3 lanes, 60 km/h), which the shortest path skips.
2. **All right turns on the three shuttle routes are at signal-controlled junctions.**
   The reconstructed paths have 7, 8 and 13 right turns at signals and none without
   (BUS-400 and BUS-191 each have one without). At 4 of these turns OSM tags a signal
   but LTA's traffic-light layer shows none within 35 m. The ODD checklists list them
   for a site check.
3. **Each shuttle route spends 1.1-1.7 km on roads posted 60 km/h or more**
   (Punggol North Avenue, Punggol East, Punggol Road, Punggol Way). From the published
   lengths and durations, the shuttles average 13-18 km/h including stops. These
   sections carry the highest-scoring speed-differential rows in the register.
4. **School Zones:** Route 1 has 952 m inside LTA School Zones (Greendale, Horizon and
   Punggol Green Primary). Routes 2 and 3 have about 480 m each. There are no Silver Zones
   on any shuttle route.
5. **OSM alone is not enough for a deployment survey.** OSM signal nodes on the path
   find 22-32 signal-controlled sites per shuttle route. LTA's traffic-light layer finds
   41-58. OSM also has 14-20 crossings per route with no crossing type.
6. **Speed variability in operating hours is moderate.** The length-weighted CV of
   speed-band speed is 0.17-0.19 on the shuttle routes, against 0.27 on BUS-191 and
   0.13 on BUS-400. This rests on 67 snapshots from four weekdays and should be read as
   indicative.
7. **Incident history is thin.** Singapore publishes no historical geolocated crash data,
   and the DataMall incident feed is live only. The two polls archived so far (one of
   them empty) have nothing in the study areas. The one documented shuttle incident
   (17 Jan 2026, during mapping, no passengers) was on a service road off Edgedale
   Plains that was not part of the route. Its location is 56 m from the Route 1 and
   Route 2 paths. The register's mitigation for service roads is a geofence.
8. **The register ranking is fairly robust to the scoring choices.** Severities were
   varied by x0.5-1.5 and thresholds by x0.75-1.25 over 500 draws. The median Spearman
   rho against the base ranking of shuttle segments is 0.96 (5th percentile 0.92). The
   top-10 segments keep a median 7 of 10, with a 5th percentile of 5.

| Route | km (published) | Signal sites /km | Right turns at signals / without | Crossings without signals (OSM) | School zone m | 60+ km/h m | Bus stops on kerb | Register rows (very high / high) |
|---|---|---|---|---|---|---|---|---|
| PG-R1 | 10.41 (10) | 4.5 | 7 / 0 | 7 | 952 | 1,088 | 20 | 150 (4 / 33) |
| PG-R2 | 11.34 (12) | 3.9 | 8 / 0 | 5 | 472 | 1,535 | 19 | 142 (3 / 31) |
| PG-R3 | 11.35 (12) | 5.6 | 13 / 0 | 6 | 481 | 1,675 | 22 | 167 (5 / 46) |
| BUS-400 | 11.66 (11.4) | 5.4 | 7 / 1 | 5 | 0 | 977 | 28 | comparison only |
| BUS-191 | 8.17 (7.5) | 4.0 | 3 / 1 | 7 | 646 | 2,150 | 22 | comparison only |

Full table: [`outputs/route_summary.csv`](outputs/route_summary.csv). Per segment:
[`outputs/segments.csv`](outputs/segments.csv). Turns: [`outputs/turns.csv`](outputs/turns.csv).

## The deployment-ops pack

| Document | What it is |
|---|---|
| [`outputs/risk_register.csv`](outputs/risk_register.csv), digest [`docs/RISK_REGISTER.md`](docs/RISK_REGISTER.md) | One row per hazard per 250 m segment: hazard, exposure, likelihood, severity, rating, existing control (as published), proposed mitigation, owner role, status |
| [`docs/odd/PG-R1.md`](docs/odd/PG-R1.md), [`PG-R2`](docs/odd/PG-R2.md), [`PG-R3`](docs/odd/PG-R3.md) | ODD checklist per route: observed road environment with segment IDs, items to confirm with the developer and operator, data gaps |
| [`docs/DEPLOYMENT_READINESS.md`](docs/DEPLOYMENT_READINESS.md) | Gate checklist: route and concept of operations, vehicle approval, safety and remote operators, incident escalation tiers, stakeholder notification, launch monitoring; plus the Punggol timeline as published |
| [`docs/KPI_DASHBOARD_SPEC.md`](docs/KPI_DASHBOARD_SPEC.md), [`src/avready/kpi.py`](src/avready/kpi.py) | KPI definitions with tested formulas: disengagements per 100 km, on-time performance, availability, incidents by tier, ridership |

## Method

**Stops.** The stops named in the LTA releases are geocoded with OneMap. Each query must
match the block number and road. Where a secondary source describes a pick-up point as
"between Blk A and Blk B", the stop is placed at their midpoint. The stop is then snapped
to the nearest road edge that has it on the left, since Singapore drives on the left.
Snap distances are 30-138 m for shuttle stops, because the anchors are building centres.

**Geometry.** The Annex A route lines are traced from the PDF images
(`src/avready/trace.py`). The process keeps near-black pixels, removes the stop discs
and fits an affine transform on the stop markers. It then refines the fit by matching
the traced pixels to OSM roads, starting from 75 positions. The median residual is
4-6 m. The p90 is 13-17 m on Routes 1 and 3 and 31 m on Route 2.

Routing then makes roads away from the traced line up to 5 times dearer. Route 2 needs
three shape points and Route 3 one, read from the trace and documented in
`config/routes.yaml`, because the drawn lines reuse road segments in both directions.
Agreement between path and map is 91/98% (R1), 81/79% (R2) and 91/94% (R3). Route 2 is
the least certain.

Bus services 400 and 191 use DataMall stop sequences. Their reconstructed lengths are
within +2.3% and +8.9% of DataMall's.

**Features per segment.**
- OSM signal and crossing nodes count only if they are vertices of the path.
- LTA traffic lights count within 20 m, and LTA road crossings and humps must touch the
  path.
- School and Silver Zones come from LTA polygons.
- Bus stops count only on the kerb side.
- Posted speed and lanes come from OSM. Lanes are per direction.
- A turn is a heading change of 45 degrees or more within 25 m of a junction. Right turns
  cross oncoming traffic.
- Speed bands are matched by distance and direction, and use only snapshots inside the
  published operating hours (09:30-17:30, Monday to Saturday).

**Scoring.** For each hazard, likelihood is the number of exposure thresholds met (1-5).
Severity is fixed per hazard. The score is likelihood x severity on a 5x5 matrix. All
thresholds and severities are in [`config/scoring.yaml`](config/scoring.yaml). They are
judgement calls, so the sensitivity run in finding 8 tests them.

## Limitations

- Route paths are reconstructions. Treat per-segment results as approximate where the
  map agreement is lower (Route 2), and verify every item on site.
- LTA is moving Routes 1 and 3 towards on-demand, direct routing between pick-up points
  (Jul 2026 release). The fixed loops assessed here may not be what runs later.
- Speed bands cover only 67 snapshots on four weekdays (28 Sep - 2 Oct, plus 15 Oct). No
  Saturday falls in the operating window sample.
- OSM posted-speed tags cover 88-97% of the shuttle paths. Untagged does not mean
  unrestricted.
- Severity and likelihood are desk judgements and have not been calibrated against
  outcomes.

## Run it

Python 3.11.

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m avready.build      # committed inputs -> outputs/, docs/, results/
python -m pytest -q                         # 36 tests
python tools/mutation_check.py              # 28 deliberate bugs; each must make the suite fail
```

The fetch steps need network access. The DataMall steps also need a key in `LTA_KEY`,
which is never written to disk. Their outputs are committed, so the build runs offline:

```bash
pip install -r requirements-fetch.txt
python -m avready.geocode                                   # OneMap -> data/derived/anchors.csv
python -m avready.fetch_osm Singapore.osm.gz --source-url ... --last-modified ...
python -m avready.fetch_lta geo                             # DataMall geospatial layers
python -m avready.fetch_lta bus DIR_WITH_BusRoutes_json     # bus 400/191 stop sequences
python -m avready.trace 250920-AV-shuttle-punggol.pdf       # Annex A route lines
python -m avready.build routes
python -m avready.speedbands --links speedband_links.csv.gz SNAPSHOT_DIR [...]
python -m avready.incidents                                 # data-collect incident polls
python -m avready.build
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the tests and rebuilds
everything from committed inputs. It fails if any output differs, then runs the mutation
check. Two coordinate files are compared to within 1e-6 degrees, because PROJ's last
decimal differs between Windows and Linux. Everything else must match byte for byte
([`tools/check_rebuild.py`](tools/check_rebuild.py)).

**The mutation check failed on its first run:** 26 of 29 mutants were killed. The tests
were fixed, and the run is recorded in
[`results/mutation_first_run.md`](results/mutation_first_run.md). The current run kills
28 of 28 ([`results/mutation.json`](results/mutation.json)).

## Licence

Code: MIT. Data under `data/` keeps its own licence: OSM is ODbL 1.0, and LTA DataMall
data is under the Singapore Open Data Licence v1.0. See [SOURCES.md](SOURCES.md).
