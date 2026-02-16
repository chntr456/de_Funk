---
type: domain-model-table
table: dim_police_beat
table_type: dimension
from: bronze.chicago_police_beats
primary_key: [beat_id]
unique_key: [beat_number]

schema:
  - [beat_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('CHICAGO_BEAT_', beat_num)))"}]
  - [beat_number, string, false, "Beat number", {derived: "beat_num"}]
  - [district_id, integer, false, "FK to dim_police_district", {fk: dim_police_district.district_id, derived: "ABS(HASH(CONCAT('CHICAGO_DIST_', district)))"}]
  - [district_number, string, false, "Parent district number", {derived: "district"}]
  - [centroid_lat, double, true, "Centroid latitude"]
  - [centroid_lon, double, true, "Centroid longitude"]
  - [geom_wkt, string, true, "Boundary geometry as WKT"]
  - [location_id, integer, true, "FK to geospatial.dim_location", {fk: geospatial.dim_location.location_id}]

measures:
  - [beat_count, count_distinct, beat_id, "Number of police beats", {format: "#,##0"}]
---

## Police Beat Dimension

~280 patrol sub-areas within Chicago's police districts.
