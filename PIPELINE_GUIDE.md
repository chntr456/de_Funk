# Pipeline Scripts Guide

This guide explains the different pipeline scripts available and when to use each one.

## Quick Reference

| Script | Purpose | Use When |
|--------|---------|----------|
| `run_full_pipeline.py` | Complete end-to-end | Production runs, scheduled jobs |
| `run_company_data_pipeline.py` | Data ingestion only | Refreshing data without forecasting |
| `run_forecasts.py` | Forecasting only | Running models on existing data |
| `refresh_data.py` | Quick data refresh | Small updates, testing |

---

## 1. Full Pipeline (Recommended for Production)

**Script**: `scripts/run_full_pipeline.py`

**What it does**:
- Ingests data from Polygon API
- Builds Silver layer tables
- Runs all forecast models
- Generates forecasts with confidence intervals

**Common Usage**:

```bash
# Production: Process last 90 days for all tickers
python scripts/run_full_pipeline.py --days 90

# Testing: Process 10 tickers with specific models
python scripts/run_full_pipeline.py --days 30 --max-tickers 10 --models arima_30d,prophet_30d

# Update forecasts only (skip data refresh)
python scripts/run_full_pipeline.py --skip-data-refresh
```

**All Options**:
```bash
python scripts/run_full_pipeline.py \
    --days 90                           # Number of recent days to process
    --from 2024-01-01 --to 2024-12-31  # Or specify date range
    --max-tickers 20                    # Limit number of tickers (default: all)
    --skip-data-refresh                 # Skip data ingestion step
    --include-news                      # Include news data (slower)
    --models arima_30d,prophet_30d     # Specific models to run
```

---

## 2. Company Data Pipeline

**Script**: `scripts/run_company_data_pipeline.py`

**What it does**:
- Ingests data from Polygon API
- Stores in Bronze layer (raw)
- Transforms to Silver layer (curated)
- Does NOT run forecasting

**Common Usage**:

```bash
# Ingest last 30 days for all tickers
python scripts/run_company_data_pipeline.py --days 30

# Ingest specific date range
python scripts/run_company_data_pipeline.py --from 2024-01-01 --to 2024-12-31

# Testing with limited tickers
python scripts/run_company_data_pipeline.py --days 7 --max-tickers 10

# Fast mode without news
python scripts/run_company_data_pipeline.py --days 30 --no-news
```

**All Options**:
```bash
python scripts/run_company_data_pipeline.py \
    --days 30                           # Number of recent days
    --from 2024-01-01 --to 2024-12-31  # Or specific date range
    --max-tickers 100                   # Limit tickers (default: all)
    --no-news                           # Skip news ingestion (faster)
```

---

## 3. Forecast Pipeline

**Script**: `scripts/run_forecasts.py`

**What it does**:
- Reads existing data from Silver layer
- Trains forecast models (ARIMA, Prophet, Random Forest)
- Generates predictions
- Calculates accuracy metrics
- Does NOT refresh data (unless --refresh specified)

**Common Usage**:

```bash
# Run forecasts for all tickers
python scripts/run_forecasts.py

# Run for specific tickers
python scripts/run_forecasts.py --tickers AAPL,GOOGL,MSFT

# Run specific models only
python scripts/run_forecasts.py --models arima_30d,prophet_30d

# Skip data refresh (use existing data)
python scripts/run_forecasts.py --no-refresh

# Testing mode
python scripts/run_forecasts.py --max-tickers 5 --models arima_30d
```

**All Options**:
```bash
python scripts/run_forecasts.py \
    --tickers AAPL,GOOGL,MSFT          # Specific tickers (default: all)
    --no-refresh                        # Skip data refresh
    --refresh-days 30                   # Days to refresh if refreshing
    --models arima_30d,prophet_30d     # Specific models
    --max-tickers 20                    # Limit tickers (default: all)
```

---

## 4. Quick Data Refresh

**Script**: `scripts/refresh_data.py`

**What it does**:
- Quick data refresh for recent days
- Simpler interface than full data pipeline
- Good for small updates

**Common Usage**:

```bash
# Refresh last 7 days
python scripts/refresh_data.py --days 7

# Refresh with ticker limit
python scripts/refresh_data.py --days 30 --max-tickers 10
```

**All Options**:
```bash
python scripts/refresh_data.py \
    --days 7                            # Number of recent days
    --max-tickers 10                    # Limit tickers (default: all)
```

---

## Common Workflows

### Daily Production Update

```bash
# Refresh last 7 days and run forecasts for all tickers
python scripts/run_full_pipeline.py --days 7
```

### Weekly Full Refresh

```bash
# Refresh last 90 days and run all forecasts
python scripts/run_full_pipeline.py --days 90
```

