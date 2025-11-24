# Stocks Facts

**Price and technical indicator schemas**

---

## fact_stock_prices

**Purpose**: Daily OHLCV price data

**Primary Key**: `[ticker, trade_date]`

**Partitions**: `trade_date`

**Extends**: `_base.securities._fact_prices`

**Record Count**: ~500K+ (depends on ticker count and history)

---

### Schema

#### Inherited Fields (from _base.securities)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `ticker` | string | Stock symbol (FK) | `AAPL` |
| `trade_date` | date | Trading date | `2024-01-15` |
| `open` | double | Opening price | `150.00` |
| `high` | double | High price | `152.00` |
| `low` | double | Low price | `149.00` |
| `close` | double | Closing price | `151.00` |
| `volume` | long | Trading volume | `50000000` |
| `volume_weighted` | double | Volume-weighted avg price | `150.75` |
| `transactions` | long | Number of transactions | `450000` |

#### Additional Fields

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `adjusted_close` | double | Split/dividend adjusted close | `151.00` |
| `dividend_amount` | double | Dividend paid (ex-date) | `0.24` |
| `split_coefficient` | double | Split ratio | `1.0` |

---

### Source Mapping

| Column | Bronze Source | Transformation |
|--------|---------------|----------------|
| `ticker` | securities_prices_daily.ticker | Direct |
| `trade_date` | securities_prices_daily.trade_date | Cast to date |
| `open` | securities_prices_daily.open | Cast to double |
| `high` | securities_prices_daily.high | Cast to double |
| `low` | securities_prices_daily.low | Cast to double |
| `close` | securities_prices_daily.close | Cast to double |
| `adjusted_close` | securities_prices_daily.adjusted_close | Cast to double |
| `volume` | securities_prices_daily.volume | Cast to long |

---

### Usage Examples

```sql
-- Get AAPL prices for 2024
SELECT trade_date, open, high, low, close, volume
FROM stocks.fact_stock_prices
WHERE ticker = 'AAPL'
  AND trade_date >= '2024-01-01'
ORDER BY trade_date

-- Daily returns
SELECT
    trade_date,
    close,
    (close - LAG(close) OVER (ORDER BY trade_date)) / LAG(close) OVER (ORDER BY trade_date) * 100 as daily_return
FROM stocks.fact_stock_prices
WHERE ticker = 'AAPL'

-- Volume analysis
SELECT
    ticker,
    AVG(volume) as avg_volume,
    MAX(volume) as max_volume
FROM stocks.fact_stock_prices
WHERE trade_date >= '2024-01-01'
GROUP BY ticker
```

---

## fact_stock_technicals

**Purpose**: Technical indicators derived from price data

**Primary Key**: `[ticker, trade_date]`

**Partitions**: `trade_date`

**Record Count**: Same as fact_stock_prices

---

### Schema

#### Identification

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `ticker` | string | Stock symbol (FK) | `AAPL` |
| `trade_date` | date | Trading date | `2024-01-15` |

#### Moving Averages

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `sma_20` | double | 20-day simple moving average | `148.50` |
| `sma_50` | double | 50-day simple moving average | `145.00` |
| `sma_200` | double | 200-day simple moving average | `140.00` |
| `ema_12` | double | 12-day exponential moving average | `149.00` |
| `ema_26` | double | 26-day exponential moving average | `147.50` |

#### Momentum Indicators

| Column | Type | Description | Range | Example |
|--------|------|-------------|-------|---------|
| `rsi_14` | double | 14-day Relative Strength Index | 0-100 | `65.5` |
| `macd` | double | MACD line (EMA12 - EMA26) | - | `1.50` |
| `macd_signal` | double | 9-day EMA of MACD | - | `1.20` |
| `macd_histogram` | double | MACD - Signal | - | `0.30` |

#### Volatility Indicators

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `volatility_20d` | double | 20-day annualized volatility | `0.25` |
| `volatility_60d` | double | 60-day annualized volatility | `0.22` |
| `bollinger_upper` | double | Upper Bollinger Band (2 std) | `155.00` |
| `bollinger_middle` | double | Middle band (20-day SMA) | `148.50` |
| `bollinger_lower` | double | Lower Bollinger Band (2 std) | `142.00` |
| `atr_14` | double | 14-day Average True Range | `3.50` |

#### Volume Indicators

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `volume_sma_20` | double | 20-day volume moving average | `45000000` |
| `volume_ratio` | double | Current volume / 20-day avg | `1.15` |
| `obv` | double | On-Balance Volume | `1500000000` |

#### Returns

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `daily_return` | double | Daily return percentage | `0.015` |

---

### Technical Indicator Formulas

#### RSI (Relative Strength Index)

```
RSI = 100 - (100 / (1 + RS))
RS = Average Gain / Average Loss (14-day)
```

**Interpretation**:
- RSI > 70: Overbought
- RSI < 30: Oversold

#### MACD

```
MACD Line = EMA(12) - EMA(26)
Signal Line = EMA(9) of MACD Line
Histogram = MACD Line - Signal Line
```

**Interpretation**:
- MACD > Signal: Bullish
- MACD < Signal: Bearish

#### Bollinger Bands

```
Middle Band = SMA(20)
Upper Band = SMA(20) + 2 * StdDev(20)
Lower Band = SMA(20) - 2 * StdDev(20)
```

**Interpretation**:
- Price near upper: Potentially overbought
- Price near lower: Potentially oversold

#### Volatility (Annualized)

```
Volatility = StdDev(daily_returns) * sqrt(252)
```

---

### Usage Examples

```sql
-- Stocks with RSI oversold
SELECT ticker, trade_date, rsi_14
FROM stocks.fact_stock_technicals
WHERE rsi_14 < 30
  AND trade_date = '2024-01-15'

-- MACD crossover signals
SELECT
    ticker,
    trade_date,
    macd,
    macd_signal,
    CASE
        WHEN macd > macd_signal THEN 'Bullish'
        ELSE 'Bearish'
    END as signal
FROM stocks.fact_stock_technicals
WHERE ticker = 'AAPL'
ORDER BY trade_date DESC
LIMIT 20

-- High volatility stocks
SELECT ticker, AVG(volatility_20d) as avg_vol
FROM stocks.fact_stock_technicals
WHERE trade_date >= '2024-01-01'
GROUP BY ticker
HAVING AVG(volatility_20d) > 0.4
ORDER BY avg_vol DESC
```

---

## Joins Between Facts

```sql
-- Combine prices with technicals
SELECT
    p.ticker,
    p.trade_date,
    p.close,
    t.rsi_14,
    t.macd,
    t.volatility_20d
FROM stocks.fact_stock_prices p
JOIN stocks.fact_stock_technicals t
    ON p.ticker = t.ticker AND p.trade_date = t.trade_date
WHERE p.ticker = 'AAPL'
ORDER BY p.trade_date DESC
```

---

## Related Documentation

- [Stocks Overview](overview.md)
- [Dimensions](dimensions.md)
- [Measures](measures.md)
