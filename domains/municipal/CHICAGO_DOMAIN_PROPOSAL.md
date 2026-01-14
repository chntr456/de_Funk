# Chicago Data Domain Structure Proposal

## Overview

The Chicago region data spans two providers with distinct data domains:
- **Chicago Data Portal** - City of Chicago municipal data
- **Cook County Data Portal** - Cook County (property assessment, parcels)

## Proposed Structure

```
domains/
├── municipal/
│   ├── chicago/                       # City of Chicago
│   │   ├── finance.md                 # Payments, contracts, budget
│   │   ├── public_safety.md           # Crimes, arrests, police
│   │   ├── operations.md              # 311 service requests
│   │   ├── transportation.md          # CTA ridership, traffic
│   │   ├── housing.md                 # Building permits, zoning
│   │   └── regulatory.md              # Inspections, violations, licenses
│   │
│   └── cook_county/                   # Cook County
│       ├── property.md                # Assessed values, sales, parcels
│       └── regulatory.md              # Appeals, permits
│
├── foundation/
│   ├── temporal.md                    # Calendar (existing)
│   └── chicago_geography.md           # Shared geography dimension
│       # Community areas, wards, beats, districts, townships
```

## Domain Breakdown

### Chicago Finance (`domains/municipal/chicago/finance.md`)

| Bronze Table | Source | Description |
|--------------|--------|-------------|
| chicago_payments | Payments | Vendor payments 1996-present |
| chicago_contracts | Contracts | City contracts |
| chicago_budget_revenue | Budget Revenue | Budget ordinance revenue |
| chicago_budget_appropriations | Budget Appropriations | Budget appropriations |
| chicago_budget_positions | Positions & Salaries | Employee positions |

**Dimensions**: `dim_vendor`, `dim_department`, `dim_contract`
**Facts**: `fact_payments`, `fact_budget_revenue`, `fact_budget_appropriations`

### Chicago Public Safety (`domains/municipal/chicago/public_safety.md`)

| Bronze Table | Source | Description |
|--------------|--------|-------------|
| chicago_crimes | Crimes | Crime incidents 2001-present |
| chicago_arrests | Arrests | Arrest records |
| chicago_iucr_codes | IUCR Codes | Crime type reference |
| chicago_police_stations | Police Stations | Station locations |
| chicago_police_beats | Police Beats | Beat boundaries |

**Dimensions**: `dim_iucr_code`, `dim_police_beat`, `dim_police_district`
**Facts**: `fact_crimes`, `fact_arrests`

### Chicago Operations (`domains/municipal/chicago/operations.md`)

| Bronze Table | Source | Description |
|--------------|--------|-------------|
| chicago_311_requests | 311 Requests | Service requests 2018-present |
| chicago_311_types | 311 Types | Request type reference |

**Dimensions**: `dim_service_type`
**Facts**: `fact_service_requests`

### Chicago Transportation (`domains/municipal/chicago/transportation.md`)

| Bronze Table | Source | Description |
|--------------|--------|-------------|
| chicago_cta_l_ridership | L Ridership | Daily L station ridership |
| chicago_cta_bus_ridership | Bus Ridership | Daily bus route ridership |
| chicago_cta_l_stops | L Stops | L station locations |
| chicago_cta_bus_stops | Bus Stops | Bus stop locations |
| chicago_traffic_congestion | Traffic | Traffic segment congestion |

**Dimensions**: `dim_l_station`, `dim_bus_route`, `dim_traffic_segment`
**Facts**: `fact_l_ridership`, `fact_bus_ridership`, `fact_traffic_congestion`

### Chicago Housing (`domains/municipal/chicago/housing.md`)

| Bronze Table | Source | Description |
|--------------|--------|-------------|
| chicago_building_permits | Building Permits | Permit applications |
| chicago_zoning_districts | Zoning | Zoning district boundaries |

**Dimensions**: `dim_zoning_district`
**Facts**: `fact_building_permits`

