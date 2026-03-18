# Architecture Walkthrough

de_Funk is a graph-based analytical overlay that turns markdown domain configs into a queryable data warehouse. Users write exhibit blocks in Obsidian notes; the plugin sends structured queries to a FastAPI backend that resolves fields, builds joins, and executes SQL against DuckDB over Delta Lake silver tables.

This document is a guided tour through the two main execution paths: the **query pipeline** (interactive, DuckDB) and the **build pipeline** (batch, Spark). Each section shows real class usage from `src/de_funk/` with constructors, method calls, and expected output.

---

## System Diagram

```
Obsidian Note (```de_funk block)
       |
       v
+--------------------+       HTTP/JSON        +------------------------------+
|  Obsidian Plugin   | ----------------------> |   FastAPI Backend             |
|  (TypeScript)      |                         |   :8765                      |
|                    | <---------------------- |                              |
|  * filter-sidebar  |    Plotly traces /      |  +-------------+  +----------------+
|  * de-funk.ts      |    GT HTML /            |  | FieldResolver|  | BronzeResolver |
|  * render/*        |    metric values        |  | (Silver)     |  | (Bronze)       |
+--------------------+                         |  +------+------+  +-------+--------+
                                               |         | resolve          | resolve
                                               |  +------v------------------v------+
                                               |  |          QueryEngine           |
                                               |  |          (DuckDB SQL)          |
                                               |  +------+------------------------+
                                               |         | read
                                               |  +------v------+  +------v------+
                                               |  | Silver Layer |  | Bronze Layer|
                                               |  | (Delta Lake) |  | (Delta Lake)|
                                               |  | dims/ facts/ |  | raw API data|
                                               |  +-------------+  +-------------+
                                               +------------------------------+

Build Pipeline (offline, Spark):

  API Sources ---> Bronze (Delta) ---> Silver (Delta)
       |                                     |
  rate-limited                          dims/ + facts/
  incremental                           per domain model
```

There are three execution paths through the system:

**Silver query path (interactive)**: An Obsidian code block fires a POST to `/api/query`. The `FieldResolver` translates `domain.field` references into Silver table paths. The `QueryEngine` generates SQL with automatic joins via BFS over a graph, executes against DuckDB, and returns Plotly traces, Great Tables HTML, or metric values.

**Bronze query path (interactive)**: An Obsidian code block with `layer: bronze` fires a POST to `/api/bronze/query`. The `BronzeResolver` translates `provider.endpoint.field` references into Bronze table paths. Queries hit raw provider data directly — no joins, no model build required. Useful for data exploration and validation.

**Build path (batch)**: `DomainBuilderFactory` scans `domains/models/` for all `model.md` files, creates dynamic builder classes, resolves dependencies with Kahn's algorithm, and builds each model's Silver tables from Bronze using Spark.

---

## Part 1: Query Pipeline (Interactive Path)

### 1.1 The Request

When an Obsidian note contains a `de_funk` code block, the plugin parses the YAML body, merges in page-level frontmatter filters and sidebar control state, and POSTs a JSON payload to `/api/query`.

A typical request looks like this:

```json
{
  "type": "plotly.bar",
  "x": "municipal.finance.org_unit_name",
  "y": ["municipal.finance.amount"],
  "aggregation": "sum",
  "filters": [
    {"field": "municipal.finance.event_type", "op": "eq", "value": "APPROPRIATION"},
    {"field": "temporal.year", "op": "eq", "value": 2025}
  ]
}
```

The `type` field determines which handler processes the request. The `x`, `y`, `group_by`, `rows`, `cols`, `measures` fields contain domain.field references that the backend must resolve to actual Silver table paths and column names. Filters use the same domain.field namespace.

### 1.2 FastAPI Backend Startup

The application is created by the factory function in `src/de_funk/api/main.py`:

```python
# src/de_funk/api/main.py

from de_funk.api.main import create_app

app = create_app()
```

On startup, `create_app()` does the following:

```python
# 1. Load configs/storage.json for DuckDB limits and storage path overrides
storage_overrides, api_cfg = _load_storage_config(repo_root)
# api_cfg contains: duckdb_memory_limit, max_sql_rows, max_dimension_values, max_response_mb

# 2. Create FieldResolver (Silver) by scanning all domains/models/**/model.md
app.state.resolver = FieldResolver(
    domains_root=_domains_root,       # domains/
    storage_root=_storage_root,       # /shared/storage/silver
    domain_overrides=storage_overrides,
)

# 3. Create BronzeResolver by scanning data_sources/Endpoints/
app.state.bronze_resolver = BronzeResolver(
    docs_root=_docs_root,             # data_sources/
    bronze_root=_bronze_root,         # /shared/storage/bronze
)
# Indexes all providers, endpoints, fields, and Delta paths

