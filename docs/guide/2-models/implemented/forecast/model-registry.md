---
title: "Model Registry"
tags: [finance/forecast, component/model, concept/ml, concept/registry]
aliases: ["Model Registry", "model_registry", "Trained Models", "ML Registry"]
---

# Model Registry

---

Registry of trained forecast models with metadata, parameters, and training information for model management and reproducibility.

**Table:** `model_registry`
**Grain:** One row per trained model instance
**Storage:** `storage/silver/forecast/facts/model_registry`
**Partitioned By:** `trained_date`

---

## Purpose

---

The model registry tracks all trained models, enabling model versioning, parameter tracking, and model lifecycle management.

**Use Cases:**
- Model versioning
- Parameter tracking
- Training audit trail
- Model deployment selection
- Performance comparison
- Reproducibility

---

## Schema

---

**Grain:** One row per trained model

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **model_id** | string | Unique model identifier | "aapl_arima_30d_20241108" |
| **model_name** | string | Human-readable name | "ARIMA_30d" |
| **model_type** | string | Algorithm type | "ARIMA" |
| **ticker** | string | Stock ticker | "AAPL" |
| **target_variable** | string | Prediction target | "close" |
| **lookback_days** | integer | Training window (days) | 30 |
| **forecast_horizon** | integer | Prediction horizon (days) | 7 |
| **day_of_week_adj** | boolean | Day-of-week adjustment | true |
| **parameters** | string | JSON model parameters | '{"p": 2, "d": 1, "q": 2}' |
| **trained_date** | date | Model training date | 2024-11-08 |
| **training_samples** | integer | Number of training samples | 850 |
| **status** | string | Model status | "active" |

**Partitioned By:** `trained_date` (year-month)

---

## Sample Data

---

```
+------------------------+--------------+------------+--------+-----------------+--------------+------------------+-----------------+-------------------+-------------+------------------+--------+
| model_id               | model_name   | model_type | ticker | target_variable | lookback_days| forecast_horizon | day_of_week_adj | parameters        | trained_date| training_samples | status |
+------------------------+--------------+------------+--------+-----------------+--------------+------------------+-----------------+-------------------+-------------+------------------+--------+
| aapl_arima_30d_20241108| ARIMA_30d    | ARIMA      | AAPL   | close           | 30           | 7                | true            | {"p":2,"d":1,"q":2}| 2024-11-08  | 850              | active |
| aapl_prophet_30d_...   | Prophet_30d  | Prophet    | AAPL   | close           | 30           | 7                | true            | {"seasonality":...}| 2024-11-08  | 850              | active |
| msft_arima_30d_...     | ARIMA_30d    | ARIMA      | MSFT   | close           | 30           | 7                | true            | {"p":1,"d":1,"q":1}| 2024-11-08  | 850              | active |
+------------------------+--------------+------------+--------+-----------------+--------------+------------------+-----------------+-------------------+-------------+------------------+--------+
```

---

## Usage Examples

---

### Get All Active Models

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get model registry
forecast = session.load_model('forecast')
registry = forecast.get_fact_df('model_registry').to_pandas()

# Filter to active models
active_models = registry[registry['status'] == 'active']

print(active_models[['model_id', 'ticker', 'model_type', 'trained_date']])
```

### Find Best Model for Ticker

```python
# Get metrics
metrics = forecast.get_fact_df('forecast_metrics').to_pandas()

# Join with registry to get full model info
merged = metrics.merge(
    registry[['model_name', 'ticker', 'model_id', 'parameters']],
    on=['model_name', 'ticker'],
    how='inner'
)

# Find best by MAPE
best_aapl = merged[merged['ticker'] == 'AAPL'].nsmallest(1, 'mape')

print("Best Model for AAPL:")
print(best_aapl[['model_id', 'model_type', 'mape', 'r2_score']])
```

### Compare Parameters Across Models

```python
import json

