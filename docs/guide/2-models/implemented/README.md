---
title: "Implemented Models"
tags: [type/reference, component/model, status/stable]
aliases: ["Models", "Data Models"]
created: 2024-11-08
updated: 2024-11-08
---

# Implemented Models

---

This directory contains all implemented data models for the de_Funk platform, organized by model domain.

---

## Model Directory Structure

---

```
implemented/
├── core/                 # Foundation model
│   ├── calendar.md            # Calendar dimension (27 attributes)
│   └── geography.md           # Planned geography dimension
├── company/              # Financial market data
│   ├── overview.md            # Company model overview
│   ├── dim-company.md         # Company dimension
│   ├── dim-exchange.md        # Exchange dimension
│   ├── fact-prices.md         # Daily prices (OHLCV)
│   ├── fact-news.md           # News with sentiment
│   ├── measures.md            # Pre-defined measures & indices
│   └── polygon-integration.md # Polygon.io data source
├── forecast/             # Time series predictions
│   ├── overview.md            # Forecast model overview
│   ├── fact-forecasts.md      # Price/volume predictions
│   ├── fact-metrics.md        # Accuracy metrics
│   ├── model-registry.md      # Trained models registry
│   └── model-types.md         # ARIMA, Prophet, Random Forest
├── macro/                # Macroeconomic indicators
│   ├── overview.md            # Macro model overview
│   ├── dim-economic-series.md # BLS series metadata
│   ├── fact-unemployment.md   # Unemployment rate
│   ├── fact-cpi.md            # Consumer Price Index
│   ├── fact-employment.md     # Total nonfarm employment
│   ├── fact-wages.md          # Average hourly earnings
│   └── bls-integration.md     # BLS API data source
└── city-finance/         # Municipal finance data
    ├── overview.md            # City finance overview
    └── community-area.md      # 77 Chicago neighborhoods
```

---

## Quick Reference

---

| Model | Directory | Primary Purpose | Dependencies | Tags |
|-------|-----------|-----------------|--------------|------|
| **[[Core Model]]** | `core/` | Shared calendar dimension (27 date attributes) | None | #reference #architecture/foundation |
| **[[Company Model]]** | `company/` | Stock prices, company data, news sentiment | Core | #finance/equities #architecture/ingestion-to-analytics |
| **[[Forecast Model]]** | `forecast/` | ML predictions, accuracy metrics | Core, Company | #finance/forecast #architecture/analytics |
| **[[Macro Model]]** | `macro/` | BLS economic indicators (unemployment, CPI, etc.) | Core | #economics/bls #architecture/ingestion-to-analytics |
| **[[City Finance Model]]** | `city-finance/` | Chicago municipal data, geographic analysis | Core, Macro | #municipal #architecture/ingestion-to-analytics |

---

## Model Dependency Graph

---

```
┌─────────────┐
│ Core Model  │ ← Foundation (no dependencies)
└──────┬──────┘
       │
       ├─────────────────┬─────────────────┬─────────────────┐
       │                 │                 │                 │
       ↓                 ↓                 ↓                 ↓
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   Company   │   │    Macro    │   │  Forecast   │   │City Finance │
│    Model    │   │    Model    │   │    Model    │   │    Model    │
└──────┬──────┘   └──────┬──────┘   └─────────────┘   └─────────────┘
       │                 │
       │                 │
       └────────┬────────┘
                │
                ↓
         (Forecast depends on Company)
         (City Finance depends on Macro)
```

---

## Architecture Alignment

---

Each model directory aligns with specific architecture components:

### Data Pipeline Models (Bronze → Silver)
- **[[Company Model]]** → `company/` → Uses [[Data Pipeline/Polygon]]
- **[[Macro Model]]** → `macro/` → Uses [[Data Pipeline/BLS]]
- **[[City Finance Model]]** → `city-finance/` → Uses [[Data Pipeline/Chicago]]

### Analytics Models (Silver-only)
- **[[Forecast Model]]** → `forecast/` → Uses [[Models System/ML]]

### Foundation Models (Seed data)
- **[[Core Model]]** → `core/` → Uses [[Bronze Storage]] (seed)

See [[MODEL_ARCHITECTURE_MAPPING]] for complete component mapping.

---

## Adding a New Model

---

To add a new model, create a new subdirectory with focused files:

