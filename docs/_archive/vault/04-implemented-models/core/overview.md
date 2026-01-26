# Core Model Overview

**Foundation calendar dimension for all time-based analysis**

---

## Summary

| Property | Value |
|----------|-------|
| **Model** | core |
| **Version** | 1.0 |
| **Status** | Production |
| **Tier** | 0 (Foundation) |
| **Dependencies** | None |
| **Data Source** | Generated |

---

## Purpose

The core model provides the **calendar dimension** that serves as the foundation for all time-series analysis in de_Funk. Every model that deals with dates links to `dim_calendar`.

### Key Uses

- **Date Filtering**: Filter by year, quarter, month, week
- **Fiscal Periods**: Fiscal year/quarter analysis
- **Aggregation**: Group by month, quarter, year
- **Joins**: Link facts to calendar for date attributes

---

## Tables

| Table | Type | Description |
|-------|------|-------------|
| [dim_calendar](dimensions.md) | Dimension | Calendar lookup with 23+ attributes |

---

## Cross-Model Usage

All time-based models join to core:

```yaml
# stocks/graph.yaml
edges:
  - from: fact_stock_prices
    to: core.dim_calendar
    on: [trade_date = date]

# macro/graph.yaml
edges:
  - from: fact_unemployment
    to: core.dim_calendar
    on: [date = date]
```

---

## Date Range

| Property | Value |
|----------|-------|
| **Start Date** | Configurable (default: 2000-01-01) |
| **End Date** | Current date + 5 years |
| **Granularity** | Daily |
| **Total Records** | ~10,000+ rows |

---

## Configuration

**File**: `configs/models/core.yaml`

```yaml
model: core
version: 1
description: "Core calendar dimension"
depends_on: []

schema:
  dimensions:
    dim_calendar:
      description: "Calendar dimension for date-based analysis"
      columns:
        date: {type: date, primary_key: true}
        year: {type: integer}
        # ... 23+ columns
```

---

## Building

The core model generates calendar data programmatically:

```bash
# Build core model first (no dependencies)
python -m scripts.build.rebuild_model --model core
```

---

## Related Documentation

- [Dimensions](dimensions.md) - dim_calendar schema
- [Graph Architecture](../../02-graph-architecture/README.md)