# 4. Create QueryEngine connected to DuckDB
app.state.executor = QueryEngine(
    storage_root=_storage_root,
    memory_limit=api_cfg["duckdb_memory_limit"],
    max_sql_rows=int(api_cfg["max_sql_rows"]),
    max_dimension_values=int(api_cfg["max_dimension_values"]),
    max_response_mb=float(api_cfg["max_response_mb"]),
)

# 5. Build handler registry — maps type strings to handler instances
app.state.registry = build_registry(**engine_kwargs)
```

The handler registry (`src/de_funk/api/handlers/__init__.py`) instantiates one instance of each handler class. Each handler declares a `handles` set of type strings:

| Handler Class | Type Strings | Output Format |
|---------------|-------------|---------------|
| `GraphicalHandler` | `plotly.line`, `plotly.bar`, `plotly.scatter`, `plotly.area`, `plotly.pie`, `plotly.heatmap`, `line`, `bar`, `scatter`, `area`, `pie`, `heatmap` | `GraphicalResponse` (Plotly JSON series) |
| `BoxHandler` | `plotly.box`, `ohlcv`, `candlestick` | Plotly OHLC traces |
| `PivotHandler` | `table.pivot`, `pivot`, `pivot_table`, `great_table`, `great_tables`, `gt` | `GreatTablesResponse` (HTML + expandable JSON) |
| `TableDataHandler` | `table.data` | `TableResponse` (flat column arrays) |
| `MetricsHandler` | `cards.metric`, `kpi`, `metric_cards` | `MetricResponse` (KPI values) |

Each handler inherits from both `ExhibitHandler` (abstract base) and `QueryEngine` (DuckDB mixin), giving it access to SQL generation and execution infrastructure.

### 1.3 FieldResolver -- The Metadata Brain

The `FieldResolver` (`src/de_funk/api/resolver.py`) is the heart of the query pipeline. It translates human-readable domain.field references into physical Silver table paths and column names.

**Index construction** happens once at startup:

```python
# src/de_funk/api/resolver.py

resolver = FieldResolver(
    domains_root=Path("domains"),
    storage_root=Path("/shared/storage/silver"),
    domain_overrides={},
)

# On first use, _build_index() scans domains/models/:
# 1. Find all model.md files to build {directory -> model_name} map
# 2. Register graph.edges from each model.md into a bidirectional join graph
# 3. Store depends_on for domain scoping
# 4. Scan all domain-model-table files for schema columns
# 5. Build index: {domain: {field: (table_name, format_code, subdir)}}
```

**Resolving a single field** uses longest-prefix matching against known domain names:

```python
field = resolver.resolve("municipal.finance.amount")

# Step 1: FieldRef parses the reference
# Known domains: {"temporal", "municipal.finance", "municipal.geospatial", ...}
# Try: "municipal" -> not a known domain
# Try: "municipal.finance" -> YES, match found
# Result: domain="municipal.finance", field="amount"

# Step 2: Lookup in index
# index["municipal.finance"]["amount"]
# -> ("fact_budget_events", "$", "facts")

# Step 3: Build Silver path
# Default mapping: "municipal.finance" -> /shared/storage/silver/municipal/finance
# subdir = "facts"
# -> /shared/storage/silver/municipal/finance/facts/fact_budget_events

# Returns:
# ResolvedField(
#     ref=FieldRef("municipal.finance.amount"),
#     table_name="fact_budget_events",
#     column="amount",
#     silver_path=Path("/shared/storage/silver/municipal/finance/facts/fact_budget_events"),
#     format_code="$",
# )
```

**Batch resolution** resolves multiple fields at once:

```python
resolved = resolver.resolve_many([
    "municipal.finance.amount",
    "municipal.finance.org_unit_name",
    "temporal.year",
])
# -> {"municipal.finance.amount": ResolvedField(...), ...}
```

**Field catalog** powers the `/api/domains` endpoint, which the Obsidian plugin uses for autocomplete:

```python
catalog = resolver.get_field_catalog()
# -> {
#     "municipal.finance": {
#         "fields": {
#             "amount": {"table": "fact_budget_events", "column": "amount", "format": "$"},
#             "org_unit_name": {"table": "dim_department", "column": "org_unit_name", "format": None},
#             "fund_description": {"table": "dim_fund", "column": "fund_description", "format": None},
#             ...
#         }
#     },
#     "municipal.public_safety": { ... },
#     "temporal": { ... },
#     ...
# }
```

**Join path finding** uses BFS over the bidirectional join graph built from `graph.edges` declarations in model.md files:

```python
# Find how to join fact_budget_events to dim_department
path = resolver.find_join_path("fact_budget_events", "dim_department")

# BFS traversal:
# fact_budget_events -> neighbors: [("dim_department", "department_description", "org_unit_code"), ...]
# dim_department == target -> FOUND

