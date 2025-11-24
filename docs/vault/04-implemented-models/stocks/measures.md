# Stocks Measures

**Pre-defined calculations for stock analysis**

---

## Measure Summary

| Type | Count | Source |
|------|-------|--------|
| Simple (YAML) | 8 | Inherited + stocks-specific |
| Computed (YAML) | 3 | Expression-based |
| Python | 6 | Complex calculations |
| **Total** | **17** | |

---

## Simple Measures (YAML)

Direct aggregations on single columns.

### Inherited from _base.securities

| Measure | Source | Aggregation | Description |
|---------|--------|-------------|-------------|
| `avg_close_price` | fact_stock_prices.close | AVG | Average closing price |
| `total_volume` | fact_stock_prices.volume | SUM | Total trading volume |
| `max_high` | fact_stock_prices.high | MAX | Maximum high price |
| `min_low` | fact_stock_prices.low | MIN | Minimum low price |
| `avg_vwap` | fact_stock_prices.volume_weighted | AVG | Average VWAP |
| `avg_daily_transactions` | fact_stock_prices.transactions | AVG | Average transactions |

### Stocks-Specific

| Measure | Source | Aggregation | Format | Description |
|---------|--------|-------------|--------|-------------|
| `avg_market_cap` | dim_stock.market_cap | AVG | $#,##0.00M | Average market cap |
| `total_market_cap` | dim_stock.market_cap | SUM | $#,##0.00B | Total market cap |
| `stock_count` | dim_stock.ticker | COUNT | #,##0 | Number of stocks |
| `avg_shares_outstanding` | dim_stock.shares_outstanding | AVG | #,##0.00M | Avg shares |
| `avg_rsi` | fact_stock_technicals.rsi_14 | AVG | #,##0.00 | Average RSI |
| `avg_volatility_20d` | fact_stock_technicals.volatility_20d | AVG | #,##0.00% | Avg 20d volatility |
| `avg_volatility_60d` | fact_stock_technicals.volatility_60d | AVG | #,##0.00% | Avg 60d volatility |
| `avg_volume_ratio` | fact_stock_technicals.volume_ratio | AVG | #,##0.00 | Avg volume ratio |

### Usage

```python
# Simple measure
result = model.calculate_measure(
    "avg_close_price",
    filters=[{"column": "ticker", "value": "AAPL"}]
)
```

---

## Computed Measures (YAML)

Expression-based calculations.

| Measure | Expression | Source Table | Description |
|---------|------------|--------------|-------------|
| `avg_dollar_volume` | `close * volume` | fact_stock_prices | Avg daily dollar volume |
| `market_cap_calculated` | `close * shares_outstanding` | fact_stock_prices + dim_stock | Calculated market cap |
| `daily_return_avg` | `(close - LAG(close)) / LAG(close) * 100` | fact_stock_prices | Average daily return % |

### Configuration

```yaml
computed_measures:
  avg_dollar_volume:
    type: computed
    expression: "close * volume"
    source_table: fact_stock_prices
    aggregation: avg
    format: "$#,##0.00M"
```

---

## Python Measures

Complex calculations requiring procedural logic.

### 1. sharpe_ratio

**Description**: Risk-adjusted return (annualized)

**Formula**:
```
Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns * sqrt(252)
```

**Parameters**:
| Param | Default | Description |
|-------|---------|-------------|
| `risk_free_rate` | 0.045 | Annual risk-free rate (4.5%) |
| `window_days` | 252 | Rolling window (1 year) |

**Usage**:
```python
sharpe = model.calculate_measure(
    "sharpe_ratio",
    ticker="AAPL",
    window_days=252,
    risk_free_rate=0.045
)
```

**Output**: DataFrame with `[ticker, trade_date, sharpe]`

---

### 2. correlation_matrix

**Description**: Correlation matrix of stock returns

**Parameters**:
| Param | Default | Description |
|-------|---------|-------------|
| `window_days` | 60 | Correlation window |
| `min_periods` | 30 | Minimum data points |

**Usage**:
```python
corr = model.calculate_measure(
    "correlation_matrix",
    tickers=["AAPL", "MSFT", "GOOGL"],
    window_days=60
)
```

**Output**: Correlation matrix DataFrame

---

### 3. momentum_score

**Description**: Multi-factor momentum score

**Formula**:
```
Score = w_rsi * RSI_norm + w_macd * MACD_norm + w_trend * Price_Trend
```

**Parameters**:
| Param | Default | Description |
|-------|---------|-------------|
| `weights.rsi` | 0.3 | RSI weight |
| `weights.macd` | 0.3 | MACD weight |
| `weights.price_trend` | 0.4 | Price trend weight |

**Usage**:
```python
momentum = model.calculate_measure(
    "momentum_score",
    ticker="AAPL"
)
```

**Output**: DataFrame with `[ticker, trade_date, momentum_score]`

---

### 4. sector_rotation_signal

**Description**: Sector rotation trading signal

**Parameters**:
| Param | Default | Description |
|-------|---------|-------------|
| `lookback_days` | 20 | Lookback period |
| `threshold` | 0.1 | Signal threshold (10%) |

**Usage**:
```python
signal = model.calculate_measure(
    "sector_rotation_signal",
    sectors=["Technology", "Healthcare"]
)
```

---

### 5. rolling_beta

**Description**: Rolling beta vs market index

**Formula**:
```
Beta = Cov(Stock Returns, Market Returns) / Var(Market Returns)
```

**Parameters**:
| Param | Default | Description |
|-------|---------|-------------|
| `market_ticker` | "SPY" | Market index ticker |
| `window_days` | 252 | Rolling window (1 year) |

**Usage**:
```python
beta = model.calculate_measure(
    "rolling_beta",
    ticker="AAPL",
    market_ticker="SPY",
    window_days=252
)
```

**Output**: DataFrame with `[ticker, trade_date, beta]`

---

### 6. drawdown

**Description**: Maximum drawdown from peak

**Formula**:
```
Drawdown = (Price - Peak) / Peak
Max Drawdown = MIN(Drawdown) over window
```

**Parameters**:
| Param | Default | Description |
|-------|---------|-------------|
| `window_days` | 252 | Window for peak calculation |

**Usage**:
```python
dd = model.calculate_measure(
    "drawdown",
    ticker="AAPL",
    window_days=252
)
```

**Output**: DataFrame with `[ticker, trade_date, drawdown, max_drawdown]`

---

## Python Implementation

**File**: `models/implemented/stocks/measures.py`

```python
class StocksMeasures:
    def __init__(self, model):
        self.model = model

    def calculate_sharpe_ratio(self, ticker=None, risk_free_rate=0.045, window_days=252, **kwargs):
        """Calculate rolling Sharpe ratio."""
        df = self.model.get_prices(ticker=ticker)
        df['returns'] = df['close'].pct_change()

        rolling_mean = df['returns'].rolling(window_days).mean()
        rolling_std = df['returns'].rolling(window_days).std()

        df['sharpe'] = (rolling_mean - risk_free_rate / 252) / rolling_std * np.sqrt(252)

        return df[['ticker', 'trade_date', 'sharpe']]
```

---

## Measure Discovery

```python
from models.api.registry import get_model_registry

registry = get_model_registry()
model = registry.get_model("stocks")

# List all measures
measures = model.list_measures()
for m in measures:
    print(f"{m['name']}: {m['type']} - {m['description']}")
```

---

## Related Documentation

- [Stocks Overview](overview.md)
- [Measure Framework](../../05-measure-framework/README.md)
- [Python Measures](../../05-measure-framework/python-measures.md)
