# Model-Architecture Mapping

---

This document maps data models to their corresponding architecture components, creating clear connections between what data exists (models) and how it's built/used (architecture).

---

## Model-to-Architecture Mapping

---

### Core Model

**Model:** [[Core Model]]
**Primary Architecture Components:**
- [[Storage]] - Calendar dimension storage strategy
- [[Models System]] - Foundation for all other models
- [[Bronze Storage]] - Seed data for calendar generation

**Tags:**
```
#component/storage/silver
#component/models-system/base
#architecture/foundation
```

**Architecture Cross-References:**
- Storage: `docs/guide/3-architecture/components/storage/silver-layer.md`
- Models: `docs/guide/3-architecture/components/models-system/base-model.md`
- Graph: `docs/guide/3-architecture/components/models-system/overview.md`

---

### Company Model

**Model:** [[Company Model]]
**Primary Architecture Components:**
- [[Data Pipeline]] - Polygon API ingestion
- [[Facets]] - Price/ticker/news normalization
- [[Providers]] - Polygon provider implementation
- [[Bronze Storage]] - Raw market data
- [[Silver Storage]] - Dimensional stock data
- [[Models System]] - Graph-based model building

**Tags:**
```
#component/data-pipeline/polygon
#component/facets/prices
#component/facets/news
#component/providers/polygon
#component/storage/bronze
#component/storage/silver
#component/models-system/dimensional
#architecture/ingestion-to-analytics
```

**Architecture Cross-References:**
- Pipeline: `docs/guide/3-architecture/components/data-pipeline/overview.md`
- Facets: `docs/guide/3-architecture/components/data-pipeline/facets.md`
- Providers: `docs/guide/3-architecture/components/data-pipeline/providers.md`
- Bronze: `docs/guide/3-architecture/components/storage/bronze-layer.md`
- Silver: `docs/guide/3-architecture/components/storage/silver-layer.md`
- Models: `docs/guide/3-architecture/components/models-system/base-model.md`

---

### Forecast Model

**Model:** [[Forecast Model]]
**Primary Architecture Components:**
- [[Models System]] - ML model framework
- [[Silver Storage]] - Forecast output storage
- [[Universal Session]] - Training data access

**Tags:**
```
#component/models-system/ml
#component/storage/silver
#component/session/cross-model
#architecture/analytics
```

**Architecture Cross-References:**
- Models: `docs/guide/3-architecture/components/models-system/base-model.md`
- Session: `docs/guide/3-architecture/components/models-system/universal-session.md`
- Storage: `docs/guide/3-architecture/components/storage/silver-layer.md`

---

### Macro Model

**Model:** [[Macro Model]]
**Primary Architecture Components:**
- [[Data Pipeline]] - BLS API ingestion
- [[Facets]] - Economic indicator normalization
- [[Providers]] - BLS provider implementation
- [[Bronze Storage]] - Raw BLS data
- [[Silver Storage]] - Economic indicators
- [[Models System]] - Time series modeling

**Tags:**
```
#component/data-pipeline/bls
#component/facets/economics
#component/providers/bls
#component/storage/bronze
#component/storage/silver
#component/models-system/dimensional
#architecture/ingestion-to-analytics
```

**Architecture Cross-References:**
- Pipeline: `docs/guide/3-architecture/components/data-pipeline/overview.md`
- Facets: `docs/guide/3-architecture/components/data-pipeline/facets.md`
- Providers: `docs/guide/3-architecture/components/data-pipeline/providers.md`
- Bronze: `docs/guide/3-architecture/components/storage/bronze-layer.md`
- Silver: `docs/guide/3-architecture/components/storage/silver-layer.md`

---

### City Finance Model

**Model:** [[City Finance Model]]
**Primary Architecture Components:**
- [[Data Pipeline]] - Chicago Data Portal ingestion
- [[Facets]] - Municipal data normalization
- [[Providers]] - Chicago provider implementation
- [[Bronze Storage]] - Raw city data
- [[Silver Storage]] - Geographic/financial data
- [[Models System]] - Multi-level dimensional modeling

**Tags:**
```
#component/data-pipeline/chicago
#component/facets/municipal
#component/providers/chicago
#component/storage/bronze
#component/storage/silver
#component/models-system/dimensional
#architecture/ingestion-to-analytics
```

**Architecture Cross-References:**
- Pipeline: `docs/guide/3-architecture/components/data-pipeline/overview.md`
- Facets: `docs/guide/3-architecture/components/data-pipeline/facets.md`
- Providers: `docs/guide/3-architecture/components/data-pipeline/providers.md`
- Bronze: `docs/guide/3-architecture/components/storage/bronze-layer.md`
- Silver: `docs/guide/3-architecture/components/storage/silver-layer.md`

---

## Architecture Component Usage by Model

---

### Data Pipeline Components

**Used By:**
- [[Company Model]] - Polygon ingestion
- [[Macro Model]] - BLS ingestion
- [[City Finance Model]] - Chicago ingestion

**Not Used By:**
- [[Core Model]] - Uses seed data generation
- [[Forecast Model]] - Consumes existing data

**Architecture Docs:**
- `3-architecture/components/data-pipeline/overview.md`
- `3-architecture/components/data-pipeline/facets.md`
- `3-architecture/components/data-pipeline/ingestors.md`
- `3-architecture/components/data-pipeline/providers.md`
- `3-architecture/components/data-pipeline/bronze-storage.md`

---

### Models System Components

