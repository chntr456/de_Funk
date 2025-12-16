# Documentation Index

**Master index of all vault documentation with cross-references**

---

## By Section

### 00 - Overview
- [README](00-overview/README.md) - Quick orientation
- [Architecture](00-overview/architecture.md) - System architecture
- [Data Flow](00-overview/data-flow.md) - Bronze → Silver → Analytics
- [Technology Stack](00-overview/technology-stack.md) - Tech reference
- [Glossary](00-overview/glossary.md) - Key terms

### 01 - Core Framework
- [README](01-core-framework/README.md) - Core concepts
- [BaseModel](01-core-framework/base-model.md) - Foundation class (v2.2: modular composition)
- [UniversalSession](01-core-framework/universal-session.md) - Query interface (v2.2: modular)
- [Connection System](01-core-framework/connection-system.md) - Backend adapters
- [Filter Engine](01-core-framework/filter-engine.md) - Filter application (v2.2: consolidated)
- [Storage Router](01-core-framework/storage-router.md) - Path management
- [Logging & Error Handling](01-core-framework/logging-error-handling.md) - Observability framework

### 02 - Graph Architecture
- [README](02-graph-architecture/README.md) - Graph concepts
- [Graph Overview](02-graph-architecture/graph-overview.md) - Architecture
- [Nodes, Edges, Paths](02-graph-architecture/nodes-edges-paths.md) - Components
- [Dependency Resolution](02-graph-architecture/dependency-resolution.md) - Build order
- [Cross-Model References](02-graph-architecture/cross-model-references.md) - Linking
- [Query Planner](02-graph-architecture/query-planner.md) - Join planning

### 03 - Data Providers
- [README](03-data-providers/README.md) - Provider overview
- [Alpha Vantage](03-data-providers/alpha-vantage/) - Securities data
  - [Terms of Use](03-data-providers/alpha-vantage/terms-of-use.md)
  - [API Reference](03-data-providers/alpha-vantage/api-reference.md)
  - [Rate Limits](03-data-providers/alpha-vantage/rate-limits.md)
- [BLS](03-data-providers/bls/) - Economic indicators
  - [Terms of Use](03-data-providers/bls/terms-of-use.md)
  - [API Reference](03-data-providers/bls/api-reference.md)
- [Chicago](03-data-providers/chicago/) - Municipal data
  - [Terms of Use](03-data-providers/chicago/terms-of-use.md)
  - [API Reference](03-data-providers/chicago/api-reference.md)
- [Adding Providers](03-data-providers/adding-providers.md) - How to add new

### 04 - Implemented Models
- [README](04-implemented-models/README.md) - Model overview & dependencies
- [Core](04-implemented-models/core/) - Calendar dimension
- [Company](04-implemented-models/company/) - Corporate entities
- [Stocks](04-implemented-models/stocks/) - Stock securities
- [Options](04-implemented-models/options/) - Options contracts [PARTIAL]
- [ETF](04-implemented-models/etf/) - Exchange-traded funds [SKELETON]
- [Futures](04-implemented-models/futures/) - Futures contracts [SKELETON]
- [Macro](04-implemented-models/macro/) - Economic indicators
- [City Finance](04-implemented-models/city-finance/) - Municipal data
- [Forecast](04-implemented-models/forecast/) - Predictions
- [Inheritance](04-implemented-models/inheritance/) - YAML inheritance patterns

### 05 - Measure Framework
- [README](05-measure-framework/README.md) - Measure concepts
- [Simple Measures](05-measure-framework/simple-measures.md) - Aggregations
- [Computed Measures](05-measure-framework/computed-measures.md) - Expressions
- [Weighted Measures](05-measure-framework/weighted-measures.md) - Weighting
- [Python Measures](05-measure-framework/python-measures.md) - Complex logic
- [Measure Registry](05-measure-framework/measure-registry.md) - Discovery

### 06 - Pipelines
- [README](06-pipelines/README.md) - Pipeline architecture
- [Facet System](06-pipelines/facet-system.md) - Transformations
- [Ingestors](06-pipelines/ingestors.md) - Orchestration
- [Bronze Layer](06-pipelines/bronze-layer.md) - Raw storage
- [Silver Layer](06-pipelines/silver-layer.md) - Model building
- [Pipeline Operations](06-pipelines/pipeline-operations.md) - Running ETL

### 07 - UI System
- [README](07-ui-system/README.md) - UI overview
- [Notebook System](07-ui-system/notebook-system.md) - Markdown notebooks
- [Filter Engine UI](07-ui-system/filter-engine-ui.md) - Filter components
- [Exhibits](07-ui-system/exhibits.md) - Visualizations
- [Streamlit App](07-ui-system/streamlit-app.md) - Application

