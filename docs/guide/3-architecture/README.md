# Architecture Documentation

> **Deep dive into de_Funk's system design, components, and technical implementation**

This section provides comprehensive technical documentation of the platform's architecture and all major components.

---

## 📚 What's in This Section

### **[System Design](system-design.md)**
Complete end-to-end architecture with design principles, patterns, and technology stack.

**Topics Covered:**
- Layered architecture overview
- Design patterns used (Factory, Registry, Strategy, Template Method)
- Separation of concerns
- Backend abstraction (Spark vs DuckDB)
- Configuration-driven design

---

### **[Data Flow](data-flow.md)**
Detailed walkthrough of how data flows through the system from ingestion to visualization.

**Topics Covered:**
- Bronze Layer ingestion flow
- Silver Layer transformation flow
- Query execution flow
- Filter application flow
- Complete pipeline diagrams

---

## 🏗️ Component Documentation

Detailed documentation for each major subsystem:

### **[Data Pipeline](components/data-pipeline/)**
Bronze layer ingestion and normalization system.

**Components:**
- **[Overview](components/data-pipeline/overview.md)** - Pipeline architecture
- **[Facets](components/data-pipeline/facets.md)** - API response transformation
- **[Ingestors](components/data-pipeline/ingestors.md)** - Orchestration layer
- **[Providers](components/data-pipeline/providers.md)** - API integrations (Polygon, BLS, Chicago)
- **[Bronze Storage](components/data-pipeline/bronze-storage.md)** - Raw data storage

**Key Files:**
- `datapipelines/facets/base_facet.py` - Facet base class
- `datapipelines/ingestors/base_ingestor.py` - Ingestor framework
- `datapipelines/providers/` - Provider implementations

---

### **[Core Session](components/core-session/)**
Configuration, connection management, and filtering engine.

**Components:**
- **[Overview](components/core-session/overview.md)** - Core session architecture
- **[Repo Context](components/core-session/repo-context.md)** - Configuration & factory
- **[Connections](components/core-session/connections.md)** - Spark & DuckDB abstraction
- **[Filter Engine](components/core-session/filter-engine.md)** - Backend-agnostic filtering

**Key Files:**
- `core/context.py` - RepoContext factory
- `core/connection.py` - Connection abstractions
- `core/duckdb_connection.py` - DuckDB implementation
- `core/session/filters.py` - FilterEngine

---

### **[Models System](components/models-system/)**
Dimensional modeling framework and cross-model queries.

**Components:**
- **[Overview](components/models-system/overview.md)** - Models architecture
- **[Base Model](components/models-system/base-model.md)** - BaseModel & graph building
- **[Universal Session](components/models-system/universal-session.md)** - Cross-model queries
- **[Model Registry](components/models-system/model-registry.md)** - Model discovery
- **[Storage Router](components/models-system/storage-router.md)** - Path resolution

**Key Files:**
- `models/base/model.py` - BaseModel class
- `models/api/session.py` - UniversalSession
- `models/registry.py` - ModelRegistry
- `models/api/dal.py` - StorageRouter

---

### **[Notebook System](components/notebook-system/)**
Interactive markdown-based analytics with dynamic filtering.

**Components:**
- **[Overview](components/notebook-system/overview.md)** - Notebook architecture
- **[Notebook Manager](components/notebook-system/notebook-manager.md)** - Lifecycle management
- **[Markdown Parser](components/notebook-system/markdown-parser.md)** - Parsing markdown notebooks
- **[Filter System](components/notebook-system/filter-system.md)** - Dynamic filters
- **[Exhibits](components/notebook-system/exhibits.md)** - Visualization components
- **[Folder Context](components/notebook-system/folder-context.md)** - Folder-based filtering

**Key Files:**
- `app/notebook/managers/notebook_manager.py` - NotebookManager
- `app/notebook/parsers/markdown_parser.py` - MarkdownNotebookParser
- `app/notebook/filters/` - Filter system
- `app/notebook/exhibits/` - Exhibit renderers

---

### **[UI Application](components/ui-application/)**
Streamlit-based web interface for interactive analytics.

**Components:**
- **[Overview](components/ui-application/overview.md)** - UI architecture
- **[Streamlit App](components/ui-application/streamlit-app.md)** - Main application
- **[Components](components/ui-application/components.md)** - UI component library
- **[State Management](components/ui-application/state-management.md)** - Session state handling

**Key Files:**
- `app/ui/notebook_app_duckdb.py` - Main Streamlit app
- `app/ui/components/` - UI components
- `app/ui/components/sidebar.py` - Sidebar navigation
- `app/ui/components/filters.py` - Filter widgets

---

### **[Storage](components/storage/)**
Data storage architecture for Bronze and Silver layers.

**Components:**
- **[Overview](components/storage/overview.md)** - Storage architecture
- **[Bronze Layer](components/storage/bronze-layer.md)** - Raw data storage
- **[Silver Layer](components/storage/silver-layer.md)** - Dimensional storage
- **[DuckDB Integration](components/storage/duckdb-integration.md)** - Fast analytics engine

**Key Files:**
- `configs/storage.json` - Storage configuration
- `models/api/dal.py` - StorageRouter, BronzeTable

---

## 🎯 Architecture Principles

### **1. Layered Architecture**
Clear separation between Bronze (raw), Silver (dimensional), and Analytics (query) layers.

### **2. Configuration-Driven**
YAML configs define models, storage, and data flows. Minimal code for new models.

### **3. Backend Agnostic**
Connection abstraction supports both Spark (ETL) and DuckDB (analytics) seamlessly.

