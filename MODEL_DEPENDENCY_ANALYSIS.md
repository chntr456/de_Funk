# Model Dependency Graph Analysis

**Analysis Date:** 2025-11-13
**Total Models Analyzed:** 8

---

## Executive Summary

This report analyzes the dependency graph across all domain models in the de_Funk data platform. The analysis reveals a well-structured but incomplete interconnection between models, with the deprecated `company` model creating transitional complexity as the system migrates to `equity` and `corporate` models.

**Key Findings:**
- 3 models have cross-model edges defined
- 1 model (company) is deprecated but still referenced
- Several logical connections are missing between related domains
- forecast → company edges exist, but forecast → equity/corporate are missing

---

## 1. Dependency Hierarchy

### Tier 0: Foundation
```
core (no dependencies)
  └── Provides: dim_calendar (universal time dimension)
```

### Tier 1: Core Domain Models
```
macro
  └── depends_on: [core]

corporate
  └── depends_on: [core]

company (DEPRECATED)
  └── depends_on: [core]
```

### Tier 2: Market Data Models
```
equity
  └── depends_on: [core, corporate]

city_finance
  └── depends_on: [core, macro]
```

### Tier 3: Portfolio & Analytics Models
```
etf
  └── depends_on: [core, company]

forecast
  └── depends_on: [core, company]
```

---

## 2. Cross-Model Edges Inventory

### 2.1 Existing Cross-Model Edges

#### company → core (DEPRECATED MODEL)
```yaml
- from: fact_prices
  to: core.dim_calendar
  on: ["trade_date=date"]
  type: left
  description: "Join prices to calendar for date-based filtering and attributes"

- from: fact_news
  to: core.dim_calendar
  on: ["publish_date=date"]
  type: left
  description: "Join news to calendar for date-based filtering"
```

#### equity → corporate
```yaml
- from: dim_equity.company_id
  to: corporate.dim_corporate.company_id
  type: many_to_one
  description: "Each equity (ticker) belongs to a corporate entity (company)"
```
**Status:** DEFINED - Location: equity.yaml line 168-171

#### corporate → equity
```yaml
- from: dim_corporate.ticker_primary
  to: equity.dim_equity.ticker
  type: many_to_one
  description: "Each company has a primary ticker"
```
**Status:** DEFINED - Location: corporate.yaml line 136-139

#### etf → core
```yaml
- from: fact_etf_prices
  to: core.dim_calendar
  on: ["trade_date=date"]
  type: left
  description: "Join ETF prices to calendar"
```
**Status:** DEFINED - Location: etf.yaml line 180-183

#### etf → company (USES DEPRECATED MODEL)
```yaml
- from: dim_etf_holdings
  to: company.dim_company
  on: ["holding_ticker=ticker"]
  type: many_to_one
  description: "Holdings are company stocks"
```
**Status:** DEFINED BUT PROBLEMATIC - Location: etf.yaml line 200-204
**Issue:** References deprecated company model instead of equity model

#### forecast → core
```yaml
- from: fact_forecasts
  to: core.dim_calendar
  on: ["prediction_date=date"]
  type: left
  description: "Join forecasts to calendar on prediction date"

- from: fact_forecast_metrics
  to: core.dim_calendar
  on: ["metric_date=date"]
  type: left
  description: "Join metrics to calendar on metric date"
```
**Status:** DEFINED - Location: forecast.yaml line 225-235

#### forecast → company (USES DEPRECATED MODEL)
```yaml
- from: fact_forecasts
  to: company.fact_prices
  on: ["ticker=ticker"]
  type: left
  description: "Join forecasts to company prices on ticker (shared dimension)"

- from: fact_forecasts
  to: company.dim_company
  on: ["ticker=ticker"]
  type: left
  description: "Join forecasts to company dimension on ticker"
```
**Status:** DEFINED BUT PROBLEMATIC - Location: forecast.yaml line 238-248
**Issue:** References deprecated company model instead of equity model

---

## 3. Cross-Model Measures (Advanced References)

### etf model contains cross-model measure definitions:
```yaml
holdings_weighted_return:
  type: weighted
  source: company.fact_prices.close  # Cross-model reference!
  description: "ETF return calculated from underlying holdings"

holdings_weighted_volume:
  type: weighted
  source: company.fact_prices.volume  # Cross-model reference!
  description: "Weighted trading volume of underlying holdings"
```
**Location:** etf.yaml lines 111-130
**Issue:** References deprecated company.fact_prices instead of equity.fact_equity_prices

