---
title: "API Layer"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/api/handlers/base.py
  - src/de_funk/api/handlers/box.py
  - src/de_funk/api/handlers/formatting.py
  - src/de_funk/api/handlers/graphical.py
  - src/de_funk/api/handlers/gt_formatter.py
  - src/de_funk/api/handlers/metrics.py
  - src/de_funk/api/handlers/pivot.py
  - src/de_funk/api/handlers/reshape.py
  - src/de_funk/api/handlers/table_data.py
  - src/de_funk/api/models/requests.py
  - src/de_funk/api/routers/bronze.py
  - src/de_funk/api/routers/dimensions.py
  - src/de_funk/api/routers/domains.py
  - src/de_funk/api/routers/health.py
  - src/de_funk/api/routers/models.py
  - src/de_funk/api/routers/predict.py
  - src/de_funk/api/routers/query.py
  - src/de_funk/api/main.py
---

# API Layer

> FastAPI routers, exhibit handlers, and pydantic request/response models — the Obsidian connection point.

## Purpose & Design Decisions

### What Problem This Solves

<!-- TODO: Explain the problem this group addresses. -->

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| <!-- TODO --> | | |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| <!-- TODO --> | | |

## Architecture

### Where This Fits

```
[Upstream] --> [THIS GROUP] --> [Downstream]
```

<!-- TODO: Brief explanation of data/control flow. -->

### Dependencies

| Depends On | What For |
|------------|----------|
| <!-- TODO --> | |

| Depended On By | What For |
|----------------|----------|
| <!-- TODO --> | |

## Key Classes

### ExhibitHandler

**File**: `src/de_funk/api/handlers/base.py:22`

**Purpose**: Base class for exhibit handlers.

| Attribute | Type |
|-----------|------|
| `handles` | `set[str]` |
| `_engine` | `Any` |
| `max_response_mb` | `float` |
| `storage_root` | `Any` |
| `_max_sql_rows` | `int` |
| `_max_dimension_values` | `int` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: Any) -> Any` | Execute the exhibit query and return a response model. |
| `distinct_values(resolved, extra_filters, resolver) -> list` | Return distinct values for a dimension field. |
| `distinct_values_by_measure(resolved, order_by, order_dir, extra_filters, resolver) -> list` | Return distinct values ordered by aggregated measure. |

### BoxHandler (ExhibitHandler)

**File**: `src/de_funk/api/handlers/box.py:11`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `handles` | `—` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: FieldResolver) -> dict` | <!-- TODO --> |

### GraphicalHandler (ExhibitHandler)

**File**: `src/de_funk/api/handlers/graphical.py:20`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `handles` | `—` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: FieldResolver) -> GraphicalResponse` | <!-- TODO --> |

### MetricsHandler (ExhibitHandler)

**File**: `src/de_funk/api/handlers/metrics.py:20`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `handles` | `—` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: FieldResolver) -> MetricResponse` | <!-- TODO --> |

### PivotHandler (ExhibitHandler)

**File**: `src/de_funk/api/handlers/pivot.py:48`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `handles` | `—` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: FieldResolver) -> GreatTablesResponse` | <!-- TODO --> |

### TableDataHandler (ExhibitHandler)

**File**: `src/de_funk/api/handlers/table_data.py:20`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `handles` | `—` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: FieldResolver) -> TableResponse` | <!-- TODO --> |

### FilterSpec (BaseModel)

**File**: `src/de_funk/api/models/requests.py:17`

**Purpose**: A single filter applied to a field.

| Attribute | Type |
|-----------|------|
| `model_config` | `—` |
| `field` | `str` |
| `operator` | `str` |
| `value` | `Union[list, str, int, float, dict]` |

### PageFilters (BaseModel)

**File**: `src/de_funk/api/models/requests.py:25`

**Purpose**: Page-level filter inheritance control.

| Attribute | Type |
|-----------|------|
| `ignore` | `list[str]` |

### SortSpec (BaseModel)

**File**: `src/de_funk/api/models/requests.py:31`

**Purpose**: Sort directive — applied at query level.

| Attribute | Type |
|-----------|------|
| `by` | `Optional[str]` |
| `order` | `str` |
| `values` | `Optional[list[str]]` |

### BucketSpec (BaseModel)

**File**: `src/de_funk/api/models/requests.py:38`

**Purpose**: Binning config for a dimension.

| Attribute | Type |
|-----------|------|
| `size` | `Optional[float]` |
| `edges` | `Optional[list[float]]` |
| `count` | `Optional[int]` |

### WindowSpec (BaseModel)

**File**: `src/de_funk/api/models/requests.py:45`

**Purpose**: Row-over-row window calculation.

