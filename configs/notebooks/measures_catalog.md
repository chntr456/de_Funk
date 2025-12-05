---
id: measures_catalog
title: Measures Catalog
description: A comprehensive catalog of all available measures across the de_Funk data models
tags: [measures, documentation, reference, catalog]
models: [company, equity, corporate, forecast, macro, city_finance, etf]
author: system
created: 2025-11-13
updated: 2025-11-13
---

# 📊 Measures Catalog

A comprehensive catalog of all available measures across the de_Funk data models.

---

## 🏢 Company Model Measures

The company model provides fundamental price, volume, and market metrics for public companies.

### Price & Valuation Measures

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **market_cap** | Market capitalization proxy (close × volume) | $#,##0.00 | avg | market, valuation, aggregate |
| **avg_close_price** | Average closing price | $#,##0.00 | avg | price, average |
| **total_volume** | Total trading volume | #,##0 | sum | volume, total |
| **avg_volume_weighted** | Average volume-weighted price | $#,##0.00 | avg | vwap, average |

### Volatility & Range Measures

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **price_volatility** | Price volatility (std dev) | $#,##0.00 | stddev | volatility, risk |
| **avg_high_price** | Average high price | $#,##0.00 | avg | price, high |
| **avg_low_price** | Average low price | $#,##0.00 | avg | price, low |
| **avg_daily_range** | Average daily price range (high - low) | $#,##0.00 | avg | range, volatility |

### Count Measures

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **company_count** | Number of distinct companies | #,##0 | count_distinct | count, companies |
| **news_article_count** | Number of news articles | #,##0 | count | news, count |
| **trading_days** | Number of trading days | #,##0 | count_distinct | calendar, count |

---

## 📈 Equity Model Measures

Advanced equity analytics including technical indicators and momentum measures.

### Price Measures

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **avg_close_price** | Average closing price | $#,##0.00 | avg | price, average |
| **total_volume** | Total trading volume | #,##0 | sum | volume, total |
| **avg_open_price** | Average opening price | $#,##0.00 | avg | price, average |
| **avg_high_price** | Average high price | $#,##0.00 | avg | price, high |
| **avg_low_price** | Average low price | $#,##0.00 | avg | price, low |

### Technical Indicators

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **avg_rsi** | Average Relative Strength Index | #,##0.00 | avg | technical, rsi |
| **avg_macd** | Average MACD | #,##0.00 | avg | technical, macd |
| **avg_bollinger_width** | Average Bollinger Band width | $#,##0.00 | avg | technical, volatility |

### Momentum & Returns

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **avg_daily_return** | Average daily return | 0.00% | avg | returns, daily |
| **total_return** | Total return over period | 0.00% | sum | returns, total |
| **sharpe_ratio** | Risk-adjusted return (Sharpe ratio) | #,##0.00 | avg | risk, sharpe |

---

## 🏦 Corporate Model Measures

Corporate actions, fundamentals, and company-level metrics.

### Company Metrics

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **company_count** | Number of companies | #,##0 | count | count, corporate |

### Future Fundamental Measures

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **avg_revenue** | Average revenue (Future) | $#,##0.00M | avg | financials, future |
| **avg_earnings** | Average earnings (Future) | $#,##0.00M | avg | financials, future |
| **avg_pe_ratio** | Average P/E ratio (Future) | #,##0.00x | avg | valuation, future |

---

## 🔮 Forecast Model Measures

Forecast accuracy metrics and model performance indicators.

### Accuracy Measures

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **avg_forecast_error** | Average forecast error (MAE) | $#,##0.00 | avg | error, accuracy |
| **avg_forecast_mape** | Average Mean Absolute Percentage Error | #,##0.00% | avg | error, percentage |
| **best_model_r2** | Best R-squared score across models | #,##0.0000 | max | accuracy, r2 |

### Model Performance

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **avg_rmse** | Average Root Mean Squared Error | $#,##0.00 | avg | error, rmse |
| **prediction_count** | Number of predictions | #,##0 | sum | count, predictions |
| **active_models** | Number of active models | #,##0 | count_distinct | models, active |

---

## 🌍 Macro Model Measures

Macroeconomic indicators and economic health metrics.

### Employment Measures

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **avg_unemployment_rate** | Average unemployment rate | #,##0.00% | avg | unemployment, average |
| **employment_growth** | Total employment growth | #,##0 | sum | employment, growth |

