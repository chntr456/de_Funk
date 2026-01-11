---
type: api-endpoint          
provider: Chicago Data Portal                  
multiple_endpoints: true   
endpoint_pattern:  /api/v3/views/kf7e-cur8/query.json           
method: GET                              
auth: inherit               
domain: transportation             
legal_entity_type: municipal          
subject_entity_type: [municipal, infrustructure]       
data_tags: [ geospatial, traffic]
status: active                                
update_cadence: irregular
last_verified:              
last_reviewed:             
notes:                      
---

## Description

This dataset contains the historical estimated congestion for over 1,000 traffic segments, starting in approximately 2/28/2018 and ending 9/8/2023. Older records are in [https://data.cityofchicago.org/d/77hq-huss](https://data.cityofchicago.org/d/77hq-huss). The most recent estimates for each segment are in [https://data.cityofchicago.org/d/n4j6-wkkf](https://data.cityofchicago.org/d/n4j6-wkkf).  
  
The Chicago Traffic Tracker estimates traffic congestion on Chicago’s arterial streets (non-freeway streets) in real-time by continuously monitoring and analyzing GPS traces received from Chicago Transit Authority (CTA) buses. Two types of congestion estimates are produced every 10 minutes: 1) by Traffic Segments and 2) by Traffic Regions or Zones. Congestion estimates by traffic segments gives observed speed typically for one-half mile of a street in one direction of traffic. Traffic Segment level congestion is available for about 300 miles of principal arterials.  
  
Congestion by Traffic Region gives the average traffic condition for all arterial street segments within a region. A traffic region is comprised of two or three community areas with comparable traffic patterns. 29 regions are created to cover the entire city (except O’Hare airport area). There is much volatility in traffic segment speed. However, the congestion estimates for the traffic regions remain consistent for a relatively longer period. Most volatility in arterial speed comes from the very nature of the arterials themselves. Due to a myriad of factors, including but not limited to frequent intersections, traffic signals, transit movements, availability of alternative routes, crashes, short length of the segments, etc. Speed on individual arterial segments can fluctuate from heavily congested to no congestion and back in a few minutes.  
  
The segment speed and traffic region congestion estimates together may give a better understanding of the actual traffic conditions.

## Available Years

| Year | view_id | Format | Notes |
|----|----|----|----|
| 2024-Current | 4g9f-3jbs | JSON | provisional |
| 2018-2023 | sxs8-h27x | JSON | provisional |


## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.