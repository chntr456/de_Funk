# Overview

**System architecture and foundational concepts for de_Funk**

---

## What is de_Funk?

de_Funk is a **graphical overlay to a unified relational model** enabling low-code interactions with data warehouses. It transforms the complexity of dimensional modeling into declarative YAML configurations.

### Core Philosophy

1. **Declarative over Imperative**: Define what you want in YAML, not how to build it
2. **Graph-Based Modeling**: Tables are nodes, relationships are edges
3. **Backend Agnostic**: Same model works with DuckDB or Spark
4. **Measure-Driven Analytics**: Pre-define calculations, not ad-hoc SQL
5. **Two-Layer Storage**: Raw data (Bronze) → Dimensional models (Silver)

---

## In This Section

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System architecture and component interactions |
| [Data Flow](data-flow.md) | How data moves through Bronze → Silver → Analytics |
| [Technology Stack](technology-stack.md) | Languages, frameworks, and tools |
| [Glossary](glossary.md) | Key terms and concepts |

---

## Quick Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                              │
│  Alpha Vantage (securities) │ BLS (economic) │ Chicago (municipal)│
└─────────────────┬───────────────────┬───────────────────┬───────┘
                  │                   │                   │
                  ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BRONZE LAYER (Raw)                          │
│  Facets normalize API responses → Partitioned Parquet files      │
│  storage/bronze/{provider}/{table}/                              │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SILVER LAYER (Dimensional)                  │
│  YAML configs → Graph building → Star/Snowflake schemas          │
│  storage/silver/{model}/{table}/                                 │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ANALYTICS (Query Layer)                      │
│  UniversalSession → DuckDB queries → Notebooks/Dashboards        │
│  storage/duckdb/analytics.db (catalog only, no data duplication) │
└─────────────────────────────────────────────────────────────────┘
```

---

## Current Implementation

The framework is domain-agnostic, but demonstrates with financial/economic data:

### Data Sources (3 providers)
- **Alpha Vantage**: Stock prices, company fundamentals, technical indicators
- **BLS**: Unemployment, CPI, employment, wages
- **Chicago Data Portal**: Municipal finance, permits, licenses

### Models (8 implemented)
- **Tier 0**: `core` (calendar dimension)
- **Tier 1**: `company`, `macro`
- **Tier 2**: `stocks`, `options`, `etfs`, `futures`, `city_finance`
- **Tier 3**: `forecast`

### Key Features
- 40+ methods in BaseModel
- Hybrid measures (YAML + Python)
- YAML inheritance for model reuse
- Cross-model queries
- Backend abstraction (DuckDB/Spark)

---

## Getting Started

1. **Understand the architecture**: Read [Architecture](architecture.md)
2. **See available data**: Browse [Implemented Models](../04-implemented-models/README.md)
3. **Query data**: See [Examples Catalog](../09-examples-catalog/README.md)
4. **Run pipelines**: Check [Scripts Reference](../08-scripts-reference/README.md)

---

## Next Steps

- [Architecture](architecture.md) - Deep dive into system design
- [Data Flow](data-flow.md) - Understand the ETL process
- [Core Framework](../01-core-framework/README.md) - Learn BaseModel and sessions
