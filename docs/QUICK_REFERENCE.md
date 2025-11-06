# De_Funk Codebase - Quick Reference Guide

## Session Systems at a Glance

### The Three Systems (All Present)

| Aspect | ModelSession | UniversalSession | NotebookSession |
|--------|--------------|------------------|-----------------|
| **Location** | models/api/session.py:15-98 | models/api/session.py:104-268 | app/notebook/api/notebook_session.py |
| **Backend** | Spark only | Spark (extensible to DuckDB) | DuckDB |
| **Models** | CompanyModel only | Multi-model via registry | Any model via registry |
| **Status** | DEPRECATED | RECOMMENDED | REFACTORING |
| **Used by** | streamlit_app.py, Services | Scripts (build_silver, forecasts) | notebook_app_duckdb.py |
| **Lines** | 84 | 164 | 450+ |

### Consolidation Target: UniversalSession

**Why:** Multi-model, connection-agnostic, registry-driven design
**How:** Extract NotebookSession (→ NotebookManager), deprecate ModelSession, unify services
**Timeline:** 4 weeks (phases 1-4)

---

## Critical Files

### Core Session Files
```
/home/user/de_Funk/models/api/session.py (270 lines)
  - ModelSession (lines 15-98) [DEPRECATED]
  - UniversalSession (lines 104-268) [TARGET]

/home/user/de_Funk/app/notebook/api/notebook_session.py (450 lines)
  - Mix of parsing + data access [REFACTOR to NotebookManager]
```

### Service APIs
```
/home/user/de_Funk/models/base/service.py (85 lines)
  - BaseAPI (abstract class)
  - Compatibility shims [REMOVE in Phase 2]

/home/user/de_Funk/models/implemented/company/services/
  - prices_api.py
  - news_api.py
  - company_api.py
```

### UI Applications
```
/home/user/de_Funk/app/ui/streamlit_app.py
  - Uses ModelSession [MIGRATE to UniversalSession in Phase 3]

/home/user/de_Funk/app/ui/notebook_app_duckdb.py
  - Uses NotebookSession [UPDATE to NotebookManager + UniversalSession in Phase 3]
```

### Notebook Infrastructure
```
/home/user/de_Funk/app/notebook/
  ├── schema.py              # Type definitions
  ├── parser.py              # YAML parser
  ├── markdown_parser.py     # Markdown parser
  ├── filters/
  │   ├── context.py         # FilterContext
  │   └── dynamic.py         # FilterConfig types
  └── exhibits/              # Visualization rendering
```

---

## Key Data Structures

### Notebooks (YAML or Markdown)

**Front Matter (All Formats):**
```yaml
id: notebook_id
title: Notebook Title
description: ...
tags: [stocks, analysis]
models: [company, forecast]
author: analyst@company.com
```

**Filters (Variables):**
```python
Variable(
    id='trade_date',
    type=VariableType.DATE_RANGE,
    display_name='Date Range',
    default={'start': '2024-01-01', 'end': '2024-01-05'}
)
```

**Exhibits (Visualizations):**
```python
Exhibit(
    id='price_chart',
    type=ExhibitType.LINE_CHART,
    title='Daily Prices',
    source='company.fact_prices',
    filters={'ticker': ['AAPL', 'GOOGL']}
)
```

### Filter Types

**Old (VariableType):**
DATE_RANGE, MULTI_SELECT, SINGLE_SELECT, NUMBER, TEXT, BOOLEAN

**New (FilterType):**
DATE_RANGE, SELECT, NUMBER_RANGE, TEXT_SEARCH, SLIDER, BOOLEAN

---

## Architecture Layers

```
┌─────────────────────────────────────────┐
│  UI Layer (Streamlit)                   │
│  - streamlit_app.py (Spark)             │
│  - notebook_app_duckdb.py (DuckDB)      │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Business Logic Layer                   │
│  - NotebookManager (parsing + rendering)│
│  - Service APIs (PricesAPI, etc.)       │
│  - Storage Service (deprecated)         │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Data Access Layer (THE TARGET)         │
│  - UniversalSession                     │
│    • Multi-model support                │
│    • Registry integration               │
│    • Filter application                 │
│    • Caching                            │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Connection Layer                       │
│  - DataConnection (abstract)            │
│  - SparkConnection                      │
│  - DuckDBConnection                     │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Storage Layer                          │
│  - Bronze (raw: /storage/bronze/)       │
│  - Silver (processed: /storage/silver/) │
│  - DuckDB (views: /storage/duckdb/)     │
└─────────────────────────────────────────┘
```

---

## Consolidation Phases

### Phase 1: Foundation (Week 1) - DONE ✅
- Enhance UniversalSession
- Add DuckDB support
- Create test suite

**Status:** Complete per consolidation plan

