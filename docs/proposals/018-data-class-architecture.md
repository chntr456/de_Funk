# Proposal 018 — Data Class Architecture

**Date**: 2026-03-21
**Status**: Draft
**Builds on**: 016 (query consolidation), 017 (model simplification)

## Problem

The YAML frontmatter in domain markdown files has rich, nested structure — edges with cardinality, measures with format codes, sources with alias expressions, schemas with FK references. But the Python code flattens all of this to `Dict[str, Any]` and passes it around as `storage_cfg`, `model_cfg`, `config`. No IDE completion, no validation, no documentation of what keys exist.

The result:
- `UniversalSession.__init__(connection, storage_cfg: Dict, repo_root, models)` — `storage_cfg` could be anything
- `BaseModel.__init__(connection, storage_cfg, model_cfg, params, repo_root)` — 5 untyped params
- `GraphBuilder` reads `model_cfg["graph"]["edges"]` with no guarantee the key exists
- Bugs hide in dict key typos that only surface at runtime

Meanwhile, two fundamentally different config types get mixed:
- **Frontmatter configs** (domain models, tables, sources, providers, endpoints) = describe the data. Change when you add a data source. Live in markdown.
- **Infrastructure configs** (storage paths, connection, cluster, retry, API limits) = describe where/how to run. Change per environment. Live in JSON/env.

## Solution: Typed Data Classes Mirroring the YAML

Every YAML structure gets a Python `@dataclass` with exact field names matching YAML keys. The loader parses YAML → instantiates the dataclass → passes typed objects everywhere.

---

## Domain Model Data Classes

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Atomic types ─────────────────────────────────────────

@dataclass
class SchemaField:
    """One column in a table schema. Parsed from [name, type, nullable, desc, {opts}]."""
    name: str
    type: str
    nullable: bool = True
    description: str = ""
    derived: Optional[str] = None       # SQL expression for computed columns
    fk: Optional[str] = None            # "dim_company.company_id"
    format: Optional[str] = None        # "$2", "%", "#,##0"


@dataclass
class EdgeSpec:
    """One graph edge. Parsed from [name, from, to, [keys], cardinality, domain, ...]."""
    name: str
    from_table: str
    to_table: str
    join_keys: list[str]                # ["date_id=date_id"]
    cardinality: str                    # "many_to_one", "one_to_many"
    target_domain: Optional[str] = None # "temporal"
    optional: bool = False


@dataclass
class MeasureDef:
    """One measure. Parsed from [name, agg, field, label, {opts}]."""
    name: str
    aggregation: str                    # "avg", "sum", "count_distinct", "expression"
    field: str | dict                   # "fact.column" or {fn: "divide", ...}
    label: str = ""
    format: Optional[str] = None
    options: dict = field(default_factory=dict)


@dataclass
class AliasSpec:
    """One source alias. Parsed from [target_column, expression]."""
    target_column: str
    expression: str


@dataclass
class EnrichSpec:
    """Join-based enrichment on a table."""
    from_table: str                     # "corporate.entity.dim_company"
    join: list[str]                     # ["company_id=company_id"]
    columns: list[str]                  # ["sector", "industry"]


# ── Nested specs ─────────────────────────────────────────

@dataclass
class PhaseSpec:
    tables: list[str]


@dataclass
class BuildSpec:
    sort_by: list[str] = field(default_factory=list)
    optimize: bool = True
    partitions: list[str] = field(default_factory=list)
    phases: dict[str, PhaseSpec] = field(default_factory=dict)


@dataclass
class SilverSpec:
    root: str


@dataclass
class ModelStorageSpec:
    format: str = "delta"
    silver: Optional[SilverSpec] = None


@dataclass
class GraphSpec:
    edges: list[EdgeSpec] = field(default_factory=list)
    paths: dict[str, Any] = field(default_factory=dict)


@dataclass
class MeasuresSpec:
    simple: list[MeasureDef] = field(default_factory=list)
    computed: list[MeasureDef] = field(default_factory=list)


# ── Config containers ────────────────────────────────────

@dataclass
class TableConfig:
    """Parsed from tables/*.md frontmatter."""
    table: str                          # "dim_stock"
    table_type: str                     # "dimension" | "fact"
    schema: list[SchemaField] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    unique_key: list[str] = field(default_factory=list)
    partition_by: list[str] = field(default_factory=list)
    measures: list[MeasureDef] = field(default_factory=list)
    enrich: list[EnrichSpec] = field(default_factory=list)
    extends: Optional[str] = None
    source_file: Optional[str] = None


