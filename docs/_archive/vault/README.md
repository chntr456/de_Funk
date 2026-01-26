# de_Funk Documentation Vault

**Comprehensive technical reference for all de_Funk components**

Last Updated: 2025-11-24
Version: 2.0

---

## Quick Start

| I want to... | Go to... |
|--------------|----------|
| Understand the architecture | [00-overview](00-overview/README.md) |
| Query data or build models | [01-core-framework](01-core-framework/README.md) |
| Understand graph-based modeling | [02-graph-architecture](02-graph-architecture/README.md) |
| Add a data source | [03-data-providers](03-data-providers/README.md) |
| See what data is available | [04-implemented-models](04-implemented-models/README.md) |
| Calculate metrics | [05-measure-framework](05-measure-framework/README.md) |
| Run ETL pipelines | [06-pipelines](06-pipelines/README.md) |
| Build dashboards | [07-ui-system](07-ui-system/README.md) |
| Run scripts | [08-scripts-reference](08-scripts-reference/README.md) |
| See code examples | [09-examples-catalog](09-examples-catalog/README.md) |
| Write tests | [10-testing-guide](10-testing-guide/README.md) |
| Configure the system | [11-configuration](11-configuration/README.md) |
| Debug issues | [12-troubleshooting](12-troubleshooting/README.md) |
| Review design proposals | [13-proposals](13-proposals/README.md) |

---

## Documentation Structure

```
docs/vault/
├── 00-overview/              # Architecture, data flow, technology stack
├── 01-core-framework/        # BaseModel, UniversalSession, connections
├── 02-graph-architecture/    # Nodes, edges, paths, dependency resolution
├── 03-data-providers/        # Alpha Vantage, BLS, Chicago (with terms of use)
├── 04-implemented-models/    # Model data dictionary (dims, facts, measures)
├── 05-measure-framework/     # Simple, computed, weighted, Python measures
├── 06-pipelines/             # Bronze/Silver layer, facets, ingestors
├── 07-ui-system/             # Notebooks, filters, exhibits, Streamlit
├── 08-scripts-reference/     # Build, ingest, forecast, maintenance scripts
├── 09-examples-catalog/      # Code examples by category
├── 10-testing-guide/         # Unit, integration, validation, performance
├── 11-configuration/         # ConfigLoader, environment, API configs
├── 12-troubleshooting/       # Common issues and solutions
├── 13-proposals/             # Design proposals and RFCs
└── archive/                  # Historical documentation
```

---

## What is de_Funk?

**de_Funk** is a graphical overlay to a unified relational model enabling low-code interactions with data warehouses.

### Key Features

- **YAML-Driven Modeling**: Define dimensional models declaratively
- **Graph-Based Architecture**: Tables as nodes, relationships as edges
- **Two-Layer Storage**: Bronze (raw) → Silver (dimensional)
- **Backend Agnostic**: Supports both DuckDB and Spark
- **Unified Query Interface**: Cross-model queries via UniversalSession
- **Measure Framework**: Pre-defined calculations (YAML + Python)
- **Interactive Analytics**: Markdown notebooks with dynamic filtering

### Current Data Domain (Example)

The framework is domain-agnostic, but the current implementation demonstrates financial/economic data:

| Model | Description | Data Source |
|-------|-------------|-------------|
| **core** | Calendar dimension (foundation) | Generated |
| **company** | Corporate entities (CIK-based) | Alpha Vantage |
| **stocks** | Stock securities with technicals | Alpha Vantage |
| **macro** | Economic indicators (unemployment, CPI) | BLS |
| **city_finance** | Municipal data (Chicago) | Chicago Data Portal |
| **forecast** | Time series predictions | Derived |

---

## Navigation by Role

### Data Engineer
1. [Data Providers](03-data-providers/README.md) - Add/configure data sources
2. [Pipelines](06-pipelines/README.md) - ETL processes
3. [Implemented Models](04-implemented-models/README.md) - Data dictionary
4. [Scripts Reference](08-scripts-reference/README.md) - Operational scripts

### Data Analyst
1. [Implemented Models](04-implemented-models/README.md) - Available data
2. [Measure Framework](05-measure-framework/README.md) - Metrics and KPIs
3. [Examples Catalog](09-examples-catalog/README.md) - Query examples
4. [UI System](07-ui-system/README.md) - Notebooks and dashboards

### Developer
1. [Core Framework](01-core-framework/README.md) - BaseModel, sessions
2. [Graph Architecture](02-graph-architecture/README.md) - Model design
3. [Testing Guide](10-testing-guide/README.md) - Test patterns
4. [Proposals](13-proposals/README.md) - Design decisions

---

## Key Concepts

### Two-Layer Architecture

```
API Data → Bronze Layer → Silver Layer → Analytics
           (raw data)    (dimensional)   (queries)
```

- **Bronze**: Raw API data, partitioned Parquet files
- **Silver**: Star/snowflake schemas, YAML-configured
- **Analytics**: DuckDB queries directly on Silver (no separate Gold layer)

### Model Dependency Graph

```
Tier 0: core (calendar)
           ↓
Tier 1: company, macro
           ↓
Tier 2: stocks → options, etfs, futures
           ↓
Tier 3: forecast, city_finance
```

### Measure Types

| Type | Definition | Example |
|------|------------|---------|
| Simple | Direct aggregation | `AVG(close_price)` |
| Computed | Expression-based | `(high - low) / open` |
| Weighted | Weighted aggregation | Volume-weighted price |
| Python | Complex calculations | Sharpe ratio, correlation |

---

## Related Resources

- [CLAUDE.md](/CLAUDE.md) - AI assistant guide (high-level)
- [Architecture Diagram](/docs/architecture-diagram.drawio) - Visual system design
- [Scripts Examples](/scripts/examples/) - Runnable code examples
- [Configs](/configs/) - YAML model configurations

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2025-11-24 | Consolidated vault structure, provider terms of use, model data dictionary |
| 1.0 | 2025-11-16 | Initial vault creation |
