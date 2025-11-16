# de_Funk UI & Application Layer - Executive Summary

## Quick Overview

**de_Funk** is a professional **analytics platform** built on Streamlit that enables users to explore dimensional data models through interactive markdown-based notebooks. The system implements a clean layered architecture with two main data flows:

1. **ETL Pipeline** (API → Bronze → Silver → Storage)
2. **UI Pipeline** (Filters → Queries → Exhibits → Browser)

---

## Key Architectural Components

### 1. Streamlit UI Layer (`app/ui/`)
- **Entry point:** `notebook_app_duckdb.py` (300+ lines)
- **Responsibilities:** Page layout, tab management, session state
- **Backend:** DuckDB (10-100x faster than Spark)

### 2. Notebook System (`app/notebook/`)
- **Markdown Parser:** Extracts YAML front matter, filters, exhibits from `.md` files
- **Notebook Manager:** Lifecycle management, state, filter context
- **Filter System:** 6 filter types (date_range, multi_select, select, slider, text, number)
- **Exhibits:** 7 visualization types (metric_cards, line_chart, bar_chart, data_table, forecast, weighted_aggregate, etc.)

### 3. Data Access Layer (`models/api/`)
- **UniversalSession:** Cross-model queries with auto-join and aggregation
- **Model Registry:** Dynamic model discovery from YAML configs
- **Model Graph:** Relationship mapping for auto-joins

