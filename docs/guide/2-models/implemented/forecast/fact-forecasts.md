---
title: "Forecast Facts"
tags: [finance/forecast, component/model, concept/facts, concept/ml]
aliases: ["Forecast Facts", "forecast_price", "forecast_volume", "Predictions"]
---

# Forecast Facts

---

Machine learning-generated predictions for stock prices and trading volumes, including confidence intervals and horizon metadata.

**Tables:** `forecast_price`, `forecast_volume`
**Grain:** One row per ticker per forecast date per prediction date per model
**Storage:** `storage/silver/forecast/facts/`
**Partitioned By:** `forecast_date`

---

## Purpose

---

Forecast facts store ML model predictions to support backtesting, model comparison, and forward-looking analysis.

**Use Cases:**
- Price prediction
- Volume forecasting
- Model comparison
- Confidence interval analysis
- Backtesting strategies
- Risk assessment

---

## Price Forecasts Schema

---

**Table:** `forecast_price`
**Grain:** One row per ticker per forecast per prediction date per model

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **ticker** | string | Stock ticker | "AAPL" |
| **forecast_date** | date | Date forecast was made | 2024-11-08 |
| **prediction_date** | date | Date being predicted | 2024-11-15 |
| **horizon** | integer | Days ahead (1-30) | 7 |
| **model_name** | string | Model identifier | "ARIMA_30d" |
| **predicted_close** | double | Predicted closing price | 228.45 |
| **lower_bound** | double | 95% CI lower bound | 223.12 |
| **upper_bound** | double | 95% CI upper bound | 233.78 |
| **confidence** | double | Confidence level (0-1) | 0.95 |

**Partitioned By:** `forecast_date` (year-month)

---

## Volume Forecasts Schema

---

**Table:** `forecast_volume`
**Grain:** One row per ticker per forecast per prediction date per model

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **ticker** | string | Stock ticker | "AAPL" |
| **forecast_date** | date | Date forecast was made | 2024-11-08 |
| **prediction_date** | date | Date being predicted | 2024-11-15 |
| **horizon** | integer | Days ahead (1-30) | 7 |
| **model_name** | string | Model identifier | "Prophet_30d" |
| **predicted_volume** | long | Predicted trading volume | 52340000 |
| **lower_bound** | long | 95% CI lower bound | 45000000 |
| **upper_bound** | long | 95% CI upper bound | 60000000 |
| **confidence** | double | Confidence level (0-1) | 0.95 |

**Partitioned By:** `forecast_date` (year-month)

---

## Sample Data

---

### Price Forecasts

```
+--------+--------------+-----------------+---------+------------+-----------------+-------------+-------------+------------+
| ticker | forecast_date| prediction_date | horizon | model_name | predicted_close | lower_bound | upper_bound | confidence |
+--------+--------------+-----------------+---------+------------+-----------------+-------------+-------------+------------+
| AAPL   | 2024-11-08   | 2024-11-15      | 7       | ARIMA_30d  | 228.45          | 223.12      | 233.78      | 0.95       |
| AAPL   | 2024-11-08   | 2024-11-15      | 7       | Prophet_30d| 229.12          | 221.45      | 236.79      | 0.95       |
| AAPL   | 2024-11-08   | 2024-11-22      | 14      | ARIMA_30d  | 230.18          | 220.34      | 240.02      | 0.95       |
+--------+--------------+-----------------+---------+------------+-----------------+-------------+-------------+------------+
```

### Volume Forecasts

```
+--------+--------------+-----------------+---------+-------------+------------------+-------------+-------------+------------+
| ticker | forecast_date| prediction_date | horizon | model_name  | predicted_volume | lower_bound | upper_bound | confidence |
+--------+--------------+-----------------+---------+-------------+------------------+-------------+-------------+------------+
| AAPL   | 2024-11-08   | 2024-11-15      | 7       | Prophet_30d | 52340000         | 45000000    | 60000000    | 0.95       |
| AAPL   | 2024-11-08   | 2024-11-22      | 14      | Prophet_30d | 51200000         | 43000000    | 61000000    | 0.95       |
+--------+--------------+-----------------+---------+-------------+------------------+-------------+-------------+------------+
```

---

## Usage Examples

---

### Get Recent Forecasts

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get price forecasts
forecast = session.load_model('forecast')
price_forecasts = forecast.get_fact_df('forecast_price').to_pandas()

# Filter to recent forecasts for AAPL
aapl_recent = price_forecasts[
    (price_forecasts['ticker'] == 'AAPL') &
    (price_forecasts['forecast_date'] >= '2024-11-01')
]

print(aapl_recent.head())
```

### Compare Models for Same Horizon

```python
# Compare 7-day forecasts across models
horizon_7d = price_forecasts[
    (price_forecasts['ticker'] == 'AAPL') &
    (price_forecasts['horizon'] == 7) &
    (price_forecasts['forecast_date'] == '2024-11-08')
]

# Group by model
comparison = horizon_7d.groupby('model_name').agg({
    'predicted_close': 'mean',
    'lower_bound': 'mean',
    'upper_bound': 'mean'
}).reset_index()

print(comparison)
```

### Visualize Forecast Fan Chart

```python
import matplotlib.pyplot as plt

# Get all horizons for specific forecast date and model
forecast_snapshot = price_forecasts[
    (price_forecasts['ticker'] == 'AAPL') &
    (price_forecasts['forecast_date'] == '2024-11-08') &
    (price_forecasts['model_name'] == 'ARIMA_30d')
].sort_values('prediction_date')

