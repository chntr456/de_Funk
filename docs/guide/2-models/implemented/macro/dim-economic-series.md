---
title: "Economic Series Dimension"
tags: [economics/bls, component/model, concept/dimensional-modeling, concept/reference]
aliases: ["Economic Series", "dim_economic_series", "BLS Series"]
---

# Economic Series Dimension

---

The Economic Series dimension provides metadata for BLS economic indicator series, including series names, categories, frequency, and units.

**Table:** `dim_economic_series`
**Primary Key:** `series_id`
**Storage:** `storage/silver/macro/dims/dim_economic_series`

---

## Purpose

---

Economic series metadata enables filtering and grouping economic indicators by category, frequency, and seasonal adjustment.

**Use Cases:**
- Filter indicators by category
- Understand seasonal adjustment
- Identify indicator frequency
- Track units of measurement

---

## Schema

---

**Grain:** One row per BLS series

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **series_id** | string | BLS series identifier | "LNS14000000" |
| **series_name** | string | Series full name | "Unemployment Rate - Civilian Labor Force" |
| **category** | string | Indicator category | "unemployment" |
| **frequency** | string | Data frequency | "monthly" |
| **units** | string | Unit of measurement | "percent" |
| **seasonal_adjustment** | string | Seasonal adjustment status | "seasonally_adjusted" |

---

## Sample Data

---

```
+--------------+---------------------------------------+--------------+-----------+---------+----------------------+
| series_id    | series_name                           | category     | frequency | units   | seasonal_adjustment  |
+--------------+---------------------------------------+--------------+-----------+---------+----------------------+
| LNS14000000  | Unemployment Rate - Civilian Labor... | unemployment | monthly   | percent | seasonally_adjusted  |
| CUUR0000SA0  | Consumer Price Index - All Urban C... | inflation    | monthly   | index   | seasonally_adjusted  |
| CES0000000001| Total Nonfarm Employment              | employment   | monthly   | thousands | seasonally_adjusted|
| CES0500000003| Average Hourly Earnings - Total Pr... | wages        | monthly   | dollars | seasonally_adjusted  |
+--------------+---------------------------------------+--------------+-----------+---------+----------------------+
```

---

## Data Source

---

**Provider:** Bureau of Labor Statistics
**Source:** Derived from BLS series configuration
**Update Frequency:** Rarely changes (series metadata is stable)

**Derivation:**
```yaml
from: bronze.bls_unemployment  # Or any BLS source
select:
  series_id: series_id
derive:
  series_name: "Unemployment Rate - Civilian Labor Force"
  category: "unemployment"
  frequency: "monthly"
  units: "percent"
  seasonal_adjustment: "seasonally_adjusted"
```

---

## BLS Series IDs

---

### Unemployment Series

**Series ID:** `LNS14000000`
**Name:** Unemployment Rate - (Seas) Civilian Labor Force 16 years and over
**Category:** Labor Force Statistics from the Current Population Survey
**Seasonality:** Seasonally Adjusted
**Units:** Percent

---

### CPI Series

**Series ID:** `CUUR0000SA0`
**Name:** Consumer Price Index for All Urban Consumers (CPI-U): U.S. city average
**Category:** Consumer Price Index
**Seasonality:** Seasonally Adjusted
**Units:** Index (1982-84=100)

---

### Employment Series

**Series ID:** `CES0000000001`
**Name:** Total Nonfarm Employment
**Category:** Current Employment Statistics
**Seasonality:** Seasonally Adjusted
**Units:** Thousands of jobs

---

### Wages Series

**Series ID:** `CES0500000003`
**Name:** Average Hourly Earnings of All Employees - Total Private
**Category:** Current Employment Statistics
**Seasonality:** Seasonally Adjusted
**Units:** Dollars

---

## Usage Examples

---

### Get Series Metadata

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get series dimension
series = session.get_table('macro', 'dim_economic_series').to_pandas()

print(series)
```

### Filter by Category

```python
# Get all unemployment-related series
unemployment_series = series[series['category'] == 'unemployment']

print(unemployment_series[['series_id', 'series_name']])
```

### Join with Facts

```python
# Get unemployment facts
macro = session.load_model('macro')
unemployment = macro.get_fact_df('fact_unemployment').to_pandas()

# Join with series metadata
merged = unemployment.merge(series, on='series_id')

print(merged[['date', 'series_name', 'value', 'units']].head())
```

---

## Relationships

---

### Used By (Foreign Key References)

- **[[Unemployment Facts]]** - `fact_unemployment.series_id → dim_economic_series.series_id`
- **[[CPI Facts]]** - `fact_cpi.series_id → dim_economic_series.series_id`
- **[[Employment Facts]]** - `fact_employment.series_id → dim_economic_series.series_id`
- **[[Wages Facts]]** - `fact_wages.series_id → dim_economic_series.series_id`

---

## Design Decisions

---

### Why series_id as primary key?

**Decision:** Use BLS series ID as primary key

**Rationale:**
- **Official identifier** - BLS standard
- **Unique** - Guaranteed uniqueness
- **Traceable** - Direct link to BLS documentation
- **Stable** - Rarely changes

### Why include category field?

**Decision:** Add semantic category (unemployment, inflation, etc.)

**Rationale:**
- **User-friendly** - More intuitive than series IDs
- **Filtering** - Easy category-based queries
- **Documentation** - Self-documenting data
- **Extensibility** - Can add more series per category

---

## Future Enhancements

---

### Planned Additions

- **State-level series** - Geographic breakdowns
- **Industry-specific** - Sector employment/wages
- **Demographic splits** - Age, gender, race breakdowns
- **Alternative measures** - U-6 unemployment, core CPI

---

## Related Documentation

---

### Model Documentation
- [[Macro Model Overview]] - Parent model
- [[Unemployment Facts]] - Unemployment data
- [[CPI Facts]] - Inflation data
- [[Employment Facts]] - Employment data
- [[Wages Facts]] - Wage data

### Architecture Documentation
- [[Data Pipeline/BLS]] - API ingestion
- [[Facets/Economics]] - Economic normalization
- [[Bronze Storage]] - Raw BLS data

### External Resources
- [BLS Data Finder](https://www.bls.gov/data/)
- [Series ID Formats](https://www.bls.gov/help/hlpforma.htm)

---

**Tags:** #economics/bls #component/model #concept/dimensional-modeling #concept/reference

**Last Updated:** 2024-11-08
**Table:** dim_economic_series
**Grain:** One row per BLS series