| Attribute | Type |
|-----------|------|
| `key` | `str` |
| `source` | `str` |
| `type` | `str` |
| `label` | `Optional[str]` |

### TotalsSpec (BaseModel)

**File**: `src/de_funk/api/models/requests.py:53`

**Purpose**: Backend-computed summary rows/cols.

| Attribute | Type |
|-----------|------|
| `rows` | `bool` |
| `cols` | `bool` |

### SortConfig (BaseModel)

**File**: `src/de_funk/api/models/requests.py:59`

**Purpose**: Sort config for pivot rows and cols.

| Attribute | Type |
|-----------|------|
| `rows` | `Optional[SortSpec]` |
| `cols` | `Optional[SortSpec]` |

### MeasureTuple (BaseModel)

**File**: `src/de_funk/api/models/requests.py:65`

**Purpose**: Measure definition as a tuple.

| Attribute | Type |
|-----------|------|
| `key` | `str` |
| `field` | `Union[str, dict]` |
| `aggregation` | `Optional[str]` |
| `format` | `Optional[str]` |
| `label` | `Optional[str]` |

### ColumnTuple (BaseModel)

**File**: `src/de_funk/api/models/requests.py:78`

**Purpose**: Column definition for table.data.

| Attribute | Type |
|-----------|------|
| `key` | `str` |
| `field` | `str` |
| `aggregation` | `Optional[str]` |
| `format` | `Optional[str]` |
| `label` | `Optional[str]` |

### GraphicalQueryRequest (BaseModel)

**File**: `src/de_funk/api/models/requests.py:91`

**Purpose**: Request for plotly.line, plotly.bar, plotly.scatter, plotly.area, plotly.pie, plotly.heatmap.

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `x` | `Optional[str]` |
| `y` | `Optional[Union[str, list[str]]]` |
| `group_by` | `Optional[str]` |
| `size` | `Optional[str]` |
| `color` | `Optional[str]` |
| `labels` | `Optional[str]` |
| `values` | `Optional[str]` |
| `z` | `Optional[str]` |
| `aggregation` | `Optional[str]` |
| `sort` | `Optional[SortSpec]` |
| `filters` | `list[FilterSpec]` |
| `page_filters` | `Optional[PageFilters]` |
| `models` | `list[str]` |

### BoxQueryRequest (BaseModel)

**File**: `src/de_funk/api/models/requests.py:109`

**Purpose**: Request for plotly.box (OHLCV or generic).

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `category` | `str` |
| `open` | `Optional[str]` |
| `high` | `Optional[str]` |
| `low` | `Optional[str]` |
| `close` | `Optional[str]` |
| `y` | `Optional[str]` |
| `group_by` | `Optional[str]` |
| `sort` | `Optional[SortSpec]` |
| `filters` | `list[FilterSpec]` |
| `page_filters` | `Optional[PageFilters]` |
| `models` | `list[str]` |

### TableDataQueryRequest (BaseModel)

**File**: `src/de_funk/api/models/requests.py:125`

**Purpose**: Request for table.data.

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `columns` | `list[ColumnTuple]` |
| `sort_by` | `Optional[str]` |
| `sort_order` | `str` |
| `filters` | `list[FilterSpec]` |
| `page_filters` | `Optional[PageFilters]` |
| `models` | `list[str]` |

### PivotQueryRequest (BaseModel)

**File**: `src/de_funk/api/models/requests.py:136`

**Purpose**: Request for table.pivot — always renders via Great Tables.

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `rows` | `Union[str, list[str]]` |
| `cols` | `Optional[Union[str, list[str]]]` |
| `layout` | `str` |
| `measures` | `list[MeasureTuple]` |
| `buckets` | `Optional[dict[str, BucketSpec]]` |
| `windows` | `Optional[list[WindowSpec]]` |
| `totals` | `Optional[TotalsSpec]` |
| `sort` | `Optional[SortConfig]` |
| `filters` | `list[FilterSpec]` |
| `page_filters` | `Optional[PageFilters]` |
| `models` | `list[str]` |

| Method | Description |
|--------|-------------|
| `row_fields() -> list[str]` | Normalize rows to a list. |
| `col_fields() -> list[str]` | Normalize cols to a list (empty if None). |

### MetricQueryRequest (BaseModel)

**File**: `src/de_funk/api/models/requests.py:164`

**Purpose**: Request for cards.metric.

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `metrics` | `list[MeasureTuple]` |
| `filters` | `list[FilterSpec]` |
| `page_filters` | `Optional[PageFilters]` |
| `models` | `list[str]` |

### SeriesData (BaseModel)

**File**: `src/de_funk/api/models/requests.py:187`

**Purpose**: One series in a graphical response.

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `x` | `list` |
| `y` | `list` |
| `size` | `Optional[list]` |

### GraphicalResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:195`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `series` | `list[SeriesData]` |
| `truncated` | `bool` |
| `formatting` | `Optional[dict[str, Any]]` |

### TableColumn (BaseModel)

**File**: `src/de_funk/api/models/requests.py:201`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `key` | `str` |
| `label` | `str` |
| `format` | `Optional[str]` |
| `group` | `Optional[str]` |

### TableResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:208`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `columns` | `list[TableColumn]` |
| `rows` | `list[list[Any]]` |
| `truncated` | `bool` |
| `formatting` | `Optional[dict[str, Any]]` |

### ExpandableData (BaseModel)

**File**: `src/de_funk/api/models/requests.py:215`

**Purpose**: Overflow detail rows for hierarchical expand/collapse pivots.

| Attribute | Type |
|-----------|------|
| `columns` | `list[dict[str, Any]]` |
| `children` | `dict[str, list[list[Any]]]` |
| `total_rows` | `int` |

### GreatTablesResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:228`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `html` | `str` |
| `expandable` | `Optional[ExpandableData]` |

### MetricValue (BaseModel)

**File**: `src/de_funk/api/models/requests.py:233`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `key` | `str` |
| `label` | `str` |
| `value` | `Any` |
| `format` | `Optional[str]` |

### MetricResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:240`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `metrics` | `list[MetricValue]` |

### DimensionValuesResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:244`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `field` | `str` |
| `values` | `list[Any]` |

### HealthResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:249`

**Purpose**: <!-- TODO -->

| Attribute | Type |
|-----------|------|
| `status` | `str` |
| `version` | `str` |

## How to Use

### Common Operations

<!-- TODO: Runnable code examples with expected output -->

### Integration Examples

<!-- TODO: Show cross-group usage -->

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| <!-- TODO --> | | |

### Debug Checklist

- [ ] <!-- TODO -->

### Common Pitfalls

1. <!-- TODO -->

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/api/handlers/base.py` | ExhibitHandler — abstract base class for all exhibit execution families. | `ExhibitHandler` |
| `src/de_funk/api/handlers/box.py` | BoxHandler — executes box plot and OHLCV candlestick queries. | `BoxHandler` |
| `src/de_funk/api/handlers/formatting.py` | Shared formatting utilities for all exhibit handlers. | — |
| `src/de_funk/api/handlers/graphical.py` | GraphicalHandler — executes plotly.* chart queries. | `GraphicalHandler` |
| `src/de_funk/api/handlers/gt_formatter.py` | Great Tables formatter — converts pivot DataFrames into styled HTML. | — |
| `src/de_funk/api/handlers/metrics.py` | MetricsHandler — executes cards.metric / KPI queries. | `MetricsHandler` |
| `src/de_funk/api/handlers/pivot.py` | PivotHandler — single exhibit handler for all pivot table queries. | `PivotHandler` |
| `src/de_funk/api/handlers/reshape.py` | Pivot reshape utilities — column key construction and 1D window calculations. | — |
| `src/de_funk/api/handlers/table_data.py` | TableDataHandler — executes flat table.data queries. | `TableDataHandler` |
| `src/de_funk/api/models/requests.py` | Pydantic request and response models for the de_funk API. | `FilterSpec`, `PageFilters`, `SortSpec`, `BucketSpec`, `WindowSpec`, `TotalsSpec`, `SortConfig`, `MeasureTuple`, `ColumnTuple`, `GraphicalQueryRequest`, `BoxQueryRequest`, `TableDataQueryRequest`, `PivotQueryRequest`, `MetricQueryRequest`, `SeriesData`, `GraphicalResponse`, `TableColumn`, `TableResponse`, `ExpandableData`, `GreatTablesResponse`, `MetricValue`, `MetricResponse`, `DimensionValuesResponse`, `HealthResponse` |
| `src/de_funk/api/routers/bronze.py` | Bronze layer API routes — query, dimensions, and catalog for raw Bronze data. | — |
| `src/de_funk/api/routers/dimensions.py` | GET /api/dimensions/{ref} — return distinct values for a domain.field (for sidebar dropdowns). | — |
| `src/de_funk/api/routers/domains.py` | GET /api/domains — return the full field catalog for all domains. | — |
| `src/de_funk/api/routers/health.py` | GET /api/health — liveness check. | — |
| `src/de_funk/api/routers/models.py` | Model registry endpoint — browse trained ML models. | — |
| `src/de_funk/api/routers/predict.py` | Model prediction endpoint — serve inference from trained artifacts. | — |
| `src/de_funk/api/routers/query.py` | POST /api/query — registry-based dispatch to exhibit handlers. | — |
| `src/de_funk/api/main.py` | de_funk FastAPI application. | — |
