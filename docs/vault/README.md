# de_Funk Documentation Vault

**Comprehensive technical reference for all de_Funk components**

Last Updated: 2025-11-16
Version: 1.0

---

## Overview

This documentation vault provides in-depth technical reference for every component in the de_Funk system. Each section includes method-level documentation, architecture explanations, and usage examples.

## Documentation Structure

```
docs/vault/
├── README.md                          # This file - navigation hub
├── 01-core-components/
│   ├── base-model.md                  # BaseModel class - 40+ methods documented
│   ├── universal-session.md           # UniversalSession - cross-model queries
│   ├── connection-system.md           # Connection adapters (Spark/DuckDB)
│   └── storage-router.md              # Storage path management
├── 02-graph-architecture/
│   ├── graph-overview.md              # Graph system architecture
│   ├── nodes-edges-paths.md           # Graph components explained
│   ├── dependency-resolution.md       # Model dependency graph
│   └── cross-model-references.md      # Cross-model table access
├── 03-model-framework/
│   ├── model-lifecycle.md             # Build process and lifecycle
│   ├── yaml-configuration.md          # YAML schema reference
│   ├── measure-framework.md           # Measure types and calculations
│   └── implemented-models.md          # All 8 models documented
├── 04-data-pipelines/
│   ├── pipeline-architecture.md       # Pipeline system overview
│   ├── facets-system.md               # Facet transformations
│   ├── ingestors.md                   # Data ingestion orchestration
│   └── providers.md                   # Provider implementations
├── 05-ui-system/
│   ├── notebook-system.md             # Markdown notebook architecture
│   ├── filter-engine.md               # Filter system and contexts
│   ├── exhibits.md                    # Visualization system
│   └── streamlit-app.md               # Streamlit UI components
└── 06-configuration/
    ├── config-loader.md               # ConfigLoader system
    ├── environment-variables.md       # Environment configuration
    └── api-configs.md                 # API endpoint configuration
```

---

## Quick Navigation

### By Component Type

**Core Framework**
- [BaseModel](01-core-components/base-model.md) - Foundation for all models
- [UniversalSession](01-core-components/universal-session.md) - Unified query interface
- [Connection System](01-core-components/connection-system.md) - Backend adapters

**Graph System**
- [Graph Overview](02-graph-architecture/graph-overview.md) - Architecture explanation
- [Nodes, Edges, Paths](02-graph-architecture/nodes-edges-paths.md) - Component details
- [Cross-Model References](02-graph-architecture/cross-model-references.md) - Linking models

**Models & Measures**
- [Model Lifecycle](03-model-framework/model-lifecycle.md) - Build process
- [YAML Configuration](03-model-framework/yaml-configuration.md) - Schema reference
- [Measure Framework](03-model-framework/measure-framework.md) - Calculations

**Data Pipelines**
- [Pipeline Architecture](04-data-pipelines/pipeline-architecture.md) - ETL overview
- [Facets System](04-data-pipelines/facets-system.md) - Transformations
- [Providers](04-data-pipelines/providers.md) - Data sources

**UI & Analytics**
- [Notebook System](05-ui-system/notebook-system.md) - Interactive analytics
- [Filter Engine](05-ui-system/filter-engine.md) - Dynamic filtering
- [Exhibits](05-ui-system/exhibits.md) - Visualizations

### By Task

**Building Models**
1. [YAML Configuration](03-model-framework/yaml-configuration.md)
2. [Model Lifecycle](03-model-framework/model-lifecycle.md)
3. [BaseModel Reference](01-core-components/base-model.md)

**Writing Queries**
1. [UniversalSession](01-core-components/universal-session.md)
2. [Measure Framework](03-model-framework/measure-framework.md)
3. [Cross-Model References](02-graph-architecture/cross-model-references.md)

**Creating Pipelines**
1. [Pipeline Architecture](04-data-pipelines/pipeline-architecture.md)
2. [Facets System](04-data-pipelines/facets-system.md)
3. [Providers](04-data-pipelines/providers.md)

**Building UI**
1. [Notebook System](05-ui-system/notebook-system.md)
2. [Filter Engine](05-ui-system/filter-engine.md)
3. [Exhibits](05-ui-system/exhibits.md)

