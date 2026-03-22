# Proposal 019 — Complete Rebuild Specification

**Date**: 2026-03-22
**Status**: Final
**Depends on**: 016, 017, 018 (supersedes all three)
**Diagram**: `docs/diagrams/full_vision.puml` (82 classes, 91 edges, 16 packages)

---

## New Directory Structure

```
src/de_funk/
├── __init__.py
├── app.py                              ← NEW: DeFunk application class
│
├── core/                               ← NEW + MODIFIED
│   ├── __init__.py
│   ├── engine.py                       ← NEW: Engine, DataOps, SqlOps, DuckDBOps, SparkOps
│   ├── sessions.py                     ← NEW: Session, BuildSession, QuerySession, IngestSession
│   ├── graph.py                        ← NEW: DomainGraph
│   ├── executor.py                     ← NEW: NodeExecutor (pipeline executor)
│   ├── plugins.py                      ← NEW: BuildPluginRegistry
│   ├── artifacts.py                    ← NEW: ModelArtifact, ArtifactStore
│   ├── connection.py                   ← KEEP: DataConnection ABC, SparkConnection
│   ├── duckdb_connection.py            ← KEEP: DuckDBConnection
│   ├── context.py                      ← REMOVE (replaced by DeFunk app)
│   ├── exceptions.py                   ← KEEP
│   ├── error_handling.py               ← KEEP
│   └── validation.py                   ← KEEP
│
├── config/                             ← KEEP + ADD data_classes.py
│   ├── __init__.py
│   ├── data_classes.py                 ← NEW: ~30 typed dataclasses mirroring YAML
│   ├── loader.py                       ← KEEP: ConfigLoader
│   ├── models.py                       ← KEEP: AppConfig, ConnectionConfig, etc.
│   ├── logging.py                      ← KEEP
│   ├── constants.py                    ← KEEP
│   ├── markdown_loader.py              ← KEEP
│   └── domain/                         ← KEEP + ADD validation methods
│       ├── __init__.py                 ← MODIFY: add validate_model, get_inheritance_tree
│       ├── extends.py                  ← MODIFY: add validate_extends_chain, detect_circular
│       ├── config_translator.py        ← KEEP
│       ├── build.py                    ← KEEP
│       ├── schema.py                   ← KEEP
│       ├── sources.py                  ← KEEP
│       ├── graph.py                    ← KEEP
│       ├── federation.py               ← KEEP
│       ├── views.py                    ← KEEP
│       └── subsets.py                  ← KEEP
│
├── api/                                ← MODIFY (remove duckdb import, use sessions)
│   ├── __init__.py
│   ├── main.py                         ← MODIFY: use DeFunk.from_config()
│   ├── executor.py                     ← MODIFY: remove import duckdb, thin wrapper
│   ├── resolver.py                     ← KEEP (or move to core/resolution.py)
│   ├── bronze_resolver.py              ← KEEP
│   ├── measures.py                     ← KEEP (build_measure_sql function)
│   ├── models/                         ← KEEP: Pydantic request/response
│   ├── routers/                        ← KEEP: FastAPI routes
│   └── handlers/                       ← MODIFY: use QuerySession instead of mixin
│       ├── __init__.py                 ← MODIFY: use DeFunk for registry
│       ├── base.py                     ← KEEP: ExhibitHandler ABC
│       ├── graphical.py                ← MODIFY: remove QueryEngine mixin
│       ├── pivot.py                    ← MODIFY: remove QueryEngine mixin
│       ├── metrics.py                  ← MODIFY: remove QueryEngine mixin
│       ├── box.py                      ← MODIFY: remove QueryEngine mixin
│       ├── table_data.py               ← MODIFY: remove QueryEngine mixin
│       ├── formatting.py              ← KEEP
│       ├── gt_formatter.py            ← KEEP
│       └── reshape.py                 ← KEEP
│
├── models/                             ← MODIFY (remove dead code, simplify)
│   ├── __init__.py
│   ├── registry.py                     ← KEEP (or absorb into DomainBuilderFactory)
│   ├── graph_dsl.py                    ← KEEP
│   ├── base/
│   │   ├── __init__.py
│   │   ├── model.py                    ← MODIFY: add _run_hooks, accept BuildSession
│   │   ├── domain_model.py             ← KEEP
│   │   ├── builder.py                  ← MODIFY: BuildContext accepts Engine
│   │   ├── domain_builder.py           ← MODIFY: inject BuildSession
│   │   ├── graph_builder.py            ← MODIFY: delegate to NodeExecutor
│   │   ├── model_writer.py             ← KEEP
│   │   ├── forecast_model.py           ← KEEP
│   │   ├── enrichers.py                ← KEEP (move to plugins later)
│   │   ├── indicators.py               ← KEEP
│   │   ├── data_validator.py           ← KEEP
│   │   ├── service.py                  ← KEEP (BaseAPI)
│   │   └── backend/                    ← KEEP
│   │       ├── adapter.py              ← KEEP: BackendAdapter ABC
│   │       ├── spark_adapter.py        ← KEEP
│   │       ├── duckdb_adapter.py       ← KEEP
│   │       └── sql_builder.py          ← KEEP
│   └── domains/
│       ├── corporate/
│       │   ├── company/
│       │   │   ├── builder.py          ← KEEP
│       │   │   └── model.py            ← MODIFY: keep only after_build hook
│       │   └── __init__.py
│       ├── foundation/
│       │   └── temporal/
│       │       ├── builder.py          ← KEEP
│       │       └── model.py            ← MODIFY: keep only custom_node_loading
│       ├── securities/
│       │   ├── forecast/               ← KEEP (ML training is complex)
│       │   ├── securities/
│       │   │   └── builder.py          ← KEEP
│       │   └── stocks/
│       │       ├── builder.py          ← KEEP
│       │       └── technicals.py       ← KEEP (move to plugin later)
│       └── municipal/                  ← KEEP (config-driven, no custom code)
│
├── pipelines/                          ← KEEP (minimal changes)
│   ├── base/                           ← KEEP
│   ├── ingestors/                      ← KEEP
│   └── providers/                      ← KEEP
│
├── orchestration/                      ← KEEP + FIX
│   ├── scheduler.py                    ← FIX: broken indentation, test jobs
│   ├── dependency_graph.py             ← KEEP
│   ├── checkpoint.py                   ← KEEP
│   └── common/
│       └── spark_session.py            ← FIX: remove hardcoded paths
│
├── plugins/                            ← NEW: hook implementations
│   ├── __init__.py
│   ├── temporal_calendar.py            ← NEW: @pipeline_hook for calendar gen
│   ├── company_cik.py                  ← NEW: @pipeline_hook for CIK enrichment
│   └── stock_technicals.py             ← NEW: @pipeline_hook for RSI/MACD
│
└── utils/                              ← KEEP
    ├── repo.py
    ├── env_loader.py
    ├── api_validator.py
    └── pipeline_tracker.py
```