@dataclass
class SourceConfig:
    """Parsed from sources/**/*.md frontmatter."""
    source: str                         # "daily_prices"
    maps_to: str                        # "fact_stock_prices"
    from_ref: str                       # "bronze.alpha_vantage_time_series_daily"
    aliases: list[AliasSpec] = field(default_factory=list)
    domain_source: Optional[str] = None # "'alpha_vantage'" discriminator
    filter: list[str] = field(default_factory=list)
    discriminator: Optional[str] = None
    extends: Optional[str] = None
    source_file: Optional[str] = None


@dataclass
class DomainModelConfig:
    """Parsed from model.md frontmatter + auto-discovered tables/sources/views."""
    model: str                          # "securities.stocks" (canonical)
    version: str = "1.0"
    description: str = ""
    extends: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: str = "active"
    sources_from: Optional[str] = None

    storage: ModelStorageSpec = field(default_factory=ModelStorageSpec)
    graph: GraphSpec = field(default_factory=GraphSpec)
    build: BuildSpec = field(default_factory=BuildSpec)
    measures: MeasuresSpec = field(default_factory=MeasuresSpec)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Auto-discovered children
    tables: dict[str, TableConfig] = field(default_factory=dict)
    sources: dict[str, SourceConfig] = field(default_factory=dict)
    views: dict[str, Any] = field(default_factory=dict)

    source_file: Optional[str] = None
```

## Provider / Endpoint Data Classes

```python
@dataclass
class EndpointSchemaField:
    """One field in an endpoint schema. Different from domain SchemaField."""
    name: str
    type: str
    source_field: str                   # raw API field name ("Symbol")
    nullable: bool = True
    description: str = ""
    transform: Optional[str] = None     # "to_date(yyyy-MM-dd)"
    coerce: Optional[str] = None        # "double"
    default: Optional[Any] = None


@dataclass
class EndpointConfig:
    """Parsed from Endpoints/**/*.md frontmatter."""
    endpoint_id: str
    provider: str
    method: str = "GET"
    endpoint_pattern: str = ""
    format: str = "json"
    auth: str = "inherit"
    response_key: Optional[str] = None
    default_query: dict = field(default_factory=dict)
    required_params: list[str] = field(default_factory=list)
    pagination_type: str = "none"
    bulk_download: bool = False
    download_method: str = "json"
    json_structure: str = "object"
    raw_schema: list[list] = field(default_factory=list)
    schema: list[EndpointSchemaField] = field(default_factory=list)
    bronze: Optional[str] = None        # provider bronze dir
    partitions: list[str] = field(default_factory=list)
    write_strategy: str = "upsert"
    key_columns: list[str] = field(default_factory=list)
    date_column: Optional[str] = None
    domain: str = ""
    data_tags: list[str] = field(default_factory=list)
    status: str = "active"
    update_cadence: str = ""
    source_file: Optional[str] = None


@dataclass
class ProviderConfig:
    """Parsed from Providers/*.md frontmatter."""
    provider_id: str
    provider: str                       # display name
    api_type: str = "rest"
    base_url: str = ""
    auth_model: str = "api-key"
    env_api_key: str = ""
    rate_limit_per_sec: float = 1.0
    default_headers: dict = field(default_factory=dict)
    provider_settings: dict = field(default_factory=dict)
    endpoints: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    category: str = "public"
    data_domains: list[str] = field(default_factory=list)
    data_tags: list[str] = field(default_factory=list)
    status: str = "active"
    source_file: Optional[str] = None
```

## Infrastructure Data Classes

```python
@dataclass
class RootsConfig:
    """Storage mount points — different physical storage tiers."""
    raw: str = ""                       # HDD: /mnt/disk/storage/raw/
    bronze: str = ""                    # SSD: /shared/storage/bronze/
    silver: str = ""                    # SSD: /shared/storage/silver/


@dataclass
class ApiLimits:
    duckdb_memory_limit: str = "3GB"
    max_sql_rows: int = 30000
    max_dimension_values: int = 10000
    max_response_mb: float = 4.0


@dataclass
class TablePath:
    root: str                           # "silver"
    rel: str                            # "temporal/dims/dim_calendar"
    partitions: list[str] = field(default_factory=list)


@dataclass
class StorageConfig:
    """Parsed from storage.json."""
    roots: RootsConfig = field(default_factory=RootsConfig)
    api: ApiLimits = field(default_factory=ApiLimits)
    default_format: str = "delta"
    domain_roots: dict[str, str] = field(default_factory=dict)
    tables: dict[str, TablePath] = field(default_factory=dict)


@dataclass
class SparkConfig:
    driver_memory: str = "4g"
    executor_memory: str = "4g"
    shuffle_partitions: int = 200
    timezone: str = "UTC"


@dataclass
class DuckDBConfig:
    database_path: str = ":memory:"
    memory_limit: str = "4GB"
    threads: int = 4
    read_only: bool = False


@dataclass
class ConnectionConfig:
    type: str = "duckdb"
    spark: Optional[SparkConfig] = None
    duckdb: Optional[DuckDBConfig] = None