# Parse JSON parameters
registry['params_dict'] = registry['parameters'].apply(json.loads)

# Filter to ARIMA models
arima_models = registry[registry['model_type'] == 'ARIMA']

# Extract ARIMA parameters
for idx, row in arima_models.iterrows():
    params = row['params_dict']
    print(f"{row['ticker']} - ARIMA({params.get('p', 'auto')}, "
          f"{params.get('d', 'auto')}, {params.get('q', 'auto')})")
```

### Track Model Training History

```python
# Training frequency by ticker
training_history = registry.groupby(['ticker', registry['trained_date'].dt.to_period('M')]).agg({
    'model_id': 'count'
}).reset_index()

training_history.columns = ['ticker', 'month', 'models_trained']

print("Training History:")
print(training_history.tail(10))
```

### Archive Old Models

```python
# Mark models older than 90 days as archived
from datetime import datetime, timedelta

cutoff_date = datetime.now() - timedelta(days=90)

old_models = registry[
    (registry['trained_date'] < cutoff_date) &
    (registry['status'] == 'active')
]

print(f"Models to archive: {len(old_models)}")
print(old_models[['model_id', 'ticker', 'trained_date']])

# In practice, update status in database
# UPDATE model_registry SET status = 'archived' WHERE ...
```

---

## Relationships

---

### Foreign Keys

- **ticker** → [[Company Dimension]].ticker
- **trained_date** → [[Calendar]].date

### Used By

- **[[Forecast Facts]]** - References model_name
- **[[Forecast Metrics]]** - References model_name

---

## Model Types and Parameters

---

### ARIMA Parameters

**JSON Structure:**
```json
{
  "p": 2,           // Autoregressive order
  "d": 1,           // Differencing order
  "q": 2,           // Moving average order
  "seasonal": false,
  "auto_arima": true
}
```

---

### Prophet Parameters

**JSON Structure:**
```json
{
  "seasonality_mode": "multiplicative",
  "include_holidays": true,
  "changepoint_prior_scale": 0.05,
  "yearly_seasonality": true,
  "weekly_seasonality": true
}
```

---

### Random Forest Parameters

**JSON Structure:**
```json
{
  "n_estimators": 100,
  "max_depth": 10,
  "min_samples_split": 2,
  "features": ["lag_1", "lag_7", "rolling_mean_7", "day_of_week"]
}
```

---

## Model Status Values

---

### Active

Model is currently in use for predictions

**Use:** Production forecasts

---

### Archived

Model is no longer in active use but retained for history

**Use:** Historical reference, reproducibility

---

### Experimental

Model is under development or testing

**Use:** Research, not production-ready

---

### Failed

Model training failed

**Use:** Error tracking, debugging

---

## Design Decisions

---

### Why JSON for parameters?

**Decision:** Store model parameters as JSON string

**Rationale:**
- **Flexibility** - Different models have different parameters
- **Extensibility** - Easy to add new parameter types
- **Reproducibility** - Exact configuration captured
- **Queryable** - Can extract specific parameters if needed

**Alternative Considered:** Separate parameter columns per model type
**Why Rejected:** Rigid schema, hard to extend

### Why include training_samples?

**Decision:** Track number of training samples

**Rationale:**
- **Quality indicator** - More samples generally better
- **Debugging** - Identify insufficient training data
- **Comparison** - Understand model differences
- **Validation** - Ensure minimum sample requirements

---

## Related Documentation

---

### Model Documentation
- [[Forecast Model Overview]] - Parent model
- [[Forecast Facts]] - Predictions
- [[Forecast Metrics]] - Model accuracy
- [[Forecast Model Types]] - Algorithm details

### Architecture Documentation
- [[Models System/ML]] - ML framework
- [[Silver Storage]] - Registry storage

---

**Tags:** #finance/forecast #component/model #concept/ml #concept/registry

**Last Updated:** 2024-11-08
**Table:** model_registry
**Grain:** One row per trained model
