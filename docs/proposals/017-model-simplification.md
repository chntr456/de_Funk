# Proposal 017 — Model Layer Simplification

**Date**: 2026-03-20
**Status**: Draft
**Depends on**: Proposal 016 (API consolidation)
**Priority**: High — BaseModel exceeds 800-line limit, 1,600 lines of dead query code

## Problem

The models layer accumulated three eras of architecture:

1. **v1-v2**: Heavy Python model classes with build + query methods (StocksModel, CompanyModel)
2. **v3-v4**: Config-driven DomainModel reads markdown frontmatter, builds Silver generically
3. **FastAPI era**: FieldResolver replaced all model query methods with field-level resolution

The result:
- **BaseModel is 956 lines** — a god class mixing build logic, dead query methods, backend branching, and delegation wrappers
- **~1,600 lines of dead query methods** across 5 domain model classes — FieldResolver made them obsolete
- **98 instances of `if self.backend == 'spark'/'duckdb'`** across 17 files — BackendAdapter exists but isn't used
- **5 custom model classes** when only 2 have live build hooks
- **3 files exceed the 800-line limit** (BaseModel 956, DomainModel 815, UniversalSession 1085)

## What's Dead vs Alive

### Dead (query-era code, FieldResolver replaced it)

**BaseModel dead methods:**
- `get_denormalized()` — 210 lines of inline join code
- `calculate_measure()`, `calculate_measure_by_entity()` — measure delegation
- `get_fk_relationships()`, `get_relations()`, `get_metadata()` — introspection
- `measures`, `query_planner`, `python_measures` properties — lazy-loaded dead code
- `_parse_join_conditions()`, `_detect_backend()` — utilities for deleted methods

**Dead domain model classes:**

| Model | Lines | Live Hooks | Query Methods (all dead) |
|-------|-------|-----------|-------------------------|
| StocksModel | 324 | None | get_prices, get_technicals, get_stock_info, list_tickers, etc. (11 methods) |
| SecuritiesModel | 233 | None | get_security, get_securities_by_type, list_exchanges, etc. (9 methods) |
| CityFinanceModel | 407 | None (no builder either) | get_local_unemployment, get_building_permits, etc. (10 methods) |
| CompanyModel | 212 | `after_build()` (CIK enrichment) | get_company_by_cik, list_sectors, etc. (6 dead methods) |
| TemporalModel | 457 | `custom_node_loading()` + `_generate_calendar*()` | get_calendar, get_weekdays, etc. (8 dead methods) |

**Dead composition classes:**
- `TableAccessor` (396 lines) — only caller is UniversalSession (being deleted in 016)
- `MeasureCalculator` (278 lines) — only called by dead BaseModel.calculate_measure()

### Alive (build pipeline, runs weekly)

- `BaseModel.__init__`, `build()`, `ensure_built()`, `before_build()`, `after_build()`
- `DomainModel.custom_node_loading()` — handles seed/union/distinct/window/unpivot nodes
- `GraphBuilder._build_nodes()` — loads Bronze, applies transforms, writes Silver
- `ModelWriter.write_tables()` — Delta Lake persistence
- `CompanyModel.after_build()` — CIK→ticker FK enrichment
- `TemporalModel._generate_calendar*()` — programmatic dim_calendar generation
- `StocksBuilder.post_build()` — technical indicator computation
- `ForecastBuilder.build()` — ML model training

## Proposed Changes

### Phase 1: Delete dead query code from BaseModel (956 → ~350 lines)

Remove ~600 lines:
- `get_denormalized()` and `_parse_join_conditions()` — 210+ lines
- `calculate_measure()`, `calculate_measure_by_entity()` — 30 lines + MeasureCalculator
- `get_fk_relationships()`, `get_relations()`, `get_metadata()` — 50 lines
- `measures`, `query_planner`, `python_measures` properties — 60 lines
- `_build_window_node()` — duplicate of DomainModel's version

