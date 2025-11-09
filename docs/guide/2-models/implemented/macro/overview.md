---
title: "Macro Model Overview"
tags: [economics/bls, component/model, source/bls, status/stable]
aliases: ["Macro Model", "Economic Indicators", "BLS Model"]
dependencies: ["[[Calendar]]"]
architecture_components:
  - "[[Data Pipeline/BLS]]"
  - "[[Facets/Economics]]"
  - "[[Bronze Storage]]"
  - "[[Silver Storage]]"
---

# Macro Model - Overview

---

The Macro Model provides national macroeconomic indicators from the Bureau of Labor Statistics (BLS), enabling economic trend analysis and correlation with financial markets.

**Data Source:** Bureau of Labor Statistics (BLS) API
**Dependencies:** [[Calendar]]
**Storage:** `storage/silver/macro`

---

## Model Components

---

### Dimensions
- **[[Economic Series Dimension]]** - Economic indicator series metadata

### Facts
- **[[Unemployment Facts]]** - National unemployment rate (monthly)
- **[[CPI Facts]]** - Consumer Price Index (monthly)
- **[[Employment Facts]]** - Total nonfarm employment (monthly)
- **[[Wages Facts]]** - Average hourly earnings (monthly)

### Materialized Analytics
- **economic_indicators_wide** - All indicators pivoted by date

---

## Quick Stats

| Metric | Value |
|--------|-------|
| **Time Range** | 1948-present (varies by series) |
| **Update Frequency** | Monthly |
| **Geographic Coverage** | United States (national level) |
| **Fact Tables** | 5 (4 base + 1 materialized) |
| **Dimension Tables** | 1 |
| **Economic Series** | 4 primary indicators |

---

## Star Schema

---

```
dim_calendar (from Core)
     ↓
fact_unemployment ───→ dim_economic_series
     ↓
fact_cpi ──────────→ dim_economic_series
     ↓
fact_employment ───→ dim_economic_series
     ↓
fact_wages ────────→ dim_economic_series
```

**Grain:**
- **All fact tables:** One row per series per month

---

## Key Features

---

### 1. Comprehensive Economic Indicators
- **Unemployment Rate** - Labor market health
- **CPI** - Inflation measurement
- **Employment** - Job growth trends
- **Wages** - Income trends

### 2. Historical Depth
- Data back to 1940s for most series
- Consistent methodologies
- Seasonally adjusted

### 3. Monthly Updates
- First Friday of each month
- Official government statistics
- High reliability

### 4. Wide Format Analytics
- Pre-joined indicator table
- Easy time series comparison
- Optimized for charting

---

## BLS Series Tracked

---

| Series ID | Name | Category | Start Date |
|-----------|------|----------|------------|
| **LNS14000000** | Unemployment Rate - Civilian Labor Force | Unemployment | 1948-01 |
| **CUUR0000SA0** | Consumer Price Index - All Urban Consumers | Inflation | 1947-01 |
| **CES0000000001** | Total Nonfarm Employment | Employment | 1939-01 |
| **CES0500000003** | Average Hourly Earnings - Total Private | Wages | 2006-01 |

---

## Data Sources

---

**Provider:** Bureau of Labor Statistics (BLS)
**API Documentation:** https://www.bls.gov/developers/
**API Version:** v2
**Bronze Tables:** `bronze.bls_unemployment`, `bronze.bls_cpi`, `bronze.bls_employment`, `bronze.bls_wages`

**Update Schedule:**
- **Frequency:** Monthly (first Friday)
- **Revision:** Subject to revision for 2-3 months
- **Availability:** ~8:30 AM ET on release day

See **[[BLS Integration]]** for detailed API documentation.

---

## Usage Example

---

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get macro model
macro = session.load_model('macro')

# Get all indicators in wide format
indicators = macro.get_fact_df('economic_indicators_wide').to_pandas()

# Filter to recent data
recent = indicators[indicators['date'] >= '2020-01-01']

# Plot trends
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

recent.plot(x='date', y='unemployment_rate', ax=axes[0, 0], title='Unemployment Rate (%)')
recent.plot(x='date', y='cpi_value', ax=axes[0, 1], title='CPI (Index)')
recent.plot(x='date', y='total_employment', ax=axes[1, 0], title='Total Employment (thousands)')
recent.plot(x='date', y='avg_hourly_earnings', ax=axes[1, 1], title='Avg Hourly Earnings ($)')

plt.tight_layout()
plt.show()
```

---

## Related Documentation

---

### Model Documentation
- [[Economic Series Dimension]] - Series metadata
- [[Unemployment Facts]] - Unemployment data
- [[CPI Facts]] - Inflation data
- [[Employment Facts]] - Employment data
- [[Wages Facts]] - Wage data

### Architecture Documentation
- [[Data Pipeline/BLS]] - API ingestion
- [[Facets/Economics]] - Economic data normalization
- [[Bronze Storage]] - Raw data storage
- [[Silver Storage]] - Dimensional storage

### How-To Guides
- [[How to Analyze Economic Trends]]
- [[How to Correlate Macro with Markets]]

### Related Models
- [[City Finance Model]] - Municipal economic data
- [[Company Model]] - Correlate with stock prices

---

**Tags:** #economics/bls #component/model #source/bls #architecture/ingestion-to-analytics

**Last Updated:** 2024-11-08
**Model:** macro
**Version:** 1
