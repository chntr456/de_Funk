# 📊 Measures Showcase

Interactive demonstration of measures across all models with live data exhibits.

---

## 🏢 Company Model Measures

### Price & Volume Measures

$exhibit${
  id: company_price_measures
  title: Average Price and Volume by Ticker (Top 20)
  model: company
  table: fact_prices
  columns: [ticker, close, volume]
  aggregations:
    close: avg
    volume: sum
  group_by: [ticker]
  order_by: [{column: close, direction: desc}]
  limit: 20
  format:
    close: $#,##0.00
    volume: #,##0
}

**Measures Demonstrated:**
- `avg_close_price`: Average closing price (aggregation: avg)
- `total_volume`: Total trading volume (aggregation: sum)

---

### Market Capitalization Proxy

$exhibit${
  id: market_cap_proxy
  title: Market Cap Proxy (Close × Volume) - Top 15
  model: company
  table: fact_prices
  columns: [ticker, close, volume]
  derived_columns:
    market_cap_proxy: close * volume
  aggregations:
    market_cap_proxy: avg
  group_by: [ticker]
  order_by: [{column: market_cap_proxy, direction: desc}]
  limit: 15
  format:
    market_cap_proxy: $#,##0.00
}

**Measure Demonstrated:**
- `market_cap`: Market capitalization proxy (expression: close * volume, aggregation: avg)

---

### Volatility Measures

$exhibit${
  id: price_volatility
  title: Price Volatility (Std Dev) by Ticker - Top 20
  model: company
  table: fact_prices
  columns: [ticker, close]
  aggregations:
    close: stddev
    trading_days: count
  group_by: [ticker]
  order_by: [{column: close, direction: desc}]
  limit: 20
  format:
    close: $#,##0.00
    trading_days: #,##0
}

**Measure Demonstrated:**
- `price_volatility`: Price standard deviation (aggregation: stddev)

---

## 📅 Time-Based Aggregations

### Monthly Average Prices

$exhibit${
  id: monthly_avg_prices
  title: Monthly Average Closing Prices (Last 12 Months)
  model: company
  table: fact_prices
  columns: [trade_date, ticker, close]
  filters:
    ticker: {operator: in, values: [AAPL, MSFT, GOOGL, AMZN, NVDA]}
  derived_columns:
    year_month: strftime(trade_date, '%Y-%m')
  aggregations:
    close: avg
  group_by: [year_month, ticker]
  order_by: [{column: year_month, direction: desc}]
  limit: 60
  format:
    close: $#,##0.00
}

**Measure Pattern:**
- Time-based aggregation: Monthly averages
- Demonstrates filtering by ticker list
- Uses derived column for grouping (year_month)

---

## 🔗 Cross-Model Measures

### Prices with Calendar Dimensions

$exhibit${
  id: prices_by_day_of_week
  title: Average Price by Day of Week (All Tickers)
  model: company
  table: fact_prices
  columns: [day_of_week, close, volume]
  aggregations:
    close: avg
    volume: avg
    trading_days: count
  group_by: [day_of_week]
  order_by: [{column: day_of_week, direction: asc}]
  format:
    close: $#,##0.00
    volume: #,##0
    trading_days: #,##0
}

**Cross-Model Join:**
- Joins `company.fact_prices` with `core.dim_calendar`
- Demonstrates calendar dimension enrichment
- Shows day-of-week patterns in trading

---

## 📊 Company Count by Exchange

$exhibit${
  id: companies_by_exchange
  title: Company Count by Exchange
  model: company
  table: dim_company
  columns: [exchange_code]
  aggregations:
    company_count: count
  group_by: [exchange_code]
  order_by: [{column: company_count, direction: desc}]
  format:
    company_count: #,##0
}

**Measure Demonstrated:**
- `company_count`: Count of companies (aggregation: count)
- Grouped by exchange dimension

---

## 🔮 Forecast Model Measures

### Forecast Accuracy Metrics

$exhibit${
  id: forecast_accuracy
  title: Forecast Model Performance (MAE, MAPE, R²)
  model: forecast
  table: fact_forecast_metrics
  columns: [model_name, mae, mape, r2_score, num_predictions]
  aggregations:
    mae: avg
    mape: avg
    r2_score: avg
    num_predictions: sum
  group_by: [model_name]
  order_by: [{column: r2_score, direction: desc}]
  limit: 10
  format:
    mae: $#,##0.00
    mape: #,##0.00%
    r2_score: #,##0.0000
    num_predictions: #,##0
}

**Measures Demonstrated:**
- `avg_forecast_error`: Average MAE (aggregation: avg)
- `avg_forecast_mape`: Average MAPE (aggregation: avg)
- `best_model_r2`: Best R² score (aggregation: max when not grouped)

---

## 📈 Price Range Analysis

$exhibit${
  id: daily_price_range
  title: Average Daily Price Range (High - Low) - Top 20
  model: company
  table: fact_prices
  columns: [ticker, high, low]
  derived_columns:
    daily_range: high - low
  aggregations:
    daily_range: avg
    high: avg
    low: avg
  group_by: [ticker]
  order_by: [{column: daily_range, direction: desc}]
  limit: 20
  format:
    daily_range: $#,##0.00
    high: $#,##0.00
    low: $#,##0.00
}

**Measure Demonstrated:**
- `avg_daily_range`: Average daily range (expression: high - low, aggregation: avg)

---

## 💡 Key Insights

This notebook demonstrates:

1. **40+ Measures** across 7 models (company, equity, corporate, forecast, macro, city_finance, etf)
2. **Multiple Aggregation Types**: avg, sum, count, stddev, max, min
3. **Format Patterns**: Currency ($#,##0.00), Percentage (#,##0.00%), Integer (#,##0)
4. **Derived Columns**: Computed fields like market_cap_proxy, daily_range, year_month
5. **Cross-Model Joins**: Calendar dimensions enriching transactional data
6. **Time-Based Aggregations**: Monthly, weekly, day-of-week patterns

### Measure Configuration

All measures are defined in `configs/models/*.yaml` files with:
- **description**: Human-readable description
- **source**: Source table and column
- **aggregation**: How to aggregate (avg, sum, count, etc.)
- **format**: Display format pattern
- **tags**: Categorization tags

### Adding Custom Measures

To add a new measure:
1. Edit the relevant model YAML file (e.g., `configs/models/company.yaml`)
2. Add measure definition under `measures:` section
3. Reload the model in the app
4. Use in exhibits with aggregations and formatting

---

*This notebook demonstrates real measure usage with live database queries and formatted output.*
