---
type: domain-model
model: chicago_housing
version: 1.0
description: "Chicago building permits and zoning data"


# Dependencies
depends_on:
  - chicago_geospatial

# Storage
storage:
  root: storage/silver/chicago/housing
  format: delta

# Build
build:
  partitions: [year]
  optimize: true

# Sources
sources:
  building_permits:
    bronze_table: chicago_building_permits
    description: "Building permits issued"

  zoning_districts:
    bronze_table: chicago_zoning_districts
    description: "Zoning district boundaries"

# Schema
schema:
  dimensions:
    dim_permit_type:
      description: "Permit type dimension"
      primary_key: [permit_type_id]
      columns:
        permit_type_id: {type: string, required: true}
        permit_type: {type: string, description: "Type of permit"}
        permit_category: {type: string, description: "Category (New Construction, Alteration, etc.)"}

    dim_work_type:
      description: "Work type dimension"
      primary_key: [work_type_id]
      columns:
        work_type_id: {type: string, required: true}
        work_type: {type: string, description: "Type of work"}
        work_category: {type: string, description: "Residential, Commercial, etc."}

    dim_zoning_district:
      description: "Zoning district dimension"
      primary_key: [zone_class]
      columns:
        zone_class: {type: string, required: true, description: "Zoning classification"}
        zone_description: {type: string}
        zone_category: {type: string, description: "Residential, Commercial, Manufacturing, etc."}
        geometry: {type: geometry, description: "District boundary"}

  facts:
    fact_building_permits:
      description: "Building permits fact table"
      primary_key: [permit_id]
      columns:
        permit_id: {type: string, required: true}
        permit_number: {type: string}
        permit_type_id: {type: string}
        work_type_id: {type: string}
        issue_date: {type: date}
        year: {type: int}
        address: {type: string}
        ward: {type: int}
        community_area: {type: int}
        total_fee: {type: double, description: "Permit fees collected"}
        estimated_cost: {type: double, description: "Estimated construction cost"}
        latitude: {type: double}
        longitude: {type: double}

# Graph
graph:
  nodes:
    dim_permit_type:
      from: bronze.chicago_building_permits
      type: dimension
      transform: distinct
      columns: [permit_type]
      derive:
        permit_type_id: "MD5(COALESCE(permit_type, 'UNKNOWN'))"
        permit_category: "CASE WHEN permit_type LIKE '%NEW%' THEN 'New Construction' WHEN permit_type LIKE '%RENOVATION%' OR permit_type LIKE '%ALTERATION%' THEN 'Alteration' WHEN permit_type LIKE '%DEMOLITION%' THEN 'Demolition' ELSE 'Other' END"
      unique_key: [permit_type_id]

    dim_work_type:
      from: bronze.chicago_building_permits
      type: dimension
      transform: distinct
      columns: [work_type]
      derive:
        work_type_id: "MD5(COALESCE(work_type, 'UNKNOWN'))"
        work_category: "CASE WHEN work_type LIKE '%RESIDENTIAL%' THEN 'Residential' WHEN work_type LIKE '%COMMERCIAL%' THEN 'Commercial' ELSE 'Other' END"
      unique_key: [work_type_id]

    dim_zoning_district:
      from: bronze.chicago_zoning_districts
      type: dimension
      unique_key: [zone_class]

    fact_building_permits:
      from: bronze.chicago_building_permits
      type: fact
      derive:
        permit_type_id: "MD5(COALESCE(permit_type, 'UNKNOWN'))"
        work_type_id: "MD5(COALESCE(work_type, 'UNKNOWN'))"
      unique_key: [permit_id]

  edges:
    permit_to_type:
      from: fact_building_permits
      to: dim_permit_type
      on: [permit_type_id=permit_type_id]
      type: many_to_one

    permit_to_work_type:
      from: fact_building_permits
      to: dim_work_type
      on: [work_type_id=work_type_id]
      type: many_to_one

    permit_to_community_area:
      from: fact_building_permits
      to: chicago_geospatial.dim_community_area
      on: [community_area=area_number]
      type: many_to_one

# Measures
measures:
  simple:
    permit_count:
      description: "Number of permits issued"
      source: fact_building_permits.permit_id
      aggregation: count
      format: "#,##0"

    total_fees:
      description: "Total permit fees collected"
      source: fact_building_permits.total_fee
      aggregation: sum
      format: "$#,##0"

    total_estimated_cost:
      description: "Total estimated construction cost"
      source: fact_building_permits.estimated_cost
      aggregation: sum
      format: "$#,##0"

    avg_permit_fee:
      description: "Average permit fee"
      source: fact_building_permits.total_fee
      aggregation: avg
      format: "$#,##0.00"

  computed:
    avg_project_cost:
      description: "Average estimated project cost"
      formula: "total_estimated_cost / permit_count"
      format: "$#,##0"

# Metadata
metadata:
  domain: city
  entity: chicago
  subdomain: housing
status: active
---

## Chicago Housing Model

Building permits and zoning data for the City of Chicago.

### Data Sources

| Source | Bronze Table | Description |
|--------|--------------|-------------|
| Building Permits | chicago_building_permits | Permits issued |
| Zoning Districts | chicago_zoning_districts | Zoning boundaries |

### Permit Types

Common permit types:
- **NEW CONSTRUCTION** - New buildings
- **RENOVATION/ALTERATION** - Changes to existing structures
- **DEMOLITION** - Building teardowns
- **ELECTRICAL** - Electrical work permits
- **PLUMBING** - Plumbing work permits

### Zoning Categories

| Category | Description |
|----------|-------------|
| R | Residential |
| B | Business |
| C | Commercial |
| M | Manufacturing |
| PD | Planned Development |
| PMD | Planned Manufacturing District |

### Example Queries

```sql
-- Permits by type and year
SELECT
    pt.permit_category,
    p.year,
    COUNT(*) as permit_count,
    SUM(p.estimated_cost) as total_value
FROM fact_building_permits p
JOIN dim_permit_type pt ON p.permit_type_id = pt.permit_type_id
GROUP BY pt.permit_category, p.year
ORDER BY p.year DESC, total_value DESC;

-- New construction by community area
SELECT
    ca.community_name,
    COUNT(*) as new_construction_permits,
    SUM(p.estimated_cost) as total_investment
FROM fact_building_permits p
JOIN dim_permit_type pt ON p.permit_type_id = pt.permit_type_id
JOIN chicago_geospatial.dim_community_area ca ON p.community_area = ca.area_number
WHERE pt.permit_category = 'New Construction'
  AND p.year = 2023
GROUP BY ca.community_name
ORDER BY total_investment DESC;
```