### Testing New Models

```bash
# Test with limited data and specific models
python scripts/run_full_pipeline.py \
    --days 30 \
    --max-tickers 5 \
    --models arima_30d
```

### Data-Only Refresh

```bash
# Just refresh data without forecasting
python scripts/run_company_data_pipeline.py --days 30
```

### Forecast-Only Update

```bash
# Just run forecasts on existing data
python scripts/run_forecasts.py --no-refresh
```

### Historical Backfill

```bash
# Ingest historical data
python scripts/run_company_data_pipeline.py \
    --from 2020-01-01 \
    --to 2024-12-31 \
    --no-news  # Faster without news
```

---

## Understanding Ticker Limits

**Default Behavior** (no `--max-tickers`):
- Processes ALL active tickers in your data
- Number depends on what was ingested

**How to check current ticker count**:
```bash
# This will show how many tickers you have
python scripts/run_forecasts.py --no-refresh --max-tickers 5
# Look for: "Processing X tickers: ..."
```

**Controlling ticker limits**:

1. **During ingestion** - limits what data is fetched:
   ```bash
   python scripts/run_company_data_pipeline.py --days 30 --max-tickers 100
   ```

2. **During forecasting** - limits which tickers are forecasted:
   ```bash
   python scripts/run_forecasts.py --max-tickers 20
   ```

3. **Full pipeline** - applies to both steps:
   ```bash
   python scripts/run_full_pipeline.py --days 30 --max-tickers 50
   ```

---

## Performance Tips

### For Faster Execution

```bash
# 1. Skip news (saves ~50% time)
python scripts/run_company_data_pipeline.py --days 30 --no-news

# 2. Use fewer models
python scripts/run_forecasts.py --models arima_30d,prophet_30d

# 3. Limit tickers during testing
python scripts/run_full_pipeline.py --days 7 --max-tickers 10

# 4. Skip data refresh if data is current
python scripts/run_forecasts.py --no-refresh
```

### For Complete Data

```bash
# Include everything
python scripts/run_full_pipeline.py \
    --days 90 \
    --include-news
```

---

## Scheduling Recommendations

### Daily (Automated)
```bash
# Cron: Run every day at 6 AM
0 6 * * * cd /path/to/de_Funk && python scripts/run_full_pipeline.py --days 7
```

### Weekly (Automated)
```bash
# Cron: Run every Sunday at 2 AM
0 2 * * 0 cd /path/to/de_Funk && python scripts/run_full_pipeline.py --days 90
```

### Monthly (Manual or Automated)
```bash
# Full historical refresh
python scripts/run_full_pipeline.py --from 2024-01-01 --to 2024-12-31
```

---

## Viewing Results

After running any pipeline:

```bash
# Start the UI
streamlit run app/ui/notebook_app_duckdb.py

# Then navigate to:
# - "Stock Performance Analysis" for price/volume data
# - "Forecast Analysis" for forecast results
```

---

## Troubleshooting

### "No data available"
- Run data ingestion first: `python scripts/run_company_data_pipeline.py --days 30`

### "No forecast data available"
- Run forecasts: `python scripts/run_forecasts.py`

### "Only seeing 50 tickers"
- Your data was previously ingested with `--max-tickers 50`
- Re-run without limit: `python scripts/run_company_data_pipeline.py --days 90`

### Out of memory
- Reduce `--max-tickers`: `--max-tickers 20`
- Process in batches

### Slow performance
- Use `--no-news` flag
- Reduce `--models` to fewer models
- Reduce `--days` for smaller date range

---

## Environment Setup

Before running any pipeline:

```bash
# 1. Activate virtual environment
source venv/bin/activate  # or your venv path

# 2. Ensure dependencies are installed
pip install -r requirements.txt

# 3. Set up Polygon API key (if needed)
export POLYGON_API_KEY="your_key_here"
```

---

## Quick Start Examples

**Complete beginner setup**:
```bash
# 1. Ingest 30 days for 10 tickers (testing)
python scripts/run_company_data_pipeline.py --days 30 --max-tickers 10

# 2. Run forecasts
python scripts/run_forecasts.py --max-tickers 10

# 3. View in UI
streamlit run app/ui/notebook_app_duckdb.py
```

**Production setup**:
```bash
# 1. Ingest 90 days for all tickers
python scripts/run_company_data_pipeline.py --days 90

# 2. Run all forecasts
python scripts/run_forecasts.py

# 3. View results
streamlit run app/ui/notebook_app_duckdb.py
```

**One-command full pipeline** (recommended):
```bash
# Does everything in one command
python scripts/run_full_pipeline.py --days 90
```
