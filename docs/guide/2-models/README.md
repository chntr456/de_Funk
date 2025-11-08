# Data Models

> **Comprehensive documentation of dimensional data models in de_Funk**

This section documents all implemented data models, their schemas, data sources, and design decisions.

---

## 📚 What's in This Section

### **[Overview](overview.md)**
Learn about dimensional modeling concepts, the model framework, and how models work in de_Funk.

**Topics Covered:**
- Dimensional modeling principles (Facts & Dimensions)
- YAML-driven model definitions
- Graph-based model building
- Model dependencies and relationships
- BaseModel framework

---

### **Implemented Models**

All production data models currently available in the platform:

#### **[Core Model](implemented/core-model.md)**
**Purpose:** Shared reference data and calendar dimension
**Key Tables:** `dim_calendar` (27 date attributes)
**Dependencies:** None (foundation model)
**Data Source:** Generated seed data
**Use Cases:** Date-based filtering, fiscal period analysis, time intelligence

---

#### **[Company Model](implemented/company-model.md)**
**Purpose:** Financial market and company data
**Key Tables:** `dim_company`, `dim_exchange`, `fact_prices`, `fact_news`
**Dependencies:** Core model
**Data Source:** Polygon.io API
**Use Cases:** Stock analysis, market trends, company research

---

#### **[Forecast Model](implemented/forecast-model.md)**
**Purpose:** Time series predictions and accuracy metrics
**Key Tables:** `fact_forecasts`, `fact_forecast_metrics`, `model_registry`
**Dependencies:** Core, Company models
**Data Source:** Generated from ML models (ARIMA, Prophet, Random Forest)
**Use Cases:** Price predictions, model comparison, forecast accuracy analysis

---

#### **[Macro Model](implemented/macro-model.md)**
**Purpose:** Macroeconomic indicators
**Key Tables:** `fact_unemployment`, `fact_cpi`, `fact_employment`, `fact_wages`
**Dependencies:** Core model
**Data Source:** Bureau of Labor Statistics (BLS) API
**Use Cases:** Economic analysis, correlation with market data, macro trends

---

#### **[City Finance Model](implemented/city-finance-model.md)**
**Purpose:** Municipal finance and economic data
**Key Tables:** `fact_local_unemployment`, `fact_building_permits`, `dim_community_area`
**Dependencies:** Core, Macro models
**Data Source:** Chicago Data Portal
**Use Cases:** City economic analysis, regional trends, municipal research

---

## 🏛️ Model Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         CORE MODEL                           │
│                     (Foundation Layer)                       │
│                                                              │
│  dim_calendar (27 date attributes)                          │
│  • Date intelligence                                        │
│  • Fiscal periods                                           │
│  • Weekend/weekday flags                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┬────────────────┐
         │           │           │                │
         ↓           ↓           ↓                ↓
┌────────────┐  ┌─────────┐  ┌──────────┐  ┌───────────────┐
│  COMPANY   │  │  MACRO  │  │ FORECAST │  │ CITY FINANCE  │
│   MODEL    │  │  MODEL  │  │  MODEL   │  │     MODEL     │
└────────────┘  └─────────┘  └──────────┘  └───────────────┘
      │                            │                │
      │                            │                │
      └────────────┬───────────────┘                │
                   │                                │
                   ↓                                ↓
         ┌──────────────────┐            ┌──────────────────┐
         │ Company + Macro  │            │  Macro + City    │
         │  Cross-Model     │            │  Cross-Model     │
         │    Analysis      │            │   Analysis       │
         └──────────────────┘            └──────────────────┘
