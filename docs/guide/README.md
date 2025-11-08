# de_Funk Analytics Platform - Documentation Guide

> **Comprehensive documentation for the de_Funk financial analytics and data modeling platform**

Welcome to the consolidated documentation guide for de_Funk! This guide provides everything you need to understand, use, and extend the platform.

---

## 📚 Quick Navigation

### 🚀 **[1. Getting Started](1-getting-started/README.md)**
Start here! Learn how to install, configure, and run your first pipeline.

- **[Quickstart Guide](1-getting-started/quickstart.md)** - Get up and running in 5 minutes
- **[Architecture Overview](1-getting-started/architecture-overview.md)** - Understand the big picture
- **[Installation Guide](1-getting-started/installation.md)** - Complete setup instructions
- **[How-To Guides](1-getting-started/how-to/README.md)** - Step-by-step tutorials for common tasks

### 📊 **[2. Models](2-models/README.md)**
Understand the data models that power analytics.

- **[Overview](2-models/overview.md)** - Dimensional modeling concepts
- **[Implemented Models](2-models/implemented/)** - Detailed documentation for each model
  - [Core Model](2-models/implemented/core-model.md) - Shared calendar dimension
  - [Company Model](2-models/implemented/company-model.md) - Financial market data
  - [Forecast Model](2-models/implemented/forecast-model.md) - Time series predictions
  - [Macro Model](2-models/implemented/macro-model.md) - Economic indicators
  - [City Finance Model](2-models/implemented/city-finance-model.md) - Municipal data

### 🏗️ **[3. Architecture](3-architecture/README.md)**
Deep dive into system design and component details.

- **[System Design](3-architecture/system-design.md)** - End-to-end architecture
- **[Data Flow](3-architecture/data-flow.md)** - Bronze → Silver → UI pipeline
- **[Components](3-architecture/components/)** - Detailed component documentation
  - [Data Pipeline](3-architecture/components/data-pipeline/) - Ingestion & transformation
  - [Core Session](3-architecture/components/core-session/) - Connection & context management
  - [Models System](3-architecture/components/models-system/) - Model framework
  - [Notebook System](3-architecture/components/notebook-system/) - Interactive analytics
  - [UI Application](3-architecture/components/ui-application/) - Streamlit interface
  - [Storage](3-architecture/components/storage/) - Data storage architecture

### 🔧 **[4. Development](4-development/README.md)**
Roadmap, todos, and future enhancements.

- **[Todo Tracker](4-development/todo-tracker.md)** - Track progress and improvements
- **[Roadmap](4-development/roadmap.md)** - Future features and enhancements

---

## 🎯 What is de_Funk?

**de_Funk** is a modern financial analytics platform that provides:

- **📥 Data Ingestion** - Automated pipelines for Polygon, BLS, and Chicago data
- **🔄 Data Transformation** - Bronze (raw) to Silver (dimensional) modeling
- **📊 Interactive Analytics** - Markdown-based notebooks with dynamic filtering
- **🔮 Time Series Forecasting** - ARIMA, Prophet, and Random Forest models
- **⚡ High Performance** - DuckDB for 10-100x faster analytics vs Spark
- **🎨 Modern UI** - Streamlit-based interface with professional theming

---

## 🏛️ Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                             │
│  Polygon API (stocks) │ BLS API (macro) │ Chicago Portal (city) │
└───────────────┬─────────────────────────────────────────────────┘
                │
                ↓
┌─────────────────────────────────────────────────────────────────┐
│                    BRONZE LAYER (Raw Data)                       │
│         Partitioned Parquet │ Facet Normalization                │
└───────────────┬─────────────────────────────────────────────────┘
                │
                ↓
┌─────────────────────────────────────────────────────────────────┐
│                  SILVER LAYER (Dimensional Model)                │
│    Dimensions + Facts │ YAML-Driven Graph Building               │
└───────────────┬─────────────────────────────────────────────────┘
                │
                ↓
┌─────────────────────────────────────────────────────────────────┐
│                   ANALYTICS & VISUALIZATION                      │
│  Notebooks (Markdown) │ DuckDB Queries │ Streamlit UI            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚦 Common Workflows

### **New User → First Analytics Dashboard**
1. [Quickstart Guide](1-getting-started/quickstart.md) - Install and setup
2. [Run the Pipeline](1-getting-started/how-to/run-the-pipeline.md) - Ingest data
3. [Use the UI](1-getting-started/how-to/use-the-ui.md) - View dashboards

