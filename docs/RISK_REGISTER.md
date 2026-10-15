# Risk register digest

Full register: [`outputs/risk_register.csv`](../outputs/risk_register.csv) (one row per hazard per segment). Scores are likelihood (1-5, from measured exposure) x severity (1-5, fixed per hazard), set in `config/scoring.yaml`. All rows are *proposed* and come from a desk assessment.

## Punggol West to East (Route 1) (PG-R1)

150 rows: 4 very high, 33 high, 72 medium, 41 low.

| Risk ID | Chainage (m) | Location | Hazard | L | S | Score | Owner |
|---|---|---|---|---|---|---|---|
| PG-R1-S04-school_zone | 834-1114 | Punggol Field | LTA School Zone (children, drop-off traffic, 40 km/h at school hours) | 4 | 5 | 20 | AV operator; Deployment Ops for school liaison |
| PG-R1-S20-high_speed_road | 5238-5545 | Punggol North Avenue | Posted limit 60 km/h or more (large speed differential with a slow shuttle) | 5 | 4 | 20 | Deployment Ops with AV operator |
| PG-R1-S28-school_zone | 7498-7774 | Edgedale Plains | LTA School Zone (children, drop-off traffic, 40 km/h at school hours) | 4 | 5 | 20 | AV operator; Deployment Ops for school liaison |
| PG-R1-S34-school_zone | 9308-9608 | Punggol Field | LTA School Zone (children, drop-off traffic, 40 km/h at school hours) | 4 | 5 | 20 | AV operator; Deployment Ops for school liaison |
| PG-R1-S04-signal_controlled_site | 834-1114 | Punggol Field | Signal-controlled site: junction or signalised crossing (signal recognition, red-light runners, turning conflicts) | 4 | 4 | 16 | AV developer |
| PG-R1-S21-high_speed_road | 5545-5854 | Punggol North Avenue | Posted limit 60 km/h or more (large speed differential with a slow shuttle) | 4 | 4 | 16 | Deployment Ops with AV operator |
| PG-R1-S33-signal_controlled_site | 9043-9308 | Punggol Field | Signal-controlled site: junction or signalised crossing (signal recognition, red-light runners, turning conflicts) | 4 | 4 | 16 | AV developer |
| PG-R1-S34-signal_controlled_site | 9308-9608 | Punggol Field | Signal-controlled site: junction or signalised crossing (signal recognition, red-light runners, turning conflicts) | 4 | 4 | 16 | AV developer |
| PG-R1-S15-uncontrolled_crossing | 3776-4066 | Punggol East | Pedestrian crossing without signals (zebra or unmarked) | 3 | 5 | 15 | AV operator (safety lead) |
| PG-R1-S17-multi_lane | 4321-4621 | Punggol East | Three or more lanes in the direction of travel (lane changes, merges) | 5 | 3 | 15 | AV developer |

## Punggol East to North (Route 2) (PG-R2)

142 rows: 3 very high, 31 high, 71 medium, 37 low.

| Risk ID | Chainage (m) | Location | Hazard | L | S | Score | Owner |
|---|---|---|---|---|---|---|---|
| PG-R2-S31-high_speed_road | 8627-8936 | Punggol North Avenue | Posted limit 60 km/h or more (large speed differential with a slow shuttle) | 5 | 4 | 20 | Deployment Ops with AV operator |
| PG-R2-S32-high_speed_road | 8936-9307 | Punggol North Avenue | Posted limit 60 km/h or more (large speed differential with a slow shuttle) | 5 | 4 | 20 | Deployment Ops with AV operator |
| PG-R2-S38-school_zone | 10737-10999 | Edgedale Plains | LTA School Zone (children, drop-off traffic, 40 km/h at school hours) | 4 | 5 | 20 | AV operator; Deployment Ops for school liaison |
| PG-R2-S18-high_speed_road | 5034-5353 | Punggol Way | Posted limit 60 km/h or more (large speed differential with a slow shuttle) | 4 | 4 | 16 | Deployment Ops with AV operator |
| PG-R2-S28-signal_controlled_site | 7814-8112 | Sentul Walk | Signal-controlled site: junction or signalised crossing (signal recognition, red-light runners, turning conflicts) | 4 | 4 | 16 | AV developer |
| PG-R2-S30-high_speed_road | 8369-8627 | Punggol North Avenue | Posted limit 60 km/h or more (large speed differential with a slow shuttle) | 4 | 4 | 16 | Deployment Ops with AV operator |
| PG-R2-S03-multi_lane | 586-885 | Punggol East | Three or more lanes in the direction of travel (lane changes, merges) | 5 | 3 | 15 | AV developer |
| PG-R2-S18-multi_lane | 5034-5353 | Punggol Way | Three or more lanes in the direction of travel (lane changes, merges) | 5 | 3 | 15 | AV developer |
| PG-R2-S19-multi_lane | 5353-5623 | Punggol Way | Three or more lanes in the direction of travel (lane changes, merges) | 5 | 3 | 15 | AV developer |
| PG-R2-S37-school_zone | 10474-10737 | Edgedale Plains | LTA School Zone (children, drop-off traffic, 40 km/h at school hours) | 3 | 5 | 15 | AV operator; Deployment Ops for school liaison |

## Punggol West to North (Route 3) (PG-R3)

167 rows: 5 very high, 46 high, 76 medium, 40 low.

| Risk ID | Chainage (m) | Location | Hazard | L | S | Score | Owner |
|---|---|---|---|---|---|---|---|
| PG-R3-S04-school_zone | 834-1114 | Punggol Field | LTA School Zone (children, drop-off traffic, 40 km/h at school hours) | 4 | 5 | 20 | AV operator; Deployment Ops for school liaison |
| PG-R3-S11-high_speed_road | 2652-2902 | Punggol Road | Posted limit 60 km/h or more (large speed differential with a slow shuttle) | 5 | 4 | 20 | Deployment Ops with AV operator |
| PG-R3-S12-high_speed_road | 2902-3153 | Punggol Road | Posted limit 60 km/h or more (large speed differential with a slow shuttle) | 5 | 4 | 20 | Deployment Ops with AV operator |
| PG-R3-S34-high_speed_road | 9029-9297 | Punggol Road | Posted limit 60 km/h or more (large speed differential with a slow shuttle) | 5 | 4 | 20 | Deployment Ops with AV operator |
| PG-R3-S35-high_speed_road | 9297-9562 | Punggol Road | Posted limit 60 km/h or more (large speed differential with a slow shuttle) | 5 | 4 | 20 | Deployment Ops with AV operator |
| PG-R3-S04-signal_controlled_site | 834-1114 | Punggol Field | Signal-controlled site: junction or signalised crossing (signal recognition, red-light runners, turning conflicts) | 4 | 4 | 16 | AV developer |
| PG-R3-S28-signal_controlled_site | 7428-7726 | Sentul Walk | Signal-controlled site: junction or signalised crossing (signal recognition, red-light runners, turning conflicts) | 4 | 4 | 16 | AV developer |
| PG-R3-S33-high_speed_road | 8773-9029 | Punggol Road | Posted limit 60 km/h or more (large speed differential with a slow shuttle) | 4 | 4 | 16 | Deployment Ops with AV operator |
| PG-R3-S11-multi_lane | 2652-2902 | Punggol Road | Three or more lanes in the direction of travel (lane changes, merges) | 5 | 3 | 15 | AV developer |
| PG-R3-S12-multi_lane | 2902-3153 | Punggol Road | Three or more lanes in the direction of travel (lane changes, merges) | 5 | 3 | 15 | AV developer |
