---
type: domain-model
model: stocks
version: 2.0
description: "Common stock equities with price and technical data"
tags: [stocks, equities, securities, trading]


# Inheritance and Dependencies
inherits_from: _base.securities
depends_on: []  # Builds independently from Bronze - linked to company via ticker at query time

# Storage
storage:
  root: storage/silver/stocks
  format: delta

# Build
build:
  partitions: [trade_date]
  sort_by: [ticker, trade_date]
  optimize: true

# Schema
schema:
  extends: _base.securities.schema

  dimensions:
    dim_stock:
      extends: _base.securities._dim_security
      description: "Stock equity dimension"
      primary_key: [ticker]
      columns:
        # Inherited: ticker, security_name, asset_type, asset_class,
        #            exchange_code, currency, is_active, listing_date, delisting_date
        company_id: {type: string, description: "FK to company.dim_company", required: true}
        cik: {type: string, description: "SEC Central Index Key", pattern: "^[0-9]{10}$"}
        stock_type: {type: string, description: "Type of stock", enum: [common, preferred, adr, rights, units, warrants], default: common}
        shares_outstanding: {type: long, description: "Current shares outstanding"}
        market_cap: {type: double, description: "Latest market capitalization"}
        beta: {type: double, description: "Beta vs. SPY (500-day rolling)"}
        sector: {type: string, description: "GICS Sector (denormalized)"}
        industry: {type: string, description: "GICS Industry (denormalized)"}
      tags: [dim, entity, stock, security]

  facts:
    fact_stock_prices:
      extends: _base.securities._fact_prices
      description: "Daily stock prices (filtered from unified bronze table)"
      # Inherits: ticker, trade_date, open, high, low, close, volume, volume_weighted
      primary_key: [ticker, trade_date]
      partitions: [trade_date]
      tags: [fact, prices, stocks]

# Graph
graph:
  extends: _base.securities.graph

  nodes:
    dim_stock:
      extends: _base.securities._dim_security_base
      filters:
        - "type IN ('Stock', 'Common Stock', 'Preferred Stock')"
        - "is_active = true"
      select:
        security_type: type
        cik: cik
        shares_outstanding: shares_outstanding
        market_cap: market_cap
        sector: sector
        industry: industry
      derive:
        company_id: "CONCAT('COMPANY_', cik)"
      unique_key: [ticker]
      tags: [dim, stock]

    fact_stock_prices:
      extends: _base.securities._fact_prices_base
      filter_by_dimension: dim_stock
      filters:
        - "trade_date IS NOT NULL"
        - "ticker IS NOT NULL"
      unique_key: [ticker, trade_date]
      tags: [fact, prices, stocks]

  edges:
    stock_to_company:
      from: dim_stock
      to: company.dim_company
      on: [company_id=company_id]
      type: many_to_one
      description: "Stock belongs to a company"

    prices_to_stock:
      from: fact_stock_prices
      to: dim_stock
      on: [ticker=ticker]
      type: many_to_one
      description: "Prices belong to a stock"

    prices_to_calendar:
      from: fact_stock_prices
      to: temporal.dim_calendar
      on: [trade_date=date]
      type: left
      description: "Join prices to calendar"

  paths:
    company_ticker_to_prices:
      description: "Enable ticker filter from company to prices"
      steps:
        - {from: company.dim_company, to: dim_stock, via: ticker}
        - {from: dim_stock, to: fact_stock_prices, via: ticker}