### **4. Declarative Models**
Graph-based YAML definitions for dimensional models with automatic building.

### **5. Composability**
Small, focused components that can be composed for complex workflows.

### **6. Performance-First**
DuckDB for 10-100x faster analytics, partitioned storage, lazy evaluation.

---

## 🔄 System Interaction Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI Layer                        │
│                  (app/ui/notebook_app_duckdb.py)             │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│               Notebook Management Layer                      │
│              (app/notebook/managers/)                        │
│  NotebookManager → Parser → FilterCollection → Exhibits     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                 Data Access Layer                            │
│            (models/api/session.py)                           │
│  UniversalSession → ModelRegistry → FilterEngine            │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                    Model Layer                               │
│             (models/base/model.py)                           │
│  BaseModel → Graph Building → StorageRouter                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                Connection Layer                              │
│      (core/connection.py, core/duckdb_connection.py)        │
│  SparkConnection │ DuckDBConnection                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                  Storage Layer                               │
│                 (storage/bronze/, storage/silver/)           │
│  Partitioned Parquet Files                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Technology Stack

### **Backend**
- **Python 3.8+** - Primary language
- **DuckDB** - Fast analytics engine (default)
- **PySpark** - Optional for large-scale ETL
- **Pandas** - Data manipulation

### **Storage**
- **Parquet** - Columnar storage format
- **File System** - Local or cloud storage

### **Frontend**
- **Streamlit** - Web UI framework
- **Plotly** - Interactive visualizations
- **Markdown** - Notebook format

### **Data Sources**
- **Polygon.io API** - Stock market data
- **BLS API** - Economic indicators
- **Chicago Data Portal** - Municipal data

### **ML/Forecasting**
- **statsmodels** - ARIMA models
- **Prophet** - Facebook's forecasting library
- **scikit-learn** - Random Forest models

---

## 🚀 Performance Characteristics

### **Query Performance**
- **DuckDB:** 10-100x faster than Spark for analytics queries
- **Parquet:** Efficient columnar storage with predicate pushdown
- **Partitioning:** Date-based partitioning for query pruning

### **Scalability**
- **Bronze Layer:** Handles millions of rows per table
- **Silver Layer:** Optimized for query performance
- **DuckDB:** 8GB+ data queryable on laptop

### **Latency**
- **Startup:** <1s (DuckDB) vs ~15s (Spark)
- **Query:** <100ms for typical analytical queries
- **UI:** Real-time updates on filter changes

---

## 🔧 Extensibility Points

### **1. Add New Data Sources**
Create facets and providers in `datapipelines/providers/`

### **2. Add New Models**
Define YAML config + minimal Python class in `models/implemented/`

### **3. Add New Exhibits**
Create exhibit renderers in `app/notebook/exhibits/`

### **4. Add New Backends**
Implement `DataConnection` interface in `core/`

### **5. Customize UI**
Modify Streamlit components in `app/ui/components/`

---

## 📖 Reading Guide

### **For Data Engineers**
1. [Data Flow](data-flow.md) - Understand the pipeline
2. [Data Pipeline](components/data-pipeline/overview.md) - Ingestion architecture
3. [Models System](components/models-system/overview.md) - Dimensional modeling

### **For Backend Developers**
1. [System Design](system-design.md) - Overall architecture
2. [Core Session](components/core-session/overview.md) - Connection management
3. [Storage](components/storage/overview.md) - Data storage

### **For Frontend Developers**
1. [UI Application](components/ui-application/overview.md) - Streamlit app
2. [Notebook System](components/notebook-system/overview.md) - Interactive notebooks
3. [State Management](components/ui-application/state-management.md) - Session state

### **For Data Scientists/Analysts**
1. [Models System](components/models-system/overview.md) - Data models
2. [Notebook System](components/notebook-system/overview.md) - Analytics workflow
3. [Universal Session](components/models-system/universal-session.md) - Adhoc queries

---

## 🔍 Quick Reference

**Need to understand how...?**

- **Data is ingested?** → [Data Pipeline Overview](components/data-pipeline/overview.md)
- **Models are built?** → [Base Model](components/models-system/base-model.md)
- **Filters work?** → [Filter Engine](components/core-session/filter-engine.md)
- **Notebooks parse?** → [Markdown Parser](components/notebook-system/markdown-parser.md)
- **UI renders?** → [Streamlit App](components/ui-application/streamlit-app.md)
- **Storage works?** → [Storage Overview](components/storage/overview.md)

---

## 🎓 Design Patterns Used

| Pattern | Component | Purpose |
|---------|-----------|---------|
| **Factory** | `RepoContext`, `ConnectionFactory` | Create connections based on config |
| **Registry** | `ModelRegistry` | Discover and manage models |
| **Strategy** | `DataConnection` | Backend-agnostic operations |
| **Template Method** | `BaseModel` | Extensible model building |
| **Builder** | `BaseModel.build()` | Graph-based model construction |
| **Repository** | `StorageRouter` | Abstract storage access |
| **Singleton** | `UniversalSession` | Shared model session |
| **Observer** | Streamlit state | UI reactivity |

---

## 🚀 Next Steps

**New to the architecture?** Start with **[System Design](system-design.md)**

**Want to understand data flow?** Read **[Data Flow](data-flow.md)**

**Looking for a specific component?** Browse the **[Components](components/)** directory

**Want to extend the platform?** Check the extensibility points above and relevant how-to guides

---

**Last Updated:** 2024-11-08
**Total Components:** 6 major subsystems
**Lines of Code:** ~15,000+ (Python)
**Configuration Files:** 50+ YAML/JSON configs