```

**Dependency Rules:**
- All models depend on **Core** (calendar dimension)
- **Forecast** depends on **Company** (training data)
- **City Finance** depends on **Macro** (economic context)
- Models can be queried independently or joined via UniversalSession

---

## 📊 Model Comparison

| Model | Tables | Facts | Dimensions | Measures | Partitions | Data Source |
|-------|--------|-------|------------|----------|------------|-------------|
| **Core** | 1 | 0 | 1 | 0 | None | Generated |
| **Company** | 4 | 2 | 2 | 10 | trade_date, publish_date | Polygon API |
| **Forecast** | 4 | 3 | 1 | 3 | forecast_date, metric_date | ML Generated |
| **Macro** | 5 | 4 | 1 | 4 | year | BLS API |
| **City Finance** | 4 | 2 | 2 | 2 | year, month | Chicago Portal |

---

## 🔑 Key Concepts

### **Facts**
Transactional or event data with measures (numeric values).
- Examples: prices, news, unemployment rates, forecasts
- Typically partitioned by date for performance
- Contain foreign keys to dimensions

### **Dimensions**
Descriptive attributes for slicing and filtering data.
- Examples: companies, exchanges, economic series, community areas
- Usually small, slowly changing
- Contain primary keys and descriptive columns

### **Measures**
Pre-defined aggregations and calculations.
- Examples: avg_close_price, total_volume, market_cap
- Defined in model YAML
- Support weighted aggregates, custom expressions

### **Graph Structure**
Models define relationships as a graph:
- **Nodes:** Tables (dimensions and facts)
- **Edges:** Relationships (foreign keys)
- **Paths:** Materialized joins (analytics-ready views)

---

## 🎯 Common Model Operations

### **1. Load a Model**
```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize session
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load specific model
company_model = session.load_model('company')
```

### **2. Query a Table**
```python
# Get dimension
companies = session.get_table('company', 'dim_company')

# Get fact
prices = session.get_table('company', 'fact_prices')

# Get materialized view
prices_with_company = session.get_table('company', 'prices_with_company')
```

### **3. Apply Filters**
```python
# Filter by ticker
filters = {'ticker': ['AAPL', 'GOOGL', 'MSFT']}
filtered_prices = company_model.get_fact_df('fact_prices', filters=filters)

# Filter by date range
filters = {
    'trade_date': {
        'start': '2024-01-01',
        'end': '2024-12-31'
    }
}
```

### **4. Cross-Model Queries**
```python
# Get data from multiple models
company_prices = session.get_table('company', 'fact_prices')
unemployment = session.get_table('macro', 'fact_unemployment')

# Join on date (manual join)
merged = company_prices.merge(
    unemployment,
    left_on='trade_date',
    right_on='date',
    how='left'
)
```

---

## 🔧 Creating a New Model

See **[How to Create a Model](../1-getting-started/how-to/create-a-model.md)** for step-by-step instructions.

**Quick Overview:**
1. Create YAML config in `configs/models/your_model.yaml`
2. Define schema (dimensions, facts)
3. Define graph (nodes, edges, paths)
4. Define measures (optional)
5. Create Python class inheriting from `BaseModel`
6. Register in `models/implemented/`
7. Build and test

---

## 📖 Model Documentation Template

Each model document includes:

1. **Overview** - Purpose, use cases, key features
2. **Schema** - Tables, columns, data types (summary tables)
3. **Data Sources** - Where data comes from, APIs, transformations
4. **Graph Structure** - Nodes, edges, paths with diagrams
5. **Measures** - Available calculations and aggregations
6. **Design Decisions** - Why things are structured this way
7. **Usage Examples** - Code samples with real queries
8. **Partitioning Strategy** - How data is partitioned
9. **Dependencies** - What other models are required
10. **Update Frequency** - How often data refreshes

---

## 🚀 Next Steps

**New to models?** Start with **[Overview](overview.md)** to learn the concepts.

**Want to see a specific model?** Jump to:
- [Core Model](implemented/core-model.md)
- [Company Model](implemented/company-model.md)
- [Forecast Model](implemented/forecast-model.md)
- [Macro Model](implemented/macro-model.md)
- [City Finance Model](implemented/city-finance-model.md)

**Want to create your own?** See **[How to Create a Model](../1-getting-started/how-to/create-a-model.md)**

**Want to understand architecture?** See **[Models System Architecture](../3-architecture/components/models-system/overview.md)**

---

**Last Updated:** 2024-11-08
**Total Models:** 5
**Total Tables:** 18 (5 dimensions, 11 facts, 2 materialized views)