# Measures
measures:
  extends: _base.securities.measures

  simple:
    avg_market_cap:
      description: "Average market capitalization"
      source: dim_stock.market_cap
      aggregation: avg
      format: "$#,##0.00M"
      tags: [valuation]

    total_market_cap:
      description: "Total market cap across stocks"
      source: dim_stock.market_cap
      aggregation: sum
      format: "$#,##0.00B"
      tags: [valuation, aggregate]

    stock_count:
      description: "Number of stocks"
      source: dim_stock.ticker
      aggregation: count
      format: "#,##0"
      tags: [count]

    avg_shares_outstanding:
      description: "Average shares outstanding"
      source: dim_stock.shares_outstanding
      aggregation: avg
      format: "#,##0.00M"
      tags: [shares]

    avg_rsi:
      description: "Average RSI across period"
      source: fact_stock_prices.rsi_14
      aggregation: avg
      format: "#,##0.00"
      tags: [technical, momentum]

    avg_volatility_20d:
      description: "Average 20-day volatility"
      source: fact_stock_prices.volatility_20d
      aggregation: avg
      format: "#,##0.00%"
      tags: [technical, risk]

  computed:
    avg_dollar_volume:
      description: "Average daily dollar volume"
      expression: "close * volume"
      source_table: fact_stock_prices
      aggregation: avg
      format: "$#,##0.00M"
      tags: [liquidity]

    market_cap_calculated:
      description: "Market cap (close * shares)"
      expression: "close * shares_outstanding"
      source_table: fact_stock_prices
      join_tables: [dim_stock]
      aggregation: avg
      format: "$#,##0.00M"
      tags: [valuation]

  python:
    module: securities/stocks/measures.py
    class: StocksMeasures
    functions:
      sharpe_ratio:
        description: "Risk-adjusted return (Sharpe ratio)"
        params: {risk_free_rate: 0.045, window_days: 252}
        tags: [risk, performance]

      correlation_matrix:
        description: "Correlation matrix of returns"
        params: {window_days: 60, min_periods: 30}
        tags: [correlation, risk]

      momentum_score:
        description: "Multi-factor momentum score"
        params:
          weights: {rsi: 0.3, macd: 0.3, price_trend: 0.4}
        tags: [momentum]

      rolling_beta:
        description: "Rolling beta vs. market"
        params: {market_ticker: SPY, window_days: 252}
        tags: [risk, beta]

      drawdown:
        description: "Maximum drawdown from peak"
        params: {window_days: 252}
        tags: [risk]

# Metadata
metadata:
  domain: securities
  owner: data_engineering
  sla_hours: 4
  data_quality_checks:
    - no_null_tickers
    - positive_prices
    - reasonable_volumes
    - valid_company_links
status: active
---

## Stocks Model

Common stock equities with daily prices and technical indicators.

### Data Sources

| Source | Provider | Update Frequency |
|--------|----------|------------------|
| securities_reference | Alpha Vantage | Daily |
| securities_prices_daily | Alpha Vantage | Daily |

### Key Features

- **Dimension**: `dim_stock` - Stock metadata with company linkage via CIK
- **Fact**: `fact_stock_prices` - Daily OHLCV with technical indicators
- **Cross-model**: Links to `company.dim_company` and `temporal.dim_calendar`

### Technical Indicators

Technical indicators (SMA, RSI, Bollinger, etc.) are computed after initial build:

```bash
python -m scripts.build.compute_technicals --storage-path /shared/storage
```

### Usage

```python
from models.domains.securities.stocks import StocksModel
from models.api.session import UniversalSession

session = UniversalSession(backend="duckdb")
model = session.load_model("stocks")

# Get stock dimension
stocks = model.get_table("dim_stock")

# Get prices with filters
prices = model.get_table("fact_stock_prices", filters={"ticker": "AAPL"})

# Calculate measures
sharpe = model.calculate_measure("sharpe_ratio", ticker="AAPL")
```

### Homelab Usage

```bash
# Build stocks model
python -m scripts.build.rebuild_model --model stocks

# Full pipeline with stocks
./scripts/test/test_full_pipeline_spark.sh --profile dev --max-tickers 100
```

### Notes

- Inherits OHLCV schema from `_base.securities`
- Company linkage via `company_id = CONCAT('COMPANY_', cik)`
- Prices filtered to tickers existing in `dim_stock` (JOIN-based)
