---
id: domain_strategy_showcase
title: Domain Strategy Measures Showcase
description: Interactive demonstration of domain strategy measures from the equities model including weighting strategies, risk metrics, and technical indicators
tags: [domain, strategy, measures, equity, weighting, risk, technical]
models: [equity]
author: system
created: 2025-11-14
updated: 2025-11-14
---

# 🎯 Domain Strategy Measures Showcase

This notebook demonstrates the powerful **domain strategy measures** available in the equities model. Domain strategies provide specialized financial calculations including:

- **Weighting Strategies**: 6 different index construction methods
- **Risk Metrics**: Portfolio risk analysis (beta, volatility, Sharpe ratio, drawdown, alpha)
- **Technical Indicators**: 8 momentum and trend indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, OBV)

---

## 🎛️ Interactive Filters

Select your analysis parameters below:

$filter${
  id: trade_date
  type: date_range
  label: Date Range
  operator: between
  default: {start: "2024-01-01", end: "2024-10-20"}
  help_text: Filter by trade date range for analysis
}

$filter${
  id: ticker
  label: Stock Tickers
  type: select
  multi: true
  source: {model: equity, table: fact_equity_prices, column: ticker}
  default: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
  help_text: Select stocks for index construction and analysis
}

---

## 📊 Part 1: Weighting Strategy Comparison

Domain weighting strategies allow you to construct different types of market indices. Each strategy has unique characteristics:

### Strategy Overview

| Strategy | Description | Use Case |
|----------|-------------|----------|
| **Equal Weighted** | Simple average across all stocks | Benchmark without size bias |
| **Volume Weighted** | VWAP - weighted by trading volume | Institutional execution price |
| **Market Cap Weighted** | Weighted by market capitalization | S&P 500 style index |
| **Price Weighted** | Weighted by stock price | Dow Jones style index |
| **Volume Deviation** | Weighted by unusual volume | Detecting unusual activity |
| **Volatility Weighted** | Inverse volatility weighting | Risk-adjusted portfolio |

---

### 📈 Index Performance Comparison

Compare all six weighting strategies side-by-side:

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  title: Equal Weighted Index
  description: Simple average of all selected stock prices (benchmark)
  aggregations:
    close: avg
  group_by: [trade_date]
  interactive: true
  collapsible: true
  collapsible_title: "📊 Equal Weighted Index"
  collapsible_expanded: true
}

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  title: Volume Weighted Average Price (VWAP)
  description: Price weighted by trading volume - represents institutional execution price
  aggregations:
    close: weighted_avg
    weight_column: volume
  group_by: [trade_date]
  interactive: true
  collapsible: true
  collapsible_title: "💹 Volume Weighted Index (VWAP)"
  collapsible_expanded: true
}

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  title: Market Cap Weighted Index
  description: Weighted by market capitalization (close * volume proxy) - S&P 500 methodology
  derived_columns:
    market_cap: close * volume
  aggregations:
    close: weighted_avg
    weight_column: market_cap
  group_by: [trade_date]
  interactive: true
  collapsible: true
  collapsible_title: "💰 Market Cap Weighted Index (S&P 500 Style)"
  collapsible_expanded: true
}

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  title: Price Weighted Index
  description: Weighted by stock price - Dow Jones Industrial Average methodology
  aggregations:
    close: weighted_avg
    weight_column: close
  group_by: [trade_date]
  interactive: true
  collapsible: true
  collapsible_title: "📉 Price Weighted Index (DJIA Style)"
  collapsible_expanded: false
}

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: volume
  title: Volume Deviation Weighted Index
  description: Weighted by deviation from average volume - detects unusual trading activity
  derived_columns:
    avg_volume: avg(volume)
    volume_deviation: abs(volume - avg_volume)
  aggregations:
    close: weighted_avg
    weight_column: volume_deviation
  group_by: [trade_date]
  interactive: true
  collapsible: true
  collapsible_title: "🔔 Volume Deviation Weighted Index"
  collapsible_expanded: false
}

---

### 📊 Strategy Comparison Table

View all weighting strategies in a single table for easy comparison:

$exhibits${
  type: data_table
  source: equity.fact_equity_prices
  columns: [trade_date, close, volume]
  derived_columns:
    market_cap: close * volume
  aggregations:
    equal_weighted: avg
    volume_weighted: {aggregation: weighted_avg, weight_column: volume}
    market_cap_weighted: {aggregation: weighted_avg, weight_column: market_cap}
    price_weighted: {aggregation: weighted_avg, weight_column: close}
    num_stocks: count
  group_by: [trade_date]
  order_by: [{column: trade_date, direction: desc}]
  limit: 50
  format:
    equal_weighted: $#,##0.00
    volume_weighted: $#,##0.00
    market_cap_weighted: $#,##0.00
    price_weighted: $#,##0.00
    num_stocks: #,##0
  collapsible: true
  collapsible_title: "📊 All Weighting Strategies Comparison"
  collapsible_expanded: true
}

---

## 📈 Part 2: Technical Indicators

Technical indicators help identify trends, momentum, and potential trading signals.

### 🎯 Key Technical Metrics