# Returns: [
#     ("dim_department", "department_description", "org_unit_code"),
# ]
# Meaning: JOIN dim_department ON fact_budget_events.department_description = dim_department.org_unit_code
```

The BFS accepts an `allowed_domains` parameter to prevent cross-domain traversal (see Section 1.5).

### 1.4 QueryEngine -- SQL Generation

The `QueryEngine` (`src/de_funk/api/executor.py`) generates and executes DuckDB SQL. Let's walk through the full SQL generation pipeline for our example request: "budget appropriations by department."

**Step 1: Resolve all fields and collect tables**

```python
# Inside GraphicalHandler.execute():
x_resolved  = resolver.resolve("municipal.finance.org_unit_name")
# -> table=dim_department, column=org_unit_name, path=.../municipal/finance/dims/dim_department

y_resolved  = [resolver.resolve("municipal.finance.amount")]
# -> table=fact_budget_events, column=amount, path=.../municipal/finance/facts/fact_budget_events

# Collect tables from resolved fields
tables = self._collect_tables([x_resolved] + y_resolved + filter_fields)
# -> {
#     "dim_department": "/shared/storage/silver/municipal/finance/dims/dim_department",
#     "fact_budget_events": "/shared/storage/silver/municipal/finance/facts/fact_budget_events",
# }
```

**Step 2: Build FROM clause with automatic joins**

`_build_from()` sorts tables (facts first, dimensions last) and uses BFS to chain joins:

```python
from_clause = self._build_from(tables, resolver, allowed_domains=allowed)

# Base table: fact_budget_events (fact, sorted first)
# Next: dim_department
#   BFS: fact_budget_events -> dim_department via department_description=org_unit_code edge
#   -> JOIN dim_department ON fact_budget_events.department_description = dim_department.org_unit_code
```

The `_safe_scan()` method probes each path for Delta format, falling back to Parquet glob:

```python
# For Delta tables:
self._safe_scan("/shared/storage/silver/municipal/finance/facts/fact_budget_events")
# -> "delta_scan('/shared/storage/silver/municipal/finance/facts/fact_budget_events')"

# If Delta fails:
# -> "read_parquet('/shared/storage/silver/municipal/finance/facts/fact_budget_events/*.parquet')"
```

If BFS finds no path between two tables, the engine falls back to CROSS JOIN and logs a warning.

**Step 3: Build WHERE clause from filters**

```python
where_clauses = self._build_where(req.filters, resolver)
# Filter: field="municipal.finance.event_type", op="eq", value="APPROPRIATION"
# Resolves to: "fact_budget_events"."event_type" = 'APPROPRIATION'
# Filter: field="temporal.year", op="eq", value=2025
# Resolves to: "fact_budget_events"."fiscal_year" = 2025

# Supported operators:
# "in"      -> col IN ('A', 'B', 'C')
# "eq"      -> col = 'value'
# "gte"     -> col >= 'value'
# "lte"     -> col <= 'value'
# "like"    -> col LIKE 'pattern'
# "between" -> col BETWEEN 'from' AND 'to'
#
# Date expressions in between values:
# "current_date"       -> today's date
# "current_date - 30"  -> 30 days ago
# "year_start"         -> January 1 of current year
```

Filters referencing tables not in the FROM clause are silently skipped. This prevents cross-domain page filters from injecting unreachable table references.

**Step 4: Build SELECT / GROUP BY (handler-specific)**

Each handler constructs its own SELECT. For `GraphicalHandler`:

```python
select_parts = [
    '"dim_department"."org_unit_name" AS x',
    'SUM("fact_budget_events"."amount") AS y0',
]
group_cols = ['"dim_department"."org_unit_name"']
```

**The generated SQL:**

```sql
SELECT "dim_department"."org_unit_name" AS x,
       SUM("fact_budget_events"."amount") AS y0
FROM delta_scan('/shared/storage/silver/municipal/finance/facts/fact_budget_events') AS "fact_budget_events"
JOIN delta_scan('/shared/storage/silver/municipal/finance/dims/dim_department') AS "dim_department"
  ON "fact_budget_events"."department_description" = "dim_department"."org_unit_code"
WHERE "fact_budget_events"."event_type" = 'APPROPRIATION'
  AND "fact_budget_events"."fiscal_year" = 2025
GROUP BY "dim_department"."org_unit_name"
ORDER BY "dim_department"."org_unit_name" ASC
```

**Step 5: Execute and shape response**

```python
rows = self._execute(sql)  # Streams at most max_sql_rows rows
# -> [("POLICE", 1942107935.0), ("FIRE", 834526172.0), ("STREETS & SAN", 412830500.0), ...]

