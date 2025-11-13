# Model Edges Quick Reference

**Last Updated:** 2025-11-13

## Table of Contents
1. [All Defined Edges](#all-defined-edges)
2. [Edges by Source Model](#edges-by-source-model)
3. [Edges by Target Model](#edges-by-target-model)
4. [Cross-Model Edges Only](#cross-model-edges-only)
5. [Missing/Broken Edges](#missingbroken-edges)

---

## All Defined Edges

| Source Model | Source Table/Field | Target Model | Target Table/Field | Type | Status | File Location |
|-------------|-------------------|-------------|-------------------|------|--------|---------------|
| equity | dim_equity.company_id | corporate | dim_corporate.company_id | many_to_one | ✅ VALID | equity.yaml:168-171 |
| corporate | dim_corporate.ticker_primary | equity | dim_equity.ticker | many_to_one | ✅ VALID | corporate.yaml:136-139 |
| etf | fact_etf_prices | core | dim_calendar | left | ✅ VALID | etf.yaml:180-183 |
| etf | dim_etf_holdings | company | dim_company | many_to_one | ⚠️ DEPRECATED | etf.yaml:200-204 |
| forecast | fact_forecasts | core | dim_calendar | left | ✅ VALID | forecast.yaml:225-229 |
| forecast | fact_forecast_metrics | core | dim_calendar | left | ✅ VALID | forecast.yaml:231-235 |
| forecast | fact_forecasts | company | fact_prices | left | ⚠️ DEPRECATED | forecast.yaml:238-242 |
| forecast | fact_forecasts | company | dim_company | left | ⚠️ DEPRECATED | forecast.yaml:244-248 |
| company | fact_prices | core | dim_calendar | left | ⚠️ DEPRECATED MODEL | company.yaml:271-274 |
| company | fact_news | core | dim_calendar | left | ⚠️ DEPRECATED MODEL | company.yaml:277-280 |

---

## Edges by Source Model

### core
**Cross-Model Edges Out:** 0 (core is a foundation model, others depend on it)

### macro
**Cross-Model Edges Out:** 0

### city_finance
**Cross-Model Edges Out:** 0
**NOTE:** Declares `depends_on: [macro]` but no edges defined

### company (DEPRECATED)
**Cross-Model Edges Out:** 2 (to core)
- fact_prices → core.dim_calendar
- fact_news → core.dim_calendar

### equity
**Cross-Model Edges Out:** 1
- dim_equity.company_id → corporate.dim_corporate.company_id ✅

### corporate
**Cross-Model Edges Out:** 1
- dim_corporate.ticker_primary → equity.dim_equity.ticker ✅

### etf
**Cross-Model Edges Out:** 2
- fact_etf_prices → core.dim_calendar ✅
- dim_etf_holdings → company.dim_company ⚠️ (should be equity)

### forecast
**Cross-Model Edges Out:** 4
- fact_forecasts → core.dim_calendar ✅
- fact_forecast_metrics → core.dim_calendar ✅
- fact_forecasts → company.fact_prices ⚠️ (should be equity)
- fact_forecasts → company.dim_company ⚠️ (should be equity)

---

## Edges by Target Model

### core (receives most connections)
**Cross-Model Edges In:** 5
- etf.fact_etf_prices → dim_calendar ✅
- forecast.fact_forecasts → dim_calendar ✅
- forecast.fact_forecast_metrics → dim_calendar ✅
- company.fact_prices → dim_calendar ⚠️ (deprecated)
- company.fact_news → dim_calendar ⚠️ (deprecated)

### macro
**Cross-Model Edges In:** 0
**NOTE:** city_finance declares dependency but no edge defined

### city_finance
**Cross-Model Edges In:** 0

### company (DEPRECATED)
**Cross-Model Edges In:** 3 (all problematic)
- etf.dim_etf_holdings → dim_company ⚠️
- forecast.fact_forecasts → fact_prices ⚠️
- forecast.fact_forecasts → dim_company ⚠️

### equity
**Cross-Model Edges In:** 1
- corporate.dim_corporate.ticker_primary → dim_equity ✅

### corporate
**Cross-Model Edges In:** 1
- equity.dim_equity.company_id → dim_corporate ✅

### etf
**Cross-Model Edges In:** 0

### forecast
**Cross-Model Edges In:** 0

---

## Cross-Model Edges Only

| From | To | Join Condition | Purpose | Status |
|------|-----|---------------|---------|--------|
| equity | corporate | company_id=company_id | Equity belongs to corporate entity | ✅ VALID |
| corporate | equity | ticker_primary=ticker | Company has primary ticker | ✅ VALID |
| etf | core | trade_date=date | Time-based filtering | ✅ VALID |
| etf | company | holding_ticker=ticker | ETF holdings | ⚠️ USE DEPRECATED |
| forecast | core | prediction_date=date | Time-based filtering | ✅ VALID |
| forecast | core | metric_date=date | Time-based filtering | ✅ VALID |
| forecast | company | ticker=ticker | Forecast to prices | ⚠️ USE DEPRECATED |
| forecast | company | ticker=ticker | Forecast to company | ⚠️ USE DEPRECATED |

**Summary:**
- Total cross-model edges: 8
- Valid edges: 4 (50%)
- Deprecated edges: 4 (50%)
- Edges to deprecated models: 3
- Edges from deprecated models: 2 (excluding company internal edges)

---

## Missing/Broken Edges

### CRITICAL: Must Fix (Blocking Production)

| Source | Target | Missing Edge | Reason | Priority |
|--------|--------|-------------|--------|----------|
| etf | equity | dim_etf_holdings → dim_equity | Replace deprecated company reference | 🔴 CRITICAL |
| forecast | equity | fact_forecasts → fact_equity_prices | Replace deprecated company reference | 🔴 CRITICAL |
| forecast | equity | fact_forecasts → dim_equity | Replace deprecated company reference | 🔴 CRITICAL |

### HIGH: Should Add (Functional Gap)

| Source | Target | Missing Edge | Reason | Priority |
|--------|--------|-------------|--------|----------|
| city_finance | macro | fact_local_unemployment → fact_unemployment | Declared in depends_on but not implemented | 🟠 HIGH |
| etf | corporate | dim_etf_holdings → dim_corporate | ETF holdings at corporate level | 🟠 HIGH |
| forecast | corporate | fact_forecasts → dim_corporate | Connect predictions to fundamentals | 🟠 HIGH |

### MEDIUM: Nice to Have (Analytics Enhancement)

| Source | Target | Missing Edge | Reason | Priority |
|--------|--------|-------------|--------|----------|
| equity | macro | fact_equity_prices → fact_unemployment | Macro correlation analysis | 🟡 MEDIUM |
| equity | macro | fact_equity_prices → fact_cpi | Inflation correlation | 🟡 MEDIUM |
| equity | macro | fact_equity_prices → economic_indicators_wide | Full macro context | 🟡 MEDIUM |

### LOW: Optional (Future Enhancement)

| Source | Target | Missing Edge | Reason | Priority |
|--------|--------|-------------|--------|----------|
| forecast | macro | fact_forecasts → economic_indicators_wide | Macro-enriched forecasts | 🟢 LOW |
| city_finance | equity | fact_local_unemployment → fact_equity_prices | Local economic impact (if applicable) | 🟢 LOW |
| city_finance | corporate | fact_building_permits → dim_corporate | Corporate real estate activity | 🟢 LOW |

---

## Cross-Model Measures (Non-Edge References)

These are measure definitions that reference columns from other models:

| Model | Measure Name | References | Status |
|-------|-------------|-----------|--------|
| etf | holdings_weighted_return | company.fact_prices.close | ⚠️ Should be equity.fact_equity_prices.close |
| etf | holdings_weighted_volume | company.fact_prices.volume | ⚠️ Should be equity.fact_equity_prices.volume |

---

## Edge Syntax Quick Reference

### Within-Model Edge
```yaml
edges:
  - from: fact_table
    to: dim_table
    on: ["column=column"]
    type: many_to_one
    description: "Description"
```

### Cross-Model Edge
```yaml
edges:
  - from: local_table
    to: other_model.remote_table
    on: ["local_col=remote_col"]
    type: many_to_one
    description: "Cross-model relationship"
```

### Common Join Types
- `many_to_one` - Many fact records to one dimension record
- `one_to_many` - One dimension to many facts (rare)
- `left` - Left outer join (keeps all source records)
- `inner` - Inner join (only matching records)

---

## Action Items Summary

### Phase 1: Fix Deprecated References (BLOCKING)
```bash
# etf.yaml
- Line ~200: company.dim_company → equity.dim_equity
- Line ~113: company.fact_prices.close → equity.fact_equity_prices.close
- Line ~124: company.fact_prices.volume → equity.fact_equity_prices.volume

# forecast.yaml
- Line ~239: company.fact_prices → equity.fact_equity_prices
- Line ~245: company.dim_company → equity.dim_equity
```

### Phase 2: Add Missing Relationships
```yaml
# city_finance.yaml
- from: fact_local_unemployment
  to: macro.fact_unemployment
  on: ["date=date"]
  type: left

# etf.yaml
- from: dim_etf_holdings
  to: corporate.dim_corporate
  on: ["holding_ticker=ticker_primary"]  # May need mapping
  type: many_to_one

# forecast.yaml
- from: fact_forecasts
  to: corporate.dim_corporate
  on: ["ticker=ticker_primary"]
  type: left
```

### Phase 3: Cleanup
- Archive company.yaml
- Update all documentation
- Verify no code references to company model

---

## Related Documentation

- Main Analysis: `/home/user/de_Funk/MODEL_DEPENDENCY_ANALYSIS.md`
- Visual Graph: `/home/user/de_Funk/MODEL_DEPENDENCY_GRAPH.txt`
- Migration Guide: `docs/EQUITY_CORPORATE_MIGRATION_GUIDE.md` (if exists)

---

**Legend:**
- ✅ VALID - Edge is correctly defined
- ⚠️ DEPRECATED - Edge references deprecated model
- 🔴 CRITICAL - Must fix before production
- 🟠 HIGH - Should fix soon
- 🟡 MEDIUM - Nice to have
- 🟢 LOW - Future enhancement
