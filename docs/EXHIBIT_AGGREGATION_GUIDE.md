# Exhibit Aggregation Guide

This guide explains how to use aggregation in exhibits to control how data is grouped and summarized in charts and tables.

## Overview

Exhibits support flexible aggregation through three configuration options:

1. **`aggregations`**: Dict of column → aggregation function (e.g., `{close: avg, volume: sum}`)
2. **`group_by`**: Columns to group by (e.g., `[trade_date]` or `[trade_date, ticker]`)
3. **`color_by`**: Visual dimension to split by (automatically added to group_by when aggregating)

## Aggregation Patterns

### Pattern 1: Aggregate Across All Tickers (Single Line)

**Use Case**: Show overall market trend by averaging all stocks together

```yaml
$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  aggregations:
    close: avg
  # No group_by specified - defaults to [trade_date] only
  # No color_by - produces single aggregated line
  title: "Average Market Close Price"
}
```

**SQL Equivalent**:
```sql
SELECT trade_date, AVG(close) as close
FROM equity.fact_equity_prices
GROUP BY trade_date
```

**Result**: One line showing the average close price across all tickers for each date

---

### Pattern 2: Split by Ticker (Multiple Lines)

**Use Case**: Show individual stock trends with each line averaged within that ticker

```yaml
$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  color_by: ticker
  aggregations:
    close: avg
  # group_by automatically becomes [trade_date, ticker] due to color_by
  title: "Stock Price Trends by Ticker"
}
```

**SQL Equivalent**:
```sql
SELECT trade_date, ticker, AVG(close) as close
FROM equity.fact_equity_prices
GROUP BY trade_date, ticker
```

**Result**: Multiple lines, one per ticker, each showing averaged values

---

### Pattern 3: Explicit Group By (Full Control)

**Use Case**: Group by specific dimensions regardless of chart configuration

```yaml
$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  color_by: sector  # Visual grouping
  aggregations:
    close: avg
  group_by: [trade_date, sector]  # Explicit grouping
  title: "Average Price by Sector"
}
```

**SQL Equivalent**:
```sql
SELECT trade_date, sector, AVG(close) as close
FROM equity.fact_equity_prices
GROUP BY trade_date, sector
```

**Result**: Multiple lines, one per sector, showing sector-averaged prices

---

### Pattern 4: Data Table Aggregation

**Use Case**: Summary statistics grouped by dimension

```yaml
$exhibits${
  type: data_table
  source: equity.fact_equity_prices
  columns: [ticker, close, volume, market_cap]
  aggregations:
    close: avg
    volume: sum
    market_cap: avg
  group_by: [ticker]
  order_by: [{column: market_cap, direction: desc}]
  limit: 20
  title: "Top 20 Stocks by Market Cap"
}
```

**SQL Equivalent**:
```sql
SELECT
  ticker,
  AVG(close) as close,
  SUM(volume) as volume,
  AVG(market_cap) as market_cap
FROM equity.fact_equity_prices
GROUP BY ticker
ORDER BY market_cap DESC
LIMIT 20
```

**Result**: Table with one row per ticker showing aggregated metrics

---

### Pattern 5: Portfolio/Index Aggregation

**Use Case**: Aggregate across tickers within a portfolio or index

```yaml
$exhibits${
  type: line_chart
  source: equity.fact_equity_prices_with_portfolio  # Joined with portfolio dimension
  x: trade_date
  y: close
  color_by: portfolio_name
  aggregations:
    close: avg
    volume: sum
  # group_by becomes [trade_date, portfolio_name] due to color_by
  title: "Portfolio Performance Comparison"
}
```

**SQL Equivalent**:
```sql
SELECT
  trade_date,
  portfolio_name,
  AVG(close) as close,
  SUM(volume) as volume
FROM equity.fact_equity_prices_with_portfolio
GROUP BY trade_date, portfolio_name
```

**Result**: Multiple lines, one per portfolio, showing aggregated metrics across all tickers in each portfolio

---

## Aggregation Functions

Supported aggregation functions in the `aggregations` dict:

| Function | Description | Common Use Cases |
|----------|-------------|------------------|
| `avg` | Average value | Prices, ratios, percentages |
| `sum` | Total sum | Volumes, counts, totals |
| `min` | Minimum value | Lowest price, floor values |
| `max` | Maximum value | Highest price, ceiling values |
| `count` | Count of rows | Number of trading days, occurrences |
| `stddev` | Standard deviation | Volatility, dispersion |
| `median` | Median value | Robust central tendency |

## Smart Defaults

When `aggregations` is specified but `group_by` is not:

1. **X-axis column** is automatically added to `group_by`
2. **`color_by` column** is automatically added to `group_by` (if specified)
3. **Result**: Aggregation happens at the right grain for the visualization

### Example: Smart Default Behavior

```yaml
$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  color_by: ticker
  aggregations:
    close: avg
  # No explicit group_by
  # Smart default: group_by = [trade_date, ticker]
}
```

This is equivalent to:

```yaml
$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  color_by: ticker
  aggregations:
    close: avg
  group_by: [trade_date, ticker]  # Explicit
}
```

## Common Use Cases

### Single Aggregated Line (Market Average)

```yaml
aggregations:
  close: avg
# Don't specify group_by or color_by
# Result: One line showing average across all tickers
```

### Multiple Lines (Per Ticker)

```yaml
aggregations:
  close: avg
color_by: ticker
# Smart default adds ticker to group_by
# Result: One line per ticker
```

### Multiple Lines (Per Portfolio/Index)

```yaml
aggregations:
  close: avg
  volume: sum
color_by: portfolio_name
group_by: [trade_date, portfolio_name]
# Result: One line per portfolio, aggregated across tickers
```

### Summary Table (Per Ticker)

```yaml
type: data_table
aggregations:
  close: avg
  volume: sum
  market_cap: avg
group_by: [ticker]
# Result: One row per ticker with aggregated metrics
```

## Troubleshooting

### Issue: Chart shows jumpy, noisy lines

**Cause**: Displaying raw unaggregated data (individual ticker values)

**Solution**: Add aggregations:
```yaml
aggregations:
  close: avg
```

### Issue: Only one line when I want multiple

**Cause**: Missing `color_by` or `group_by` for splitting

**Solution**: Add color_by to split by dimension:
```yaml
color_by: ticker
aggregations:
  close: avg
```

### Issue: Too many lines, want aggregated view

**Cause**: `color_by` is splitting into too many groups

**Solution**: Remove `color_by` or change to higher-level dimension:
```yaml
# Instead of color_by: ticker (100+ lines)
color_by: sector  # Fewer lines
aggregations:
  close: avg
```

### Issue: Aggregation not being applied

**Cause**: Missing `aggregations` field

**Solution**: Explicitly define aggregations:
```yaml
aggregations:
  close: avg
  volume: sum
```

## Debug Output

When exhibits use aggregation, you'll see debug output in the console:

```
📊 Using explicit aggregation config: group_by=['ticker'], aggregations={'close': 'avg', 'volume': 'sum'}
```

Or for smart defaults:

```
📊 Using smart default aggregation: group_by=['trade_date', 'ticker'], aggregations={'close': 'avg'}
```

This helps verify that aggregation is being applied correctly.