```bash
mkdir docs/guide/2-models/implemented/your-model/
```

Create focused files following the established pattern:

**1. Overview File** (`overview.md`):
```markdown
---
title: "Your Model Overview"
tags: [domain/category, component/model, status/stable]
dependencies: ["[[Calendar]]"]
architecture_components:
  - "[[Data Pipeline/YourProvider]]"
  - "[[Bronze Storage]]"
  - "[[Silver Storage]]"
---

# Your Model - Overview

[Model description, quick stats, components, usage]
```

**2. Dimension Files** (e.g., `dim-your-dimension.md`):
```markdown
---
title: "Your Dimension"
tags: [domain/category, component/model, concept/dimensional-modeling]
aliases: ["dim_your_dimension"]
---

# Your Dimension

[Schema, sample data, relationships, usage]
```

**3. Fact Files** (e.g., `fact-your-facts.md`):
```markdown
---
title: "Your Facts"
tags: [domain/category, component/model, concept/facts]
aliases: ["fact_your_facts"]
---

# Your Facts

[Grain, schema, partitioning, usage examples]
```

See [[TEMPLATES]] for complete templates.

---

## Model Documentation Standards

---

Each model directory contains **focused individual files** for each major concept:

### 1. Overview File
- **Filename:** `overview.md`
- **Purpose:** Model summary, quick stats, data sources
- **Contents:** Component list, star schema, usage examples

### 2. Dimension Files
- **Pattern:** `dim-{name}.md` (e.g., `dim-company.md`)
- **Purpose:** One file per dimension table
- **Contents:** Schema, sample data, relationships, usage

### 3. Fact Files
- **Pattern:** `fact-{name}.md` (e.g., `fact-prices.md`)
- **Purpose:** One file per fact table
- **Contents:** Grain, schema, partitioning, examples

### 4. Integration Files
- **Pattern:** `{provider}-integration.md` (e.g., `polygon-integration.md`)
- **Purpose:** Data source API documentation
- **Contents:** Endpoints, authentication, pipeline details

### 5. Additional Files
- **Measures:** Pre-defined aggregations (`measures.md`)
- **Model Types:** ML algorithm details (`model-types.md`)
- **Registry:** Model metadata tracking (`model-registry.md`)

**Note:** Each file is a standalone Obsidian node with its own frontmatter, tags, and wiki-links.

---

## Navigation

---

### Core Model
- [[Calendar]] - `core/calendar.md` - Calendar dimension with 27 attributes
- [[Geography]] - `core/geography.md` - Planned geography dimension

### Company Model
- [[Company Model Overview]] - `company/overview.md`
- [[Company Dimension]] - `company/dim-company.md`
- [[Exchange Dimension]] - `company/dim-exchange.md`
- [[Price Facts]] - `company/fact-prices.md`
- [[News Facts]] - `company/fact-news.md`
- [[Company Measures]] - `company/measures.md`
- [[Polygon Integration]] - `company/polygon-integration.md`

### Forecast Model
- [[Forecast Model Overview]] - `forecast/overview.md`
- [[Forecast Facts]] - `forecast/fact-forecasts.md`
- [[Forecast Metrics]] - `forecast/fact-metrics.md`
- [[Model Registry]] - `forecast/model-registry.md`
- [[Forecast Model Types]] - `forecast/model-types.md`

### Macro Model
- [[Macro Model Overview]] - `macro/overview.md`
- [[Economic Series Dimension]] - `macro/dim-economic-series.md`
- [[Unemployment Facts]] - `macro/fact-unemployment.md`
- [[CPI Facts]] - `macro/fact-cpi.md`
- [[Employment Facts]] - `macro/fact-employment.md`
- [[Wages Facts]] - `macro/fact-wages.md`
- [[BLS Integration]] - `macro/bls-integration.md`

### City Finance Model
- [[City Finance Model Overview]] - `city-finance/overview.md`
- [[Community Area]] - `city-finance/community-area.md`

### Related Documentation
- [[MODEL_ARCHITECTURE_MAPPING]] - Architecture component mapping
- [[TEMPLATES]] - Model documentation template
- [[TAGGING_SYSTEM]] - Hierarchical tagging for Obsidian

---

**Tags:** #type/reference #component/model #status/stable

**Last Updated:** 2024-11-08
**Total Models:** 5
