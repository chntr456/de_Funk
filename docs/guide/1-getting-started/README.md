# Getting Started with de_Funk

Welcome! This section will help you get up and running with de_Funk quickly.

---

## 📚 Documentation in This Section

### **[Quickstart Guide](quickstart.md)**
Get de_Funk running in 5 minutes. Perfect for first-time users who want to see the platform in action.

**Time Required:** 5-10 minutes
**Prerequisites:** Python 3.8+, pip
**What You'll Do:**
- Install dependencies
- Run the data pipeline
- Launch the UI
- View your first dashboard

---

### **[Architecture Overview](architecture-overview.md)**
Understand the big picture before diving into details. A high-level introduction to how de_Funk works.

**Topics Covered:**
- System design principles
- Data flow (Bronze → Silver → UI)
- Key components and their roles
- Technology stack

**Good For:** Understanding what de_Funk does and how components fit together

---

### **[Installation Guide](installation.md)**
Complete installation and configuration instructions for production use.

**Topics Covered:**
- Environment setup
- Dependency management
- Configuration files
- API key setup (Polygon, BLS, Chicago)
- Storage configuration
- Database setup (Spark vs DuckDB)

**Good For:** Production deployments and custom configurations

---

### **[How-To Guides](how-to/README.md)**
Step-by-step tutorials for common tasks.

**Available Guides:**

#### Data Engineering
- **[Run the Pipeline](how-to/run-the-pipeline.md)** - Execute data ingestion and transformations
- **[Create a Facet](how-to/create-a-facet.md)** - Add new data source transformations
- **[Create an API Provider](how-to/create-an-api-provider.md)** - Integrate new external APIs
- **[Create a Model](how-to/create-a-model.md)** - Build dimensional data models

#### Analytics
- **[Create a Notebook](how-to/create-a-notebook.md)** - Build interactive analytics dashboards
- **[Work with Session Data](how-to/work-with-session-data.md)** - Adhoc data analysis techniques
- **[Use the UI](how-to/use-the-ui.md)** - Navigate and use the Streamlit interface

---

## 🎯 Choose Your Path

### **Path 1: I'm New and Want to See It Working (5 min)**
→ Start with **[Quickstart Guide](quickstart.md)**

### **Path 2: I Want to Understand Before Running (15 min)**
→ Start with **[Architecture Overview](architecture-overview.md)**, then **[Quickstart](quickstart.md)**

### **Path 3: I'm Setting Up for Production (30 min)**
→ Read **[Installation Guide](installation.md)**, then **[Architecture Overview](architecture-overview.md)**

### **Path 4: I Have a Specific Task**
→ Find your task in **[How-To Guides](how-to/README.md)**

---

## 🔍 Quick Concepts

Before you start, here are key concepts you'll encounter:

| Concept | Description |
|---------|-------------|
| **Bronze Layer** | Raw data from APIs (Polygon, BLS, Chicago) stored as Parquet |
| **Silver Layer** | Dimensional models (facts + dimensions) for analytics |
| **Facet** | Transforms raw API responses into normalized DataFrames |
| **Model** | YAML-defined dimensional data model with graph structure |
| **Notebook** | Markdown-based interactive dashboard with filters and exhibits |
| **UniversalSession** | Interface for querying across models |
| **DuckDB** | Fast analytics engine (10-100x faster than Spark) |

---

## 🚦 Typical First Session

Here's what most users do in their first hour:

1. **[Quickstart](quickstart.md)** (5 min) - Install and run
2. **Open the UI** (2 min) - Explore stock_analysis notebook
3. **[Architecture Overview](architecture-overview.md)** (10 min) - Understand the system
4. **[Create a Notebook](how-to/create-a-notebook.md)** (15 min) - Build your own dashboard
5. **[Work with Session Data](how-to/work-with-session-data.md)** (20 min) - Adhoc analysis

---

## ❓ Common Questions

**Q: Do I need Spark?**
A: No! DuckDB is the default and recommended for analytics (10-100x faster). Spark is only needed for large-scale ETL.

**Q: Can I use my own data?**
A: Yes! Create a custom facet and provider. See [Create a Facet](how-to/create-a-facet.md).

**Q: How do I add a new dashboard?**
A: Create a markdown notebook. See [Create a Notebook](how-to/create-a-notebook.md).

**Q: Where is my data stored?**
A: `storage/bronze/` for raw data, `storage/silver/` for dimensional models. All Parquet format.

**Q: Can I query data programmatically?**
A: Yes! Use UniversalSession. See [Work with Session Data](how-to/work-with-session-data.md).

---

## 📦 Prerequisites

Before starting, ensure you have:

- **Python 3.8+**
- **pip** (package manager)
- **8GB+ RAM** (recommended for DuckDB analytics)
- **Git** (to clone the repository)

Optional but recommended:
- **Polygon API key** (for stock data)
- **BLS API key** (for economic data)

---

## 🆘 Troubleshooting

**Installation Issues?**
→ Check [Installation Guide](installation.md) troubleshooting section

**Pipeline Not Running?**
→ See [Run the Pipeline](how-to/run-the-pipeline.md) troubleshooting

**UI Not Loading?**
→ Check [Use the UI](how-to/use-the-ui.md) common issues

**Data Issues?**
→ Review [Architecture Overview](architecture-overview.md) to understand data flow

---

## 🚀 Ready to Start?

Head to the **[Quickstart Guide](quickstart.md)** to begin your journey!

Or jump directly to:
- **[Architecture Overview](architecture-overview.md)** - Learn the concepts first
- **[How-To Guides](how-to/README.md)** - Find a specific task

---

**Next:** [Quickstart Guide](quickstart.md) →