### 4. Storage Layer (`storage/`)
- **Bronze:** Raw API data (Parquet, partitioned)
- **Silver:** Dimensional models (Parquet, partitioned)
- **DuckDB Catalog:** Metadata & query workspace (doesn't duplicate data)

### 5. Orchestration (`orchestration/` + 27 scripts)
- **Main pipeline:** `run_full_pipeline.py` (API → ETL → UI)
- **Build scripts:** `build_all_models.py`, `rebuild_model.py`
- **Test scripts:** E2E, integration, unit tests
- **Utility scripts:** Migration, validation, verification

---

## How Data Flows (User Perspective)

```
1. User opens notebook
   ↓
2. MarkdownNotebookParser extracts filters and exhibits
   ↓
3. User adjusts filters in sidebar
   ↓
4. Streamlit re-runs app
   ↓
5. For each exhibit:
   a. Load data: session.get_table("model", "table")
   b. Apply filters: FilterEngine.apply_filters(df, context)
   c. Render selectors: measure_selector, dimension_selector
   d. Create Plotly figure
   e. Display in browser
   ↓
6. User interacts with chart (hover, zoom, etc.)
```

---

## Strengths ✅

1. **Clean Architecture** - Excellent separation of concerns
2. **Flexible** - Backend-agnostic (DuckDB, Spark), model-agnostic
3. **Type-Safe** - Dataclass models, type hints throughout
4. **User-Friendly** - Markdown-based notebooks, no-code filter definitions
5. **Well-Documented** - CLAUDE.md is comprehensive
6. **Performance** - DuckDB with smart caching and filter pushdown
7. **Professional UI** - Modern Streamlit with Plotly visualizations

---

## Key Complexity Areas ⚠️

### 1. **Exhibit Logic is Split** (Medium Priority)
- **Problem:** Exhibit rendering split between two modules
  - `app/notebook/exhibits/` - mostly empty stubs
  - `app/ui/components/exhibits/` - actual rendering logic
- **Impact:** Confusing for contributors; hard to find where logic lives
- **Fix:** Consolidate into single `app/notebook/exhibits/` module (2-3 days)

### 2. **Filters Module Fragmented** (Low Priority)
- **Problem:** Filters split across 4 files
  - `filters/context.py` - FilterContext
  - `filters/dynamic.py` - FilterConfig types
  - `filters/engine.py` - FilterEngine
  - `filters/types.py` - FilterOperator
- **Impact:** Simple concept spread across multiple files
- **Fix:** Consolidate to 2 focused files (1 day)

### 3. **27 Operational Scripts** (Medium Priority)
- **Problem:** 27 scripts in `/scripts/` directory with mixed concerns
- **Impact:** Hard to discover available commands; difficult to maintain
- **Fix:** Create CLI tool with subcommands (3-5 days)
  ```bash
  python -m de_funk build --model equity
  python -m de_funk test --suite integration
  python -m de_funk ingest --source polygon
  ```

### 4. **Large Monolithic Files** (Low Priority)
- `schema.py` - 350+ lines (should be split 3 ways)
- `build_all_models.py` - 600+ lines
- `test_pipeline_e2e.py` - 600+ lines

### 5. **Session/Context Abstraction** (Medium Priority)
- **Problem:** Multiple "session" concepts
  - `RepoContext` - config + connection
  - `UniversalSession` - model access
  - `FilterContext` - filter state
- **Impact:** Unclear which to use when
- **Fix:** Document clearly or consolidate (2-3 days)

---

## Quick Wins (Easy, High Value)

| Task | Effort | Value | Impact |
|------|--------|-------|--------|
| Consolidate exhibits | 2-3 days | High | Clarity + Maintainability |
| Clean up filters | 1 day | High | Discoverability |
| Remove dead code | 1 day | Medium | Cleanliness |
| Split schema.py | 2 days | High | Readability |

**Total: 6-7 days of work → Significant improvement**

---

## For New Contributors

**Start here:**
1. Read `CLAUDE.md` for project overview
2. Explore example notebooks in `configs/notebooks/`
3. Read `notebook_app_duckdb.py` to understand app structure
4. Look at `NotebookManager` to understand notebook lifecycle
5. Check `UniversalSession` for data access patterns

**Key files to understand (in order):**
1. `app/ui/notebook_app_duckdb.py` - App entry point
2. `app/notebook/managers/notebook_manager.py` - Notebook lifecycle
3. `app/notebook/parsers/markdown_parser.py` - Parsing logic
4. `models/api/session.py` - Data access
5. `core/context.py` - Configuration

---

## Technical Debt Summary

| Item | Severity | Effort | Risk |
|------|----------|--------|------|
| Exhibit logic split | Medium | 2-3d | Low |
| Filters fragmented | Low | 1d | Low |
| 27 scripts | Medium | 3-5d | Low |
| Monolithic files | Low | 2d | Low |
| Dead code | Low | 1d | Low |
| Session abstraction | Medium | 2-3d | Low |
| **Total** | | **11-16 days** | **Low Risk** |

All improvements are **incremental, low-risk refactoring** that improve maintainability without architectural changes.

---

## Model Dependencies (FYI)

```
Tier 0: core (calendar)
         ↓
Tier 1: equity, corporate, macro
         ↓
Tier 2: etf, forecast
         ↓
Tier 3: city_finance
```

---

## Recommendations

**Immediate (Next Sprint):**
1. Consolidate exhibit renderers (**2-3 days**)
2. Remove unused services + dead code (**1 day**)
3. Document session/context layers (**1 day**)

**Short-term (Next 2-3 Sprints):**
1. Create CLI tool (**3-5 days**)
2. Split schema.py (**2 days**)
3. Clean up filters module (**1 day**)

**Long-term:**
1. Refactor session abstraction (if needed)
2. Add exhibit type registry for plugins
3. Create notebook versioning system

---

## File Locations Reference

| Component | Files |
|-----------|-------|
| **App Entry** | `run_app.py`, `app/ui/notebook_app_duckdb.py` |
| **Notebooks** | `app/notebook/` (parsers, managers, filters, exhibits) |
| **UI Components** | `app/ui/components/` (sidebar, filters, exhibits) |
| **Models** | `models/` (base, api, implemented) |
| **Storage** | `storage/bronze/`, `storage/silver/`, `storage/duckdb/` |
| **Config** | `configs/models/*.yaml`, `config/loader.py` |
| **Scripts** | `scripts/` (27 scripts), `run_full_pipeline.py` |
| **Tests** | `tests/unit/`, `tests/integration/` |

---

## Full Analysis Document

See `UI_APP_ANALYSIS.md` (1300+ lines) for comprehensive details including:
- Complete architecture diagrams
- Detailed data flow documentation
- Code examples
- Integration point analysis
- Performance considerations
- User interaction flows
- Technical debt audit