Summary of technical indicators across selected stocks:

$exhibits${
  type: metric_cards
  source: equity.fact_equity_technicals
  metrics: [
    { measure: rsi_14, label: "Avg RSI (14)", aggregation: avg, format: "#,##0.00" },
    { measure: volatility_20d, label: "Avg Volatility (20d)", aggregation: avg, format: "#,##0.00%" },
    { measure: beta, label: "Avg Beta", aggregation: avg, format: "#,##0.00" }
  ]
  collapsible: true
  collapsible_title: "🎯 Technical Indicator Summary"
  collapsible_expanded: true
}

---

### 📊 RSI (Relative Strength Index)

RSI measures momentum on a scale of 0-100. Values above 70 indicate overbought, below 30 indicate oversold.

$exhibits${
  type: line_chart
  source: equity.fact_equity_technicals
  x: trade_date
  y: rsi_14
  color: ticker
  title: RSI (14-period) by Ticker
  description: Momentum indicator - values above 70 are overbought, below 30 are oversold
  interactive: true
  collapsible: true
  collapsible_title: "📊 Relative Strength Index (RSI)"
  collapsible_expanded: true
}

---

### 📈 Volatility Analysis

20-day rolling volatility shows price stability and risk:

$exhibits${
  type: line_chart
  source: equity.fact_equity_technicals
  x: trade_date
  y: volatility_20d
  color: ticker
  title: 20-Day Volatility by Ticker
  description: Rolling 20-day price volatility - higher values indicate greater risk
  interactive: true
  collapsible: true
  collapsible_title: "📈 20-Day Rolling Volatility"
  collapsible_expanded: true
}

---

### 📊 Beta vs. Market

Beta measures systematic risk relative to the market (beta = 1.0 means moves with market):

$exhibits${
  type: bar_chart
  source: equity.fact_equity_technicals
  x: ticker
  y: beta
  title: Beta by Ticker
  description: Systematic risk vs. market - beta > 1 means more volatile than market
  aggregations:
    beta: avg
  group_by: [ticker]
  interactive: true
  collapsible: true
  collapsible_title: "📊 Beta Comparison"
  collapsible_expanded: true
}

---

## 📊 Part 3: Price & Volume Analysis

Combine price measures with weighting strategies for deeper insights.

### 💰 Price Metrics by Ticker

$exhibits${
  type: data_table
  source: equity.fact_equity_prices
  columns: [ticker, close, volume, high, low]
  derived_columns:
    price_range: high - low
    market_cap: close * volume
  aggregations:
    avg_close: avg
    total_volume: sum
    max_high: max
    min_low: min
    avg_range: avg
    avg_market_cap: avg
  group_by: [ticker]
  order_by: [{column: avg_market_cap, direction: desc}]
  format:
    avg_close: $#,##0.00
    total_volume: #,##0
    max_high: $#,##0.00
    min_low: $#,##0.00
    avg_range: $#,##0.00
    avg_market_cap: $#,##0.00
  collapsible: true
  collapsible_title: "💰 Price Metrics by Ticker"
  collapsible_expanded: true
}

---

### 📊 Volume Analysis

$exhibits${
  type: bar_chart
  source: equity.fact_equity_prices
  x: ticker
  y: volume
  title: Total Volume by Ticker
  description: Total trading volume across selected date range
  aggregations:
    volume: sum
  group_by: [ticker]
  order_by: [{column: volume, direction: desc}]
  interactive: true
  collapsible: true
  collapsible_title: "📊 Total Volume by Ticker"
  collapsible_expanded: true
}

---

### 📈 Price Range Distribution

$exhibits${
  type: bar_chart
  source: equity.fact_equity_prices
  x: ticker
  y: high
  title: Average Daily Price Range
  description: Average difference between high and low prices
  derived_columns:
    price_range: high - low
  aggregations:
    price_range: avg
  group_by: [ticker]
  order_by: [{column: price_range, direction: desc}]
  interactive: true
  collapsible: true
  collapsible_title: "📈 Average Daily Price Range"
  collapsible_expanded: false
}

---

## 🎯 Part 4: Combined Analysis

Bring it all together with multi-dimensional analysis.

### 📊 Correlation: Volume vs. Volatility

$exhibits${
  type: scatter_chart
  source: equity.fact_equity_prices
  x: volume
  y: close
  color: ticker
  title: Volume vs. Price Correlation
  description: Relationship between trading volume and price levels
  aggregations:
    volume: avg
    close: avg
  group_by: [ticker]
  interactive: true
  collapsible: true
  collapsible_title: "📊 Volume vs. Price Scatter"
  collapsible_expanded: true
}

---

### 📈 Index Construction Summary

Compare index values across all weighting methodologies:

