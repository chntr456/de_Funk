---
type: domain-model
model: forecast
version: 3.0
description: "Time series forecasting for securities prices and volumes"
tags: [forecast, ml, securities]

# Dependencies
depends_on: [temporal, stocks]

# Storage
storage:
  root: storage/silver/forecast
  format: delta

# Build
build:
  partitions: [forecast_date]
  sort_by: [security_id, forecast_date]
  optimize: true

# Tables
tables:
  fact_forecast_price:
    type: fact
    description: "Price forecast predictions"
    primary_key: [forecast_price_id]
    partition_by: [forecast_date]

    schema:
      # Keys - all integers
      - [forecast_price_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT(ticker, '_', model_name, '_', forecast_date, '_', prediction_date)))"}]
      - [security_id, integer, false, "FK to dim_security", {fk: stocks.dim_security.security_id}]
      - [date_id, integer, false, "FK to dim_calendar (forecast_date)", {fk: temporal.dim_calendar.date_id}]
      - [prediction_date_id, integer, false, "FK to dim_calendar (prediction_date)", {fk: temporal.dim_calendar.date_id}]

      # Forecast attributes
      - [ticker, string, false, "Stock ticker"]
      - [model_name, string, false, "Model identifier (e.g., arima_7d)"]
      - [horizon, integer, false, "Days ahead prediction"]
      - [predicted_close, double, false, "Predicted closing price"]
      - [lower_bound, double, true, "Lower confidence bound"]
      - [upper_bound, double, true, "Upper confidence bound"]
      - [confidence, double, true, "Confidence level (e.g., 0.95)", {default: 0.95}]

    measures:
      - [forecast_count, count_distinct, forecast_price_id, "Number of forecasts", {format: "#,##0"}]
      - [avg_predicted_close, avg, predicted_close, "Average predicted close", {format: "$#,##0.00"}]

  fact_forecast_volume:
    type: fact
    description: "Volume forecast predictions"
    primary_key: [forecast_volume_id]
    partition_by: [forecast_date]

    schema:
      - [forecast_volume_id, integer, false, "PK - Integer surrogate"]
      - [security_id, integer, false, "FK to dim_security", {fk: stocks.dim_security.security_id}]
      - [date_id, integer, false, "FK to dim_calendar (forecast_date)", {fk: temporal.dim_calendar.date_id}]
      - [prediction_date_id, integer, false, "FK to dim_calendar (prediction_date)", {fk: temporal.dim_calendar.date_id}]
      - [ticker, string, false, "Stock ticker"]
      - [model_name, string, false, "Model identifier"]
      - [horizon, integer, false, "Days ahead prediction"]
      - [predicted_volume, long, false, "Predicted trading volume"]
      - [lower_bound, long, true, "Lower confidence bound"]
      - [upper_bound, long, true, "Upper confidence bound"]
      - [confidence, double, true, "Confidence level", {default: 0.95}]

    measures:
      - [volume_forecast_count, count_distinct, forecast_volume_id, "Number of volume forecasts", {format: "#,##0"}]

  fact_forecast_metrics:
    type: fact
    description: "Forecast model accuracy metrics"
    primary_key: [metric_id]
    partition_by: [metric_date]

    schema:
      - [metric_id, integer, false, "PK - Integer surrogate"]
      - [security_id, integer, true, "FK to dim_security", {fk: stocks.dim_security.security_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [ticker, string, false, "Stock ticker"]
      - [model_name, string, false, "Model identifier"]
      - [mae, double, true, "Mean Absolute Error"]
      - [rmse, double, true, "Root Mean Square Error"]
      - [mape, double, true, "Mean Absolute Percentage Error"]
      - [r2_score, double, true, "R-squared score"]
      - [directional_accuracy, double, true, "Direction prediction accuracy %"]
      - [num_predictions, integer, true, "Number of predictions evaluated"]

    measures:
      - [avg_mape, avg, mape, "Average MAPE", {format: "#,##0.00%"}]
      - [avg_r2, avg, r2_score, "Average R2", {format: "#,##0.00"}]

  dim_model_registry:
    type: dimension
    description: "Trained model registry"
    primary_key: [registry_id]

    schema:
      - [registry_id, integer, false, "PK - Integer surrogate"]
      - [model_id, string, false, "Unique model identifier", {unique: true}]
      - [model_name, string, false, "Model name"]
      - [model_type, string, false, "Model type (ARIMA, Prophet, RandomForest)", {enum: [ARIMA, Prophet, RandomForest]}]
      - [ticker, string, false, "Stock ticker"]
      - [target_variable, string, false, "Target column (close, volume)"]
      - [lookback_days, integer, false, "Training window days"]
      - [forecast_horizon, integer, false, "Forecast horizon days"]
      - [parameters, string, true, "JSON-encoded model parameters"]
      - [trained_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [training_samples, integer, true, "Number of training samples"]
      - [status, string, false, "active or inactive", {enum: [active, inactive]}]

    measures:
      - [model_count, count_distinct, registry_id, "Number of models", {format: "#,##0"}]
      - [active_model_count, expression, "SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END)", "Active models", {format: "#,##0"}]

# ML Models Configuration
ml_models:
  arima_7d:
    type: arima
    target: [close]
    lookback_days: 60
    forecast_horizon: 7
    day_of_week_adj: true
    seasonal: false
    auto_arima: true

  arima_30d:
    type: arima
    target: [close]
    lookback_days: 180
    forecast_horizon: 30
    day_of_week_adj: true
    seasonal: true
    auto_arima: true

  prophet_7d:
    type: prophet
    target: [close]
    lookback_days: 90
    forecast_horizon: 7
    day_of_week_adj: true
    seasonality_mode: multiplicative

  prophet_30d:
    type: prophet
    target: [close]
    lookback_days: 365
    forecast_horizon: 30
    day_of_week_adj: true
    seasonality_mode: multiplicative

  random_forest_14d:
    type: random_forest
    target: [close]
    lookback_days: 90
    forecast_horizon: 14
    n_estimators: 100
    max_depth: 10

# Graph - Forecast doesn't load from bronze, it generates predictions
graph:
  nodes:
    fact_forecast_price:
      type: fact
      generated: true  # Not loaded from bronze
      primary_key: [forecast_price_id]
      tags: [fact, forecast, price]

    fact_forecast_volume:
      type: fact
      generated: true
      primary_key: [forecast_volume_id]
      tags: [fact, forecast, volume]

    fact_forecast_metrics:
      type: fact
      generated: true
      primary_key: [metric_id]
      tags: [fact, forecast, metrics]

    dim_model_registry:
      type: dimension
      generated: true
      primary_key: [registry_id]
      tags: [dim, forecast, registry]

  edges:
    forecast_price_to_security:
      from: fact_forecast_price
      to: stocks.dim_security
      on: [security_id=security_id]
      type: many_to_one

    forecast_price_to_calendar:
      from: fact_forecast_price
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one

    forecast_volume_to_security:
      from: fact_forecast_volume
      to: stocks.dim_security
      on: [security_id=security_id]
      type: many_to_one

    metrics_to_security:
      from: fact_forecast_metrics
      to: stocks.dim_security
      on: [security_id=security_id]
      type: many_to_one

# Metadata
metadata:
  domain: securities
  owner: data_engineering
  sla_hours: 12
status: active
---

## Forecast Model

Time series forecasting for securities using ARIMA, Prophet, and Random Forest models.

### Integer Keys

| Key | Type | Derivation |
|-----|------|------------|
| `forecast_price_id` | integer | `HASH(ticker + model + dates)` |
| `security_id` | integer | `HASH(ticker)` |
| `date_id` | integer | `YYYYMMDD` format |

### Supported Models

| Model | Use Case | Horizon |
|-------|----------|---------|
| `arima_7d` | Short-term price | 7 days |
| `arima_30d` | Medium-term price | 30 days |
| `prophet_7d` | Short-term with seasonality | 7 days |
| `prophet_30d` | Medium-term with seasonality | 30 days |
| `random_forest_14d` | Feature-based | 14 days |

### Query Pattern

```sql
-- Get latest forecasts with historical accuracy
SELECT
    f.ticker,
    f.model_name,
    f.prediction_date,
    f.predicted_close,
    f.lower_bound,
    f.upper_bound,
    m.mape,
    m.r2_score
FROM fact_forecast_price f
JOIN fact_forecast_metrics m ON f.ticker = m.ticker
    AND f.model_name = m.model_name
WHERE f.forecast_date = CURRENT_DATE
ORDER BY f.ticker, f.horizon
```

### Notes

- Forecasts are generated by ML models, not loaded from bronze
- Requires stocks model to be built first (for price data)
- Metrics calculated on holdout validation data
- Model registry tracks trained models and parameters
