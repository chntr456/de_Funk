---
title: "Forecast Metrics"
tags: [finance/forecast, component/model, concept/metrics, concept/ml]
aliases: ["Forecast Metrics", "forecast_metrics", "Model Accuracy", "Error Metrics"]
---

# Forecast Metrics

---

Model accuracy and error metrics for evaluating forecast performance, including MAE, RMSE, MAPE, and R² scores.

**Table:** `forecast_metrics`
**Grain:** One row per ticker per model per evaluation period
**Storage:** `storage/silver/forecast/facts/forecast_metrics`
**Partitioned By:** `metric_date`

---

## Purpose

---

Forecast metrics track model performance over time, enabling model comparison, accuracy monitoring, and automated model selection.

**Use Cases:**
- Model performance comparison
- Accuracy monitoring
- Model selection
- Performance degradation detection
- Training/test set validation

---

## Schema

---

**Grain:** One row per ticker per model per evaluation period

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **ticker** | string | Stock ticker | "AAPL" |
| **model_name** | string | Model identifier | "ARIMA_30d" |
| **metric_date** | date | Evaluation date | 2024-11-08 |
| **training_start** | date | Training period start | 2024-01-01 |
| **training_end** | date | Training period end | 2024-10-31 |
| **test_start** | date | Test period start | 2024-11-01 |
| **test_end** | date | Test period end | 2024-11-08 |
| **mae** | double | Mean Absolute Error | 2.34 |
| **rmse** | double | Root Mean Squared Error | 3.12 |
| **mape** | double | Mean Absolute Percentage Error | 1.02 |
| **r2_score** | double | R-squared score | 0.87 |
| **num_predictions** | integer | Number of test predictions | 156 |
| **avg_error_pct** | double | Average error percentage | 1.15 |

**Partitioned By:** `metric_date` (year-month)

---

## Sample Data

---

```
+--------+---------------+-------------+----------------+--------------+------------+----------+------+------+------+----------+-----------------+--------------+
| ticker | model_name    | metric_date | training_start | training_end | test_start | test_end | mae  | rmse | mape | r2_score | num_predictions | avg_error_pct|
+--------+---------------+-------------+----------------+--------------+------------+----------+------+------+------+----------+-----------------+--------------+
| AAPL   | ARIMA_30d     | 2024-11-08  | 2024-01-01     | 2024-10-31   | 2024-11-01 |2024-11-08| 2.34 | 3.12 | 1.02 | 0.87     | 156             | 1.15         |
| AAPL   | Prophet_30d   | 2024-11-08  | 2024-01-01     | 2024-10-31   | 2024-11-01 |2024-11-08| 2.89 | 3.67 | 1.26 | 0.82     | 156             | 1.38         |
| AAPL   | RandomForest_14d|2024-11-08  | 2024-01-01     | 2024-10-31   | 2024-11-01 |2024-11-08| 3.12 | 4.01 | 1.35 | 0.79     | 156             | 1.42         |
+--------+---------------+-------------+----------------+--------------+------------+----------+------+------+------+----------+-----------------+--------------+
```

---

## Usage Examples

---

### Get Model Metrics

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get forecast metrics
forecast = session.load_model('forecast')
metrics = forecast.get_fact_df('forecast_metrics').to_pandas()

# Filter to AAPL
aapl_metrics = metrics[metrics['ticker'] == 'AAPL']

print(aapl_metrics[['model_name', 'mae', 'rmse', 'mape', 'r2_score']].sort_values('mape'))
```

### Compare Model Performance

```python
# Pivot to compare models side-by-side
comparison = aapl_metrics.pivot_table(
    index='model_name',
    values=['mae', 'rmse', 'mape', 'r2_score'],
    aggfunc='mean'
).reset_index()

print("Model Performance Comparison:")
print(comparison.sort_values('mape'))

# Best model by metric
print(f"\nBest MAE: {comparison.loc[comparison['mae'].idxmin(), 'model_name']}")
print(f"Best MAPE: {comparison.loc[comparison['mape'].idxmin(), 'model_name']}")
print(f"Best R²: {comparison.loc[comparison['r2_score'].idxmax(), 'model_name']}")
```

### Track Performance Over Time

```python
import matplotlib.pyplot as plt

# Track ARIMA_30d performance over time
arima_metrics = metrics[
    (metrics['ticker'] == 'AAPL') &
    (metrics['model_name'] == 'ARIMA_30d')
].sort_values('metric_date')

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# MAE
axes[0, 0].plot(arima_metrics['metric_date'], arima_metrics['mae'], marker='o')
axes[0, 0].set_title('Mean Absolute Error (MAE)')
axes[0, 0].set_ylabel('Error ($)')
axes[0, 0].grid(True, alpha=0.3)

