# Proposal 016 — API Layer Consolidation

**Date**: 2026-03-19
**Status**: Draft
**Priority**: High — blocks all vertical completion work

## Problem

de_Funk has three query/API layers built across multiple sessions, each reimplementing overlapping capabilities:

| Layer | Location | Built For | Status |
|-------|----------|-----------|--------|
| **models/api/** | `src/de_funk/models/api/` | Original Spark+DuckDB interactive queries | Partially dead, partially load-bearing |
| **notebook/** | `src/de_funk/notebook/` | Streamlit notebook rendering | Dead (Streamlit removed) |
| **api/** (FastAPI) | `src/de_funk/api/` | Obsidian plugin REST queries | Active, incomplete |

This happened because each Claude session solved the immediate ask without checking what already existed. The result is ~3,500 lines of overlapping code with no single authoritative query path.

## Capability Audit

### What models/api/ has that FastAPI doesn't

| Capability | Old Module | FastAPI Equivalent | Gap |
|-----------|-----------|-------------------|-----|
| Dynamic join planning at query time | `auto_join.py` | Static join graph built at startup | Cannot request arbitrary cross-table columns |
| Universal date filter translation | `auto_join.py` | None | `forecast_date` → `trade_date` mapping lost |
| Generic aggregation engine | `aggregation.py` | Per-handler GROUP BY in graphical, pivot, metric, table_data | Aggregation exists but is duplicated across handlers rather than centralized |
| Materialized view detection | `query_planner.py` | None | Cannot skip joins when pre-computed view exists |
| Cross-model filter validation | `session.py` | Partial (domain deps in resolver) | Static, not dynamic |
| Backend-agnostic helpers (16 methods) | `session.py` | DuckDB only | No Spark query support |
| Model loading + caching | `session.py` | None | FastAPI is field-based, not model-based |
| Graph metrics + visualization | `graph.py` | None | No introspection API |

### What FastAPI has that models/api/ doesn't

| Capability | FastAPI Module | Notes |
|-----------|---------------|-------|
| Bronze layer queries | `bronze_resolver.py`, `bronze_router.py` | Direct API-endpoint queries over raw data |
| Exhibit-type handlers | `handlers/` | Typed response formats (pivot HTML, chart series, metric cards) |
| REST API with validation | `routers/`, Pydantic models | HTTP interface for Obsidian plugin |
| Field-level resolution | `resolver.py` | `domain.model.field` → `table.column` with BFS joins |
| Domain catalog endpoint | `routers/domains.py` | Lists available domains and fields |
| Dimension values endpoint | `routers/dimensions.py` | Distinct values for filter pickers |

### What's load-bearing in models/api/ (cannot delete yet)

| Module | Used By | Why |
|--------|---------|-----|
| `dal.py` → `StorageRouter` | `BaseModel.__init__()` | Path resolution for Silver builds |
| `query_planner.py` → `GraphQueryPlanner` | `BaseModel.query_planner` | Offline model enrichment queries |
| `session.py` → `UniversalSession` | Domain API classes | Cross-model access for Spark builds |
| `graph.py` → `ModelGraph` | `DependencyGraph` | Build ordering (topological sort) |

### What's dead (safe to delete)

| Module | Reason |
|--------|--------|
| `notebook/managers/` | Deleted this session |
| `notebook/api/notebook_session.py` | Streamlit-only |
| `services/notebook_service.py` | Deleted this session |
| `aggregation.py` (if not imported) | Only used by UniversalSession.get_table() |
| `auto_join.py` (if not imported) | Only used by UniversalSession.get_table() |

## Proposed Architecture

### Target: One query path, two entry points

```
                  ┌──────────────┐     ┌──────────────┐
                  │  FastAPI     │     │  Spark Build  │
                  │  (REST)      │     │  (Offline)    │
                  └──────┬───────┘     └──────┬────────┘
                         │                     │
                         ▼                     ▼
                  ┌──────────────────────────────────────┐
                  │         Semantic Query Layer          │
                  │                                      │
                  │  FieldResolver  — field → table.col  │
                  │  JoinPlanner    — BFS join paths      │
                  │  FilterEngine   — universal filters   │
                  │  Aggregator     — GROUP BY + measures │
                  │  StorageRouter  — path resolution     │
                  └──────────┬───────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
              ┌──────────┐     ┌──────────┐
              │  DuckDB   │     │  Spark   │
              │  (query)  │     │  (build) │
              └──────────┘     └──────────┘
```

### Migration steps

#### Phase 1: Extract shared core (no behavior change)

Move load-bearing pieces out of `models/api/` into a new `core/query/` layer:

```
src/de_funk/core/query/
├── resolver.py        ← merge FastAPI FieldResolver + models/api graph resolution
├── join_planner.py    ← extract from auto_join.py + query_planner.py
├── filter_engine.py   ← already exists in core/session/filters.py
├── aggregator.py      ← extract from aggregation.py
├── storage.py         ← extract StorageRouter from dal.py
└── session.py         ← thin wrapper: DuckDB or Spark backend
```

**Key rule**: `core/query/` has zero imports from `api/`, `models/`, or `notebook/`. Everything imports from it.

#### Phase 2: Rewire FastAPI to use core/query/

Replace `api/resolver.py` and `api/executor.py` with calls to `core/query/`. This adds:
- Server-side aggregation (currently missing)
- Dynamic join planning (currently static)
- Universal date filter translation (currently missing)

#### Phase 3: Rewire BaseModel to use core/query/

Replace `BaseModel`'s imports from `models/api/dal.py` and `models/api/query_planner.py` with `core/query/storage.py` and `core/query/join_planner.py`.

#### Phase 4: Delete dead code

Remove entire directories:
- `src/de_funk/models/api/` (all functionality moved to core/query/)
- `src/de_funk/notebook/` (Streamlit dead, parsers unused)
- `src/de_funk/services/` (notebook_service already deleted)

## Event-Driven Rendering (replaces TUI proposal)

The plugin's filter → re-render pipeline currently has no batching or reconciliation, causing 30+ duplicate queries per filter change. Instead of building a TUI, invest in a proper event loop:

```
Event Loop (single tick = 16ms frame):
  1. Collect      — gather all events (filter change, control toggle, data ready)
  2. Deduplicate  — merge identical events within tick
  3. Diff         — compare new state vs old, determine dirty exhibits
  4. Schedule     — batch API calls, prioritize visible exhibits
  5. Render       — update only changed DOM elements
```

This architecture:
- Fixes the 30-query storm problem
- Eliminates progressive slowdown (DuckDB memory pressure from duplicate scans)
- Serves as foundation for any future frontend (web, desktop, or terminal)
- Lives in the plugin as a TypeScript state manager, not a Python-side concern

## What this unlocks

| Blocked Feature | Why It's Blocked | Unblocked By |
|----------------|-----------------|-------------|
| Server-side aggregation | No aggregator in FastAPI | Phase 2 (aggregator in core) |
| Dynamic cross-domain joins | Static resolver graph | Phase 2 (join planner in core) |
| Date filter universality | No translation layer | Phase 2 (filter engine in core) |
| Spark-backed queries via API | DuckDB-only executor | Phase 3 (backend-agnostic session) |
| Safe deletion of 2,000+ dead lines | Load-bearing imports | Phase 4 (all rewired) |
| Responsive filter interactions | No event batching | Event loop (plugin) |

## Effort and risk

| Phase | Scope | Risk |
|-------|-------|------|
| Phase 1 | Extract + move, no behavior change | Low — pure refactor |
| Phase 2 | Rewire FastAPI handlers | Medium — regression risk on exhibits |
| Phase 3 | Rewire BaseModel | Medium — build pipeline regression |
| Phase 4 | Delete dead code | Low — if phases 1-3 pass tests |
| Event loop | Plugin TypeScript refactor | Medium — requires careful testing |

## Appendix: Malloy as an alternative query engine

During this review, we evaluated whether [Malloy](https://github.com/malloydata/malloy) (Google-backed semantic query language over DuckDB) would have been a better foundation for the query layer than custom Python+SQL.

### What Malloy provides natively that de_Funk rebuilt

| Capability | de_Funk (custom) | Malloy (built-in) |
|-----------|-----------------|-------------------|
| Field resolution | `FieldResolver` — BFS over join graph (~300 lines) | Implicit — declare `source` with joins, fields resolve automatically |
| Auto-joins | Static graph built at startup | Declared in source definition, executed at query time |
| Measures/dimensions | YAML frontmatter + custom SQL generation | First-class constructs (`measure:`, `dimension:`) |
| Nested queries | Not supported | Core feature — queries within queries |
| Aggregation | Implemented per-handler (graphical, pivot, metric, table_data) | Built into every query, centralized |
| Filtering | Custom filter engine | `where:` clause with type safety |
| Reusable definitions | Markdown domain configs | `.malloy` source files with `extend` |

### Example — same query in both

```
-- de_Funk: FieldResolver resolves fields, handler builds SQL
POST /api/query
{
  "type": "plotly.bar",
  "x": "corporate.entity.sector",
  "y": "securities.stocks.adjusted_close",
  "aggregation": "avg"
}
-- Internally generates:
SELECT dim_company.sector, AVG(fact_stock_prices.adjusted_close)
FROM fact_stock_prices
JOIN dim_stock ON ... JOIN dim_company ON ...
GROUP BY dim_company.sector
```

```malloy
-- Malloy: the language handles resolution, joins, and aggregation
source: stocks is duckdb.table('fact_stock_prices')
  extend {
    join_one: company is duckdb.table('dim_company') on ticker = company.ticker
    measure: avg_close is adjusted_close.avg()
    dimension: sector is company.sector
  }

run: stocks -> {
  group_by: sector
  aggregate: avg_close
}
```

### Where Malloy would have been better

- **Less custom code.** `FieldResolver`, `auto_join`, `query_planner` are reimplementations of what Malloy does natively. The per-handler aggregation duplication (graphical, pivot, metric each building their own GROUP BY SQL) would be replaced by a single query language
- **Type-safe queries.** Errors caught at parse time, not at SQL execution
- **Nested queries.** "Average close by sector, then for each sector show top 5 stocks" — requires multiple API calls in de_Funk, one query in Malloy
- **Composability.** Malloy sources extend each other naturally, similar to domain `extends:` but with query-time semantics

### Where Malloy would have been worse

- **Markdown-as-config dies.** Malloy uses `.malloy` files. The YAML frontmatter → query pipeline that makes domain configs simultaneously browsable documentation would need a translation layer (markdown → .malloy codegen)
- **Bronze layer doesn't fit.** Malloy expects tables, not API endpoints. The Bronze resolver that queries raw Socrata/Alpha Vantage data has no Malloy equivalent
- **Obsidian integration is harder.** Exhibit YAML → Malloy query → Malloy result → chart series. Two translation layers instead of one
- **Build pipeline is separate.** Malloy is query-only. Bronze → Silver ETL still needs Spark/DuckDB directly
- **Young ecosystem.** Google-backed but still pre-1.0. Limited community, breaking changes likely

### Assessment

If de_Funk were only a query tool over Silver tables, Malloy would have saved significant effort. The custom field resolution + join planning + per-handler aggregation stack is a less capable version of what Malloy does natively.

But de_Funk's value is the **markdown config → build pipeline → query → visualization** full loop. Malloy replaces one piece (query) while making the others harder (config format, Bronze, Obsidian integration).

### Recommendation

Don't adopt Malloy wholesale, but **use its semantics as the design target** for the `core/query/` consolidation:

1. **Declarative joins** — define join relationships once in domain config, resolve at query time (like Malloy `source extend { join_one: ... }`)
2. **First-class measures** — measures defined in YAML should translate to aggregation expressions centrally, not per-handler (like Malloy `measure:`)
3. **Composable sources** — domain `extends:` should work at query time, not just build time (like Malloy `extend`)
4. **Nested queries** — consider supporting sub-queries in exhibit definitions for drill-down analytics

This gives de_Funk Malloy-level query semantics while preserving the markdown-as-config architecture that makes the project unique.

---

## Decisions needed

1. **Confirm Phase 1-4 ordering** — or should we do Phase 4 (delete dead code) first to reduce noise?
2. **Event loop scope** — full reconciler, or just dedup + throttle as a first pass?
3. **Aggregation centralization** — should the per-handler GROUP BY logic be extracted into a shared aggregator in `core/query/`?
4. **Malloy semantics** — should `core/query/` target Malloy-style declarative joins and first-class measures, or keep the current pattern?
