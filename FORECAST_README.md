# Time Series Forecast Model

## Overview

This forecasting system provides comprehensive time series predictions for stock prices and trading volumes using multiple statistical and machine learning models. The system is designed to integrate seamlessly with the existing de_Funk data pipeline and UI.

## Features

- **Multiple Model Types**:
  - ARIMA (AutoRegressive Integrated Moving Average)
  - Prophet (Facebook's forecasting library)
  - Random Forest (Machine Learning ensemble method)

- **Configurable Timeframes**:
  - 7-day, 14-day, 30-day, and 60-day lookback periods
  - Adjustable forecast horizons
  - Day-of-week adjustments for seasonal patterns

- **Comprehensive Metrics**:
  - Mean Absolute Error (MAE)
  - Root Mean Squared Error (RMSE)
  - Mean Absolute Percentage Error (MAPE)
  - R² Score

- **Interactive UI**:
  - Forecast charts with confidence intervals
  - Model comparison visualizations
  - Accuracy metrics dashboards
  - Historical vs. predicted comparisons

## Architecture

### Model Structure

The forecast model inherits the same architecture pattern as the CompanyModel:

```
de_Funk/
├── models/
│   ├── forecast_model.py          # Main forecasting engine
│   └── company_model.py            # Company data model
├── configs/
│   └── models/
│       ├── forecast.yaml           # Forecast model configuration
│       └── company.yaml            # Company model configuration
├── scripts/
│   ├── refresh_data.py             # Data ingestion pipeline
│   └── run_forecasts.py            # Forecast execution orchestrator
└── storage/
    └── silver/
        ├── company/                # Company data (input)
        └── forecast/               # Forecast results (output)
            ├── facts/
            │   ├── forecast_price/
            │   ├── forecast_volume/
            │   └── forecast_metrics/
            └── ...
```

### Data Flow

```
1. Data Ingestion
   └─> Polygon API → Bronze Layer → Silver Layer (Company)

2. Forecasting
   └─> Load Price/Volume Data → Train Models → Generate Forecasts

3. Storage
   └─> Save Forecasts → Save Metrics → Partition by Date

4. UI Display
   └─> Load Forecasts → Render Charts → Display Metrics
```

## Installation

### 1. Install Required Packages

```bash
pip install -r requirements.txt
```

This installs:
- `statsmodels>=0.14.0` - ARIMA models
- `prophet>=1.1.5` - Facebook Prophet
- `scikit-learn>=1.3.0` - Random Forest and metrics

### 2. Verify Installation

```bash
python -c "import statsmodels; import prophet; import sklearn; print('All packages installed successfully!')"
```

## Usage

### Quick Start

Run forecasts for a few tickers:

```bash
# Run forecasts for AAPL, GOOGL, MSFT with data refresh
python scripts/run_forecasts.py --tickers AAPL,GOOGL,MSFT
```

### Step-by-Step Usage

#### Step 1: Refresh Recent Data

Before running forecasts, ensure you have the latest data:

```bash
# Refresh the last 30 days of data
python scripts/refresh_data.py --days 30

# Refresh for specific number of tickers (for testing)
python scripts/refresh_data.py --days 30 --max-tickers 10
```

#### Step 2: Run Forecasts

Execute forecasts with various options:

```bash
# Run all models for all active tickers
python scripts/run_forecasts.py

# Run specific models
python scripts/run_forecasts.py --models arima_30d,prophet_30d

# Run for specific tickers
python scripts/run_forecasts.py --tickers AAPL,GOOGL,MSFT,TSLA

# Skip data refresh (use existing data)
python scripts/run_forecasts.py --no-refresh --tickers AAPL

# Limit number of tickers (for testing)
python scripts/run_forecasts.py --max-tickers 5
```

#### Step 3: View Results in UI

1. Start the Streamlit app:
   ```bash
   streamlit run app/ui/notebook_app_duckdb.py
   ```

2. Navigate to the "Forecast Analysis" notebook

3. Select tickers and models to visualize

4. Explore forecast charts and accuracy metrics

### Advanced Usage

#### Custom Model Configuration

Edit `configs/models/forecast.yaml` to add or modify models:

```yaml
models:
  my_custom_arima:
    type: ARIMA
    target: [close, volume]
    lookback_days: 45
    forecast_horizon: 15
    day_of_week_adj: true
    auto_arima: true
    seasonal: true
```

#### Programmatic API

Use the ForecastModel class directly in Python:

```python
from models.forecast_model import ForecastModel
import yaml

# Load configurations
with open('configs/storage.json') as f:
    storage_cfg = json.load(f)

with open('configs/models/forecast.yaml') as f:
    forecast_cfg = yaml.safe_load(f)

# Initialize model
forecast_model = ForecastModel(
    storage_cfg=storage_cfg,
    model_cfg=forecast_cfg
)

# Run forecasts for a ticker
results = forecast_model.run_forecast_for_ticker(
    ticker='AAPL',
    model_configs=['arima_30d', 'prophet_30d']
)

print(f"Trained {results['models_trained']} models")
print(f"Generated {results['forecasts_generated']} forecasts")
```

## Model Details

### ARIMA Models

ARIMA (AutoRegressive Integrated Moving Average) is a statistical time series model that uses:
- **AR (AutoRegressive)**: Past values to predict future
- **I (Integrated)**: Differencing to make data stationary
- **MA (Moving Average)**: Past forecast errors

**Configurations**:
- `arima_7d`: 7-day lookback, 7-day forecast
- `arima_14d`: 14-day lookback, 14-day forecast
- `arima_30d`: 30-day lookback, 30-day forecast, seasonal
- `arima_60d`: 60-day lookback, 30-day forecast, seasonal

**Best for**:
- Short to medium-term forecasts
- Data with clear trends
- Stationary time series

### Prophet Models

Prophet is Facebook's forecasting library designed for time series with:
- Multiple seasonality (daily, weekly, yearly)
- Holiday effects
- Trend changes
- Missing data handling

**Configurations**:
- `prophet_7d`: 7-day lookback, multiplicative seasonality
- `prophet_30d`: 30-day lookback, with holidays
- `prophet_60d`: 60-day lookback, with holidays

**Best for**:
- Business time series with seasonality
- Data with trend changes
- Long-term forecasts

### Random Forest Models

Random Forest uses ensemble learning with multiple decision trees:
- Lagged features (lag_1, lag_7, lag_14, lag_30)
- Rolling statistics (7-day and 30-day means/std)
- Day-of-week features

**Configurations**:
- `random_forest_14d`: 14-day lookback, 7-day forecast
- `random_forest_30d`: 30-day lookback, 14-day forecast

**Best for**:
- Non-linear patterns
- Complex feature interactions
- Short-term forecasts (up to 14 days)

## Output Data

### Forecast Tables

#### `forecast_price`
Stores price forecasts with confidence intervals:

| Column | Type | Description |
|--------|------|-------------|
| ticker | string | Stock symbol |
| forecast_date | date | When forecast was generated |
| prediction_date | date | Date being predicted |
| horizon | int | Days ahead (1-30) |
| model_name | string | Model identifier |
| predicted_close | double | Predicted closing price |
| lower_bound | double | Lower 95% CI |
| upper_bound | double | Upper 95% CI |
| confidence | double | Confidence level (0-1) |

#### `forecast_volume`
Same structure as `forecast_price` but for trading volume.

#### `forecast_metrics`
Stores accuracy metrics for model evaluation:

| Column | Type | Description |
|--------|------|-------------|
| ticker | string | Stock symbol |
| model_name | string | Model identifier |
| metric_date | date | When metrics were calculated |
| mae | double | Mean Absolute Error |
| rmse | double | Root Mean Squared Error |
| mape | double | Mean Absolute Percentage Error |
| r2_score | double | R² score (coefficient of determination) |
| num_predictions | int | Number of predictions evaluated |

## UI Components

### Forecast Chart

Interactive chart showing:
- Historical actual values (solid line)
- Predicted values (dashed lines)
- Confidence intervals (shaded areas)
- Multiple model comparison

**Features**:
- Hover tooltips with detailed values
- Model selection via multiselect
- Ticker input field
- Target selection (price/volume)
- Dark/light theme support

### Forecast Metrics Table

Comprehensive accuracy metrics with:
- MAE, RMSE, MAPE, R² for each model
- Ticker and model filters
- Summary statistics
- Best model highlighting

## Troubleshooting

### Common Issues

#### 1. No forecast data available

**Problem**: UI shows "No forecast data available"

**Solution**: Run forecasts first:
```bash
python scripts/run_forecasts.py --tickers AAPL
```

#### 2. Import errors for prophet or statsmodels

**Problem**: `ModuleNotFoundError: No module named 'prophet'`

**Solution**: Install missing packages:
```bash
pip install prophet statsmodels scikit-learn
```

#### 3. ARIMA convergence warnings

**Problem**: ARIMA model shows convergence warnings

**Solution**: This is normal for some time series. The model will still generate forecasts. Try:
- Using `auto_arima: true` (already default)
- Increasing `lookback_days`
- Setting `seasonal: false` for non-seasonal data

#### 4. Out of memory errors

**Problem**: System runs out of memory when forecasting many tickers

**Solution**: Process in batches:
```bash
# Process 10 tickers at a time
python scripts/run_forecasts.py --max-tickers 10
```

#### 5. Slow forecast generation

**Problem**: Forecasts take a long time to generate

**Solution**:
- Start with fewer models: `--models arima_30d,prophet_30d`
- Use smaller lookback periods
- Process fewer tickers: `--max-tickers 5`

## Performance Tips

1. **Start Small**: Test with 1-5 tickers before running on all
2. **Use Appropriate Models**:
   - ARIMA for quick forecasts
   - Prophet for complex seasonality
   - Random Forest for short-term predictions
3. **Optimize Lookback**: Longer lookback ≠ better accuracy
4. **Monitor Metrics**: Check R² and MAPE to evaluate model performance
5. **Refresh Data Regularly**: Run daily or weekly to keep forecasts current

## Example Workflow

Complete workflow for production forecasting:

```bash
# 1. Install dependencies (one-time)
pip install -r requirements.txt

# 2. Refresh data (daily/weekly)
python scripts/refresh_data.py --days 90

# 3. Run forecasts (daily/weekly)
python scripts/run_forecasts.py \
    --models arima_30d,prophet_30d \
    --max-tickers 50

# 4. View in UI
streamlit run app/ui/notebook_app_duckdb.py

# 5. Monitor results and iterate
# Check forecast_metrics table for accuracy
# Adjust model configurations as needed
```

## Model Accuracy Interpretation

### MAE (Mean Absolute Error)
- Average magnitude of errors
- Same units as target variable
- Lower is better
- **Good**: MAE < 5% of average price/volume

### RMSE (Root Mean Squared Error)
- Penalizes large errors more than MAE
- Same units as target variable
- Lower is better
- **Good**: RMSE < 10% of average price/volume

### MAPE (Mean Absolute Percentage Error)
- Percentage error (scale-independent)
- Easier to interpret across different stocks
- Lower is better
- **Excellent**: MAPE < 5%
- **Good**: MAPE < 10%
- **Fair**: MAPE < 20%

### R² Score
- Proportion of variance explained
- Range: -∞ to 1.0
- Higher is better
- **Excellent**: R² > 0.9
- **Good**: R² > 0.7
- **Fair**: R² > 0.5
- **Poor**: R² < 0.5

## Future Enhancements

Potential improvements to the forecasting system:

1. **Additional Models**:
   - LSTM/GRU neural networks
   - XGBoost for gradient boosting
   - Ensemble methods combining multiple models

2. **Advanced Features**:
   - Sentiment analysis from news
   - Technical indicators (RSI, MACD, etc.)
   - Market indices as exogenous variables
   - Volatility forecasting

3. **Automation**:
   - Scheduled daily/weekly forecasts
   - Automatic model selection based on accuracy
   - Alert system for prediction errors
   - Model retraining triggers

4. **UI Enhancements**:
   - Model comparison side-by-side
   - Backtesting visualization
   - Forecast vs. actual performance tracking
   - Interactive parameter tuning

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs in the console output
3. Inspect forecast_metrics table for model performance
4. Open an issue in the project repository

## License

This forecast model is part of the de_Funk analytics platform.