response = self._shape_graphical(rows, has_group=False, y_count=1)
# -> GraphicalResponse(
#        series=[SeriesData(name="Series 1", x=["POLICE", "FIRE", ...], y=[1942107935.0, 834526172.0, ...])],
#        truncated=False,
#    )
```

### 1.5 Domain Scoping

Domain scoping prevents cross-domain filter contamination on pages that contain exhibits from unrelated domains.

**The problem**: A page has both municipal finance and public safety exhibits. The user selects `event_type = APPROPRIATION` in the sidebar. Without scoping, the BFS join-path search would walk through shared tables like `dim_calendar` and accidentally join public safety tables to finance tables, producing enormous cross-domain joins and wrong results.

**The solution**: Each exhibit computes its **allowed domains** from its core domains plus their `depends_on` declarations.

```python
# Inside a handler's execute() method:

# 1. Collect domains from the exhibit's own fields
core_tables, core_domains = self._collect_tables_with_domains(core_fields)
# core_domains = {"municipal.public_safety"}

# 2. Expand to include depends_on
allowed = resolver.reachable_domains(core_domains)
# resolver._domain_deps["municipal.public_safety"] = {"temporal", "geospatial", "municipal.geospatial"}
# allowed = {"municipal.public_safety", "temporal", "geospatial", "municipal.geospatial"}

# 3. Resolve filters with domain scoping
filter_fields = self._resolve_filter_tables(
    req.filters, resolver, allowed_domains=allowed
)

# Filter "municipal.finance.event_type" resolves to domain "municipal.finance"
# "municipal.finance" NOT IN allowed -> filter is EXCLUDED
# Log: "Skipping out-of-scope filter 'municipal.finance.event_type' —
#        domain 'municipal.finance' not in {'municipal.public_safety', 'temporal', ...}"

# 4. BFS also respects allowed_domains
from_clause = self._build_from(tables, resolver, allowed_domains=allowed)
# BFS will not traverse into tables belonging to municipal.finance
```

This means each exhibit on a page independently decides which page-level filters apply to it. A public safety exhibit ignores finance filters; a finance exhibit ignores public safety filters. Shared dimensions like `temporal` are reachable by both because both declare `temporal` in their `depends_on`.

### 1.6 Response Handlers

Each handler shapes raw SQL rows into a typed response model that the Obsidian plugin knows how to render.

**GraphicalHandler** (`src/de_funk/api/handlers/graphical.py`):

Handles `plotly.line`, `plotly.bar`, `plotly.scatter`, `plotly.area`, `plotly.pie`, `plotly.heatmap`. Groups results by an optional `group_by` field to produce multiple series. Returns `GraphicalResponse` with `series: list[SeriesData]`, where each `SeriesData` has `name`, `x`, and `y` arrays.

```python
# Without group_by: one series per y field
GraphicalResponse(series=[
    SeriesData(name="Series 1", x=["POLICE", "FIRE", "STREETS & SAN"], y=[1942107935.0, 834526172.0, 412830500.0])
])

# With group_by="municipal.finance.event_type":
GraphicalResponse(series=[
    SeriesData(name="APPROPRIATION", x=[2023, 2024, 2025], y=[12800000000.0, 13400000000.0, 14200000000.0]),
    SeriesData(name="REVENUE", x=[2023, 2024, 2025], y=[12500000000.0, 13100000000.0, 13800000000.0]),
])
```

**PivotHandler** (`src/de_funk/api/handlers/pivot.py`):

Handles `table.pivot` and `great_table`. Supports 1D pivots (rows only), 2D pivots (rows + cols), multiple layout modes (`by_measure`, `by_column`, `by_dimension`), totals via `GROUPING SETS`, and window calculations (yoy, diff). Returns `GreatTablesResponse` with rendered HTML. When row count exceeds `MAX_HTML_ROWS` (400), it switches to hierarchical mode: subtotals as HTML, detail rows as `ExpandableData` JSON for client-side expand/collapse.

**TableDataHandler** (`src/de_funk/api/handlers/table_data.py`):

Handles `table.data`. Returns flat `TableResponse` with typed columns and row arrays.

**MetricsHandler** (`src/de_funk/api/handlers/metrics.py`):

Handles `cards.metric` and `kpi`. Returns `MetricResponse` with `metrics: list[MetricValue]`, each containing a key, label, value, and optional format string.

**BoxHandler** (`src/de_funk/api/handlers/box.py`):

Handles `plotly.box`, `ohlcv`, `candlestick`. In OHLCV mode, resolves open/high/low/close fields; in generic box mode, resolves a single y field grouped by a category.

### 1.7 Response Size Capping

All handlers enforce `max_response_mb` (configured in `configs/storage.json`). The engine estimates the JSON response size using a fast sampling method:

```python
# src/de_funk/api/executor.py

def truncate_to_mb(rows, columns, max_mb):
    max_bytes = int(max_mb * 1024 * 1024)
    sample = rows[:min(50, len(rows))]
    sample_bytes = len(json.dumps(sample, default=str).encode())
    bytes_per_row = sample_bytes / len(sample)
    estimated_total = bytes_per_row * len(rows)
    if estimated_total <= max_bytes:
        return rows, False          # Within budget
    max_rows = max(1, int(max_bytes / bytes_per_row))
    return rows[:max_rows], True    # Truncated
