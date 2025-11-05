# Shared Calendar Dimension Guide

## Overview

The de_Funk platform now includes a **shared calendar dimension** (`core.dim_calendar`) that provides unified time-based querying across all models. This eliminates duplicate date logic and provides rich date attributes for analytics.

## Architecture

```
Core Model (core)
├── dim_calendar (shared calendar dimension)
│
├── Company Model (depends on core)
├── Forecast Model (depends on core, company)
├── Macro Model (depends on core)
└── City Finance Model (depends on core, macro)
```

All models now depend on the `core` model and can reference `core.dim_calendar` for time-based queries.

## Calendar Dimension Schema

The `dim_calendar` table includes **27 comprehensive date attributes**:

### Basic Attributes
- `date` - Date value (primary key)
- `year` - Year (e.g., 2024)
- `quarter` - Quarter (1-4)
- `month` - Month (1-12)
- `month_name` - Full month name (e.g., "January")
- `month_abbr` - Abbreviated month name (e.g., "Jan")

### Week Attributes
- `week_of_year` - ISO week number (1-53)
- `day_of_week` - Day of week (1=Monday, 7=Sunday)
- `day_of_week_name` - Full day name (e.g., "Monday")
- `day_of_week_abbr` - Abbreviated day name (e.g., "Mon")

### Day Attributes
- `day_of_month` - Day of month (1-31)
- `day_of_year` - Day of year (1-366)
- `days_in_month` - Number of days in the month

### Period Flags
- `is_weekend` - True if Saturday or Sunday
- `is_weekday` - True if Monday-Friday
- `is_month_start` - True if first day of month
- `is_month_end` - True if last day of month
- `is_quarter_start` - True if first day of quarter
- `is_quarter_end` - True if last day of quarter
- `is_year_start` - True if January 1
- `is_year_end` - True if December 31

### Fiscal Year Attributes
- `fiscal_year` - Fiscal year
- `fiscal_quarter` - Fiscal quarter (1-4)
- `fiscal_month` - Fiscal month (1-12)

### Formatted Strings
- `year_month` - Formatted as "YYYY-MM" (e.g., "2024-01")
- `year_quarter` - Formatted as "YYYY-Q#" (e.g., "2024-Q1")
- `date_str` - Formatted as "YYYY-MM-DD"

## Usage Examples

### 1. In Notebooks (YAML)

Use the calendar dimension directly in notebook exhibits:

```yaml
exhibits:
  - id: monthly_summary
    type: data_table
    title: "Monthly Summary"
    source: core.dim_calendar
    filters:
      year: 2024
      is_month_start: true
    columns:
      - date
      - month_name
      - year_quarter
      - is_weekend
```

### 2. In Python (UniversalSession)

Query the calendar dimension programmatically:

```python
from models.api.session import UniversalSession
from pathlib import Path
import json

# Setup
repo_root = Path.cwd()
with open(repo_root / "configs/storage.json") as f:
    storage_cfg = json.load(f)

# Create session
session = UniversalSession(
    connection=spark,
    storage_cfg=storage_cfg,
    repo_root=repo_root
)

# Get calendar data
calendar = session.get_table('core', 'dim_calendar')

# Filter to weekdays in 2024
weekdays_2024 = calendar.filter(
    (calendar.year == 2024) &
    (calendar.is_weekday == True)
)

# Get month-end dates
month_ends = calendar.filter(calendar.is_month_end == True)

# Get fiscal year data
fy_2024 = calendar.filter(calendar.fiscal_year == 2024)
```

### 3. In Models (Cross-Model Queries)

Models can reference the calendar dimension for joins:

```python
class MyModel(BaseModel):
    def get_monthly_aggregates(self, year):
        # Get calendar
        calendar = self._session.get_table('core', 'dim_calendar')

        # Get month-start dates for the year
        month_starts = calendar.filter(
            (calendar.year == year) &
            (calendar.is_month_start == True)
        )

        # Join with fact data
        fact_data = self.get_fact_df('my_fact_table')
        return fact_data.join(month_starts, on='date')
```

### 4. Time-Based Filtering

Filter data to specific time periods:

