# Forecast Measures

**Forecast accuracy calculations**

---

## Overview

The forecast model provides 3 measures for evaluating forecast accuracy.

---

## Simple Measures

### avg_forecast_error

**Average forecast error (MAE)**

| Property | Value |
|----------|-------|
| Source | `fact_forecast_metrics.mae` |
| Aggregation | `avg` |
| Data Type | double |
| Format | `$#,##0.00` |

**Usage**:
```python
model.calculate_measure("avg_forecast_error")
```

**Interpretation**: Lower is better. Average absolute difference between predicted and actual values.

---

### avg_forecast_mape

**Average Mean Absolute Percentage Error**

| Property | Value |
|----------|-------|
| Source | `fact_forecast_metrics.mape` |
| Aggregation | `avg` |
| Data Type | double |
| Format | `#,##0.00%` |

**Usage**:
```python
model.calculate_measure("avg_forecast_mape")
```

**Interpretation**: Lower is better. Expressed as percentage for interpretability.

---

### best_model_r2

**Best R-squared score across models**

| Property | Value |
|----------|-------|
| Source | `fact_forecast_metrics.r2_score` |
| Aggregation | `max` |
| Data Type | double |
| Format | `#,##0.0000` |

**Usage**:
```python
model.calculate_measure("best_model_r2")
```

**Interpretation**: Higher is better. Range 0-1, where 1 is perfect fit.

---

## Metric Comparison

| Metric | Range | Best | Use Case |
|--------|-------|------|----------|
| MAE | 0 - ∞ | 0 | Absolute error comparison |
| RMSE | 0 - ∞ | 0 | Penalizes large errors |
| MAPE | 0% - 100%+ | 0% | Percentage-based comparison |
| R² | -∞ - 1 | 1 | Model fit quality |

---

## Usage Examples

```python
from models.api.registry import get_model_registry

registry = get_model_registry()
model = registry.get_model("forecast")

# Average error across all models
error = model.calculate_measure("avg_forecast_error")

# Best performing model
best_r2 = model.calculate_measure("best_model_r2")

# Filter by ticker
aapl_error = model.calculate_measure(
    "avg_forecast_error",
    filters=[{"column": "ticker", "value": "AAPL"}]
)

# Filter by model type
arima_mape = model.calculate_measure(
    "avg_forecast_mape",
    filters=[{"column": "model_name", "operator": "like", "value": "ARIMA%"}]
)
```

---

## Model Selection Guide

| Scenario | Recommended Metric | Threshold |
|----------|-------------------|-----------|
| Short-term trading | MAE | < $2.00 |
| Long-term planning | MAPE | < 5% |
| Model comparison | R² | > 0.80 |
| High volatility | RMSE | Context-dependent |

---

## Related Documentation

- [Overview](overview.md) - Model overview
- [Dimensions](dimensions.md) - Schema details
