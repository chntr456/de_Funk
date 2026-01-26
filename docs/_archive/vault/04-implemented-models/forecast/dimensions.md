# Forecast Dimensions

**Forecast output schema**

---

## fact_forecasts

**Price and volume forecasts with confidence intervals**

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `ticker` | string | Stock ticker | `AAPL` |
| `target` | string | Target variable | `close` or `volume` |
| `forecast_date` | date | Date forecast was made | `2024-11-01` |
| `prediction_date` | date | Date being predicted | `2024-11-08` |
| `horizon` | int | Days ahead (1-30) | `7` |
| `model_name` | string | Model identifier | `ARIMA_7d` |
| `predicted_close` | double | Predicted price | `185.50` |
| `predicted_volume` | long | Predicted volume | `50000000` |
| `lower_bound` | double | Lower 95% CI | `180.00` |
| `upper_bound` | double | Upper 95% CI | `191.00` |
| `confidence` | double | Confidence level | `0.95` |

**Partitions**: `forecast_date`

---

## fact_forecast_metrics

**Forecast accuracy metrics**

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `ticker` | string | Stock ticker | `AAPL` |
| `model_name` | string | Model identifier | `ARIMA_7d` |
| `metric_date` | date | Evaluation date | `2024-11-01` |
| `training_start` | date | Training period start | `2024-01-01` |
| `training_end` | date | Training period end | `2024-10-01` |
| `test_start` | date | Test period start | `2024-10-02` |
| `test_end` | date | Test period end | `2024-10-31` |
| `mae` | double | Mean Absolute Error | `2.35` |
| `rmse` | double | Root Mean Squared Error | `3.12` |
| `mape` | double | Mean Absolute % Error | `0.0156` |
| `r2_score` | double | R-squared | `0.85` |
| `num_predictions` | int | Prediction count | `30` |
| `avg_error_pct` | double | Average error % | `0.0145` |

**Partitions**: `metric_date`

---

## fact_model_registry

**Registry of trained models**

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `model_id` | string | Unique model ID | `ARIMA_7d_AAPL_20241101` |
| `model_name` | string | Model name | `ARIMA_7d` |
| `model_type` | string | Algorithm type | `ARIMA` |
| `ticker` | string | Trained ticker | `AAPL` |
| `target_variable` | string | Target | `close` |
| `lookback_days` | int | Training lookback | `7` |
| `forecast_horizon` | int | Prediction horizon | `7` |
| `day_of_week_adj` | boolean | Day-of-week adjustment | `true` |
| `parameters` | string | JSON parameters | `{"p": 1, "d": 1, "q": 1}` |
| `trained_date` | date | Training date | `2024-11-01` |
| `training_samples` | int | Training samples | `252` |
| `status` | string | Model status | `active` |

**Partitions**: `trained_date`

---

## Graph Structure

### Edges

| From | To | Join |
|------|----|------|
| fact_forecasts | core.dim_calendar | prediction_date = date |
| fact_forecasts | equity.dim_equity | ticker = ticker |
| fact_forecast_metrics | core.dim_calendar | metric_date = date |

### Paths

| Path | Description |
|------|-------------|
| forecasts_with_calendar | Forecasts with calendar attributes |
| metrics_with_calendar | Metrics with calendar attributes |

---

## Usage Examples

```sql
-- Get latest forecasts for AAPL
SELECT
    prediction_date,
    model_name,
    predicted_close,
    lower_bound,
    upper_bound
FROM forecast.fact_forecasts
WHERE ticker = 'AAPL'
    AND forecast_date = CURRENT_DATE
ORDER BY prediction_date

-- Compare model accuracy
SELECT
    model_name,
    AVG(mae) as avg_mae,
    AVG(mape) as avg_mape,
    AVG(r2_score) as avg_r2
FROM forecast.fact_forecast_metrics
GROUP BY model_name
ORDER BY avg_mae
```

---

## Related Documentation

- [Overview](overview.md) - Model overview
- [Measures](measures.md) - Forecast measures