---

## Understanding Key Concepts

### Why So Many Methods in BaseModel?

BaseModel contains 40+ methods because it provides a **complete, YAML-driven graph building framework** that works for any dimensional model. Instead of duplicating graph-building logic in each model, all models inherit this powerful framework.

**Method Categories in BaseModel:**

1. **Graph Building** (8 methods)
   - `build()` - Main orchestrator
   - `_build_nodes()` - Create nodes from YAML
   - `_apply_edges()` - Validate relationships
   - `_materialize_paths()` - Create joined views

2. **Data Access** (7 methods)
   - `get_table()` - Retrieve table
   - `get_dimension_df()` - Get dimension
   - `get_fact_df()` - Get fact
   - `has_table()` - Check existence

3. **Cross-Model Support** (3 methods)
   - `set_session()` - Inject session reference
   - `_resolve_node()` - Resolve cross-model refs
   - `get_table_enriched()` - Fetch with joins

4. **Measure Execution** (2 methods)
   - `calculate_measure()` - Execute measure
   - `calculate_measure_by_entity()` - Grouped calculation

5. **Backend Abstraction** (8 methods)
   - `_detect_backend()` - Identify Spark/DuckDB
   - `_select_columns()` - Column operations
   - `_apply_derive()` - Computed columns
   - `_join_with_dedupe()` - Joining logic

6. **Storage Operations** (3 methods)
   - `write_tables()` - Persist to Silver
   - `ensure_built()` - Lazy loading
   - Custom hooks

7. **Metadata & Introspection** (5 methods)
   - `list_tables()` - Inventory
   - `get_table_schema()` - Schema info
   - `get_relations()` - Relationship map
   - `get_metadata()` - Model metadata

8. **Extension Points** (3 methods)
   - `before_build()` - Pre-build hook
   - `after_build()` - Post-build hook
   - `custom_node_loading()` - Custom loaders

**See**: [BaseModel Reference](01-core-components/base-model.md) for complete documentation of all methods.

### Understanding Graphs in Models

Models use a **directed acyclic graph (DAG)** to define dimensional schemas:

- **Nodes**: Tables (dimensions and facts)
- **Edges**: Relationships (foreign keys)
- **Paths**: Materialized joins (denormalized views)

This graph-based approach enables:
- **Declarative modeling**: Define structure in YAML, not code
- **Automatic joins**: Query planner traverses graph
- **Cross-model queries**: Models link via dependency graph
- **Backend agnostic**: Same graph works with Spark or DuckDB

**See**: [Graph Architecture Overview](02-graph-architecture/graph-overview.md) for detailed explanation.

---

## Architecture Diagram

Visual representation of the system architecture:
- **File**: `docs/architecture-diagram.drawio`
- **Tool**: Draw.io (https://app.diagrams.net)

Includes:
- Two-layer architecture (Bronze → Silver)
- Data flow from APIs to analytics
- Model dependency graph
- Universal Session architecture
- Storage layer organization

---

## Related Documentation

### Getting Started
- [QUICKSTART.md](/QUICKSTART.md) - Installation and first steps
- [RUNNING.md](/RUNNING.md) - How to run the application
- [CLAUDE.md](/CLAUDE.md) - AI assistant guide

### Development Guides
- [TESTING_GUIDE.md](/TESTING_GUIDE.md) - Testing strategies
- [PIPELINE_GUIDE.md](/PIPELINE_GUIDE.md) - Data pipeline workflows
- [docs/configuration.md](/docs/configuration.md) - Configuration system

### Reference
- [MODEL_DEPENDENCY_ANALYSIS.md](/MODEL_DEPENDENCY_ANALYSIS.md) - Model dependencies
- [MODEL_EDGES_REFERENCE.md](/MODEL_EDGES_REFERENCE.md) - Cross-model relationships
- [FORECAST_README.md](/FORECAST_README.md) - Forecasting models

---

## Contributing to Documentation

When adding or modifying code, update the relevant documentation:

1. **New component**: Create new file in appropriate vault section
2. **New method**: Document in component's reference file
3. **Architecture change**: Update graph architecture docs
4. **Configuration change**: Update configuration docs

Keep documentation synchronized with code to maintain accuracy.
