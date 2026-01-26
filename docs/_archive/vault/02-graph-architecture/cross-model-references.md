# Cross-Model References

**Quick reference for all cross-model edges and relationships**

Source: Migrated from `/MODEL_EDGES_REFERENCE.md`
Last Updated: 2025-11-16

---

## Overview

This document provides a comprehensive reference for all cross-model edges in de_Funk. Cross-model edges enable queries that span multiple models, such as joining equity prices with corporate fundamentals or enriching forecasts with macroeconomic indicators.

**Quick Stats:**
- **Total cross-model edges**: 8 defined
- **Valid edges**: 4 (50%)
- **Deprecated edges**: 4 (50%)
- **Models with cross-model edges**: 5/8

---

## All Cross-Model Edges

| Source Model | Source Table | Target Model | Target Table | Type | Status | Location |
|-------------|-------------|-------------|-------------|------|--------|----------|
| equity | dim_equity | corporate | dim_corporate | many_to_one | ✅ VALID | equity.yaml:168-171 |
| corporate | dim_corporate | equity | dim_equity | many_to_one | ✅ VALID | corporate.yaml:136-139 |
| etf | fact_etf_prices | core | dim_calendar | left | ✅ VALID | etf.yaml:180-183 |
| etf | dim_etf_holdings | company | dim_company | many_to_one | ⚠️ DEPRECATED | etf.yaml:200-204 |
| forecast | fact_forecasts | core | dim_calendar | left | ✅ VALID | forecast.yaml:225-229 |
| forecast | fact_forecast_metrics | core | dim_calendar | left | ✅ VALID | forecast.yaml:231-235 |
| forecast | fact_forecasts | company | fact_prices | left | ⚠️ DEPRECATED | forecast.yaml:238-242 |
| forecast | fact_forecasts | company | dim_company | left | ⚠️ DEPRECATED | forecast.yaml:244-248 |

---

## Edges by Source Model

### core

**Outgoing Cross-Model Edges:** 0

**Note**: core is a foundation model - other models depend on it, but it doesn't reference other models.

---

### macro

**Outgoing Cross-Model Edges:** 0

**Note**: Currently independent, but should connect to other models for correlation analysis.

---

### city_finance

**Outgoing Cross-Model Edges:** 0

⚠️ **Issue**: Declares `depends_on: [macro]` but no edges defined.

**Recommended Edge:**
```yaml
# city_finance.yaml
edges:
  - from: fact_local_unemployment
    to: macro.fact_unemployment
    on: ["date=date"]
    type: left
    description: "Compare local vs national unemployment rates"
```

---

### equity

**Outgoing Cross-Model Edges:** 1

✅ **dim_equity → corporate.dim_corporate**
```yaml
# equity.yaml:168-171
- from: dim_equity
  to: corporate.dim_corporate
  on: ["company_id=company_id"]
  type: many_to_one
  description: "Each equity (ticker) belongs to a corporate entity (company)"
```

**Purpose**: Link tradable securities to their parent companies

**Example Query:**
```sql
SELECT
    e.ticker,
    e.company_name,
    c.sector,
    c.industry
FROM equity.dim_equity e
JOIN corporate.dim_corporate c ON e.company_id = c.company_id
```

---

### corporate

**Outgoing Cross-Model Edges:** 1

✅ **dim_corporate → equity.dim_equity**
```yaml
# corporate.yaml:136-139
- from: dim_corporate
  to: equity.dim_equity
  on: ["ticker_primary=ticker"]
  type: many_to_one
  description: "Each company has a primary ticker"
```

**Purpose**: Link companies to their primary trading symbol

**Example Query:**
```sql
SELECT
    c.company_name,
    c.ticker_primary,
    e.exchange_id
FROM corporate.dim_corporate c
JOIN equity.dim_equity e ON c.ticker_primary = e.ticker
```

---

### etf

**Outgoing Cross-Model Edges:** 2

✅ **fact_etf_prices → core.dim_calendar**
```yaml
# etf.yaml:180-183
- from: fact_etf_prices
  to: core.dim_calendar
  on: ["trade_date=date"]
  type: left
  description: "Join ETF prices to calendar for date-based filtering"
```

⚠️ **dim_etf_holdings → company.dim_company** (DEPRECATED)
```yaml
# etf.yaml:200-204
- from: dim_etf_holdings
  to: company.dim_company
  on: ["holding_ticker=ticker"]
  type: many_to_one
  description: "ETF holdings reference company stocks"
```

**Issue**: References deprecated company model

**Fix Required:**
```yaml
# etf.yaml (UPDATED)
- from: dim_etf_holdings
  to: equity.dim_equity
  on: ["holding_ticker=ticker"]
  type: many_to_one
  description: "ETF holdings reference equity instruments"
```

---

### forecast

**Outgoing Cross-Model Edges:** 4

✅ **fact_forecasts → core.dim_calendar**
```yaml
# forecast.yaml:225-229
- from: fact_forecasts
  to: core.dim_calendar
  on: ["prediction_date=date"]
  type: left
  description: "Join forecasts to calendar on prediction date"
```