---

## 4. Missing Relationships Analysis

### 4.1 CRITICAL: Broken Migration Path

#### Missing: equity ← → etf
**Current State:** etf → company (deprecated)
**Should Be:** etf → equity
```yaml
# MISSING in etf.yaml
- from: dim_etf_holdings
  to: equity.dim_equity
  on: ["holding_ticker=ticker"]
  type: many_to_one
  description: "ETF holdings reference equity instruments"
```

#### Missing: equity ← → forecast
**Current State:** forecast → company (deprecated)
**Should Be:** forecast → equity
```yaml
# MISSING in forecast.yaml
- from: fact_forecasts
  to: equity.fact_equity_prices
  on: ["ticker=ticker", "prediction_date=trade_date"]
  type: left
  description: "Join forecasts to equity prices for validation"

- from: fact_forecasts
  to: equity.dim_equity
  on: ["ticker=ticker"]
  type: left
  description: "Join forecasts to equity dimension"
```

### 4.2 Logical Missing Connections

#### Missing: corporate ← → forecast
**Rationale:** Forecasts predict equity prices, which belong to corporate entities. Connecting forecast → corporate would enable fundamental-based forecast analysis.
```yaml
# RECOMMENDED in forecast.yaml
- from: fact_forecasts
  to: corporate.dim_corporate
  on: ["ticker=ticker_primary"]
  type: left
  description: "Join forecasts to corporate entities for fundamental analysis"
```

#### Missing: corporate ← → etf
**Rationale:** ETF holdings are company stocks. Connecting etf → corporate enables portfolio analysis at the corporate entity level.
```yaml
# RECOMMENDED in etf.yaml
- from: dim_etf_holdings
  to: corporate.dim_corporate
  on: ["holding_ticker=ticker_primary"]
  type: many_to_one
  description: "ETF holdings belong to corporate entities"
```

#### Missing: macro ← → equity
**Rationale:** Macroeconomic indicators correlate with equity performance. No direct edge exists.
```yaml
# RECOMMENDED in equity.yaml
- from: fact_equity_prices
  to: macro.fact_unemployment
  on: ["trade_date=date"]
  type: left
  description: "Join equity prices to macro indicators for correlation analysis"
```

#### Missing: macro ← → forecast
**Rationale:** Macroeconomic indicators could improve forecast models.
```yaml
# RECOMMENDED in forecast.yaml
- from: fact_forecasts
  to: macro.economic_indicators_wide
  on: ["prediction_date=date"]
  type: left
  description: "Enrich forecasts with macro economic context"
```

#### Missing: city_finance edges to other models
**Current State:** city_finance declares `depends_on: [core, macro]` but has NO cross-model edges defined.
**Rationale:** Chicago unemployment and permit data could correlate with local corporate activity or equity performance.
```yaml
# RECOMMENDED in city_finance.yaml
- from: fact_local_unemployment
  to: macro.fact_unemployment
  on: ["date=date"]
  type: left
  description: "Compare local vs national unemployment rates"
```

---

## 5. Verification: forecast → company & forecast → core

### forecast → core edges: CORRECT
```yaml
✓ fact_forecasts → core.dim_calendar (on prediction_date=date)
✓ fact_forecast_metrics → core.dim_calendar (on metric_date=date)
```
**Status:** Properly defined in forecast.yaml lines 225-235

### forecast → company edges: DEPRECATED REFERENCE
```yaml
⚠ fact_forecasts → company.fact_prices (on ticker=ticker)
⚠ fact_forecasts → company.dim_company (on ticker=ticker)
```
**Status:** Defined but uses deprecated company model
**Location:** forecast.yaml lines 238-248
**Action Required:** Migrate to equity model

---

## 6. Model Interconnection Matrix

|            | core | macro | city_finance | company (deprecated) | equity | corporate | etf | forecast |
|------------|------|-------|--------------|---------------------|--------|-----------|-----|----------|
| **core**   | -    | ←     | ←            | ←                   | ←      | ←         | ←   | ←        |
| **macro**  | →    | -     |              |                     |        |           |     |          |
| **city_finance** | → | (depends) | -    |                     |        |           |     |          |
| **company (deprecated)** | → | - | -        | -                   | ←      |           | ←   | ←        |
| **equity** | →    |       |              |                     | -      | ↔         |     |          |
| **corporate** | → |       |              |                     | ↔      | -         |     |          |
| **etf**    | →    |       |              | → (deprecated)      |        |           | -   |          |
| **forecast** | →  |       |              | → (deprecated)      |        |           |     | -        |

