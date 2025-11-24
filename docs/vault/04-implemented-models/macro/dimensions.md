# Macro Dimensions

**Economic indicator schema**

---

## dim_economic_series

**Purpose**: Economic indicator series metadata

**Primary Key**: `series_id`

---

## Schema

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `series_id` | string | BLS series identifier | `LNS14000000` |
| `series_name` | string | Human-readable name | `National Unemployment Rate` |
| `category` | string | Category | `unemployment` |
| `frequency` | string | Data frequency | `monthly` |
| `units` | string | Unit of measure | `percent` |
| `seasonal_adjustment` | string | Adjustment type | `seasonally_adjusted` |

---

## Fact Tables

### fact_unemployment

**National unemployment rate (monthly)**

| Column | Type | Description |
|--------|------|-------------|
| `series_id` | string | BLS series ID |
| `date` | date | Observation date |
| `year` | integer | Year |
| `period` | string | Period code (M01-M12) |
| `value` | double | Unemployment rate (%) |
| `period_name` | string | Period name (January, etc.) |

**Partitions**: `year`

### fact_cpi

**Consumer Price Index (monthly)**

| Column | Type | Description |
|--------|------|-------------|
| `series_id` | string | BLS series ID |
| `date` | date | Observation date |
| `year` | integer | Year |
| `period` | string | Period code |
| `value` | double | CPI value |
| `period_name` | string | Period name |

**Partitions**: `year`

### fact_employment

**Total nonfarm employment (monthly)**

| Column | Type | Description |
|--------|------|-------------|
| `series_id` | string | BLS series ID |
| `date` | date | Observation date |
| `year` | integer | Year |
| `period` | string | Period code |
| `value` | double | Employment (thousands) |
| `period_name` | string | Period name |

**Partitions**: `year`

### fact_wages

**Average hourly earnings (monthly)**

| Column | Type | Description |
|--------|------|-------------|
| `series_id` | string | BLS series ID |
| `date` | date | Observation date |
| `year` | integer | Year |
| `period` | string | Period code |
| `value` | double | Earnings ($) |
| `period_name` | string | Period name |

**Partitions**: `year`

### economic_indicators_wide

**All indicators pivoted wide by date**

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | Observation date |
| `unemployment_rate` | double | Unemployment rate (%) |
| `cpi_value` | double | CPI value |
| `total_employment` | double | Employment (thousands) |
| `avg_hourly_earnings` | double | Average hourly earnings ($) |

**Partitions**: `date`

---

## Related Documentation

- [Overview](overview.md) - Model overview
- [Measures](measures.md) - Available measures
