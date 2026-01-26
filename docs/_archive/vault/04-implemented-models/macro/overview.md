# Macro Model Overview

**Macroeconomic indicators from Bureau of Labor Statistics**

---

## Summary

| Property | Value |
|----------|-------|
| **Model** | macro |
| **Version** | 1.0 |
| **Status** | Production |
| **Tier** | 1 (Independent) |
| **Dependencies** | core |
| **Data Source** | Bureau of Labor Statistics (BLS) |

---

## Purpose

The macro model provides **macroeconomic indicators** from the Bureau of Labor Statistics:

- **Unemployment Rate**: National unemployment statistics
- **Consumer Price Index (CPI)**: Inflation indicators
- **Employment**: Total nonfarm employment
- **Wages**: Average hourly earnings

---

## Tables

| Table | Type | Description |
|-------|------|-------------|
| `dim_economic_series` | Dimension | Economic indicator series metadata |
| `fact_unemployment` | Fact | National unemployment rate (monthly) |
| `fact_cpi` | Fact | Consumer Price Index (monthly) |
| `fact_employment` | Fact | Total nonfarm employment (monthly) |
| `fact_wages` | Fact | Average hourly earnings (monthly) |
| `economic_indicators_wide` | Fact | All indicators pivoted wide by date |

---

## BLS Series

| Series | ID | Name |
|--------|-----|------|
| Unemployment | `LNS14000000` | Unemployment Rate - Civilian Labor Force |
| CPI | `CUUR0000SA0` | Consumer Price Index - All Urban Consumers |
| Employment | `CES0000000001` | Total Nonfarm Employment |
| Wages | `CES0500000003` | Average Hourly Earnings - Total Private |

---

## Measures

| Measure | Source | Aggregation | Description |
|---------|--------|-------------|-------------|
| `avg_unemployment_rate` | fact_unemployment.value | avg | Average unemployment rate |
| `latest_cpi` | fact_cpi.value | max | Latest CPI value |
| `employment_growth` | fact_employment.value | sum | Total employment growth |
| `wage_trend` | fact_wages.value | avg | Average wage trend |

---

## Usage Example

```sql
-- Get unemployment trend
SELECT date, value as unemployment_rate
FROM macro.fact_unemployment
WHERE date >= '2024-01-01'
ORDER BY date

-- Compare indicators
SELECT
    date,
    unemployment_rate,
    cpi_value,
    avg_hourly_earnings
FROM macro.economic_indicators_wide
ORDER BY date
```

---

## Data Availability

- **Update Frequency**: Monthly
- **Historical Range**: Varies by series (typically 20+ years)
- **Seasonal Adjustment**: Most series are seasonally adjusted

---

## Related Documentation

- [Dimensions](dimensions.md) - Schema details
- [Measures](measures.md) - Measure definitions
- [Data Providers](../../03-data-providers/bls/) - BLS terms of use
