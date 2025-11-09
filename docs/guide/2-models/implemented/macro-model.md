---
title: "Macro Model"
tags: [economics/bls, component/model, source/bls, status/stable]
aliases: ["Macro", "Economics Model", "BLS Model"]
created: 2024-11-08
updated: 2024-11-08
status: stable
dependencies: ["[[Core Model]]"]
used_by: ["[[Company Model]]"]
architecture_components:
  - "[[Data Pipeline]]"
  - "[[Facets]]"
  - "[[Providers]]"
  - "[[Bronze Storage]]"
  - "[[Silver Storage]]"
  - "[[Models System]]"
---

# Macro Model

---

> **Macroeconomic indicators from the Bureau of Labor Statistics (BLS)**

The Macro model provides comprehensive economic indicators from the BLS, including unemployment rates, CPI (inflation), employment figures, and wage data. These indicators are essential for understanding economic trends and their correlation with financial markets.

**Configuration:** `/home/user/de_Funk/configs/models/macro.yaml`
**Implementation:** `/home/user/de_Funk/models/implemented/macro/`

---

## Table of Contents

---

- [Overview](#overview)
- [Schema Overview](#schema-overview)
- [Data Sources](#data-sources)
- [Detailed Schema](#detailed-schema)
- [Economic Indicators](#economic-indicators)
- [Graph Structure](#graph-structure)
- [Measures](#measures)
- [How-To Guides](#how-to-guides)
- [Usage Examples](#usage-examples)
- [Integration Examples](#integration-examples)
- [Design Decisions](#design-decisions)

---

## Overview

---

### Purpose

The Macro model provides:
- National unemployment rate (monthly)
- Consumer Price Index (CPI) for inflation tracking
- Total nonfarm employment figures
- Average hourly earnings (wage data)
- Wide-format indicator table for easy analysis

### Key Features

- **Official BLS Data** - Authoritative government statistics
- **Monthly Updates** - Regular data refresh from BLS API
- **Multiple Indicators** - 4 key economic metrics
- **Series Metadata** - Full context for each indicator
- **Wide Format View** - All indicators by date
- **Historical Data** - Back to 1990s for most series

### Model Characteristics

| Attribute | Value |
|-----------|-------|
| **Model Name** | `macro` |
| **Tags** | `macro`, `economics`, `bls`, `timeseries` |
| **Dependencies** | [[Core Model]] (calendar dimension) |
| **Data Source** | Bureau of Labor Statistics API |
| **Storage Root** | `storage/silver/macro` |
| **Format** | Parquet |
| **Tables** | 6 (1 dimension, 5 facts) |
| **Dimensions** | 1 (dim_economic_series) |
| **Facts** | 5 (4 indicators + 1 wide view) |
| **Measures** | 4 |
| **Update Frequency** | Monthly (after BLS release) |

---

## Architecture Components Used

---

This model uses the following architecture components:

### Primary Components

| Component | Purpose | Documentation |
|-----------|---------|---------------|
| **[[Data Pipeline/BLS]]** | Ingest economic indicators from Bureau of Labor Statistics API | [[Data Pipeline Overview]] |
| **[[Facets/Economics]]** | Normalize unemployment, CPI, employment, and wage data | [[Facets]] |
| **[[Providers/BLS]]** | BLS API provider implementation | [[Providers]] |
| **[[Bronze Storage]]** | Raw economic data from BLS | [[Bronze Layer]] |
| **[[Silver Storage]]** | Dimensional economic indicators (star schema) | [[Silver Layer]] |
| **[[Models System/Dimensional]]** | Time series dimensional modeling | [[Base Model]] |

### Data Flow

Economic data flows from BLS API through facets for normalization, into Bronze storage, then transformed via the models system into dimensional time series tables in Silver storage.

**Flow:** BLS API → Facets (Economics) → Bronze/bls → BaseModel.build() → Silver/macro

See [[MODEL_ARCHITECTURE_MAPPING]] for complete architecture mapping.

---

## Schema Overview

---

### High-Level Summary

The Macro model implements a **star schema** with economic series dimension connected to indicator facts. All data is sourced from the Bureau of Labor Statistics API and partitioned by year for optimal query performance.

**Quick Reference:**

| Table Type | Count | Purpose |
|------------|-------|---------|
| **Dimensions** | 1 | Economic series metadata |
| **Facts** | 4 | Individual economic indicators |
| **Wide Views** | 1 | All indicators pivoted by date |
| **Measures** | 4 | Pre-defined economic calculations |

### Dimensions (Metadata)

| Dimension | Rows | Primary Key | Purpose |
|-----------|------|-------------|---------|
| **dim_economic_series** | ~4-10 | series_id | BLS series metadata and categorization |

### Facts (Economic Data)

| Fact | Grain | Partitions | Purpose |
|------|-------|------------|---------|
| **fact_unemployment** | Monthly national | year | Unemployment rate (percent) |
| **fact_cpi** | Monthly national | year | Consumer Price Index (inflation) |
| **fact_employment** | Monthly national | year | Total nonfarm employment (thousands) |
| **fact_wages** | Monthly national | year | Average hourly earnings (dollars) |

### Wide Views (Analytics)

| View | Purpose | Grain |
|------|---------|-------|
| **economic_indicators_wide** | All indicators in one table | Monthly (one row per month) |

### Star Schema Diagram

```
                    ┌─────────────────────────┐
                    │  dim_economic_series    │
                    │  ───────────────────────│
                    │  series_id (PK)         │
                    │  series_name            │
                    │  category               │
                    │  frequency              │
                    │  units                  │
                    └────────┬────────────────┘
                             │
                             │ (series_id)
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        │                    │                    │
┌───────▼───────────┐ ┌──────▼──────────┐ ┌──────▼──────────┐
│fact_unemployment  │ │   fact_cpi      │ │fact_employment  │
│                   │ │                 │ │                 │
│  • series_id (FK) │ │  • series_id    │ │  • series_id    │
│  • date           │ │  • date         │ │  • date         │
│  • year (part)    │ │  • year (part)  │ │  • year (part)  │
│  • value (%)      │ │  • value (index)│ │  • value (000s) │
│                   │ │                 │ │                 │
└───────────────────┘ └─────────────────┘ └─────────────────┘
        │
        │ (series_id)
        │
┌───────▼───────────┐
│   fact_wages      │
│                   │
│  • series_id (FK) │
│  • date           │
│  • year (part)    │
│  • value ($)      │
│                   │
└───────────────────┘

Analytics View:
┌─────────────────────────────────────────┐
│    economic_indicators_wide             │
│  ───────────────────────────────────────│
│  • date                                 │
│  • unemployment_rate                    │
│  • cpi_value                            │
│  • total_employment                     │
│  • avg_hourly_earnings                  │
│                                         │
│  All indicators in one row per month    │
└─────────────────────────────────────────┘
```

**Relationships:**
- `fact_unemployment.series_id` → `dim_economic_series.series_id` (many-to-one)
- `fact_cpi.series_id` → `dim_economic_series.series_id` (many-to-one)
- `fact_employment.series_id` → `dim_economic_series.series_id` (many-to-one)
- `fact_wages.series_id` → `dim_economic_series.series_id` (many-to-one)
- All facts can join to [[Core Model]].dim_calendar on date

---

## Data Sources

---

### Bureau of Labor Statistics API

**Provider:** Bureau of Labor Statistics (https://www.bls.gov)
**API Endpoint:** `https://api.bls.gov/publicAPI/v2/timeseries/data/`
**Authentication:** API key (optional, recommended for higher rate limits)

### API Access Tiers

| Tier | Requests/Day | Years/Request | Best For |
|------|--------------|---------------|----------|
| **Free** | 25 | 10 | Development, testing |
| **Registered** | 500 | 20 | Production use |

### BLS Series IDs

#### Unemployment Rate
```yaml
unemployment:
  series_id: "LNS14000000"
  name: "Unemployment Rate - Civilian Labor Force"
  category: "unemployment"
  frequency: "monthly"
  units: "percent"
  seasonal_adjustment: "seasonally_adjusted"
```

**Description:**
- Percent of civilian labor force that is unemployed
- Seasonally adjusted
- Based on Current Population Survey (CPS)

#### Consumer Price Index (CPI)
```yaml
cpi:
  series_id: "CUUR0000SA0"
  name: "Consumer Price Index - All Urban Consumers"
  category: "inflation"
  frequency: "monthly"
  units: "index"
  base_period: "1982-84 = 100"
```

**Description:**
- All items, U.S. city average
- Base period: 1982-84 = 100
- Measures inflation in consumer goods and services

#### Total Nonfarm Employment
```yaml
employment:
  series_id: "CES0000000001"
  name: "Total Nonfarm Employment"
  category: "employment"
  frequency: "monthly"
  units: "thousands"
  seasonal_adjustment: "seasonally_adjusted"
```

**Description:**
- Total employed in nonfarm payroll jobs
- Seasonally adjusted
- In thousands of jobs
- From Current Employment Statistics (CES)

#### Average Hourly Earnings
```yaml
wages:
  series_id: "CES0500000003"
  name: "Average Hourly Earnings - Total Private"
  category: "wages"
  frequency: "monthly"
  units: "dollars"
  seasonal_adjustment: "seasonally_adjusted"
```

**Description:**
- Average hourly earnings for all private employees
- Seasonally adjusted
- In current dollars (not inflation-adjusted)

### Bronze → Silver Transformation

**Pipeline:** `datapipelines/providers/bls/`

```
BLS API
    ↓
Facets (normalize responses)
    ├─→ UnemploymentFacet
    ├─→ CPIFacet
    ├─→ EmploymentFacet
    └─→ WagesFacet
    ↓
Bronze Storage (partitioned Parquet)
    ├─→ bronze/bls_unemployment/ (partitioned by year)
    ├─→ bronze/bls_cpi/ (partitioned by year)
    ├─→ bronze/bls_employment/ (partitioned by year)
    └─→ bronze/bls_wages/ (partitioned by year)
    ↓
BaseModel.build() (YAML-driven graph transformation)
    ↓
Silver Storage (dimensional model)
    ├─→ silver/macro/dims/dim_economic_series/
    ├─→ silver/macro/facts/fact_unemployment/
    ├─→ silver/macro/facts/fact_cpi/
    ├─→ silver/macro/facts/fact_employment/
    ├─→ silver/macro/facts/fact_wages/
    └─→ silver/macro/facts/economic_indicators_wide/
```

### Update Schedule

**BLS Release Calendar:**
- **Employment Situation Report** - First Friday of month (8:30 AM ET)
  - Unemployment rate
  - Nonfarm employment
  - Average hourly earnings

- **CPI Report** - Mid-month, typically 8:30 AM ET
  - Consumer Price Index

**Data Pipeline:**
1. BLS publishes data (scheduled releases)
2. API fetch within 24 hours
3. Bronze layer update
4. Silver layer rebuild
5. Available for queries

### Data Quality

- **Completeness:** All months covered (no gaps)
- **Accuracy:** Official government statistics
- **Timeliness:** Updated monthly after BLS release
- **Consistency:** Schema validated via facets
- **Revisions:** BLS may revise prior months (we capture latest)

---

## Detailed Schema

---

### Dimensions

#### dim_economic_series

Economic indicator series metadata from BLS.

**Path:** `storage/silver/macro/dims/dim_economic_series`
**Primary Key:** `series_id`
**Grain:** One row per BLS series

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **series_id** | string | BLS series identifier (PK) | LNS14000000 |
| **series_name** | string | Full series name | Unemployment Rate - Civilian Labor Force |
| **category** | string | Indicator category | unemployment, inflation, employment, wages |
| **frequency** | string | Data frequency | monthly, quarterly, annual |
| **units** | string | Measurement units | percent, index, thousands, dollars |
| **seasonal_adjustment** | string | Seasonal adjustment status | seasonally_adjusted, not_adjusted |

**Sample Data:**
```
+---------------+---------------------------------------+-------------+-----------+----------+---------------------+
| series_id     | series_name                           | category    | frequency | units    | seasonal_adjustment |
+---------------+---------------------------------------+-------------+-----------+----------+---------------------+
| LNS14000000   | Unemployment Rate - Civilian Labor... | unemployment| monthly   | percent  | seasonally_adjusted |
| CUUR0000SA0   | Consumer Price Index - All Urban...  | inflation   | monthly   | index    | seasonally_adjusted |
| CES0000000001 | Total Nonfarm Employment              | employment  | monthly   | thousands| seasonally_adjusted |
| CES0500000003 | Average Hourly Earnings - Total...   | wages       | monthly   | dollars  | seasonally_adjusted |
+---------------+---------------------------------------+-------------+-----------+----------+---------------------+
```

### Facts

#### fact_unemployment

National unemployment rate (monthly).

**Path:** `storage/silver/macro/facts/fact_unemployment`
**Partitions:** `year`
**Grain:** One row per month

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **series_id** | string | BLS series ID (LNS14000000) | LNS14000000 |
| **date** | date | First day of month | 2024-11-01 |
| **year** | integer | Year (partition key) | 2024 |
| **period** | string | BLS period code (M01-M12) | M11 |
| **value** | double | Unemployment rate (percent) | 3.9 |
| **period_name** | string | Month name | November |

**Sample Data:**
```
+---------------+------------+------+--------+-------+-------------+
| series_id     | date       | year | period | value | period_name |
+---------------+------------+------+--------+-------+-------------+
| LNS14000000   | 2024-01-01 | 2024 | M01    |  3.7  | January     |
| LNS14000000   | 2024-02-01 | 2024 | M02    |  3.9  | February    |
| LNS14000000   | 2024-03-01 | 2024 | M03    |  3.8  | March       |
| LNS14000000   | 2024-10-01 | 2024 | M10    |  4.1  | October     |
| LNS14000000   | 2024-11-01 | 2024 | M11    |  3.9  | November    |
+---------------+------------+------+--------+-------+-------------+
```

#### fact_cpi

Consumer Price Index (monthly inflation indicator).

**Path:** `storage/silver/macro/facts/fact_cpi`
**Partitions:** `year`
**Grain:** One row per month

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **series_id** | string | BLS series ID (CUUR0000SA0) | CUUR0000SA0 |
| **date** | date | First day of month | 2024-11-01 |
| **year** | integer | Year (partition key) | 2024 |
| **period** | string | BLS period code | M11 |
| **value** | double | CPI index value (1982-84 = 100) | 314.540 |
| **period_name** | string | Month name | November |

**Sample Data:**
```
+---------------+------------+------+--------+---------+-------------+
| series_id     | date       | year | period | value   | period_name |
+---------------+------------+------+--------+---------+-------------+
| CUUR0000SA0   | 2024-01-01 | 2024 | M01    | 308.417 | January     |
| CUUR0000SA0   | 2024-02-01 | 2024 | M02    | 310.326 | February    |
| CUUR0000SA0   | 2024-03-01 | 2024 | M03    | 312.230 | March       |
| CUUR0000SA0   | 2024-10-01 | 2024 | M10    | 314.069 | October     |
| CUUR0000SA0   | 2024-11-01 | 2024 | M11    | 314.540 | November    |
+---------------+------------+------+--------+---------+-------------+
```

**CPI Calculation Example:**
```python
# Year-over-year inflation rate
inflation_rate = ((CPI_Nov2024 - CPI_Nov2023) / CPI_Nov2023) * 100
# = ((314.540 - 307.051) / 307.051) * 100
# = 2.44%
```

#### fact_employment

Total nonfarm employment (monthly).

**Path:** `storage/silver/macro/facts/fact_employment`
**Partitions:** `year`
**Grain:** One row per month

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **series_id** | string | BLS series ID (CES0000000001) | CES0000000001 |
| **date** | date | First day of month | 2024-11-01 |
| **year** | integer | Year (partition key) | 2024 |
| **period** | string | BLS period code | M11 |
| **value** | double | Employment (thousands) | 158935.0 |
| **period_name** | string | Month name | November |

**Sample Data:**
```
+---------------+------------+------+--------+----------+-------------+
| series_id     | date       | year | period | value    | period_name |
+---------------+------------+------+--------+----------+-------------+
| CES0000000001 | 2024-01-01 | 2024 | M01    | 157485.0 | January     |
| CES0000000001 | 2024-02-01 | 2024 | M02    | 157750.0 | February    |
| CES0000000001 | 2024-03-01 | 2024 | M03    | 158012.0 | March       |
| CES0000000001 | 2024-10-01 | 2024 | M10    | 158721.0 | October     |
| CES0000000001 | 2024-11-01 | 2024 | M11    | 158935.0 | November    |
+---------------+------------+------+--------+----------+-------------+
```

**Units:** Thousands of jobs (158,935,000 total employment)

#### fact_wages

Average hourly earnings for all private employees (monthly).

**Path:** `storage/silver/macro/facts/fact_wages`
**Partitions:** `year`
**Grain:** One row per month

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **series_id** | string | BLS series ID (CES0500000003) | CES0500000003 |
| **date** | date | First day of month | 2024-11-01 |
| **year** | integer | Year (partition key) | 2024 |
| **period** | string | BLS period code | M11 |
| **value** | double | Average hourly earnings (USD) | 34.92 |
| **period_name** | string | Month name | November |

**Sample Data:**
```
+---------------+------------+------+--------+-------+-------------+
| series_id     | date       | year | period | value | period_name |
+---------------+------------+------+--------+-------+-------------+
| CES0500000003 | 2024-01-01 | 2024 | M01    | 34.31 | January     |
| CES0500000003 | 2024-02-01 | 2024 | M02    | 34.45 | February    |
| CES0500000003 | 2024-03-01 | 2024 | M03    | 34.58 | March       |
| CES0500000003 | 2024-10-01 | 2024 | M10    | 34.78 | October     |
| CES0500000003 | 2024-11-01 | 2024 | M11    | 34.92 | November    |
+---------------+------------+------+--------+-------+-------------+
```

**Calculation:**
```python
# Annual wage growth
wage_growth = ((Wage_Nov2024 - Wage_Nov2023) / Wage_Nov2023) * 100
# = ((34.92 - 33.89) / 33.89) * 100
# = 3.04%
```

#### economic_indicators_wide

All indicators pivoted wide by date (analytics-ready format).

**Path:** `storage/silver/macro/facts/economic_indicators_wide`
**Partitions:** `date`
**Grain:** One row per month

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **date** | date | First day of month (partition key) | 2024-11-01 |
| **unemployment_rate** | double | Unemployment rate (%) | 3.9 |
| **cpi_value** | double | Consumer Price Index | 314.540 |
| **total_employment** | double | Total employment (thousands) | 158935.0 |
| **avg_hourly_earnings** | double | Average hourly wage ($) | 34.92 |

**Sample Data:**
```
+------------+-------------------+-----------+------------------+---------------------+
| date       | unemployment_rate | cpi_value | total_employment | avg_hourly_earnings |
+------------+-------------------+-----------+------------------+---------------------+
| 2024-01-01 |       3.7         |  308.417  |    157485.0      |       34.31         |
| 2024-02-01 |       3.9         |  310.326  |    157750.0      |       34.45         |
| 2024-03-01 |       3.8         |  312.230  |    158012.0      |       34.58         |
| 2024-10-01 |       4.1         |  314.069  |    158721.0      |       34.78         |
| 2024-11-01 |       3.9         |  314.540  |    158935.0      |       34.92         |
+------------+-------------------+-----------+------------------+---------------------+
```

**Benefits:**
- All indicators in one row per month
- Easy correlation analysis
- Ready for visualization
- No joins needed

---

## Economic Indicators

---

### Unemployment Rate

**What it measures:** Percent of labor force actively seeking work

**Formula:**
```
Unemployment Rate = (Unemployed / Labor Force) × 100
where Labor Force = Employed + Unemployed
```

**Interpretation:**
- **< 4%** - Very low (tight labor market)
- **4-5%** - Normal/healthy
- **5-7%** - Elevated
- **> 7%** - High (recession indicator)

**Historical Context:**
- Great Recession (2009): 10.0%
- COVID-19 Peak (2020): 14.7%
- Historic Low (1953): 2.5%
- Pre-pandemic (2019): 3.5-3.7%

### Consumer Price Index (CPI)

**What it measures:** Average change in prices paid by urban consumers

**Calculation:**
```python
# Year-over-year inflation
inflation_rate = ((CPI_current - CPI_year_ago) / CPI_year_ago) × 100

# Month-over-month change
monthly_change = ((CPI_current - CPI_prev_month) / CPI_prev_month) × 100 × 12  # Annualized
```

**Interpretation:**
- **0-2%** - Low/stable (Fed target: ~2%)
- **2-3%** - Moderate
- **3-5%** - Elevated
- **> 5%** - High inflation

**Historical Context:**
- 1970s-1980s: 5-14% (high inflation)
- 2010-2020: 1-2% (stable)
- 2021-2022: 5-9% (post-COVID spike)
- 2024: ~2-3% (normalizing)

### Total Nonfarm Employment

**What it measures:** Number of paid jobs (in thousands)

**Interpretation:**
- **Monthly Growth:**
  - **> 200k** - Strong job growth
  - **100-200k** - Moderate growth
  - **< 100k** - Weak growth
  - **Negative** - Job losses (recession indicator)

**Historical Context:**
- Pre-pandemic (Feb 2020): 152,463k jobs
- Pandemic Low (Apr 2020): 130,190k jobs (lost 22M jobs)
- Recovery (2024): 158,935k jobs (above pre-pandemic)

### Average Hourly Earnings

**What it measures:** Average hourly pay for private employees

**Interpretation:**
- **Year-over-year growth:**
  - **< 2%** - Low wage growth (below inflation)
  - **2-3%** - Normal (matches inflation)
  - **3-5%** - Strong wage growth
  - **> 5%** - Very strong (potential inflation driver)

**Real Wages:**
```python
# Adjust for inflation
real_wage_growth = wage_growth - inflation_rate
```

**Historical Context:**
- 2010-2019: 2-3% annual growth
- 2021-2022: 4-6% growth (but inflation higher)
- 2024: 3-4% growth (real gains as inflation moderates)

---

## Graph Structure

---

### Nodes, Edges, Paths

**Nodes:**
- `dim_economic_series`
- `fact_unemployment`
- `fact_cpi`
- `fact_employment`
- `fact_wages`

**Edges:**
- `fact_unemployment → dim_economic_series` (series_id)
- `fact_cpi → dim_economic_series` (series_id)
- `fact_employment → dim_economic_series` (series_id)
- `fact_wages → dim_economic_series` (series_id)

**Paths:**
- None (simple star schema)

---

## Measures

---

### Simple Aggregations

| Measure | Source | Aggregation | Format | Purpose |
|---------|--------|-------------|--------|---------|
| **avg_unemployment_rate** | fact_unemployment.value | avg | #,##0.00% | Average unemployment rate over period |
| **latest_cpi** | fact_cpi.value | max | #,##0.00 | Latest CPI value (most recent month) |
| **employment_growth** | fact_employment.value | sum | #,##0 | Total employment growth |
| **wage_trend** | fact_wages.value | avg | $#,##0.00 | Average wage trend over period |

**Example YAML Definition:**
```yaml
measures:
  avg_unemployment_rate:
    description: "Average unemployment rate"
    source: fact_unemployment.value
    aggregation: avg
    data_type: double
    format: "#,##0.00%"
    tags: [unemployment, average]

  latest_cpi:
    description: "Latest CPI value"
    source: fact_cpi.value
    aggregation: max
    data_type: double
    format: "#,##0.00"
    tags: [cpi, latest]

  employment_growth:
    description: "Total employment growth"
    source: fact_employment.value
    aggregation: sum
    data_type: double
    format: "#,##0"
    tags: [employment, growth]

  wage_trend:
    description: "Average wage trend"
    source: fact_wages.value
    aggregation: avg
    data_type: double
    format: "$#,##0.00"
    tags: [wages, average]
```

---

## How-To Guides

---

### How to Query Economic Indicators

**Step 1:** Load the macro model

```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load macro model
macro = session.load_model('macro')
```

**Step 2:** Get unemployment data

```python
# Get all unemployment data
unemployment = macro.get_fact_df('fact_unemployment')

# Filter for 2024
unemployment_2024 = unemployment.filter(F.col('year') == 2024).orderBy('date')

unemployment_2024.select('date', 'value', 'period_name').show()

# +------------+-------+-------------+
# | date       | value | period_name |
# +------------+-------+-------------+
# | 2024-01-01 |  3.7  | January     |
# | 2024-02-01 |  3.9  | February    |
# | 2024-03-01 |  3.8  | March       |
# | ...
# +------------+-------+-------------+
```

**Step 3:** Get all indicators in wide format

```python
# Get wide format table
indicators = macro.get_fact_df('economic_indicators_wide')

# Get latest month
latest = indicators.orderBy(F.desc('date')).limit(1)
latest.show()

# +------------+-------------------+-----------+------------------+---------------------+
# | date       | unemployment_rate | cpi_value | total_employment | avg_hourly_earnings |
# +------------+-------------------+-----------+------------------+---------------------+
# | 2024-11-01 |       3.9         |  314.540  |    158935.0      |       34.92         |
# +------------+-------------------+-----------+------------------+---------------------+
```

---

### How to Calculate Inflation

**Step 1:** Get CPI data

```python
from pyspark.sql import Window
import pyspark.sql.functions as F

# Get CPI data
cpi = macro.get_fact_df('fact_cpi')

# Filter for recent years
cpi_recent = cpi.filter(F.col('year') >= 2020).orderBy('date')
```

**Step 2:** Calculate year-over-year inflation

```python
# Calculate year-over-year inflation
window_spec = Window.orderBy('date')

inflation = cpi_recent.withColumn(
    'cpi_year_ago',
    F.lag('value', 12).over(window_spec)
).withColumn(
    'inflation_rate',
    ((F.col('value') - F.col('cpi_year_ago')) / F.col('cpi_year_ago')) * 100
)

# Show recent inflation rates
inflation.filter(F.col('year') == 2024).select(
    'date', 'period_name', 'value', 'cpi_year_ago', 'inflation_rate'
).show()

# +------------+-------------+---------+-------------+---------------+
# | date       | period_name | value   | cpi_year_ago| inflation_rate|
# +------------+-------------+---------+-------------+---------------+
# | 2024-01-01 | January     | 308.417 |   302.480   |     1.96%     |
# | 2024-02-01 | February    | 310.326 |   304.702   |     1.85%     |
# | 2024-03-01 | March       | 312.230 |   305.361   |     2.25%     |
# | ...
# +------------+-------------+---------+-------------+---------------+
```

**Step 3:** Calculate month-over-month change (annualized)

```python
# Calculate month-over-month inflation (annualized)
mom_inflation = cpi_recent.withColumn(
    'cpi_prev_month',
    F.lag('value', 1).over(window_spec)
).withColumn(
    'monthly_change',
    ((F.col('value') - F.col('cpi_prev_month')) / F.col('cpi_prev_month')) * 100
).withColumn(
    'annualized_monthly',
    F.col('monthly_change') * 12  # Annualize
)

mom_inflation.filter(F.col('year') == 2024).select(
    'date', 'monthly_change', 'annualized_monthly'
).show()
```

**Step 4:** Visualize inflation trends

```python
import pandas as pd
import matplotlib.pyplot as plt

# Convert to pandas
inflation_df = inflation.filter(F.col('inflation_rate').isNotNull()).toPandas()

# Plot
plt.figure(figsize=(12, 6))
plt.plot(inflation_df['date'], inflation_df['inflation_rate'], marker='o')
plt.axhline(y=2.0, color='r', linestyle='--', label='Fed Target (2%)')
plt.xlabel('Date')
plt.ylabel('Year-over-Year Inflation (%)')
plt.title('US Inflation Rate (CPI)')
plt.legend()
plt.grid(True, alpha=0.3)
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

---

### How to Join with Company Data

**Step 1:** Load both models

```python
# Load models
company = session.load_model('company')
macro = session.load_model('macro')

# Get stock prices
prices = company.get_fact_df('fact_prices')

# Get unemployment rate
unemployment = macro.get_fact_df('fact_unemployment')
```

**Step 2:** Aggregate prices to monthly

```python
# Aggregate prices to monthly
monthly_prices = prices.groupBy(
    F.date_trunc('month', 'trade_date').alias('month'),
    'ticker'
).agg(
    F.avg('close').alias('avg_close')
)
```

**Step 3:** Join with unemployment

```python
# Join with unemployment
prices_with_unemp = monthly_prices.join(
    unemployment.select(
        F.col('date').alias('month'),
        F.col('value').alias('unemployment_rate')
    ),
    on='month',
    how='left'
)

# Analyze correlation
aapl_unemp = prices_with_unemp.filter(F.col('ticker') == 'AAPL')
correlation = aapl_unemp.select(
    F.corr('avg_close', 'unemployment_rate').alias('correlation')
).first()['correlation']

print(f"AAPL price vs unemployment correlation: {correlation:.3f}")
```

**Step 4:** Visualize relationship

```python
import plotly.express as px

# Convert to pandas
aapl_df = aapl_unemp.to_pandas()

# Create scatter plot
fig = px.scatter(
    aapl_df,
    x='unemployment_rate',
    y='avg_close',
    trendline='ols',
    title='AAPL Stock Price vs Unemployment Rate',
    labels={
        'unemployment_rate': 'Unemployment Rate (%)',
        'avg_close': 'Average Stock Price ($)'
    }
)
fig.show()
```

---

## Usage Examples

---

### 1. Load Macro Model

```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize session
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load macro model
macro_model = session.load_model('macro')
```

### 2. Get Unemployment Rate

```python
# Get all unemployment data
unemployment = macro_model.get_fact_df('fact_unemployment')

# Filter for 2024
unemployment_2024 = unemployment.filter(F.col('year') == 2024).orderBy('date')

unemployment_2024.select('date', 'value', 'period_name').show()
```

### 3. Calculate Year-over-Year Inflation

```python
from pyspark.sql import Window

# Get CPI data
cpi = macro_model.get_fact_df('fact_cpi')

# Calculate year-over-year inflation
window_spec = Window.orderBy('date')

inflation = cpi.withColumn(
    'cpi_year_ago',
    F.lag('value', 12).over(window_spec)
).withColumn(
    'inflation_rate',
    ((F.col('value') - F.col('cpi_year_ago')) / F.col('cpi_year_ago')) * 100
)

# Show recent inflation rates
inflation.filter(F.col('year') == 2024).select(
    'date', 'value', 'cpi_year_ago', 'inflation_rate'
).show()
```

### 4. Analyze Employment Growth

```python
from pyspark.sql import Window

# Get employment data
employment = macro_model.get_fact_df('fact_employment')

# Calculate month-over-month change
window_spec = Window.orderBy('date')

employment_growth = employment.withColumn(
    'prev_month',
    F.lag('value').over(window_spec)
).withColumn(
    'jobs_added',
    F.col('value') - F.col('prev_month')
)

# Show monthly job growth
employment_growth.filter(F.col('year') == 2024).select(
    'date', 'period_name', 'value', 'jobs_added'
).show()
```

### 5. Calculate Real Wage Growth

```python
# Get wages and CPI
wages = macro_model.get_fact_df('fact_wages')
cpi = macro_model.get_fact_df('fact_cpi')

# Join on date
wages_with_cpi = wages.join(
    cpi.select('date', F.col('value').alias('cpi')),
    on='date',
    how='left'
)

# Calculate year-over-year changes
window_spec = Window.orderBy('date')

real_wages = wages_with_cpi.withColumn(
    'wage_year_ago',
    F.lag('value', 12).over(window_spec)
).withColumn(
    'cpi_year_ago',
    F.lag('cpi', 12).over(window_spec)
).withColumn(
    'nominal_wage_growth',
    ((F.col('value') - F.col('wage_year_ago')) / F.col('wage_year_ago')) * 100
).withColumn(
    'inflation_rate',
    ((F.col('cpi') - F.col('cpi_year_ago')) / F.col('cpi_year_ago')) * 100
).withColumn(
    'real_wage_growth',
    F.col('nominal_wage_growth') - F.col('inflation_rate')
)

# Show real wage growth
real_wages.filter(F.col('year') == 2024).select(
    'date', 'value', 'nominal_wage_growth', 'inflation_rate', 'real_wage_growth'
).show()
```

### 6. Use Wide Format Table

```python
# Get all indicators in wide format
indicators = macro_model.get_fact_df('economic_indicators_wide')

# Get latest month
latest = indicators.orderBy(F.desc('date')).limit(1)
latest.show()

# Easy to analyze correlations
correlation = indicators.select(
    F.corr('unemployment_rate', 'cpi_value').alias('unemp_cpi_corr'),
    F.corr('unemployment_rate', 'avg_hourly_earnings').alias('unemp_wage_corr')
)
correlation.show()
```

### 7. Visualize Economic Dashboard

```python
import pandas as pd
import matplotlib.pyplot as plt

# Get wide format as pandas
indicators_pd = indicators.filter(
    F.col('date') >= '2020-01-01'
).toPandas()

# Create dashboard
fig, axes = plt.subplots(2, 2, figsize=(15, 10))

# Unemployment rate
axes[0, 0].plot(indicators_pd['date'], indicators_pd['unemployment_rate'])
axes[0, 0].set_title('Unemployment Rate (%)')
axes[0, 0].set_ylabel('Percent')

# CPI (inflation)
axes[0, 1].plot(indicators_pd['date'], indicators_pd['cpi_value'])
axes[0, 1].set_title('Consumer Price Index')
axes[0, 1].set_ylabel('Index (1982-84=100)')

# Total employment
axes[1, 0].plot(indicators_pd['date'], indicators_pd['total_employment'])
axes[1, 0].set_title('Total Nonfarm Employment')
axes[1, 0].set_ylabel('Thousands')

# Average hourly earnings
axes[1, 1].plot(indicators_pd['date'], indicators_pd['avg_hourly_earnings'])
axes[1, 1].set_title('Average Hourly Earnings')
axes[1, 1].set_ylabel('Dollars')

plt.tight_layout()
plt.show()
```

---

## Integration Examples

---

### Company + Macro: Stocks vs Unemployment

```python
# Load models
company_model = session.load_model('company')
macro_model = session.load_model('macro')

# Get prices and unemployment
prices = company_model.get_fact_df('fact_prices')
unemployment = macro_model.get_fact_df('fact_unemployment')

# Aggregate prices to monthly
monthly_prices = prices.groupBy(
    F.date_trunc('month', 'trade_date').alias('month'),
    'ticker'
).agg(
    F.avg('close').alias('avg_close')
)

# Join with unemployment
prices_with_unemp = monthly_prices.join(
    unemployment.select(
        F.col('date').alias('month'),
        F.col('value').alias('unemployment_rate')
    ),
    on='month',
    how='left'
)

# Analyze correlation
aapl_unemp = prices_with_unemp.filter(F.col('ticker') == 'AAPL')
correlation = aapl_unemp.select(
    F.corr('avg_close', 'unemployment_rate').alias('correlation')
).first()['correlation']

print(f"AAPL price vs unemployment correlation: {correlation:.3f}")
```

See [[Company Model]] for stock market data.

---

## Design Decisions

---

### 1. Partition by Year

**Decision:** Partition all fact tables by `year`

**Rationale:**
- Monthly data, but queries often span years
- Fewer partitions than monthly (12× fewer)
- BLS reports historical data by year

### 2. Wide Format View

**Decision:** Create `economic_indicators_wide` materialized view

**Rationale:**
- Analysts often need all indicators together
- Easier correlation analysis
- No joins needed for dashboards

### 3. Include Period Codes

**Decision:** Keep BLS `period` codes (M01-M12)

**Rationale:**
- Matches BLS API format
- Useful for debugging data issues
- Supports quarterly data (Q01-Q04) if added later

### 4. Separate Tables per Indicator

**Decision:** Don't combine all indicators in one table

**Rationale:**
- Different series have different update schedules
- Cleaner schema (no sparse columns)
- Easier to add new indicators

### 5. Monthly Grain Only

**Decision:** Don't include weekly or daily data

**Rationale:**
- BLS publishes monthly data
- Sufficient for most macro analysis
- Reduces complexity

---

## Related Documentation

---

### Model Documentation
- [[Core Model]] - Shared calendar dimension
- [[City Finance Model]] - Local economic data (Chicago)
- [[Company Model]] - Market correlation analysis
- [[Forecast Model]] - Economic indicators as ML features

### Architecture Documentation
- [[MODEL_ARCHITECTURE_MAPPING]] - Complete architecture mapping
- [[Data Pipeline]] - BLS API ingestion pipeline
- [[Facets]] - Economic indicator normalization
- [[Providers]] - BLS provider implementation
- [[Bronze Storage]] - Raw BLS data storage
- [[Silver Storage]] - Dimensional time series storage
- [[Universal Session]] - Cross-model query examples

---

**Tags:** #economics/bls #component/model #source/bls #status/stable #component/data-pipeline/bls #component/facets/economics #component/providers/bls #component/storage/bronze #component/storage/silver #component/models-system/dimensional #architecture/ingestion-to-analytics #pattern/star-schema #pattern/time-series

**Last Updated:** 2024-11-08
**Model Version:** 1.0
**Dependencies:** [[Core Model]]
**Used By:** [[Company Model]]