### **Data Engineer → Add New Data Source**
1. [Create a Facet](1-getting-started/how-to/create-a-facet.md) - Normalize API responses
2. [Create an API Provider](1-getting-started/how-to/create-an-api-provider.md) - Implement provider
3. [Run the Pipeline](1-getting-started/how-to/run-the-pipeline.md) - Ingest data

### **Analyst → Create New Dashboard**
1. [Create a Notebook](1-getting-started/how-to/create-a-notebook.md) - Markdown-based analytics
2. [Work with Session Data](1-getting-started/how-to/work-with-session-data.md) - Adhoc queries
3. [Use the UI](1-getting-started/how-to/use-the-ui.md) - Share insights

### **Developer → Extend the Platform**
1. [Architecture Overview](1-getting-started/architecture-overview.md) - Understand design
2. [Create a Model](1-getting-started/how-to/create-a-model.md) - Add dimensional model
3. [Component Documentation](3-architecture/components/) - Deep dive into internals

---

## 📖 Documentation Conventions

Throughout this guide:

- **Code examples** are tested against the actual codebase
- **File paths** are shown as `path/to/file.py:123` (with line numbers when relevant)
- **ASCII diagrams** illustrate architecture and data flow
- **Summary tables** provide quick reference (full schemas in YAML configs)
- **Runnable examples** are available in the `examples/` directory

---

## 🆘 Getting Help

- **Start here:** [Quickstart Guide](1-getting-started/quickstart.md)
- **How do I...?** [How-To Guides](1-getting-started/how-to/README.md)
- **What is...?** [Architecture Guide](3-architecture/README.md)
- **Troubleshooting:** Check the relevant how-to guide or component doc

---

## 📦 Project Structure

```
de_Funk/
├── app/
│   ├── notebook/          # Notebook system (parsers, managers, filters)
│   ├── services/          # Business logic services
│   └── ui/                # Streamlit application
├── configs/
│   ├── models/            # Model YAML configurations
│   ├── notebooks/         # Markdown notebook definitions
│   └── storage.json       # Storage configuration
├── core/                  # Core session, context, connections
├── datapipelines/         # Data ingestion (facets, ingestors, providers)
├── models/                # Data modeling framework
│   ├── api/               # Model sessions and registry
│   ├── base/              # BaseModel class
│   └── implemented/       # Implemented models (core, company, forecast, etc.)
├── docs/
│   └── guide/             # This documentation guide
├── examples/              # Runnable code examples
├── scripts/               # Pipeline execution scripts
└── storage/
    ├── bronze/            # Raw ingested data (Parquet)
    └── silver/            # Dimensional models (Parquet)
```

---

## 🔑 Key Concepts

### **Bronze Layer**
Raw data ingested from external APIs, stored as partitioned Parquet files.

### **Silver Layer**
Dimensional models (facts + dimensions) built from Bronze via YAML-driven graph transformations.

### **Facets**
Transform raw API responses into normalized DataFrames with consistent schemas.

### **Models**
Dimensional data models defined in YAML with nodes (tables), edges (relationships), and paths (joins).

### **Notebooks**
Markdown-based analytics with inline filters (`$filter${}`) and exhibits (`$exhibits${}`).

### **Universal Session**
Cross-model query interface for adhoc analysis and data exploration.

### **Filter Engine**
Backend-agnostic filter application (supports Spark and DuckDB).

---

## 🚀 Next Steps

**Ready to get started?** Head to the **[Quickstart Guide](1-getting-started/quickstart.md)**

**Want to understand the architecture first?** Check out **[Architecture Overview](1-getting-started/architecture-overview.md)**

**Looking for a specific how-to?** Browse **[How-To Guides](1-getting-started/how-to/README.md)**

---

## 📝 Contributing to Docs

When contributing to this guide:

1. **Test all code examples** against the actual codebase
2. **Use ASCII diagrams** for universal compatibility
3. **Link to implementation files** with line numbers when helpful
4. **Keep docs in sync** with code changes
5. **Use summary tables** for schemas (link to full YAML for details)

---

**Last Updated:** 2024-11-08
**Version:** 1.0
**Platform Version:** See `configs/models/` for model versions
