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
├── core/                 # Foundation model (calendar dimension)
│   └── README.md
├── company/              # Financial market data
│   └── README.md
├── forecast/             # Time series predictions
│   └── README.md
├── macro/                # Macroeconomic indicators
│   └── README.md
└── city-finance/         # Municipal finance data
    └── README.md
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

To add a new model, create a new subdirectory:

```bash
mkdir docs/guide/2-models/implemented/your-model/
```

Then create `README.md` using the template from [[TEMPLATES]]:

```markdown
---
title: "Your Model"
tags: [domain/category, component/model, status/stable]
dependencies: ["[[Core Model]]"]
architecture_components:
  - "[[Data Pipeline]]"
  - "[[Storage]]"
---

# Your Model

See [[TEMPLATES#Model Documentation Template]] for full structure.
```

---

## Model Documentation Standards

---

Each model directory contains:

1. **README.md** - Main model documentation
   - Overview and purpose
   - Schema overview
   - Data sources
   - Architecture components used
   - How-to guides
   - Usage examples

2. **Additional files (optional):**
   - `examples/` - Code examples
   - `schemas/` - Detailed schema files
   - `queries/` - Common queries
   - `CHANGELOG.md` - Version history

---

## Navigation

---

**Browse Models:**
- [[Core Model]] - `core/README.md`
- [[Company Model]] - `company/README.md`
- [[Forecast Model]] - `forecast/README.md`
- [[Macro Model]] - `macro/README.md`
- [[City Finance Model]] - `city-finance/README.md`

**Related Documentation:**
- [[Overview]] - Dimensional modeling concepts
- [[MODEL_ARCHITECTURE_MAPPING]] - Architecture component mapping
- [[TEMPLATES]] - Model documentation template

---

**Tags:** #type/reference #component/model #status/stable

**Last Updated:** 2024-11-08
**Total Models:** 5
