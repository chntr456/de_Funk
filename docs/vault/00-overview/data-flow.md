# Data Flow

**How data moves through the de_Funk system**

---

## Overview

Data flows through three main stages:

```
External APIs → Bronze Layer → Silver Layer → Analytics
   (raw)         (normalized)   (dimensional)   (queries)
```

---

## Stage 1: API Ingestion

### Flow

```
API Endpoint → Provider → HTTP Client → Raw JSON → Facet → DataFrame → Parquet
```

### Components

| Component | Role | Example |
|-----------|------|---------|
| **Provider** | API client with auth, rate limiting | `AlphaVantageIngestor` |
| **HTTP Client** | Request execution, retries | `HttpClient` with key rotation |
| **Facet** | Response normalization | `SecuritiesPricesFacetAV` |

### Example: Alpha Vantage Stock Prices

```python
# 1. Provider generates API calls
facet = SecuritiesPricesFacetAV(spark, tickers=['AAPL', 'MSFT'])
calls = list(facet.calls())
# [{'endpoint': 'time_series_daily_adjusted', 'params': {'symbol': 'AAPL'}}, ...]

# 2. Ingestor fetches data
raw_batches = ingestor._fetch_calls(calls)
# [{'Time Series (Daily)': {'2024-01-15': {'1. open': '150.00', ...}}}]

# 3. Facet normalizes to DataFrame
df = facet.normalize(raw_batches)
# DataFrame with columns: ticker, trade_date, open, high, low, close, volume

# 4. Write to Bronze
sink.write(df, 'securities_prices_daily', partitions=['asset_type', 'year', 'month'])
```

---

## Stage 2: Bronze Layer

### Purpose
Store raw, normalized data from APIs without transformation.

### Characteristics
- **Format**: Partitioned Parquet files
- **Schema**: Facet-defined (provider-agnostic)
- **Partitioning**: By date, asset_type, or other logical keys
- **Updates**: Append or overwrite by partition

### Bronze Tables (v2.0)

| Table | Source | Partitions | Contents |
|-------|--------|------------|----------|
| `securities_reference` | Alpha Vantage | snapshot_dt, asset_type | Company fundamentals, CIK |
| `securities_prices_daily` | Alpha Vantage | asset_type, year, month | Daily OHLCV |
| `bls_unemployment` | BLS | year | Monthly unemployment rates |
| `bls_cpi` | BLS | year | Monthly CPI values |
| `chicago_unemployment` | Chicago | date | Local unemployment by area |
| `chicago_building_permits` | Chicago | issue_date | Building permit records |

### Storage Path Pattern

```
storage/bronze/{table_name}/
└── {partition_key}={partition_value}/
    └── part-00000.parquet
```

---

## Stage 3: Silver Layer (Model Building)

### Flow

```
Bronze Parquet → YAML Config → BaseModel.build() → Dimensions + Facts → Silver Parquet
```

### Process

1. **Load YAML Configuration**
   ```python
   loader = ModelConfigLoader(Path("configs/models"))
   config = loader.load_model_config("stocks")
   ```

2. **Build Nodes from Bronze**
   ```yaml
   graph:
     nodes:
       - id: dim_stock
         from: bronze.securities_reference
         filters: ["asset_type = 'stocks'"]
         select:
           ticker: ticker
           company_id: "CONCAT('COMPANY_', cik)"
   ```

3. **Validate Edges**
   ```yaml
   edges:
     - from: fact_stock_prices
       to: dim_stock
       on: [ticker = ticker]
   ```

4. **Write to Silver**
   ```python
   dims, facts = model.build()
   model.write_tables(dims, facts)
   ```

### Silver Table Types

| Type | Purpose | Example |
|------|---------|---------|
| **Dimension** | Reference/lookup data | `dim_stock`, `dim_calendar` |
| **Fact** | Measurable events | `fact_stock_prices`, `fact_forecasts` |

### Storage Path Pattern

```
storage/silver/{model_name}/
└── {table_name}/
    └── part-00000.parquet
```

---

## Stage 4: Analytics (Query Layer)

### Flow

```
User Request → UniversalSession → Model Resolution → Query Execution → Result
```