**Used By:**
- ALL models (core framework)

**Specific Usage:**
- [[Core Model]] - Simplest: 1 dimension, no facts
- [[Company Model]] - Full star schema with paths
- [[Forecast Model]] - ML-specific extensions
- [[Macro Model]] - Time series patterns
- [[City Finance Model]] - Geographic dimensions

**Architecture Docs:**
- `3-architecture/components/models-system/overview.md`
- `3-architecture/components/models-system/base-model.md`
- `3-architecture/components/models-system/universal-session.md`
- `3-architecture/components/models-system/model-registry.md`
- `3-architecture/components/models-system/storage-router.md`

---

### Storage Components

**Bronze Layer:**
- [[Company Model]] - prices_daily, news, tickers, exchanges
- [[Macro Model]] - unemployment, cpi, employment, wages
- [[City Finance Model]] - permits, unemployment, community areas

**Silver Layer:**
- ALL models write dimensional data here

**Architecture Docs:**
- `3-architecture/components/storage/overview.md`
- `3-architecture/components/storage/bronze-layer.md`
- `3-architecture/components/storage/silver-layer.md`
- `3-architecture/components/storage/duckdb-integration.md`

---

### Notebook System Components

**Model Visualization:**
- ALL models can be visualized in notebooks
- [[Company Model]] - Most common (stock analysis)
- [[Forecast Model]] - Prediction visualizations
- [[Macro Model]] - Economic trend charts
- [[City Finance Model]] - Geographic heatmaps

**Architecture Docs:**
- `3-architecture/components/notebook-system/overview.md`
- `3-architecture/components/notebook-system/markdown-parser.md`
- `3-architecture/components/notebook-system/exhibits.md`

---

### UI Application Components

**Model Access:**
- ALL models accessible via Streamlit UI
- Filter system works with all model dimensions
- Exhibit rendering for all fact tables

**Architecture Docs:**
- `3-architecture/components/ui-application/overview.md`
- `3-architecture/components/ui-application/streamlit-app.md`

---

## Tag Hierarchy for Model-Architecture Connections

---

### Level 1: Architecture Layer Tags

```
#architecture/foundation        → Core Model
#architecture/ingestion-to-analytics → Company, Macro, City Finance
#architecture/analytics         → Forecast Model
```

### Level 2: Component Tags

```
#component/data-pipeline/{provider}
  - /polygon   → Company Model
  - /bls       → Macro Model
  - /chicago   → City Finance Model

#component/facets/{type}
  - /prices    → Company Model
  - /news      → Company Model
  - /economics → Macro Model
  - /municipal → City Finance Model

#component/storage/{layer}
  - /bronze    → All ingestion models
  - /silver    → All models

#component/models-system/{aspect}
  - /base          → All models
  - /dimensional   → Company, Macro, City Finance
  - /ml            → Forecast Model
  - /cross-model   → Models with dependencies

#component/notebook-system/visualization → All models
#component/ui-application/access → All models
```

### Level 3: Implementation Pattern Tags

```
#pattern/star-schema           → Company, Macro, City Finance
#pattern/time-series           → Company, Macro, Forecast
#pattern/geographic            → City Finance
#pattern/ml-predictions        → Forecast
#pattern/reference-only        → Core
```

---

## Obsidian Graph View Organization

---

With these tags, your Obsidian graph will cluster:

1. **Data Pipeline Cluster**
   - Company, Macro, City Finance models
   - Connected to: Facets, Providers, Bronze Storage

2. **Models System Cluster**
   - All 5 models
   - Connected to: BaseModel, UniversalSession, Registry

3. **Storage Cluster**
   - All models
   - Connected to: Bronze Layer, Silver Layer, DuckDB

4. **Analytics Cluster**
   - Forecast Model (central)
   - Connected to: Company Model (data source)

5. **Foundation Cluster**
   - Core Model (central hub)
   - Connected to: All other models (dependency)

---

## Quick Reference: Model → Architecture Lookups

---

### "Which architecture components does [Model] use?"

**Core Model:**
- Storage/Silver Layer (writes calendar)
- Models System/BaseModel (simplest implementation)

**Company Model:**
- Data Pipeline/Polygon (ingestion)
- Facets/Prices + News (normalization)
- Storage/Bronze (raw data)
- Storage/Silver (dimensional data)
- Models System/BaseModel (graph building)

**Forecast Model:**
- Models System/BaseModel (ML extensions)
- Models System/UniversalSession (training data access)
- Storage/Silver (predictions output)

**Macro Model:**
- Data Pipeline/BLS (ingestion)
- Facets/Economics (normalization)
- Storage/Bronze + Silver
- Models System/BaseModel (time series)

**City Finance Model:**
- Data Pipeline/Chicago (ingestion)
- Facets/Municipal (normalization)
- Storage/Bronze + Silver
- Models System/BaseModel (geographic dimensions)

---

### "Which models use [Architecture Component]?"

**Data Pipeline:**
- Company (Polygon), Macro (BLS), City Finance (Chicago)

**Facets:**
- Company (Prices, News), Macro (Economics), City Finance (Municipal)

**Bronze Storage:**
- Company, Macro, City Finance

**Silver Storage:**
- ALL models

**BaseModel:**
- ALL models

**UniversalSession:**
- Forecast (training), Cross-model analysis

**Notebook System:**
- ALL models (visualization)

---

**Tags:** #type/reference #architecture/mapping #component/models-system

**Last Updated:** 2024-11-08