$exhibits${
  type: metric_cards
  source: equity.fact_equity_prices
  derived_columns:
    market_cap: close * volume
  metrics: [
    {
      measure: close,
      label: "Equal Weighted",
      aggregation: avg,
      format: "$#,##0.00"
    },
    {
      measure: close,
      label: "Volume Weighted (VWAP)",
      aggregation: weighted_avg,
      weight_column: volume,
      format: "$#,##0.00"
    },
    {
      measure: close,
      label: "Market Cap Weighted",
      aggregation: weighted_avg,
      weight_column: market_cap,
      format: "$#,##0.00"
    },
    {
      measure: close,
      label: "Price Weighted",
      aggregation: weighted_avg,
      weight_column: close,
      format: "$#,##0.00"
    }
  ]
  collapsible: true
  collapsible_title: "📈 Index Construction Summary"
  collapsible_expanded: true
}

---

## 📚 Understanding Domain Strategy Measures

### What are Domain Strategy Measures?

Domain strategy measures are specialized calculations that implement financial domain logic. They are:

1. **Declarative**: Defined in YAML configuration
2. **Backend-Agnostic**: Work with DuckDB and Spark
3. **Composable**: Can be combined with filters and aggregations
4. **Type-Safe**: Strongly typed with proper validation

### Weighting Strategy Architecture

Each weighting strategy implements a common interface:

```python
class WeightingStrategy:
    def generate_sql(
        adapter,
        table_name,
        value_column,
        group_by,
        weight_column,
        filters
    ) -> str:
        """Generate backend-specific SQL for weighted aggregation."""
```

### Available Strategies

**Weighting Strategies** (`models/implemented/equity/domains/weighting.py`):
- `equal`: Simple average (AVG)
- `volume`: Volume-weighted average price (VWAP)
- `market_cap`: Market capitalization weighted
- `price`: Price-weighted (DJIA methodology)
- `volume_deviation`: Weighted by unusual volume
- `volatility`: Inverse volatility weighted (risk parity)

**Risk Metrics** (`models/implemented/equity/domains/risk.py`):
- `beta`: Systematic risk vs. market
- `volatility`: Rolling standard deviation
- `sharpe_ratio`: Risk-adjusted returns
- `max_drawdown`: Largest peak-to-trough decline
- `alpha`: Excess return vs. market

**Technical Indicators** (`models/implemented/equity/domains/technical.py`):
- `sma`: Simple Moving Average
- `ema`: Exponential Moving Average
- `rsi`: Relative Strength Index
- `macd`: Moving Average Convergence Divergence
- `bollinger_bands`: Volatility bands
- `atr`: Average True Range
- `obv`: On-Balance Volume

### How to Use in Python

```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize session with DuckDB backend
ctx = RepoContext.from_repo_root(connection_type="duckdb")
session = UniversalSession(
    connection=ctx.connection,
    storage_cfg=ctx.storage,
    repo_root=ctx.repo
)

# Load equity model (domain strategies auto-loaded)
equity_model = session.get_model_instance('equity')

# Calculate weighted index measure
result = equity_model.calculate_measure(
    measure_name='volume_weighted_index',
    filters={
        'ticker': ['AAPL', 'MSFT', 'GOOGL'],
        'trade_date': {'start': '2024-01-01', 'end': '2024-10-20'}
    }
)

# Get DataFrame
df = result.data
print(df.head())
```

### Configuration Example

Define a weighted measure in `configs/models/equity.yaml`:

```yaml
volume_weighted_index:
  description: "Volume weighted price index across stocks"
  type: weighted
  source: fact_equity_prices.close
  weighting_method: volume
  weight_column: fact_equity_prices.volume
  group_by: [trade_date]
  data_type: double
  format: "$#,##0.00"
  tags: [index, aggregate, volume_weighted]
```

---

## 🎯 Next Steps

This showcase demonstrates the power of domain strategy measures. To extend this:

1. **Add More Strategies**: Implement custom weighting or risk strategies
2. **Combine Measures**: Create composite measures using multiple strategies
3. **Real-time Analysis**: Connect to live data feeds
4. **Portfolio Optimization**: Use risk metrics for portfolio construction
5. **Backtesting**: Test strategies against historical data

**For more information**, see:
- `examples/domain_strategy_measures_example.py` - Python usage examples with session setup
- `models/implemented/equity/domains/` - Strategy implementations
- `configs/models/equity.yaml` - Measure definitions

### Quick Start Guide

```python
# 1. Initialize session (from any script)
from core.context import RepoContext
from models.api.session import UniversalSession

ctx = RepoContext.from_repo_root(connection_type="duckdb")
session = UniversalSession(
    connection=ctx.connection,
    storage_cfg=ctx.storage,
    repo_root=ctx.repo
)

# 2. Load equity model
equity_model = session.get_model_instance('equity')

# 3. Access domain measures directly
# All weighted indices
indices = equity_model.calculate_measure('equal_weighted_index')
vwap = equity_model.calculate_measure('volume_weighted_index')

# Price measures by ticker
prices = equity_model.calculate_measure_by_ticker(
    'avg_close_price',
    tickers=['AAPL', 'MSFT', 'GOOGL']
)

# Technical indicators
rsi_data = equity_model.calculate_measure('avg_rsi')
volatility = equity_model.calculate_measure('avg_volatility_20d')

# 4. Work with results
df = indices.data  # Get DataFrame
print(df.head())   # Display data
```

---

*Built with de_Funk domain model framework*