```

Graphical handlers cap points per series rather than truncating rows. Pivot handlers split into subtotal HTML + detail JSON when exceeding the cap.

---

## Part 2: Build Pipeline (Batch Path)

The build pipeline transforms raw Bronze data into dimensional Silver tables. It runs offline using Spark + Delta Lake.

### 2.1 Discovery

`DomainBuilderFactory` (`src/de_funk/models/base/domain_builder.py`) scans `domains/models/` for all `model.md` files and creates a dynamic builder class for each one:

```python
# src/de_funk/models/base/domain_builder.py

from de_funk.models.base.domain_builder import discover_domain_builders

builders = discover_domain_builders(repo_root)
print(sorted(builders.keys()))
# -> ['corporate.entity', 'corporate.finance', 'county.geospatial',
#     'county.property', 'municipal.entity', 'municipal.finance',
#     'municipal.geospatial', 'municipal.housing', 'municipal.operations',
#     'municipal.public_safety', 'municipal.regulatory',
#     'municipal.transportation', 'securities.master',
#     'securities.stocks', 'temporal']
```

Internally, `DomainBuilderFactory.create_builders()` does the following for each model:

```python
# 1. Use DomainConfigLoaderV4 to find all model.md files
loader = DomainConfigLoaderV4(domains_dir)

for model_name in loader.list_models():
    # 2. Load minimal config to get depends_on
    config = loader.load_model_config(model_name)
    depends = config.get("depends_on", [])

    # 3. Create a dynamic builder class with type()
    builder_class = type(
        f"DomainBuilder_{model_name}",
        (BaseModelBuilder,),
        {
            "model_name": model_name,
            "depends_on": depends,
            "get_model_class": ...,      # Returns DomainModel or custom class
            "get_model_config": ...,     # Loads + translates domain config
            "pre_build": ...,
            "post_build": ...,
        },
    )

    # 4. Register with BuilderRegistry
    BuilderRegistry.register(builder_class)
```

### 2.2 Dependency Resolution

Build order is determined by `depends_on` declarations in each `model.md`. `BuilderRegistry.get_build_order()` uses Kahn's algorithm (topological sort):

```python
# src/de_funk/models/base/builder.py

order = BuilderRegistry.get_build_order()
```

Visualizing the algorithm:

```
Initial in-degree computation:
  temporal:                0 deps  -> in_degree = 0
  municipal.entity:        [temporal]  -> in_degree = 1
  municipal.geospatial:    [geospatial, municipal.entity]  -> in_degree = 2
  county.geospatial:       [temporal]  -> in_degree = 1
  municipal.finance:       [temporal, municipal.entity, county.property]  -> in_degree = 3
  municipal.public_safety: [temporal, geospatial, municipal.geospatial]  -> in_degree = 3
  county.property:         [temporal, county.geospatial]  -> in_degree = 2
  ...

Round 1: Process queue = [temporal]  (in_degree == 0)
  Build temporal -> decrement dependents
  municipal.entity:        1 -> 0  (add to queue)
  county.geospatial:       1 -> 0  (add to queue)

Round 2: Process queue = [municipal.entity, county.geospatial]
  Build both -> decrement their dependents
  municipal.geospatial:    2 -> 0  (add to queue)
  county.property:         2 -> 0  (add to queue)

Round 3: Process queue = [municipal.geospatial, county.property]
  Build both -> decrement their dependents
  municipal.finance:       3 -> 0  (add to queue)
  municipal.public_safety: 3 -> 0  (add to queue)

Round 4: Build municipal.finance, municipal.public_safety, ...

Result: [temporal, municipal.entity, county.geospatial, ..., municipal.finance, ...]
```

If you request a subset of models, the algorithm automatically expands to include all required dependencies:

```python
order = BuilderRegistry.get_build_order(["municipal.finance"])
# Expands: municipal.finance depends on temporal, municipal.entity, county.property
#          county.property depends on temporal, county.geospatial
# -> ["temporal", "municipal.entity", "county.geospatial", "county.property", "municipal.finance"]
```

### 2.3 DomainBuilderFactory -- Model Class Selection

For each model, the factory determines whether to use a custom model class or the generic `DomainModel`:

```python
# src/de_funk/models/base/domain_builder.py

CUSTOM_MODEL_CLASSES = {
    "temporal": (
        "de_funk.models.domains.foundation.temporal.model",
        "TemporalModel",
    ),
    "corporate.entity": (
        "de_funk.models.domains.corporate.company.model",
        "CompanyModel",
    ),
    "securities.stocks": (
        "de_funk.models.domains.securities.stocks.model",
        "StocksModel",
    ),
}

