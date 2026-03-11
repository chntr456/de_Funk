# Unified Domain Model Specification v4.0

**Version**: 4.0
**Status**: Proposal
**Date**: January 2026
**Example Domain**: Securities/Stocks (mapped from existing implementation)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Document Types](#2-document-types)
3. [Data Sources (Bronze Layer)](#3-data-sources-bronze-layer)
4. [Storage (Silver Layer)](#4-storage-silver-layer)
5. [Field System and Aliasing](#5-field-system-and-aliasing)
6. [Base Templates Reference](#6-base-templates-reference)
7. [Domain Model Implementation](#7-domain-model-implementation)
8. [Auto-Federation and Cross-Model Queries](#8-auto-federation-and-cross-model-queries)
9. [Build System](#9-build-system)
10. [Complete Securities Example](#10-complete-securities-example)
11. [Appendix: YAML Reference](#appendix-yaml-reference)

---

## 1. Overview

### 1.1 Purpose

This specification defines how domain models are structured, inherited, and federated in de_Funk. All examples are drawn from the **existing securities/stocks implementation** to demonstrate real-world patterns.

### 1.2 Core Concepts

| Concept | Description | Example |
|---------|-------------|---------|
| **domain-base** | Reusable template - defines schema, never materializes | `_base/finance/securities.md` |
| **domain-model** | Concrete implementation - creates tables in storage | `securities/stocks.md` |
| **domain-view** | Query layer - cross-model aggregation without new storage | (federation queries) |
| **Bronze** | Raw data from source systems (Alpha Vantage, Chicago) | `storage/bronze/alpha_vantage/` |
| **Silver** | Transformed dimensional models | `storage/silver/stocks/` |

### 1.3 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        DOMAIN LAYER                             │
│                                                                 │
│  ┌─────────────────┐        ┌──────────────────────────────┐   │
│  │  domain-base    │        │       domain-model           │   │
│  │  _base/finance/ │◄───────│  securities/stocks.md        │   │
│  │  securities.md  │extends │  securities/securities.md    │   │
│  └─────────────────┘        │  corporate/company.md        │   │
│                             └──────────────────────────────┘   │
│                                          │                      │
│                                          ▼                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                     GRAPH LAYER                            │ │
│  │   edges: stock_to_company (stocks → company)               │ │
│  │   paths: prices_to_sector (prices → stock → company)       │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                               │
│                                                                 │
│  ┌─────────────────┐        ┌──────────────────────────────┐   │
│  │  BRONZE (Raw)   │        │      SILVER (Models)         │   │
│  │  alpha_vantage/ │───────▶│  stocks/dim_stock            │   │
│  │   listing_status│  ETL   │  stocks/fact_stock_prices    │   │
│  │   time_series   │        │  company/dim_company         │   │
│  │   company_overview       │  company/fact_income_stmt    │   │
│  └─────────────────┘        └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 Existing Model Hierarchy

Based on the actual implementation in `domains/`:

```
Foundation (no dependencies)
├── temporal                    # Calendar dimension (2000-2050)
└── geospatial                 # US geographic hierarchy

Tier 1 (depend only on temporal)
├── securities                 # Master security dimension + unified prices
├── company                    # Corporate entities + financials
└── chicago_finance            # Municipal finance

Tier 2 (depend on temporal + tier 1)
├── stocks                     # (depends: temporal, securities, company)
├── chicago_public_safety      # (depends: temporal, geospatial, chicago_geospatial)
└── [etfs, options, futures]   # (depend: temporal, securities)
```

---

## 2. Document Types

### 2.1 domain-base (Template)

**Purpose**: Define reusable schemas that multiple models can inherit. Never creates storage.

**Location**: `domains/_base/{category}/{template}.md`

**Characteristics**:
- `type: domain-base` in YAML front matter
- Contains template tables (prefixed with `_`)
- Defines aliasable fields with default mappings
- Specifies federation configuration
- NO `storage:` section (no materialization)

**Existing Examples**:
- `_base/finance/securities.md` - Template for all tradable instruments
- `_base/temporal/calendar.md` - Calendar dimension template
- `_base/geospatial/geospatial.md` - Geographic hierarchy template
- `_base/public_safety/crime.md` - Crime/incident data template

**Real Example**: `_base/finance/securities.md`

```yaml
---
type: domain-base
model: securities
version: 2.0
description: "Template for all tradable securities"

# Template tables (underscore prefix = template, not materialized)
tables:
  _dim_security:
    type: dimension
    description: "Base security dimension template"
    primary_key: [security_id]
    unique_key: [ticker]

    schema:
      - [security_id, integer, false, "Surrogate PK", {derived: "ABS(HASH(ticker))"}]
      - [ticker, string, false, "Trading symbol (natural key)"]
      - [security_name, string, true, "Full security name"]
      - [asset_type, string, false, "Asset class", {enum: [stocks, etf, option, future]}]
      - [exchange_code, string, true, "Exchange listing"]
      - [currency, string, true, "Trading currency", {default: "USD"}]
      - [is_active, boolean, true, "Currently trading", {default: true}]

    # Aliasable fields - child models can map source fields to these
    aliasable_fields:
      ticker:
        default_aliases: [symbol, tic, trading_symbol]
        description: "Trading symbol identifier"
      security_name:
        default_aliases: [name, company_name, security_description]
        description: "Full name of the security"
      exchange_code:
        default_aliases: [exchange, listing_exchange, primary_exchange]
        description: "Exchange where security trades"

  _fact_prices_base:
    type: fact
    description: "Base OHLCV price template"
    primary_key: [price_id]
    partition_by: [date_id]

    schema:
      - [price_id, integer, false, "Surrogate PK", {derived: "ABS(HASH(CONCAT(ticker, '_', trade_date)))"}]
      - [security_id, integer, false, "FK to dimension", {fk: _dim_security.security_id}]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [ticker, string, false, "Trading symbol (kept for queries)"]
      - [trade_date, date, false, "Trading date (kept for queries)"]
      - [open, decimal(18,4), true, "Opening price"]
      - [high, decimal(18,4), true, "High price"]
      - [low, decimal(18,4), true, "Low price"]
      - [close, decimal(18,4), true, "Closing price"]
      - [volume, long, true, "Trading volume"]
      - [adjusted_close, decimal(18,4), true, "Split-adjusted close"]

    aliasable_fields:
      open: {default_aliases: [open_price, opening_price]}
      high: {default_aliases: [high_price, daily_high]}
      low: {default_aliases: [low_price, daily_low]}
      close: {default_aliases: [close_price, closing_price, adj_close]}
      volume: {default_aliases: [vol, trading_volume, daily_volume]}

# Federation configuration
federation:
  enabled: true
  union_key: asset_type
  primary_key: security_id
  children:
    - stocks
    - options
    - etfs
    - futures
---

## Base Securities Template

This template provides the foundation for all tradable securities. Child models
inherit the schema and can extend it with asset-specific fields.

### Usage

```yaml
extends: _base.finance.securities
```

### Inheritance

Child models get:
- All columns from `_dim_security` and `_fact_prices_base`
- Field aliasing capabilities
- Auto-federation membership
```

### 2.2 domain-model (Concrete)

**Purpose**: Implement a base template for a specific data source. Creates actual tables in storage.

**Location**: `domains/{category}/{model}.md`

**Characteristics**:
- `type: domain-model` in YAML front matter
- `extends:` references parent template
- `storage:` section defines bronze sources and silver output
- `aliases:` maps source fields to canonical names
- `build:` section controls materialization

**Existing Examples**:
- `securities/stocks.md` - Stock equities (v3.1)
- `securities/securities.md` - Master security domain
- `corporate/company.md` - Corporate entities (v3.0)
- `temporal/temporal.md` - Calendar dimension
- `municipal/chicago/finance.md` - Municipal finance
- `municipal/chicago/public_safety.md` - Crime data (extends `_base.crime`)

**Real Example**: `securities/stocks.md`

```yaml
---
type: domain-model
model: stocks
version: 3.1
description: "Stock equities with company linkage and technical indicators"
tags: [securities, stocks, equities]

# Inheritance
extends: _base.finance.securities

# Dependencies (build order)
depends_on: [temporal, securities, company]

# Storage configuration
storage:
  format: delta
  auto_vacuum: true

  bronze:
    provider: alpha_vantage
    tables:
      listing_status: alpha_vantage/listing_status
      time_series: alpha_vantage/time_series_daily_adjusted
      dividends: alpha_vantage/dividends
      splits: alpha_vantage/splits

  silver:
    root: storage/silver/stocks/

# Build configuration
build:
  partitions: [date_id]
  sort_by: [security_id, date_id]
  optimize: true

# Tables (extends base + adds stock-specific)
tables:
  dim_stock:
    extends: _base.finance.securities._dim_security
    type: dimension
    description: "Stock equities dimension"
    primary_key: [stock_id]
    unique_key: [ticker]

    schema:
      # Inherited from base: security_id, ticker, security_name, asset_type, exchange_code, currency, is_active
      - [stock_id, integer, false, "Stock-specific PK", {derived: "ABS(HASH(CONCAT('STOCK_', ticker)))"}]
      - [security_id, integer, false, "FK to securities", {fk: securities.dim_security.security_id}]
      - [company_id, integer, true, "FK to company", {fk: company.dim_company.company_id, optional: true}]
      - [stock_type, string, true, "Common, Preferred, etc.", {enum: [common, preferred, adr]}]

    # Aliases: map source field names to canonical schema
    aliases:
      name: security_name
      symbol: ticker
      exchange: exchange_code
      assetType: asset_type
      status: is_active

  fact_stock_prices:
    extends: _base.finance.securities._fact_prices_base
    type: fact
    description: "Stock daily prices (filtered from securities)"
    primary_key: [price_id]
    partition_by: [date_id]

    source:
      from: securities.fact_security_prices
      filter: "asset_type = 'stocks'"

    # Aliases from Alpha Vantage API response
    aliases:
      "1. open": open
      "2. high": high
      "3. low": low
      "4. close": close
      "5. adjusted close": adjusted_close
      "6. volume": volume
      "7. dividend amount": dividend_amount
      "8. split coefficient": split_coefficient

  fact_stock_technicals:
    type: fact
    description: "Technical indicators (computed post-build)"
    primary_key: [technical_id]
    partition_by: [date_id]

    schema:
      - [technical_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', trade_date)))"}]
      - [security_id, integer, false, "FK", {fk: securities.dim_security.security_id}]
      - [date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [sma_20, decimal(18,4), true, "20-day SMA"]
      - [sma_50, decimal(18,4), true, "50-day SMA"]
      - [sma_200, decimal(18,4), true, "200-day SMA"]
      - [rsi_14, decimal(8,4), true, "14-day RSI"]
      - [bollinger_upper, decimal(18,4), true, "Upper Bollinger Band"]
      - [bollinger_middle, decimal(18,4), true, "Middle Bollinger Band"]
      - [bollinger_lower, decimal(18,4), true, "Lower Bollinger Band"]
      - [daily_return, decimal(12,6), true, "Daily return percentage"]
      - [volatility_20d, decimal(12,6), true, "20-day rolling volatility"]
      - [volatility_60d, decimal(12,6), true, "60-day rolling volatility"]
      - [volume_sma_20, decimal(18,2), true, "20-day volume SMA"]
      - [volume_ratio, decimal(8,4), true, "Volume vs 20-day avg"]

  fact_dividends:
    type: fact
    description: "Dividend payments"
    primary_key: [dividend_id]
    partition_by: [ex_dividend_date_id]

    schema:
      - [dividend_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', ex_dividend_date)))"}]
      - [security_id, integer, false, "FK", {fk: securities.dim_security.security_id}]
      - [ex_dividend_date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [payment_date_id, integer, true, "FK", {fk: temporal.dim_calendar.date_id}]
      - [dividend_amount, decimal(12,6), false, "Amount per share"]
      - [dividend_type, string, true, "Cash, Stock, etc."]

  fact_splits:
    type: fact
    description: "Stock splits"
    primary_key: [split_id]

    schema:
      - [split_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', effective_date)))"}]
      - [security_id, integer, false, "FK", {fk: securities.dim_security.security_id}]
      - [effective_date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [split_factor, decimal(10,4), false, "Split ratio (4.0 = 4:1)"]

# Graph definition
graph:
  nodes:
    dim_stock:
      from: bronze.alpha_vantage.listing_status
      type: dimension
      filter: "asset_type = 'stocks'"
      filter_by_dimension: securities.dim_security

      select:
        stock_id: "ABS(HASH(CONCAT('STOCK_', symbol)))"
        security_id: "ABS(HASH(symbol))"
        company_id: "ABS(HASH(CONCAT('COMPANY_', symbol)))"
        ticker: symbol
        security_name: name
        asset_type: assetType
        exchange_code: exchange
        stock_type: "'common'"
        is_active: "status = 'Active'"

      derive:
        currency: "'USD'"

    fact_stock_prices:
      from: securities.fact_security_prices
      type: fact
      filter: "asset_type = 'stocks'"

  edges:
    stock_to_security:
      from: dim_stock
      to: securities.dim_security
      on: [security_id=security_id]
      type: many_to_one
      cross_model: securities

    stock_to_company:
      from: dim_stock
      to: company.dim_company
      on: [company_id=company_id]
      type: many_to_one
      cross_model: company
      optional: true

    prices_to_stock:
      from: fact_stock_prices
      to: dim_stock
      on: [security_id=security_id]
      type: many_to_one

    prices_to_calendar:
      from: fact_stock_prices
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal

    technicals_to_stock:
      from: fact_stock_technicals
      to: dim_stock
      on: [security_id=security_id]
      type: many_to_one

    dividends_to_stock:
      from: fact_dividends
      to: dim_stock
      on: [security_id=security_id]
      type: many_to_one

  paths:
    prices_to_company:
      description: "Navigate from stock prices to company fundamentals"
      steps:
        - {from: fact_stock_prices, to: dim_stock, via: security_id}
        - {from: dim_stock, to: company.dim_company, via: company_id}

    prices_to_sector:
      description: "Get sector for price analysis"
      steps:
        - {from: fact_stock_prices, to: dim_stock, via: security_id}
        - {from: dim_stock, to: company.dim_company, via: company_id}
      # sector and industry are columns in company.dim_company

# Measures
measures:
  simple:
    - [avg_close, avg, close, "Average closing price", {format: "$#,##0.00"}]
    - [total_volume, sum, volume, "Total trading volume", {format: "#,##0"}]
    - [price_count, count, price_id, "Number of price records"]
    - [max_high, max, high, "Maximum high price", {format: "$#,##0.00"}]
    - [min_low, min, low, "Minimum low price", {format: "$#,##0.00"}]

  computed:
    - [price_range, expression, "AVG(high - low)", "Average daily range", {format: "$#,##0.00"}]
    - [avg_return, expression, "AVG(daily_return) * 100", "Average daily return %", {format: "#,##0.00%"}]
    - [total_dividend, expression, "SUM(dividend_amount)", "Total dividends paid", {format: "$#,##0.00"}]

  python:
    sharpe_ratio:
      function: "stocks.measures.calculate_sharpe_ratio"
      params:
        risk_free_rate: 0.045
        window_days: 252

    beta:
      function: "stocks.measures.calculate_beta"
      params:
        benchmark: "SPY"
        window_days: 252

# Metadata
metadata:
  domain: securities
  owner: data_team
  sla_hours: 4

status: active
---

## Stocks Model

Stock equities with company linkage, technical indicators, dividends, and splits.

### Dependencies

- **temporal**: Calendar dimension for date_id joins
- **securities**: Master security dimension and unified prices
- **company**: Company fundamentals for sector/industry analysis

### Key Design Decisions

1. **stock_id vs security_id**: Stocks have their own PK prefixed with 'STOCK_'
   to distinguish from the master security_id

2. **Prices sourced from securities**: Stock prices are filtered from
   `securities.fact_security_prices` rather than ingested separately

3. **Technicals computed post-build**: Technical indicators are calculated
   by `scripts/build/compute_technicals.py` after price data is loaded

4. **Optional company link**: company_id is nullable because some tickers
   may not have company data available

### Field Aliasing

Alpha Vantage returns fields with numeric prefixes:
- `"1. open"` → `open`
- `"2. high"` → `high`
- etc.

The `aliases:` section handles this mapping during ingestion.
```

### 2.3 domain-views (Cross-Model)

**Purpose**: Define query patterns across multiple models without creating new storage.

**Characteristics**:
- References multiple domain-models
- Defines join paths and aggregation patterns
- Does NOT create new tables
- Used for federation and cross-model analysis

Federation views are generated from `federation:` configuration in base templates.

---

## 3. Data Sources (Bronze Layer)

### 3.1 Overview

The Bronze layer stores raw data from source systems without transformation. Each provider has its own directory with endpoint-organized tables.

### 3.2 Directory Structure (Actual)

```
storage/bronze/
├── alpha_vantage/
│   ├── listing_status/           # All US tickers (12,499)
│   ├── time_series_daily_adjusted/  # OHLCV prices
│   ├── company_overview/         # Company fundamentals
│   ├── income_statement/         # Financial statements
│   ├── balance_sheet/
│   ├── cash_flow/
│   ├── earnings/
│   ├── dividends/
│   └── splits/
├── chicago/
│   ├── chicago_crimes/
│   ├── chicago_arrests/
│   ├── chicago_payments/
│   ├── chicago_contracts/
│   └── chicago_iucr_codes/
└── bls/
    ├── unemployment/
    └── cpi/
```

### 3.3 Bronze Configuration in Domain Models

```yaml
storage:
  bronze:
    provider: alpha_vantage
    tables:
      # Mapping: local_name → provider/endpoint
      listing_status: alpha_vantage/listing_status
      time_series: alpha_vantage/time_series_daily_adjusted
      company_overview: alpha_vantage/company_overview
```

### 3.4 Provider Mapping

| Provider | Endpoint | Domain Models Using |
|----------|----------|---------------------|
| alpha_vantage | listing_status | securities, stocks |
| alpha_vantage | time_series_daily_adjusted | securities, stocks |
| alpha_vantage | company_overview | company |
| alpha_vantage | income_statement | company |
| alpha_vantage | balance_sheet | company |
| alpha_vantage | cash_flow | company |
| alpha_vantage | earnings | company |
| alpha_vantage | dividends | stocks |
| alpha_vantage | splits | stocks |
| chicago | chicago_crimes | chicago_public_safety |
| chicago | chicago_arrests | chicago_public_safety |
| chicago | chicago_payments | chicago_finance |
| chicago | chicago_contracts | chicago_finance |

### 3.5 Provider Documentation

Provider details are documented in `data_sources/providers/`:

```yaml
# data_sources/providers/alpha_vantage.md (front matter)
---
provider: alpha_vantage
description: "Financial data API"
base_url: "https://www.alphavantage.co/query"
rate_limit:
  free: 5 per minute
  premium: 75 per minute
authentication: api_key
env_var: ALPHA_VANTAGE_API_KEYS

endpoints:
  listing_status:
    function: LISTING_STATUS
    returns: CSV
    fields: [symbol, name, exchange, assetType, ipoDate, delistingDate, status]

  time_series_daily_adjusted:
    function: TIME_SERIES_DAILY_ADJUSTED
    params: [symbol, outputsize]
    returns: JSON
    fields: ["1. open", "2. high", "3. low", "4. close", "5. adjusted close", "6. volume"]
---
```

---

## 4. Storage (Silver Layer)

### 4.1 Overview

The Silver layer contains transformed dimensional models ready for analytics. Each model has its own directory with Delta Lake tables.

### 4.2 Directory Structure (Actual)

```
storage/silver/
├── temporal/
│   └── dim_calendar/             # 18,628 rows (2000-2050)
├── securities/
│   ├── dim_security/             # All tickers (master)
│   └── fact_security_prices/     # Unified OHLCV (all asset types)
├── stocks/
│   ├── dim_stock/                # Stock equities only
│   ├── fact_stock_prices/        # Filtered prices (asset_type='stocks')
│   ├── fact_stock_technicals/    # Technical indicators
│   ├── fact_dividends/
│   └── fact_splits/
├── company/
│   ├── dim_company/              # Corporate entities
│   ├── fact_income_statement/
│   ├── fact_balance_sheet/
│   ├── fact_cash_flow/
│   └── fact_earnings/
├── geospatial/
│   ├── dim_state/
│   ├── dim_county/
│   └── dim_city/
└── chicago/
    ├── finance/
    │   ├── dim_vendor/
    │   ├── dim_department/
    │   └── fact_payments/
    └── public_safety/
        ├── dim_crime_type/
        ├── dim_location_type/
        └── fact_crimes/
```

### 4.3 Storage Configuration

```yaml
storage:
  format: delta              # Always Delta Lake
  auto_vacuum: true          # Remove old versions (save space)

  silver:
    root: storage/silver/stocks/  # Output directory
```

### 4.4 Delta Lake Features

| Feature | Purpose | Configuration |
|---------|---------|---------------|
| ACID Transactions | Data reliability | Default |
| Schema Evolution | Handle new columns | `mergeSchema: true` |
| Time Travel | Debug/audit | Disabled with `auto_vacuum: true` |
| Partitioning | Query efficiency | `partition_by: [date_id]` |
| Z-Ordering | Clustered access | `sort_by: [security_id, date_id]` |

---

## 5. Field System and Aliasing

### 5.1 The Aliasing Problem

Different data sources use different names for the same concept:

| Concept | Alpha Vantage | Yahoo | Polygon | SEC |
|---------|---------------|-------|---------|-----|
| Opening price | `1. open` | `Open` | `o` | `open_price` |
| Closing price | `4. close` | `Close` | `c` | `close_price` |
| Stock symbol | `symbol` | `Symbol` | `T` | `ticker` |

### 5.2 Two-Level Field System

The field system separates **what** canonical fields exist from **how** each source maps to them:

**Level 1: domain-base (Canonical Definition)**

Defines the official field names that ALL child models will output. Does NOT know about source-specific names - never needs updating when new sources are added.

```yaml
# In _base/finance/securities.md
type: domain-base

canonical_fields:
  # These are the official field names - all children output these
  ticker:
    type: string
    nullable: false
    description: "Trading symbol identifier"

  open:
    type: decimal(18,4)
    nullable: true
    description: "Opening price for the trading period"

  high:
    type: decimal(18,4)
    nullable: true
    description: "Highest price during the trading period"

  low:
    type: decimal(18,4)
    nullable: true
    description: "Lowest price during the trading period"

  close:
    type: decimal(18,4)
    nullable: true
    description: "Closing price for the trading period"

  volume:
    type: long
    nullable: true
    description: "Number of shares/contracts traded"
```

**Level 2: domain-model (Source Mapping)**

Each model defines how ITS specific source fields map to the canonical names. Self-contained - adding a new source is just a new model file.

```yaml
# securities/stocks_alpha_vantage.md
type: domain-model
extends: _base.finance.securities

# This model's source → canonical mappings
aliases:
  "1. open": open
  "2. high": high
  "3. low": low
  "4. close": close
  "6. volume": volume
  "symbol": ticker
```

```yaml
# securities/stocks_yahoo.md (hypothetical second source)
type: domain-model
extends: _base.finance.securities

# Different source, same canonical output
aliases:
  "Open": open
  "High": high
  "Low": low
  "Close": close
  "Volume": volume
  "Symbol": ticker
```

```yaml
# securities/stocks_polygon.md (hypothetical third source)
type: domain-model
extends: _base.finance.securities

# Yet another source format
aliases:
  "o": open
  "h": high
  "l": low
  "c": close
  "v": volume
  "T": ticker
```

### 5.3 Why This Separation Matters

**Key Benefit**: The domain-base NEVER needs to change when adding new data sources.

| Action | domain-base | domain-model |
|--------|-------------|--------------|
| Add new data source | No change | Create new model with aliases |
| Add new canonical field | Update base | Update models that have it |
| Query across sources | Uses canonical names | All output same schema |

**Cross-Source Queries Work**:

```sql
-- All three sources output 'open', 'close', 'ticker' columns
-- Federation query works because they share canonical schema
SELECT ticker, open, close, volume
FROM securities.v_all_prices  -- Union of all sources
WHERE date_id = 20250101
```

### 5.4 Semantic Field Mapping (The Real Value)

The aliasing system is most valuable for **semantic concepts** that exist across domains with different terminology - not just simple field name variations.

**Example: Organizational Unit**

The concept of "the department responsible for security" exists in multiple domains:

| Canonical | Corporate | Municipal | Healthcare |
|-----------|-----------|-----------|------------|
| `security_unit` | Security Department | Police Department | Security Services |

**Example: Expense Categorization (Chart of Accounts)**

The concept of "how expenses are categorized" varies by domain:

| Canonical | Corporate | Municipal | Federal |
|-----------|-----------|-----------|---------|
| `expense_category` | Cost Center | Fund/Appropriation | Budget Object Class |
| `organizational_unit` | Department | Department | Agency |
| `revenue_source` | Revenue Stream | Tax Type | Receipt Account |

**Base Template (Ledger/Accounting)**:

```yaml
# _base/finance/ledger.md
type: domain-base

canonical_fields:
  # These are semantic CONCEPTS, not just field names
  organizational_unit:
    type: string
    description: "The organizational entity responsible for the transaction"
    # Corporate calls it "department", Municipal calls it "department" too,
    # but the SECURITY organizational unit means different things

  expense_category:
    type: string
    description: "Classification of how the expense is categorized"
    # Corporate: Cost Center, Municipal: Fund, Federal: Budget Object Class

  transaction_amount:
    type: decimal(18,2)
    description: "The monetary value of the transaction"
```

**Corporate Implementation**:

```yaml
# corporate/general_ledger.md
extends: _base.finance.ledger

aliases:
  # Map corporate terminology → canonical concepts
  "cost_center": expense_category
  "department": organizational_unit
  "amount": transaction_amount
```

**Municipal Implementation**:

```yaml
# municipal/chicago/finance.md
extends: _base.finance.ledger

aliases:
  # Map municipal terminology → canonical concepts
  "fund": expense_category
  "department": organizational_unit      # Same field name, different meaning!
  "amount": transaction_amount
```

**The Power**: Query across both with canonical concepts:

```sql
-- Works across corporate AND municipal data
-- Because both map their terminology to canonical fields
SELECT
    organizational_unit,
    expense_category,
    SUM(transaction_amount) as total
FROM finance.v_all_ledger_entries
GROUP BY organizational_unit, expense_category
```

**Key Insight**: "department" appears in both sources, but:
- Corporate Security Department ≠ Municipal Police Department
- The canonical `organizational_unit` represents the CONCEPT
- Each model maps its source fields to canonical MEANING

### 5.5 Alias Resolution During Build

When building a model, aliases resolve source fields to canonical names:

```
Source (Alpha Vantage):
  {"symbol": "AAPL", "1. open": 185.50, "4. close": 187.25}

Alias Mapping:
  "symbol" → ticker
  "1. open" → open
  "4. close" → close

Output (Canonical):
  {"ticker": "AAPL", "open": 185.50, "close": 187.25}
```

Resolution order:
1. If source field matches canonical name exactly → use directly
2. If source field is in `aliases:` → use mapped canonical name
3. Unknown field → log warning, exclude from output

### 5.6 Multi-Source Union Pattern

When multiple endpoints from the same provider contribute to a single canonical model, use the `sources:` pattern. Each source has its own aliases and derivations, and the build process unions them into a single table.

**Problem**: Chicago has multiple endpoints that all represent financial transactions:
- `chicago_payments` - Vendor payments
- `chicago_salaries` - Employee payroll
- `chicago_contracts` - Contract payments

Each has different field names but they all map to the same journal entry concept.

**Solution**: Define multiple sources within one domain-model:

```yaml
# municipal/chicago/finance.md
type: domain-model
extends: _base.finance.ledger

# Multiple endpoints → single canonical model
# Each source defines its own interpretation
sources:
  vendor_payments:
    from: bronze.chicago.chicago_payments
    entry_type: VENDOR_PAYMENT

    # This source's field mappings
    aliases:
      vendor_name: payee
      amount: transaction_amount
      check_date: transaction_date
      department_name: organizational_unit
      fund: expense_category

    # This source's derived fields
    derive:
      credit_account: "'Accounts Payable'"
      debit_account: "CONCAT('Expense:', fund)"
      entry_description: "CONCAT('Vendor payment to ', vendor_name)"

  employee_salaries:
    from: bronze.chicago.chicago_salaries
    entry_type: PAYROLL

    aliases:
      employee_name: payee
      salary_amount: transaction_amount
      pay_date: transaction_date
      department: organizational_unit
      position_type: expense_category

    derive:
      credit_account: "'Cash'"
      debit_account: "'Salaries Expense'"
      entry_description: "CONCAT('Salary: ', position_title)"

  contract_disbursements:
    from: bronze.chicago.chicago_contracts
    entry_type: CONTRACT

    aliases:
      contractor: payee
      contract_amount: transaction_amount
      payment_date: transaction_date
      awarding_department: organizational_unit
      contract_type: expense_category

    derive:
      credit_account: "'Accounts Payable'"
      debit_account: "'Contract Services'"
      entry_description: "CONCAT('Contract: ', contract_description)"

# Output table is UNION of all sources
tables:
  fact_journal_entries:
    type: fact
    source: union(vendor_payments, employee_salaries, contract_disbursements)
    partition_by: [date_id]

    schema:
      # All fields are canonical - same regardless of source
      - [entry_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(entry_type, '_', source_id)))"}]
      - [entry_type, string, false, "Source type discriminator"]
      - [date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [payee, string, false, "Who received payment"]
      - [transaction_amount, decimal(18,2), false, "Amount"]
      - [organizational_unit, string, true, "Department responsible"]
      - [expense_category, string, true, "How expense is classified"]
      - [debit_account, string, false, "Debit side of entry"]
      - [credit_account, string, false, "Credit side of entry"]
      - [entry_description, string, true, "Human-readable description"]
```

**Build Process**:

```
Phase 1: Process each source independently
  vendor_payments:    chicago_payments    → aliases → derive → canonical schema
  employee_salaries:  chicago_salaries    → aliases → derive → canonical schema
  contract_disbursements: chicago_contracts → aliases → derive → canonical schema

Phase 2: Union all sources
  fact_journal_entries = UNION(vendor_payments, employee_salaries, contract_disbursements)

Phase 3: Write to Silver
  storage/silver/chicago/finance/fact_journal_entries/
```

**Query Result**: Unified journal entries with `entry_type` discriminator:

```sql
SELECT
    entry_type,
    organizational_unit,
    expense_category,
    SUM(transaction_amount) as total
FROM chicago_finance.fact_journal_entries
WHERE date_id BETWEEN 20240101 AND 20241231
GROUP BY entry_type, organizational_unit, expense_category
ORDER BY total DESC
```

| entry_type | organizational_unit | expense_category | total |
|------------|---------------------|------------------|-------|
| PAYROLL | Police | Salaries | 1,234,567.00 |
| VENDOR_PAYMENT | Streets & San | Maintenance | 987,654.00 |
| CONTRACT | Aviation | Construction | 876,543.00 |

**Key Benefits**:

1. **Single table output** - All sources unioned into one queryable table
2. **Source traceability** - `entry_type` tells you which source each row came from
3. **Independent mappings** - Each source has its own aliases/derivations
4. **Canonical schema** - Output columns are consistent regardless of source
5. **Extensible** - Add new sources without changing existing ones

### 5.7 Field Derivation

Beyond aliasing, fields can be derived using SQL expressions:

```yaml
schema:
  - [security_id, integer, false, "PK", {derived: "ABS(HASH(ticker))"}]
  - [date_id, integer, false, "FK", {derived: "CAST(DATE_FORMAT(trade_date, 'yyyyMMdd') AS INT)"}]
  - [company_id, integer, true, "FK", {derived: "ABS(HASH(CONCAT('COMPANY_', ticker)))"}]
```

### 5.8 Integer Surrogate Key Pattern (Universal)

All primary keys in the system are integers using deterministic hash functions:

```yaml
# Pattern: ABS(HASH(...)) for consistent integer PKs
- [security_id, integer, false, "PK", {derived: "ABS(HASH(ticker))"}]
- [stock_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('STOCK_', ticker)))"}]
- [company_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('COMPANY_', ticker)))"}]
- [date_id, integer, false, "PK", {derived: "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"}]
- [crime_type_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(iucr_code, '_', fbi_code)))"}]
```

**Benefits:**
- 4 bytes storage (vs 20+ for strings/UUIDs)
- Fast integer comparisons in joins
- Deterministic - same input always yields same key
- Prefix patterns allow namespacing (`STOCK_`, `COMPANY_`)

### 5.9 date_id Pattern (Time-Series)

All facts use integer `date_id` FK to `temporal.dim_calendar`, not date columns:

```yaml
# CORRECT: date_id FK pattern
schema:
  - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]

# Join pattern:
SELECT c.date, c.year, c.month, p.close
FROM fact_prices p
JOIN temporal.dim_calendar c ON p.date_id = c.date_id
```

**Why date_id?**
- 4 bytes (integer) vs 4+ bytes (date)
- Fast integer comparison
- All calendar attributes via single join
- Consistent filtering across all models

---

## 6. Base Templates Reference

### 6.1 Temporal Base

**Location**: `domains/_base/temporal/calendar.md`

**Purpose**: Integer date_id pattern for all time-series joins

```yaml
---
type: domain-base
model: calendar
version: 3.0
description: "Calendar dimension template"

tables:
  dim_calendar:
    type: dimension
    primary_key: [date_id]
    unique_key: [date]

    schema:
      # Primary key (integer YYYYMMDD)
      - [date_id, integer, false, "PK (YYYYMMDD format)", {derived: "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"}]
      - [date, date, false, "Calendar date (natural key)"]

      # Year hierarchy
      - [year, integer, false, "Calendar year"]
      - [year_start_date, date, false, "First day of year"]
      - [year_end_date, date, false, "Last day of year"]

      # Quarter hierarchy
      - [quarter, integer, false, "Quarter (1-4)"]
      - [quarter_name, string, false, "Q1, Q2, Q3, Q4"]
      - [quarter_start_date, date, false, "First day of quarter"]
      - [quarter_end_date, date, false, "Last day of quarter"]

      # Month hierarchy
      - [month, integer, false, "Month (1-12)"]
      - [month_name, string, false, "January, February, etc."]
      - [month_short, string, false, "Jan, Feb, etc."]
      - [month_start_date, date, false, "First day of month"]
      - [month_end_date, date, false, "Last day of month"]
      - [days_in_month, integer, false, "Number of days"]

      # Week hierarchy
      - [week_of_year, integer, false, "ISO week (1-53)"]
      - [week_start_date, date, false, "Monday of week"]
      - [week_end_date, date, false, "Sunday of week"]

      # Day attributes
      - [day_of_month, integer, false, "Day (1-31)"]
      - [day_of_week, integer, false, "Day (1=Mon, 7=Sun)"]
      - [day_name, string, false, "Monday, Tuesday, etc."]
      - [day_short, string, false, "Mon, Tue, etc."]

      # Boolean flags
      - [is_weekday, boolean, false, "Mon-Fri"]
      - [is_weekend, boolean, false, "Sat-Sun"]
      - [is_trading_day, boolean, false, "Stock market open"]
      - [is_holiday, boolean, false, "US federal holiday"]

      # Fiscal periods (configurable)
      - [fiscal_year, integer, false, "Fiscal year"]
      - [fiscal_quarter, integer, false, "Fiscal quarter (1-4)"]
      - [fiscal_month, integer, false, "Fiscal month (1-12)"]

# Generation config
generation:
  start_date: "2000-01-01"
  end_date: "2050-12-31"
  fiscal_year_start_month: 1
  holidays: us_federal
---
```

### 6.2 Finance/Securities Base

**Location**: `domains/_base/finance/securities.md`

**Purpose**: Template for all tradable securities (stocks, options, ETFs, futures)

**Key Design**: The base defines **canonical field names only** - it does NOT know about source-specific names like `"1. open"` or `"o"`. Each domain-model provides its own alias mappings.

```yaml
---
type: domain-base
model: securities
version: 2.0
description: "Template for all tradable securities"

# Canonical fields - the official names ALL children will output
# Does NOT include source-specific aliases - those live in domain-models
canonical_fields:
  # Dimension fields
  ticker:
    type: string
    nullable: false
    description: "Trading symbol identifier (natural key)"

  security_name:
    type: string
    nullable: true
    description: "Full name of the security"

  asset_type:
    type: string
    nullable: false
    description: "Asset class classification"
    enum: [stocks, etf, option, future, warrant, unit, rights]

  exchange_code:
    type: string
    nullable: true
    description: "Primary exchange listing"

  # Price fields
  open:
    type: decimal(18,4)
    nullable: true
    description: "Opening price for the trading period"

  high:
    type: decimal(18,4)
    nullable: true
    description: "Highest price during the trading period"

  low:
    type: decimal(18,4)
    nullable: true
    description: "Lowest price during the trading period"

  close:
    type: decimal(18,4)
    nullable: true
    description: "Closing price for the trading period"

  volume:
    type: long
    nullable: true
    description: "Number of shares/contracts traded"

  adjusted_close:
    type: decimal(18,4)
    nullable: true
    description: "Split and dividend adjusted closing price"

# Template tables use canonical fields
tables:
  _dim_security:
    type: dimension
    description: "Base security dimension"
    primary_key: [security_id]
    unique_key: [ticker]

    schema:
      - [security_id, integer, false, "PK", {derived: "ABS(HASH(ticker))"}]
      - [ticker, string, false, "Trading symbol"]           # canonical
      - [security_name, string, true, "Full name"]          # canonical
      - [asset_type, string, false, "Asset class"]          # canonical
      - [exchange_code, string, true, "Exchange"]           # canonical
      - [currency, string, true, "Currency", {default: "USD"}]
      - [is_active, boolean, true, "Trading status", {default: true}]

  _fact_prices_base:
    type: fact
    description: "Base OHLCV price template"
    primary_key: [price_id]
    partition_by: [date_id]

    schema:
      - [price_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', trade_date)))"}]
      - [security_id, integer, false, "FK", {fk: _dim_security.security_id}]
      - [date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [ticker, string, false, "Symbol (kept for queries)"]
      - [trade_date, date, false, "Date (kept for queries)"]
      - [open, decimal(18,4), true, "Open"]                 # canonical
      - [high, decimal(18,4), true, "High"]                 # canonical
      - [low, decimal(18,4), true, "Low"]                   # canonical
      - [close, decimal(18,4), true, "Close"]               # canonical
      - [volume, long, true, "Volume"]                      # canonical
      - [adjusted_close, decimal(18,4), true, "Adjusted"]   # canonical

# Federation configuration
federation:
  enabled: true
  union_key: asset_type
  primary_key: security_id
  children:
    - stocks
    - options
    - etfs
    - futures
---

## Base Securities Template

This template defines the **canonical schema** for all tradable securities.

### Adding a New Data Source

To add a new data source (e.g., Yahoo Finance), create a new domain-model:

```yaml
# securities/stocks_yahoo.md
type: domain-model
extends: _base.finance.securities

# Map Yahoo's field names → canonical names
aliases:
  "Symbol": ticker
  "Name": security_name
  "Open": open
  "High": high
  "Low": low
  "Close": close
  "Volume": volume
  "Adj Close": adjusted_close
```

The base template does NOT need to be updated - it only knows canonical names.
```

### 6.3 Geospatial Base

**Location**: `domains/_base/geospatial/geospatial.md`

**Purpose**: Geographic hierarchy dimensions

```yaml
---
type: domain-base
model: geospatial
version: 1.0
description: "Geographic dimensions template"

tables:
  dim_location:
    type: dimension
    description: "Flat location dimension (any level)"
    primary_key: [location_id]
    unique_key: [location_type, location_code]

    schema:
      - [location_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(location_type, '_', location_code)))"}]
      - [location_type, string, false, "country, state, county, city, zip, etc."]
      - [location_code, string, false, "FIPS, ZIP, etc."]
      - [location_name, string, false, "Full name"]
      - [latitude, decimal(10,6), true, "Centroid latitude"]
      - [longitude, decimal(10,6), true, "Centroid longitude"]
      - [geometry_wkt, string, true, "WKT for spatial ops"]
      - [population, long, true, "Population"]
      - [land_area_sqmi, decimal(12,2), true, "Land area"]

  _dim_state_base:
    type: dimension
    primary_key: [state_id]
    unique_key: [state_fips]

    schema:
      - [state_id, integer, false, "PK", {derived: "ABS(HASH(state_fips))"}]
      - [state_fips, string, false, "2-digit FIPS code"]
      - [state_abbr, string, false, "2-letter abbreviation"]
      - [state_name, string, false, "Full name"]
      - [region, string, true, "Census region"]
      - [division, string, true, "Census division"]

  _dim_county_base:
    type: dimension
    primary_key: [county_id]
    unique_key: [county_fips]

    schema:
      - [county_id, integer, false, "PK", {derived: "ABS(HASH(county_fips))"}]
      - [county_fips, string, false, "5-digit FIPS code"]
      - [county_name, string, false, "County name"]
      - [state_id, integer, false, "FK to state", {fk: _dim_state_base.state_id}]
---
```

### 6.4 Public Safety/Crime Base

**Location**: `domains/_base/public_safety/crime.md`

**Purpose**: Crime/incident data structure across jurisdictions

```yaml
---
type: domain-base
model: crime
version: 1.0
description: "Crime and incident data template"

tables:
  dim_crime_type:
    type: dimension
    primary_key: [crime_type_id]
    unique_key: [iucr_code, fbi_code]

    schema:
      - [crime_type_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(iucr_code, '_', fbi_code)))"}]
      - [iucr_code, string, false, "IUCR crime code"]
      - [fbi_code, string, true, "FBI UCR code"]
      - [primary_type, string, false, "Crime category"]
      - [description, string, true, "Crime description"]
      - [crime_category, string, false, "VIOLENT, PROPERTY, OTHER", {enum: [VIOLENT, PROPERTY, OTHER]}]
      - [is_index_crime, boolean, false, "FBI index crime"]

    aliasable_fields:
      iucr_code: {default_aliases: [crime_code, iucr]}
      primary_type: {default_aliases: [crime_type, offense_type]}

  dim_location_type:
    type: dimension
    primary_key: [location_type_id]
    unique_key: [location_description]

    schema:
      - [location_type_id, integer, false, "PK", {derived: "ABS(HASH(location_description))"}]
      - [location_description, string, false, "Location type"]
      - [location_category, string, false, "STREET, RESIDENCE, BUSINESS, etc."]

  _fact_crimes_base:
    type: fact
    primary_key: [incident_id]
    partition_by: [date_id]

    schema:
      - [incident_id, integer, false, "PK", {derived: "ABS(HASH(case_number))"}]
      - [crime_type_id, integer, false, "FK", {fk: dim_crime_type.crime_type_id}]
      - [location_type_id, integer, false, "FK", {fk: dim_location_type.location_type_id}]
      - [date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [location_id, integer, true, "FK to geospatial"]
      - [case_number, string, false, "Natural key"]
      - [block, string, true, "Block address"]
      - [latitude, decimal(10,6), true, "Incident latitude"]
      - [longitude, decimal(10,6), true, "Incident longitude"]
      - [arrest_made, boolean, true, "Arrest flag"]
      - [domestic, boolean, true, "Domestic flag"]

federation:
  enabled: true
  union_key: jurisdiction
  children:
    - chicago_public_safety
    - cook_county_public_safety
---
```

---

## 7. Domain Model Implementation

### 7.1 Inheritance Pattern

When a domain model uses `extends:`, it inherits:

1. **Schema columns** - All columns from parent template
2. **Aliasable fields** - Field aliasing configuration
3. **Graph patterns** - Node and edge definitions
4. **Federation membership** - Auto-registration with parent federation

**Deep Merge Rules**:

```
Parent Template         +        Child Model          =        Result
─────────────────────────────────────────────────────────────────────
schema:                          schema:                       schema:
  - [ticker, string]              - [stock_type, string]        - [ticker, string]      # inherited
  - [security_name, string]                                      - [security_name, string]
                                                                 - [stock_type, string]  # added

aliases:                         aliases:                      aliases:
  (from aliasable_fields)          symbol: ticker                symbol: ticker         # merged
                                   name: security_name           name: security_name
```

### 7.2 Graph Building

The graph section defines how Bronze data transforms into Silver tables:

```yaml
graph:
  nodes:
    dim_stock:
      # Source: Bronze table
      from: bronze.alpha_vantage.listing_status
      type: dimension

      # Filter rows
      filter: "asset_type = 'stocks'"

      # Only include tickers that exist in securities
      filter_by_dimension: securities.dim_security

      # Column mapping (source → target with transformations)
      select:
        stock_id: "ABS(HASH(CONCAT('STOCK_', symbol)))"
        security_id: "ABS(HASH(symbol))"
        company_id: "ABS(HASH(CONCAT('COMPANY_', symbol)))"
        ticker: symbol
        security_name: name
        asset_type: assetType
        exchange_code: exchange
        is_active: "status = 'Active'"

      # Computed columns not from source
      derive:
        currency: "'USD'"
        stock_type: "'common'"

      # Columns to exclude
      drop: [delistingDate, ipoDate]
```

### 7.3 Cross-Model Edges

Edges can reference tables in other models using dot notation:

```yaml
edges:
  stock_to_company:
    from: dim_stock                    # Table in current model
    to: company.dim_company            # Table in 'company' model
    on: [company_id=company_id]        # Join condition
    type: many_to_one                  # Cardinality
    cross_model: company               # Explicit cross-model reference
    optional: true                     # Left join (nullable FK)
```

### 7.4 Navigation Paths

Paths define reusable multi-step query patterns:

```yaml
paths:
  prices_to_company:
    description: "Navigate from stock prices to company fundamentals"
    steps:
      - {from: fact_stock_prices, to: dim_stock, via: security_id}
      - {from: dim_stock, to: company.dim_company, via: company_id}
```

**Usage in Queries**:

```python
# Session can use paths for auto-join
session.query_with_path(
    "prices_to_company",
    select=["ticker", "close", "sector", "industry"],
    filters=[{"year": 2025}]
)
```

### 7.5 Filter-by-Dimension Pattern

Quality control to only build facts for known dimension members:

```yaml
nodes:
  fact_stock_prices:
    from: bronze.alpha_vantage.time_series_daily_adjusted
    filter_by_dimension: dim_stock  # Only prices for known stocks
```

This ensures that price records without a matching stock dimension entry are excluded.

---

## 8. Auto-Federation and Cross-Model Queries

### 8.1 Federation Configuration

Base templates declare federation settings that child models inherit:

```yaml
# In _base/finance/securities.md
federation:
  enabled: true
  union_key: asset_type       # Column that identifies source model
  primary_key: security_id    # Shared PK across federated tables

  children:
    - stocks
    - options
    - etfs
    - futures
```

### 8.2 Automatic Registration

When a model extends a federation-enabled template, it automatically registers:

```yaml
# In securities/stocks.md
extends: _base.finance.securities

# Automatically registered as federation child with:
#   union_key value: 'stocks'
#   Contributes: dim_stock, fact_stock_prices
```

### 8.3 Query Patterns

**Pattern 1: Query Single Model**

```sql
-- Query stocks only
SELECT ticker, close, volume
FROM stocks.fact_stock_prices
WHERE date_id = 20250101
```

**Pattern 2: Cross-Model Join**

```sql
-- Join stocks with company
SELECT s.ticker, p.close, c.sector, c.industry
FROM stocks.fact_stock_prices p
JOIN stocks.dim_stock s ON p.security_id = s.security_id
JOIN company.dim_company c ON s.company_id = c.company_id
WHERE c.sector = 'Technology'
```

**Pattern 3: Federated Query (All Securities)**

```sql
-- Query all asset types through federation view
SELECT asset_type, COUNT(*) as count, AVG(close) as avg_close
FROM securities.v_all_prices  -- Federation view
WHERE date_id = 20250101
GROUP BY asset_type
```

### 8.4 Federation View (Generated)

The framework can generate federation views:

```yaml
# Generated federation view definition
views:
  v_all_securities:
    type: federation
    base: _base.finance.securities
    description: "Union of all security types"

    union:
      - model: stocks
        table: dim_stock
        union_value: 'stocks'
      - model: options
        table: dim_option
        union_value: 'options'
      - model: etfs
        table: dim_etf
        union_value: 'etfs'
      - model: futures
        table: dim_future
        union_value: 'futures'

    select:
      - security_id
      - ticker
      - security_name
      - asset_type
      - exchange_code
      - is_active
```

### 8.5 Materialized Federation (Optional)

For performance, federated views can be materialized:

```yaml
# In domains/securities/all_securities.md
---
type: domain-model
model: all_securities
version: 1.0
description: "Materialized union of all securities"

federation:
  materialize: true           # Create actual tables
  refresh: daily              # Rebuild frequency

storage:
  silver:
    root: storage/silver/all_securities/

tables:
  dim_all_securities:
    type: dimension
    materialized: true

    source:
      union:
        - model: stocks
          table: dim_stock
        - model: options
          table: dim_option
        - model: etfs
          table: dim_etf
        - model: futures
          table: dim_future

    schema:
      - [security_id, integer, false, "PK"]
      - [ticker, string, false, "Symbol"]
      - [security_name, string, true, "Name"]
      - [asset_type, string, false, "Source model"]
      # ... inherited columns
---
```

---

## 9. Build System

### 9.1 Build Order (Dependencies)

Models are built in dependency order:

```
Phase 0: Foundation (no dependencies)
  └── temporal

Phase 1: Independent models
  ├── securities (depends: temporal)
  ├── company (depends: temporal)
  └── geospatial (depends: none)

Phase 2: Dependent models
  ├── stocks (depends: temporal, securities, company)
  ├── chicago_geospatial (depends: geospatial)
  └── chicago_finance (depends: temporal)

Phase 3: Complex dependencies
  └── chicago_public_safety (depends: temporal, geospatial, chicago_geospatial)

Phase 4: Federation materialization (if enabled)
  └── all_securities (depends: stocks, options, etfs, futures)
```

### 9.2 Build Configuration

```yaml
build:
  # Partition columns for Delta Lake
  partitions: [date_id]

  # Sort order for Z-ordering (clustered access)
  sort_by: [security_id, date_id]

  # Run OPTIMIZE command after build
  optimize: true

  # Optional: intermediate tables for multi-step transforms
  phases:
    1:
      tables: [_int_raw_prices]      # Intermediate
      persist: false                  # Drop after phase 2
    2:
      tables: [fact_stock_prices]    # Final
      persist: true
```

### 9.3 Intermediate Tables

For complex transformations, use intermediate tables:

```yaml
tables:
  # Intermediate (phase 1) - not persisted
  _int_raw_prices:
    type: intermediate
    persist: false

    source:
      from: bronze.alpha_vantage.time_series_daily_adjusted

    select:
      ticker: symbol
      trade_date: "TO_DATE(timestamp)"
      open: "1. open"
      close: "4. close"

  # Final (phase 2) - persisted
  fact_stock_prices:
    type: fact
    persist: true

    source:
      from: _int_raw_prices          # Reference intermediate
      join:
        - table: securities.dim_security
          on: [ticker=ticker]

    select:
      price_id: "ABS(HASH(CONCAT(ticker, '_', trade_date)))"
      security_id: securities.dim_security.security_id
      date_id: "CAST(DATE_FORMAT(trade_date, 'yyyyMMdd') AS INT)"
```

### 9.4 Build Commands

```bash
# Build all models in dependency order
python -m scripts.build.build_models

# Build specific model
python -m scripts.build.build_models --models stocks

# Rebuild with fresh ingestion
python -m scripts.build.rebuild_model --model stocks --reingest

# Build federation materialization
python -m scripts.build.build_models --models all_securities
```

### 9.5 SLA Configuration

Models can specify service level agreements:

```yaml
metadata:
  sla_hours: 4   # Must complete within 4 hours

# SLA by model type (actual):
# temporal: 1 hour
# securities: 4 hours
# stocks: 4 hours
# company: 24 hours (many API calls)
# chicago_public_safety: 24 hours
```

---

## 10. Complete Securities Example

### 10.1 Model Dependency Graph

```
temporal (foundation)
    │
    ├─────────────────────────────┐
    ▼                             ▼
securities                    company
(dim_security,                (dim_company,
 fact_security_prices)         fact_income_statement,
    │                          fact_balance_sheet,
    │                          fact_cash_flow,
    │                          fact_earnings)
    │                             │
    └──────────┬──────────────────┘
               ▼
            stocks
         (dim_stock,
          fact_stock_prices,
          fact_stock_technicals,
          fact_dividends,
          fact_splits)
```

### 10.2 Data Flow

```
Alpha Vantage API
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│                    BRONZE LAYER                         │
│  alpha_vantage/listing_status      → All US tickers    │
│  alpha_vantage/time_series_daily   → OHLCV prices      │
│  alpha_vantage/company_overview    → Fundamentals      │
│  alpha_vantage/dividends           → Dividend history  │
│  alpha_vantage/splits              → Split history     │
└─────────────────────────────────────────────────────────┘
      │
      ▼ ETL (build_models.py)
      │
┌─────────────────────────────────────────────────────────┐
│                    SILVER LAYER                         │
│                                                         │
│  temporal/                                              │
│    dim_calendar (18,628 rows: 2000-2050)               │
│                                                         │
│  securities/                                            │
│    dim_security (master security dimension)            │
│    fact_security_prices (unified OHLCV)                │
│                                                         │
│  company/                                               │
│    dim_company (corporate entities)                    │
│    fact_income_statement                               │
│    fact_balance_sheet                                  │
│    fact_cash_flow                                      │
│    fact_earnings                                       │
│                                                         │
│  stocks/                                                │
│    dim_stock (filtered from securities)                │
│    fact_stock_prices (filtered from securities)        │
│    fact_stock_technicals (computed post-build)         │
│    fact_dividends                                       │
│    fact_splits                                          │
└─────────────────────────────────────────────────────────┘
      │
      ▼ Query (UniversalSession)
      │
┌─────────────────────────────────────────────────────────┐
│                  ANALYTICS LAYER                        │
│  DuckDB catalog (storage/duckdb/analytics.db)          │
│  - Point queries for BI                                │
│  - Cross-model joins via edges/paths                   │
│  - Measure calculations                                │
│  - Federated queries                                   │
└─────────────────────────────────────────────────────────┘
```

### 10.3 Query Examples

**Example 1: Stock prices with calendar**

```sql
SELECT
    c.date,
    c.year,
    c.quarter,
    s.ticker,
    p.open,
    p.high,
    p.low,
    p.close,
    p.volume
FROM stocks.fact_stock_prices p
JOIN temporal.dim_calendar c ON p.date_id = c.date_id
JOIN stocks.dim_stock s ON p.security_id = s.security_id
WHERE s.ticker = 'AAPL'
  AND c.year = 2025
  AND c.is_trading_day = true
ORDER BY c.date DESC
LIMIT 10
```

**Example 2: Sector analysis with company fundamentals**

```sql
SELECT
    co.sector,
    co.industry,
    COUNT(DISTINCT s.ticker) as num_stocks,
    AVG(p.close) as avg_price,
    SUM(p.volume) as total_volume,
    AVG(i.net_income) as avg_net_income
FROM stocks.fact_stock_prices p
JOIN stocks.dim_stock s ON p.security_id = s.security_id
JOIN company.dim_company co ON s.company_id = co.company_id
LEFT JOIN company.fact_income_statement i
    ON co.company_id = i.company_id
    AND i.period_end_date_id = (
        SELECT MAX(period_end_date_id)
        FROM company.fact_income_statement
        WHERE company_id = co.company_id
    )
WHERE p.date_id = 20250127
GROUP BY co.sector, co.industry
ORDER BY total_volume DESC
```

**Example 3: Technical analysis with RSI**

```sql
SELECT
    s.ticker,
    c.date,
    p.close,
    t.rsi_14,
    t.sma_50,
    t.sma_200,
    CASE
        WHEN t.rsi_14 < 30 THEN 'Oversold'
        WHEN t.rsi_14 > 70 THEN 'Overbought'
        ELSE 'Neutral'
    END as rsi_signal,
    CASE
        WHEN t.sma_50 > t.sma_200 THEN 'Golden Cross'
        WHEN t.sma_50 < t.sma_200 THEN 'Death Cross'
        ELSE 'Neutral'
    END as ma_signal
FROM stocks.fact_stock_prices p
JOIN stocks.dim_stock s ON p.security_id = s.security_id
JOIN stocks.fact_stock_technicals t
    ON t.security_id = s.security_id AND t.date_id = p.date_id
JOIN temporal.dim_calendar c ON p.date_id = c.date_id
WHERE s.ticker IN ('AAPL', 'MSFT', 'GOOGL')
  AND c.date >= '2025-01-01'
ORDER BY s.ticker, c.date
```

**Example 4: Dividend yield calculation**

```sql
WITH latest_prices AS (
    SELECT
        s.ticker,
        p.close as current_price,
        ROW_NUMBER() OVER (PARTITION BY s.ticker ORDER BY p.date_id DESC) as rn
    FROM stocks.fact_stock_prices p
    JOIN stocks.dim_stock s ON p.security_id = s.security_id
),
annual_dividends AS (
    SELECT
        s.ticker,
        SUM(d.dividend_amount) as annual_dividend
    FROM stocks.fact_dividends d
    JOIN stocks.dim_stock s ON d.security_id = s.security_id
    JOIN temporal.dim_calendar c ON d.ex_dividend_date_id = c.date_id
    WHERE c.year = 2024
    GROUP BY s.ticker
)
SELECT
    lp.ticker,
    lp.current_price,
    ad.annual_dividend,
    (ad.annual_dividend / lp.current_price) * 100 as dividend_yield_pct
FROM latest_prices lp
JOIN annual_dividends ad ON lp.ticker = ad.ticker
WHERE lp.rn = 1
ORDER BY dividend_yield_pct DESC
```

### 10.4 Python Measures

Complex calculations in Python:

```python
# models/implemented/stocks/measures.py

class StocksMeasures:
    """Python measures for stocks model."""

    def __init__(self, model):
        self.model = model

    def calculate_sharpe_ratio(
        self,
        ticker: str = None,
        risk_free_rate: float = 0.045,
        window_days: int = 252,
        **kwargs
    ) -> float:
        """Calculate annualized Sharpe ratio.

        Args:
            ticker: Stock ticker (required)
            risk_free_rate: Annual risk-free rate (default 4.5%)
            window_days: Rolling window in trading days

        Returns:
            Sharpe ratio (annualized)
        """
        import numpy as np

        # Get price data via model
        df = self.model.get_prices(ticker=ticker, columns=['trade_date', 'close'])

        if len(df) < window_days:
            return None

        # Calculate daily returns
        df['return'] = df['close'].pct_change()

        # Annualized metrics
        mean_return = df['return'].mean() * 252
        std_return = df['return'].std() * np.sqrt(252)

        # Sharpe ratio
        sharpe = (mean_return - risk_free_rate) / std_return

        return round(sharpe, 4)

    def calculate_beta(
        self,
        ticker: str = None,
        benchmark: str = "SPY",
        window_days: int = 252,
        **kwargs
    ) -> float:
        """Calculate beta relative to benchmark.

        Args:
            ticker: Stock ticker
            benchmark: Benchmark ticker (default SPY)
            window_days: Rolling window in trading days

        Returns:
            Beta coefficient
        """
        import numpy as np

        # Get both price series
        stock_df = self.model.get_prices(ticker=ticker, columns=['trade_date', 'close'])
        bench_df = self.model.get_prices(ticker=benchmark, columns=['trade_date', 'close'])

        # Align on dates and calculate returns
        merged = stock_df.merge(bench_df, on='trade_date', suffixes=('_stock', '_bench'))
        merged['stock_return'] = merged['close_stock'].pct_change()
        merged['bench_return'] = merged['close_bench'].pct_change()
        merged = merged.dropna().tail(window_days)

        # Calculate beta
        covariance = np.cov(merged['stock_return'], merged['bench_return'])[0, 1]
        variance = np.var(merged['bench_return'])

        beta = covariance / variance

        return round(beta, 4)
```

---

## Appendix: YAML Reference

### A.1 Top-Level Keys

| Key | Required | Type | Description |
|-----|----------|------|-------------|
| `type` | Yes | string | `domain-base` or `domain-model` |
| `model` | Yes | string | Model identifier |
| `version` | Yes | string | Semantic version |
| `description` | Yes | string | Model description |
| `tags` | No | list | Classification tags |
| `extends` | No | string | Parent template reference |
| `depends_on` | No | list | Build dependencies |
| `storage` | Conditional | object | Required for `domain-model` |
| `build` | No | object | Build configuration |
| `tables` | Yes | object | Table definitions |
| `graph` | No | object | Graph (nodes, edges, paths) |
| `measures` | No | object | Measure definitions |
| `federation` | No | object | Federation configuration |
| `metadata` | No | object | Ownership, SLA |
| `status` | No | string | `active`, `deprecated`, `draft` |

### A.2 Storage Configuration

```yaml
storage:
  format: delta                    # Storage format (always delta)
  auto_vacuum: true                # Remove old versions

  bronze:                          # Source tables
    provider: alpha_vantage        # Provider name
    tables:                        # Table mappings
      local_name: provider/table

  silver:                          # Output configuration
    root: storage/silver/model/    # Output directory
```

### A.3 Table Definition

```yaml
tables:
  table_name:
    type: dimension | fact | intermediate
    extends: _base.template._table   # Optional inheritance
    description: "Description"
    primary_key: [columns]
    unique_key: [columns]            # Optional
    partition_by: [columns]          # Optional
    persist: true | false            # For intermediate tables

    schema:
      - [column, type, nullable, description, {options}]

    aliases:                         # Source → canonical mapping
      source_field: canonical_field

    aliasable_fields:                # For base templates
      field_name:
        default_aliases: [alias1, alias2]
        description: "Field description"
```

### A.4 Schema Column Options

```yaml
# Full column definition
- [column_name, type, nullable, description, {options}]

# Options object keys:
{
  derived: "SQL_EXPRESSION",        # Computed column
  fk: "table.column",               # Foreign key reference
  optional: true,                   # Nullable FK
  enum: [value1, value2],           # Allowed values
  default: value,                   # Default value
  format: "$#,##0.00"               # Display format
}
```

### A.5 Data Types

| Type | Description | Example |
|------|-------------|---------|
| `integer` | 32-bit integer | `security_id` |
| `long` | 64-bit integer | `volume` |
| `decimal(p,s)` | Fixed-point decimal | `decimal(18,4)` |
| `string` | Variable-length string | `ticker` |
| `boolean` | True/false | `is_active` |
| `date` | Calendar date | `trade_date` |
| `timestamp` | Date + time | `updated_on` |

### A.6 Graph Definition

```yaml
graph:
  nodes:
    node_name:
      from: bronze.provider.table | model.table | self
      type: dimension | fact
      filter: "SQL condition"
      filter_by_dimension: model.table

      select:
        target_col: source_col | "SQL expression"

      derive:
        computed_col: "SQL expression"

      drop: [columns_to_exclude]

  edges:
    edge_name:
      from: source_table
      to: target_table | model.target_table
      on: [col1=col2]
      type: many_to_one | one_to_one | one_to_many
      cross_model: model_name       # For cross-model edges
      optional: true                 # Left join

  paths:
    path_name:
      description: "Path description"
      steps:
        - {from: table1, to: table2, via: column}
```

### A.7 Measures Definition

```yaml
measures:
  simple:
    - [name, aggregation, column, description, {options}]
    # Aggregations: count, count_distinct, sum, avg, min, max

  computed:
    - [name, expression, "SQL", description, {options}]

  python:
    measure_name:
      function: "module.function_name"
      params:
        param1: value1
```

### A.8 Federation Configuration

```yaml
federation:
  enabled: true | false
  union_key: column_name           # Column identifying source
  primary_key: column_name         # Shared PK across children

  children:                        # Child models (auto-populated)
    - model1
    - model2

  materialize: true | false        # Create physical tables
  refresh: daily | hourly          # Refresh frequency
```

### A.9 Build Configuration

```yaml
build:
  partitions: [columns]            # Delta Lake partitions
  sort_by: [columns]               # Z-ordering columns
  optimize: true                   # Run OPTIMIZE

  phases:                          # Multi-phase builds
    1:
      tables: [_int_table]
      persist: false
    2:
      tables: [final_table]
      persist: true
```

---

## Appendix B: Step-by-Step Template Guide

This appendix consolidates all template patterns into a step-by-step reference showing what's required vs optional at each level.

### B.1 Creating a domain-base (Template)

A domain-base defines reusable patterns that never materialize as tables themselves.

**Step 1: Header (Required)**

```yaml
---
type: domain-base                    # REQUIRED: Identifies as template
model: securities                    # REQUIRED: Template name
version: 2.0                         # REQUIRED: Semantic version
description: "Template for..."      # REQUIRED: What this template provides
```

**Step 2: Canonical Fields (Required)**

Define the official field names that ALL child models will output. These represent semantic CONCEPTS, not source-specific names.

```yaml
canonical_fields:
  # Each field defines the canonical name and its meaning
  ticker:
    type: string                     # REQUIRED: Data type
    nullable: false                  # REQUIRED: Can be null?
    description: "Trading symbol"    # REQUIRED: Semantic meaning

  open:
    type: decimal(18,4)
    nullable: true
    description: "Opening price for the trading period"

  expense_category:
    type: string
    nullable: true
    description: "Classification of how the expense is categorized"
    # Note: Corporate calls it "cost_center", Municipal calls it "fund"
```

**Step 3: Template Tables (Required)**

Define table structures using underscore prefix (indicates template, not materialized).

```yaml
tables:
  _dim_security:                     # Underscore = template table
    type: dimension                  # REQUIRED: dimension | fact
    description: "Base security dimension"
    primary_key: [security_id]       # REQUIRED for dimensions
    unique_key: [ticker]             # OPTIONAL: Natural key

    schema:
      # Format: [name, type, nullable, description, {options}]
      - [security_id, integer, false, "PK", {derived: "ABS(HASH(ticker))"}]
      - [ticker, string, false, "Symbol"]           # Uses canonical field
      - [security_name, string, true, "Full name"]  # Uses canonical field
      - [asset_type, string, false, "Asset class"]

  _fact_prices_base:
    type: fact
    primary_key: [price_id]
    partition_by: [date_id]          # OPTIONAL: Partitioning hint

    schema:
      - [price_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', trade_date)))"}]
      - [security_id, integer, false, "FK", {fk: _dim_security.security_id}]
      - [date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [open, decimal(18,4), true, "Open"]         # Uses canonical field
      - [close, decimal(18,4), true, "Close"]       # Uses canonical field
      - [volume, long, true, "Volume"]              # Uses canonical field
```

**Step 4: Federation Configuration (Optional)**

Enable cross-model queries for all children extending this template.

```yaml
federation:
  enabled: true                      # REQUIRED if federation block present
  union_key: asset_type              # REQUIRED: Column that identifies source
  primary_key: security_id           # REQUIRED: Shared PK across children

  children:                          # OPTIONAL: Auto-populated by framework
    - stocks
    - options
    - etfs
    - futures
```

**Step 5: Close YAML and Add Documentation**

```yaml
---

## Template Name

Description of what this template provides...

### Usage

To use this template:

```yaml
extends: _base.finance.securities
```
```

---

### B.2 Creating a domain-model (Concrete Implementation)

A domain-model implements a base template for a specific data source and creates actual tables.

**Step 1: Header (Required)**

```yaml
---
type: domain-model                   # REQUIRED: Identifies as concrete model
model: stocks                        # REQUIRED: Model name
version: 3.1                         # REQUIRED: Semantic version
description: "Stock equities..."     # REQUIRED: What this model provides
tags: [securities, stocks]           # OPTIONAL: Classification
```

**Step 2: Inheritance (Optional but Recommended)**

```yaml
extends: _base.finance.securities    # OPTIONAL: Parent template
```

**Step 3: Dependencies (Required if model has dependencies)**

```yaml
depends_on: [temporal, securities, company]  # Build order dependencies
```

**Step 4: Storage Configuration (Required)**

```yaml
storage:
  format: delta                      # REQUIRED: Always delta
  auto_vacuum: true                  # OPTIONAL: Remove old versions

  bronze:                            # REQUIRED: Source data
    provider: alpha_vantage          # Provider name
    tables:
      listing_status: alpha_vantage/listing_status
      time_series: alpha_vantage/time_series_daily_adjusted

  silver:                            # REQUIRED: Output location
    root: storage/silver/stocks/
```

**Step 5: Build Configuration (Optional)**

```yaml
build:
  partitions: [date_id]              # Delta Lake partitions
  sort_by: [security_id, date_id]    # Z-ordering for clustering
  optimize: true                     # Run OPTIMIZE after build
```

**Step 6: Aliases (Required if source fields differ from canonical)**

Map YOUR source's field names to canonical names from the base template.

```yaml
aliases:
  # Source field → Canonical field
  "symbol": ticker
  "name": security_name
  "1. open": open
  "4. close": close
  "6. volume": volume
```

**Step 7: Tables (Required)**

Define concrete tables, optionally extending base templates.

```yaml
tables:
  dim_stock:
    extends: _base.finance.securities._dim_security  # OPTIONAL: Inherit from base
    type: dimension
    primary_key: [stock_id]
    unique_key: [ticker]

    schema:
      # Inherited columns come automatically from base
      # Add model-specific columns:
      - [stock_id, integer, false, "Stock PK", {derived: "ABS(HASH(CONCAT('STOCK_', ticker)))"}]
      - [company_id, integer, true, "FK to company", {fk: company.dim_company.company_id, optional: true}]

    aliases:                         # Table-specific aliases
      symbol: ticker
      name: security_name
```

**Step 8: Graph Definition (Optional but Recommended)**

```yaml
graph:
  nodes:
    dim_stock:
      from: bronze.alpha_vantage.listing_status
      type: dimension
      filter: "asset_type = 'stocks'"
      filter_by_dimension: securities.dim_security

      select:
        stock_id: "ABS(HASH(CONCAT('STOCK_', symbol)))"
        ticker: symbol
        security_name: name

      derive:
        currency: "'USD'"

  edges:
    stock_to_company:
      from: dim_stock
      to: company.dim_company
      on: [company_id=company_id]
      type: many_to_one
      cross_model: company
      optional: true

  paths:
    prices_to_sector:
      description: "Navigate from prices to company sector"
      steps:
        - {from: fact_stock_prices, to: dim_stock, via: security_id}
        - {from: dim_stock, to: company.dim_company, via: company_id}
```

**Step 9: Measures (Optional)**

```yaml
measures:
  simple:
    - [avg_close, avg, close, "Average closing price", {format: "$#,##0.00"}]
    - [total_volume, sum, volume, "Total volume", {format: "#,##0"}]

  computed:
    - [price_range, expression, "AVG(high - low)", "Daily range", {format: "$#,##0.00"}]

  python:
    sharpe_ratio:
      function: "stocks.measures.calculate_sharpe_ratio"
      params:
        risk_free_rate: 0.045
```

**Step 10: Metadata (Optional)**

```yaml
metadata:
  domain: securities
  owner: data_team
  sla_hours: 4

status: active
---
```

---

### B.3 Multi-Source Union Pattern

When multiple endpoints contribute to a single model.

**Step 1: Define Sources**

```yaml
sources:
  vendor_payments:                   # Source identifier
    from: bronze.chicago.chicago_payments  # Bronze table
    entry_type: VENDOR_PAYMENT       # Discriminator value

    aliases:                         # This source's field mappings
      vendor_name: payee
      amount: transaction_amount
      check_date: transaction_date

    derive:                          # This source's computed fields
      credit_account: "'Accounts Payable'"
      debit_account: "CONCAT('Expense:', fund)"

  employee_salaries:                 # Second source
    from: bronze.chicago.chicago_salaries
    entry_type: PAYROLL

    aliases:
      employee_name: payee
      salary_amount: transaction_amount
      pay_date: transaction_date

    derive:
      credit_account: "'Cash'"
      debit_account: "'Salaries Expense'"
```

**Step 2: Define Union Output Table**

```yaml
tables:
  fact_journal_entries:
    type: fact
    source: union(vendor_payments, employee_salaries)  # Union of sources
    partition_by: [date_id]

    schema:
      - [entry_id, integer, false, "PK"]
      - [entry_type, string, false, "Source discriminator"]
      - [payee, string, false, "Canonical payee field"]
      - [transaction_amount, decimal(18,2), false, "Canonical amount"]
      - [debit_account, string, false, "Derived debit"]
      - [credit_account, string, false, "Derived credit"]
```

---

### B.4 Field Options Reference

Options available in schema column definitions:

```yaml
schema:
  - [column_name, type, nullable, description, {options}]
```

| Option | Purpose | Example |
|--------|---------|---------|
| `derived` | SQL expression to compute value | `{derived: "ABS(HASH(ticker))"}` |
| `fk` | Foreign key reference | `{fk: temporal.dim_calendar.date_id}` |
| `optional` | Nullable FK (left join) | `{fk: company.dim_company.company_id, optional: true}` |
| `enum` | Allowed values | `{enum: [stocks, etf, option, future]}` |
| `default` | Default value | `{default: "USD"}` |
| `format` | Display format | `{format: "$#,##0.00"}` |

---

### B.5 Graph Node Options Reference

```yaml
nodes:
  node_name:
    from: bronze.provider.table      # REQUIRED: Source table
    type: dimension | fact           # REQUIRED: Table type

    filter: "SQL condition"          # OPTIONAL: Row filter
    filter_by_dimension: model.table # OPTIONAL: Only include matching dimension members

    select:                          # OPTIONAL: Column mapping
      target_col: source_col         # Direct mapping
      target_col: "SQL expression"   # Computed mapping

    derive:                          # OPTIONAL: Computed columns
      new_col: "SQL expression"

    drop: [col1, col2]               # OPTIONAL: Exclude columns
```

---

### B.6 Edge Options Reference

```yaml
edges:
  edge_name:
    from: source_table               # REQUIRED: Source table
    to: target_table                 # REQUIRED: Target (can be model.table)
    on: [col1=col2]                  # REQUIRED: Join condition(s)
    type: many_to_one | one_to_one | one_to_many  # REQUIRED

    cross_model: model_name          # OPTIONAL: If joining across models
    optional: true                   # OPTIONAL: Left join (nullable FK)
    description: "..."               # OPTIONAL: Documentation
```

---

### B.7 Quick Reference: Required vs Optional

**domain-base (Template)**

| Section | Required | Notes |
|---------|----------|-------|
| `type: domain-base` | Yes | |
| `model` | Yes | Template identifier |
| `version` | Yes | Semantic version |
| `description` | Yes | |
| `canonical_fields` | Yes | Define semantic concepts |
| `tables` | Yes | Template tables (underscore prefix) |
| `federation` | No | Enable cross-model queries |

**domain-model (Concrete)**

| Section | Required | Notes |
|---------|----------|-------|
| `type: domain-model` | Yes | |
| `model` | Yes | Model identifier |
| `version` | Yes | Semantic version |
| `description` | Yes | |
| `extends` | No | Parent template reference |
| `depends_on` | Conditional | Required if model has dependencies |
| `storage` | Yes | Bronze sources + Silver output |
| `storage.bronze` | Yes | Source data configuration |
| `storage.silver` | Yes | Output location |
| `aliases` | Conditional | Required if source fields differ from canonical |
| `tables` | Yes | Concrete table definitions |
| `graph` | No | Transformation logic |
| `measures` | No | Calculations |
| `metadata` | No | Ownership, SLA |

**Multi-Source Union**

| Section | Required | Notes |
|---------|----------|-------|
| `sources` | Yes | Define each source endpoint |
| `sources.*.from` | Yes | Bronze table path |
| `sources.*.entry_type` | Yes | Discriminator value |
| `sources.*.aliases` | Conditional | Source-specific mappings |
| `sources.*.derive` | No | Source-specific computed fields |
| `tables.*.source: union(...)` | Yes | Reference sources to union |

---

### B.8 Complete Checklist: New Model from Scratch

**Phase 1: Planning**
- [ ] Identify the semantic domain (securities, municipal, healthcare, etc.)
- [ ] Determine if a base template exists or needs to be created
- [ ] List all data sources/endpoints that will feed this model
- [ ] Map source fields to canonical concepts
- [ ] Identify cross-model dependencies

**Phase 2: Base Template (if needed)**
- [ ] Create `domains/_base/{category}/{template}.md`
- [ ] Define `canonical_fields` with semantic meanings
- [ ] Create template tables with underscore prefix
- [ ] Configure federation if cross-model queries needed
- [ ] Document usage in markdown section

**Phase 3: Domain Model**
- [ ] Create `domains/{category}/{model}.md`
- [ ] Set header: type, model, version, description
- [ ] Add `extends:` reference to base template
- [ ] List `depends_on:` for build order
- [ ] Configure `storage:` with bronze sources and silver output

**Phase 4: Field Mapping**
- [ ] Add `aliases:` mapping source fields → canonical names
- [ ] Define `derive:` expressions for computed fields
- [ ] Add foreign key references with `{fk: ...}`

**Phase 5: Tables**
- [ ] Define dimension tables with primary_key and unique_key
- [ ] Define fact tables with partition_by
- [ ] Use `extends:` to inherit from base template tables

**Phase 6: Graph (if complex transformations)**
- [ ] Define nodes with from, type, filter, select, derive
- [ ] Define edges for joins (including cross-model)
- [ ] Define paths for common navigation patterns

**Phase 7: Multi-Source (if applicable)**
- [ ] Create `sources:` block for each endpoint
- [ ] Each source gets its own aliases and derive
- [ ] Table uses `source: union(source1, source2, ...)`

**Phase 8: Measures (optional)**
- [ ] Add simple measures for basic aggregations
- [ ] Add computed measures for SQL expressions
- [ ] Add python measures for complex calculations

**Phase 9: Validation**
- [ ] All required fields present
- [ ] Dependencies correctly ordered
- [ ] Aliases cover all non-canonical source fields
- [ ] FKs reference valid tables
- [ ] Partitioning makes sense for query patterns

---

### B.9 Complete Example: Ledger Domain (Base + Two Implementations)

This example shows all concepts working together: a base template for ledger/journal entries, two domain-model implementations (corporate and municipal), and the resulting federated queries.

#### Example 1: Base Template (Ledger)

```yaml
# domains/_base/finance/ledger.md
---
type: domain-base
model: ledger
version: 1.0
description: "Template for financial ledger and journal entries across domains"

# Canonical fields - semantic concepts that ALL children will output
# Children map their source fields to these canonical names
canonical_fields:
  # Who/What
  payee:
    type: string
    nullable: false
    description: "Entity receiving payment (vendor, employee, contractor)"

  payer:
    type: string
    nullable: true
    description: "Entity making payment (if applicable)"

  # When
  transaction_date:
    type: date
    nullable: false
    description: "Date of the transaction"

  # How Much
  transaction_amount:
    type: decimal(18,2)
    nullable: false
    description: "Monetary value of the transaction"

  # Classification
  organizational_unit:
    type: string
    nullable: true
    description: "Department/agency responsible for the transaction"

  expense_category:
    type: string
    nullable: true
    description: "How the expense is classified (cost center, fund, etc.)"

  # Accounting
  debit_account:
    type: string
    nullable: false
    description: "Account to debit"

  credit_account:
    type: string
    nullable: false
    description: "Account to credit"

  # Metadata
  entry_description:
    type: string
    nullable: true
    description: "Human-readable description of the entry"

  entry_type:
    type: string
    nullable: false
    description: "Type of journal entry (discriminator for unions)"

# Template tables - underscore prefix means NOT materialized
tables:
  _dim_account:
    type: dimension
    description: "Chart of accounts template"
    primary_key: [account_id]
    unique_key: [account_code]

    schema:
      - [account_id, integer, false, "PK", {derived: "ABS(HASH(account_code))"}]
      - [account_code, string, false, "Account number"]
      - [account_name, string, false, "Account description"]
      - [account_type, string, false, "Asset, Liability, Equity, Revenue, Expense"]
      - [parent_account_id, integer, true, "FK for hierarchy", {fk: _dim_account.account_id}]

  _dim_organizational_unit:
    type: dimension
    description: "Department/agency dimension template"
    primary_key: [org_unit_id]
    unique_key: [org_unit_code]

    schema:
      - [org_unit_id, integer, false, "PK", {derived: "ABS(HASH(org_unit_code))"}]
      - [org_unit_code, string, false, "Department code"]
      - [org_unit_name, string, false, "Department name"]
      - [parent_org_unit_id, integer, true, "FK for hierarchy", {fk: _dim_organizational_unit.org_unit_id}]

  _fact_journal_entries:
    type: fact
    description: "Journal entry template"
    primary_key: [entry_id]
    partition_by: [date_id]

    schema:
      - [entry_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(entry_type, '_', source_id)))"}]
      - [date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [org_unit_id, integer, true, "FK", {fk: _dim_organizational_unit.org_unit_id}]
      - [debit_account_id, integer, false, "FK", {fk: _dim_account.account_id}]
      - [credit_account_id, integer, false, "FK", {fk: _dim_account.account_id}]
      - [entry_type, string, false, "Source discriminator"]
      - [payee, string, false, "Who received payment"]
      - [transaction_amount, decimal(18,2), false, "Amount"]
      - [transaction_date, date, false, "Date"]
      - [organizational_unit, string, true, "Department name"]
      - [expense_category, string, true, "Classification"]
      - [entry_description, string, true, "Description"]

# Federation - enables cross-domain queries
federation:
  enabled: true
  union_key: domain_type
  primary_key: entry_id

  children:
    - corporate_ledger
    - municipal_ledger
    - federal_ledger
---

## Ledger Base Template

This template provides canonical schema for financial ledger entries.

### Canonical Concepts

| Canonical Field | Corporate Term | Municipal Term | Federal Term |
|-----------------|----------------|----------------|--------------|
| `payee` | vendor_name | vendor_name | contractor |
| `organizational_unit` | department | department | agency |
| `expense_category` | cost_center | fund | budget_object_class |
| `transaction_amount` | amount | amount | obligation_amount |

### Usage

```yaml
extends: _base.finance.ledger
```
```

---

#### Example 2: Corporate Implementation

```yaml
# domains/corporate/general_ledger.md
---
type: domain-model
model: corporate_ledger
version: 1.0
description: "Corporate general ledger with vendor payments and payroll"
tags: [corporate, finance, ledger]

extends: _base.finance.ledger

depends_on: [temporal]

storage:
  format: delta
  auto_vacuum: true

  bronze:
    provider: corporate_erp
    tables:
      vendor_payments: corporate_erp/ap_payments
      payroll: corporate_erp/payroll_register
      chart_of_accounts: corporate_erp/gl_accounts

  silver:
    root: storage/silver/corporate/ledger/

build:
  partitions: [date_id]
  sort_by: [date_id, entry_id]
  optimize: true

# Multiple sources → single journal entry model
sources:
  vendor_payments:
    from: bronze.corporate_erp.ap_payments
    entry_type: VENDOR_PAYMENT
    domain_type: CORPORATE

    # Corporate ERP field names → canonical names
    aliases:
      vendor_name: payee
      payment_amount: transaction_amount
      payment_date: transaction_date
      department: organizational_unit
      cost_center: expense_category
      invoice_description: entry_description

    derive:
      debit_account: "CONCAT('6', cost_center_code)"
      credit_account: "'2100'"
      payer: "'Corporate Treasury'"

  payroll:
    from: bronze.corporate_erp.payroll_register
    entry_type: PAYROLL
    domain_type: CORPORATE

    aliases:
      employee_name: payee
      gross_pay: transaction_amount
      pay_date: transaction_date
      department_name: organizational_unit
      job_code: expense_category

    derive:
      debit_account: "'6100'"
      credit_account: "'1000'"
      entry_description: "CONCAT('Payroll: ', employee_name, ' - ', pay_period)"
      payer: "'Corporate Treasury'"

tables:
  dim_account:
    extends: _base.finance.ledger._dim_account
    type: dimension
    primary_key: [account_id]

    aliases:
      gl_account: account_code
      gl_description: account_name
      gl_type: account_type

  dim_department:
    extends: _base.finance.ledger._dim_organizational_unit
    type: dimension
    primary_key: [org_unit_id]

    aliases:
      dept_code: org_unit_code
      dept_name: org_unit_name

  fact_journal_entries:
    extends: _base.finance.ledger._fact_journal_entries
    type: fact
    source: union(vendor_payments, payroll)
    partition_by: [date_id]

graph:
  edges:
    entry_to_calendar:
      from: fact_journal_entries
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal

    entry_to_department:
      from: fact_journal_entries
      to: dim_department
      on: [org_unit_id=org_unit_id]
      type: many_to_one

measures:
  simple:
    - [total_payments, sum, transaction_amount, "Total payment amount", {format: "$#,##0.00"}]
    - [payment_count, count, entry_id, "Number of entries"]
    - [avg_payment, avg, transaction_amount, "Average payment", {format: "$#,##0.00"}]

  computed:
    - [payroll_ratio, expression, "SUM(CASE WHEN entry_type = 'PAYROLL' THEN transaction_amount ELSE 0 END) / SUM(transaction_amount)", "Payroll as % of total", {format: "0.00%"}]

metadata:
  domain: corporate
  owner: finance_team
  sla_hours: 24

status: active
---

## Corporate General Ledger

General ledger entries from corporate ERP system.

### Sources

| Source | Entry Type | Description |
|--------|------------|-------------|
| `vendor_payments` | VENDOR_PAYMENT | AP payments to vendors |
| `payroll` | PAYROLL | Employee payroll register |

### Field Mappings

| ERP Field | Canonical Field |
|-----------|-----------------|
| `vendor_name` / `employee_name` | `payee` |
| `payment_amount` / `gross_pay` | `transaction_amount` |
| `department` / `department_name` | `organizational_unit` |
| `cost_center` / `job_code` | `expense_category` |
```

---

#### Example 3: Municipal Implementation

```yaml
# domains/municipal/chicago/finance.md
---
type: domain-model
model: municipal_ledger
version: 1.0
description: "Chicago municipal ledger with vendor payments, payroll, and contracts"
tags: [municipal, chicago, finance, ledger]

extends: _base.finance.ledger

depends_on: [temporal]

storage:
  format: delta
  auto_vacuum: true

  bronze:
    provider: chicago
    tables:
      payments: chicago/chicago_payments
      salaries: chicago/chicago_salaries
      contracts: chicago/chicago_contracts

  silver:
    root: storage/silver/chicago/finance/

build:
  partitions: [date_id]
  sort_by: [date_id, entry_id]
  optimize: true

# Three sources → single journal entry model
sources:
  vendor_payments:
    from: bronze.chicago.chicago_payments
    entry_type: VENDOR_PAYMENT
    domain_type: MUNICIPAL

    # Chicago data portal field names → canonical names
    aliases:
      vendor_name: payee
      amount: transaction_amount
      check_date: transaction_date
      department_name: organizational_unit
      fund: expense_category
      contract_description: entry_description

    derive:
      debit_account: "CONCAT('Expense:', fund)"
      credit_account: "'Accounts Payable'"
      payer: "'City of Chicago'"

  employee_salaries:
    from: bronze.chicago.chicago_salaries
    entry_type: PAYROLL
    domain_type: MUNICIPAL

    aliases:
      name: payee
      annual_salary: transaction_amount
      effective_date: transaction_date
      department: organizational_unit
      job_title: expense_category

    derive:
      debit_account: "'Salaries Expense'"
      credit_account: "'Cash'"
      entry_description: "CONCAT('Salary: ', job_title)"
      payer: "'City of Chicago'"
      # Prorate annual salary to monthly
      transaction_amount: "annual_salary / 12"

  contract_payments:
    from: bronze.chicago.chicago_contracts
    entry_type: CONTRACT
    domain_type: MUNICIPAL

    aliases:
      vendor: payee
      award_amount: transaction_amount
      start_date: transaction_date
      awarding_department: organizational_unit
      contract_type: expense_category
      description: entry_description

    derive:
      debit_account: "'Contract Services'"
      credit_account: "'Accounts Payable'"
      payer: "'City of Chicago'"

tables:
  dim_fund:
    type: dimension
    description: "Municipal fund dimension"
    primary_key: [fund_id]
    unique_key: [fund_code]

    schema:
      - [fund_id, integer, false, "PK", {derived: "ABS(HASH(fund_code))"}]
      - [fund_code, string, false, "Fund number"]
      - [fund_name, string, false, "Fund description"]
      - [fund_type, string, false, "General, Special Revenue, etc."]

  dim_department:
    extends: _base.finance.ledger._dim_organizational_unit
    type: dimension
    primary_key: [org_unit_id]

    aliases:
      department_name: org_unit_name
      department_code: org_unit_code

  fact_journal_entries:
    extends: _base.finance.ledger._fact_journal_entries
    type: fact
    source: union(vendor_payments, employee_salaries, contract_payments)
    partition_by: [date_id]

    # Add municipal-specific columns
    schema:
      # Inherited from base: entry_id, date_id, payee, transaction_amount, etc.
      - [fund_id, integer, true, "FK to fund", {fk: dim_fund.fund_id}]
      - [voucher_number, string, true, "Payment voucher number"]

graph:
  edges:
    entry_to_calendar:
      from: fact_journal_entries
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal

    entry_to_department:
      from: fact_journal_entries
      to: dim_department
      on: [org_unit_id=org_unit_id]
      type: many_to_one

    entry_to_fund:
      from: fact_journal_entries
      to: dim_fund
      on: [fund_id=fund_id]
      type: many_to_one

measures:
  simple:
    - [total_expenditure, sum, transaction_amount, "Total expenditure", {format: "$#,##0.00"}]
    - [vendor_count, count_distinct, payee, "Unique payees"]
    - [entry_count, count, entry_id, "Number of entries"]

  computed:
    - [payroll_pct, expression, "SUM(CASE WHEN entry_type = 'PAYROLL' THEN transaction_amount ELSE 0 END) * 100.0 / SUM(transaction_amount)", "Payroll % of total", {format: "0.0%"}]
    - [contract_pct, expression, "SUM(CASE WHEN entry_type = 'CONTRACT' THEN transaction_amount ELSE 0 END) * 100.0 / SUM(transaction_amount)", "Contracts % of total", {format: "0.0%"}]

metadata:
  domain: municipal
  owner: chicago_data_team
  sla_hours: 24

status: active
---

## Chicago Municipal Ledger

Municipal finance entries from Chicago Data Portal.

### Sources

| Source | Entry Type | Description |
|--------|------------|-------------|
| `vendor_payments` | VENDOR_PAYMENT | Vendor/contractor payments |
| `employee_salaries` | PAYROLL | Employee salary data |
| `contract_payments` | CONTRACT | Contract awards |

### Chicago-Specific Fields

| Chicago Field | Canonical Field |
|---------------|-----------------|
| `vendor_name` / `name` / `vendor` | `payee` |
| `amount` / `annual_salary` / `award_amount` | `transaction_amount` |
| `department_name` / `department` / `awarding_department` | `organizational_unit` |
| `fund` / `job_title` / `contract_type` | `expense_category` |
```

---

#### Example 4: Federated Query

With both models extending the same base template, federated queries work:

```sql
-- Query across BOTH corporate and municipal ledgers
-- Works because both output the same canonical schema
SELECT
    domain_type,
    entry_type,
    organizational_unit,
    expense_category,
    SUM(transaction_amount) as total_amount,
    COUNT(*) as entry_count
FROM finance.v_all_ledger_entries  -- Federation view
WHERE date_id BETWEEN 20240101 AND 20241231
GROUP BY domain_type, entry_type, organizational_unit, expense_category
ORDER BY total_amount DESC
LIMIT 20
```

**Result:**

| domain_type | entry_type | organizational_unit | expense_category | total_amount | entry_count |
|-------------|------------|---------------------|------------------|--------------|-------------|
| MUNICIPAL | PAYROLL | Police | Police Officer | 45,678,901.00 | 12,345 |
| CORPORATE | PAYROLL | Engineering | Software Dev | 23,456,789.00 | 456 |
| MUNICIPAL | VENDOR_PAYMENT | Streets & San | Maintenance | 12,345,678.00 | 2,345 |
| CORPORATE | VENDOR_PAYMENT | IT | Cloud Services | 8,765,432.00 | 123 |
| MUNICIPAL | CONTRACT | Aviation | Construction | 5,432,109.00 | 45 |

---

### B.10 Complete Example: Securities Domain (Simpler)

A simpler example showing securities with just one source per model.

#### Base Template

```yaml
# domains/_base/finance/securities.md
---
type: domain-base
model: securities
version: 2.0
description: "Template for tradable securities"

canonical_fields:
  ticker:
    type: string
    nullable: false
    description: "Trading symbol"

  security_name:
    type: string
    nullable: true
    description: "Full security name"

  open:
    type: decimal(18,4)
    nullable: true
    description: "Opening price"

  high:
    type: decimal(18,4)
    nullable: true
    description: "High price"

  low:
    type: decimal(18,4)
    nullable: true
    description: "Low price"

  close:
    type: decimal(18,4)
    nullable: true
    description: "Closing price"

  volume:
    type: long
    nullable: true
    description: "Trading volume"

tables:
  _dim_security:
    type: dimension
    primary_key: [security_id]
    unique_key: [ticker]

    schema:
      - [security_id, integer, false, "PK", {derived: "ABS(HASH(ticker))"}]
      - [ticker, string, false, "Symbol"]
      - [security_name, string, true, "Name"]
      - [asset_type, string, false, "stocks, etf, option, future"]
      - [exchange_code, string, true, "Exchange"]
      - [is_active, boolean, true, "Trading status", {default: true}]

  _fact_prices:
    type: fact
    primary_key: [price_id]
    partition_by: [date_id]

    schema:
      - [price_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', trade_date)))"}]
      - [security_id, integer, false, "FK", {fk: _dim_security.security_id}]
      - [date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [open, decimal(18,4), true, "Open"]
      - [high, decimal(18,4), true, "High"]
      - [low, decimal(18,4), true, "Low"]
      - [close, decimal(18,4), true, "Close"]
      - [volume, long, true, "Volume"]

federation:
  enabled: true
  union_key: asset_type
  primary_key: security_id
  children: [stocks, etfs, options]
---
```

#### Stocks Implementation (Alpha Vantage)

```yaml
# domains/securities/stocks.md
---
type: domain-model
model: stocks
version: 3.0
description: "Stock equities from Alpha Vantage"

extends: _base.finance.securities
depends_on: [temporal]

storage:
  format: delta
  auto_vacuum: true
  bronze:
    provider: alpha_vantage
    tables:
      listing: alpha_vantage/listing_status
      prices: alpha_vantage/time_series_daily_adjusted
  silver:
    root: storage/silver/stocks/

# Map Alpha Vantage fields → canonical
aliases:
  symbol: ticker
  name: security_name
  "1. open": open
  "2. high": high
  "3. low": low
  "4. close": close
  "6. volume": volume

tables:
  dim_stock:
    extends: _base.finance.securities._dim_security
    type: dimension
    primary_key: [security_id]

    derive:
      asset_type: "'stocks'"

  fact_stock_prices:
    extends: _base.finance.securities._fact_prices
    type: fact
    partition_by: [date_id]

graph:
  nodes:
    dim_stock:
      from: bronze.alpha_vantage.listing_status
      type: dimension
      filter: "assetType = 'Stock'"

      select:
        security_id: "ABS(HASH(symbol))"
        ticker: symbol
        security_name: name
        exchange_code: exchange
        is_active: "status = 'Active'"

      derive:
        asset_type: "'stocks'"

    fact_stock_prices:
      from: bronze.alpha_vantage.time_series_daily_adjusted
      type: fact
      filter_by_dimension: dim_stock

      select:
        price_id: "ABS(HASH(CONCAT(symbol, '_', timestamp)))"
        security_id: "ABS(HASH(symbol))"
        date_id: "CAST(DATE_FORMAT(timestamp, 'yyyyMMdd') AS INT)"
        open: "1. open"
        high: "2. high"
        low: "3. low"
        close: "4. close"
        volume: "6. volume"

  edges:
    prices_to_stock:
      from: fact_stock_prices
      to: dim_stock
      on: [security_id=security_id]
      type: many_to_one

    prices_to_calendar:
      from: fact_stock_prices
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal

measures:
  simple:
    - [avg_close, avg, close, "Average close", {format: "$#,##0.00"}]
    - [total_volume, sum, volume, "Total volume", {format: "#,##0"}]
    - [max_high, max, high, "Maximum high", {format: "$#,##0.00"}]
    - [min_low, min, low, "Minimum low", {format: "$#,##0.00"}]

  computed:
    - [avg_range, expression, "AVG(high - low)", "Avg daily range", {format: "$#,##0.00"}]

metadata:
  domain: securities
  owner: data_team
  sla_hours: 4

status: active
---

## Stocks Model

Stock equities from Alpha Vantage API.

### Aliases

| Alpha Vantage | Canonical |
|---------------|-----------|
| `symbol` | `ticker` |
| `name` | `security_name` |
| `1. open` | `open` |
| `4. close` | `close` |
| `6. volume` | `volume` |
```

---

### B.11 Summary: Key Patterns at a Glance

| Pattern | Where | Purpose |
|---------|-------|---------|
| `canonical_fields` | domain-base | Define semantic concepts |
| `aliases` | domain-model | Map source → canonical |
| `extends` | domain-model | Inherit from base template |
| `sources` | domain-model | Multiple endpoints → one table |
| `union()` | table.source | Combine sources |
| `entry_type` | source | Discriminator for union |
| `derive` | source/node | Computed fields |
| `federation` | domain-base | Enable cross-model queries |
| `cross_model` | edge | Join across models |
| `paths` | graph | Reusable navigation |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 4.0 | 2026-01-27 | Mapped to real securities/stocks patterns from existing codebase |
| 3.0 | 2026-01-27 | Added auto-federation, field aliasing (theoretical accounting example) |
| 2.0 | 2025-11 | Modular YAML, inheritance |
| 1.0 | 2025-10 | Initial specification |
