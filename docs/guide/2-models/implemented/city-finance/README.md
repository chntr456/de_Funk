---
title: "City Finance Model"
tags: [municipal, economics, component/model, source/chicago, status/stable]
aliases: ["City Finance", "Chicago Model", "Municipal Data"]
created: 2024-11-08
updated: 2024-11-08
status: stable
dependencies: ["[[Core Model]]"]
used_by: []
architecture_components:
  - "[[Data Pipeline]]"
  - "[[Facets]]"
  - "[[Providers]]"
  - "[[Bronze Storage]]"
  - "[[Silver Storage]]"
  - "[[Models System]]"
---

# City Finance Model

---

> **Chicago municipal and community data from the City of Chicago Data Portal**

The City Finance model provides hyperlocal economic data for Chicago, including building permits, business licenses, community area demographics, and geographic boundaries. This data enables analysis of neighborhood-level economic activity and development trends.

**Configuration:** `/home/user/de_Funk/configs/models/city_finance.yaml`
**Implementation:** `/home/user/de_Funk/models/implemented/city_finance/`

---

## Table of Contents

---

- [Overview](#overview)
- [Schema Overview](#schema-overview)
- [Data Sources](#data-sources)
- [Detailed Schema](#detailed-schema)
- [Community Areas](#community-areas)
- [Graph Structure](#graph-structure)
- [Measures](#measures)
- [How-To Guides](#how-to-guides)
- [Usage Examples](#usage-examples)
- [Cross-Model Integration](#cross-model-integration)
- [Design Decisions](#design-decisions)

---

## Overview

---

### Purpose

The City Finance model provides:
- Community area unemployment rates (77 Chicago neighborhoods)
- Building permits with fees and locations
- Business licenses by type and area
- City-level economic indicators
- Geographic boundaries for spatial analysis

### Key Features

- **Hyperlocal Data** - Neighborhood-level granularity (77 community areas)
- **Real-Time Updates** - Daily refresh from Chicago Data Portal
- **Geographic Context** - Latitude/longitude for mapping
- **Economic Indicators** - Construction fees, license counts, permit types
- **Open Data** - Free, public data from City of Chicago
- **Cross-Model Analysis** - Compare with national (Macro) data

### Model Characteristics

| Attribute | Value |
|-----------|-------|
| **Model Name** | `city_finance` |
| **Tags** | `municipal`, `chicago`, `permits`, `geographic` |
| **Dependencies** | [[Core Model]] (calendar dimension) |
| **Data Source** | Chicago Data Portal (Socrata API) |
| **Storage Root** | `storage/silver/city_finance` |
| **Format** | Parquet |
| **Tables** | 6 (2 dimensions, 4 facts, 2 materialized views) |
| **Dimensions** | 2 (dim_community_area, dim_permit_type) |
| **Facts** | 4 (unemployment, permits, licenses, indicators) |
| **Measures** | 5 |
| **Update Frequency** | Daily for permits/licenses, Monthly for unemployment |

---

## Architecture Components Used

---

This model uses the following architecture components:

### Primary Components

| Component | Purpose | Documentation |
|-----------|---------|---------------|
| **[[Data Pipeline/Chicago]]** | Ingest municipal data from Chicago Data Portal (Socrata API) | [[Data Pipeline Overview]] |
| **[[Facets/Municipal]]** | Normalize permits, licenses, unemployment, and community area data | [[Facets]] |
| **[[Providers/Chicago]]** | Chicago Data Portal provider implementation | [[Providers]] |
| **[[Bronze Storage]]** | Raw municipal data from Chicago | [[Bronze Layer]] |
| **[[Silver Storage]]** | Dimensional geographic/financial data (star schema) | [[Silver Layer]] |
| **[[Models System/Dimensional]]** | Multi-level dimensional modeling with geography | [[Base Model]] |

### Data Flow

Municipal data flows from Chicago Data Portal through facets for normalization, into Bronze storage, then transformed via the models system into geographic dimensional tables in Silver storage.

**Flow:** Chicago API → Facets (Municipal) → Bronze/chicago → BaseModel.build() → Silver/city_finance

See [[MODEL_ARCHITECTURE_MAPPING]] for complete architecture mapping.

---

## Schema Overview

---

### High-Level Summary

The City Finance model implements a **star schema** with community area dimension connected to permit, license, and unemployment facts. All data is sourced from the Chicago Data Portal and partitioned by date for optimal query performance.

**Quick Reference:**

| Table Type | Count | Purpose |
|------------|-------|---------|
| **Dimensions** | 2 | Chicago's 77 community areas + permit types |
| **Facts** | 4 | Unemployment, building permits, business licenses, economic indicators |
| **Materialized Views** | 2 | Pre-joined analytics tables |
| **Measures** | 5 | Pre-defined economic calculations |

### Dimensions (Geography & Reference)

| Dimension | Rows | Primary Key | Purpose |
|-----------|------|-------------|---------|
| **dim_community_area** | 77 | community_area | Chicago community areas with names |
| **dim_permit_type** | ~10-20 | permit_type | Building permit categorization |

### Facts (Economic Activity)

| Fact | Grain | Partitions | Purpose |
|------|-------|------------|---------|
| **fact_local_unemployment** | Monthly per community | date | Community area unemployment rates |
| **fact_building_permits** | Per permit | issue_date | Building permits with fees and work type |
| **fact_business_licenses** | Per license | start_date | Active business licenses by type |
| **fact_economic_indicators** | Per indicator per period | date | City-level economic metrics |

### Materialized Views (Analytics)

| View | Purpose | Grain |
|------|---------|-------|
| **unemployment_with_area** | Unemployment with community names | Monthly per community |
| **permits_with_area** | Permits with community names | Per permit |

### Star Schema Diagram

```
                    ┌─────────────────────────┐
                    │  dim_community_area     │
                    │  ───────────────────────│
                    │  community_area (PK)    │
                    │  community_name         │
                    │  geography_type         │
                    │                         │
                    │  77 Chicago communities │
                    └────────┬────────────────┘
                             │
                             │ (community_area)
                             │
        ┌────────────────────┼────────────────────┬──────────────────┐
        │                    │                    │                  │
        │                    │                    │                  │
┌───────▼──────────┐ ┌───────▼───────────┐ ┌─────▼─────────────┐ ┌─▼──────────────┐
│fact_local_       │ │fact_building_     │ │fact_business_     │ │fact_economic_  │
│ unemployment     │ │ permits           │ │ licenses          │ │ indicators     │
│                  │ │                   │ │                   │ │                │
│  • geography (FK)│ │  • permit_number  │ │  • license_id     │ │  • indicator   │
│  • date          │ │  • permit_type(FK)│ │  • business_name  │ │  • date        │
│  • unemp_rate    │ │  • issue_date     │ │  • license_type   │ │  • value       │
│  • labor_force   │ │  • total_fee      │ │  • start_date     │ │  • comm_area   │
│  • employed      │ │  • contractor     │ │  • comm_area (FK) │ │                │
│  • unemployed    │ │  • comm_area (FK) │ │                   │ │                │
│                  │ │  • lat/long       │ │                   │ │                │
│  Part: date      │ │  Part: issue_date │ │  Part: start_date │ │  Part: date    │
└──────────────────┘ └─────────┬─────────┘ └───────────────────┘ └────────────────┘
                               │
                               │ (permit_type)
                               │
                      ┌────────▼────────────┐
                      │  dim_permit_type    │
                      │  ───────────────────│
                      │  permit_type (PK)   │
                      │  permit_category    │
                      └─────────────────────┘
```

**Relationships:**
- `fact_local_unemployment.geography` → `dim_community_area.community_area` (many-to-one)
- `fact_building_permits.community_area` → `dim_community_area.community_area` (many-to-one)
- `fact_building_permits.permit_type` → `dim_permit_type.permit_type` (many-to-one)
- `fact_business_licenses.community_area` → `dim_community_area.community_area` (many-to-one)
- `fact_economic_indicators.community_area` → `dim_community_area.community_area` (many-to-one, nullable)
- All facts can join to [[Core Model]].dim_calendar on date

---

## Data Sources

---

### Chicago Data Portal (Socrata)

**Provider:** City of Chicago (https://data.cityofchicago.org)
**API:** Socrata Open Data API (SODA)
**Authentication:** App token (optional, recommended for higher rate limits)
**License:** Public domain (no restrictions)

### Datasets

#### Unemployment Rates by Community Area
```yaml
unemployment:
  dataset_id: "ane4-dwhs"
  name: "Chicago Unemployment Rates by Community Area"
  frequency: "Monthly"
  granularity: "Community area + city-wide"
  url: "https://data.cityofchicago.org/resource/ane4-dwhs.json"
  date_range: "1990-present"
```

**Description:**
- Monthly unemployment rates for 77 community areas
- Includes labor force, employed, unemployed counts
- Sourced from Illinois Department of Employment Security (IDES)
- Updated monthly (typically 3rd week after month ends)

#### Building Permits
```yaml
building_permits:
  dataset_id: "ydr8-5enu"
  name: "Building Permits"
  frequency: "Real-time (event-based)"
  granularity: "Per permit"
  url: "https://data.cityofchicago.org/resource/ydr8-5enu.json"
  rows: "~4.2M permits"
  date_range: "2006-present"
```

**Description:**
- All building permits issued by Department of Buildings
- Includes construction type, cost, fees, work description
- Geographic location (address, community area, lat/long)
- ~50,000+ permits issued per year

**Key Fields:**
- `permit_` - Permit number (unique ID)
- `issue_date` - Date permit issued
- `work_description` - Type of work
- `total_fee` - Permit fees collected
- `community_area` - Community area number
- `estimated_cost` - Declared construction cost

#### Business Licenses
```yaml
business_licenses:
  dataset_id: "r5kz-chrr"
  name: "Business Licenses - Current Active"
  frequency: "Daily"
  granularity: "Per license"
  url: "https://data.cityofchicago.org/resource/r5kz-chrr.json"
  rows: "~100k active licenses"
  date_range: "Active licenses only"
```

**Description:**
- Currently active business licenses
- License type, business activity, account number
- Geographic location (address, community area)
- Updated daily

**Key Fields:**
- `license_id` - License identifier
- `license_type` - Type of license
- `business_activity` - Specific business activity
- `license_start_date` - Date license became active
- `community_area` - Community area number
- `doing_business_as_name` - Business name

#### Economic Indicators
```yaml
economic_indicators:
  dataset_id: "nej5-8p3s"
  name: "Economic Indicators"
  frequency: "Monthly/Quarterly"
  granularity: "City-level"
  url: "https://data.cityofchicago.org/resource/nej5-8p3s.json"
```

**Description:**
- Various city-level economic metrics
- Tourism, sales tax, building activity
- Monthly or quarterly depending on indicator

### Bronze → Silver Transformation

**Pipeline:** `datapipelines/providers/chicago/`

```
Chicago Data Portal (Socrata API)
    ↓
Facets (normalize responses)
    ├─→ UnemploymentFacet
    ├─→ BuildingPermitsFacet
    ├─→ BusinessLicensesFacet
    └─→ EconomicIndicatorsFacet
    ↓
Bronze Storage (partitioned Parquet)
    ├─→ bronze/chicago_unemployment/ (partitioned by year)
    ├─→ bronze/chicago_building_permits/ (partitioned by year)
    ├─→ bronze/chicago_business_licenses/
    └─→ bronze/chicago_economic_indicators/
    ↓
BaseModel.build() (YAML-driven graph transformation)
    ↓
Silver Storage (dimensional model)
    ├─→ silver/city_finance/dims/dim_community_area/
    ├─→ silver/city_finance/dims/dim_permit_type/
    ├─→ silver/city_finance/facts/fact_local_unemployment/
    ├─→ silver/city_finance/facts/fact_building_permits/
    ├─→ silver/city_finance/facts/fact_business_licenses/
    ├─→ silver/city_finance/facts/fact_economic_indicators/
    ├─→ silver/city_finance/facts/unemployment_with_area/ (materialized)
    └─→ silver/city_finance/facts/permits_with_area/ (materialized)
```

### Update Schedule

**Data Pipeline:**
- **Unemployment** - Monthly (after IDES release, typically 3rd week)
- **Building Permits** - Daily (real-time from Dept of Buildings)
- **Business Licenses** - Daily (real-time from Dept of Business Affairs)
- **Economic Indicators** - Monthly/Quarterly depending on indicator

### Data Quality

- **Completeness:** Historical permits back to 2006, unemployment to 1990
- **Accuracy:** Official city records
- **Timeliness:** Daily for permits/licenses, monthly for unemployment
- **Consistency:** Schema validated via facets
- **Geographic Coverage:** All 77 community areas

---

## Detailed Schema

---

### Dimensions

#### dim_community_area

Chicago's 77 official community areas.

**Path:** `storage/silver/city_finance/dims/dim_community_area`
**Primary Key:** `community_area`
**Grain:** One row per community area

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **community_area** | string | Community area code (PK) | 8, 32, 76 |
| **community_name** | string | Official neighborhood name | Loop, Near North Side, O'Hare |
| **geography_type** | string | Geographic level | community_area, city |

**Sample Data:**
```
+----------------+------------------+------------------+
| community_area | community_name   | geography_type   |
+----------------+------------------+------------------+
| 1              | Rogers Park      | community_area   |
| 8              | Near North Side  | community_area   |
| 28             | Near West Side   | community_area   |
| 32             | Loop             | community_area   |
| 76             | O'Hare           | community_area   |
+----------------+------------------+------------------+
```

**Geographic Hierarchy:**
```
Chicago
  ├─ Community Area 1: Rogers Park
  ├─ Community Area 2: West Ridge
  ├─ Community Area 3: Uptown
  ...
  ├─ Community Area 32: Loop (Downtown)
  ...
  └─ Community Area 77: Edgewater
```

#### dim_permit_type

Building permit types and categories.

**Path:** `storage/silver/city_finance/dims/dim_permit_type`
**Primary Key:** `permit_type`
**Grain:** One row per permit type

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **permit_type** | string | Permit type code (PK) | PERMIT, RENOVATION, DEMOLITION |
| **permit_category** | string | Broader category | construction, electrical, plumbing |

**Sample Data:**
```
+--------------------+-------------------+
| permit_type        | permit_category   |
+--------------------+-------------------+
| PERMIT             | construction      |
| RENOVATION         | construction      |
| DEMOLITION         | construction      |
| ELECTRICAL         | electrical        |
| PLUMBING           | plumbing          |
+--------------------+-------------------+
```

### Facts

#### fact_local_unemployment

Unemployment by Chicago community area (monthly).

**Path:** `storage/silver/city_finance/facts/fact_local_unemployment`
**Partitions:** `date`
**Grain:** One row per community area per month

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **geography** | string | Community area code | 8, 32, Chicago |
| **geography_type** | string | Geographic level | community_area, city |
| **date** | date | First day of month (partition) | 2024-11-01 |
| **unemployment_rate** | double | Unemployment rate (percent) | 4.2 |
| **labor_force** | long | Total labor force | 45830 |
| **employed** | long | Number employed | 43906 |
| **unemployed** | long | Number unemployed | 1924 |

**Sample Data:**
```
+-----------+------------------+------------+-------------------+-------------+----------+------------+
| geography | geography_type   | date       | unemployment_rate | labor_force | employed | unemployed |
+-----------+------------------+------------+-------------------+-------------+----------+------------+
| 8         | community_area   | 2024-11-01 |       4.2         |    45830    |  43906   |    1924    |
| 32        | community_area   | 2024-11-01 |       3.8         |    18234    |  17542   |     692    |
| Chicago   | city             | 2024-11-01 |       4.5         |  1345678    | 1285123  |   60555    |
+-----------+------------------+------------+-------------------+-------------+----------+------------+
```

**Calculation:**
```python
unemployment_rate = (unemployed / labor_force) × 100
```

#### fact_building_permits

Building permits issued in Chicago.

**Path:** `storage/silver/city_finance/facts/fact_building_permits`
**Partitions:** `issue_date`
**Grain:** One row per permit

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **permit_number** | string | Unique permit ID (PK) | 105678432 |
| **permit_type** | string | Type of permit (FK) | PERMIT, RENOVATION |
| **issue_date** | date | Date permit issued (partition) | 2024-11-08 |
| **total_fee** | double | Permit fee in USD | 850.00 |
| **contractor_name** | string | Contractor company name | ABC Construction Co. |
| **work_description** | string | Description of work | New single family residence |
| **community_area** | string | Community area code (FK) | 8 |
| **latitude** | double | Latitude coordinate | 41.8940 |
| **longitude** | double | Longitude coordinate | -87.6298 |

**Sample Data:**
```
+---------------+-------------+------------+-----------+---------------------+----------------------------+----------------+
| permit_number | permit_type | issue_date | total_fee | contractor_name     | work_description           | community_area |
+---------------+-------------+------------+-----------+---------------------+----------------------------+----------------+
| 105678432     | PERMIT      | 2024-11-08 |   850.00  | ABC Construction    | New single family home     | 8              |
| 105678433     | RENOVATION  | 2024-11-08 |   425.00  | XYZ Remodeling      | Kitchen renovation         | 32             |
| 105678434     | ELECTRICAL  | 2024-11-08 |   125.00  | Electric Works Inc  | Electrical panel upgrade   | 28             |
+---------------+-------------+------------+-----------+---------------------+----------------------------+----------------+

+----------+-----------+
| latitude | longitude |
+----------+-----------+
| 41.8940  | -87.6298  |
| 41.8819  | -87.6278  |
| 41.8796  | -87.6471  |
+----------+-----------+
```

**Permit Types:**
- **PERMIT** - New construction
- **RENOVATION** - Alterations, additions
- **ELECTRICAL** - Electrical work
- **PLUMBING** - Plumbing work
- **DEMOLITION** - Building demolition

#### fact_business_licenses

Active business licenses in Chicago.

**Path:** `storage/silver/city_finance/facts/fact_business_licenses`
**Partitions:** `start_date`
**Grain:** One row per business license

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **license_id** | string | Unique license ID (PK) | 2745321 |
| **business_name** | string | Business name | Joe's Coffee Shop |
| **license_type** | string | Type of license | Retail Food, Restaurant |
| **start_date** | date | License start date (partition) | 2024-01-15 |
| **community_area** | string | Community area code (FK) | 8 |

**Sample Data:**
```
+------------+-------------------------+-------------------+------------+----------------+
| license_id | business_name           | license_type      | start_date | community_area |
+------------+-------------------------+-------------------+------------+----------------+
| 2745321    | Joe's Coffee Shop       | Retail Food       | 2024-01-15 | 8              |
| 2745322    | Chicago Pizza Co.       | Restaurant        | 2024-02-01 | 32             |
| 2745323    | Smith & Sons Hardware   | Retail Merchant   | 2024-03-10 | 28             |
+------------+-------------------------+-------------------+------------+----------------+
```

**License Types:**
- **Retail Food Establishment** - Grocery, restaurant, catering
- **Liquor** - Bars, taverns, liquor stores
- **Public Place of Amusement** - Theaters, gyms, arcades
- **Limited Business License** - General business

#### fact_economic_indicators

City-level economic indicators.

**Path:** `storage/silver/city_finance/facts/fact_economic_indicators`
**Partitions:** `date`
**Grain:** One row per indicator per time period per area

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **indicator_name** | string | Name of indicator | median_income, crime_rate |
| **date** | date | Date of measurement (partition) | 2024-11-01 |
| **value** | double | Indicator value | 67500.00 |
| **community_area** | string | Community area code (optional FK) | 8, NULL |

**Sample Data:**
```
+------------------+------------+----------+----------------+
| indicator_name   | date       | value    | community_area |
+------------------+------------+----------+----------------+
| median_income    | 2024-01-01 | 67500.00 | 8              |
| median_income    | 2024-01-01 | 125000.0 | 32             |
| sales_tax_rev    | 2024-11-01 | 8500000  | NULL           |
+------------------+------------+----------+----------------+
```

### Materialized Views

#### unemployment_with_area

Local unemployment with community area details.

**Path:** `storage/silver/city_finance/facts/unemployment_with_area`
**Partitions:** `date`
**Tags:** `analytics`, `materialized`

| Column | Type | Description |
|--------|------|-------------|
| **date** | date | First day of month |
| **geography** | string | Community area code |
| **community_name** | string | Community area name (from dim) |
| **unemployment_rate** | double | Unemployment rate |
| **labor_force** | long | Labor force |
| **employed** | long | Number employed |
| **unemployed** | long | Number unemployed |

**Graph Path:** `fact_local_unemployment → dim_community_area`

#### permits_with_area

Building permits with community area context.

**Path:** `storage/silver/city_finance/facts/permits_with_area`
**Partitions:** `issue_date`
**Tags:** `analytics`, `materialized`

| Column | Type | Description |
|--------|------|-------------|
| **issue_date** | date | Permit issue date |
| **permit_number** | string | Permit ID |
| **permit_type** | string | Permit type |
| **total_fee** | double | Permit fee |
| **contractor_name** | string | Contractor |
| **community_area** | string | Area code |
| **community_name** | string | Area name (from dim) |
| **latitude** | double | Location latitude |
| **longitude** | double | Location longitude |

**Graph Path:** `fact_building_permits → dim_community_area`

---

## Community Areas

---

### Overview

Chicago is divided into **77 community areas** defined by the University of Chicago in the 1920s. These areas are used for statistical and planning purposes.

### Geographic Distribution

**North Side (Areas 1-14):**
- Rogers Park, West Ridge, Uptown, Lincoln Square, Edison Park, etc.

**Northwest Side (Areas 15-20):**
- Portage Park, Irving Park, Dunning, etc.

**West Side (Areas 21-31):**
- Austin, West Town, Humboldt Park, etc.

**Central (Areas 32-33):**
- Loop (downtown), Near South Side

**Southwest Side (Areas 56-71):**
- Garfield Ridge, Clearing, West Lawn, etc.

**South Side (Areas 34-55, 72-77):**
- Armour Square, Douglas, Oakland, etc.

### Notable Areas

| Area | Name | Characteristics |
|------|------|-----------------|
| **1** | Rogers Park | Diverse, lakefront, residential |
| **8** | Near North Side | Gold Coast, shopping, entertainment |
| **32** | Loop | Central business district, high-rise development |
| **7** | Lincoln Park | Affluent, lakefront, parks |
| **28** | Near West Side | University of Illinois, medical district |
| **76** | O'Hare | Airport, industrial |

---

## Graph Structure

---

### Nodes, Edges, Paths

**Nodes:**
- `dim_community_area`
- `dim_permit_type`
- `fact_local_unemployment`
- `fact_building_permits`
- `fact_business_licenses`
- `fact_economic_indicators`

**Edges:**
- `fact_local_unemployment → dim_community_area` (geography)
- `fact_building_permits → dim_community_area` (community_area)
- `fact_building_permits → dim_permit_type` (permit_type)
- `fact_business_licenses → dim_community_area` (community_area)
- `fact_economic_indicators → dim_community_area` (community_area, optional)

**Paths:**
- `unemployment_with_area`: fact_local_unemployment → dim_community_area
- `permits_with_area`: fact_building_permits → dim_community_area

---

## Measures

---

### Simple Aggregations

| Measure | Source | Aggregation | Format | Purpose |
|---------|--------|-------------|--------|---------|
| **avg_local_unemployment** | fact_local_unemployment.unemployment_rate | avg | #,##0.00% | Average community unemployment rate |
| **total_permits_issued** | fact_building_permits.permit_number | count | #,##0 | Total building permits issued |
| **total_permit_fees** | fact_building_permits.total_fee | sum | $#,##0.00 | Total permit fees collected |
| **avg_permit_fee** | fact_building_permits.total_fee | avg | $#,##0.00 | Average permit fee |
| **total_labor_force** | fact_local_unemployment.labor_force | sum | #,##0 | Total labor force |

**Example YAML Definition:**
```yaml
measures:
  avg_local_unemployment:
    description: "Average community area unemployment rate"
    source: fact_local_unemployment.unemployment_rate
    aggregation: avg
    data_type: double
    format: "#,##0.00%"
    tags: [unemployment, average, local]

  total_permits_issued:
    description: "Total building permits issued"
    source: fact_building_permits.permit_number
    aggregation: count
    data_type: long
    format: "#,##0"
    tags: [permits, count]

  total_permit_fees:
    description: "Total permit fees collected"
    source: fact_building_permits.total_fee
    aggregation: sum
    data_type: double
    format: "$#,##0.00"
    tags: [permits, fees, revenue]
```

---

## How-To Guides

---

### How to Query Community Data

**Step 1:** Load the city finance model

```python
from core.context import RepoContext
from models.api.session import UniversalSession
import pyspark.sql.functions as F

# Initialize
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load city finance model
city = session.load_model('city_finance')
```

**Step 2:** Get community areas

```python
# Get all community areas
communities = city.get_dimension_df('dim_community_area')

# Show all 77 areas
communities.select(
    'community_area',
    'community_name',
    'geography_type'
).orderBy('community_area').show(10)

# +----------------+------------------+------------------+
# | community_area | community_name   | geography_type   |
# +----------------+------------------+------------------+
# | 1              | Rogers Park      | community_area   |
# | 2              | West Ridge       | community_area   |
# | 3              | Uptown           | community_area   |
# | ...
# +----------------+------------------+------------------+
```

**Step 3:** Get unemployment for a community

```python
# Get unemployment data
unemployment = city.get_fact_df('fact_local_unemployment')

# Filter for Loop (area 32)
loop_unemp = unemployment.filter(
    (F.col('geography') == '32') &
    (F.col('date') >= '2024-01-01')
).orderBy('date')

loop_unemp.select('date', 'unemployment_rate', 'labor_force').show()
```

**Step 4:** Analyze unemployment by community

```python
# Join with community names
communities = city.get_dimension_df('dim_community_area')

unemp_with_names = unemployment.join(
    communities.select('community_area', 'community_name'),
    unemployment.geography == communities.community_area
).filter(F.col('date') == '2024-11-01')

# Show communities sorted by unemployment rate
unemp_with_names.select(
    'community_name', 'unemployment_rate', 'labor_force'
).orderBy(F.desc('unemployment_rate')).show(10)
```

---

### How to Map Geographic Data

**Step 1:** Get permits with locations

```python
# Get permits with latitude/longitude
permits = city.get_fact_df('fact_building_permits').filter(
    (F.col('issue_date') >= '2024-11-01') &
    (F.col('latitude').isNotNull()) &
    (F.col('longitude').isNotNull())
)

# Convert to pandas for mapping
permits_pd = permits.limit(1000).toPandas()
```

**Step 2:** Create a map with folium

```python
import folium

# Create base map centered on Chicago
chicago_map = folium.Map(
    location=[41.8781, -87.6298],  # Chicago coordinates
    zoom_start=11,
    tiles='OpenStreetMap'
)

# Add permit markers
for idx, row in permits_pd.iterrows():
    folium.CircleMarker(
        location=[row['latitude'], row['longitude']],
        radius=5,
        popup=f"{row['work_description']}<br>Fee: ${row['total_fee']:,.2f}",
        color='blue',
        fill=True,
        fillColor='blue'
    ).add_to(chicago_map)

# Save map
chicago_map.save('chicago_permits.html')
```

**Step 3:** Create a heatmap

```python
from folium.plugins import HeatMap

# Create heatmap of permit density
heat_data = [[row['latitude'], row['longitude']] for _, row in permits_pd.iterrows()]

heatmap_map = folium.Map(
    location=[41.8781, -87.6298],
    zoom_start=11
)

HeatMap(heat_data).add_to(heatmap_map)
heatmap_map.save('permit_heatmap.html')
```

---

### How to Analyze Permits

**Step 1:** Get permit data

```python
# Load permits
permits = city.get_fact_df('fact_building_permits')

# Filter for 2024
permits_2024 = permits.filter(F.col('issue_date') >= '2024-01-01')
```

**Step 2:** Analyze by permit type

```python
# Count permits by type
permits_by_type = permits_2024.groupBy('permit_type').agg(
    F.count('permit_number').alias('num_permits'),
    F.sum('total_fee').alias('total_fees'),
    F.avg('total_fee').alias('avg_fee')
)

permits_by_type.orderBy(F.desc('num_permits')).show()

# +-------------+-------------+------------+----------+
# | permit_type | num_permits | total_fees | avg_fee  |
# +-------------+-------------+------------+----------+
# | PERMIT      |    12000    | 15000000.0 | 1250.00  |
# | RENOVATION  |     5000    |  2125000.0 |  425.00  |
# | ELECTRICAL  |     3000    |   375000.0 |  125.00  |
# +-------------+-------------+------------+----------+
```

**Step 3:** Analyze by community area

```python
# Get communities and permits
communities = city.get_dimension_df('dim_community_area')

# Permits by community
permits_by_community = permits_2024.groupBy('community_area').agg(
    F.count('permit_number').alias('num_permits'),
    F.sum('total_fee').alias('total_fees')
).join(
    communities.select('community_area', 'community_name'),
    on='community_area'
)

# Top 10 communities by permits
permits_by_community.orderBy(F.desc('num_permits')).show(10)
```

**Step 4:** Time series analysis

```python
from pyspark.sql import Window

# Monthly permit counts
monthly_permits = permits.groupBy(
    F.date_trunc('month', 'issue_date').alias('month')
).agg(
    F.count('permit_number').alias('permit_count'),
    F.sum('total_fee').alias('total_fees')
).orderBy('month')

# Calculate moving average
window_spec = Window.orderBy('month').rowsBetween(-2, 0)

permits_with_ma = monthly_permits.withColumn(
    'permit_count_ma',
    F.avg('permit_count').over(window_spec)
)

# Show recent trends
permits_with_ma.filter(F.year('month') == 2024).show()
```

---

## Usage Examples

---

See detailed usage examples in the original documentation above, including:
1. Load City Finance Model
2. Get Community Area Unemployment
3. Analyze Building Permits by Area
4. Map Building Permits
5. Use Materialized Views
6. Analyze Business License Types
7. Time Series Analysis

---

## Cross-Model Integration

---

### Compare Local vs National Unemployment

```python
# Load macro model
macro_model = session.load_model('macro')
national_unemp = macro_model.get_fact_df('fact_unemployment')

# Load city finance
local_unemp = city.get_fact_df('fact_local_unemployment')

# Get Chicago city-level
chicago_unemp = local_unemp.filter(F.col('geography') == 'Chicago')

# Join national and local
comparison = national_unemp.select(
    F.col('date'),
    F.col('value').alias('national_rate')
).join(
    chicago_unemp.select(
        F.col('date'),
        F.col('unemployment_rate').alias('chicago_rate')
    ),
    on='date',
    how='inner'
).withColumn(
    'diff',
    F.col('chicago_rate') - F.col('national_rate')
)

comparison.orderBy('date').show()

# +------------+---------------+--------------+------+
# | date       | national_rate | chicago_rate | diff |
# +------------+---------------+--------------+------+
# | 2024-01-01 |     3.7       |     4.8      | 1.1  |
# | 2024-02-01 |     3.9       |     5.0      | 1.1  |
# | ...
# +------------+---------------+--------------+------+
```

See [[Macro Model]] for national economic data.

---

## Design Decisions

---

### 1. 77 Community Areas

**Decision:** Use official 77 Chicago community areas as geographic grain

**Rationale:**
- Official city planning boundaries
- More stable than ZIP codes or wards
- Used consistently across datasets
- Historical comparability (since 1920s)

### 2. Include Latitude/Longitude

**Decision:** Include lat/long for building permits

**Rationale:**
- Enables mapping and spatial analysis
- Useful for clustering and hotspot detection
- Small storage overhead

### 3. Partition by Date

**Decision:** Partition facts by date columns (issue_date, start_date)

**Rationale:**
- Most queries filter by recent time periods
- Event data grows continuously
- Easy to archive old partitions

### 4. City-Level Aggregates

**Decision:** Include city-level unemployment (not just community areas)

**Rationale:**
- Easy comparison with national data
- Consistent with how data is reported
- Avoids having to aggregate 77 areas

### 5. Materialized Views

**Decision:** Create `unemployment_with_area` and `permits_with_area`

**Rationale:**
- Common join pattern (fact → dim_community_area)
- Easier for analysts (no joins needed)
- Better performance for dashboards

---

## Related Documentation

---

### Model Documentation
- [[Core Model]] - Shared calendar dimension
- [[Macro Model]] - National economic indicators for comparison
- [[Company Model]] - Stock market data
- [Chicago Data Portal](https://data.cityofchicago.org) - Data source

### Architecture Documentation
- [[MODEL_ARCHITECTURE_MAPPING]] - Complete architecture mapping
- [[Data Pipeline]] - Chicago Data Portal ingestion pipeline
- [[Facets]] - Municipal data normalization
- [[Providers]] - Chicago provider implementation
- [[Bronze Storage]] - Raw municipal data storage
- [[Silver Storage]] - Geographic dimensional storage
- [[Universal Session]] - Cross-model query examples

---

**Tags:** #municipal #economics #component/model #source/chicago #status/stable #component/data-pipeline/chicago #component/facets/municipal #component/providers/chicago #component/storage/bronze #component/storage/silver #component/models-system/dimensional #architecture/ingestion-to-analytics #pattern/star-schema #pattern/geographic

**Last Updated:** 2024-11-08
**Model Version:** 1.0
**Dependencies:** [[Core Model]]
**Used By:** N/A