Keep in BaseModel:
- `__init__`, `set_session`, `backend` property
- `build()`, `ensure_built()`, `before_build()`, `after_build()`
- `custom_node_loading()` — dispatches to subclass overrides
- `write_tables()` — delegates to ModelWriter
- `get_table()`, `has_table()`, `list_tables()` — used by build hooks internally
- `get_table_schema()` — used by config translator

### Phase 2: Delete dead domain model classes

| File | Action |
|------|--------|
| `models/domains/securities/stocks/model.py` | DELETE (StocksModel — no live hooks) |
| `models/domains/securities/securities/model.py` | DELETE (SecuritiesModel — no live hooks) |
| `models/domains/municipal/city_finance/` | DELETE entire directory |
| `models/domains/corporate/company/model.py` | Strip to after_build() only (~60 lines) |
| `models/domains/foundation/temporal/model.py` | Strip to calendar generation only (~210 lines) |
| `models/base/domain_builder.py` | Remove StocksModel from CUSTOM_MODEL_CLASSES |

After deletion, `CUSTOM_MODEL_CLASSES` shrinks to:
```python
CUSTOM_MODEL_CLASSES = {
    "temporal": ("...temporal.model", "TemporalModel"),
    "corporate.entity": ("...company.model", "CompanyModel"),
}
```

All other models use generic `DomainModel` (config-driven, no custom Python).

### Phase 3: Deprecate TableAccessor and MeasureCalculator

- Inline the 3 surviving methods from `TableAccessor` (get_table, has_table, list_tables) into BaseModel — they're trivial dict lookups on `self._dims` and `self._facts`
- Add `warnings.warn("deprecated")` to TableAccessor and MeasureCalculator
- Full deletion deferred to 018 (after confirming no notebook/script callers)

### Phase 4: Extract BackendOps

Create `models/base/backend/ops.py`:

```python
class BackendOps:
    """Backend-agnostic DataFrame operations for build pipeline."""

    def __init__(self, connection, backend_type: str):
        self.connection = connection
        self.backend = backend_type

    def select_columns(self, df, select_config: dict) -> Any: ...
    def apply_filters(self, df, filters: list) -> Any: ...
    def apply_derive(self, df, col_name: str, expr: str) -> Any: ...
    def union_dataframes(self, dfs: list) -> Any: ...
    def drop_duplicates(self, df, subset: list) -> Any: ...
    def create_empty_df(self, columns: list) -> Any: ...
    def read_delta_or_parquet(self, path: str) -> Any: ...
    def join(self, left, right, on: list, how: str = 'left') -> Any: ...
    def with_column(self, df, name: str, expr) -> Any: ...
    def count(self, df) -> int: ...
```

Migrate 13 backend branches from BaseModel + GraphBuilder to BackendOps calls. Each method is a direct extract of the existing if/else block — no logic changes.

## Future (018): Plugin Architecture + Full Rollout

Deferred:
- `BuildPluginRegistry` — hook registration by (hook_type, model_name)
- Extract temporal calendar, CIK enrichment to plugin files
- Roll out BackendOps to DomainModel (7 branches) and remaining 78 branches
- Delete TableAccessor and MeasureCalculator (after deprecation period)

## Impact

| Metric | Before | After 017 |
|--------|--------|-----------|
| BaseModel lines | 956 | ~350 |
| Dead query code | ~1,600 lines | 0 |
| Domain model classes | 5 | 2 (hooks only) |
| Backend if/else branches | 98 | ~75 |
| Files over 800 lines | 3 | 1 (DomainModel) |
| Total lines removed | — | ~2,500 |

## Risks

1. **Dead code not actually dead** — Mitigated: Phase 3 adds deprecation warnings before deletion
2. **BackendOps breaks build pipeline** — Mitigated: mechanical refactoring, run full build end-to-end
3. **Removing CUSTOM_MODEL_CLASSES entry** — Safe: DomainBuilderFactory falls back to DomainModel

## Decisions Needed

1. Should StocksBuilder.post_build() (technicals) stay in the builder, or should `securities.stocks` use DomainModel's `_transform: window` for indicators instead?
2. Should ForecastModel/TimeSeriesForecastModel be simplified, or is the ML training pattern fundamentally different enough to keep as-is?