# During get_model_class():
spec = CUSTOM_MODEL_CLASSES.get(model_name)
if spec:
    return _import_model_class(spec[0], spec[1])  # e.g., TemporalModel
else:
    from de_funk.models.base.domain_model import DomainModel
    return DomainModel  # Generic for all other models
```

| Model | Custom Class | Special Logic |
|-------|-------------|---------------|
| `temporal` | `TemporalModel` | Generates calendar dimension (2000-2050) from scratch |
| `corporate.entity` | `CompanyModel` | CIK-based company linkage, SEC identifiers |
| `securities.stocks` | `StocksModel` | Post-build technical indicators, market cap enrichment |
| All others | `DomainModel` | Config-driven build from graph.nodes |

All municipal models (`municipal.finance`, `municipal.public_safety`, `municipal.geospatial`, etc.) use the generic `DomainModel` -- their entire build logic is expressed declaratively in `model.md` frontmatter and table configs.

### 2.4 GraphBuilder -- Table Construction

Once a builder creates a model instance and calls `model.build()`, the `GraphBuilder` (`src/de_funk/models/base/graph_builder.py`) takes over. It iterates `graph.nodes` from the model config and builds each table.

```python
# src/de_funk/models/base/graph_builder.py

class GraphBuilder:
    def build(self):
        # 1. Call before_build hook
        self.model.before_build()

        # 2. Build all tables from graph.nodes config
        nodes = self._build_nodes()

        # 3. Separate by naming convention
        dims  = {k: v for k, v in nodes.items() if k.startswith("dim_")}
        facts = {k: v for k, v in nodes.items() if k.startswith("fact_")}

        # 4. Call after_build hook (model-specific customization)
        dims, facts = self.model.after_build(dims, facts)

        return dims, facts
```

For each node in `_build_nodes()`, the pipeline is:

```python
for node_id, node_config in node_items:

    # 1. Try custom loading first (DomainModel handles special node types)
    custom_df = self.model.custom_node_loading(node_id, node_config)
    if custom_df is not None:
        nodes[node_id] = custom_df
        continue

    # 2. Load source data based on from spec
    from_spec = node_config["from"]
    if from_spec.startswith("bronze."):
        # e.g., "bronze.chicago.budget_appropriations"
        df = self._load_bronze_table(table)
    elif "." in from_spec:
        # e.g., "municipal.entity.dim_municipality" (Silver cross-model)
        df = self._load_silver_table(model_name, table)
    else:
        # Internal reference to already-built node
        df = nodes[from_spec]

    # 3. Apply filters (push down to source data)
    if node_config.get("filters"):
        df = self.model._apply_filters(df, node_config["filters"])

    # 4. Apply joins (e.g., join IUCR code lookup)
    if node_config.get("join"):
        df = self._apply_joins(df, node_config["join"], nodes, node_id)

    # 5. Apply select (column selection + aliasing)
    if node_config.get("select"):
        df = self.model._select_columns(df, node_config["select"])

    # 6. Apply derive (computed columns via SQL expressions)
    if node_config.get("derive"):
        for out_name, expr in node_config["derive"].items():
            df = self._apply_derive(df, out_name, expr, node_id)

    # 7. Enforce unique_key deduplication
    if node_config.get("unique_key"):
        df = df.dropDuplicates(node_config["unique_key"])

    # 8. Drop temporary columns
    if node_config.get("drop"):
        df = df.drop(*node_config["drop"])

    nodes[node_id] = df
```

Bronze tables are loaded via `StorageRouter` which resolves logical table names to physical Delta Lake paths:

```python
# _load_bronze_table("chicago.budget_appropriations")
# -> Resolves to /shared/storage/bronze/chicago/budget_appropriations/
# -> spark.read.format("delta").option("mergeSchema", "true").load(path)
```

Silver cross-model tables are loaded with subdirectory inference:

```python
# _load_silver_table("municipal.geospatial", "dim_community_area")
# table starts with "dim_" -> subdir = "dims"
# -> silver/municipal/geospatial/dims/dim_community_area
```

### 2.5 DomainModel Node Types

`DomainModel` (`src/de_funk/models/base/domain_model.py`) extends the standard graph processing with specialized node types that can't be expressed as simple Bronze-to-Silver transforms:

| `from` Spec | Handler Method | Purpose | Example |
|-------------|----------------|---------|---------|
| `__seed__` | `_build_seed_node()` | Creates DataFrame from inline YAML data + derived expressions | Static lookup tables, category mappings |
| `__union__` | `_build_union_node()` | Loads multiple Bronze/Silver sources, applies unpivot/aliases, UNIONs them | Budget events from budget_appropriations + budget_revenue + budget_positions |
| `__generated__` | Deferred to post_build | Placeholder for post-build computed tables | Returns empty schema; filled by `ComputedColumnsEnricher` |
| `__distinct__` | `_build_distinct_node()` | SELECT DISTINCT with optional GROUP BY aggregation | Building dim_department from fact_ledger_entries keys |
| `_transform: window` | `_build_window_node()` | Applies technical indicators (EMA, MACD, RSI, Bollinger) | Technical indicator tables partitioned by security |
| `_transform: unpivot` | `_build_unpivot_node()` | Pivots wide-format data to long format | Wide financial columns to (line_item_code, value) rows |

A seed node example:

```python
# From YAML config:
# dim_location_type:
#   from: __seed__
#   data:
#     - {location_type_id: 1, location_type: "STREET", description: "Public street"}
#     - {location_type_id: 2, location_type: "APARTMENT", description: "Residential apartment"}
#     - {location_type_id: 3, location_type: "RESIDENCE", description: "Private residence"}