@dataclass
class ClusterConfig:
    spark_master: str = "local[*]"
    fallback_to_local: bool = True
    task_batch_size: int = 50


@dataclass
class RetryConfig:
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    exponential_backoff: bool = True


@dataclass
class RunConfig:
    """Parsed from run_config.json."""
    defaults: dict = field(default_factory=dict)
    providers: dict[str, dict] = field(default_factory=dict)
    silver_models: list[str] = field(default_factory=list)
    cluster: ClusterConfig = field(default_factory=ClusterConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    profiles: dict[str, dict] = field(default_factory=dict)
```

---

## Revised EngineContext

With typed data classes, EngineContext becomes much clearer:

```python
@dataclass
class EngineContext:
    """Universal runtime context. Created once, passed everywhere.

    Replaces: connection + storage_cfg + repo_root + models threading.
    """
    # Infrastructure (from JSON/env — how to run)
    storage: StorageConfig
    connection: ConnectionConfig
    run: RunConfig
    repo_root: Path

    # Domain knowledge (from markdown — what data exists)
    models: dict[str, DomainModelConfig]     # loaded by DomainConfigLoader
    providers: dict[str, ProviderConfig]      # loaded from Providers/*.md
    endpoints: dict[str, EndpointConfig]      # loaded from Endpoints/**/*.md

    # Live connection (created from ConnectionConfig)
    conn: DataConnection                      # DuckDB or Spark

    # Derived (built from above at creation time)
    _ops: DataOps                             # backend-specific DataFrame ops
    _sql: SqlOps                              # backend-specific SQL ops
```

The key insight: EngineContext holds **typed configs** (not raw dicts) and a **live connection** (not a connection config). Everything else is derived.

A session is just: load the configs, create the connection, build the context. No 5-parameter constructors, no `storage_cfg: Dict[str, Any]`.

---

## What Changes

### Frontmatter configs (domain knowledge)
| Today | Future |
|-------|--------|
| `model_cfg: Dict[str, Any]` | `model: DomainModelConfig` |
| `model_cfg["graph"]["edges"][0][3]` | `model.graph.edges[0].join_keys` |
| `model_cfg.get("build", {}).get("phases", {})` | `model.build.phases` |
| `model_cfg["tables"]["dim_stock"]["schema"]` | `model.tables["dim_stock"].schema` |
| No IDE completion | Full autocompletion on every field |
| Key typos fail at runtime | Missing fields fail at parse time |

### Infrastructure configs (how to run)
| Today | Future |
|-------|--------|
| `storage_cfg: Dict[str, Any]` everywhere | `ctx.storage: StorageConfig` |
| `storage_cfg["roots"]["silver"]` | `ctx.storage.roots.silver` |
| `storage_cfg.get("api", {}).get("max_sql_rows", 10000)` | `ctx.storage.api.max_sql_rows` |

### Measures
| Today | Future |
|-------|--------|
| `models/measures/` class hierarchy (500 lines, dead) | Deleted |
| `api/measures.py build_measure_sql()` (84 lines, alive) | Stays as-is |
| `MeasureDef` defined in YAML frontmatter | `DomainModelConfig.measures.simple[0]` |
| `PivotHandler` calls `build_measure_sql(measure_tuple)` | Same — reads from `MeasureDef` |

Measures don't need classes because the YAML IS the definition. The handler reads `MeasureDef` from the config, passes it to `build_measure_sql()`, gets SQL back. Done.

---

## Migration Path

### Phase 1: Define data classes (no behavior change)
- Create `src/de_funk/config/data_classes.py` with all data classes above
- Add `from_dict()` classmethods that parse raw YAML dicts into typed objects
- DomainConfigLoader returns `DomainModelConfig` instead of `Dict`

### Phase 2: Thread typed configs
- `BaseModel.__init__(ctx: EngineContext, model: DomainModelConfig)` replaces 5 params
- `GraphBuilder` reads `model.graph.edges` (typed) instead of `model_cfg["graph"]["edges"]` (dict)
- `FieldResolver.__init__(ctx: EngineContext)` reads from `ctx.models` and `ctx.storage`

### Phase 3: Delete raw dict passing
- Remove all `storage_cfg: Dict[str, Any]` parameters
- Remove all `model_cfg: Dict[str, Any]` parameters
- Remove all `.get("key", {}).get("subkey", default)` chains

---

## Decisions Needed

1. Should `DomainModelConfig` be immutable (frozen dataclass) or mutable? The config translator currently mutates the dict to add `graph.nodes`. If frozen, translator returns a new object.
2. Should the data classes live in `config/data_classes.py` (one file) or split into `config/domain.py`, `config/provider.py`, `config/infrastructure.py`?
