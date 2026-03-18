# de_Funk

**de_Funk** is a graph-based analytical data warehouse that turns markdown domain configs into a queryable snowflake-schema like layer over a Delta Lake. It serves as an nteractive analytics — charts, tables, pivots, metric cards — directly inside Obsidian notes. 

## History

**de_Funk** started as a homelab setup goal from the idea of bringing dispart sources of information into a single interactive queryable space. The goal to simplify the interaction of data sources and create a news paper experience of open source data feeds. 

## The Core Idea: Markdown is the Config

Everything in de_Funk is defined in markdown files with YAML frontmatter. The framework reads these files as its configuration — there is no separate config language, no JSON schemas, no admin UI. The same markdown files you read in Obsidian are the ones the pipeline executes against.

A **domain model** is a directory of markdown files:

```
domains/models/municipal/
  finance/
    model.md                          ← Domain definition (dependencies, graph edges, measures)
    tables/
      fact_budget_events.md           ← Fact table schema (columns, types, partitions)
      dim_department.md               ← Dimension definition (transform, enrich)
      dim_vendor.md
  sources/                            ← All sources grouped at domain-group level
    chicago/                          ← Entity: City of Chicago
      finance/
        budget_appropriations.md      ← Source mapping (API field → schema column aliases)
        budget_revenue.md
        contracts.md
      public_safety/
        crimes.md
```

Each file has YAML frontmatter that the build pipeline reads:

- **`model.md`** declares dependencies (`depends_on`), graph edges (join keys), measures, and storage routing
- **Table files** define the dimensional schema — column names, types, nullable flags, and how dimensions are derived (distinct, union, aggregate)
- **Source files** map external API field names to the canonical schema — this is how raw Chicago Data Portal columns become your dimensional model

**Data providers and API endpoints** are also markdown configs:

```
data_sources/
  Providers/
    Chicago Data Portal.md            ← base_url, auth_model, rate_limit_per_sec, default_headers
    Cook County Data Portal.md
    Alpha Vantage.md
  Endpoints/
    Chicago Data Portal/
      Public Safety/
        Crimes.md                     ← endpoint_pattern, schema, pagination, write_strategy, key_columns
        Arrests.md
      Finance/
        Chicago Budget Ordinance - Appropriations.md
        Contracts.md
      Transportation/
        CTA L Ridership - Daily Totals.md
    Cook County Data Portal/
      Finance/
        Assessed Values.md
        Parcel Sales.md
```

The provider Python code (`ChicagoProvider`, `CookCountyProvider`) reads these frontmatter configs at runtime. The Crimes endpoint file defines the Socrata resource ID (`/resource/ijzp-q8t2.json`), the schema mapping (API column → Bronze column), pagination strategy, write mode (upsert on `id`), and partition key (`year`) — all in YAML frontmatter.

This design means:
- **Adding a data source** = writing markdown files describing the provider, endpoints, and field mappings — not Python code
- **Documentation and config are the same artifact** — your model docs and API docs are always in sync because they *are* the config
- **Obsidian is the IDE** — you browse, search, and edit domain models and data source configs in the same tool where you view the analytics

## What It Does

1. **Ingest** — Pull data from open APIs (Chicago Data Portal, Cook County, Alpha Vantage) into a Bronze layer of raw Delta Lake tables
2. **Build** — Read the markdown configs, resolve the dependency graph, and transform Bronze into Silver dimensional models (fact + dimension tables) via Spark
3. **Query** — A FastAPI backend resolves field references across domains, builds joins from the graph edges defined in `model.md`, and executes SQL against DuckDB
4. **Visualize** — An Obsidian plugin renders `de_funk` code blocks as interactive charts, tables, pivots, and metric cards — querying the API in real time

## Architecture at a Glance

```
Obsidian Note                 FastAPI                    DuckDB
┌─────────────┐    POST     ┌──────────────┐  SQL     ┌──────────────┐
│ ```de_funk   │──────────→│ FieldResolver │────────→│ Silver Layer │
│ type: ...    │            │ BronzeResolver│────────→│ Bronze Layer │
│ rows: [...]  │←──────────│ QueryEngine   │←────────│ (Delta Lake) │
│ ```          │  JSON/HTML │ Handlers      │          └──────────────┘
└─────────────┘             └──────────────┘                  ↑
                                                       Build Pipeline
                                                       (Spark reads YAML
                                                        from markdown)
                                                              ↑
                                                        Bronze Layer
                                                        (Raw API Data)
```

The markdown files in `domains/models/` drive both the build pipeline (Spark reads them to know what tables to create and how to join them) and the query pipeline (the API reads them to resolve field references and build SQL joins).

## Quick Start