```python
# Get trading days (weekdays)
trading_days = session.get_table('core', 'dim_calendar').filter(
    lambda df: df.is_weekday == True
)

# Get quarter-end dates
quarter_ends = session.get_table('core', 'dim_calendar').filter(
    lambda df: df.is_quarter_end == True
)

# Get specific month
january_2024 = session.get_table('core', 'dim_calendar').filter(
    lambda df: (df.year == 2024) & (df.month == 1)
)
```

### 5. Fiscal Year Analysis

Use fiscal year attributes for financial reporting:

```python
# Get fiscal year 2024 data
fy2024 = calendar.filter(calendar.fiscal_year == 2024)

# Get fiscal quarter boundaries
fq_starts = calendar.filter(
    (calendar.fiscal_year == 2024) &
    (calendar.fiscal_month == 1)  # First month of each fiscal quarter
)
```

## Configuration

Calendar configuration is defined in `configs/models/core.yaml`:

```yaml
calendar_config:
  start_date: "2000-01-01"    # Calendar start date
  end_date: "2050-12-31"      # Calendar end date
  fiscal_year_start_month: 1  # Month fiscal year starts (1-12)
  weekend_days: [6, 7]        # Weekend days (1=Mon, 7=Sun)
```

## Benefits

### 1. **Single Source of Truth**
- One calendar dimension shared across all models
- Consistent date logic everywhere
- No duplicate date calculations

### 2. **Rich Date Attributes**
- 27 comprehensive date attributes
- Fiscal year support
- Period boundaries (month-end, quarter-end, etc.)
- Weekday/weekend flags

### 3. **Easy Cross-Model Joins**
- All models use the same date dimension
- Simple time-based joins across models
- Unified time filtering

### 4. **Performance**
- Pre-calculated date attributes
- No runtime date calculations
- Efficient time-based queries

### 5. **Flexibility**
- Configurable fiscal year start
- Customizable weekend days
- Easy to extend with new attributes

## Building the Calendar

The calendar dimension is automatically built when running the full pipeline:

```bash
# Build everything including calendar
python run_full_pipeline.py --top-n 100

# Build only core model (calendar)
python run_full_pipeline.py --only-core
```

Or build it manually:

```python
from models.core.builders.calendar_builder import build_calendar_table
from orchestration.common.spark_session import get_spark_session

spark = get_spark_session("BuildCalendar")

calendar_df = build_calendar_table(
    spark=spark,
    output_path="storage/bronze/calendar_seed",
    start_date="2000-01-01",
    end_date="2050-12-31",
    fiscal_year_start_month=1
)
```

## Testing

Run the comprehensive test suite:

```bash
python test_shared_calendar.py
```

This validates:
- ✓ Core model discovery
- ✓ Model dependencies on core
- ✓ Calendar schema (27 attributes)
- ✓ Calendar builder functionality
- ✓ Fiscal year calculations
- ✓ Storage configuration

## Migration Guide

### For Existing Notebooks

Update notebook YAML to reference `core.dim_calendar`:

**Before:**
```yaml
source: company.fact_prices  # Only has trade_date
```

**After:**
```yaml
source: company.fact_prices
# Join with calendar for rich date attributes
joins:
  - table: core.dim_calendar
    on: trade_date = date
```

### For Existing Models

Models automatically get access to calendar via session injection:

```python
class MyModel(BaseModel):
    def my_query(self, date_from, date_to):
        # Get calendar
        calendar = self._session.get_table('core', 'dim_calendar')

        # Use calendar attributes
        weekdays = calendar.filter(
            (calendar.date >= date_from) &
            (calendar.date <= date_to) &
            (calendar.is_weekday == True)
        )

        return weekdays
```

## Best Practices

1. **Use calendar for date filtering** instead of hard-coding date logic
2. **Reference fiscal year attributes** for financial reporting
3. **Use period flags** (is_month_end, is_quarter_end) for periodic analysis
4. **Join with calendar** to enrich fact tables with date attributes
5. **Filter to weekdays** using `is_weekday` for trading day analysis

## See Also

- `configs/models/core.yaml` - Core model configuration
- `models/core/model.py` - Core model implementation
- `models/core/builders/calendar_builder.py` - Calendar builder
- `test_shared_calendar.py` - Comprehensive test suite
- `run_full_pipeline.py` - Pipeline orchestration