df = model._build_seed_node("dim_location_type", node_config)
# Creates a Spark DataFrame with 3 rows from the inline data
# Then applies any {derived: "expr"} columns from the schema
```

A distinct node example:

```python
# Build dim_department from fact_ledger_entries + fact_budget_events
# dim_department:
#   from: __distinct__
#   _distinct_from: fact_ledger_entries
#   union_from: [fact_ledger_entries, fact_budget_events]
#   _distinct_group_by: [organizational_unit]

df = model._build_distinct_node("dim_department", node_config)
# SELECT DISTINCT organizational_unit, ... FROM fact_ledger_entries UNION fact_budget_events
# Then applies derived columns (org_unit_id = ABS(HASH(...))) and enrichment JOINs
```

### 2.6 ModelWriter -- Persisting to Silver

After `GraphBuilder.build()` produces dimensions and facts, `ModelWriter` (`src/de_funk/models/base/model_writer.py`) persists them to Delta Lake:

```python
# src/de_funk/models/base/model_writer.py

model.write_tables()

# Internally:
# 1. Determine output root: /shared/storage/silver/{model_name}/
# 2. Write each dimension: silver/{model}/dims/{table_name}/
# 3. Write each fact:      silver/{model}/facts/{table_name}/
# 4. Format: Delta Lake with overwriteSchema=true
# 5. Auto-vacuum (default): remove old Delta versions immediately

# Example output:
# /shared/storage/silver/municipal/finance/dims/dim_department/
# /shared/storage/silver/municipal/finance/dims/dim_vendor/
# /shared/storage/silver/municipal/finance/dims/dim_fund/
# /shared/storage/silver/municipal/finance/facts/fact_budget_events/
# /shared/storage/silver/municipal/finance/facts/fact_ledger_entries/
```

The writer uses Delta Lake's `overwriteSchema` option to handle schema evolution automatically. Auto-vacuum is enabled by default to save storage (disabling time travel). To enable time travel for a specific model, set `storage.auto_vacuum: false` in the model's markdown frontmatter.

### 2.7 Post-Build Enrichments

After the main build, `ComputedColumnsEnricher` (`src/de_funk/models/base/enrichers.py`) handles cross-table computed columns declared in `build.post_build`:

```yaml
# In dim_department table config (enrich section):
enrich:
  - from: fact_ledger_entries
    join: [organizational_unit = org_unit_code]
    columns:
      - [total_paid, "decimal(18,2)", true, "Total actual spending", {derived: "SUM(transaction_amount)"}]
      - [payment_count, integer, true, "Number of payments", {derived: "COUNT(DISTINCT entry_id)"}]
  - from: fact_budget_events
    join: [department_description = org_unit_code]
    filter: "event_type = 'APPROPRIATION'"
    columns:
      - [total_appropriated, "decimal(18,2)", true, "Total budgeted", {derived: "SUM(amount)"}]
  - derived:
      - [budget_variance, "decimal(18,2)", true, "Budget minus actual", {derived: "COALESCE(total_appropriated, 0) - COALESCE(total_paid, 0)"}]
      - [budget_utilization_pct, "decimal(5,4)", true, "% of budget used", {derived: "COALESCE(total_paid, 0) / NULLIF(total_appropriated, 0)"}]
```

The enricher processes each column tuple:

```python
# src/de_funk/models/base/enrichers.py

enricher = ComputedColumnsEnricher()
enricher.run(spark, storage_config, graph_cfg, step)

# For "total_paid" (aggregate from fact_ledger_entries):
# 1. Load fact_ledger_entries
# 2. GROUP BY organizational_unit, compute SUM(transaction_amount)
# 3. Join onto dim_department via organizational_unit = org_unit_code

# For "total_appropriated" (filtered aggregate from fact_budget_events):
# 1. Load fact_budget_events WHERE event_type = 'APPROPRIATION'
# 2. GROUP BY department_description, compute SUM(amount)
# 3. Join onto dim_department via department_description = org_unit_code