### Phase 2: Services (Week 2) - READY
- Update BaseAPI (remove shims)
- Update PricesAPI, NewsAPI, CompanyAPI
- Test services

**Effort:** 2-3 days

### Phase 3: UI (Week 3) - READY
- Create NotebookManager
- Migrate streamlit_app.py
- Migrate notebook_app_duckdb.py
- Test both UIs

**Effort:** 2-3 days each

### Phase 4: Cleanup (Week 4) - READY
- Deprecate ModelSession
- Remove compatibility shims
- Document changes
- Performance testing

**Effort:** 1-2 days

---

## Issues Confirmed ✅

### Issue 1: API Inconsistency
```python
# Problem:
ModelSession.get_dimension_df(model_name, node_name)
UniversalSession.get_dimension_df(model_name, dim_id)  # Different params!
NotebookSession.storage_service.get_table(...)        # Different API!

# Solution: Use UniversalSession API everywhere
session.get_table(model_name, table_name)
```

### Issue 2: Backend Incompatibility
```python
# Problem:
ModelSession → pyspark.sql.DataFrame (manual filtering)
NotebookSession → duckdb.DuckDBPyRelation (SQL filtering)

# Solution: Abstract in UniversalSession + DataConnection
```

### Issue 3: Duplicate Filter Logic (3 places!)
```
1. models/base/service.py:54-84         (BaseAPI._apply_filters)
2. app/notebook/api/notebook_session.py:180-250 (_build_filters)
3. app/services/storage_service.py:80-120      (filter application)

→ Consolidate into UniversalSession
```

### Issue 4: Mixed Concerns in NotebookSession
```python
NotebookSession = Parser + DataAccess + Filter Management
                  ↓       ↓            ↓
NotebookManager + UniversalSession + FilterContext
```

---

## File Modification Checklist

### P0 (Critical) - Phase 1-2
- [ ] `models/api/session.py` - Enhance UniversalSession
- [ ] `models/base/service.py` - Remove compatibility shims

### P1 (High) - Phase 3
- [ ] `app/ui/streamlit_app.py` - Migrate to UniversalSession
- [ ] `app/ui/notebook_app_duckdb.py` - Use NotebookManager + UniversalSession
- [ ] `app/notebook/api/notebook_session.py` - Refactor to NotebookManager (NEW FILE)
- [ ] Service APIs (3 files) - Update for UniversalSession

### P2 (Medium) - Phase 3-4
- [ ] `app/services/storage_service.py` - Deprecate/refactor
- [ ] `docs/` - Update all documentation
- [ ] Create tests for new architecture

---

## Quick Validation Checklist

Before implementing, confirm:

- [ ] UniversalSession is the right foundation (multi-model, registry-driven)
- [ ] Both Spark and DuckDB connections work
- [ ] NotebookSession's filter logic is well understood
- [ ] All service APIs use BaseAPI
- [ ] Both UIs have integration tests
- [ ] No external dependencies on ModelSession
- [ ] Phase-based approach acceptable to stakeholders
- [ ] Performance targets achievable (DuckDB available)

---

## Key Commands

### Run Old UI (Spark)
```bash
streamlit run app/ui/streamlit_app.py
```

### Run New UI (DuckDB)
```bash
streamlit run app/ui/notebook_app_duckdb.py
```

### View Notebooks
Located: `/configs/notebooks/`
- stock_analysis.md
- forecast_analysis.md
- aggregate_stock_analysis.md
- stock_analysis_dynamic.md

### Build Data
```bash
python run_full_pipeline.py          # Full pipeline
python scripts/build_silver_layer.py # Just silver layer
```

---

## Documentation Files Generated

1. **CODEBASE_ARCHITECTURE_ANALYSIS.md** (1015 lines)
   - Comprehensive architecture analysis
   - All 12 detailed sections
   - Complete type hierarchies
   - Data flow diagrams

2. **CONSOLIDATION_VALIDATION_CHECKLIST.md** (540 lines)
   - Validation against plan
   - All 12 sections confirmed
   - Ready for implementation
   - Recommendations by phase

3. **QUICK_REFERENCE.md** (This file)
   - One-page summary
   - Critical files
   - Quick lookup tables
   - Phase checklist

---

## Summary

**What:** Consolidate 3 session systems → 1 (UniversalSession)
**Why:** Reduce duplication, support both Spark & DuckDB, simplify services
**How:** Phased approach (4 weeks, 4 phases)
**Status:** READY FOR IMPLEMENTATION
**Risk:** Medium (well-mitigated)
**Effort:** 5-7 weeks

**Next Step:** Start Phase 1 - strengthen UniversalSession foundation

---

**Generated:** 2025-11-06
**Plan Version:** 1.0
**Status:** Ready to Execute