Get Chicago municipal data flowing in 5 steps. Assumes Python 3.10+, Java 17+ (for Spark), and Node 18+ (for the plugin).

### 1. Install

```bash
git clone <repo-url> && cd de_Funk
pip install -e ".[all]"
cp .env.example .env
# Edit .env — add your free Chicago Data Portal app token (optional but recommended)
# Get one at: https://data.cityofchicago.org/profile/app_tokens
```

### 2. Seed foundation data

```bash
python -m scripts.seed.seed_calendar --storage-path /shared/storage
python -m scripts.seed.seed_geography --storage-path /shared/storage
```

### 3. Ingest Chicago data

```python
from de_funk.orchestration.common.spark_session import get_spark
from de_funk.pipelines.providers.chicago import create_chicago_provider
from de_funk.pipelines.providers.cook_county import create_cook_county_provider
from de_funk.pipelines.base.ingestor_engine import IngestorEngine
from de_funk.config.loader import ConfigLoader
from de_funk.utils.repo import get_repo_root
from pathlib import Path
import json

repo_root = get_repo_root()
storage_path = Path("/shared/storage")
spark = get_spark("Ingestion")

with open(repo_root / "configs" / "storage.json") as f:
    storage_cfg = json.load(f)

# Chicago Data Portal — crimes, budgets, inspections, permits, transit
provider = create_chicago_provider(spark=spark, docs_path=repo_root, storage_path=storage_path)
engine = IngestorEngine(provider, storage_cfg)
results = engine.run(work_items=["crimes", "budget_appropriations", "food_inspections"])
print(f"Chicago: {results.total_errors} errors")

# Cook County — property assessments and sales
provider = create_cook_county_provider(spark=spark, docs_path=repo_root, storage_path=storage_path)
engine = IngestorEngine(provider, storage_cfg)
results = engine.run(work_items=["assessments", "parcel_sales"])
print(f"Cook County: {results.total_errors} errors")

spark.stop()
```

### 4. Build Silver models

```bash
python -m scripts.build.build_models \
    --models municipal.public_safety municipal.finance municipal.regulatory county.property \
    --storage-root /shared/storage
```

### 5. Start the API and open Obsidian

```bash
python -m scripts.serve.run_api --port 8765
```

Then in any Obsidian note:

````markdown
```de_funk
type: plotly.bar
domain: municipal.finance
rows: [municipal.finance.department_description]
measures:
  - key: municipal.finance.amount
    agg: sum
    format: "$#,##0"
filters:
  event_type: APPROPRIATION
  fiscal_year: 2024
formatting:
  title: "Chicago Budget by Department (2024)"
```
````

See [Operations](operations.md) for the full walkthrough with all options and diagnostics.

---

## Guides

Comprehensive walkthrough guides written in notebook style with executable code examples, CLI commands, and step-by-step explanations.

| Document | Description | Start Here If... |
|----------|-------------|------------------|
| [Operations](operations.md) | Full pipeline walkthrough: setup, seed, ingest, build, serve, query, test, maintain | You want to get the system running |
| [Architecture](architecture.md) | Query pipeline, build pipeline, backend abstraction — with worked examples | You want to understand how it works |
| [Domain Models](domain-models.md) | Creating and configuring models: catalog, YAML frontmatter, inheritance, graph edges | You need to add or modify a domain |
| [Data Pipeline](data-pipeline.md) | Bronze ingestion: providers, facets, IngestorEngine, BronzeSink, Silver builds | You need to add a data source |
| [API Reference](api.md) | FastAPI endpoints with curl/Python examples, handler details, query flow | You're building exhibits or querying data |
| [Obsidian Plugin](obsidian-plugin.md) | Exhibit blocks, frontmatter filters, controls, complete dashboard tutorial | You're creating Obsidian dashboards |
| [Internals](internals.md) | Config, logging, exceptions, measures, filters, storage routing — with class examples | You're working on framework internals |

## Reference

| Location | Description |
|----------|-------------|
| [Python Reference](python-reference.md) | Every Python class and method — purpose, inputs/outputs, why it exists |
| [domains/_model_guides_/](../domains/_model_guides_/) | YAML frontmatter syntax reference for model.md files |
| [exhibits/_index.md](../exhibits/_index.md) | Exhibit type catalog (chart, table, metric, control) |
| [data_sources/](../data_sources/) | API provider configs and endpoint documentation |
| [proposals/](proposals/) | Accepted architectural proposals (005, 008) |
| [scripts/examples/](../scripts/examples/) | Runnable code examples (queries, measures, extending, backends) |
| [CLAUDE.md](../CLAUDE.md) | AI assistant guide — code quality rules, conventions |