# Historical prices for context
company = session.load_model('company')
prices = company.get_fact_df('fact_prices').to_pandas()
historical = prices[
    (prices['ticker'] == 'AAPL') &
    (prices['trade_date'] <= '2024-11-08') &
    (prices['trade_date'] >= '2024-10-01')
]

# Plot
fig, ax = plt.subplots(figsize=(12, 6))

# Historical
ax.plot(historical['trade_date'], historical['close'],
        label='Historical', linewidth=2, color='black')

# Forecast
ax.plot(forecast_snapshot['prediction_date'], forecast_snapshot['predicted_close'],
        label='Forecast', linewidth=2, color='blue', linestyle='--')

# Confidence interval
ax.fill_between(
    forecast_snapshot['prediction_date'],
    forecast_snapshot['lower_bound'],
    forecast_snapshot['upper_bound'],
    alpha=0.3,
    color='blue',
    label='95% Confidence Interval'
)

ax.set_title('AAPL Price Forecast - ARIMA 30d')
ax.set_xlabel('Date')
ax.set_ylabel('Price ($)')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
```

### Backtest Forecast Accuracy

```python
# Get forecasts that can be validated (prediction_date in past)
backtest = price_forecasts[
    price_forecasts['prediction_date'] <= '2024-11-08'
].copy()

# Merge with actual prices
actual_prices = prices[['trade_date', 'ticker', 'close']].rename(
    columns={'trade_date': 'prediction_date', 'close': 'actual_close'}
)

backtest = backtest.merge(actual_prices, on=['ticker', 'prediction_date'], how='inner')

# Calculate errors
backtest['error'] = backtest['predicted_close'] - backtest['actual_close']
backtest['abs_error'] = backtest['error'].abs()
backtest['pct_error'] = (backtest['error'] / backtest['actual_close']) * 100

# Summarize by model
by_model = backtest.groupby('model_name').agg({
    'abs_error': 'mean',
    'pct_error': 'mean',
    'error': 'std'
}).reset_index()

by_model.columns = ['model_name', 'mae', 'mape', 'std_error']

print("Backtest Results:")
print(by_model.sort_values('mape'))
```

### Volume Forecast Analysis

```python
# Get volume forecasts
volume_forecasts = forecast.get_fact_df('forecast_volume').to_pandas()

# Filter to specific ticker and date
aapl_volume = volume_forecasts[
    (volume_forecasts['ticker'] == 'AAPL') &
    (volume_forecasts['forecast_date'] == '2024-11-08')
].sort_values('prediction_date')

# Plot
plt.figure(figsize=(12, 6))
plt.plot(aapl_volume['prediction_date'], aapl_volume['predicted_volume'],
         marker='o', label='Predicted Volume')
plt.fill_between(
    aapl_volume['prediction_date'],
    aapl_volume['lower_bound'],
    aapl_volume['upper_bound'],
    alpha=0.3,
    label='95% CI'
)
plt.title('AAPL Volume Forecast')
plt.xlabel('Date')
plt.ylabel('Volume')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
```

---

## Relationships

---

### Foreign Keys

- **ticker** → [[Company Dimension]].ticker
- **forecast_date** → [[Calendar]].date
- **prediction_date** → [[Calendar]].date

### Related Tables

- **[[Forecast Metrics]]** - Model accuracy metrics
- **[[Model Registry]]** - Model metadata
- **[[Price Facts]]** - Historical data for validation

---

## Forecast Horizon

---

**Horizon:** Number of days ahead being predicted

**Available Horizons:**
- **1-7 days** - Short-term (high confidence)
- **8-14 days** - Medium-term (moderate confidence)
- **15-30 days** - Long-term (lower confidence)

**Confidence vs Horizon:**
- Shorter horizons = narrower confidence intervals
- Longer horizons = wider confidence intervals

---

## Confidence Intervals

---

**Level:** 95% (2 standard deviations)

**Interpretation:**
- 95% probability actual value falls within bounds
- Wider intervals = higher uncertainty
- Narrower intervals = higher confidence

**Calculation:**
```python
# Simplified confidence interval calculation
predicted = model.predict(X)
std_error = model.prediction_std()

lower_bound = predicted - 1.96 * std_error  # 95% CI
upper_bound = predicted + 1.96 * std_error
```

---

## Design Decisions

---

### Why separate price and volume tables?

**Decision:** Split price and volume forecasts into separate tables

**Rationale:**
- **Data types** - Volume is long int, price is double
- **Use cases** - Often analyzed separately
- **Query performance** - Smaller tables, faster scans
- **Schema clarity** - Explicit about target variable

### Why include horizon field?

**Decision:** Store days-ahead as separate column

**Rationale:**
- **Filtering** - Easy horizon-specific queries
- **Analysis** - Compare accuracy by horizon
- **Clarity** - Explicit prediction timeframe
- **Partitioning** - Potential future partitioning strategy

---

## Related Documentation

---

### Model Documentation
- [[Forecast Model Overview]] - Parent model
- [[Forecast Metrics]] - Accuracy metrics
- [[Model Registry]] - Trained models
- [[Forecast Model Types]] - Algorithm details

### Architecture Documentation
- [[Models System/ML]] - ML framework
- [[Silver Storage]] - Forecast storage

### Related Models
- [[Company Model]] - Training data
- [[Price Facts]] - Historical prices

---

**Tags:** #finance/forecast #component/model #concept/facts #concept/ml

**Last Updated:** 2024-11-08
**Tables:** forecast_price, forecast_volume
**Grain:** One row per ticker per forecast per prediction per model