### 08 - Scripts Reference
- [README](08-scripts-reference/README.md) - Script categories
- [Build Scripts](08-scripts-reference/build-scripts.md)
- [Ingestion Scripts](08-scripts-reference/ingestion-scripts.md)
- [Forecast Scripts](08-scripts-reference/forecast-scripts.md)
- [Maintenance Scripts](08-scripts-reference/maintenance-scripts.md)
- [Debug Scripts](08-scripts-reference/debug-scripts.md)
- [Quick Reference](08-scripts-reference/quick-reference.md) - Cheatsheet

### 09 - Examples Catalog
- [README](09-examples-catalog/README.md) - Examples overview
- [Quickstart](09-examples-catalog/quickstart.md) - Getting started
- [Parameter Interface](09-examples-catalog/parameter-interface.md)
- [Weighting Strategies](09-examples-catalog/weighting-strategies.md)
- [Measure Calculations](09-examples-catalog/measure-calculations.md)
- [Query Examples](09-examples-catalog/query-examples.md)
- [Extension Examples](09-examples-catalog/extension-examples.md)

### 10 - Testing Guide
- [README](10-testing-guide/README.md) - Testing philosophy
- [Unit Tests](10-testing-guide/unit-tests.md)
- [Integration Tests](10-testing-guide/integration-tests.md)
- [Validation Tests](10-testing-guide/validation-tests.md)
- [Performance Tests](10-testing-guide/performance-tests.md)
- [Fixtures](10-testing-guide/fixtures.md) - Test data
- [CI/CD](10-testing-guide/ci-cd.md) - Automation

### 11 - Configuration
- [README](11-configuration/README.md) - Config overview
- [Config Loader](11-configuration/config-loader.md) - Loading system
- [Environment Variables](11-configuration/environment-variables.md)
- [API Configs](11-configuration/api-configs.md)
- [Storage Config](11-configuration/storage-config.md)

### 12 - Troubleshooting
- [README](12-troubleshooting/README.md) - Issue index
- [Data Issues](12-troubleshooting/data-issues.md)
- [Query Issues](12-troubleshooting/query-issues.md)
- [Model Issues](12-troubleshooting/model-issues.md)
- [API Issues](12-troubleshooting/api-issues.md)
- [Performance](12-troubleshooting/performance.md)

### 13 - Proposals
- [README](13-proposals/README.md) - Proposal process
- [Accepted](13-proposals/accepted/) - Implemented proposals
- [Active](13-proposals/active/) - In-progress proposals
- [Draft](13-proposals/draft/) - Under discussion

---

## By Topic

### Data Sources
- [Provider Overview](03-data-providers/README.md)
- [Alpha Vantage](03-data-providers/alpha-vantage/) (securities)
- [BLS](03-data-providers/bls/) (economic)
- [Chicago](03-data-providers/chicago/) (municipal)
- [Adding New Providers](03-data-providers/adding-providers.md)

### Available Data (Models)
- [All Models Overview](04-implemented-models/README.md)
- [Core (Calendar)](04-implemented-models/core/)
- [Company](04-implemented-models/company/)
- [Stocks](04-implemented-models/stocks/)
- [Macro](04-implemented-models/macro/)
- [City Finance](04-implemented-models/city-finance/)
- [Forecast](04-implemented-models/forecast/)

### Querying & Analytics
- [UniversalSession](01-core-framework/universal-session.md)
- [Query Planner](02-graph-architecture/query-planner.md)
- [Measure Framework](05-measure-framework/README.md)
- [Query Examples](09-examples-catalog/query-examples.md)

### Development
- [BaseModel](01-core-framework/base-model.md)
- [Graph Architecture](02-graph-architecture/README.md)
- [Testing Guide](10-testing-guide/README.md)
- [Extension Examples](09-examples-catalog/extension-examples.md)

### Operations
- [Scripts Reference](08-scripts-reference/README.md)
- [Pipeline Operations](06-pipelines/pipeline-operations.md)
- [Troubleshooting](12-troubleshooting/README.md)

---

## File Count by Section

| Section | Files | Status |
|---------|-------|--------|
| 00-overview | 5 | Complete |
| 01-core-framework | 7 | Complete |
| 02-graph-architecture | 6 | Complete |
| 03-data-providers | 12 | Complete |
| 04-implemented-models | 30+ | Complete |
| 05-measure-framework | 6 | Complete |
| 06-pipelines | 6 | Complete |
| 07-ui-system | 6 | Complete |
| 08-scripts-reference | 7 | Complete |
| 09-examples-catalog | 7 | Complete |
| 10-testing-guide | 7 | Complete |
| 11-configuration | 5 | Complete |
| 12-troubleshooting | 6 | Complete |
| 13-proposals | 3+ | Complete |
| **Total** | **100+** | - |