# For "budget_variance" (inline expression):
# 1. Evaluate: F.expr("COALESCE(total_appropriated, 0) - COALESCE(total_paid, 0)")
# 2. Positive = under budget, negative = over budget

# For "budget_utilization_pct" (inline expression):
# 1. Evaluate: F.expr("COALESCE(total_paid, 0) / NULLIF(total_appropriated, 0)")

# Final: Delta MERGE into dim_department with autoMerge for schema evolution
```

The enricher supports a catalog of window functions (`last_by`, `first_by`, `sum_all`, `avg_all`) and expression functions (`multiply`, `divide`, `add`, `subtract`), plus arbitrary inline SQL expressions.

---

## Part 3: Backend Abstraction

de_Funk uses two backends for different purposes. Application code accesses them through the `UniversalSession` abstraction rather than importing `duckdb` or `pyspark` directly.

```python
from de_funk.models.api.session import UniversalSession

session = UniversalSession(backend="duckdb")
df = session.query("SELECT org_unit_name, amount FROM fact_budget_events LIMIT 10")
```

**Backend selection rules:**

| Use Case | Backend | Rationale |
|----------|---------|-----------|
| Silver model building (ETL) | **Spark** | Batch transforms, Delta Lake writes, schema evolution |
| Bronze ingestion | **Spark** | Rate-limited API calls, incremental Delta appends |
| Interactive queries (API) | **DuckDB** | Sub-second point queries, BI analytics |
| Notebook execution | **DuckDB** | User-facing, needs speed |
| Post-build enrichment | **Spark** | Delta MERGE operations |
| Unit tests | **DuckDB** | In-memory, fast isolation |

**Decision tree:**

```
Is this a scheduled/batch operation?
  YES -> Use Spark
  NO  -> Is this user-facing (UI/API/notebook)?
           YES -> Use DuckDB
           NO  -> Is it a full table scan or heavy aggregation?
                   YES -> Use Spark
                   NO  -> Use DuckDB (default for queries)
```

The query pipeline (Part 1) always uses DuckDB. The build pipeline (Part 2) always uses Spark. The `QueryEngine` in the API layer creates its own DuckDB connection with Delta extension at startup and manages it for the lifetime of the process.

---

## Part 4: Data Storage

### Two-Layer Architecture

| Layer | Format | Path | Queryable | Purpose |
|-------|--------|------|-----------|---------|
| **Bronze** | Delta Lake | `/shared/storage/bronze/{provider}/{endpoint}/` | Yes — `/api/bronze/query` | Raw API data, partitioned by snapshot date. Mirrors API response structure. |
| **Silver** | Delta Lake | `/shared/storage/silver/{domain}/{subdomain}/{dims\|facts}/{table}/` | Yes — `/api/query` | Dimensional snowflake schemas with automatic joins via graph edges. |

There is no separate Gold layer. DuckDB queries both Bronze and Silver directly for interactive analytics. Bronze queries are single-table scans (no joins); Silver queries use BFS-based automatic joins across the domain graph.

### Storage Path Resolution

Canonical domain names map to filesystem paths via two mechanisms:

**Default mapping**: Replace dots with slashes.
```
municipal.finance     -> silver/municipal/finance/
municipal.geospatial  -> silver/municipal/geospatial/
county.property       -> silver/county/property/
temporal              -> silver/temporal/
```

**Explicit overrides**: The `domain_roots` section in `configs/storage.json` maps domain names to non-default paths (e.g., `"municipal.finance": "municipal/chicago/finance"`).

Within each domain directory, tables are organized by type:
```
silver/municipal/finance/
  dims/
    dim_department/          <- Delta table directory
    dim_vendor/
    dim_fund/
    dim_contract/
    dim_chart_of_accounts/
  facts/
    fact_budget_events/
    fact_ledger_entries/
    fact_property_tax/
```

### Delta Lake Features

All Bronze and Silver tables use Delta Lake format, providing:

- **ACID transactions**: Reliable concurrent reads/writes
- **Schema evolution**: `mergeSchema` and `overwriteSchema` handle new columns automatically
- **Efficient upserts**: Post-build enrichments use Delta MERGE
- **Auto-detection**: The `QueryEngine._safe_scan()` probes for Delta format and falls back to Parquet glob if unavailable

Time travel is disabled by default (auto-vacuum removes old versions). Enable it per-model by setting `storage.auto_vacuum: false` in the model's markdown frontmatter.

---

## Cross-References

- [Domain Models](domain-models.md) -- Model catalog, YAML frontmatter reference, graph edges
- [API Reference](api.md) -- Endpoint details, request/response formats
- [Data Pipeline](data-pipeline.md) -- Bronze ingestion, Silver builds, providers
- [Internals](internals.md) -- Config, logging, errors, measures, filters, storage routing
- [Obsidian Plugin](obsidian-plugin.md) -- Exhibit blocks, frontmatter controls, plugin architecture
