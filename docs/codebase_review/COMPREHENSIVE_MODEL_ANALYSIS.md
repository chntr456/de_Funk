# Comprehensive Analysis of de_Funk Models

## Executive Summary

The de_Funk codebase contains **8 domain models** organized in a dependency hierarchy, supporting a complete financial and economic data platform. Beyond the equity and corporate models commonly discussed, there are 5 additional models covering foundational dimensions, macroeconomic indicators, municipal finance, ETF holdings, and time series forecasting.

**Model Dependencies (Tiers):**
```
Tier 0 (Foundation):
└── core (calendar dimension)

Tier 1 (Independent):
├── macro (BLS economic indicators)
└── (equity/corporate - mentioned for completeness)

Tier 2 (Dependent):
├── city_finance (Chicago data - depends on core, macro)
└── (etf/forecast depend on equity/corporate)

Tier 3 (Advanced):
└── forecast (time series predictions)
```

---

## 1. CORE MODEL - Calendar Dimension (Foundation)

### Purpose & Scope
- **Business Domain**: Universal reference dimension used by ALL other models
- **Questions Answered**: 
  - What dates fall on weekdays/weekends?
  - What fiscal year/quarter/month for a given date?
  - Date range statistics (# of trading days, quarters, etc.)?
- **Status**: ACTIVE - Full implementation

### Configuration Analysis

**File**: `/home/user/de_Funk/configs/models/core.yaml`

**Tables**:
- `dim_calendar` (1 dimension, no facts)
  - Primary Key: `date` (YYYY-MM-DD)
  - **Rich Date Attributes** (25 columns):
    - Time components: `year`, `quarter`, `month`, `month_name`, `month_abbr`, `week_of_year`, `day_of_month`, `day_of_year`
    - Day metadata: `day_of_week`, `day_of_week_name`, `day_of_week_abbr`, `is_weekend`, `is_weekday`
    - Period boundaries: `is_month_start`, `is_month_end`, `is_quarter_start`, `is_quarter_end`, `is_year_start`, `is_year_end`
    - Fiscal dimensions: `fiscal_year`, `fiscal_quarter`, `fiscal_month`
    - Aggregates: `days_in_month`, `year_month`, `year_quarter`, `date_str`

**Calendar Configuration**:
```yaml
start_date: "2000-01-01"
end_date: "2050-12-31"
fiscal_year_start_month: 1  # January (configurable)
weekend_days: [6, 7]  # Saturday, Sunday
holidays: [New Year's Day, Independence Day, Christmas]  # US Federal Holidays
```

**Measures**: None (pure reference data)

**Dependencies**: None (foundation model - no dependencies)

### Implementation

**File**: `/home/user/de_Funk/models/implemented/core/model.py`

**Class**: `CoreModel(BaseModel)`

**Custom Methods** (convenience layer):
- `get_calendar()` - Filter calendar by date range, year, month
- `get_weekdays()` / `get_weekends()` - Trading day filters
- `get_fiscal_year_dates(fiscal_year)` - Get all dates for fiscal year
- `get_quarter_dates(year, quarter)` - Get quarter dates
- `get_month_dates(year, month)` - Get month dates
- `get_date_range_info(date_from, date_to)` - Statistics (days, quarters, months)
- `get_calendar_config()` - Access YAML config

**Calendar Builder**:
- Location: `/home/user/de_Funk/models/implemented/core/builders/calendar_builder.py`
- Generates calendar table from configuration
- Supports US holidays + custom holidays

### Data Pipeline

**Source**: Seed data (not from external API)
- **Bronze Table**: `bronze.calendar_seed`
- **Status**: ✅ Data exists (calendar is built, not ingested)

**Transformation**:
```
calendar_seed (Bronze)
    ↓
dim_calendar (Silver) → Select + derive columns
```

**No ingestion pipeline** - Calendar is generated once and updated as needed.

### Cross-Model Relationships

**All other models depend on core**:
- `fact_*` tables join to `core.dim_calendar` on date columns
- Enables consistent date-based filtering across all models
- Provides shared time attributes (year_quarter, fiscal_year, etc.)

**Usage Pattern**:
```yaml
edges:
  - from: fact_unemployment
    to: core.dim_calendar
    on: ["date=date"]
    type: left
    # All models can now filter by calendar attributes
```

### Storage Status

**Path**: `/home/user/de_Funk/storage/silver/core/`

**Parquet Files**: 
- `dims/dim_calendar/` - Calendar dimension table

**Maturity**: ✅ FULLY BUILT - Core foundation table, always available.

---

## 2. MACRO MODEL - Macroeconomic Indicators (BLS Data)

### Purpose & Scope
- **Business Domain**: U.S. macroeconomic indicators from Bureau of Labor Statistics
- **Questions Answered**:
  - What was national unemployment rate in a given period?
  - How has CPI (inflation) trended over time?
  - What are employment trends across the economy?
  - How have wages changed over time?
  - Compare local vs national economic indicators?

### Configuration Analysis

**File**: `/home/user/de_Funk/configs/models/macro.yaml`

**Tables**:

**Dimensions** (1):
- `dim_economic_series` 
  - Primary Key: `series_id`
  - Columns: `series_id`, `series_name`, `category`, `frequency`, `units`, `seasonal_adjustment`
  - Purpose: Metadata about BLS data series

**Facts** (5):
1. `fact_unemployment` (monthly)
   - Columns: `series_id`, `date`, `year`, `period`, `value`, `period_name`
   - Partitions: `year`
   - BLS Series: `LNS14000000` (Unemployment Rate - Civilian Labor Force)

2. `fact_cpi` (monthly)
   - Columns: `series_id`, `date`, `year`, `period`, `value`, `period_name`
   - Partitions: `year`
   - BLS Series: `CUUR0000SA0` (Consumer Price Index - All Urban Consumers)

3. `fact_employment` (monthly)
   - Columns: `series_id`, `date`, `year`, `period`, `value`, `period_name`
   - Partitions: `year`
   - BLS Series: `CES0000000001` (Total Nonfarm Employment)

4. `fact_wages` (monthly)
   - Columns: `series_id`, `date`, `year`, `period`, `value`, `period_name`
   - Partitions: `year`
   - BLS Series: `CES0500000003` (Average Hourly Earnings - Total Private)

5. `economic_indicators_wide` (wide format)
   - Pivoted view with all indicators by date
   - Columns: `date`, `unemployment_rate`, `cpi_value`, `total_employment`, `avg_hourly_earnings`

**Graph Edges** (4 internal):
- Each fact table → dim_economic_series (many-to-one)

**Measures** (4):
- `avg_unemployment_rate` - Average unemployment (%)
- `latest_cpi` - Most recent CPI value
- `employment_growth` - Total employment sum
- `wage_trend` - Average hourly earnings

**Dependencies**: 
- `core` - Uses dim_calendar for date-based filtering

### Implementation

**File**: `/home/user/de_Funk/models/implemented/macro/model.py`

**Class**: `MacroModel(BaseModel)`

**Custom Methods**:
- `get_unemployment(date_from, date_to)` - Filter unemployment data
- `get_cpi(date_from, date_to)` - Filter CPI data
- `get_employment(date_from, date_to)` - Filter employment data
- `get_wages(date_from, date_to)` - Filter wage data
- `get_all_indicators(date_from, date_to)` - Wide join of all 4 indicators
- `get_latest_values()` - Get most recent value for each indicator
- `get_bls_series_config()` - Access BLS configuration

### Data Pipeline

**Data Provider**: Bureau of Labor Statistics (BLS)
- **Frequency**: Monthly (U.S. federal data release schedule)
- **Endpoint Configuration**: `/home/user/de_Funk/configs/bls_endpoints.json` (auto-discovered)

**Ingestor**: 
- Location: `/home/user/de_Funk/datapipelines/providers/bls/bls_ingestor.py`
- Class: `BLSIngestor`
- Authentication: API key in `.env` (`BLS_API_KEYS`)
- HTTP Method: POST (JSON body with series IDs and date range)
- Rate Limiting: Implemented via `ApiKeyPool`

**Facets** (Data Normalizers):
- `unemployment_facet.py` - Normalizes BLS unemployment response
- `cpi_facet.py` - Normalizes BLS CPI response
- Base facet: `bls_base_facet.py`

**Bronze Tables** (Raw Data):
- `bronze.bls_unemployment`
- `bronze.bls_cpi`
- `bronze.bls_employment`
- `bronze.bls_wages`

**Transformation Pipeline**:
```
BLS API → HttpClient → Ingestor → Facet (normalize) → Bronze (Parquet)
    ↓
    Silver nodes (dim_economic_series, fact_*)
```

**Data Ingestion Status**: 
- ⚠️ CONDITIONAL - Requires BLS_API_KEYS in `.env`
- Not automatically ingested; requires `run_full_pipeline.py`

### Cross-Model Relationships

**Edges to Other Models**:
- ✅ `macro.fact_unemployment` ←→ `city_finance.fact_local_unemployment` (date=date)
  - Enables local vs national unemployment comparison
- ✅ `macro.fact_unemployment` ←→ `core.dim_calendar` (date=date)
  - Date filtering and time attributes

### Storage Status

**Path**: `/home/user/de_Funk/storage/silver/macro/`

**Expected Structure**:
```
storage/silver/macro/
├── dims/
│   └── dim_economic_series/
└── facts/
    ├── fact_unemployment/
    ├── fact_cpi/
    ├── fact_employment/
    ├── fact_wages/
    └── economic_indicators_wide/
```

**Maturity**: 🟡 PARTIAL - Schema defined, data depends on successful BLS API ingestion.

---

## 3. CITY_FINANCE MODEL - Chicago Municipal Data

### Purpose & Scope
- **Business Domain**: City of Chicago financial and economic data
- **Questions Answered**:
  - What's the unemployment rate by Chicago community area?
  - How many building permits issued in a specific area?
  - What building activities are happening?
  - How do local unemployment rates compare to national?
  - Where is economic activity concentrated in Chicago?

### Configuration Analysis

**File**: `/home/user/de_Funk/configs/models/city_finance.yaml`

**Tables**:

**Dimensions** (2):
1. `dim_community_area`
   - Primary Key: `community_area`
   - Columns: `community_area`, `community_name`, `geography_type`
   - Purpose: Chicago's 77 community areas + geographic context

2. `dim_permit_type`
   - Primary Key: `permit_type`
   - Columns: `permit_type`, `permit_category`
   - Purpose: Building permit type taxonomy

**Facts** (5):
1. `fact_local_unemployment` (monthly, by community area)
   - Columns: `geography`, `geography_type`, `date`, `unemployment_rate`, `labor_force`, `employed`, `unemployed`
   - Partitions: `date`
   - Source: Chicago Data Portal (dataset: `ane4-dwhs`)

2. `fact_building_permits` (event-based)
   - Columns: `permit_number`, `permit_type`, `issue_date`, `total_fee`, `contractor_name`, `work_description`, `community_area`, `latitude`, `longitude`
   - Partitions: `issue_date`
   - Source: Chicago Data Portal (dataset: `ydr8-5enu`)
   - Rich spatial data (lat/long for geo-mapping)

3. `fact_business_licenses` (event-based)
   - Columns: `license_id`, `business_name`, `license_type`, `start_date`, `community_area`
   - Partitions: `start_date`
   - Source: Chicago Data Portal (dataset: `r5kz-chrr`)

4. `fact_economic_indicators` (monthly)
   - Columns: `indicator_name`, `date`, `value`, `community_area`
   - Partitions: `date`
   - Source: Chicago Data Portal (dataset: `nej5-8p3s`)

5. **Materialized Paths** (Analytics Views):
   - `unemployment_with_area` - fact_local_unemployment + dim_community_area
   - `permits_with_area` - fact_building_permits + dim_community_area

**Graph Edges** (6 internal + 3 cross-model):

Internal:
- fact_local_unemployment → dim_community_area (many-to-one)
- fact_building_permits → dim_community_area (many-to-one)
- fact_building_permits → dim_permit_type (many-to-one)

Cross-Model:
- fact_local_unemployment → `core.dim_calendar` (date join)
- fact_building_permits → `core.dim_calendar` (issue_date join)
- fact_local_unemployment → `macro.fact_unemployment` (date=date) **Key cross-model edge!**
  - Enables local vs national unemployment comparison

**Measures** (5):
- `avg_local_unemployment` - Average unemployment by community
- `total_permits_issued` - Count of permits
- `total_permit_fees` - Sum of permit fees (revenue)
- `avg_permit_fee` - Average permit fee
- `total_labor_force` - Sum of labor force across communities

**Dependencies**:
- `core` (for calendar)
- `macro` (for national comparison)

### Implementation

**File**: `/home/user/de_Funk/models/implemented/city_finance/model.py`

**Class**: `CityFinanceModel(BaseModel)`

**Custom Methods**:
- `get_local_unemployment(community_area, date_from, date_to)` - Filter local unemployment
- `get_building_permits(community_area, permit_type, date_from, date_to)` - Filter permits
- `get_permits_with_context(...)` - Permits + community area details (materialized path)
- `get_unemployment_with_context(...)` - Unemployment + community area details (materialized path)
- `get_community_areas()` - List all 77 Chicago community areas
- `get_permit_types()` - List permit types

**Cross-Model Analysis**:
- `compare_to_national_unemployment(community_area, date_from, date_to)` 
  - Joins local unemployment with national macro data
  - Calculates rate_diff (local - national)
  - Requires session for macro model access
- `get_permit_summary_by_area(date_from, date_to)`
  - Aggregates permits and fees by community area

### Data Pipeline

**Data Provider**: Chicago Data Portal (Socrata API)
- **API Type**: REST with offset-based pagination
- **Endpoint Configuration**: `/home/user/de_Funk/configs/chicago_endpoints.json` (auto-discovered)

**Ingestor**:
- Location: `/home/user/de_Funk/datapipelines/providers/chicago/chicago_ingestor.py`
- Class: `ChicagoIngestor`
- Authentication: Optional API token in `.env` (`CHICAGO_API_KEYS`)
- Pagination: Offset-based ($offset, $limit parameters)
- Rate Limiting: Implemented via `ApiKeyPool`

**Facets** (Data Normalizers):
- `unemployment_rates_facet.py` - Normalizes Chicago unemployment data
- `building_permits_facet.py` - Normalizes building permits data
- Base facet: `chicago_base_facet.py`

**Bronze Tables**:
- `bronze.chicago_unemployment`
- `bronze.chicago_building_permits`
- `bronze.chicago_business_licenses`
- `bronze.chicago_economic_indicators`

**Transformation Pipeline**:
```
Chicago Socrata API → HttpClient → Ingestor → Facet (normalize) → Bronze
    ↓
Silver nodes (dims + facts + materialized paths)
```

**Data Ingestion Status**:
- ⚠️ CONDITIONAL - Optional API token, may have lower rate limits without auth
- Requires `run_full_pipeline.py`

### Cross-Model Relationships

**Outgoing Edges**:
- ✅ `fact_local_unemployment` → `core.dim_calendar` - Date filtering
- ✅ `fact_building_permits` → `core.dim_calendar` - Date filtering
- ✅ `fact_local_unemployment` → `macro.fact_unemployment` - **National comparison**

**Incoming Edges**: None (not referenced by other models)

**Integration Point**: Compare local economic conditions to national trends.

### Storage Status

**Path**: `/home/user/de_Funk/storage/silver/city_finance/`

**Expected Structure**:
```
storage/silver/city_finance/
├── dims/
│   ├── dim_community_area/
│   └── dim_permit_type/
└── facts/
    ├── fact_local_unemployment/
    ├── fact_building_permits/
    ├── fact_business_licenses/
    ├── fact_economic_indicators/
    ├── unemployment_with_area/
    └── permits_with_area/
```

**Maturity**: 🟡 PARTIAL - Schema defined, data depends on Chicago API ingestion.

---

## 4. ETF MODEL - Exchange Traded Funds

### Purpose & Scope
- **Business Domain**: ETF holdings, pricing, and weighted analysis
- **Questions Answered**:
  - What are the top-performing ETFs?
  - What stocks does a given ETF hold?
  - How do ETF prices compare to NAV (premium/discount)?
  - What's the weighted return of an ETF based on its holdings?
  - How has ETF expense ratio changed?

### Configuration Analysis

**File**: `/home/user/de_Funk/configs/models/etf.yaml`

**Tables**:

**Dimensions** (2):
1. `dim_etf`
   - Primary Key: `etf_ticker`
   - Columns: `etf_ticker`, `etf_name`, `fund_family`, `expense_ratio`, `inception_date`, `category`, `index_tracked`, `etf_id`
   - Purpose: ETF master data and fund metadata
   - Source: `bronze.etf_info`

2. `dim_etf_holdings` (Temporal - snapshot-based)
   - Primary Key: `(etf_ticker, holding_ticker, as_of_date)`
   - Columns: `etf_ticker`, `holding_ticker`, `as_of_date`, `weight_percent`, `shares_held`, `market_value`
   - Purpose: Holdings at a specific date (point-in-time snapshot)
   - **Critical for weighted analysis**: Tracks portfolio composition over time
   - Source: `bronze.etf_holdings`

**Facts** (2):
1. `fact_etf_prices` (daily)
   - Columns: `trade_date`, `etf_ticker`, `open`, `high`, `low`, `close`, `volume_weighted`, `volume`, `nav`, `premium_discount`
   - Partitions: `trade_date`
   - Purpose: Daily price data with NAV comparison
   - Source: `bronze.etf_prices_daily`

2. `etf_prices_with_info` (Materialized Path)
   - Join of fact_etf_prices + dim_etf
   - Enriches price data with fund metadata
   - Partitions: `trade_date`

**Graph Edges** (5):

Internal:
- fact_etf_prices → dim_etf (many-to-one: prices belong to fund)
- dim_etf_holdings → dim_etf (many-to-one: holdings belong to fund)

Cross-Model:
- fact_etf_prices → `core.dim_calendar` (trade_date=date) - Date filtering
- dim_etf_holdings → `equity.dim_equity` (holding_ticker=ticker) - **Cross-model edge!**
  - Holdings reference equity stocks from the equity model

**Paths** (3):
- `etf_prices_with_info` - fact_etf_prices → dim_etf
- `etf_prices_with_calendar` - fact_etf_prices → core.dim_calendar
- `etf_holdings_with_equity` - dim_etf_holdings → equity.dim_equity

**Measures** (5 - includes weighted):
1. Simple Measures:
   - `avg_expense_ratio` - Average expense ratio
   - `avg_etf_close` - Average closing price
   - `avg_premium_discount` - Average premium/discount to NAV

2. **Weighted Measures** (Advanced):
   - `holdings_weighted_return` - **Type: weighted**
     - Source: `equity.fact_equity_prices.close` (cross-model!)
     - Method: `etf_holdings`
     - Weight: `dim_etf_holdings.weight_percent`
     - Groups by: `[trade_date, etf_ticker]`
     - Calculates ETF return from underlying holdings
   
   - `holdings_weighted_volume` - **Type: weighted**
     - Source: `equity.fact_equity_prices.volume` (cross-model!)
     - Method: `etf_holdings`
     - Weight: `dim_etf_holdings.weight_percent`
     - Aggregates volume across holdings

**Dependencies**:
- `core` (for calendar)
- `equity` (for holdings cross-reference and weighted calculations)
- `corporate` (for company fundamentals)

### Implementation

**File**: `/home/user/de_Funk/models/implemented/etf/model.py`

**Class**: `ETFModel(BaseModel)`

**Custom Methods**:
- `calculate_measure_by_etf(measure_name, limit)` - Calculate measure aggregated by ETF
- `get_top_etfs_by_measure(measure_name, limit)` - Get top N ETF tickers
- `get_etf_prices(etf_ticker)` - Filter price data
- `get_etf_info(etf_ticker)` - Get ETF metadata
- `get_etf_holdings(etf_ticker, as_of_date)` - Get holdings at a point in time
- `get_etf_with_context(etf_ticker)` - Prices with fund information

**Weighting Strategy**:

Location: `/home/user/de_Funk/models/implemented/etf/domains/weighting.py`

Class: `HoldingsWeightStrategy(WeightingStrategy)`

- Joins holdings table with price/metric table
- Weights by holdings percentage (weight_percent / 100)
- Implements SQL generation for both backends
- Use Case: Calculate ETF return from underlying stock returns

Example SQL (conceptual):
```sql
SELECT
    h.trade_date, h.etf_ticker,
    SUM(s.close * (h.weight_percent / 100.0)) / SUM(h.weight_percent / 100.0) as weighted_return
FROM dim_etf_holdings h
JOIN equity.fact_equity_prices s
    ON h.holding_ticker = s.ticker
    AND h.as_of_date = s.trade_date
GROUP BY h.trade_date, h.etf_ticker
```

### Data Pipeline

**Data Provider**: ETF holdings and price data
- **Sources**: 
  - ETF prices: Likely from Polygon.io (same as stock prices)
  - ETF holdings: Third-party provider (IEX Cloud, Morningstar, etc.)
  - ETF metadata: Various provider APIs

**Bronze Tables**:
- `bronze.etf_info` - ETF metadata
- `bronze.etf_holdings` - Point-in-time holdings
- `bronze.etf_prices_daily` - Daily prices

**Transformation**: 
```
API Data → Facet (normalize) → Bronze (Parquet)
    ↓
Silver (dims + facts + materialized paths)
```

**Data Ingestion Status**:
- 🟡 PARTIAL - ETF infrastructure exists, actual ingestion may depend on data availability

### Cross-Model Relationships

**Key Cross-Model Integration**:
- ✅ `dim_etf_holdings` → `equity.dim_equity` (holding_ticker=ticker)
  - Every holding references an equity stock
  - Enables weighted measure calculation

**Example Workflow**:
```
1. Get ETF holdings as of date D
2. For each holding:
   - Lookup equity prices for that ticker
   - Weight by holding percentage
3. Aggregate to get ETF-level metrics
```

### Storage Status

**Path**: `/home/user/de_Funk/storage/silver/etf/`

**Expected Structure**:
```
storage/silver/etf/
├── dims/
│   ├── dim_etf/
│   └── dim_etf_holdings/
└── facts/
    ├── fact_etf_prices/
    └── etf_prices_with_info/
```

**Maturity**: 🟡 PARTIAL - Schema defined, data availability depends on data provider configuration.

---

## 5. FORECAST MODEL - Time Series Predictions

### Purpose & Scope
- **Business Domain**: Time series forecasting for stock prices and volumes
- **Questions Answered**:
  - What will stock prices be in the next 7/14/30 days?
  - What are confidence intervals for predictions?
  - How accurate are different models?
  - What are forecast error metrics (MAE, RMSE, MAPE)?
  - Which model performs best for a given stock?

### Configuration Analysis

**File**: `/home/user/de_Funk/configs/models/forecast.yaml`

**Tables**:

**Facts** (3):
1. `fact_forecasts` - Predictions
   - Columns: `ticker`, `target` (close/volume), `forecast_date`, `prediction_date`, `horizon` (1-30 days), `model_name`, `predicted_close`, `predicted_volume`, `lower_bound`, `upper_bound`, `confidence`
   - Partitions: `forecast_date`
   - Purpose: Point predictions with confidence intervals (95%)

2. `fact_forecast_metrics` - Model Accuracy
   - Columns: `ticker`, `model_name`, `metric_date`, `training_start`, `training_end`, `test_start`, `test_end`, `mae`, `rmse`, `mape`, `r2_score`, `num_predictions`, `avg_error_pct`
   - Partitions: `metric_date`
   - Purpose: Track model accuracy over time

3. `fact_model_registry` - Trained Models
   - Columns: `model_id`, `model_name`, `model_type`, `ticker`, `target_variable`, `lookback_days`, `forecast_horizon`, `day_of_week_adj`, `parameters` (JSON), `trained_date`, `training_samples`, `status`
   - Partitions: `trained_date`
   - Purpose: Registry of trained models and their parameters

**No explicit dimensions** - Uses ticker from equity model

**Graph Edges** (3):
- fact_forecasts → `core.dim_calendar` (prediction_date=date)
- fact_forecast_metrics → `core.dim_calendar` (metric_date=date)
- fact_forecasts → `equity.fact_equity_prices` (ticker=ticker) - **Actuals vs predictions**
- fact_forecasts → `equity.dim_equity` (ticker=ticker)

**Paths** (2):
- `forecasts_with_calendar` - Forecasts + calendar attributes
- `metrics_with_calendar` - Metrics + calendar attributes

**Measures** (3):
- `avg_forecast_error` - Average MAE across models
- `avg_forecast_mape` - Average MAPE across models
- `best_model_r2` - Best R² score

**Model Configurations** (8 + variants):

1. **ARIMA Models** (Autoregressive Integrated Moving Average)
   - `arima_7d` - 7-day lookback, 7-day horizon
   - `arima_14d` - 14-day lookback, 14-day horizon
   - `arima_30d` - 30-day lookback, 30-day horizon, seasonal
   - `arima_60d` - 60-day lookback, 30-day horizon, seasonal

2. **Prophet Models** (Facebook's Time Series Library)
   - `prophet_7d` - 7-day lookback, 7-day horizon
   - `prophet_30d` - 30-day lookback, 30-day horizon, holidays
   - `prophet_60d` - 60-day lookback, 30-day horizon, holidays

3. **Random Forest Models** (ML-based)
   - `random_forest_14d` - 14-day lookback, 7-day horizon
   - `random_forest_30d` - 30-day lookback, 14-day horizon
   - Features: lag_1, lag_7, lag_14, day_of_week, rolling_mean/std

**Features for ML Models**:
- Lag features (lag_1, lag_7, lag_14, lag_30)
- Rolling statistics (rolling_mean_7/30, rolling_std_7/30)
- Temporal features (day_of_week)
- Day-of-week adjustment

**Dependencies**:
- `core` (for calendar and fiscal dates)
- `equity` (for historical stock price data)
- `corporate` (for fundamentals to enhance predictions)

### Implementation

**File**: `/home/user/de_Funk/models/implemented/forecast/company_forecast_model.py`

**Class**: `CompanyForecastModel(TimeSeriesForecastModel)`

**Extends**: `BaseModel` via `TimeSeriesForecastModel`

**Abstract Methods Implementation**:
- `get_source_model_name()` → `'company'` or `'equity'`
- `get_source_table_name()` → `'fact_prices'`
- `get_entity_column()` → `'ticker'`
- `get_date_column()` → `'trade_date'`

**Custom Node Loading**:
- Overrides `custom_node_loading()` to load from Silver (pre-computed forecasts)
- Supports loading from `silver.*` tables (not just Bronze)

**Training Methods**:

Location: `/home/user/de_Funk/models/implemented/forecast/training_methods.py`

- ARIMA training (statsmodels)
- Prophet training (Facebook)
- Random Forest training (scikit-learn)
- Model evaluation (MAE, RMSE, MAPE, R²)

### Data Pipeline

**Data Source**: Equity model historical data
- Reads from `equity.fact_equity_prices` (Bronze or Silver)
- Uses `trade_date`, `ticker`, `close`, `volume`

**Workflow**:
```
1. Extract historical data (training set)
   Source: equity.fact_equity_prices
   
2. Train models
   - ARIMA: statsmodels.tsa.arima.ARIMA
   - Prophet: fbprophet.Prophet
   - Random Forest: sklearn.ensemble.RandomForestRegressor
   
3. Generate predictions
   - For each horizon (1-30 days)
   - With confidence intervals
   - Store in fact_forecasts
   
4. Calculate metrics
   - Train/test split
   - Evaluate on test set
   - Store in fact_forecast_metrics
   
5. Register models
   - Store parameters and metadata
   - Store in fact_model_registry
```

**Execution**:
- Run via: `python scripts/run_forecasts.py`
- Or individual: `python scripts/run_forecast_model.py --model arima`

**Data Ingestion Status**:
- ✅ SELF-CONTAINED - Generates data from equity model
- No external API dependency
- On-demand execution

### Cross-Model Relationships

**Data Dependencies**:
- ✅ Reads from `equity.fact_equity_prices` (training data)
- ✅ Reads from `equity.dim_equity` (ticker dimension)
- ✅ References `core.dim_calendar` (date filtering)

**Enables**:
- Stock price prediction notebooks
- Volume prediction for liquidity analysis
- Model performance dashboards

### Storage Status

**Path**: `/home/user/de_Funk/storage/silver/forecast/`

**Expected Structure**:
```
storage/silver/forecast/
└── facts/
    ├── forecast_price/ (fact_forecasts)
    ├── forecast_metrics/ (fact_forecast_metrics)
    └── model_registry/ (fact_model_registry)
```

**Maturity**: 🟡 PARTIAL - Schema defined, data depends on successful forecast generation.

---

## Cross-Model Dependency Graph

### Complete Dependency Hierarchy

```
Tier 0 (Foundation):
└── core
    └── Used by ALL other models for time-based filtering

Tier 1 (Independent):
├── macro
│   └── Depends on: core
│
└── equity/corporate
    └── Depends on: core

Tier 2 (Geographic/Business):
├── city_finance
│   ├── Depends on: core, macro
│   └── Compares local vs national unemployment
│
└── etf
    ├── Depends on: core, equity, corporate
    └── Holdings reference equity stocks (cross-model!)

Tier 3 (Predictive):
└── forecast
    ├── Depends on: core, equity, corporate
    └── Trains on historical equity prices
```

### Key Cross-Model Edges

| From | To | Join Key | Purpose |
|------|----|---------|---------| 
| All fact_* | core.dim_calendar | date columns | Date filtering, time attributes |
| city_finance.fact_unemployment | macro.fact_unemployment | date | Local vs national comparison |
| etf.dim_etf_holdings | equity.dim_equity | holding_ticker=ticker | Holdings reference stocks |
| forecast.fact_forecasts | equity.fact_equity_prices | ticker | Actuals vs predictions |

### Data Flow Visualization

```
External APIs (Bronze Layer)
│
├─→ Polygon.io        → prices_daily, ref_all_tickers, news
├─→ BLS               → bls_unemployment, bls_cpi, bls_employment, bls_wages
└─→ Chicago Portal    → chicago_unemployment, chicago_building_permits

             ↓

Model Graph Building (Silver Layer)
│
├─→ core
│   └─ dim_calendar (seed data)
│
├─→ macro
│   ├─ dim_economic_series, fact_unemployment, fact_cpi, ...
│   └─ (depends on: core.dim_calendar)
│
├─→ city_finance
│   ├─ dim_community_area, fact_local_unemployment, ...
│   └─ (depends on: core.dim_calendar, macro.fact_unemployment)
│
├─→ equity/corporate
│   ├─ dim_equity, dim_corporate, fact_prices, ...
│   └─ (depends on: core.dim_calendar)
│
├─→ etf
│   ├─ dim_etf, dim_etf_holdings, fact_etf_prices
│   └─ (depends on: core, equity)
│
└─→ forecast
    ├─ fact_forecasts, fact_forecast_metrics, fact_model_registry
    └─ (depends on: core, equity)

             ↓

Query Layer (Analytics)
│
└─→ DuckDB Catalog (in-memory or persistent)
    │
    ├─→ Notebooks (Markdown with filters)
    ├─→ Dashboards (Streamlit UI)
    └─→ SQL Queries (UniversalSession)
```

---

## Summary by Model Maturity

### Status Legend
- ✅ **ACTIVE** - Fully implemented and working
- 🟡 **PARTIAL** - Schema defined, data depends on ingestion/computation
- 🔴 **PLACEHOLDER** - Not yet implemented

### Model Maturity Table

| Model | Implementation | Data | Maturity | Notes |
|-------|---|---|---------|-------|
| **core** | ✅ Full | ✅ Built | ✅ ACTIVE | Calendar seed data, no API |
| **macro** | ✅ Full | 🟡 Conditional | 🟡 PARTIAL | BLS API ingestion required |
| **city_finance** | ✅ Full | 🟡 Conditional | 🟡 PARTIAL | Chicago Portal ingestion required |
| **etf** | ✅ Full | 🟡 Conditional | 🟡 PARTIAL | Requires ETF data provider |
| **forecast** | ✅ Full | 🟡 On-demand | 🟡 PARTIAL | Generates from equity data |

### Implementation Completeness

**Fully Implemented**:
- All 5 models have complete YAML configurations
- All 5 models have Python class implementations
- All measures defined in YAML
- All graph edges defined

**Data Availability**:
- **core**: Always available (seed data)
- **macro**, **city_finance**, **etf**: Require successful API ingestion
- **forecast**: Requires running forecast generation script

---

## Key Insights

### 1. Domain-Agnostic Framework
de_Funk is a **domain-agnostic framework** demonstrated with financial/economic domain:
- Can model ANY domain (healthcare, retail, logistics, etc.)
- Same YAML-driven architecture applies universally
- Models, measures, paths all defined declaratively

### 2. Cross-Model Analysis Capability
The system enables sophisticated **cross-model analysis**:
- Local unemployment vs national trends (city_finance ↔ macro)
- ETF holdings vs stock prices (etf ↔ equity)
- Forecast accuracy vs actual prices (forecast ↔ equity)

### 3. Weighted Measure Innovation
ETF model demonstrates **weighted measure framework**:
- Not just simple aggregation (avg, sum)
- Can weight by holdings percentages
- Enables "ETF return from holdings" calculation
- Extensible to other weighting scenarios

### 4. Temporal Dimension Handling
Models use **point-in-time snapshots**:
- ETF holdings change over time (tracking date: as_of_date)
- Enables historical portfolio composition analysis
- Required for accurate time-series calculations

### 5. Two-Layer Architecture Simplicity
Simplified **Bronze → Silver** (no separate Gold):
- DuckDB serves analytics role
- No data duplication between layers
- More efficient than three-layer medallion

---

## Configuration Precedence

All models follow same **configuration loading hierarchy**:
1. Explicit parameters (programmatic)
2. Environment variables (.env file)
3. Configuration files (configs/*.yaml, configs/*.json)
4. Default values (config/constants.py)

This applies to:
- API credentials (BLS_API_KEYS, CHICAGO_API_KEYS, POLYGON_API_KEYS)
- Connection type (spark vs duckdb)
- Storage paths
- Model parameters

---

## Integration Points for Users

### Data Scientists
- Build models with YAML, implement custom logic in Python
- Use UniversalSession for cross-model queries
- Run forecasts, access measures

### Business Analysts
- Query models via Streamlit UI
- Use Markdown notebooks with dynamic filters
- Visualize cross-model relationships

### Data Engineers
- Ingest new data sources via Facet + Ingestor pattern
- Add new models by extending BaseModel
- Implement weighting strategies for complex calculations

---

## Files Reference

### YAML Configurations
- `/home/user/de_Funk/configs/models/core.yaml`
- `/home/user/de_Funk/configs/models/macro.yaml`
- `/home/user/de_Funk/configs/models/city_finance.yaml`
- `/home/user/de_Funk/configs/models/etf.yaml`
- `/home/user/de_Funk/configs/models/forecast.yaml`

### Python Implementations
- `/home/user/de_Funk/models/implemented/core/model.py`
- `/home/user/de_Funk/models/implemented/macro/model.py`
- `/home/user/de_Funk/models/implemented/city_finance/model.py`
- `/home/user/de_Funk/models/implemented/etf/model.py`
- `/home/user/de_Funk/models/implemented/forecast/company_forecast_model.py`

### Data Pipelines
- `/home/user/de_Funk/datapipelines/providers/bls/` (BLS ingestor)
- `/home/user/de_Funk/datapipelines/providers/chicago/` (Chicago ingestor)
- `/home/user/de_Funk/datapipelines/providers/polygon/` (Polygon ingestor)

### Configuration Files
- `/home/user/de_Funk/configs/storage.json` (Storage paths)
- `/home/user/de_Funk/configs/bls_endpoints.json` (BLS API auto-discovered)
- `/home/user/de_Funk/configs/chicago_endpoints.json` (Chicago API auto-discovered)
- `/home/user/de_Funk/configs/polygon_endpoints.json` (Polygon API auto-discovered)
