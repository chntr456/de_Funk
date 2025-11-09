---
id: forecast_analysis_example
title: Time Series Prediction Analysis (Example)
description: Example of using the general-purpose prediction chart with unified data
tags: [forecast, timeseries, predictions, example]
models: [forecast]
author: analyst@company.com
created: 2024-01-01
updated: 2024-01-15
---

# Time Series Prediction Analysis

This example shows how to use the refactored `forecast_chart` exhibit type with a unified data structure.

## Data Structure

The prediction chart expects data with this unified schema:

```sql
-- Example: Create a view that combines actuals and predictions
CREATE VIEW vw_time_series_predictions AS
SELECT
    date,
    ticker,
    model_name,
    actual_price as actual,
    predicted_price as predicted,
    upper_confidence_bound as upper_bound,
    lower_confidence_bound as lower_bound
FROM fact_predictions
```

## Prediction Chart with Measure Selector

Use standard measure and dimension selectors for interactive filtering:

$exhibits${
  type: forecast_chart
  source: forecast.vw_time_series_predictions
  title: "Stock Price Predictions"
  description: "Interactive time series with predictions and confidence intervals"

  x_axis: {dimension: date, label: "Date"}
  y_axis: {label: "Price ($)"}

  measure_selector: {
    available_measures: [actual, predicted, upper_bound, lower_bound]
    default_measures: [actual, predicted]
    selector_type: multiselect
    label: "Select Metrics"
    help_text: "Choose which metrics to display"
  }

  dimension_selector: {
    available_dimensions: [ticker, model_name]
    default_dimension: model_name
    label: "Group By"
    help_text: "Group predictions by ticker or model"
  }

  # Optional: Special styling for actual vs predicted
  actual_column: actual          # Renders as solid line
  predicted_column: predicted    # Renders as dashed line
  confidence_bounds: [lower_bound, upper_bound]  # Renders as shaded area
}

## Simple Prediction Chart (Static Configuration)

Without selectors, using static y_axis configuration:

$exhibits${
  type: forecast_chart
  source: forecast.vw_time_series_predictions
  title: "Price Forecast - ARIMA Model"

  x_axis: {dimension: date, label: "Date"}
  y_axis: {
    measures: [actual, predicted]
    label: "Price ($)"
  }

  color_by: ticker

  actual_column: actual
  predicted_column: predicted
  confidence_bounds: [lower_bound, upper_bound]
}

## Benefits of Unified Data Structure

1. **Single source of truth**: Actuals and predictions in one view
2. **Standard filters apply**: Date range, ticker, model filters work automatically
3. **No custom data loading**: Uses notebook session like other exhibits
4. **Flexible**: Works with any time series prediction data (not just stocks)
5. **Composable**: Combine with other exhibits (metric cards, data tables)

## Example SQL to Create Unified View

```sql
-- Combine historical actuals with future predictions
CREATE VIEW vw_stock_predictions AS

-- Historical actuals (predictions are NULL)
SELECT
    trade_date as date,
    ticker,
    'Historical' as model_name,
    close as actual,
    NULL as predicted,
    NULL as upper_bound,
    NULL as lower_bound
FROM fact_prices

UNION ALL

-- Future predictions (actuals are NULL)
SELECT
    prediction_date as date,
    ticker,
    model_name,
    NULL as actual,
    predicted_close as predicted,
    upper_bound,
    lower_bound
FROM fact_forecasts

ORDER BY date, ticker, model_name
```

## Using with Global Filters

The chart automatically respects global filters:

```yaml
$filter${
  id: trade_date
  type: date_range
  label: "Date Range"
  operator: between
  default: {start: "2024-01-01", end: "2024-12-31"}
}

$filter${
  id: ticker
  label: "Stock Tickers"
  type: select
  multi: true
  source: {model: forecast, table: vw_time_series_predictions, column: ticker}
}
```

The prediction chart will filter data based on these selections automatically!
