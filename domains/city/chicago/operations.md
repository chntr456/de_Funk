---
type: domain-model
model: chicago_operations
version: 1.0
description: "Chicago 311 service requests and operational data"

# Python Module
python_module: models/domains/city/chicago/operations/

# Dependencies
depends_on:
  - chicago_geospatial

# Schema Template Reference
schema_template: _schema/service_request.md

# Storage
storage:
  root: storage/silver/chicago/operations
  format: delta

# Build
build:
  partitions: [year]
  optimize: true

# Sources
sources:
  service_requests:
    bronze_table: chicago_311_requests
    description: "311 service requests since 2018"
    column_mappings:
      request_id: sr_number
      request_type: sr_type
      request_short_code: sr_short_code
      created_date: created_date
      closed_date: closed_date
      status: status

  request_types:
    bronze_table: chicago_311_types
    description: "311 request type reference"

# Schema
schema:
  dimensions:
    dim_request_type:
      description: "Service request type dimension"
      primary_key: [request_type_id]
      columns:
        request_type_id: {type: string, required: true}
        sr_type: {type: string, description: "Request type name"}
        sr_short_code: {type: string, description: "Short code"}
        request_category: {type: string, description: "Taxonomy level 1"}
        request_subcategory: {type: string, description: "Taxonomy level 2"}

    dim_status:
      description: "Request status dimension"
      primary_key: [status_id]
      columns:
        status_id: {type: string, required: true}
        status_name: {type: string}
        is_open: {type: boolean}
        is_closed: {type: boolean}

  facts:
    fact_service_requests:
      description: "311 service requests fact table"
      primary_key: [request_id]
      columns:
        request_id: {type: string, required: true, description: "Service request number"}
        request_type_id: {type: string, description: "FK to dim_request_type"}
        status_id: {type: string, description: "FK to dim_status"}
        created_date: {type: timestamp, description: "Request created date"}
        closed_date: {type: timestamp, description: "Request closed date"}
        year: {type: int, description: "Year created"}
        street_address: {type: string}
        zip_code: {type: string}
        ward: {type: int, description: "City ward"}
        community_area: {type: int, description: "Community area number"}
        latitude: {type: double}
        longitude: {type: double}
        is_legacy: {type: boolean, description: "From old 311 system"}
        days_to_close: {type: int, description: "Days from created to closed"}

# Graph
graph:
  nodes:
    dim_request_type:
      from: bronze.chicago_311_requests
      type: dimension
      transform: distinct
      columns: [sr_type, sr_short_code]
      derive:
        request_type_id: "MD5(COALESCE(sr_type, 'UNKNOWN'))"
        request_category: "CASE WHEN sr_type LIKE '%Pothole%' OR sr_type LIKE '%Street%' THEN 'INFRASTRUCTURE' WHEN sr_type LIKE '%Graffiti%' OR sr_type LIKE '%Garbage%' OR sr_type LIKE '%Sanitation%' THEN 'SANITATION' WHEN sr_type LIKE '%Tree%' THEN 'TREES' WHEN sr_type LIKE '%Building%' THEN 'BUILDINGS' WHEN sr_type LIKE '%Rodent%' OR sr_type LIKE '%Animal%' THEN 'ANIMALS' ELSE 'OTHER' END"
      unique_key: [request_type_id]

    dim_status:
      from: bronze.chicago_311_requests
      type: dimension
      transform: distinct
      columns: [status]
      derive:
        status_id: "MD5(COALESCE(status, 'UNKNOWN'))"
        status_name: status
        is_open: "status IN ('Open', 'In Progress')"
        is_closed: "status = 'Completed'"
      unique_key: [status_id]

    fact_service_requests:
      from: bronze.chicago_311_requests
      type: fact
      derive:
        request_id: sr_number
        request_type_id: "MD5(COALESCE(sr_type, 'UNKNOWN'))"
        status_id: "MD5(COALESCE(status, 'UNKNOWN'))"
        is_legacy: legacy_record
        days_to_close: "DATEDIFF('day', created_date, closed_date)"
      unique_key: [request_id]

  edges:
    request_to_type:
      from: fact_service_requests
      to: dim_request_type
      on: [request_type_id=request_type_id]
      type: many_to_one

    request_to_status:
      from: fact_service_requests
      to: dim_status
      on: [status_id=status_id]
      type: many_to_one

    request_to_community_area:
      from: fact_service_requests
      to: chicago_geospatial.dim_community_area
      on: [community_area=area_number]
      type: many_to_one

# Measures
measures:
  simple:
    request_count:
      description: "Total service requests"
      source: fact_service_requests.request_id
      aggregation: count
      format: "#,##0"

    open_request_count:
      description: "Open service requests"
      source: fact_service_requests.request_id
      aggregation: count
      filters:
        - "status_id IN (SELECT status_id FROM dim_status WHERE is_open = true)"
      format: "#,##0"

    avg_days_to_close:
      description: "Average days to close request"
      source: fact_service_requests.days_to_close
      aggregation: avg
      format: "#,##0.1"

  computed:
    completion_rate:
      description: "Percentage of requests completed"
      formula: "(request_count - open_request_count) / request_count * 100"
      format: "#,##0.0%"

# Metadata
metadata:
  domain: city
  entity: chicago
  subdomain: operations
status: active
---

## Chicago Operations Model

311 service requests and operational data for the City of Chicago.

### Data Sources

| Source | Bronze Table | Description |
|--------|--------------|-------------|
| 311 Requests | chicago_311_requests | Service requests since 12/18/2018 |
| Request Types | chicago_311_types | Request type reference |

### Request Taxonomy

Uses `_schema/service_request.md` template:

```
INFRASTRUCTURE
├── Pothole complaints
├── Street light outages
└── Street sign issues

SANITATION
├── Garbage cart requests
├── Graffiti removal
└── Alley/street cleaning

TREES
├── Tree trim requests
├── Tree removal
└── Tree debris pickup

BUILDINGS
├── Building violations
├── Vacant building complaints
└── Permit inquiries

ANIMALS
├── Rodent complaints
├── Animal control
└── Stray animal reports
```

### Data Notes

- New 311 system launched 12/18/2018
- `is_legacy` flag indicates records from old system
- "311 INFORMATION ONLY CALL" requests often use 311 Center address

### Example Queries

```sql
-- Requests by type and status
SELECT
    rt.sr_type,
    st.status_name,
    COUNT(*) as request_count
FROM fact_service_requests r
JOIN dim_request_type rt ON r.request_type_id = rt.request_type_id
JOIN dim_status st ON r.status_id = st.status_id
WHERE r.year = 2023
GROUP BY rt.sr_type, st.status_name;

-- Average response time by category
SELECT
    rt.request_category,
    AVG(r.days_to_close) as avg_days,
    COUNT(*) as total_requests
FROM fact_service_requests r
JOIN dim_request_type rt ON r.request_type_id = rt.request_type_id
WHERE r.closed_date IS NOT NULL
GROUP BY rt.request_category
ORDER BY avg_days DESC;
```
