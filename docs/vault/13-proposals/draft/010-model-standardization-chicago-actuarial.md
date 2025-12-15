# Proposal 010: Model Standardization & Chicago Actuarial Forecast

**Status**: Draft
**Created**: 2025-12-15
**Author**: Claude (AI Assistant)
**Priority**: High

---

## Executive Summary

This proposal provides a step-by-step roadmap for:

1. **Model Standardization**: Clean up inconsistencies, remove legacy code, create unified patterns
2. **Chicago Actuarial Forecast Model**: Build comprehensive municipal economic analysis
3. **Orchestration Improvements**: Unified build/ingest system for all models and providers

This is a **planning document** - implementation should follow after approval.

---

## Table of Contents

1. [Current Architecture Assessment](#part-1-current-architecture-assessment)
2. [Target Architecture](#part-2-target-architecture)
3. [Model Build Flow - Current vs Target](#part-3-model-build-flow)
4. [Ingestion Flow - Current vs Target](#part-4-ingestion-flow)
5. [Files to Remove](#part-5-files-to-remove)
6. [Files to Create](#part-6-files-to-create)
7. [Files to Modify](#part-7-files-to-modify)
8. [Step-by-Step Implementation Tasks](#part-8-step-by-step-implementation-tasks)
9. [Chicago Actuarial Model Design](#part-9-chicago-actuarial-model-design)

---

## Part 1: Current Architecture Assessment

### Directory Structure Rating

| Component | Rating | Key Issues |
|-----------|--------|------------|
| `configs/models/` | ⚠️ 6/10 | Mixed v1.x/v2.0 patterns, duplicate deprecated files |
| `models/implemented/` | ⚠️ 6/10 | Backend branching, inconsistent model patterns |
| `models/base/` | ✅ 8/10 | Well-structured composition, clean abstractions |
| `configs/exhibits/` | ⚠️ 5/10 | Only `great_table` has presets, others missing |
| `datapipelines/providers/` | ✅ 7/10 | Consistent facet pattern, needs registry |
| `orchestration/` | ⚠️ 5/10 | Checkpoint exists but no unified orchestrator |
| `scripts/` | ⚠️ 6/10 | Fragmented - many overlapping scripts |

### Current Model Configuration Layout

```
configs/models/
├── core.yaml              # ❌ v1.x ONLY - needs migration
├── company.yaml           # ❌ DEPRECATED - delete (v2.0 exists in company/)
├── etf.yaml               # ❌ DEPRECATED - delete (v2.0 exists in etfs/)
├── forecast.yaml          # ❌ v1.x ONLY - needs migration
├── _base/                 # ✅ Base templates for inheritance
│   └── securities/
├── company/               # ✅ v2.0 modular
├── stocks/                # ✅ v2.0 modular
├── options/               # ✅ v2.0 modular (partial implementation)
├── etfs/                  # ✅ v2.0 modular (naming: plural vs singular)
├── futures/               # ✅ v2.0 modular (skeleton)
├── macro/                 # ✅ v2.0 modular
└── city_finance/          # ✅ v2.0 modular
```

### Current Implemented Models Layout

```
models/implemented/
├── core/
│   └── model.py           # ⚠️ Spark-only, needs backend abstraction
├── company/
│   ├── model.py           # ⚠️ 6 backend if-statements
│   └── services.py        # ❌ ORPHANED - not used by model.py
├── stocks/
│   ├── model.py           # ⚠️ 9 backend if-statements
│   └── measures.py        # ⚠️ 6 backend if-statements
├── options/               # ⚠️ Skeleton only
├── etfs/                  # ⚠️ No model.py (only __init__)
├── futures/               # ⚠️ Skeleton only
├── macro/
│   └── model.py           # ✅ Relatively clean
├── city_finance/
│   └── model.py           # ✅ Current implementation
└── forecast/
    └── model.py           # ⚠️ Uses legacy patterns
```

### Key Problem: Backend Branching

**21+ instances** of backend-specific code scattered across models:

```python
# Pattern found 21+ times across codebase:
if self._backend == 'spark':
    return df.filter(df.column == value)
else:
    return df[df['column'] == value]
```

**Where it appears:**
- `models/implemented/company/model.py` - 6 instances
- `models/implemented/stocks/model.py` - 9 instances
- `models/implemented/stocks/measures.py` - 6 instances

**Root cause:** Models bypass the filter abstraction in `core/session/filters.py`

---

## Part 2: Target Architecture

### Target Model Configuration Layout

```
configs/models/
├── _base/                 # Shared templates
│   └── securities/        # Securities base schema/graph/measures
├── core/                  # ✅ MIGRATE from v1.x
│   ├── model.yaml
│   ├── schema.yaml
│   └── graph.yaml
├── company/               # Existing v2.0
├── stocks/                # Existing v2.0
├── options/               # Complete implementation
├── etf/                   # ✅ RENAME from etfs/ (singular convention)
├── futures/               # Complete implementation
├── macro/                 # Existing v2.0
├── city_finance/          # Existing v2.0
├── chicago_actuarial/     # ✅ NEW - actuarial forecast model
└── forecast/              # ✅ MIGRATE from v1.x

# DELETED:
# - core.yaml (migrated to core/)
# - company.yaml (deprecated duplicate)
# - etf.yaml (deprecated duplicate)
# - forecast.yaml (migrated to forecast/)
```

### Target Implemented Models Layout

```
models/implemented/
├── core/
│   └── model.py           # ✅ Refactored with QueryHelper
├── company/
│   └── model.py           # ✅ Refactored - remove backend branching
├── stocks/
│   ├── model.py           # ✅ Refactored - remove backend branching
│   └── measures.py        # ✅ Refactored - remove backend branching
├── etf/                   # ✅ RENAMED from etfs/
│   ├── model.py           # ✅ NEW - actual implementation
│   └── measures.py        # ✅ NEW - Python measures
├── options/
│   ├── model.py           # ✅ NEW - actual implementation
│   └── measures.py        # ✅ NEW - Black-Scholes, Greeks
├── futures/
│   ├── model.py           # ✅ NEW - actual implementation
│   └── measures.py        # ✅ NEW - roll calculations
├── macro/
│   └── model.py           # Existing
├── city_finance/
│   └── model.py           # Existing
├── chicago_actuarial/     # ✅ NEW
│   ├── model.py
│   └── measures.py        # Actuarial calculations
└── forecast/
    └── model.py           # ✅ Refactored
```

### New Base Helper Layer

```
models/base/
├── model.py               # Existing BaseModel
├── graph_builder.py       # Existing
├── table_accessor.py      # Existing
├── measure_calculator.py  # Existing
├── model_writer.py        # Existing
└── query_helpers.py       # ✅ NEW - backend-agnostic operations
```

---

## Part 3: Model Build Flow

### Current Flow (Fragmented)

```
┌─────────────────────────────────────────────────────────────────┐
│                     CURRENT BUILD FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Entry Points (FRAGMENTED):                                     │
│  ┌────────────────────┐  ┌────────────────────┐                │
│  │ run_full_pipeline  │  │ build_silver_duckdb│                │
│  │ .py                │  │ .py                │                │
│  └─────────┬──────────┘  └─────────┬──────────┘                │
│            │                       │                            │
│  ┌─────────┴──────────┐  ┌────────┴───────────┐                │
│  │ build_company_     │  │ rebuild_model.py   │                │
│  │ model.py           │  │                    │                │
│  └─────────┬──────────┘  └────────┬───────────┘                │
│            │                       │                            │
│            └───────────┬───────────┘                            │
│                        ▼                                        │
│           ┌────────────────────────┐                            │
│           │  HARDCODED MODEL LIST  │  ← Problem: Not dynamic    │
│           │  ['stocks', 'company'] │                            │
│           └────────────┬───────────┘                            │
│                        │                                        │
│                        ▼                                        │
│           ┌────────────────────────┐                            │
│           │  Import Model Class    │  ← Problem: Manual imports │
│           │  Directly              │                            │
│           └────────────┬───────────┘                            │
│                        │                                        │
│                        ▼                                        │
│           ┌────────────────────────┐                            │
│           │  model.build()         │                            │
│           │  model.write_tables()  │                            │
│           └────────────────────────┘                            │
│                                                                 │
│  Problems:                                                      │
│  1. Multiple entry points - confusing                           │
│  2. Hardcoded model lists - not extensible                      │
│  3. No dependency resolution - manual ordering                  │
│  4. No checkpoint/resume - starts from scratch                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Target Flow (Unified)

```
┌─────────────────────────────────────────────────────────────────┐
│                     TARGET BUILD FLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Single Entry Point:                                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  python -m scripts.orchestrate --models stocks --build-only │ │
│  │  python -m scripts.orchestrate --all                        │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                 │
│                               ▼                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    ORCHESTRATOR                             │ │
│  │  scripts/orchestrate.py                                     │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                 │
│         ┌─────────────────────┼─────────────────────┐           │
│         │                     │                     │           │
│         ▼                     ▼                     ▼           │
│  ┌──────────────┐    ┌───────────────┐    ┌───────────────────┐ │
│  │ Dependency   │    │ Checkpoint    │    │ Provider          │ │
│  │ Graph        │    │ Manager       │    │ Registry          │ │
│  │              │    │               │    │                   │ │
│  │ Reads YAML   │    │ Resume from   │    │ Discovers         │ │
│  │ depends_on   │    │ failure       │    │ providers         │ │
│  │              │    │               │    │                   │ │
│  │ Topological  │    │ Tracks        │    │ Knows which       │ │
│  │ Sort         │    │ progress      │    │ models each feeds │ │
│  └──────┬───────┘    └───────────────┘    └───────────────────┘ │
│         │                                                       │
│         │  Returns ordered list:                                │
│         │  [core, company, stocks] (auto-resolved)              │
│         │                                                       │
│         ▼                                                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    MODEL BUILDER                            │ │
│  │  orchestration/builders/model_builder.py (NEW)              │ │
│  │                                                             │ │
│  │  1. Load model config from configs/models/{name}/           │ │
│  │  2. Dynamically import model class                          │ │
│  │  3. Call model.build()                                      │ │
│  │  4. Call model.write_tables()                               │ │
│  │  5. Update checkpoint                                       │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                 │
│                               ▼                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    MODEL CLASS                              │ │
│  │  models/implemented/{name}/model.py                         │ │
│  │                                                             │ │
│  │  Inherits: BaseModel                                        │ │
│  │  Uses: QueryHelper (no backend branching)                   │ │
│  │                                                             │ │
│  │  build() → returns (dimensions, facts)                      │ │
│  │  write_tables() → persists to silver layer                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Model Class Location Decision

**Question:** Where does the build code for a single model live?

**Answer:**

```
┌────────────────────────────────────────────────────────────────────┐
│                    MODEL BUILD CODE LOCATION                        │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  CONFIGURATION (What to build):                                    │
│  configs/models/{model_name}/                                      │
│  ├── model.yaml       # Metadata, dependencies, storage config     │
│  ├── schema.yaml      # Table definitions (dims, facts, columns)   │
│  ├── graph.yaml       # Node/edge/path definitions                 │
│  └── measures.yaml    # Measure definitions (simple + Python refs) │
│                                                                    │
│  IMPLEMENTATION (How to build):                                    │
│  models/implemented/{model_name}/                                  │
│  ├── model.py         # Model class extending BaseModel            │
│  │                    # Contains: build(), custom methods          │
│  └── measures.py      # Python measures (complex calculations)     │
│                                                                    │
│  BASE FRAMEWORK (Shared logic):                                    │
│  models/base/                                                      │
│  ├── model.py         # BaseModel - orchestrates build process     │
│  ├── graph_builder.py # Builds graph from YAML config              │
│  ├── table_accessor.py# Reads tables from bronze/silver            │
│  ├── model_writer.py  # Writes tables to silver layer              │
│  └── query_helpers.py # Backend-agnostic operations (NEW)          │
│                                                                    │
│  ORCHESTRATION (When/order to build):                              │
│  orchestration/                                                    │
│  ├── dependency_graph.py  # Resolves build order                   │
│  ├── checkpoint.py        # Tracks progress, enables resume        │
│  └── builders/                                                     │
│      └── model_builder.py # Builds single model (NEW)              │
│                                                                    │
│  ENTRY POINT (User interface):                                     │
│  scripts/orchestrate.py   # Unified CLI                            │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Part 4: Ingestion Flow

### Current Flow (Fragmented)

```
┌─────────────────────────────────────────────────────────────────┐
│                   CURRENT INGESTION FLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Entry Points (MULTIPLE):                                       │
│  ┌────────────────────┐                                         │
│  │ run_full_pipeline  │ ← Only Alpha Vantage hardcoded          │
│  │ .py                │                                         │
│  └─────────┬──────────┘                                         │
│            │                                                    │
│            ▼                                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  HARDCODED PROVIDER                                         │ │
│  │  from datapipelines.providers.alpha_vantage import ...     │ │
│  │                                                             │ │
│  │  Problems:                                                  │ │
│  │  - Chicago/BLS ingestion not integrated                    │ │
│  │  - No provider discovery                                   │ │
│  │  - Can't select which providers to run                     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Separate Scripts (NOT INTEGRATED):                             │
│  - Chicago: No unified entry point                              │
│  - BLS: No unified entry point                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Target Flow (Unified)

```
┌─────────────────────────────────────────────────────────────────┐
│                   TARGET INGESTION FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Single Entry Point:                                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  python -m scripts.orchestrate --providers chicago         │ │
│  │  python -m scripts.orchestrate --providers all --ingest    │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                 │
│                               ▼                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                  PROVIDER REGISTRY                          │ │
│  │  datapipelines/providers/registry.py                        │ │
│  │                                                             │ │
│  │  Discovers from provider.yaml files:                        │ │
│  │  - alpha_vantage → feeds: stocks, company                   │ │
│  │  - bls → feeds: macro                                       │ │
│  │  - chicago → feeds: city_finance, chicago_actuarial         │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                 │
│         ┌─────────────────────┼─────────────────────┐           │
│         │                     │                     │           │
│         ▼                     ▼                     ▼           │
│  ┌──────────────┐    ┌───────────────┐    ┌───────────────────┐ │
│  │ Alpha        │    │ BLS           │    │ Chicago           │ │
│  │ Vantage      │    │ Ingestor      │    │ Ingestor          │ │
│  │ Ingestor     │    │               │    │                   │ │
│  │              │    │ Endpoint:     │    │ Endpoints:        │ │
│  │ Endpoints:   │    │ - series_data │    │ - budget          │ │
│  │ - overview   │    │ - catalog     │    │ - employees       │ │
│  │ - prices     │    │               │    │ - contracts       │ │
│  │ - income     │    │ Facets:       │    │ - tax_assessment  │ │
│  │ - balance    │    │ - BLSSeries   │    │ - community_areas │ │
│  │ - cash_flow  │    │               │    │                   │ │
│  │ - earnings   │    │               │    │ Facets:           │ │
│  │              │    │               │    │ - ChicagoBudget   │ │
│  │ Facets:      │    │               │    │ - TaxAssessment   │ │
│  │ - Reference  │    │               │    │ - CommunityArea   │ │
│  │ - Prices     │    │               │    │                   │ │
│  │ - Income     │    │               │    │                   │ │
│  │ etc.         │    │               │    │                   │ │
│  └──────┬───────┘    └───────┬───────┘    └─────────┬─────────┘ │
│         │                    │                      │           │
│         └────────────────────┼──────────────────────┘           │
│                              ▼                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    BRONZE SINK                              │ │
│  │  datapipelines/ingestors/bronze_sink.py                     │ │
│  │                                                             │ │
│  │  Writes to: storage/bronze/{provider}/{table}/              │ │
│  │  Format: Delta Lake (ACID, time travel, schema evolution)   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Provider-to-Model Mapping

```
┌────────────────────────────────────────────────────────────────────┐
│                  PROVIDER → MODEL RELATIONSHIP                      │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Provider          Bronze Tables              Models Fed           │
│  ──────────────────────────────────────────────────────────────── │
│  alpha_vantage  →  securities_reference    →  stocks, company      │
│                    securities_prices_daily →  stocks               │
│                    income_statements       →  company              │
│                    balance_sheets          →  company              │
│                    cash_flows              →  company              │
│                    earnings                →  company              │
│                                                                    │
│  bls            →  bls_series_data         →  macro                │
│                    bls_series_catalog      →  macro                │
│                                                                    │
│  chicago        →  chicago_budget          →  city_finance         │
│                    chicago_employees       →  city_finance         │
│                    chicago_contracts       →  city_finance         │
│                    chicago_tax_assessment  →  chicago_actuarial    │
│                    chicago_community_areas →  chicago_actuarial    │
│                                                                    │
│  Encoded in: datapipelines/providers/{name}/provider.yaml          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Part 5: Files to Remove

| File | Reason | Action |
|------|--------|--------|
| `configs/models/company.yaml` | Deprecated v1.x, v2.0 exists in `company/` | DELETE |
| `configs/models/etf.yaml` | Deprecated v1.x, v2.0 exists in `etfs/` | DELETE |
| `models/implemented/company/services.py` | Orphaned - not used by model.py | DELETE |
| `scripts/build_company_model.py` | Fragmented - use orchestrate.py | DELETE after migration |
| `scripts/build_silver_duckdb.py` | Fragmented - use orchestrate.py | DELETE after migration |

**Note:** Keep `run_full_pipeline.py` temporarily as deprecated wrapper, then delete.

---

## Part 6: Files to Create

### New Files Needed

| File | Purpose | Priority |
|------|---------|----------|
| `configs/models/core/model.yaml` | v2.0 modular config for core | High |
| `configs/models/core/schema.yaml` | Core schema definition | High |
| `configs/models/core/graph.yaml` | Core graph definition | High |
| `configs/models/forecast/model.yaml` | v2.0 modular config for forecast | Medium |
| `configs/models/forecast/schema.yaml` | Forecast schema | Medium |
| `configs/models/forecast/graph.yaml` | Forecast graph | Medium |
| `configs/models/chicago_actuarial/model.yaml` | New actuarial model config | High |
| `configs/models/chicago_actuarial/schema.yaml` | Actuarial schema | High |
| `configs/models/chicago_actuarial/graph.yaml` | Actuarial graph | High |
| `configs/models/chicago_actuarial/measures.yaml` | Actuarial measures | High |
| `models/implemented/chicago_actuarial/model.py` | Actuarial model class | High |
| `models/implemented/chicago_actuarial/measures.py` | Actuarial Python measures | High |
| `models/implemented/etf/model.py` | ETF model implementation | Medium |
| `models/implemented/etf/measures.py` | ETF Python measures | Medium |
| `models/implemented/options/model.py` | Options model implementation | Medium |
| `models/implemented/options/measures.py` | Options Python measures | Medium |
| `models/implemented/futures/model.py` | Futures model implementation | Low |
| `models/implemented/futures/measures.py` | Futures Python measures | Low |
| `models/base/query_helpers.py` | Backend-agnostic query operations | High |
| `orchestration/builders/model_builder.py` | Single model build logic | High |
| `datapipelines/providers/chicago/facets/tax_assessment.py` | Tax assessment facet | High |
| `datapipelines/providers/chicago/facets/community_area.py` | Community area facet | High |
| `configs/exhibits/presets/base_exhibit.yaml` | Base exhibit defaults | Medium |
| `configs/exhibits/presets/markdown.yaml` | Markdown exhibit config | Medium |

---

## Part 7: Files to Modify

### Refactoring Required

| File | Changes Needed | Effort |
|------|----------------|--------|
| `models/implemented/company/model.py` | Replace 6 backend if-statements with QueryHelper | 2 hrs |
| `models/implemented/stocks/model.py` | Replace 9 backend if-statements with QueryHelper | 3 hrs |
| `models/implemented/stocks/measures.py` | Replace 6 backend if-statements with QueryHelper | 2 hrs |
| `models/implemented/core/model.py` | Add DuckDB support via QueryHelper | 2 hrs |
| `configs/models/etfs/` | Rename to `etf/` (singular convention) | 1 hr |
| `scripts/run_full_pipeline.py` | Add deprecation warning, delegate to orchestrate.py | 1 hr |

---

## Part 8: Step-by-Step Implementation Tasks

### Phase 1: Cleanup (Day 1)

**Goal:** Remove deprecated files, fix naming inconsistencies

| # | Task | Files Affected |
|---|------|----------------|
| 1.1 | Delete deprecated v1.x YAML files | `configs/models/company.yaml`, `etf.yaml` |
| 1.2 | Delete orphaned services file | `models/implemented/company/services.py` |
| 1.3 | Rename `etfs/` to `etf/` for consistency | `configs/models/etfs/` → `etf/` |
| 1.4 | Update any imports referencing renamed dirs | Search and replace |

### Phase 2: Backend Abstraction (Days 2-3)

**Goal:** Eliminate backend branching in model implementations

| # | Task | Files Affected |
|---|------|----------------|
| 2.1 | Create QueryHelper class | NEW: `models/base/query_helpers.py` |
| 2.2 | Refactor CompanyModel to use QueryHelper | `models/implemented/company/model.py` |
| 2.3 | Refactor StocksModel to use QueryHelper | `models/implemented/stocks/model.py` |
| 2.4 | Refactor StocksMeasures to use QueryHelper | `models/implemented/stocks/measures.py` |
| 2.5 | Refactor CoreModel to use QueryHelper | `models/implemented/core/model.py` |
| 2.6 | Test all models with both backends | Run test suite |

### Phase 3: Migrate v1.x Configs to v2.0 (Days 4-5)

**Goal:** All models use v2.0 modular YAML pattern

| # | Task | Files Affected |
|---|------|----------------|
| 3.1 | Create `core/` modular config from core.yaml | NEW: `configs/models/core/*.yaml` |
| 3.2 | Create `forecast/` modular config from forecast.yaml | NEW: `configs/models/forecast/*.yaml` |
| 3.3 | Delete old v1.x files after migration | DELETE: `core.yaml`, `forecast.yaml` |
| 3.4 | Update ModelConfigLoader if needed | `config/model_loader.py` |

### Phase 4: Orchestration Layer (Days 6-7)

**Goal:** Unified build/ingest system

| # | Task | Files Affected |
|---|------|----------------|
| 4.1 | Create DependencyGraph class | NEW: `orchestration/dependency_graph.py` |
| 4.2 | Create ProviderRegistry class | NEW: `datapipelines/providers/registry.py` |
| 4.3 | Create provider.yaml for each provider | NEW: `providers/{name}/provider.yaml` |
| 4.4 | Create model_builder module | NEW: `orchestration/builders/model_builder.py` |
| 4.5 | Create unified orchestrate.py CLI | NEW: `scripts/orchestrate.py` |
| 4.6 | Deprecate old scripts | Add warnings to old scripts |

### Phase 5: Chicago Actuarial Model (Days 8-12)

**Goal:** Complete actuarial economic forecast model

| # | Task | Files Affected |
|---|------|----------------|
| 5.1 | Create chicago_actuarial config | NEW: `configs/models/chicago_actuarial/*.yaml` |
| 5.2 | Create TaxAssessmentFacet | NEW: `datapipelines/providers/chicago/facets/tax_assessment.py` |
| 5.3 | Create CommunityAreaFacet | NEW: `datapipelines/providers/chicago/facets/community_area.py` |
| 5.4 | Update ChicagoIngestor to use new facets | `datapipelines/providers/chicago/chicago_ingestor.py` |
| 5.5 | Create ChicagoActuarialModel class | NEW: `models/implemented/chicago_actuarial/model.py` |
| 5.6 | Create actuarial measures | NEW: `models/implemented/chicago_actuarial/measures.py` |
| 5.7 | Create analysis notebooks | NEW: `configs/notebooks/chicago_actuarial/*.md` |

### Phase 6: Exhibit Configuration (Days 13-14)

**Goal:** Complete exhibit preset system

| # | Task | Files Affected |
|---|------|----------------|
| 6.1 | Create base exhibit preset | NEW: `configs/exhibits/presets/base_exhibit.yaml` |
| 6.2 | Create markdown exhibit preset | NEW: `configs/exhibits/presets/markdown.yaml` |
| 6.3 | Create grid exhibit preset | NEW: `configs/exhibits/presets/grid.yaml` |
| 6.4 | Update exhibit registry | `configs/exhibits/registry.yaml` |

### Phase 7: Complete Missing Model Implementations (Days 15-20)

**Goal:** All models have working implementations

| # | Task | Files Affected |
|---|------|----------------|
| 7.1 | Implement ETF model | NEW: `models/implemented/etf/model.py`, `measures.py` |
| 7.2 | Implement Options model | NEW: `models/implemented/options/model.py`, `measures.py` |
| 7.3 | Implement Futures model | NEW: `models/implemented/futures/model.py`, `measures.py` |
| 7.4 | Test all model builds | Run orchestrate.py --all |

---

## Part 9: Chicago Actuarial Model Design

### Schema Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                 CHICAGO ACTUARIAL SCHEMA                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  DIMENSIONS:                                                    │
│                                                                 │
│  dim_geography (77 Chicago community areas)                     │
│  ├── community_area_id (PK)                                     │
│  ├── community_area_name                                        │
│  ├── region (North, South, West, Central, Far South)           │
│  ├── population (2020 census)                                   │
│  ├── area_sq_miles                                              │
│  └── median_income                                              │
│                                                                 │
│  dim_property_class (assessment classifications)                │
│  ├── property_class_id (PK)                                     │
│  ├── class_code                                                 │
│  ├── class_description                                          │
│  └── assessment_rate                                            │
│                                                                 │
│  FACTS:                                                         │
│                                                                 │
│  fact_tax_assessment (property assessments by year)             │
│  ├── assessment_id (PK)                                         │
│  ├── community_area_id (FK)                                     │
│  ├── property_class_id (FK)                                     │
│  ├── assessment_year                                            │
│  ├── total_assessed_value                                       │
│  ├── property_count                                             │
│  ├── avg_assessed_value                                         │
│  └── tax_year                                                   │
│                                                                 │
│  fact_budget_allocation (city budget by department/area)        │
│  ├── budget_id (PK)                                             │
│  ├── fiscal_year                                                │
│  ├── department_code                                            │
│  ├── appropriation_amount                                       │
│  └── expenditure_type                                           │
│                                                                 │
│  fact_pension_status (pension fund metrics)                     │
│  ├── pension_id (PK)                                            │
│  ├── fund_name                                                  │
│  ├── fiscal_year                                                │
│  ├── assets_market_value                                        │
│  ├── actuarial_liability                                        │
│  ├── funded_ratio                                               │
│  └── amortization_period                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Actuarial Measures (Python)

| Measure | Description | Inputs |
|---------|-------------|--------|
| `tax_base_cagr` | Compound annual growth rate of tax base | assessment values, years |
| `tax_base_projection` | Project future tax base | historical values, growth model |
| `pension_solvency_index` | Combined pension health metric | funded ratios, amortization |
| `fiscal_stress_index` | Overall fiscal health score | multiple indicators |
| `revenue_volatility` | Variance in revenue streams | historical revenues |
| `demographic_risk_score` | Population/income trend risk | census data, trends |

### Data Sources (Chicago Data Portal)

| Dataset | Socrata ID | Use |
|---------|------------|-----|
| Property Tax Assessments | `jcxq-k9xf` | Tax base analysis |
| Community Area Boundaries | `igwz-8jzy` | Geography dimension |
| Budget Appropriations | `g867-z4xg` | Budget analysis |
| Employee Salaries | `xzkq-xp2w` | Expenditure analysis |
| Pension Fund Reports | Manual | Pension analysis |

---

## Summary

### What We Have Now (Implemented - May Need Removal/Revision)

The following files were created during this session but should be reviewed against this plan:

- `datapipelines/providers/registry.py` - ProviderRegistry ✓
- `datapipelines/providers/{name}/provider.yaml` - Provider metadata ✓
- `orchestration/dependency_graph.py` - DependencyGraph ✓
- `scripts/orchestrate.py` - Unified CLI ✓

**Decision Needed:** Keep these implementations or revise based on the planning document?

### What's Left to Build

1. **Phase 1-2**: Cleanup and backend abstraction (QueryHelper)
2. **Phase 3**: v1.x to v2.0 config migration
3. **Phase 4**: Model builder module
4. **Phase 5**: Chicago actuarial model (schema, facets, measures)
5. **Phase 6**: Exhibit configuration presets
6. **Phase 7**: Missing model implementations (ETF, Options, Futures)

### Total Estimated Effort

| Phase | Days | Priority |
|-------|------|----------|
| Phase 1: Cleanup | 1 | High |
| Phase 2: Backend Abstraction | 2 | High |
| Phase 3: Config Migration | 2 | High |
| Phase 4: Orchestration | 2 | High |
| Phase 5: Chicago Actuarial | 5 | High |
| Phase 6: Exhibits | 2 | Medium |
| Phase 7: Missing Models | 6 | Medium |
| **Total** | **20 days** | |

---

## Appendix A: Model Registry Pattern

How models are discovered and instantiated:

```
┌────────────────────────────────────────────────────────────────────┐
│                    MODEL DISCOVERY FLOW                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  1. Scan configs/models/ for directories with model.yaml           │
│                                                                    │
│  2. For each model.yaml found:                                     │
│     - Read depends_on field                                        │
│     - Read storage config                                          │
│     - Read component references                                    │
│                                                                    │
│  3. Build dependency graph                                         │
│     core → company, macro                                          │
│     company → stocks                                               │
│     macro → city_finance                                           │
│     etc.                                                           │
│                                                                    │
│  4. To instantiate a model:                                        │
│     a. Map model name to class:                                    │
│        'stocks' → models.implemented.stocks.model.StocksModel      │
│        'company' → models.implemented.company.model.CompanyModel   │
│                                                                    │
│     b. Convention: {name}/model.py contains {Name}Model class      │
│                                                                    │
│     c. Fallback: Explicit registry mapping for exceptions          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```