### Query Methods

1. **Direct Table Access**
   ```python
   session = UniversalSession(backend="duckdb")
   df = session.get_table("stocks", "dim_stock")
   ```

2. **SQL Queries**
   ```python
   df = session.query("""
       SELECT ticker, close_price
       FROM stocks.fact_stock_prices
       WHERE trade_date >= '2024-01-01'
   """)
   ```

3. **Cross-Model Joins**
   ```python
   df = session.query("""
       SELECT s.ticker, s.close_price, c.company_name
       FROM stocks.fact_stock_prices s
       JOIN company.dim_company c ON s.company_id = c.company_id
   """)
   ```

4. **Measure Calculations**
   ```python
   result = model.calculate_measure(
       "avg_close_price",
       filters=[{"column": "ticker", "value": "AAPL"}]
   )
   ```

### DuckDB Analytics

- **No Gold Layer**: Queries run directly on Silver Parquet files
- **Catalog**: `storage/duckdb/analytics.db` stores metadata only
- **In-Process**: Runs within the application process

---

## Complete Data Flow Example

### Scenario: Get AAPL Stock with Company Info

```
1. INGESTION (one-time or scheduled)
   ┌──────────────────────────────────────────────────────────────┐
   │ Alpha Vantage API                                            │
   │ GET /query?function=OVERVIEW&symbol=AAPL                     │
   │ GET /query?function=TIME_SERIES_DAILY_ADJUSTED&symbol=AAPL   │
   └─────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ FACETS (SecuritiesReferenceFacetAV, SecuritiesPricesFacetAV) │
   │ - Normalize JSON to DataFrame                                │
   │ - Extract CIK, clean data                                    │
   └─────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ BRONZE LAYER                                                 │
   │ storage/bronze/securities_reference/snapshot_dt=.../         │
   │ storage/bronze/securities_prices_daily/asset_type=stocks/... │
   └──────────────────────────────────────────────────────────────┘

2. MODEL BUILDING (on demand or scheduled)
   ┌──────────────────────────────────────────────────────────────┐
   │ YAML CONFIGS (configs/models/stocks/)                        │
   │ - model.yaml: dependencies, composition                      │
   │ - schema.yaml: dim_stock, fact_stock_prices                  │
   │ - graph.yaml: nodes, edges                                   │
   └─────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ BaseModel.build()                                            │
   │ - Load bronze tables                                         │
   │ - Apply filters (asset_type = 'stocks')                      │
   │ - Build dimension (dim_stock with company_id)                │
   │ - Build fact (fact_stock_prices)                             │
   └─────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ SILVER LAYER                                                 │
   │ storage/silver/stocks/dim_stock/                             │
   │ storage/silver/stocks/fact_stock_prices/                     │
   │ storage/silver/company/dim_company/ (separate model)         │
   └──────────────────────────────────────────────────────────────┘

3. QUERY (user request)
   ┌──────────────────────────────────────────────────────────────┐
   │ USER QUERY                                                   │
   │ SELECT s.ticker, s.close, c.company_name                     │
   │ FROM stocks.dim_stock s                                      │
   │ JOIN company.dim_company c ON s.company_id = c.company_id    │
   │ WHERE s.ticker = 'AAPL'                                      │
   └─────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ UniversalSession                                             │
   │ - Resolve models (stocks, company)                           │
   │ - Execute cross-model join                                   │
   │ - Return result                                              │
   └─────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ RESULT                                                       │
   │ ticker | close  | company_name                               │
   │ AAPL   | 182.50 | Apple Inc.                                 │
   └──────────────────────────────────────────────────────────────┘
```

---

## Data Freshness

| Layer | Update Frequency | Trigger |
|-------|------------------|---------|
| **Bronze** | Daily or on-demand | `run_full_pipeline.py` |
| **Silver** | On Bronze update | `build_silver_layer.py` |
| **Analytics** | Real-time | Direct Parquet queries |

---

## Related Documentation

- [Architecture](architecture.md) - System architecture
- [Pipelines](../06-pipelines/README.md) - ETL operations
- [Implemented Models](../04-implemented-models/README.md) - Available data
