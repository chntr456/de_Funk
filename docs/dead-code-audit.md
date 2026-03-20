# Dead Code Audit

**Date**: 2026-03-20
**Updated**: Added domain model query methods, CityFinanceModel, legacy query classes

## Summary

~60 dead items found. Three categories:
1. **Legacy query layer** — UniversalSession, AutoJoinHandler, etc. (replaced by core/query/ in Proposal 016)
2. **Domain model query methods** — get_prices(), get_company_by_ticker(), etc. (replaced by FieldResolver)
3. **Streamlit remnants** — notebook classes, GT config, weighting

---

## Legacy Query Layer (Proposal 016 deletes these)

| File | Class/Item | Lines | Replaced By |
|------|-----------|-------|-------------|
| `models/api/session.py` | `UniversalSession` | 1,084 | `core/query/session.QuerySession` |
| `models/api/auto_join.py` | `AutoJoinHandler` | 1,874 | `core/query/join_planner.JoinPlanner` + graph edges for temporal |
| `models/api/aggregation.py` | `AggregationHandler` | 369 | `core/query/aggregator.Aggregator` |
| `models/api/query_planner.py` | `GraphQueryPlanner` | 743 | `core/query/join_planner.JoinPlanner` |
| `models/api/graph.py` | `ModelGraph` | 469 | Build ordering → `orchestration/dependency_graph.py`. Join paths → `FieldResolver._join_graph` |
| `models/api/dal.py` | `Table` class | ~75 | Direct Spark reads |
| `models/api/services.py` | Empty stub | 15 | Nothing (v2.6 deprecation) |
| `models/api/types.py` | Empty stub | 14 | Nothing (v2.6 deprecation) |

Note: `StorageRouter` from `dal.py` moves to `core/query/storage.py` (not deleted, relocated).

---

## Dead Domain Model: CityFinanceModel

`src/de_funk/models/domains/municipal/city_finance/model.py` — entire file is dead.

- No builder exists (municipal Silver built by generic DomainModel + markdown configs)
- Zero external method calls
- References non-existent `macro` model
- Registered in ModelRegistry under old name `city_finance` (pre-canonical naming)
- Municipal domains are fully config-driven via `domains/models/municipal/*/model.md`

**All methods dead:**
- get_local_unemployment, get_building_permits, get_permits_with_context
- get_unemployment_with_context, compare_to_national_unemployment
- get_community_areas, get_permit_types, get_permit_summary_by_area
- list_community_areas, get_chicago_data_sources

---

## Dead Domain Model Query Methods

The FastAPI FieldResolver replaced all domain-specific query methods. These are Streamlit/notebook-era APIs that nothing calls.

### StocksModel — query methods dead, build hooks alive
| Dead Method | What it did |
|-------------|-------------|
| `get_prices(ticker, date_from, date_to)` | Query fact_stock_prices with filters |
| `get_technicals(ticker, date_from, date_to)` | Query fact_stock_technicals |
| `get_stock_info(ticker)` | Query dim_stock |
| `get_stock_with_company(ticker)` | Cross-model join stocks→company |
| `get_stocks_by_sector(sector)` | Filter by sector |
| `list_tickers(active_only)` | Distinct ticker values |
| `list_sectors()` | Distinct sector values |
| `get_top_by_market_cap(limit)` | Top N by market cap |

**Alive:** `get_asset_type_filter()` — used by StocksBuilder

### SecuritiesModel — all query methods dead
| Dead Method | What it did |
|-------------|-------------|
| `get_security(ticker)` | Query dim_security |
| `get_securities_by_type(asset_type)` | Filter by type |
| `get_securities_by_exchange(exchange)` | Filter by exchange |
| `get_active_securities()` | Active flag filter |
| `list_asset_types()` | Distinct asset types |
| `list_exchanges()` | Distinct exchanges |
| `get_prices(ticker, ...)` | Query fact_security_prices |
| `get_security_count_by_type()` | Aggregation |
| `get_security_count_by_exchange()` | Aggregation |

### CompanyModel — query methods dead, after_build alive
| Dead Method | What it did |
|-------------|-------------|
| `get_company_by_cik(cik)` | Query dim_company by CIK |
| `get_company_by_ticker(ticker)` | Query dim_company by ticker |
| `get_companies_by_sector(sector)` | Filter by sector |
| `get_active_companies()` | Active flag filter |
| `list_sectors()` | Distinct sectors |
| `get_company_count_by_sector()` | Aggregation |

**Alive:** `after_build()` — CIK→ticker enrichment (build hook)

### TemporalModel — query methods dead, calendar generation alive
| Dead Method | What it did |
|-------------|-------------|
| `get_calendar(date_from, date_to)` | Query dim_calendar |
| `get_weekdays/get_weekends(...)` | Filtered calendar |
| `get_fiscal_year_dates(fiscal_year)` | Fiscal year filter |
| `get_quarter_dates(year, quarter)` | Quarter filter |
| `get_month_dates(year, month)` | Month filter |
| `get_date_range_info(from, to)` | Calendar metadata |
| `get_calendar_config()` | Config metadata |

**Alive:** `custom_node_loading()`, `_generate_calendar_spark/duckdb()` — programmatic dim_calendar generation

---

## Critical — Dead Imports (runtime errors)

| File | Import | Issue |
|------|--------|-------|
| `scripts/debug/test_ui_model_access.py` | `from de_funk.notebook.managers import NotebookManager` | Module deleted |
| `tests/diagnose_stocks_tab.py` | `from de_funk.notebook.exhibits.registry import ExhibitTypeRegistry` | Module deleted |

## Dead Files

| File | Contents | Lines |
|------|----------|-------|
| `models/domains/municipal/city_finance/model.py` | CityFinanceModel (entire class) | ~310 |
| `models/domains/municipal/city_finance/__init__.py` | Re-export | ~10 |
| `notebook/folder_context.py` | FolderFilterContext, FolderFilterContextManager | 254 |
| `models/api/services.py` | Empty compat (`__all__ = []`) | 15 |
| `models/api/types.py` | Empty compat (`__all__ = []`) | 14 |

## Dead Classes in Active Modules

### `notebook/schema.py` — Streamlit GreatTable config
GTColumnConfig, GTDateDimensionConfig, GTFootnoteConfig, GTRowConfig, GTSpannerConfig, GreatTableConfig, WeightingMethod, WeightingConfig

### `notebook/parsers/`
BlockPosition, MarkdownNotebook (markdown_parser.py), VariableResolver (yaml_parser.py)

### `notebook/expressions/resolver.py`
resolve_expression() function

## Dead Functions

### `utils/env_loader.py`
find_dotenv, get_api_keys, get_bls_api_keys, get_chicago_api_keys, get_polygon_api_keys

### `utils/repo.py`
repo_root_for_script()

## Empty Directories
- `src/de_funk/pipelines/facets/`

---

## What Stays (build hooks only)

| Domain | Custom Python | Why it can't be markdown |
|--------|--------------|--------------------------|
| TemporalModel | `_generate_calendar_spark/duckdb()` | Programmatic dim_calendar (no Bronze source) |
| CompanyModel | `after_build()` | CIK→ticker cross-table enrichment |
| StocksBuilder | `post_build()` | Technical indicator computation |
| ForecastBuilder | `build()` entirely custom | ML model training |

Everything else is config-driven via `DomainConfigLoaderV4` + `DomainModel` + markdown frontmatter.
