# The de_Funk Codebase Journey
## A Complete Guide Through the Architecture, Models, and Infrastructure

**Last Updated**: 2025-11-16
**Version**: 1.0
**Purpose**: Comprehensive walkthrough of the entire de_Funk codebase for new contributors, maintainers, and decision-makers

---

## 📖 Table of Contents

1. [Welcome & Overview](#welcome--overview)
2. [The 30-Second Pitch](#the-30-second-pitch)
3. [Your Journey Begins: Three Perspectives](#your-journey-begins-three-perspectives)
4. [Part I: The Foundation - Understanding the Framework](#part-i-the-foundation---understanding-the-framework)
5. [Part II: The Data Pipeline - From API to Analytics](#part-ii-the-data-pipeline---from-api-to-analytics)
6. [Part III: The Model Ecosystem - All 8 Models Explained](#part-iii-the-model-ecosystem---all-8-models-explained)
7. [Part IV: The User Experience - Notebooks and UI](#part-iv-the-user-experience---notebooks-and-ui)
8. [Part V: The Technical Debt - What Needs Cleaning](#part-v-the-technical-debt---what-needs-cleaning)
9. [Part VI: The Roadmap - Where We're Going](#part-vi-the-roadmap---where-were-going)
10. [Quick Reference Cards](#quick-reference-cards)

---

## Welcome & Overview

Welcome to **de_Funk**, a sophisticated yet pragmatic data analytics framework that proves you don't need complex infrastructure to do powerful dimensional modeling and cross-model analytics.

This document is your **complete journey** through the codebase - from high-level architecture to specific file locations, from design patterns to technical debt, from quick wins to strategic recommendations.

### What Makes This Special?

Unlike typical documentation that describes *what* the code does, this journey explains:
- **Why** architectural decisions were made
- **How** the pieces fit together
- **Where** to find specific functionality
- **What** could be improved
- **When** to use which approach

---

## The 30-Second Pitch

**de_Funk** is a graphical overlay to a unified relational model enabling low-code interactions with data warehouses.

**In Plain English:**
- Define dimensional models in YAML (not code)
- Automatically build relationships between models
- Query across multiple models seamlessly
- Use Markdown notebooks for analytics
- Run on DuckDB (fast) or Spark (distributed)
- No Gold layer needed - analytics happen directly on Silver

**Real-World Example:**
```yaml
# Define a model in 50 lines of YAML
model: equity
dimensions:
  dim_equity: [ticker, company_name, exchange_code]
facts:
  fact_prices: [trade_date, open, high, low, close, volume]
measures:
  avg_close_price: {type: simple, column: close, aggregation: avg}
```

That's it. The framework does the rest:
- Auto-loads data from Bronze
- Validates relationships
- Materializes optimized paths
- Exposes measures for querying
- Works on both Spark and DuckDB

---

## Your Journey Begins: Three Perspectives

Before diving deep, choose your perspective:

### 🎯 **Perspective 1: The Business Analyst**
*"I want to analyze data and create dashboards"*

**Your Path:**
1. Start with [Part IV: User Experience](#part-iv-the-user-experience---notebooks-and-ui)
2. Read `QUICKSTART.md` and `RUNNING.md`
3. Explore example notebooks in `configs/notebooks/`
4. Create your first custom notebook
5. Reference [Part III: Model Ecosystem](#part-iii-the-model-ecosystem---all-8-models-explained) as needed

**Time Investment:** 2-3 hours to productivity

---

### 🔧 **Perspective 2: The Data Engineer**
*"I need to add new data sources and build models"*

**Your Path:**
1. Start with [Part II: Data Pipeline](#part-ii-the-data-pipeline---from-api-to-analytics)
2. Read `PIPELINE_GUIDE.md`
3. Study existing providers in `datapipelines/providers/`
4. Review model YAML configs in `configs/models/`
5. Check [Part I: Framework](#part-i-the-foundation---understanding-the-framework) for architecture

**Time Investment:** 4-6 hours to first contribution

---

### 🏗️ **Perspective 3: The Framework Developer**
*"I want to understand and improve the core framework"*

**Your Path:**
1. Read this entire document (1-2 hours)
2. Deep-dive into `docs/INFRASTRUCTURE_ANALYSIS.md`
3. Study `models/base/model.py` (the heart of the framework)
4. Review `models/api/session.py` (orchestration layer)
5. Check [Part V: Technical Debt](#part-v-the-technical-debt---what-needs-cleaning)

**Time Investment:** 8-12 hours to mastery

---

## Part I: The Foundation - Understanding the Framework

### 1.1 The Big Idea: YAML-Driven Graph Models

**Core Concept:** Models are graphs, not tables.

Traditional approach:
```sql
-- You write SQL joins manually every time
SELECT p.*, c.company_name, e.exchange_name
FROM fact_prices p
JOIN dim_company c ON p.ticker = c.ticker
JOIN dim_exchange e ON c.exchange_code = e.code
WHERE p.trade_date >= '2024-01-01'
```

de_Funk approach:
```yaml
# Define the graph once in YAML
graph:
  nodes:
    fact_prices: {source: bronze.prices_daily}
    dim_company: {source: bronze.ref_all_tickers}
    dim_exchange: {source: bronze.exchanges}
  edges:
    - {from: fact_prices, to: dim_company, on: [ticker=ticker]}
    - {from: dim_company, to: dim_exchange, on: [exchange_code=code]}
  paths:
    prices_with_context:
      start: fact_prices
      joins: [dim_company, dim_exchange]
```

Then query:
```python
# Framework auto-joins based on graph
df = model.get_table('prices_with_context')
# Automatically includes company_name, exchange_name, etc.
```

**Why This Matters:**
- Define relationships once, use everywhere
- Changes propagate automatically
- No SQL joins to write or maintain
- Works across Spark and DuckDB identically

---

### 1.2 The Seven-Layer Architecture

```
┌─────────────────────────────────────────────┐
│  Layer 7: Applications & UI                 │
│  - Streamlit notebooks                      │
│  - Markdown-based analytics                 │
│  - Interactive filters & exhibits           │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Layer 6: Orchestration                     │
│  - UniversalSession (cross-model queries)   │
│  - NotebookManager (user workflows)         │
│  - Pipeline orchestration                   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Layer 5: Domain Models                     │
│  - 8 business models (equity, macro, etc.)  │
│  - Model-specific convenience methods       │
│  - Measure definitions                      │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Layer 4: Framework Core                    │
│  - BaseModel (graph building)               │
│  - ModelRegistry (discovery)                │
│  - MeasureFramework (calculations)          │
│  - GraphQueryPlanner (joins)                │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Layer 3: Backend Abstraction               │
│  - Spark adapter (distributed)              │
│  - DuckDB adapter (single-machine)          │
│  - Filter engine (backend-agnostic)         │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Layer 2: Data Access                       │
│  - StorageRouter (path resolution)          │
│  - ParquetLoader (optimized reads)          │
│  - DuckDB catalog (metadata)                │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Layer 1: Storage                           │
│  - Bronze: Raw Parquet (partitioned)        │
│  - Silver: Dimensional Parquet              │
│  - DuckDB: analytics.db (catalog only)      │
└─────────────────────────────────────────────┘
```

**Key Files by Layer:**

| Layer | Primary Files | Lines of Code |
|-------|--------------|---------------|
| **7: Applications** | `app/ui/notebook_app_duckdb.py` | ~400 |
| **6: Orchestration** | `models/api/session.py` | ~1,063 |
| **5: Domain Models** | `models/implemented/*/model.py` | ~2,000 total |
| **4: Framework** | `models/base/model.py` | ~1,237 |
| **3: Backends** | `core/session/filters.py` | ~500 |
| **2: Data Access** | `models/api/dal.py` | ~300 |
| **1: Storage** | Parquet files (not code) | N/A |

---

### 1.3 The Seven Design Patterns

#### Pattern 1: **Graph-Based Planning**
- **What**: Dependencies and joins derived from NetworkX DAGs
- **Why**: Dynamic query planning without hardcoded joins
- **Where**: `models/api/graph.py`, `models/api/query_planner.py`

#### Pattern 2: **YAML as Source of Truth**
- **What**: All models defined declaratively
- **Why**: Non-developers can create models
- **Where**: `configs/models/*.yaml`

#### Pattern 3: **Backend Transparency**
- **What**: Same code works on Spark and DuckDB
- **Why**: Dev on DuckDB (fast), prod on Spark (scale)
- **Where**: `core/session/filters.py`, `models/base/model.py`

#### Pattern 4: **Lazy Evaluation + Caching**
- **What**: Models built on first access, results cached
- **Why**: Efficiency - don't load unused models
- **Where**: `models/registry.py` (lazy registration)

#### Pattern 5: **Dependency Injection**
- **What**: Session injected into models for cross-model access
- **Why**: Models can query other models seamlessly
- **Where**: `models/api/session.py` → `BaseModel.__init__()`

#### Pattern 6: **Factory Pattern**
- **What**: Registry-based instantiation
- **Why**: Extensibility - register new types without changing core
- **Where**: `models/registry.py`, `models/base/measures/registry.py`

#### Pattern 7: **Adapter Pattern**
- **What**: Abstracts Spark DataFrame vs DuckDB SQL
- **Why**: Single API for multiple backends
- **Where**: `core/session/filters.py`, backend-specific methods in BaseModel

---

### 1.4 Configuration System (NEW - Nov 2025)

**The Modern Way:**
```python
from config import ConfigLoader

# Single entry point for ALL configuration
config = ConfigLoader().load(connection_type="duckdb")

# Type-safe access
print(config.repo_root)           # Path object
print(config.connection.type)     # "duckdb"
print(config.apis["polygon"])     # Auto-discovered API config
```

**Precedence (highest to lowest):**
1. Explicit parameters → `ConfigLoader.load(connection_type="duckdb")`
2. Environment variables → `.env` file
3. Configuration files → `configs/*.json`
4. Default values → `config/constants.py`

**Key Files:**
- `config/loader.py` - ConfigLoader implementation (150 lines)
- `config/models.py` - Type-safe dataclasses (100 lines)
- `utils/repo.py` - Repository discovery (80 lines)

**Migration Status:** ⚠️ ~50% of code still using old patterns (see Part V)

---

## Part II: The Data Pipeline - From API to Analytics

### 2.1 The Two-Layer Architecture (Bronze → Silver)

**Why Only Two Layers?**

Traditional Medallion (3 layers):
```
Bronze (raw) → Silver (clean) → Gold (aggregated)
```

de_Funk (2 layers):
```
Bronze (raw) → Silver (dimensional) → DuckDB queries (Gold-equivalent)
```

**Reasoning:**
- DuckDB is so fast (10-100x faster than Spark) that we don't need materialized aggregates
- Queries run directly against Silver Parquet files
- DuckDB catalog stores metadata/views, not duplicate data
- Simpler architecture, same performance

---

### 2.2 Complete Data Flow: API → Analytics

```
┌──────────────┐
│  External    │
│  APIs        │  Polygon.io, BLS, Chicago Data Portal
└──────┬───────┘
       │
       ↓ HTTP Requests
┌──────────────┐
│  Providers   │  API clients (polygon_provider.py, bls_provider.py)
└──────┬───────┘
       │
       ↓ JSON Responses
┌──────────────┐
│  Facets      │  Normalize to DataFrame (ref_all_tickers_facet.py)
└──────┬───────┘
       │
       ↓ Spark/Pandas DataFrames
┌──────────────┐
│  Ingestors   │  Orchestrate fetching (company_ingestor.py)
└──────┬───────┘
       │
       ↓ Write Parquet
┌──────────────────────────────────────┐
│  BRONZE LAYER                        │
│  storage/bronze/{provider}/{table}/  │
│  - Partitioned by date               │
│  - Raw schema from API               │
└──────┬───────────────────────────────┘
       │
       ↓ Model.build() reads Bronze
┌──────────────┐
│  BaseModel   │  Graph construction (model.py)
│  build()     │  - Load nodes from Bronze
└──────┬───────┘  - Validate edges
       │          - Materialize paths
       ↓
┌──────────────────────────────────────┐
│  SILVER LAYER                        │
│  storage/silver/{model}/{table}/     │
│  - Star/snowflake schemas            │
│  - Optimized for analytics           │
└──────┬───────────────────────────────┘
       │
       ↓ UniversalSession queries
┌──────────────┐
│  DuckDB      │  analytics.db (catalog + temp workspace)
│  or Spark    │  - No data duplication
└──────┬───────┘  - Just metadata & views
       │
       ↓ DataFrame results
┌──────────────┐
│  Notebook    │  Streamlit UI
│  Manager     │  - Apply filters
└──────┬───────┘  - Render exhibits
       │
       ↓ HTML/Plotly
┌──────────────┐
│  User's      │
│  Browser     │
└──────────────┘
```

---

### 2.3 Data Providers (3 Active)

#### Provider 1: **Polygon.io** (Stock Market Data)
- **Status:** ✅ ACTIVE
- **Ingestor:** `datapipelines/ingestors/company_ingestor.py` (177 lines)
- **Facets:** 5 facets (ref_all_tickers, exchanges, prices, news, **ref_ticker**)
- **Bronze Tables:** 5 tables
- **Feeds Models:** equity, corporate
- **API Limit:** 1,000 results per request
- **⚠️ Issue:** ref_ticker facet is 100% unused (see Part V)

#### Provider 2: **Bureau of Labor Statistics** (Economic Data)
- **Status:** ✅ ACTIVE
- **Ingestor:** `datapipelines/providers/bls/bls_ingestor.py`
- **Series:** 4 (unemployment, CPI, employment, wages)
- **Bronze Tables:** 1 table (monthly_data)
- **Feeds Models:** macro
- **Frequency:** Monthly updates

#### Provider 3: **Chicago Data Portal** (Municipal Data)
- **Status:** ✅ ACTIVE
- **Ingestor:** `datapipelines/providers/chicago/chicago_ingestor.py`
- **Datasets:** Unemployment, permits, licenses, indicators
- **Bronze Tables:** 5 tables
- **Feeds Models:** city_finance
- **Spatial Data:** Includes lat/long for 77 community areas

---

### 2.4 Facet Pattern (Data Normalization)

**Purpose:** Convert messy API JSON → clean, typed DataFrames

**Example: Polygon Prices Facet**
```python
# Input (JSON from API):
{
  "results": [
    {"T": "AAPL", "o": 150.5, "h": 152.0, "l": 149.0, "c": 151.5, "v": 50000000, "t": 1704067200000}
  ]
}

# Facet transformation:
class PricesDailyGroupedFacet(BaseFacet):
    def normalize(self, batches):
        # 1. Parse JSON → DataFrame
        # 2. Rename: T→ticker, o→open, h→high, l→low, c→close, v→volume
        # 3. Convert: t (timestamp millis) → trade_date (YYYY-MM-DD)
        # 4. Coerce types: float64, int64
        # 5. Deduplicate
        return df

# Output (Parquet-ready DataFrame):
| ticker | trade_date | open  | high  | low   | close | volume    |
|--------|------------|-------|-------|-------|-------|-----------|
| AAPL   | 2024-01-01 | 150.5 | 152.0 | 149.0 | 151.5 | 50000000  |
```

**All Facets:** `datapipelines/providers/{provider}/facets/*.py`

---

### 2.5 Bronze Sink (Storage Layer)

**Purpose:** Write DataFrames to partitioned Parquet files

**Key Features:**
- Partition-aware writes (by date, snapshot_dt)
- Idempotent (skip if partition exists)
- Schema evolution support
- Atomic writes

**Example:**
```python
sink = BronzeSink(storage_cfg, spark)

# Writes to: storage/bronze/polygon/prices_daily/trade_date=2024-01-01/
sink.write_if_missing("prices_daily", {"trade_date": "2024-01-01"}, df)

# Check before fetching:
if not sink.exists("prices_daily", {"trade_date": "2024-01-01"}):
    # Fetch from API
    pass
```

**File:** `datapipelines/ingestors/bronze_sink.py`

---

### 2.6 Silver Layer Building (Model Construction)

**Trigger:** `model.build()` called (usually on first table access)

**Process:**
1. **Load Nodes** from Bronze
   - Read Parquet files
   - Apply column selections
   - Derive calculated columns
   - Enforce unique keys

2. **Validate Edges**
   - Check foreign keys exist
   - Validate cross-model references
   - Log warnings for missing joins

3. **Materialize Paths**
   - Execute joins based on graph
   - Write to Silver layer
   - Create optimized views

4. **Register Measures**
   - Parse measure definitions
   - Register in measure registry
   - Prepare for execution

**File:** `models/base/model.py` lines 300-500

---

## Part III: The Model Ecosystem - All 8 Models Explained

### 3.1 Model Dependency Graph

```
        Tier 0: Foundation
        ┌──────────┐
        │   core   │  Calendar dimension (2000-2050)
        └────┬─────┘
             │
    ┌────────┴────────────────┐
    │                         │
Tier 1: Independent       Tier 1: Business
┌──────────┐            ┌──────────┬──────────┐
│  macro   │            │  equity  │corporate │
│ (BLS)    │            │ (Polygon)│ (future) │
└────┬─────┘            └────┬─────┴────┬─────┘
     │                       │          │
     │                       │          │ (bidirectional)
     │                       │          │
Tier 2: Local          Tier 2: Holdings
┌────┴──────────┐      ┌─────┴─────┐
│ city_finance  │      │    etf    │
│  (Chicago)    │      │(Holdings) │
└───────────────┘      └─────┬─────┘
                             │
                      Tier 3: Predictions
                       ┌─────┴─────┐
                       │ forecast  │
                       │(8 models) │
                       └───────────┘
```

**Build Order:**
1. core (no dependencies)
2. macro, equity, corporate (depend on core)
3. city_finance, etf (depend on Tier 0-1)
4. forecast (depends on equity)

---

### 3.2 Model-by-Model Tour

#### Model 1: **CORE** (Calendar Dimension)
**Tagline:** The foundation - every model's best friend

**Purpose:** Provide rich date dimension for time-series filtering

**Key Tables:**
- `dim_calendar` - One row per day (2000-2050)

**Key Columns (25 total):**
```
date, day_of_week, week_of_year, month, quarter, year
fiscal_year, fiscal_quarter, is_weekend, is_holiday
first_day_of_month, last_day_of_month
calendar_year_month (YYYY-MM for grouping)
```

**Dependencies:** None (Tier 0)

**Usage Example:**
```python
# Every model can filter by date ranges using core
df = model.query_table('fact_prices', filters={
    'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}
})
```

**Status:** ✅ FULLY ACTIVE (always available)

**Files:**
- Config: `configs/models/core.yaml` (110 lines)
- Implementation: `models/implemented/core/model.py` (80 lines)
- Data: Seed data (generated, not from API)

---

#### Model 2: **EQUITY** (Tradable Securities)
**Tagline:** Trading instruments and market data

**Purpose:** Stock prices, volumes, technical indicators, news

**Key Tables (7):**
```
Dimensions:
  dim_equity        - Tradable securities (ticker symbols)
  dim_exchange      - Stock exchanges (NASDAQ, NYSE)

Facts:
  fact_equity_prices      - Daily OHLCV (open/high/low/close/volume)
  fact_equity_technicals  - RSI, MACD, Bollinger, ATR, volatility, beta
  fact_equity_news        - News articles with sentiment

Paths (Materialized):
  equity_prices_with_company - Prices + equity + exchange context
  equity_news_with_company   - News + equity context
```

**Key Columns:**
```sql
-- dim_equity
ticker (PK), company_name, exchange_code, company_id (FK→corporate),
shares_outstanding, listing_date, delisting_date, is_active

-- fact_equity_prices
ticker, trade_date (PKs), open, high, low, close, volume, volume_weighted

-- fact_equity_technicals
ticker, trade_date (PKs), sma_20, sma_50, sma_200, rsi_14, macd,
bollinger_upper/middle/lower, atr_14, volatility_20d, beta
```

**Measures (30+):**
- Simple: `avg_close_price`, `total_volume`, `max_high`, `min_low`
- Computed: `avg_market_cap`, `price_range`
- Weighted: `market_cap_weighted_index`, `volume_weighted_index`, `equal_weighted_index`
- Technical: `avg_rsi`, `avg_volatility_20d`, `avg_beta`

**Cross-Model Edges:**
```yaml
# Equity → Corporate (many-to-one)
- from: dim_equity
  to: corporate.dim_corporate
  on: [company_id=company_id]
```

**Dependencies:** core

**Data Source:** Polygon.io (prices, technicals, news)

**Status:** ✅ FULLY ACTIVE

**Files:**
- Config: `configs/models/equity.yaml` (570 lines)
- Implementation: `models/implemented/equity/model.py` (356 lines)
- Domains: `models/implemented/equity/domains/` (weighting, technical, risk)

**Migration Note:** Replaces deprecated `company` model

---

#### Model 3: **CORPORATE** (Business Entities)
**Tagline:** Legal entities and fundamentals (future)

**Purpose:** Company information, SEC filings, financial statements

**Key Tables (4):**
```
Dimensions:
  dim_corporate - Legal business entities

Facts (Future - Placeholders):
  fact_sec_filings      - SEC filing metadata
  fact_financials       - Financial statements (10-K, 10-Q)
  fact_financial_ratios - PE, PB, ROE, margins, growth rates
```

**Key Columns:**
```sql
-- dim_corporate
company_id (PK), cik_number (SEC identifier), company_name, legal_name,
ticker_primary (FK→equity), sector, industry, sic_code,
incorporation_state, headquarters_city/state, website
```

**Measures (Placeholders):**
- `company_count` (active now)
- `avg_revenue`, `avg_pe_ratio`, `avg_roe` (future)

**Cross-Model Edges:**
```yaml
# Corporate → Equity (bidirectional relationship)
- from: dim_corporate
  to: equity.dim_equity
  on: [ticker_primary=ticker]
```

**Dependencies:** core, equity

**Data Source:** Currently manual/seed, future = SEC EDGAR API

**Status:** 🟡 PARTIAL (dim_corporate exists, facts are placeholders)

**Files:**
- Config: `configs/models/corporate.yaml` (237 lines)
- Implementation: `models/implemented/corporate/model.py` (150 lines)

**Roadmap:**
- Phase 1: SEC EDGAR integration (Q1 2025)
- Phase 2: Financial data pipeline
- Phase 3: Fundamental analysis measures

---

#### Model 4: **MACRO** (Economic Indicators)
**Tagline:** National economic trends

**Purpose:** BLS economic indicators for macro analysis

**Key Tables (2):**
```
Facts:
  fact_monthly_data - Economic time series (long format)

Paths:
  monthly_data_wide - Pivoted view for dashboards
```

**BLS Series (4):**
1. **LNS14000000** - Unemployment rate
2. **CUUR0000SA0** - Consumer Price Index (CPI)
3. **CES0000000001** - Total nonfarm employment
4. **CES0500000003** - Average hourly earnings

**Key Columns:**
```sql
-- fact_monthly_data (long format)
series_id, date, value, series_name, category, units

-- monthly_data_wide (pivoted)
date, unemployment_rate, cpi, total_employment, avg_hourly_earnings
```

**Measures:**
- `avg_unemployment_rate`
- `avg_cpi`
- `avg_total_employment`
- `avg_hourly_earnings`

**Dependencies:** core

**Data Source:** Bureau of Labor Statistics API

**Status:** 🟡 PARTIAL (4 series active, monthly updates)

**Files:**
- Config: `configs/models/macro.yaml` (185 lines)
- Implementation: `models/implemented/macro/model.py` (120 lines)
- Ingestor: `datapipelines/providers/bls/bls_ingestor.py`

---

#### Model 5: **CITY_FINANCE** (Municipal Data)
**Tagline:** Chicago-specific economic and civic data

**Purpose:** Local economic indicators, permits, licenses, community profiles

**Key Tables (6):**
```
Dimensions:
  dim_community_area - 77 Chicago community areas with lat/long

Facts:
  fact_community_unemployment - Unemployment by community
  fact_business_licenses      - Business license issuance
  fact_building_permits       - Construction permits
  fact_civic_indicators       - General indicators
  fact_unemployment_comparison - Local vs national (cross-model!)
```

**Key Columns:**
```sql
-- dim_community_area
area_number (PK), area_name, latitude, longitude, population

-- fact_community_unemployment
area_number, date, unemployment_rate, labor_force, employed, unemployed
```

**Unique Feature: Cross-Model Analysis**
```python
# Compare local (Chicago) to national (BLS) unemployment
df = city_model.compare_to_national_unemployment()
# Returns: area_name, date, local_rate, national_rate, difference
```

**Cross-Model Edges:**
```yaml
# City Finance → Macro (unemployment comparison)
- from: fact_unemployment_comparison
  to: macro.fact_monthly_data
  on: [date=date]
  conditions: [series_id='LNS14000000']  # National unemployment
```

**Dependencies:** core, macro (for comparison)

**Data Source:** Chicago Data Portal (Socrata API)

**Status:** 🟡 PARTIAL (infrastructure ready, data ingestion tested)

**Files:**
- Config: `configs/models/city_finance.yaml` (280 lines)
- Implementation: `models/implemented/city_finance/model.py` (200 lines)
- Ingestor: `datapipelines/providers/chicago/chicago_ingestor.py`

**Spatial Analysis:** Ready for geo-mapping with lat/long

---

#### Model 6: **ETF** (Exchange-Traded Funds)
**Tagline:** Holdings-based portfolio analysis

**Purpose:** ETF composition, performance, and holdings-weighted analytics

**Key Tables (4):**
```
Dimensions:
  dim_etf - ETF metadata (ticker, name, expense_ratio)

Facts:
  fact_etf_prices    - Daily ETF prices (OHLCV)
  dim_etf_holdings   - Holdings snapshot (ticker, weight, shares, as_of_date)

Paths:
  prices_with_info         - ETF prices + metadata
  holdings_with_equity     - Holdings → equity prices (cross-model!)
```

**Key Columns:**
```sql
-- dim_etf
etf_ticker (PK), etf_name, expense_ratio, inception_date

-- dim_etf_holdings (temporal dimension!)
etf_ticker, holding_ticker (FKs), as_of_date, weight_percent,
shares_held, market_value
```

**Unique Feature: Cross-Model Weighted Measures**
```yaml
measures:
  holdings_weighted_return:
    type: weighted
    source: equity.fact_equity_prices.close  # ← Cross-model!
    weighting_method: etf_holdings
    entity: etf_ticker

  holdings_weighted_volume:
    type: weighted
    source: equity.fact_equity_prices.volume  # ← Cross-model!
    weighting_method: etf_holdings
```

**How It Works:**
1. ETF model queries equity model for stock prices
2. Applies holdings weights from dim_etf_holdings
3. Calculates weighted average return/volume
4. Result: ETF performance derived from underlying stocks

**Cross-Model Edges:**
```yaml
# ETF Holdings → Equity (many-to-one)
- from: dim_etf_holdings
  to: equity.dim_equity
  on: [holding_ticker=ticker]
```

**Dependencies:** core, equity, corporate

**Data Source:** Polygon.io (ETF holdings API)

**Status:** 🟡 PARTIAL (schema ready, holdings data pending)

**Files:**
- Config: `configs/models/etf.yaml` (320 lines)
- Implementation: `models/implemented/etf/model.py` (180 lines)
- Weighting: `models/implemented/etf/domains/weighting.py` (custom strategy)

**Innovation:** Demonstrates cross-model measure calculation

---

#### Model 7: **FORECAST** (Time Series Predictions)
**Tagline:** Machine learning predictions on equity prices

**Purpose:** Generate and evaluate time series forecasts using multiple models

**Key Tables (3):**
```
Facts:
  fact_forecasts - Predicted values by model/ticker/horizon
  fact_forecast_metrics - Model accuracy (MAE, RMSE, MAPE, R²)
  dim_model_registry - Trained model metadata
```

**8 Model Variants:**
```
ARIMA Family:
  - arima_7d   (7-day horizon)
  - arima_14d  (14-day horizon)
  - arima_30d  (30-day horizon)
  - arima_60d  (60-day horizon)

Prophet Family:
  - prophet_7d
  - prophet_30d
  - prophet_60d

Machine Learning:
  - random_forest_14d
  - random_forest_30d
```

**Key Columns:**
```sql
-- fact_forecasts
ticker, forecast_date, prediction_date, model_name,
predicted_close, confidence_lower, confidence_upper

-- fact_forecast_metrics
ticker, model_name, train_start_date, train_end_date,
mae, rmse, mape, r_squared
```

**Features Used (ARIMA/Prophet):**
```
Price lags: lag_1, lag_2, ..., lag_30
Rolling stats: rolling_mean_7/14/30, rolling_std_7/14/30
Temporal: day_of_week, month, quarter
Technical: rsi_14, macd, volatility_20d (from equity model)
```

**Cross-Model Edges:**
```yaml
# Forecast → Equity (training data)
- from: fact_forecasts
  to: equity.fact_equity_prices
  on: [ticker=ticker, forecast_date=trade_date]
```

**Dependencies:** core, equity, corporate

**Data Source:** Internal (trains on equity historical prices)

**Status:** 🟡 PARTIAL (models trainable, scripts functional)

**Files:**
- Config: `configs/models/forecast.yaml` (425 lines)
- Implementation: `models/implemented/forecast/company_forecast_model.py` (450 lines)
- Scripts: `scripts/run_forecasts.py`, `scripts/run_forecast_model.py`

**Roadmap:**
- Add LSTM/GRU deep learning models
- Ensemble predictions
- Real-time forecast updates

---

#### Model 8: **COMPANY** (DEPRECATED)
**Status:** ⚠️ DEPRECATED - Being phased out

**Replacement:** Equity model (for prices) + Corporate model (for fundamentals)

**See Part V** for migration details and cleanup recommendations.

---

### 3.3 Model Maturity Matrix

| Model | Config | Implementation | Data Pipeline | Silver Data | Measures | Status |
|-------|--------|----------------|---------------|-------------|----------|--------|
| **core** | ✅ 100% | ✅ 100% | ✅ Seed | ✅ Always | ✅ N/A | ACTIVE |
| **equity** | ✅ 100% | ✅ 100% | ✅ Polygon | ✅ Built | ✅ 30+ | ACTIVE |
| **corporate** | ✅ 100% | ✅ 80% | 🟡 Partial | 🟡 Dim only | 🟡 1 | PARTIAL |
| **macro** | ✅ 100% | ✅ 100% | ✅ BLS | 🟡 4 series | ✅ 4 | PARTIAL |
| **city_finance** | ✅ 100% | ✅ 100% | ✅ Chicago | 🟡 Tested | ✅ 6+ | PARTIAL |
| **etf** | ✅ 100% | ✅ 100% | 🟡 Schema | ❌ Pending | ✅ 10+ | PARTIAL |
| **forecast** | ✅ 100% | ✅ 100% | ✅ Internal | 🟡 On-demand | ✅ 8 | PARTIAL |
| **company** | ⚠️ Deprecated | ⚠️ Compat | ⚠️ Old | ⚠️ Legacy | ⚠️ Migrated | DEPRECATED |

---

## Part IV: The User Experience - Notebooks and UI

### 4.1 The Notebook Philosophy

**Core Idea:** Analytics should be documents, not code.

**Traditional BI:**
```python
# User writes Python/SQL code
import pandas as pd
df = spark.sql("SELECT * FROM prices WHERE ticker='AAPL'")
df = df[df['date'] > '2024-01-01']
# ... 50 more lines of code
```

**de_Funk Approach:**
```markdown
---
title: Stock Analysis
models: [equity]
---

$filter${
  type: date_range
  column: trade_date
  default: {start: "2024-01-01", end: "2024-12-31"}
}

$exhibits${
  type: line_chart
  data: equity.fact_equity_prices
  x: trade_date
  y: close
  group_by: ticker
}
```

**Result:** Non-technical users create sophisticated analytics

---

### 4.2 Notebook Anatomy

```markdown
---
# YAML Front Matter (Metadata)
id: my_notebook
title: Equity Analysis
description: Analyze stock performance
models: [equity, macro]  # Which models to load
tags: [stocks, analysis]
---

# Filter Definitions (Optional)
$filter${
  id: ticker_filter
  type: select
  multi: true
  source: {model: equity, table: dim_equity, column: ticker}
  default: ["AAPL", "MSFT", "GOOGL"]
}

$filter${
  id: date_range
  type: date_range
  column: trade_date
  default: {start: "2024-01-01", end: "2024-12-31"}
}

# Markdown Content
## Stock Performance Analysis

This analysis examines price trends across selected equities.

# Exhibit Definitions (Visualizations)
$exhibits${
  id: price_chart
  type: line_chart
  data: equity.fact_equity_prices
  x: trade_date
  y: close
  group_by: ticker
  title: "Daily Close Prices"
}

$exhibits${
  type: summary_stats
  data: equity.fact_equity_prices
  metrics: [avg_close_price, total_volume, max_high, min_low]
  group_by: ticker
}
```

**What Happens:**
1. NotebookManager parses YAML + Markdown
2. FilterEngine applies user selections
3. UniversalSession queries models
4. ExhibitRenderer creates Plotly visualizations
5. Streamlit displays in browser

---

### 4.3 Filter Types (6 Available)

| Type | Purpose | UI Component | Example |
|------|---------|--------------|---------|
| **select** | Choose from list | Dropdown/Multiselect | Ticker selection |
| **date_range** | Date filtering | Date pickers (start/end) | Trade date range |
| **slider** | Numeric range | Slider widget | Volume threshold |
| **text** | Free text search | Text input | Company name search |
| **checkbox** | Boolean toggle | Checkbox | Include inactive |
| **radio** | Single choice | Radio buttons | Aggregation level |

**Filter Sources:**
```yaml
# Static options
filter:
  type: select
  options: ["AAPL", "MSFT", "GOOGL"]

# Dynamic from database
filter:
  type: select
  source: {model: equity, table: dim_equity, column: ticker}

# With conditions
filter:
  type: select
  source:
    model: equity
    table: dim_equity
    column: ticker
    where: {is_active: true}  # Only active tickers
```

---

### 4.4 Exhibit Types (7 Available)

| Type | Purpose | Plotly Chart | Use Case |
|------|---------|--------------|----------|
| **line_chart** | Time series trends | `px.line()` | Price over time |
| **bar_chart** | Categorical comparison | `px.bar()` | Volume by ticker |
| **scatter_plot** | Correlation analysis | `px.scatter()` | Price vs volume |
| **heatmap** | Matrix visualization | `px.imshow()` | Correlation matrix |
| **box_plot** | Distribution analysis | `px.box()` | Price distribution |
| **summary_stats** | Aggregated metrics | Custom table | Key statistics |
| **data_table** | Raw data display | Streamlit table | Detailed records |

**Exhibit Configuration:**
```yaml
exhibits:
  type: line_chart
  data: equity.fact_equity_prices  # Model.table reference
  x: trade_date
  y: close
  group_by: ticker              # Multiple lines
  color: ticker                 # Color by group
  title: "Stock Prices"
  height: 600
  filters:                      # Apply notebook filters
    - ticker_filter
    - date_range
```

---

### 4.5 Folder Contexts (Shared Filters)

**Problem:** Many notebooks need the same filters (e.g., date range)

**Solution:** `.filter_context.yaml` at folder level

```yaml
# configs/notebooks/Financial Analysis/.filter_context.yaml
filters:
  - id: date_range
    type: date_range
    column: trade_date
    default: {start: "2024-01-01", end: "2024-12-31"}

  - id: ticker_selection
    type: select
    multi: true
    source: {model: equity, table: dim_equity, column: ticker}
    default: ["AAPL", "MSFT", "GOOGL"]
```

**Effect:** All notebooks in `Financial Analysis/` inherit these filters

---

### 4.6 Complete Data Flow (User Perspective)

```
User opens notebook
       ↓
Streamlit renders sidebar with filters
       ↓
User selects: ["AAPL", "MSFT"], date range [2024-01-01 to 2024-12-31]
       ↓
NotebookManager.apply_filters()
       ↓
FilterEngine converts to backend-specific filters:
  - DuckDB: WHERE ticker IN ('AAPL', 'MSFT') AND trade_date BETWEEN ...
  - Spark: df.filter((col('ticker').isin(...)) & (col('trade_date') >= ...))
       ↓
UniversalSession.query(model="equity", table="fact_equity_prices", filters=...)
       ↓
Backend executes query against Silver Parquet files
       ↓
DataFrame returned to notebook
       ↓
ExhibitRenderer.render(type="line_chart", data=df, ...)
       ↓
Plotly chart displayed in Streamlit
       ↓
User sees interactive visualization
```

---

### 4.7 Key UI Files

| File | Purpose | Lines | Key Functions |
|------|---------|-------|---------------|
| `app/ui/notebook_app_duckdb.py` | Main Streamlit app | 400 | `main()`, `render_sidebar()` |
| `app/notebook/parser.py` | Parse markdown notebooks | 350 | `NotebookParser.parse()` |
| `app/notebook/manager.py` | Notebook lifecycle | 450 | `NotebookManager.load()`, `apply_filters()` |
| `app/notebook/filters/engine.py` | Filter application | 300 | `FilterEngine.apply()` |
| `app/notebook/exhibits/renderer.py` | Exhibit rendering | 500 | `ExhibitRenderer.render()` |
| `app/services/notebook_service.py` | Business logic | 200 | `discover_notebooks()`, `get_notebook()` |

---

## Part V: The Technical Debt - What Needs Cleaning

### 5.1 Technical Debt Summary

**Total Estimated Cleanup:** 59 files, ~20-30 hours

| Category | Files | Hours | Impact | Priority |
|----------|-------|-------|--------|----------|
| **Unused code** | 2 | 1-2 | ⚡⚡⚡ High | P0 |
| **Model migration** | 13 | 3-4 | 📝📝 Medium | P0 |
| **Config consolidation** | 8 | 3-4 | 🧹🧹 Medium | P1 |
| **Path discovery** | 32 | 2-3 | 🔧 Low | P1 |
| **Naming cleanup** | 4 | 2-3 | 🏗️ Low | P2 |

---

### 5.2 Priority 0: Immediate Wins (4-6 hours)

#### Issue 1: Unused ref_ticker Pipeline Step
**Impact:** ⚡⚡⚡ 25% faster ingestion, 100 fewer API calls

**Problem:**
```python
# datapipelines/ingestors/company_ingestor.py:125-132
# Step 3: Fetches per-ticker details (100 API calls)
r_f = RefTickerFacet(self.spark, tickers=tickers_list)
r_batches = self._fetch_calls_concurrent(r_f.calls(), max_workers=10)
df_r = r_f.normalize(r_batches)
self.sink.write_if_missing("ref_ticker", {"snapshot_dt": snap}, df_r)
```

**Evidence:**
```bash
grep -r "ref_ticker" configs/models/*.yaml
# Result: 0 matches - NO MODEL USES THIS TABLE
```

**Fix:**
```bash
# DELETE lines 125-132 from company_ingestor.py
# DELETE file: datapipelines/providers/polygon/facets/ref_ticker_facet.py
```

**Benefit:** 25% fewer API calls (900 → 675 for typical dataset)

**Time:** 1 hour
**Risk:** None (table unused)

---

#### Issue 2: Notebooks Using Deprecated Company Model
**Impact:** 📝📝 Remove deprecation warnings, modernize notebooks

**Problem:** 10+ notebooks reference `models: [company]`

**Files:**
```
configs/notebooks/stock_analysis.md
configs/notebooks/aggregate_stock_analysis.md
configs/notebooks/dimension_selector_demo.md
configs/notebooks/Financial Analysis/stock_analysis.md
configs/notebooks/forecast_analysis_example.md
configs/notebooks/forecast_analysis.md
configs/notebooks/measures_catalog.md
configs/notebooks/stock_analysis_dynamic.md
configs/notebooks/stock_analysis_interactive.md
configs/notebooks/README_MARKDOWN.md
```

**Fix Pattern:**
```yaml
# OLD
models: [company]
source: {model: company, table: fact_prices}

# NEW
models: [equity]
source: {model: equity, table: fact_equity_prices}
```

**Time:** 2-3 hours (10 files × 15 min each)
**Risk:** Low (test each notebook in UI)

---

#### Issue 3: Deprecated env_loader Usage
**Impact:** 🧹🧹 Single configuration pattern

**Problem:** 3 files still import deprecated `utils/env_loader.py`

**Files:**
- `run_full_pipeline.py`
- `test_env_loader.py`
- `API_key_tests.py`

**Fix:**
```python
# OLD
from utils.env_loader import inject_credentials_into_config
polygon_cfg = json.load(f)
polygon_cfg = inject_credentials_into_config(polygon_cfg, 'polygon')

# NEW
from config import ConfigLoader
config = ConfigLoader().load()
polygon_cfg = config.apis["polygon"]  # Credentials auto-injected
```

**Time:** 1-2 hours (3 files)
**Risk:** Low (ConfigLoader well-tested)

---

### 5.3 Priority 1: Structural Cleanup (6-9 hours)

#### Issue 4: Inconsistent Path Discovery (32 files)
**Impact:** 🔧 Single import pattern

**Problem:** 32 files use manual `sys.path.insert()` patterns

**Current Pattern (5 lines):**
```python
_current_file = Path(__file__).resolve()
for _parent in [_current_file.parent] + list(_current_file.parents):
    if (_parent / "configs").exists():
        _repo_root = _parent
        break
sys.path.insert(0, str(_repo_root))
```

**Better Pattern (1 line):**
```python
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()
```

**Automation:** Use existing `scripts/auto_fix_migration.py`

**Time:** 2-3 hours (mostly automated)
**Risk:** Very low (auto-fix script tested)

---

#### Issue 5: CompanyPolygonIngestor Naming
**Impact:** 🏗️ Clear domain ownership

**Problem:** Ingestor named "Company" but feeds "Equity" model

**Fix:**
```bash
# Rename file
mv datapipelines/ingestors/company_ingestor.py \
   datapipelines/ingestors/equity_ingestor.py

# Rename class
class CompanyPolygonIngestor → class EquityPolygonIngestor

# Update imports (3 files)
```

**Time:** 1 hour
**Risk:** Low (well-isolated change)

---

#### Issue 6: Exhibit Logic Fragmentation
**Impact:** 🔧 Consolidate rendering logic

**Problem:** Exhibit logic split across 2 directories:
- `app/notebook/exhibits/` (parsing, validation)
- `app/ui/components/exhibits/` (rendering)

**Recommendation:**
```
Consolidate to: app/notebook/exhibits/
  ├── types.py         (data types)
  ├── validator.py     (validation)
  ├── renderer.py      (Plotly rendering)
  └── builders/        (chart builders)
```

**Time:** 2-3 hours
**Risk:** Medium (many imports to update)

---

### 5.4 Priority 2: Nice-to-Haves (8-12 hours)

#### Issue 7: Scripts Organization
**Impact:** Better developer experience

**Current:** 27 scripts in flat `scripts/` directory

**Recommendation:**
```
scripts/
├── build/          (build_all_models.py, rebuild_model.py)
├── pipeline/       (run_full_pipeline.py, clear_and_refresh.py)
├── forecasts/      (run_forecasts.py, run_forecast_model.py)
├── testing/        (test_*.py)
└── migration/      (auto_fix_*.py, validate_migration.py)
```

**Time:** 3-4 hours
**Risk:** Low (better organization, not a functional change)

---

#### Issue 8: Archive Company Model
**Impact:** Clear deprecation status

**Action:**
```bash
# After notebooks updated
mv configs/models/company.yaml \
   configs/models/.deprecated/company.yaml

mv models/implemented/company/ \
   models/implemented/.deprecated/company/
```

**Time:** 1 hour
**Risk:** None (already deprecated)

---

### 5.5 Optional: Breaking Changes (Future)

#### Bronze Table Renaming
**Impact:** Domain-specific clarity

**Current → Proposed:**
```
ref_all_tickers → equity_tickers
prices_daily    → equity_prices_daily
news            → equity_news
exchanges       → exchanges (OK as-is)
```

**Effort:** 4-6 hours (requires Bronze rebuild)
**Risk:** High (breaking change)
**Recommendation:** Consider for v2.0

---

### 5.6 Technical Debt Tracker

| ID | Issue | Priority | Hours | Risk | Dependencies |
|----|-------|----------|-------|------|--------------|
| TD-001 | Remove ref_ticker | P0 | 1 | None | None |
| TD-002 | Update notebooks | P0 | 2-3 | Low | None |
| TD-003 | Remove env_loader | P0 | 1-2 | Low | None |
| TD-004 | Path discovery | P1 | 2-3 | Very Low | None |
| TD-005 | Rename ingestor | P1 | 1 | Low | TD-002 |
| TD-006 | Consolidate exhibits | P1 | 2-3 | Medium | None |
| TD-007 | Organize scripts | P2 | 3-4 | Low | None |
| TD-008 | Archive company model | P2 | 1 | None | TD-002, TD-005 |

**Total P0-P1:** 11-16 hours
**Total All:** 17-23 hours

---

## Part VI: The Roadmap - Where We're Going

### 6.1 Immediate Focus (Next 2-4 Weeks)

**Phase 1: Clean Technical Debt**
- ✅ Remove ref_ticker step (1 hour)
- ✅ Update 10 notebooks to equity model (3 hours)
- ✅ Consolidate ConfigLoader usage (2 hours)
- ✅ Standardize path discovery (3 hours)

**Deliverable:** Clean, consistent codebase with 25% faster pipeline

---

**Phase 2: Complete Model Migrations**
- ✅ Rename CompanyPolygonIngestor → EquityPolygonIngestor (1 hour)
- ✅ Archive deprecated company model (1 hour)
- ✅ Update documentation (2 hours)

**Deliverable:** All references to "company" removed, clear equity/corporate separation

---

### 6.2 Short-Term (Next 1-3 Months)

**Corporate Model Completion**
- [ ] Integrate SEC EDGAR API
- [ ] Build fact_sec_filings pipeline
- [ ] Build fact_financials pipeline
- [ ] Implement fundamental measures (PE, ROE, margins)

**ETF Model Completion**
- [ ] Ingest ETF holdings data (Polygon ETF API)
- [ ] Build holdings temporal tracking
- [ ] Test cross-model weighted measures
- [ ] Create ETF analysis notebooks

**Macro Model Enhancement**
- [ ] Add more BLS series (GDP, inflation expectations)
- [ ] Implement economic indicator dashboard
- [ ] Cross-model analysis with equity (sector performance vs macro)

---

### 6.3 Medium-Term (3-6 Months)

**Framework Enhancements**
- [ ] GraphQL API layer (query models via API)
- [ ] Real-time data support (streaming ingestion)
- [ ] Advanced caching strategies
- [ ] Query optimization engine

**Forecast Model Evolution**
- [ ] Add LSTM/GRU deep learning models
- [ ] Ensemble predictions (combine multiple models)
- [ ] Feature importance analysis
- [ ] Automated hyperparameter tuning

**UI/UX Improvements**
- [ ] Notebook version control
- [ ] Collaborative editing
- [ ] Export to PDF/PowerPoint
- [ ] Mobile-responsive design

---

### 6.4 Long-Term Vision (6-12 Months)

**Multi-Tenant SaaS**
- [ ] User authentication & authorization
- [ ] Workspace isolation
- [ ] Usage metering
- [ ] Cloud deployment (AWS/Azure/GCP)

**Domain Expansion**
- [ ] Healthcare domain models (claims, patients, providers)
- [ ] Retail domain models (sales, inventory, customers)
- [ ] Logistics domain models (shipments, warehouses, routes)

**AI-Powered Features**
- [ ] Natural language queries ("Show me top gainers this week")
- [ ] Automated insight generation
- [ ] Anomaly detection
- [ ] Predictive alerting

---

## Quick Reference Cards

### Card 1: Project Statistics

```
Repository: de_Funk
Language:   Python 3.x
Size:       244 Python files, 136 Markdown files

Architecture:
  - 7 layers (Storage → Applications)
  - 8 domain models (core, equity, corporate, macro, city_finance, etf, forecast, company*)
  - 2 storage layers (Bronze, Silver)
  - 2 backend engines (Spark, DuckDB)

Data Sources:
  - Polygon.io (stock market)
  - Bureau of Labor Statistics (economics)
  - Chicago Data Portal (municipal)

Storage:
  - Bronze: 5 providers, ~20 tables
  - Silver: 8 models, ~30 tables
  - Format: Partitioned Parquet
  - Catalog: DuckDB analytics.db

Scripts: 27 operational scripts
Tests:   Unit + integration (pytest)
Docs:    136 markdown files
```

---

### Card 2: Key Commands

```bash
# Application
python run_app.py                    # Launch Streamlit UI (DuckDB)
./run_app.sh                         # Same, with shell script

# Data Pipeline
python run_full_pipeline.py --top-n 100   # Full ETL (100 tickers)
python -m scripts.build_all_models        # Build Silver layer

# Model Operations
python -m scripts.rebuild_model --model equity
python -m scripts.reset_model --model equity
python -m scripts.test_all_models

# Forecasting
python -m scripts.run_forecasts
python -m scripts.run_forecast_model --model arima

# Testing
pytest tests/unit/
pytest tests/integration/
bash scripts/run_backend_tests.sh
python -m scripts.test_pipeline_e2e

# Maintenance
python -m scripts.clear_and_refresh
python -m scripts.verify_ticker_count
```

---

### Card 3: File Locations

```
Core Framework:
  models/base/model.py              - BaseModel (1,237 lines)
  models/api/session.py             - UniversalSession (1,063 lines)
  models/registry.py                - ModelRegistry (416 lines)
  config/loader.py                  - ConfigLoader (150 lines)

Domain Models:
  configs/models/*.yaml             - Model definitions
  models/implemented/*/model.py     - Implementations

Data Pipeline:
  datapipelines/providers/          - API clients
  datapipelines/facets/             - Data transformations
  datapipelines/ingestors/          - Orchestration

Application:
  app/ui/notebook_app_duckdb.py     - Main Streamlit app
  app/notebook/parser.py            - Notebook parser
  app/notebook/manager.py           - Notebook lifecycle

Configuration:
  .env                              - Environment variables
  configs/storage.json              - Storage paths
  configs/*_endpoints.json          - API configurations
  configs/notebooks/                - Notebook definitions

Documentation:
  CLAUDE.md                         - AI assistant guide
  QUICKSTART.md                     - Getting started
  RUNNING.md                        - How to run
  TESTING_GUIDE.md                  - Testing guide
  docs/INFRASTRUCTURE_ANALYSIS.md   - This document
```

---

### Card 4: When to Use What

```
I want to...                        Use this...
─────────────────────────────────────────────────────────────
Query a single model               model.query_table('fact_prices')
Query across models                session.query_with_joins(...)
Calculate a measure                model.calculate_measure('avg_close')
Apply filters                      FilterEngine.apply(df, filters)
Build a model                      model.build() or rebuild_model.py
Create a notebook                  configs/notebooks/my_notebook.md
Add a data source                  Create new provider in datapipelines/
Define a new model                 Create YAML in configs/models/
Test backend compatibility         bash scripts/run_backend_tests.sh
Debug model dependencies           scripts/analyze_model_dependencies.py
Clear cache                        scripts/clear_and_refresh.py
Switch backends                    ConfigLoader.load(connection_type="duckdb|spark")
```

---

### Card 5: Design Principles

```
1. YAML is Source of Truth
   - Models defined in configs/models/*.yaml
   - Python implements framework, not business logic

2. Graph-Based Everything
   - Dependencies: NetworkX DAG
   - Joins: Graph edges
   - Build order: Topological sort

3. Backend Transparency
   - Single codebase
   - Works on Spark (distributed) or DuckDB (single-machine)
   - Adapter pattern abstracts differences

4. Lazy Evaluation
   - Models built on first access
   - Tables loaded on demand
   - Results cached

5. Configuration-Driven
   - No hardcoded paths
   - Environment variables override files
   - Type-safe dataclasses

6. Two-Layer Storage
   - Bronze: Raw from API
   - Silver: Dimensional models
   - No Gold: Analytics on Silver via DuckDB

7. Cross-Model Composability
   - Models reference each other
   - Measures span models
   - Unified query interface
```

---

## Conclusion: Your Next Steps

### If You're a **Business Analyst:**
1. Read `QUICKSTART.md`
2. Run `python run_app.py`
3. Explore example notebooks
4. Create your first custom notebook
5. Share insights!

### If You're a **Data Engineer:**
1. Read `PIPELINE_GUIDE.md`
2. Study `datapipelines/providers/polygon/`
3. Build a test model with your own data
4. Contribute a new provider
5. Share your learnings!

### If You're a **Framework Developer:**
1. Read `docs/INFRASTRUCTURE_ANALYSIS.md`
2. Study `models/base/model.py`
3. Fix a P0 technical debt item
4. Propose a framework enhancement
5. Open a PR!

---

## Additional Resources

**Detailed Documentation:**
- `COMPREHENSIVE_MODEL_ANALYSIS.md` - All 8 models deep-dive
- `INFRASTRUCTURE_ANALYSIS.md` - Framework architecture
- `UI_APP_ANALYSIS.md` - Application layer details
- `POLYGON_PIPELINE_ANALYSIS.md` - Data pipeline optimization
- `docs/ARCHITECTURE_LAYERS.md` - Visual layer diagrams

**Quick References:**
- `MODEL_QUICK_REFERENCE.md` - Model cheat sheet
- `INFRASTRUCTURE_QUICK_REFERENCE.md` - Framework cheat sheet
- `UI_APP_QUICK_REFERENCE.md` - Application cheat sheet

**Migration Guides:**
- `docs/EQUITY_CORPORATE_MIGRATION_GUIDE.md` - Company → Equity/Corporate
- `docs/configuration.md` - New ConfigLoader system
- `docs/IMPORT-PATTERNS.md` - Standardized imports

---

**Welcome to de_Funk. Let's build something great together.**

---

*Last Updated: 2025-11-16*
*Version: 1.0*
*Maintained by: de_Funk Core Team*
