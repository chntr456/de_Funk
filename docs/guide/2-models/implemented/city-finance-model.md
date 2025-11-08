# City Finance Model

> **City of Chicago financial and economic data from the Chicago Data Portal**

The City Finance model provides municipal-level economic and financial data for Chicago, including community area unemployment rates, building permits, business licenses, and economic indicators. This model enables local economic analysis and comparison with national trends.

**Configuration:** `/home/user/de_Funk/configs/models/city_finance.yaml`
**Implementation:** `/home/user/de_Funk/models/implemented/city_finance/`

---

## Table of Contents

- [Overview](#overview)
- [Schema](#schema)
- [Data Sources](#data-sources)
- [Graph Structure](#graph-structure)
- [Usage Examples](#usage-examples)
- [Cross-Model Integration](#cross-model-integration)
- [Design Decisions](#design-decisions)

---

## Overview

### Purpose

The City Finance model provides:
- Community area unemployment rates (77 Chicago neighborhoods)
- Building permits with fees and locations
- Business licenses by type and area
- City-level economic indicators
- Pre-joined analytical views

### Key Features

- **Granular Geography** - 77 community areas
- **Event Data** - Building permits, business licenses
- **Economic Indicators** - Local unemployment, labor force
- **Location Data** - Latitude/longitude for mapping
- **Cross-Model Analysis** - Compare with national (Macro) data
- **Open Data** - Chicago Data Portal (public API)

### Model Characteristics

| Attribute | Value |
|-----------|-------|
| **Model Name** | `city_finance` |
| **Tags** | `municipal`, `chicago`, `city`, `finance`, `budget` |
| **Dependencies** | `core` (calendar), `macro` (national comparison) |
| **Data Source** | Chicago Data Portal (Socrata API) |
| **Storage Root** | `storage/silver/city_finance` |
| **Format** | Parquet |
| **Tables** | 6 (2 dimensions, 4 facts + 2 materialized) |
| **Dimensions** | 2 (dim_community_area, dim_permit_type) |
| **Facts** | 4 (unemployment, permits, licenses, indicators) |
| **Measures** | 5 |
| **Update Frequency** | Daily for permits/licenses, Monthly for unemployment |

---

## Schema

### Dimensions

#### dim_community_area

Chicago community areas (77 neighborhoods).

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

**Chicago Community Areas:**
- 77 distinct neighborhoods
- Official boundaries since 1920s
- Used for census and city planning
- More stable than ZIP codes or wards

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
| **permit_number** | string | Unique permit ID | 105678432 |
| **permit_type** | string | Type of permit (FK to dim_permit_type) | PERMIT, RENOVATION |
| **issue_date** | date | Date permit issued (partition) | 2024-11-08 |
| **total_fee** | double | Permit fee in USD | 850.00 |
| **contractor_name** | string | Contractor company name | ABC Construction Co. |
| **work_description** | string | Description of work | "New single family residence" |
| **community_area** | string | Community area code (FK) | 8 |
| **latitude** | double | Latitude coordinate | 41.8940 |
| **longitude** | double | Longitude coordinate | -87.6298 |

**Sample Data:**
```
+---------------+-------------+------------+-----------+---------------------+----------------------------+----------------+----------+-----------+
| permit_number | permit_type | issue_date | total_fee | contractor_name     | work_description           | community_area | latitude | longitude |
+---------------+-------------+------------+-----------+---------------------+----------------------------+----------------+----------+-----------+
| 105678432     | PERMIT      | 2024-11-08 |   850.00  | ABC Construction    | New single family home     | 8              | 41.8940  | -87.6298  |
| 105678433     | RENOVATION  | 2024-11-08 |   425.00  | XYZ Remodeling      | Kitchen renovation         | 32             | 41.8819  | -87.6278  |
| 105678434     | ELECTRICAL  | 2024-11-08 |   125.00  | Electric Works Inc  | Electrical panel upgrade   | 28             | 41.8796  | -87.6471  |
+---------------+-------------+------------+-----------+---------------------+----------------------------+----------------+----------+-----------+
```

#### fact_business_licenses

Active business licenses in Chicago.

**Path:** `storage/silver/city_finance/facts/fact_business_licenses`
**Partitions:** `start_date`
**Grain:** One row per business license

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **license_id** | string | Unique license ID | 2745321 |
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
| **community_area** | string | Community area code (optional) | 8, NULL |

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

### Measures

#### avg_local_unemployment

Average community area unemployment rate.

```yaml
avg_local_unemployment:
  description: "Average community area unemployment rate"
  source: fact_local_unemployment.unemployment_rate
  aggregation: avg
  data_type: double
  format: "#,##0.00%"
  tags: [unemployment, average, local]
```

#### total_permits_issued

Total building permits issued.

```yaml
total_permits_issued:
  description: "Total building permits issued"
  source: fact_building_permits.permit_number
  aggregation: count
  data_type: long
  format: "#,##0"
  tags: [permits, count]
```

#### total_permit_fees

Total permit fees collected (revenue).

```yaml
total_permit_fees:
  description: "Total permit fees collected"
  source: fact_building_permits.total_fee
  aggregation: sum
  data_type: double
  format: "$#,##0.00"
  tags: [permits, fees, revenue]
```

#### avg_permit_fee

Average permit fee.

```yaml
avg_permit_fee:
  description: "Average permit fee"
  source: fact_building_permits.total_fee
  aggregation: avg
  data_type: double
  format: "$#,##0.00"
  tags: [permits, fees, average]
```

#### total_labor_force

Total labor force across communities.

```yaml
total_labor_force:
  description: "Total labor force across communities"
  source: fact_local_unemployment.labor_force
  aggregation: sum
  data_type: long
  format: "#,##0"
  tags: [employment, labor_force]
```

---

## Data Sources

### Chicago Data Portal

The City Finance model sources data from the Chicago Data Portal (Socrata Open Data API).

**Portal URL:** https://data.cityofchicago.org/

**API Format:** Socrata Open Data API (SODA)
**Authentication:** Optional API token (recommended for higher rate limits)

### Dataset Details

#### Unemployment Rates by Community Area

```yaml
unemployment:
  dataset_id: "ane4-dwhs"
  name: "Chicago Unemployment Rates by Community Area"
  frequency: monthly
  granularity: community_area
  url: https://data.cityofchicago.org/resource/ane4-dwhs.json
```

**Description:**
- Monthly unemployment rates for 77 community areas
- Includes labor force, employed, unemployed counts
- Sourced from Illinois Department of Employment Security (IDES)
- Available: 1990-present

#### Building Permits

```yaml
building_permits:
  dataset_id: "ydr8-5enu"
  name: "Building Permits"
  frequency: event
  granularity: permit
  url: https://data.cityofchicago.org/resource/ydr8-5enu.json
```

**Description:**
- All building permits issued by Dept of Buildings
- Includes permit type, fees, contractor, location
- Real-time updates (within 24 hours)
- Available: 2006-present
- ~50,000+ permits per year

#### Business Licenses

```yaml
business_licenses:
  dataset_id: "r5kz-chrr"
  name: "Business Licenses"
  frequency: event
  granularity: license
  url: https://data.cityofchicago.org/resource/r5kz-chrr.json
```

**Description:**
- Active and inactive business licenses
- Includes business name, type, dates, location
- Updated daily
- Available: Current licenses + historical
- ~100,000+ active licenses

#### Economic Indicators

```yaml
economic_indicators:
  dataset_id: "nej5-8p3s"
  name: "Economic Indicators"
  frequency: monthly
  granularity: city
  url: https://data.cityofchicago.org/resource/nej5-8p3s.json
```

**Description:**
- Various city-level economic metrics
- Tourism, sales tax, building activity
- Monthly or quarterly depending on indicator

### Bronze Layer Mapping

| Bronze Table | Dataset ID | Silver Table |
|--------------|------------|--------------|
| `bronze.chicago_unemployment` | ane4-dwhs | `fact_local_unemployment` |
| `bronze.chicago_building_permits` | ydr8-5enu | `fact_building_permits` |
| `bronze.chicago_business_licenses` | r5kz-chrr | `fact_business_licenses` |
| `bronze.chicago_economic_indicators` | nej5-8p3s | `fact_economic_indicators` |

### Data Transformations

#### fact_local_unemployment
```python
bronze.chicago_unemployment
  .select(
    geography=geography,
    geography_type=geography_type,
    date=date,
    unemployment_rate=unemployment_rate,
    labor_force=labor_force,
    employed=employed,
    unemployed=unemployed
  )
  .partition_by(date)
```

#### fact_building_permits
```python
bronze.chicago_building_permits
  .select(
    permit_number=id,
    permit_type=permit_type,
    issue_date=issue_date,
    total_fee=total_fee,
    contractor_name=contractor_1_name,
    work_description=work_description,
    community_area=community_area,
    latitude=latitude,
    longitude=longitude
  )
  .partition_by(issue_date)
```

### Update Schedule

- **Unemployment** - Monthly (after IDES release, typically 3rd week)
- **Building Permits** - Daily (real-time from Dept of Buildings)
- **Business Licenses** - Daily (real-time from Dept of Business Affairs)
- **Economic Indicators** - Monthly/Quarterly depending on indicator

---

## Graph Structure

### ASCII Diagram

```
                    ┌─────────────────────────┐
                    │  dim_community_area     │
                    │                         │
                    │  • community_area (PK)  │
                    │  • community_name       │
                    │  • geography_type       │
                    │                         │
                    └────────┬────────────────┘
                             │
                             │ community_area
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        │                    │                    │
┌───────▼───────────┐ ┌──────▼──────────┐ ┌──────▼──────────┐
│fact_local_        │ │fact_building_   │ │fact_business_   │
│  unemployment     │ │  permits        │ │  licenses       │
│                   │ │                 │ │                 │
│  • geography      │ │  • permit_number│ │  • license_id   │
│  • date           │ │  • issue_date   │ │  • business_name│
│  • unemp_rate     │ │  • total_fee    │ │  • license_type │
│  • labor_force    │ │  • contractor   │ │  • start_date   │
│  • employed       │ │  • community_area│ │  • community_area│
│  • unemployed     │ │  • lat/long     │ │                 │
│                   │ │                 │ │                 │
│  Partitioned by   │ │  Partitioned by │ │  Partitioned by │
│  date             │ │  issue_date     │ │  start_date     │
└───────────────────┘ └─────────────────┘ └─────────────────┘
                             │
                             │ permit_type
                             │
                    ┌────────▼────────────┐
                    │  dim_permit_type    │
                    │                     │
                    │  • permit_type (PK) │
                    │  • permit_category  │
                    └─────────────────────┘

Materialized Paths:
  1. unemployment_with_area: fact_local_unemployment → dim_community_area
  2. permits_with_area:      fact_building_permits → dim_community_area

Cross-Model:
  ┌──────────────┐        ┌────────────────┐
  │ macro.fact_  │        │ city_finance.  │
  │ unemployment │   VS   │ fact_local_    │
  │              │        │ unemployment   │
  │ (National)   │        │ (Chicago)      │
  └──────────────┘        └────────────────┘

Legend:
  ┌─────┐
  │     │  = Table (dimension or fact)
  └─────┘

  ──▶    = Foreign key relationship
```

### Dependencies

```yaml
depends_on:
  - core  # Uses shared dim_calendar for time-based queries
  - macro # Compare local vs national indicators
```

---

## Usage Examples

### 1. Load City Finance Model

```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize session
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load city finance model
city_model = session.load_model('city_finance')
```

### 2. Get Community Area Unemployment

```python
# Get local unemployment
local_unemp = city_model.get_fact_df('fact_local_unemployment')

# Filter for specific community area
loop_unemp = local_unemp.filter(
    (F.col('geography') == '32') &  # Loop
    (F.col('date') >= '2024-01-01')
).orderBy('date')

loop_unemp.select('date', 'community_name', 'unemployment_rate', 'labor_force').show()
```

### 3. Analyze Building Permits by Area

```python
# Get permits
permits = city_model.get_fact_df('fact_building_permits')

# Count permits by community area
permits_by_area = permits.filter(
    F.col('issue_date') >= '2024-01-01'
).groupBy('community_area').agg(
    F.count('permit_number').alias('total_permits'),
    F.sum('total_fee').alias('total_fees'),
    F.avg('total_fee').alias('avg_fee')
).orderBy(F.desc('total_permits'))

permits_by_area.show(10)
```

### 4. Map Building Permits

```python
# Get permits with locations
permits_with_loc = permits.filter(
    (F.col('issue_date') >= '2024-11-01') &
    (F.col('latitude').isNotNull()) &
    (F.col('longitude').isNotNull())
)

# Convert to pandas for mapping
permits_pd = permits_with_loc.toPandas()

# Plot on map (using folium or plotly)
import folium

chicago_map = folium.Map(location=[41.8781, -87.6298], zoom_start=11)

for idx, row in permits_pd.iterrows():
    folium.CircleMarker(
        location=[row['latitude'], row['longitude']],
        radius=5,
        popup=f"{row['permit_type']}: ${row['total_fee']:.2f}",
        color='blue',
        fill=True
    ).add_to(chicago_map)

chicago_map.save('chicago_permits.html')
```

### 5. Use Materialized View

```python
# Get unemployment with community names
unemp_with_area = city_model.get_fact_df('unemployment_with_area')

# Easy to analyze with names
unemp_with_area.filter(F.col('date') == '2024-11-01').orderBy('unemployment_rate').show(10)

# +------------+-----------+------------------+-------------------+-------------+
# | date       | geography | community_name   | unemployment_rate | labor_force |
# +------------+-----------+------------------+-------------------+-------------+
# | 2024-11-01 | 32        | Loop             |       3.2         |    18234    |
# | 2024-11-01 | 8         | Near North Side  |       3.8         |    45830    |
# | ...
# +------------+-----------+------------------+-------------------+-------------+
```

### 6. Analyze Business License Types

```python
# Get licenses
licenses = city_model.get_fact_df('fact_business_licenses')

# Count by license type
licenses_by_type = licenses.groupBy('license_type').agg(
    F.count('license_id').alias('total_licenses')
).orderBy(F.desc('total_licenses'))

licenses_by_type.show(10)

# +-------------------------+------------------+
# | license_type            | total_licenses   |
# +-------------------------+------------------+
# | Retail Food             |      25430       |
# | Restaurant              |      15823       |
# | Limited Business License|      12456       |
# | ...
# +-------------------------+------------------+
```

### 7. Time Series Analysis: Permits Over Time

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
window_spec = Window.orderBy('month').rowsBetween(-2, 0)  # 3-month MA

permits_with_ma = monthly_permits.withColumn(
    'permit_count_ma',
    F.avg('permit_count').over(window_spec)
)

permits_with_ma.show()
```

---

## Cross-Model Integration

### Compare Local vs National Unemployment

```python
# Load macro model
macro_model = session.load_model('macro')
national_unemp = macro_model.get_fact_df('fact_unemployment')

# Load city finance
local_unemp = city_model.get_fact_df('fact_local_unemployment')

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

### Analyze Community-Level Disparities

```python
# Get all community area unemployment
community_unemp = local_unemp.filter(
    (F.col('geography_type') == 'community_area') &
    (F.col('date') == '2024-11-01')
)

# Join with national average
comparison = community_unemp.crossJoin(
    national_unemp.filter(F.col('date') == '2024-11-01')
        .select(F.col('value').alias('national_rate'))
).select(
    'geography',
    'unemployment_rate',
    'national_rate',
    (F.col('unemployment_rate') - F.col('national_rate')).alias('vs_national')
).orderBy(F.desc('unemployment_rate'))

# Show hardest hit communities
comparison.show(10)
```

### Join with Calendar for Seasonality

```python
# Load core model
core_model = session.load_model('core')
calendar = core_model.get_dimension_df('dim_calendar')

# Join permits with calendar
permits_with_dates = permits.join(
    calendar,
    permits.issue_date == calendar.date,
    how='left'
)

# Analyze by month
monthly_patterns = permits_with_dates.groupBy('month_name').agg(
    F.count('permit_number').alias('avg_permits')
).orderBy('month')

monthly_patterns.show()

# Peak building season: Spring/Summer (April-August)
```

### Economic Health Dashboard

```python
# Combine multiple indicators
from pyspark.sql import functions as F

# Get latest month
latest_date = '2024-11-01'

# Local unemployment
local_unemp_latest = local_unemp.filter(
    (F.col('geography') == 'Chicago') &
    (F.col('date') == latest_date)
).select('unemployment_rate')

# Building permits (last 30 days)
permits_30d = permits.filter(
    F.col('issue_date') >= F.date_sub(F.lit(latest_date), 30)
).agg(
    F.count('permit_number').alias('permits_30d'),
    F.sum('total_fee').alias('permit_fees_30d')
)

# New business licenses (last 30 days)
licenses_30d = licenses.filter(
    F.col('start_date') >= F.date_sub(F.lit(latest_date), 30)
).agg(
    F.count('license_id').alias('new_licenses_30d')
)

# Combine into dashboard
dashboard = local_unemp_latest.crossJoin(permits_30d).crossJoin(licenses_30d)
dashboard.show()

# +-------------------+-------------+------------------+-------------------+
# | unemployment_rate | permits_30d | permit_fees_30d  | new_licenses_30d  |
# +-------------------+-------------+------------------+-------------------+
# |       4.5         |     1234    |    $1,250,000    |        156        |
# +-------------------+-------------+------------------+-------------------+
```

---

## Design Decisions

### 1. 77 Community Areas

**Decision:** Use official 77 Chicago community areas as geographic grain

**Rationale:**
- Official city planning boundaries
- More stable than ZIP codes or wards
- Used consistently across datasets
- Historical comparability (since 1920s)

**Alternative:**
- ZIP codes: Change over time
- Wards: Political boundaries, redrawn regularly
- Census tracts: Too granular for most analysis

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
- Consistent with how BLS reports city-level data
- Avoids having to aggregate 77 areas

### 5. Materialized Views

**Decision:** Create `unemployment_with_area` and `permits_with_area`

**Rationale:**
- Common join pattern (fact → dim_community_area)
- Easier for analysts (no joins needed)
- Better performance for dashboards

### 6. Separate Tables for Licenses and Permits

**Decision:** Don't combine all event data in one table

**Rationale:**
- Different schemas (permits have fees, licenses have types)
- Different update frequencies
- Cleaner, more focused tables

---

## Summary

The City Finance model provides granular municipal economic data with:

- **77 Community Areas** - Neighborhood-level granularity
- **Multiple Indicators** - Unemployment, permits, licenses, economic data
- **Location Data** - Latitude/longitude for mapping
- **Cross-Model Integration** - Compare with national (Macro) trends
- **Open Data** - Chicago Data Portal (public access)
- **Real-time Updates** - Daily for permits/licenses

Essential for understanding local economic trends and community-level disparities.

---

**Next Steps:**
- See [Macro Model](macro-model.md) for national economic comparison
- See [Company Model](company-model.md) for market data
- See [Overview](../overview.md) for framework concepts

---

**Related Documentation:**
- [Chicago Data Portal](https://data.cityofchicago.org/)
- [Community Areas Map](https://en.wikipedia.org/wiki/Community_areas_in_Chicago)
- [Cross-Model Queries](../../1-getting-started/how-to/cross-model-queries.md)
- [Spatial Analysis Guide](../../5-domain-guides/geo/spatial-analysis.md)