---

## Dead Code to Remove (~7,500 lines)

### Legacy Query Layer (4,733 lines)
| File | Lines | Reason |
|------|-------|--------|
| `models/api/session.py` | 1,084 | Replaced by core/sessions.py (QuerySession) |
| `models/api/auto_join.py` | 1,874 | Replaced by core/graph.py (DomainGraph) + core/executor.py |
| `models/api/query_planner.py` | 743 | Replaced by DomainGraph + NodeExecutor |
| `models/api/aggregation.py` | 369 | Replaced by Engine.aggregate() |
| `models/api/graph.py` | 469 | Replaced by DomainGraph + DependencyGraph |
| `models/api/dal.py` | 164 | StorageRouter moves to core, Table deleted |
| `models/api/services.py` | 16 | Empty stub |
| `models/api/types.py` | 14 | Empty stub |

### Dead Domain Models (962 lines)
| File | Lines | Reason |
|------|-------|--------|
| `models/domains/securities/stocks/model.py` | 324 | All query methods dead, no build hooks |
| `models/domains/securities/securities/model.py` | 232 | All query methods dead, no build hooks |
| `models/domains/municipal/city_finance/model.py` | 406 | Entire class dead, no builder |

### Dead Measure Hierarchy (1,535 lines)
| File | Lines | Reason |
|------|-------|--------|
| `models/measures/base_measure.py` | 125 | Measures = YAML + build_measure_sql() |
| `models/measures/simple.py` | 254 | Dead |
| `models/measures/computed.py` | 164 | Dead |
| `models/measures/domain_measures.py` | 401 | Dead |
| `models/measures/executor.py` | 432 | Dead |
| `models/measures/registry.py` | 159 | Dead |

### Dead Notebook Code (304 lines)
| File | Lines | Reason |
|------|-------|--------|
| `notebook/folder_context.py` | 304 | Streamlit removed |

### Dead Code in Active Files (trim, don't delete file)
| File | Dead Methods | Lines Removed |
|------|-------------|---------------|
| `models/base/model.py` | get_denormalized, calculate_measure, calculate_measure_by_entity, get_fk_relationships, get_relations, get_metadata, measures/query_planner/python_measures properties | ~600 |
| `models/domains/corporate/company/model.py` | 6 query methods (keep only after_build) | ~150 |
| `models/domains/foundation/temporal/model.py` | 8 query methods (keep only custom_node_loading + calendar gen) | ~250 |
| `models/base/table_accessor.py` | Entire class deprecated (inline surviving methods) | ~396 |
| `models/base/measure_calculator.py` | Entire class deprecated | ~278 |
| `models/domains/securities/stocks/measures.py` | StocksMeasures (no callers) | ~30 |

**Total dead code: ~7,534 lines**

---

## Model File Changes