✅ **fact_forecast_metrics → core.dim_calendar**
```yaml
# forecast.yaml:231-235
- from: fact_forecast_metrics
  to: core.dim_calendar
  on: ["metric_date=date"]
  type: left
  description: "Join forecast metrics to calendar"
```

⚠️ **fact_forecasts → company.fact_prices** (DEPRECATED)
```yaml
# forecast.yaml:238-242
- from: fact_forecasts
  to: company.fact_prices
  on: ["ticker=ticker"]
  type: left
  description: "Join forecasts to price history"
```

⚠️ **fact_forecasts → company.dim_company** (DEPRECATED)
```yaml
# forecast.yaml:244-248
- from: fact_forecasts
  to: company.dim_company
  on: ["ticker=ticker"]
  type: left
  description: "Join forecasts to company dimension"
```

**Fix Required:**
```yaml
# forecast.yaml (UPDATED)
- from: fact_forecasts
  to: equity.fact_equity_prices
  on: ["ticker=ticker", "prediction_date=trade_date"]
  type: left
  description: "Join forecasts to equity price history for validation"

- from: fact_forecasts
  to: equity.dim_equity
  on: ["ticker=ticker"]
  type: left
  description: "Join forecasts to equity dimension"
```

---

## Edges by Target Model

### core (Most Connected)

**Incoming Cross-Model Edges:** 5

- etf.fact_etf_prices → dim_calendar ✅
- forecast.fact_forecasts → dim_calendar ✅
- forecast.fact_forecast_metrics → dim_calendar ✅
- company.fact_prices → dim_calendar ⚠️ (deprecated model)
- company.fact_news → dim_calendar ⚠️ (deprecated model)

**Pattern**: Calendar dimension is universally referenced for time-based filtering.

---

### equity

**Incoming Cross-Model Edges:** 1

- corporate.dim_corporate → dim_equity ✅

**Expected Additional Edges:**
- etf.dim_etf_holdings → dim_equity (currently points to deprecated company)
- forecast.fact_forecasts → fact_equity_prices (currently points to deprecated company)

---

### corporate

**Incoming Cross-Model Edges:** 1

- equity.dim_equity → dim_corporate ✅

**Recommended Additional Edges:**
- etf.dim_etf_holdings → dim_corporate (for portfolio analysis at corporate level)
- forecast.fact_forecasts → dim_corporate (for fundamental-based forecasting)

---

### macro

**Incoming Cross-Model Edges:** 0

**Recommended Edges:**
- equity.fact_equity_prices → fact_unemployment (macro correlation)
- forecast.fact_forecasts → economic_indicators_wide (macro-enriched forecasts)
- city_finance.fact_local_unemployment → fact_unemployment (local vs national)

---

## Cross-Model Measures

Measures can reference columns from other models directly:

### etf Model Cross-Model Measures

⚠️ **holdings_weighted_return** (DEPRECATED)
```yaml
# etf.yaml:111-120
holdings_weighted_return:
  type: weighted
  source: company.fact_prices.close  # ⚠️ Should be equity.fact_equity_prices.close
  weighting_method: holdings_weight
  description: "ETF return calculated from underlying holdings"
```

⚠️ **holdings_weighted_volume** (DEPRECATED)
```yaml
# etf.yaml:122-130
holdings_weighted_volume:
  type: weighted
  source: company.fact_prices.volume  # ⚠️ Should be equity.fact_equity_prices.volume
  weighting_method: holdings_weight
  description: "Weighted trading volume of underlying holdings"
```

**Fix Required:**
```yaml
# etf.yaml (UPDATED)
holdings_weighted_return:
  type: weighted
  source: equity.fact_equity_prices.close
  weighting_method: holdings_weight

holdings_weighted_volume:
  type: weighted
  source: equity.fact_equity_prices.volume
  weighting_method: holdings_weight
```

---

## Missing Cross-Model Edges

### Critical (Must Fix)

**Priority**: 🔴 BLOCKING

| Source | Target | Missing Edge | Reason |
|--------|--------|-------------|--------|
| etf | equity | dim_etf_holdings → dim_equity | Replace deprecated company reference |
| forecast | equity | fact_forecasts → fact_equity_prices | Replace deprecated company reference |
| forecast | equity | fact_forecasts → dim_equity | Replace deprecated company reference |

---

### High (Should Add)

**Priority**: 🟠 FUNCTIONAL GAP

| Source | Target | Missing Edge | Reason |
|--------|--------|-------------|--------|
| city_finance | macro | fact_local_unemployment → fact_unemployment | Implement declared dependency |
| etf | corporate | dim_etf_holdings → dim_corporate | Portfolio analysis at corporate level |
| forecast | corporate | fact_forecasts → dim_corporate | Fundamental-based forecasting |

---

### Medium (Analytics Enhancement)

**Priority**: 🟡 NICE TO HAVE

| Source | Target | Missing Edge | Reason |
|--------|--------|-------------|--------|
| equity | macro | fact_equity_prices → fact_unemployment | Macro correlation analysis |
| equity | macro | fact_equity_prices → fact_cpi | Inflation correlation |
| equity | macro | fact_equity_prices → economic_indicators_wide | Full macro context |

