# Sources

All retrieved on 2026-10-15 unless stated. Keys match `sources:` in `config/routes.yaml`.
Official sources come first; secondary sources are used only for details the official
pages do not give, and are marked as such wherever they are used.

## Official

| Key | Source | Used for |
|---|---|---|
| `lta-2025-09-20` | LTA news release, *New Autonomous Shuttle Services to be Progressively Deployed in Punggol* (20 Sep 2025). https://www.lta.gov.sg/content/ltagov/en/newsroom/2025/9/news-releases/new-autonomous-shuttle-services-to-be-progressively-deployed-in-.html | Three fixed routes, operators and platforms, round-trip lengths (10, 12, 12 km) and durations (35, 55, 40 min), phased approach, safety operator on board at all times, real-time monitoring, Tengah named only as a possible later town |
| `lta-annex-a` | Annex A to the release above: route maps and stop lists. https://www.lta.gov.sg/content/dam/ltagov/news/press/2025/250920-AV-shuttle-punggol.pdf | Stop order per route; the drawn route lines traced in `src/avready/trace.py` |
| `lta-2026-03` | LTA news release, *Autonomous Shuttle Services in Punggol Open for Public Rides from 1 April 2026* (Mar 2026). https://www.lta.gov.sg/content/ltagov/en/newsroom/2026/3/news-releases/autonomous-shuttle-services-in-punggol-open-for-public-rides-fro.html | Public rides on Routes 1 and 3 from 1 Apr 2026; Route 2 still in familiarisation at the time; by-invite rides from 12 Jan 2026 |
| `lta-2026-07` | LTA news release, *Service Enhancements to Autonomous Shuttle Services in Punggol* (Jul 2026). https://www.lta.gov.sg/content/ltagov/en/newsroom/2026/7/news-releases/service-enhancements-autonomous-shuttle-Punggol.html | Ridership to 12 Jul 2026; survey results; planned on-demand pilot on Routes 1 and 3; fixed routes continue |
| `lta-2025-10` | LTA news release, *LTA Awards Contract for the Pilot Deployment of Autonomous Buses on Two Public Bus Services* (Oct 2025). https://www.lta.gov.sg/content/ltagov/en/newsroom/2025/10/news-releases/lta_awards_contract_pilot_deployment_autonomous_buses.html | Services 400 and 191 named for the pilot; safety operator then remote operator; Milestone 1 test at CETRAN |
| `mot-2026-02` | MOT, written parliamentary reply, *Managing Teething Issues of Autonomous Vehicle Shuttle Implementation in Punggol* (Feb 2026). https://www.mot.gov.sg/news-resources/newsroom/managing-teething-issues-of-autonomous-vehicle-shuttle-implementation-in-punggol/ | LTA and the operator reviewed procedures for transitions between autonomous and manual driving after the January 2026 incident |
| `datamall-busroutes` | LTA DataMall BusRoutes, BusStops, BusServices (snapshot of 2026-09-26, taken by the sg-bus-network-monitor project) | Stop sequence and stop positions of services 400 and 191; bus stops near the shuttle routes |
| `datamall-geo` | LTA DataMall *Geospatial Whole Island*: SchoolZone, SilverZone, TrafficLight, RoadCrossing, RoadHump (retrieved 2026-10-15) | School and Silver Zones, traffic lights, road crossings, road humps |
| `datamall-speedbands` | LTA DataMall Traffic Speed Bands v4 snapshots (2026-09-26 to 2026-10-03 from a laptop collector, and 2026-10-15 from the public `data-collect` branch of LUOaini1213/sg-bus-network-monitor) | Speed variability in operating hours |
| `datamall-incidents` | LTA DataMall Traffic Incidents polls on the `data-collect` branch above | Incidents near the routes (two polls so far; see README) |
| `onemap` | Singapore Land Authority OneMap search API | Coordinates of the HDB blocks and buildings named as stops |

DataMall data is used under the Singapore Open Data Licence v1.0. Clipped subsets are
committed under `data/lta/`.

## OpenStreetMap

`osm`: BBBike extract of Singapore, https://download.bbbike.org/osm/bbbike/Singapore/Singapore.osm.gz,
Last-Modified 2026-10-11 03:05 GMT, SHA-256 `62ee40971167e0428f68bb1af75d07befb0ba5549d2e22095080c38c3dae309f`.
(c) OpenStreetMap contributors, ODbL 1.0. Clipped subsets are committed under `data/osm/`.
Overpass was tried first; all four public endpoints returned HTTP 5xx or 406 on 2026-10-15.

## Secondary (enthusiast or news sites)

| Key | Source | Used for |
|---|---|---|
| `ltg-punggol` | Land Transport Guru, *Punggol Autonomous Shuttle Services*. https://landtransportguru.net/punggol-autonomous-shuttle-service/ | Pick-up point descriptions (for example "between Blk 234 and Blk 231"), operating hours 09:30-17:30 Mon-Sat, Route 2 by-invite and public dates |
| `ltg-suspend` | Land Transport Guru, *Autonomous Shuttle suspended following accident near Punggol Plaza*. https://landtransportguru.net/autonomous-shuttle-suspended-following-accident-near-punggol-plaza/ | Location of the 17 Jan 2026 incident (service road outside Blk 172 Edgedale Plains); resumption on 30 Jan 2026 |
| `ltg-bus-cancel` | Land Transport Guru, *Planned Autonomous Public Bus Deployments on Services 191 & 400 Cancelled* (Oct 2026), reporting LTA's reply to Lianhe Zaobao; also covered by Mothership, https://mothership.sg/2026/10/lta-halts-pilot-programme-for-self-driving-public-buses-to-explore-narrower-use-cases-for-now/ | Deployment on services 400 and 191 called off; LTA exploring narrower use cases such as employee shuttles. An LTA page for this was not found. |

## Not found

- **Tengah.** No published autonomous shuttle or bus route for Tengah was found. LTA's
  September 2025 release names Tengah only as a town where similar shuttles may follow.
  No Tengah route is assessed here.
- **Historical crash locations.** Singapore does not publish geolocated historical road
  crash records. DataMall's incident feed is live only.