### CompanyModel → hook only (model.py: 212 → ~60 lines)
```python
# BEFORE: 212 lines with 6 dead query methods
class CompanyModel(BaseModel):
    def get_company_by_cik(self, cik): ...      # DEAD
    def get_company_by_ticker(self, ticker): ... # DEAD
    def get_companies_by_sector(self, sector): . # DEAD
    def get_active_companies(self): ...          # DEAD
    def list_sectors(self): ...                  # DEAD
    def get_company_count_by_sector(self): ...   # DEAD
    def after_build(self, dims, facts): ...      # ALIVE — CIK enrichment

# AFTER: ~60 lines, hook only
class CompanyModel(BaseModel):
    def after_build(self, dims, facts):
        """CIK→ticker FK enrichment."""
        # ... enrichment logic stays ...
        return dims, facts
```

**Future**: Move to `plugins/company_cik.py` as config-driven hook:
```yaml
# corporate/entity/model.md
hooks:
  after_build:
    - {fn: plugins.company_cik.fix_ids, params: {ticker_col: ticker, target_col: company_id}}
```

### TemporalModel → hook only (model.py: 457 → ~210 lines)
```python
# BEFORE: 457 lines with 8 dead query methods
# AFTER: ~210 lines, calendar generation only
class TemporalModel(BaseModel):
    def custom_node_loading(self, node_id, config):
        if node_id == "dim_calendar":
            return self._generate_calendar()
        return None
    def _generate_calendar(self): ...
    def _generate_calendar_spark(self, ...): ...
    def _generate_calendar_duckdb(self, ...): ...
```

**Future**: Move to `plugins/temporal_calendar.py`

### StocksModel → DELETE entirely
- No live build hooks
- `get_asset_type_filter()` can be a constant or config value
- StocksBuilder keeps `post_build()` for technicals

### SecuritiesModel → DELETE entirely
- No live hooks, generic DomainModel handles everything

### CityFinanceModel → DELETE entirely
- No builder, no callers, references non-existent `macro` model

---

## New Plugin Templates

### `src/de_funk/plugins/__init__.py`
```python
"""Plugin hooks for build pipeline customization."""
```

### `src/de_funk/plugins/temporal_calendar.py`
```python
"""Generate dim_calendar programmatically (no Bronze source)."""
from de_funk.core.plugins import pipeline_hook

@pipeline_hook("custom_node_loading", model="temporal")
def generate_calendar(df, engine, config, node_id=None, **params):
    """Generate dim_calendar from date range config."""
    if node_id != "dim_calendar":
        return None
    start = params.get("start", "2000-01-01")
    end = params.get("end", "2050-12-31")
    # Calendar generation logic (backend-agnostic via engine)
    return engine.execute_sql(f"SELECT ... generate_series('{start}', '{end}', INTERVAL '1 day')")
```

### `src/de_funk/plugins/company_cik.py`
```python
"""Fix company_id FK using CIK from dim_company."""
from de_funk.core.plugins import pipeline_hook

@pipeline_hook("after_build", model="corporate.entity")
def fix_company_ids(df, engine, config, dims=None, facts=None, **params):
    """Enrich fact tables with CIK-based company_id from dim_company."""
    ticker_col = params.get("ticker_col", "ticker")
    target_col = params.get("target_col", "company_id")
    dim_company = dims.get("dim_company")
    if dim_company is None:
        return dims, facts
    for fact_name, fact_df in facts.items():
        if ticker_col in engine.columns(fact_df):
            facts[fact_name] = engine.join(fact_df, dim_company, on=[ticker_col], how="left")
    return dims, facts
```

### `src/de_funk/plugins/stock_technicals.py`
```python
"""Compute technical indicators (RSI, MACD) post-build."""
from de_funk.core.plugins import pipeline_hook

@pipeline_hook("post_build", model="securities.stocks")
def compute_technicals(df, engine, config, result=None, **params):
    """Add technical indicators to fact_stock_prices."""
    periods = params.get("periods", [14, 30])
    # Technical indicator computation via engine.window()
    pass
```

### `src/de_funk/core/plugins.py` (template)
```python
"""Build plugin registry — extensible hook system."""
from typing import Callable, Dict, List

_registry: Dict[str, Dict[str, List[Callable]]] = {}

def pipeline_hook(hook_type: str, model: str = "*"):
    """Decorator to register a pipeline hook."""
    def decorator(fn: Callable) -> Callable:
        _registry.setdefault(hook_type, {}).setdefault(model, []).append(fn)
        return fn
    return decorator

class BuildPluginRegistry:
    @staticmethod
    def register(hook_type: str, model_name: str, fn: Callable):
        _registry.setdefault(hook_type, {}).setdefault(model_name, []).append(fn)

    @staticmethod
    def get(hook_type: str, model_name: str) -> List[Callable]:
        hooks = _registry.get(hook_type, {})
        return hooks.get(model_name, []) + hooks.get("*", [])

    @staticmethod
    def discover(plugins_dir: str):
        """Auto-discover and import all plugin modules."""
        import importlib, pkgutil
        package = importlib.import_module(plugins_dir)
        for _, name, _ in pkgutil.iter_modules(package.__path__):
            importlib.import_module(f"{plugins_dir}.{name}")
```