### Inflation Measures

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **latest_cpi** | Latest CPI value | #,##0.00 | max | cpi, latest |
| **avg_inflation_rate** | Average inflation rate | #,##0.00% | avg | inflation, average |

---

## 🏙️ City Finance Model Measures

Local government finance and urban development indicators.

### Economic Measures

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **avg_local_unemployment** | Average community area unemployment rate | #,##0.00% | avg | unemployment, average, local |

### Building & Development

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **total_permits_issued** | Total building permits issued | #,##0 | count | permits, count |
| **total_permit_fees** | Total permit fees collected | $#,##0.00 | sum | permits, revenue |
| **avg_construction_value** | Average construction value | $#,##0.00M | avg | construction, value |

---

## 📦 ETF Model Measures

Exchange-Traded Fund analytics and fund performance.

### Fund Metrics

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **avg_expense_ratio** | Average expense ratio across ETFs | 0.00% | avg | expense, average |
| **avg_etf_close** | Average ETF closing price | $#,##0.00 | avg | price, average |
| **avg_premium_discount** | Average premium/discount to NAV | 0.00% | avg | nav, premium |

### Volume & Liquidity

| Measure | Description | Format | Aggregation | Tags |
|---------|-------------|--------|-------------|------|
| **total_etf_volume** | Total ETF trading volume | #,##0 | sum | volume, total |
| **avg_daily_turnover** | Average daily turnover ratio | 0.00% | avg | liquidity, turnover |

---

## 🎯 Using Measures

### In DuckDB Queries

```sql
-- Example: Get average closing price by ticker
SELECT
    ticker,
    AVG(close) as avg_close_price
FROM stocks.fact_stock_prices
GROUP BY ticker
ORDER BY avg_close_price DESC
LIMIT 10;
```

### In Python with UniversalSession

```python
from models.api.session import UniversalSession

# Initialize session
session = UniversalSession(
    connection=spark,
    storage_cfg=storage_cfg,
    repo_root=Path.cwd()
)

# Get price data with measures
prices = session.get_table(
    'company',
    'fact_prices',
    required_columns=['ticker', 'close', 'volume'],
    group_by=['ticker'],
    aggregations={'close': 'avg', 'volume': 'sum'}
)
```

### In Streamlit

Measures are automatically available in the Metrics Explorer tab, allowing you to:
- Select any measure from any model
- Filter by date range, ticker, or other dimensions
- Visualize trends over time
- Compare across different segments

---

## 📝 Measure Metadata

### Aggregation Types

- **avg**: Average/mean value
- **sum**: Total/sum of values
- **count**: Count of records
- **count_distinct**: Count of unique values
- **max**: Maximum value
- **min**: Minimum value
- **stddev**: Standard deviation
- **first**: First value in group

### Format Patterns

- **$#,##0.00**: Currency with 2 decimals (e.g., $1,234.56)
- **#,##0**: Integer with thousands separator (e.g., 1,234)
- **#,##0.00%**: Percentage with 2 decimals (e.g., 12.34%)
- **0.00%**: Percentage (e.g., 0.75%)
- **#,##0.00x**: Ratio/multiple (e.g., 15.25x)
- **#,##0.00M**: Millions (e.g., 123.45M)

### Tags

Tags help categorize and filter measures:
- **price**: Price-related measures
- **volume**: Volume/quantity measures
- **volatility**: Risk and volatility indicators
- **returns**: Return metrics
- **technical**: Technical analysis indicators
- **fundamental**: Fundamental analysis metrics
- **forecast**: Forecast and prediction metrics
- **count**: Count-based measures

---

## 🔄 Cross-Model Measures

Some measures combine data from multiple models:

### Company × Forecast
- **forecast_vs_actual**: Compares predicted vs actual prices
- **prediction_accuracy**: Accuracy of forecasts by ticker

### Company × Macro
- **macro_adjusted_returns**: Returns adjusted for economic conditions
- **correlation_with_unemployment**: Price correlation with unemployment

### Equity × ETF
- **sector_momentum**: Combined equity and sector ETF momentum
- **relative_performance**: Individual stocks vs sector ETFs

---

## 📚 Additional Resources

- **Model Configs**: See `configs/models/*.yaml` for complete measure definitions
- **API Documentation**: Use `session.get_model_metadata(model_name)` for programmatic access
- **Measure Registry**: All measures are auto-discovered from model configs
- **Custom Measures**: Add new measures by editing model YAML files

---

*Last updated: 2025-11-13*
