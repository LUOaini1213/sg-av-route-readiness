# Deployment readiness checklist (AV shuttle route)

A gate checklist for taking one AV route from approved plan to passenger service. It is
written for use in a trial and has not been used on a real deployment. Items marked
*(published)* restate what LTA has said publicly about the Punggol deployment; the rest
are proposals. Route-specific inputs come from the generated files:

- ODD checklist per route: [`docs/odd/`](odd/)
- Segment risk register: [`outputs/risk_register.csv`](../outputs/risk_register.csv), digest in [`RISK_REGISTER.md`](RISK_REGISTER.md)
- KPI definitions: [`KPI_DASHBOARD_SPEC.md`](KPI_DASHBOARD_SPEC.md)

Each item has an owner role and the evidence that closes it. A gate passes when every item
is closed or has a recorded, accepted exception.

## Gate 0: Route and concept of operations agreed

| # | Item | Owner | Evidence |
|---|---|---|---|
| 0.1 | Route, stops and pick-up points fixed; any service roads inside the route listed and the rest geofenced | Deployment Ops with operator | Route file and geofence signed off; ODD checklist section 1 |
| 0.2 | Every *High* and *Very high* row in the risk register has an accepted mitigation or a route change | Deployment Ops | Register with status updated |
| 0.3 | Unprotected right turns and roundabouts on the route reviewed; replaced by left-turn variants where practical | Operator, AV developer | Route variant comparison |
| 0.4 | Operating hours and days, weather limits and lighting limits written into the ODD | AV developer | ODD statement |
| 0.5 | Programme plan with baseline dates for each gate, and the owner of each workstream | Deployment Ops | Plan baselined |

## Gate 1: Vehicle and system approval

| # | Item | Owner | Evidence |
|---|---|---|---|
| 1.1 | Closed-circuit test passed at CETRAN *(published: required before on-road activity)* | AV developer | Test certificate |
| 1.2 | On-road preparation without passengers, safety operator on board: mapping, sensor calibration, model validation, operator familiarisation *(published)* | AV developer, operator | Familiarisation log with km and disengagements by segment |
| 1.3 | Familiarisation covers every segment flagged for signal recognition, crossings and school zones at the times they are busiest | AV developer | Coverage table against `outputs/segments.csv` |
| 1.4 | Disengagement and near-miss trend reviewed per segment; segments with repeat events have a fix or a restriction | Deployment Ops | Review minutes |

## Gate 2: People and procedures

| # | Item | Owner | Evidence |
|---|---|---|---|
| 2.1 | Safety operators trained and assessed on this route; roster covers every scheduled trip with relief | Operator | Training records, roster |
| 2.2 | Procedure for transitions between autonomous and manual driving, including when a takeover is mandatory *(published: reviewed by LTA and an operator after the January 2026 incident)* | Operator | SOP version and sign-off |
| 2.3 | If a remote operator is used: staffing ratio, maximum vehicles per operator, network latency and coverage along the full route, loss-of-link behaviour | Operator, AV developer | Remote ops test report |
| 2.4 | Minimal-risk stopping places identified for each segment | AV developer | Map of stopping places |
| 2.5 | Passenger rules (seat belts, boarding, accessibility) and in-vehicle announcements | Operator | Passenger notice |

## Gate 3: Incident escalation

Proposed severity tiers, to be agreed with LTA and the operator:

| Tier | Definition | Notify | Within |
|---|---|---|---|
| 1 | Property damage only, or a safety-critical disengagement without contact | Operator control room; Deployment Ops duty officer | 30 min |
| 2 | Minor injury, or any contact with a vulnerable road user | As tier 1, plus LTA management, Police (if required by law) | 15 min |
| 3 | Serious injury or fatality | As tier 2, plus senior management and Corporate Communications; service suspended on the route | Immediate |
| 4 | Repeat tier 1 events at one location (e.g. 3 in 30 days) | Deployment Ops; AV developer | Next working day |

| # | Item | Owner | Evidence |
|---|---|---|---|
| 3.1 | Contact tree with 24/7 numbers for every role above, tested by a call-out drill | Deployment Ops | Drill record |
| 3.2 | Criteria and authority to suspend and to resume service *(published precedent: one operator paused its service for review after the 17 Jan 2026 incident and resumed on 30 Jan 2026, per a secondary source)* | Deployment Ops | Suspension/resumption procedure |
| 3.3 | Data preservation after an event: vehicle logs, video, operator statement | AV developer, operator | Procedure |
| 3.4 | Holding statement templates agreed with Corporate Communications | Deployment Ops | Templates |

## Gate 4: Stakeholder notification

| # | Who | What | Owner |
|---|---|---|---|
| 4.1 | Residents and grassroots advisers *(published: routes were planned with Grassroot Advisers)* | Launch date, stops, how to book, feedback channel | Deployment Ops, operator |
| 4.2 | Schools in or next to School Zones on the route (named in each ODD checklist) | Operating hours, vehicle appearance, contact | Deployment Ops |
| 4.3 | Town Council and estate management (service roads, kerbs, signage at pick-up points) | Pick-up point signage, kerb use | Deployment Ops |
| 4.4 | Bus operator for stops on the path (count per route in the ODD checklist) | Kerb sharing, driver briefing | Deployment Ops |
| 4.5 | Traffic Police and emergency services | Vehicle identification (purple, labelled, amber beacon *(published)*), incident contacts | Deployment Ops |
| 4.6 | Road and signal operations (LTA) | Junctions on the route, any temporary works that affect it | Deployment Ops |
| 4.7 | Corporate Communications and engagement team | Milestone announcements aligned with readiness | Deployment Ops |

## Gate 5: Launch and monitoring

| # | Item | Owner | Evidence |
|---|---|---|---|
| 5.1 | KPI feed live from day one (see spec): disengagements per 100 km, on-time performance, incidents by tier, ridership, availability | Operator, Deployment Ops | Dashboard |
| 5.2 | Weekly review for the first 8 weeks, then fortnightly; actions logged against risk-register IDs | Deployment Ops | Review log |
| 5.3 | Rider feedback collected and summarised *(published practice: LTA post-ride surveys)* | Operator | Survey summary |
| 5.4 | Criteria for the next phase (e.g. paid service, on-demand routing, more vehicles) written before launch, not after | Deployment Ops | Phase criteria |

## Reference timeline: Punggol, as published

Used to sanity-check a programme plan, not as a target.

| Date | Milestone | Source |
|---|---|---|
| 20 Sep 2025 | Three routes announced | `lta-2025-09-20` |
| 12 Jan 2026 | By-invite community rides start (Grab routes) | `lta-2026-03` |
| 17 Jan 2026 | Incident during mapping (no passengers); service paused, resumed 30 Jan | `mot-2026-02`, `ltg-suspend` |
| 25 Mar 2026 | Online registration for Routes 1 and 3 | `lta-2026-03` |
| 1 Apr 2026 | Public rides on Routes 1 and 3 | `lta-2026-03` |
| Apr-Jun 2026 | Route 2 by-invite, then a shorter public variant | `ltg-punggol` |
| 12 Jul 2026 | More than 11,500 unique riders | `lta-2026-07` |
| Jul 2026 | On-demand pilot on Routes 1 and 3 announced; fixed routes continue free | `lta-2026-07` |

About nine months passed between announcement and public rides on the first two routes,
and Route 2 took longer. The revenue service planned for mid-2026 had not started by the
July 2026 release.