**Legend:**
- → = Outgoing edge/dependency
- ← = Incoming edge/dependency
- ↔ = Bidirectional relationship
- (depends) = Declared in depends_on but no edges defined
- (deprecated) = References deprecated model

---

## 7. Recommendations

### Priority 1: CRITICAL - Fix Deprecated References
1. **Update etf.yaml:**
   - Replace `company.dim_company` with `equity.dim_equity` in holdings edge
   - Update cross-model measures to reference `equity.fact_equity_prices` instead of `company.fact_prices`

2. **Update forecast.yaml:**
   - Replace `company.fact_prices` with `equity.fact_equity_prices`
   - Replace `company.dim_company` with `equity.dim_equity`

3. **Remove or archive company.yaml** after migration is complete

### Priority 2: HIGH - Add Missing Core Relationships
1. **Add etf → corporate edge:** Connect ETF holdings to corporate entities for entity-level portfolio analysis
2. **Add forecast → corporate edge:** Enable fundamental-based forecast analysis
3. **Add macro → equity edge:** Enable macro-economic correlation analysis

### Priority 3: MEDIUM - Complete city_finance Integration
1. **Add city_finance → macro edge:** Implement the declared but missing cross-model edge for local vs national comparison
2. **Consider city_finance → corporate edge:** If Chicago companies are in scope

### Priority 4: LOW - Enhanced Analytics
1. **Add macro → forecast edge:** Enrich forecast models with macroeconomic indicators
2. **Add city_finance → equity edge:** Analyze local economic impact on equities (if applicable)

---

## 8. Graph Completeness Score

### Current State:
- **Total Models:** 8 (7 active + 1 deprecated)
- **Models with Cross-Model Edges:** 5/8 (62.5%)
- **Models with Complete Edges:** 3/8 (37.5%)
- **Deprecated References:** 3 edges + 2 measures (BLOCKING ISSUES)

### Target State (after migration):
- **Models with Cross-Model Edges:** 7/7 (100% for active models)
- **Models with Complete Edges:** 6/7 (85.7%)
- **Deprecated References:** 0 (CLEAN)

---

## 9. Action Items

### Immediate (Block Production Issues)
- [ ] Update etf.yaml edge: `dim_etf_holdings → equity.dim_equity`
- [ ] Update etf.yaml measures to reference `equity.fact_equity_prices`
- [ ] Update forecast.yaml edges to reference `equity` model instead of `company`

### Short-term (Complete Migration)
- [ ] Archive company.yaml or add sunset date
- [ ] Verify no other references to company model exist in codebase
- [ ] Update documentation to reflect equity/corporate split

### Medium-term (Enhance Graph)
- [ ] Add etf → corporate edge
- [ ] Add forecast → corporate edge
- [ ] Implement city_finance → macro edge (already declared in depends_on)

### Long-term (Advanced Analytics)
- [ ] Add macro → equity correlation edges
- [ ] Add macro → forecast enrichment edges
- [ ] Consider graph database implementation for advanced traversal

---

## Appendix A: Model File Locations

- `/home/user/de_Funk/configs/models/core.yaml`
- `/home/user/de_Funk/configs/models/macro.yaml`
- `/home/user/de_Funk/configs/models/city_finance.yaml`
- `/home/user/de_Funk/configs/models/company.yaml` (DEPRECATED)
- `/home/user/de_Funk/configs/models/equity.yaml`
- `/home/user/de_Funk/configs/models/corporate.yaml`
- `/home/user/de_Funk/configs/models/etf.yaml`
- `/home/user/de_Funk/configs/models/forecast.yaml`

---

## Appendix B: Edge Syntax Reference

### Within-Model Edge
```yaml
- from: fact_table
  to: dim_table
  on: ["column=column"]
  type: many_to_one
```

### Cross-Model Edge
```yaml
- from: fact_table
  to: other_model.dim_table
  on: ["column=column"]
  type: many_to_one
  description: "Cross-model relationship description"
```

### Cross-Model Measure
```yaml
measure_name:
  type: weighted
  source: other_model.fact_table.column
  description: "Uses data from another model"
```