# RMSE
axes[0, 1].plot(arima_metrics['metric_date'], arima_metrics['rmse'], marker='o', color='orange')
axes[0, 1].set_title('Root Mean Squared Error (RMSE)')
axes[0, 1].set_ylabel('Error ($)')
axes[0, 1].grid(True, alpha=0.3)

# MAPE
axes[1, 0].plot(arima_metrics['metric_date'], arima_metrics['mape'], marker='o', color='green')
axes[1, 0].set_title('Mean Absolute Percentage Error (MAPE)')
axes[1, 0].set_ylabel('Error (%)')
axes[1, 0].grid(True, alpha=0.3)

# R²
axes[1, 1].plot(arima_metrics['metric_date'], arima_metrics['r2_score'], marker='o', color='red')
axes[1, 1].set_title('R-squared Score')
axes[1, 1].set_ylabel('R² Score')
axes[1, 1].grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
```

### Automated Model Selection

```python
# Select best model for each ticker based on MAPE
best_models = metrics.loc[metrics.groupby('ticker')['mape'].idxmin()]

print("Best Model by Ticker:")
print(best_models[['ticker', 'model_name', 'mape', 'r2_score']])
```

### Detect Performance Degradation

```python
# Check if recent performance has degraded
recent = metrics[metrics['metric_date'] >= '2024-10-01']
historical = metrics[metrics['metric_date'] < '2024-10-01']

recent_avg = recent.groupby('model_name')['mape'].mean()
historical_avg = historical.groupby('model_name')['mape'].mean()

degradation = ((recent_avg - historical_avg) / historical_avg * 100).reset_index()
degradation.columns = ['model_name', 'mape_increase_pct']

print("Performance Degradation:")
print(degradation[degradation['mape_increase_pct'] > 10])  # >10% worse
```

---

## Relationships

---

### Foreign Keys

- **ticker** → [[Company Dimension]].ticker
- **metric_date** → [[Calendar]].date

### Related Tables

- **[[Forecast Facts]]** - Predictions being evaluated
- **[[Model Registry]]** - Model metadata
- **[[Price Facts]]** - Actual values for comparison

---

## Error Metrics

---

### Mean Absolute Error (MAE)

**Formula:** `MAE = (1/n) × Σ|predicted - actual|`

**Interpretation:**
- Average magnitude of errors
- Same units as target variable (dollars, shares)
- Lower is better

**Use Case:** Understanding typical prediction error

---

### Root Mean Squared Error (RMSE)

**Formula:** `RMSE = √[(1/n) × Σ(predicted - actual)²]`

**Interpretation:**
- Penalizes large errors more than MAE
- Same units as target variable
- Lower is better

**Use Case:** When large errors are particularly undesirable

---

### Mean Absolute Percentage Error (MAPE)

**Formula:** `MAPE = (1/n) × Σ|predicted - actual| / |actual| × 100`

**Interpretation:**
- Error as percentage of actual value
- Scale-independent (comparable across stocks)
- Lower is better

**Use Case:** Comparing accuracy across different price ranges

---

### R-squared (R²)

**Formula:** `R² = 1 - (SS_residual / SS_total)`

**Interpretation:**
- Proportion of variance explained (0 to 1)
- 1 = perfect fit, 0 = no better than mean
- Higher is better

**Use Case:** Goodness of fit assessment

---

## Typical Performance Benchmarks

---

### Price Forecasts

**Good Performance:**
- MAPE < 2% (very good)
- MAPE 2-5% (good)
- R² > 0.8 (strong fit)

**Acceptable Performance:**
- MAPE 5-10% (acceptable)
- R² 0.5-0.8 (moderate fit)

**Poor Performance:**
- MAPE > 10% (poor)
- R² < 0.5 (weak fit)

---

## Design Decisions

---

### Why track training/test periods?

**Decision:** Store training and test date ranges

**Rationale:**
- **Reproducibility** - Understand evaluation context
- **Validation** - Ensure no data leakage
- **Comparison** - Compare metrics across consistent periods
- **Debugging** - Identify time-specific issues

### Why include num_predictions?

**Decision:** Track number of predictions in test set

**Rationale:**
- **Statistical significance** - More predictions = more reliable metrics
- **Context** - Understand sample size
- **Validation** - Ensure sufficient test data
- **Debugging** - Identify incomplete evaluations

---

## Related Documentation

---

### Model Documentation
- [[Forecast Model Overview]] - Parent model
- [[Forecast Facts]] - Predictions
- [[Model Registry]] - Model metadata
- [[Forecast Model Types]] - Algorithm details

### Architecture Documentation
- [[Models System/ML]] - ML framework
- [[Silver Storage]] - Metrics storage

---

**Tags:** #finance/forecast #component/model #concept/metrics #concept/ml

**Last Updated:** 2024-11-08
**Table:** forecast_metrics
**Grain:** One row per ticker per model per evaluation period