### Chicago Regulatory (`domains/municipal/chicago/regulatory.md`)

| Bronze Table | Source | Description |
|--------------|--------|-------------|
| chicago_food_inspections | Food Inspections | Restaurant inspections |
| chicago_building_violations | Building Violations | Code violations |
| chicago_ordinance_violations | Ordinance Violations | Municipal code violations |
| chicago_business_licenses | Business Licenses | Active business licenses |

**Dimensions**: `dim_business`, `dim_violation_type`
**Facts**: `fact_food_inspections`, `fact_building_violations`, `fact_business_licenses`

### Cook County Property (`domains/municipal/cook_county/property.md`)

| Bronze Table | Source | Description |
|--------------|--------|-------------|
| cook_county_assessed_values | Assessed Values | Property assessments 1999-present |
| cook_county_parcel_sales | Parcel Sales | Property transactions |
| cook_county_tax_exempt | Tax-Exempt | Tax-exempt parcels |
| cook_county_parcel_universe | Parcel Universe | All parcels |
| cook_county_parcel_addresses | Parcel Addresses | Parcel address mapping |
| cook_county_residential | Residential Chars | Residential property details |
| cook_county_commercial | Commercial Values | Commercial valuations |

**Dimensions**: `dim_parcel`, `dim_property_class`, `dim_township`
**Facts**: `fact_assessed_values`, `fact_parcel_sales`

### Chicago Geography (`domains/foundation/chicago_geography.md`)

Shared geography dimension used across all Chicago/Cook County models:

| Table | Description |
|-------|-------------|
| dim_community_area | 77 Chicago community areas |
| dim_ward | 50 Chicago wards |
| dim_police_beat | Police beats |
| dim_police_district | Police districts |
| dim_township | Cook County townships |

**Cross-model edges**: All fact tables with geography can join to these dimensions.

## Python Module Structure

```
models/domains/municipal/
├── __init__.py
├── chicago/
│   ├── __init__.py
│   ├── finance/
│   │   ├── __init__.py
│   │   ├── model.py
│   │   └── builder.py
│   ├── public_safety/
│   │   ├── __init__.py
│   │   ├── model.py
│   │   └── builder.py
│   ├── operations/
│   ├── transportation/
│   ├── housing/
│   └── regulatory/
└── cook_county/
    ├── __init__.py
    └── property/
        ├── __init__.py
        ├── model.py
        └── builder.py
```

## Cross-Model Relationships

```
Chicago Geography (foundation)
    ↑
    ├── Chicago Finance
    ├── Chicago Public Safety (crimes have community_area, ward, beat)
    ├── Chicago Operations (311 has community_area, ward)
    ├── Chicago Transportation (stations have community_area)
    ├── Chicago Housing (permits have ward)
    └── Cook County Property (parcels have township)
```

## Alternative Structure Considered

**Flat by category** (rejected):
```
domains/municipal/
├── finance.md          # Mixed Chicago + Cook County
├── public_safety.md    # Chicago only
├── property.md         # Cook County only
```

Rejected because:
- Chicago finance (payments, budget) is fundamentally different from Cook County finance (property taxes)
- Would conflate different legal entities and data schemas
- Harder to understand data lineage

## Implementation Priority

1. **Phase 1**: Chicago Public Safety (crimes, arrests) - high volume, interesting
2. **Phase 2**: Chicago Operations (311) - good for city services analysis
3. **Phase 3**: Chicago Finance (payments, contracts) - government spending
4. **Phase 4**: Cook County Property (assessments) - property tax analysis
5. **Phase 5**: Chicago Transportation (CTA ridership) - transit patterns
6. **Phase 6**: Chicago Geography (shared dimension) - enable cross-domain analysis

## Open Questions

1. Should `chicago_geography` be in `foundation/` or `municipal/chicago/`?
2. Should we create `_base/municipal` templates for common patterns?
3. How to handle multi-year datasets with different schemas (e.g., old 311 system)?