---

## Edge Syntax Reference

### Basic Cross-Model Edge

```yaml
edges:
  - from: local_table
    to: other_model.remote_table
    on: ["local_col=remote_col"]
    type: join_type
    description: "Relationship description"
```

### Example: Equity to Corporate

```yaml
# equity.yaml
edges:
  - from: dim_equity
    to: corporate.dim_corporate
    on: ["company_id=company_id"]
    type: many_to_one
    description: "Each equity belongs to a corporate entity"
```

### Join Types

| Type | SQL Equivalent | Use Case |
|------|---------------|----------|
| `many_to_one` | LEFT JOIN | Many fact records to one dimension |
| `one_to_many` | LEFT JOIN | One dimension to many facts |
| `left` | LEFT OUTER JOIN | Keep all source records |
| `inner` | INNER JOIN | Only matching records |
| `full` / `outer` | FULL OUTER JOIN | All records from both sides |

---

## Cross-Model Query Examples

### Join Equity Prices with Corporate Info

```python
from models.api.session import UniversalSession

session = UniversalSession(backend='duckdb')

# Prices with company sector and industry
df = session.query("""
    SELECT
        p.ticker,
        p.trade_date,
        p.close,
        c.company_name,
        c.sector,
        c.industry
    FROM equity.fact_equity_prices p
    JOIN equity.dim_equity e ON p.ticker = e.ticker
    JOIN corporate.dim_corporate c ON e.company_id = c.company_id
    WHERE p.trade_date >= '2024-01-01'
""")
```

---

### Analyze ETF Holdings by Corporate Entity

```python
# After fixing deprecated reference
df = session.query("""
    SELECT
        etf.etf_ticker,
        c.company_name,
        c.sector,
        etf.weight
    FROM etf.dim_etf_holdings etf
    JOIN equity.dim_equity e ON etf.holding_ticker = e.ticker
    JOIN corporate.dim_corporate c ON e.company_id = c.company_id
    WHERE etf.etf_ticker = 'SPY'
    ORDER BY etf.weight DESC
""")
```

---

### Macro-Enriched Price Analysis

```python
# After adding equity → macro edge
df = session.query("""
    SELECT
        p.trade_date,
        AVG(p.close) as avg_price,
        u.unemployment_rate,
        cpi.value as cpi
    FROM equity.fact_equity_prices p
    JOIN macro.fact_unemployment u ON p.trade_date = u.date
    JOIN macro.fact_cpi cpi ON p.trade_date = cpi.date
    GROUP BY p.trade_date, u.unemployment_rate, cpi.value
    ORDER BY p.trade_date
""")
```

---

## Action Plan

### Phase 1: Fix Deprecated References

**Files to Update:**

**etf.yaml:**
```bash
# Line ~200: Update edge
- from: dim_etf_holdings
  to: equity.dim_equity  # Changed from company.dim_company
  on: ["holding_ticker=ticker"]

# Line ~113: Update measure
holdings_weighted_return:
  source: equity.fact_equity_prices.close  # Changed from company.fact_prices.close

# Line ~124: Update measure
holdings_weighted_volume:
  source: equity.fact_equity_prices.volume  # Changed from company.fact_prices.volume
```

**forecast.yaml:**
```bash
# Line ~239: Update edge
- from: fact_forecasts
  to: equity.fact_equity_prices  # Changed from company.fact_prices
  on: ["ticker=ticker", "prediction_date=trade_date"]

# Line ~245: Update edge
- from: fact_forecasts
  to: equity.dim_equity  # Changed from company.dim_company
  on: ["ticker=ticker"]
```

---

### Phase 2: Add Missing Relationships

**city_finance.yaml:**
```yaml
edges:
  - from: fact_local_unemployment
    to: macro.fact_unemployment
    on: ["date=date"]
    type: left
    description: "Compare local vs national unemployment"
```

**etf.yaml:**
```yaml
edges:
  - from: dim_etf_holdings
    to: corporate.dim_corporate
    on: ["holding_ticker=ticker_primary"]
    type: many_to_one
    description: "ETF holdings at corporate entity level"
```

**forecast.yaml:**
```yaml
edges:
  - from: fact_forecasts
    to: corporate.dim_corporate
    on: ["ticker=ticker_primary"]
    type: left
    description: "Connect forecasts to corporate fundamentals"
```

---

### Phase 3: Cleanup

1. **Archive company.yaml** (after all references updated)
2. **Update documentation** (remove company references)
3. **Verify no code references** to company model

```bash
# Search for lingering references
grep -r "company\." configs/models/
grep -r "company\." models/implemented/
```

---

## Related Documentation

- [Dependency Resolution](dependency-resolution.md) - Model dependency hierarchy
- [Graph Overview](graph-overview.md) - Graph architecture explanation
- [Query Planner](query-planner.md) - How cross-model joins work
- [UniversalSession](../01-core-components/universal-session.md) - Cross-model query interface
