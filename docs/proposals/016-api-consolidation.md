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
| Aggregation engine (GROUP BY) | `aggregation.py` | None | No server-side aggregation in FastAPI |
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

## Decisions needed

1. **Confirm Phase 1-4 ordering** — or should we do Phase 4 (delete dead code) first to reduce noise?
2. **Event loop scope** — full reconciler, or just dedup + throttle as a first pass?
3. **Aggregation priority** — is server-side GROUP BY needed now, or can exhibits continue with raw data?
