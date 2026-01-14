# Chicago Region Domain Structure

## Overview

Two distinct entity types with separate geospatial models:
- **Cook County** (county) - property, assessments, parcels
- **City of Chicago** (city) - contained by Cook County

## Domain Structure

```
domains/
├── _schema/                          # City-agnostic schema templates
│   ├── crime.yaml                    # Canonical crime schema + taxonomy
│   ├── service_request.yaml          # Canonical 311 schema
│   └── property.yaml                 # Canonical property schema
│
├── county/
│   └── cook_county/
│       ├── property.md               # Assessments, parcels, sales
│       ├── regulatory.md             # Appeals, permits
│       └── geospatial.md             # Townships, municipalities, parcels
│
├── city/
│   └── chicago/
│       ├── finance.md                # Payments, contracts, budget
│       ├── public_safety.md          # Crimes, arrests (refs _schema/crime.yaml)
│       ├── operations.md             # 311 requests (refs _schema/service_request.yaml)
│       ├── transportation.md         # CTA ridership, traffic
│       ├── housing.md                # Building permits, zoning
│       ├── regulatory.md             # Inspections, violations, licenses
│       └── geospatial.md             # Community areas, wards, beats
│
└── foundation/
    ├── temporal.md                   # Calendar dimension
    └── geospatial.md                 # Containment logic: Chicago ⊂ Cook County
```

## Entity Hierarchy

```
Cook County (county)
│
├── Townships (property tax administration)
│
├── Municipalities
│   ├── Chicago (city) ◄── foundation/geospatial provides
│   │   ├── Community Areas (77)      containment join logic
│   │   ├── Wards (50)
│   │   ├── Police Districts
│   │   └── Police Beats
│   ├── Evanston
│   ├── Oak Park
│   └── ... (130+ municipalities)
│
└── Unincorporated Areas
```

## Geospatial Approach

**Backend**: DuckDB spatial extension + Apache Sedona (Spark)

```sql
-- DuckDB spatial extension
INSTALL spatial;
LOAD spatial;

-- Point-in-polygon for geo assignment
SELECT c.*, ca.community_area_name
FROM chicago_crimes c
JOIN community_areas ca
  ON ST_Contains(ca.geometry, ST_Point(c.longitude, c.latitude));
```

**Foundation geospatial model provides:**
- Containment relationships (Chicago ⊂ Cook County)
- Lookup tables (community_area → township mapping)
- Pre-computed at build time, not query time

## Schema Strategy

**Bronze** = Source truth (preserve raw schema)
```
bronze/chicago_crimes/
├── year=2015/  # Schema v1: crime_type, desc, ...
├── year=2020/  # Schema v2: primary_type, description, ...
```

**Silver** = Unified model (apply schema template)
```
silver/chicago/public_safety/
├── dim_crime_type/   # Compressed, normalized
├── fact_crimes/      # Canonical columns, taxonomy assigned
```

**Schema templates** (`_schema/crime.yaml`):
- Define canonical column names
- Map source variants → canonical
- Define taxonomy with catch-all at each level
- City-agnostic, reusable

## Data Sources by Domain

### Cook County Property
| Bronze Table | Endpoint | Description |
|--------------|----------|-------------|
| cook_county_assessed_values | Assessed Values | 1999-present |
| cook_county_parcel_sales | Parcel Sales | Transactions |
| cook_county_parcels | Parcel Universe | All parcels |

### Chicago Public Safety
| Bronze Table | Endpoint | Description |
|--------------|----------|-------------|
| chicago_crimes | Crimes | 2001-present |
| chicago_arrests | Arrests | Arrest records |
| chicago_iucr_codes | IUCR Codes | Crime type reference |

### Chicago Operations
| Bronze Table | Endpoint | Description |
|--------------|----------|-------------|
| chicago_311_requests | 311 Requests | 2018-present |
| chicago_311_types | 311 Types | Request type reference |

### Chicago Finance
| Bronze Table | Endpoint | Description |
|--------------|----------|-------------|
| chicago_payments | Payments | 1996-present |
| chicago_contracts | Contracts | City contracts |
| chicago_budget_* | Budget | Revenue, appropriations, positions |

### Chicago Transportation
| Bronze Table | Endpoint | Description |
|--------------|----------|-------------|
| chicago_cta_l_ridership | L Ridership | Daily station entries |
| chicago_cta_bus_ridership | Bus Ridership | Daily route totals |
| chicago_traffic | Traffic | Segment congestion |

## Implementation Priority

1. **Chicago Public Safety** - crimes, arrests (high volume, good test case)
2. **Chicago Operations** - 311 requests
3. **Chicago Geospatial** - community areas, wards (enables spatial joins)
4. **Cook County Property** - assessments (different entity type)
5. **Foundation Geospatial** - containment logic

## Decisions Made

| Topic | Decision |
|-------|----------|
| Entity split | County vs City (not both "municipal") |
| Naming | "geospatial" not "geography" |
| Geospatial backend | DuckDB spatial + Sedona (existing backends) |
| Schema templates | `_schema/` folder, city-agnostic |
| Bronze | Preserve source schema exactly |
| Silver | Apply template, normalize, assign taxonomy |
| Taxonomy | Catch-all `_OTHER` at each level |
| Templates | Hold off on complex patterns for now |
