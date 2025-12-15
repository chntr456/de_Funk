# Proposal 010: Model Standardization & Chicago Economic Analysis

**Status**: Draft
**Created**: 2025-12-15
**Updated**: 2025-12-15
**Author**: Claude (AI Assistant)
**Priority**: High

---

## Executive Summary

This proposal provides a step-by-step roadmap for:

1. **Model Standardization**: Clean up inconsistencies, remove legacy code, create unified patterns
2. **Chart of Accounts Base Class**: Create inherited base class for financial models (like securities)
3. **Chicago Economic Data**: Expand data sources for municipal/economic analysis (NOT a separate model)
4. **Orchestration Improvements**: Unified build/ingest system for all models and providers
5. **Logging & Error Handling**: Document existing framework and patterns

This is a **planning document** - implementation should follow after approval.

**Key Change**: There is NO "actuarial model" - economic/municipal data feeds into existing models (macro, city_finance, company) via expanded data sources and the Chart of Accounts base class pattern.

---

## Table of Contents

1. [Current Architecture Assessment](#part-1-current-architecture-assessment)
2. [What Already Exists](#part-2-what-already-exists)
3. [Target Architecture](#part-3-target-architecture)
4. [Chart of Accounts Base Class](#part-4-chart-of-accounts-base-class)
5. [Logging & Error Handling Walkthrough](#part-5-logging-and-error-handling)
6. [Model Build Flow - Current vs Target](#part-6-model-build-flow)
7. [Ingestion Flow - Current vs Target](#part-7-ingestion-flow)
8. [Files to Remove](#part-8-files-to-remove)
9. [Files to Create](#part-9-files-to-create)
10. [Files to Modify](#part-10-files-to-modify)
11. [Step-by-Step Implementation Tasks](#part-11-step-by-step-implementation-tasks)
12. [Chicago Economic Data Sources](#part-12-chicago-economic-data-sources)

---

## Part 1: Current Architecture Assessment

### Directory Structure Rating

| Component | Rating | Key Issues |
|-----------|--------|------------|
| `configs/models/` | ⚠️ 6/10 | Mixed v1.x/v2.0 patterns, duplicate deprecated files |
| `models/implemented/` | ⚠️ 6/10 | Backend branching, inconsistent model patterns |
| `models/base/` | ✅ 8/10 | Well-structured composition, clean abstractions |
| `configs/exhibits/` | ⚠️ 5/10 | Only `great_table` has presets, others missing |
| `datapipelines/providers/` | ✅ 7/10 | Consistent facet pattern, needs registry |
| `orchestration/` | ⚠️ 5/10 | Checkpoint exists but no unified orchestrator |
| `scripts/` | ⚠️ 6/10 | Fragmented - many overlapping scripts |

### Current Model Configuration Layout

```
configs/models/
├── core.yaml              # ❌ v1.x ONLY - needs migration
├── company.yaml           # ❌ DEPRECATED - delete (v2.0 exists in company/)
├── etf.yaml               # ❌ DEPRECATED - delete (v2.0 exists in etfs/)
├── forecast.yaml          # ❌ v1.x ONLY - needs migration
├── _base/                 # ✅ Base templates for inheritance
│   └── securities/
├── company/               # ✅ v2.0 modular
├── stocks/                # ✅ v2.0 modular
├── options/               # ✅ v2.0 modular (partial implementation)
├── etfs/                  # ✅ v2.0 modular (naming: plural vs singular)
├── futures/               # ✅ v2.0 modular (skeleton)
├── macro/                 # ✅ v2.0 modular
└── city_finance/          # ✅ v2.0 modular
```

### Current Implemented Models Layout

```
models/implemented/
├── core/
│   └── model.py           # ⚠️ Spark-only, needs backend abstraction
├── company/
│   ├── model.py           # ⚠️ 6 backend if-statements
│   └── services.py        # ❌ ORPHANED - not used by model.py
├── stocks/
│   ├── model.py           # ⚠️ 9 backend if-statements
│   └── measures.py        # ⚠️ 6 backend if-statements
├── options/               # ⚠️ Skeleton only
├── etfs/                  # ⚠️ No model.py (only __init__)
├── futures/               # ⚠️ Skeleton only
├── macro/
│   └── model.py           # ✅ Relatively clean
├── city_finance/
│   └── model.py           # ✅ Current implementation
└── forecast/
    └── model.py           # ⚠️ Uses legacy patterns
```

### Key Problem: Backend Branching

**21+ instances** of backend-specific code scattered across models:

```python
# Pattern found 21+ times across codebase:
if self._backend == 'spark':
    return df.filter(df.column == value)
else:
    return df[df['column'] == value]
```

**Where it appears:**
- `models/implemented/company/model.py` - 6 instances
- `models/implemented/stocks/model.py` - 9 instances
- `models/implemented/stocks/measures.py` - 6 instances

**Root cause:** Models bypass the filter abstraction in `core/session/filters.py`

---

## Part 2: What Already Exists

Before proposing new components, it's critical to understand what's already implemented.

### Registry Classes (NOT Duplicates - Different Purposes)

| Registry | Location | Purpose | Status |
|----------|----------|---------|--------|
| `BaseRegistry` | `datapipelines/base/registry.py` | API endpoint rendering (URLs, params) | ✅ Exists |
| `AlphaVantageRegistry` | `providers/alpha_vantage/alpha_vantage_registry.py` | Alpha Vantage API endpoints | ✅ Exists |
| `BLSRegistry` | `providers/bls/bls_registry.py` | BLS API endpoints | ✅ Exists |
| `ChicagoRegistry` | `providers/chicago/chicago_registry.py` | Chicago API endpoints | ✅ Exists |
| `ModelRegistry` | `models/registry.py` | Discovers model YAMLs, instantiates model classes | ✅ Exists |
| `MeasureRegistry` | `models/base/measures/registry.py` | Measure definitions | ✅ Exists |
| `ProviderRegistry` | `datapipelines/providers/registry.py` | Discovers data **providers**, instantiates ingestors | ✅ NEW (created this session) |

**Key Distinction:**
- `BaseRegistry` + subclasses = API endpoint management (how to call APIs)
- `ModelRegistry` = Model class discovery (how to build models)
- `ProviderRegistry` = Data provider discovery (which data sources exist)

These serve **different purposes** and are NOT duplicates.

### Orchestration Components

| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| `DependencyGraph` | `orchestration/dependency_graph.py` | Model build order via topological sort | ✅ NEW (created this session) |
| `CheckpointManager` | `orchestration/checkpoint.py` | Resume from failure | ✅ Exists |
| `orchestrate.py` | `scripts/orchestrate.py` | Unified CLI | ✅ NEW (created this session) |

### Build Scripts (Current - Fragmented)

| Script | Purpose | Status |
|--------|---------|--------|
| `build_company_model.py` | Build company model only (hardcoded) | ⚠️ To deprecate |
| `build_silver_duckdb.py` | Build with DuckDB (hardcoded model list) | ⚠️ To deprecate |
| `run_full_pipeline.py` | Full pipeline (Alpha Vantage only) | ⚠️ To deprecate |
| `orchestrate.py` | Unified replacement | ✅ NEW |

### Logging Framework (Complete)

| Component | Location | Status |
|-----------|----------|--------|
| `setup_logging()` | `config/logging.py` | ✅ Complete |
| `get_logger()` | `config/logging.py` | ✅ Complete |
| `LogTimer` | `config/logging.py` | ✅ Complete |
| `ColoredFormatter` | `config/logging.py` | ✅ Complete |
| `StructuredFormatter` | `config/logging.py` | ✅ Complete (JSON) |

### Error Handling Framework (Complete)

| Component | Location | Status |
|-----------|----------|--------|
| `DeFunkError` | `core/exceptions.py` | ✅ Complete |
| `ConfigurationError` | `core/exceptions.py` | ✅ Complete |
| `ModelNotFoundError` | `core/exceptions.py` | ✅ Complete |
| `@handle_exceptions` | `core/error_handling.py` | ✅ Complete |
| `@retry_on_exception` | `core/error_handling.py` | ✅ Complete |

### Working Providers

| Provider | Status | Notes |
|----------|--------|-------|
| `alpha_vantage` | ✅ Working | Only working securities provider |
| `bls` | ⚠️ Partial | Needs testing |
| `chicago` | ⚠️ Partial | Basic budget data only |

---

## Part 3: Target Architecture

### Target Model Configuration Layout

```
configs/models/
├── _base/                 # Shared templates
│   └── securities/        # Securities base schema/graph/measures
├── core/                  # ✅ MIGRATE from v1.x
│   ├── model.yaml
│   ├── schema.yaml
│   └── graph.yaml
├── company/               # Existing v2.0
├── stocks/                # Existing v2.0
├── options/               # Complete implementation
├── etf/                   # ✅ RENAME from etfs/ (singular convention)
├── futures/               # Complete implementation
├── macro/                 # Existing v2.0
├── city_finance/          # Existing v2.0
└── forecast/              # ✅ MIGRATE from v1.x

# NOTE: No "chicago_actuarial" model - economic data feeds into
# existing models via Chart of Accounts base class pattern

# DELETED:
# - core.yaml (migrated to core/)
# - company.yaml (deprecated duplicate)
# - etf.yaml (deprecated duplicate)
# - forecast.yaml (migrated to forecast/)
```

### Target Implemented Models Layout

```
models/implemented/
├── core/
│   └── model.py           # ✅ Refactored with QueryHelper
├── company/
│   └── model.py           # ✅ Refactored - remove backend branching
├── stocks/
│   ├── model.py           # ✅ Refactored - remove backend branching
│   └── measures.py        # ✅ Refactored - remove backend branching
├── etf/                   # ✅ RENAMED from etfs/
│   ├── model.py           # ✅ NEW - actual implementation
│   └── measures.py        # ✅ NEW - Python measures
├── options/
│   ├── model.py           # ✅ NEW - actual implementation
│   └── measures.py        # ✅ NEW - Black-Scholes, Greeks
├── futures/
│   ├── model.py           # ✅ NEW - actual implementation
│   └── measures.py        # ✅ NEW - roll calculations
├── macro/
│   └── model.py           # Existing
├── city_finance/
│   └── model.py           # Existing → enhance with Chart of Accounts
└── forecast/
    └── model.py           # ✅ Refactored
```

### New Base Helper Layer

```
models/base/
├── model.py               # Existing BaseModel
├── graph_builder.py       # Existing
├── table_accessor.py      # Existing
├── measure_calculator.py  # Existing
├── model_writer.py        # Existing
├── query_helpers.py       # ✅ NEW - backend-agnostic operations
└── financial/             # ✅ NEW - Financial model base classes
    ├── __init__.py
    └── chart_of_accounts.py  # Cash flow, NPV, CAGR patterns
```

---

## Part 4: Chart of Accounts Base Class

### Concept

Just as `_base/securities/` provides inherited schema/graph/measures for stock/options/etf/futures models, we need a **`_base/financial/`** template for models dealing with:

- **Budget tracking** (city_finance)
- **Financial statements** (company income/balance/cash flow)
- **NPV, CAGR, trend calculations** (both city and company)

### Why This Pattern?

```
SECURITIES INHERITANCE (existing):
─────────────────────────────────
_base/securities/
├── schema.yaml     # OHLCV columns, ticker, asset_type
├── graph.yaml      # Price nodes, technical indicator edges
└── measures.yaml   # Returns, volatility, Sharpe ratio

↓ inherited by

stocks/   → extends _base.securities + adds company_id, shares_outstanding
options/  → extends _base.securities + adds strike, expiry, Greeks
etfs/     → extends _base.securities + adds holdings, NAV

FINANCIAL INHERITANCE (proposed):
──────────────────────────────────
_base/financial/
├── schema.yaml     # Revenue, expenses, assets, liabilities columns
├── graph.yaml      # Budget hierarchy, account structure
└── measures.yaml   # NPV, CAGR, YoY growth, variance analysis

↓ inherited by

city_finance/ → extends _base.financial + adds department, fund_type
company/      → extends _base.financial + adds CIK, ticker linkage
```

### Chart of Accounts Schema (Base Template)

```yaml
# configs/models/_base/financial/schema.yaml

dimensions:
  _dim_account:
    description: "Base account dimension for Chart of Accounts"
    columns:
      account_id: string
      account_code: string
      account_name: string
      account_type: string  # asset, liability, equity, revenue, expense
      account_category: string  # operating, capital, debt_service
      parent_account_id: string  # hierarchical rollup
      level: int  # 1=top level, 2=department, 3=line item
      is_leaf: boolean

  _dim_fiscal_period:
    description: "Fiscal period dimension (beyond calendar date)"
    columns:
      fiscal_period_id: string
      fiscal_year: int
      fiscal_quarter: int
      fiscal_month: int
      period_name: string  # "FY2024-Q1"
      is_actual: boolean  # actual vs budget/forecast

facts:
  _fact_financial_transaction:
    description: "Base fact for financial transactions"
    columns:
      transaction_id: string
      account_id: string  # FK to dim_account
      fiscal_period_id: string  # FK to dim_fiscal_period
      transaction_date: date
      amount: double
      budget_amount: double  # budgeted/planned
      variance: double  # actual - budget
      transaction_type: string  # debit, credit
```

### Chart of Accounts Measures (Base Template)

```yaml
# configs/models/_base/financial/measures.yaml

simple_measures:
  total_revenue:
    type: simple
    source: fact_financial_transaction.amount
    filters: ["account_type = 'revenue'"]
    aggregation: sum

  total_expenses:
    type: simple
    source: fact_financial_transaction.amount
    filters: ["account_type = 'expense'"]
    aggregation: sum

  net_income:
    type: computed
    formula: "total_revenue - total_expenses"

  budget_variance:
    type: simple
    source: fact_financial_transaction.variance
    aggregation: sum

python_measures:
  npv:
    function: "financial.measures.calculate_npv"
    params:
      discount_rate: 0.05

  cagr:
    function: "financial.measures.calculate_cagr"
    params:
      years: 5

  yoy_growth:
    function: "financial.measures.calculate_yoy_growth"

  trend_forecast:
    function: "financial.measures.forecast_trend"
    params:
      periods: 4
      method: "linear"  # linear, exponential, arima
```

### Python Measures Implementation

```python
# models/base/financial/measures.py

class FinancialMeasures:
    """Base class for financial model measures."""

    def calculate_npv(self, cash_flows, discount_rate=0.05, **kwargs):
        """
        Calculate Net Present Value of cash flows.

        Args:
            cash_flows: DataFrame with columns [period, amount]
            discount_rate: Annual discount rate (default 5%)

        Returns:
            NPV as float
        """
        npv = 0.0
        for i, row in enumerate(cash_flows.itertuples()):
            npv += row.amount / ((1 + discount_rate) ** i)
        return npv

    def calculate_cagr(self, df, value_col='amount', years=5, **kwargs):
        """
        Calculate Compound Annual Growth Rate.

        Args:
            df: DataFrame with time-ordered values
            value_col: Column containing values
            years: Number of years for CAGR

        Returns:
            CAGR as decimal (0.08 = 8%)
        """
        start_value = df[value_col].iloc[0]
        end_value = df[value_col].iloc[-1]

        if start_value <= 0:
            return None

        cagr = (end_value / start_value) ** (1 / years) - 1
        return cagr

    def calculate_yoy_growth(self, df, value_col='amount', date_col='fiscal_year', **kwargs):
        """
        Calculate Year-over-Year growth rates.

        Returns:
            DataFrame with yoy_growth column added
        """
        df = df.sort_values(date_col)
        df['yoy_growth'] = df[value_col].pct_change()
        return df

    def forecast_trend(self, df, value_col='amount', periods=4, method='linear', **kwargs):
        """
        Forecast future values using trend analysis.

        Args:
            df: Historical data
            value_col: Column to forecast
            periods: Number of periods to forecast
            method: 'linear', 'exponential', or 'arima'

        Returns:
            DataFrame with forecast values
        """
        import numpy as np
        from scipy import stats

        x = np.arange(len(df))
        y = df[value_col].values

        if method == 'linear':
            slope, intercept, r, p, se = stats.linregress(x, y)
            future_x = np.arange(len(df), len(df) + periods)
            forecast = slope * future_x + intercept
        elif method == 'exponential':
            log_y = np.log(y[y > 0])
            slope, intercept, r, p, se = stats.linregress(x[:len(log_y)], log_y)
            future_x = np.arange(len(df), len(df) + periods)
            forecast = np.exp(slope * future_x + intercept)
        else:
            # ARIMA requires statsmodels
            from statsmodels.tsa.arima.model import ARIMA
            model = ARIMA(y, order=(1, 1, 1))
            fitted = model.fit()
            forecast = fitted.forecast(steps=periods)

        return forecast
```

### How Models Inherit

**city_finance model (example):**

```yaml
# configs/models/city_finance/model.yaml
model: city_finance
version: 2.0
inherits_from: _base.financial  # ← KEY INHERITANCE

components:
  schema: city_finance/schema.yaml
  graph: city_finance/graph.yaml
  measures: city_finance/measures.yaml

depends_on: [core, geography]
```

```yaml
# configs/models/city_finance/schema.yaml
extends: _base.financial.schema

dimensions:
  dim_department:
    extends: _base.financial._dim_account
    columns:
      # Inherited: account_id, account_code, account_name, account_type, etc.
      department_code: string  # Added
      fund_type: string  # corporate, enterprise, special
      appropriation_authority: string

  dim_fiscal_period:
    extends: _base.financial._dim_fiscal_period
    columns:
      # Inherited: fiscal_year, fiscal_quarter, etc.
      chicago_fiscal_year: string  # "FY2024" (Jan-Dec for Chicago)

facts:
  fact_budget_line_item:
    extends: _base.financial._fact_financial_transaction
    columns:
      # Inherited: transaction_id, account_id, fiscal_period_id, amount, etc.
      appropriation_amount: double
      expenditure_actual: double
      encumbrance: double
```

**company model (example):**

```yaml
# configs/models/company/model.yaml
model: company
version: 2.0
inherits_from: _base.financial  # ← KEY INHERITANCE (NEW)

# Also inherits fundamentals from Alpha Vantage
depends_on: [core]
```

```yaml
# configs/models/company/schema.yaml
extends: _base.financial.schema

facts:
  fact_income_statement:
    extends: _base.financial._fact_financial_transaction
    columns:
      # Inherited base columns
      cik: string  # SEC CIK identifier
      ticker: string  # Stock ticker
      fiscal_date_ending: date
      reported_currency: string
      total_revenue: double
      cost_of_revenue: double
      gross_profit: double
      operating_income: double
      net_income: double
      # etc.
```

---

## Part 5: Logging & Error Handling Walkthrough

### Logging Framework (config/logging.py)

The codebase has a **complete logging framework** - use it instead of print statements.

#### Setup (Once at Script Start)

```python
from config.logging import setup_logging, get_logger

# Call once at script entry point
setup_logging()

# Get module-specific logger
logger = get_logger(__name__)
```

#### Log Levels and When to Use

```python
# DEBUG: Detailed info for debugging (file only by default)
logger.debug(f"Processing row {i}: {row}")

# INFO: Normal operation progress (console + file)
logger.info(f"Processing {ticker}")

# WARNING: Issues that don't stop execution
logger.warning(f"Rate limit reached, waiting 60s")

# ERROR: Failures with stack traces
logger.error(f"Failed to process {ticker}", exc_info=True)

# CRITICAL: System is unusable
logger.critical(f"Database connection lost")
```

#### LogTimer for Timing Operations

```python
from config.logging import LogTimer

# Automatic timing with logging
with LogTimer(logger, "Building model"):
    model.build()
# Output: "Starting: Building model"
# Output: "Completed: Building model (2350.45ms)"

# With context
with LogTimer(logger, "Processing ticker", ticker="AAPL"):
    process(ticker)
```

#### Configuration via Environment

```bash
# .env file
LOG_LEVEL=DEBUG           # Console level
LOG_FILE_LEVEL=DEBUG      # File level (default: DEBUG)
LOG_DIR=logs/             # Log directory
LOG_JSON=true             # Enable JSON structured logging
```

#### Log File Location

- Main log: `logs/de_funk.log`
- JSON log: `logs/de_funk.json` (if enabled)
- Rotation: 10MB max, 5 file rotation

### Error Handling Framework (core/exceptions.py)

#### Exception Hierarchy

```python
from core.exceptions import (
    DeFunkError,           # Base class for all de_Funk errors
    ConfigurationError,    # Config loading issues
    ModelNotFoundError,    # Model doesn't exist
    MeasureError,          # Measure calculation failed
    RateLimitError,        # API rate limit exceeded
    IngestionError,        # Data ingestion failed
)

# All exceptions include recovery hints
try:
    model = registry.get_model("stocks")
except ModelNotFoundError as e:
    print(e)              # "Model not found: 'stocks'"
    print(e.recovery_hint)  # "Available models: core, company"
    print(e.details)       # {'model': 'stocks', 'available': [...]}
```

#### Error Handling Decorators (core/error_handling.py)

```python
from core.error_handling import handle_exceptions, retry_on_exception, safe_call

# Automatic error handling with default return
@handle_exceptions(ValueError, TypeError, default_return=None)
def parse_config(data):
    return json.loads(data)

# Automatic retry with exponential backoff
@retry_on_exception(ConnectionError, max_retries=3, delay_seconds=1.0)
def fetch_api_data(url):
    return requests.get(url)

# Safe function call with default
result = safe_call(risky_function, default="fallback_value")
```

### Recommended Pattern for New Scripts

```python
#!/usr/bin/env python
"""Script description."""
from __future__ import annotations

import sys
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger, LogTimer
from core.exceptions import DeFunkError

logger = get_logger(__name__)


def main():
    setup_logging()

    try:
        with LogTimer(logger, "Running pipeline"):
            # Main logic here
            pass

        logger.info("Pipeline completed successfully")
        return 0

    except DeFunkError as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        logger.info(f"Recovery hint: {e.recovery_hint}")
        return 1

    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

---

## Part 6: Model Build Flow

### Current Flow (Fragmented)

**Note**: The build scripts (`build_company_model.py`, `build_silver_duckdb.py`) have hardcoded model lists and manual imports. The new `orchestrate.py` CLI fixes this.

```
┌─────────────────────────────────────────────────────────────────┐
│                     CURRENT BUILD FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Entry Points (FRAGMENTED):                                     │
│  ┌────────────────────┐  ┌────────────────────┐                │
│  │ run_full_pipeline  │  │ build_silver_duckdb│                │
│  │ .py                │  │ .py                │                │
│  └─────────┬──────────┘  └─────────┬──────────┘                │
│            │                       │                            │
│  ┌─────────┴──────────┐  ┌────────┴───────────┐                │
│  │ build_company_     │  │ rebuild_model.py   │                │
│  │ model.py           │  │                    │                │
│  └─────────┬──────────┘  └────────┬───────────┘                │
│            │                       │                            │
│            └───────────┬───────────┘                            │
│                        ▼                                        │
│           ┌────────────────────────┐                            │
│           │  HARDCODED MODEL LIST  │  ← Problem: Not dynamic    │
│           │  ['stocks', 'company'] │                            │
│           └────────────┬───────────┘                            │
│                        │                                        │
│                        ▼                                        │
│           ┌────────────────────────┐                            │
│           │  Import Model Class    │  ← Problem: Manual imports │
│           │  Directly              │                            │
│           └────────────┬───────────┘                            │
│                        │                                        │
│                        ▼                                        │
│           ┌────────────────────────┐                            │
│           │  model.build()         │                            │
│           │  model.write_tables()  │                            │
│           └────────────────────────┘                            │
│                                                                 │
│  Problems:                                                      │
│  1. Multiple entry points - confusing                           │
│  2. Hardcoded model lists - not extensible                      │
│  3. No dependency resolution - manual ordering                  │
│  4. No checkpoint/resume - starts from scratch                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Target Flow (Unified)

```
┌─────────────────────────────────────────────────────────────────┐
│                     TARGET BUILD FLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Single Entry Point:                                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  python -m scripts.orchestrate --models stocks --build-only │ │
│  │  python -m scripts.orchestrate --all                        │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                 │
│                               ▼                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    ORCHESTRATOR                             │ │
│  │  scripts/orchestrate.py                                     │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                 │
│         ┌─────────────────────┼─────────────────────┐           │
│         │                     │                     │           │
│         ▼                     ▼                     ▼           │
│  ┌──────────────┐    ┌───────────────┐    ┌───────────────────┐ │
│  │ Dependency   │    │ Checkpoint    │    │ Provider          │ │
│  │ Graph        │    │ Manager       │    │ Registry          │ │
│  │              │    │               │    │                   │ │
│  │ Reads YAML   │    │ Resume from   │    │ Discovers         │ │
│  │ depends_on   │    │ failure       │    │ providers         │ │
│  │              │    │               │    │                   │ │
│  │ Topological  │    │ Tracks        │    │ Knows which       │ │
│  │ Sort         │    │ progress      │    │ models each feeds │ │
│  └──────┬───────┘    └───────────────┘    └───────────────────┘ │
│         │                                                       │
│         │  Returns ordered list:                                │
│         │  [core, company, stocks] (auto-resolved)              │
│         │                                                       │
│         ▼                                                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    MODEL BUILDER                            │ │
│  │  orchestration/builders/model_builder.py (NEW)              │ │
│  │                                                             │ │
│  │  1. Load model config from configs/models/{name}/           │ │
│  │  2. Dynamically import model class                          │ │
│  │  3. Call model.build()                                      │ │
│  │  4. Call model.write_tables()                               │ │
│  │  5. Update checkpoint                                       │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                 │
│                               ▼                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    MODEL CLASS                              │ │
│  │  models/implemented/{name}/model.py                         │ │
│  │                                                             │ │
│  │  Inherits: BaseModel                                        │ │
│  │  Uses: QueryHelper (no backend branching)                   │ │
│  │                                                             │ │
│  │  build() → returns (dimensions, facts)                      │ │
│  │  write_tables() → persists to silver layer                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Model Class Location Decision

**Question:** Where does the build code for a single model live?

**Answer:**

```
┌────────────────────────────────────────────────────────────────────┐
│                    MODEL BUILD CODE LOCATION                        │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  CONFIGURATION (What to build):                                    │
│  configs/models/{model_name}/                                      │
│  ├── model.yaml       # Metadata, dependencies, storage config     │
│  ├── schema.yaml      # Table definitions (dims, facts, columns)   │
│  ├── graph.yaml       # Node/edge/path definitions                 │
│  └── measures.yaml    # Measure definitions (simple + Python refs) │
│                                                                    │
│  IMPLEMENTATION (How to build):                                    │
│  models/implemented/{model_name}/                                  │
│  ├── model.py         # Model class extending BaseModel            │
│  │                    # Contains: build(), custom methods          │
│  └── measures.py      # Python measures (complex calculations)     │
│                                                                    │
│  BASE FRAMEWORK (Shared logic):                                    │
│  models/base/                                                      │
│  ├── model.py         # BaseModel - orchestrates build process     │
│  ├── graph_builder.py # Builds graph from YAML config              │
│  ├── table_accessor.py# Reads tables from bronze/silver            │
│  ├── model_writer.py  # Writes tables to silver layer              │
│  └── query_helpers.py # Backend-agnostic operations (NEW)          │
│                                                                    │
│  ORCHESTRATION (When/order to build):                              │
│  orchestration/                                                    │
│  ├── dependency_graph.py  # Resolves build order                   │
│  ├── checkpoint.py        # Tracks progress, enables resume        │
│  └── builders/                                                     │
│      └── model_builder.py # Builds single model (NEW)              │
│                                                                    │
│  ENTRY POINT (User interface):                                     │
│  scripts/orchestrate.py   # Unified CLI                            │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Part 4: Ingestion Flow

### Current Flow (Fragmented)

```
┌─────────────────────────────────────────────────────────────────┐
│                   CURRENT INGESTION FLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Entry Points (MULTIPLE):                                       │
│  ┌────────────────────┐                                         │
│  │ run_full_pipeline  │ ← Only Alpha Vantage hardcoded          │
│  │ .py                │                                         │
│  └─────────┬──────────┘                                         │
│            │                                                    │
│            ▼                                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  HARDCODED PROVIDER                                         │ │
│  │  from datapipelines.providers.alpha_vantage import ...     │ │
│  │                                                             │ │
│  │  Problems:                                                  │ │
│  │  - Chicago/BLS ingestion not integrated                    │ │
│  │  - No provider discovery                                   │ │
│  │  - Can't select which providers to run                     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Separate Scripts (NOT INTEGRATED):                             │
│  - Chicago: No unified entry point                              │
│  - BLS: No unified entry point                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Target Flow (Unified)

```
┌─────────────────────────────────────────────────────────────────┐
│                   TARGET INGESTION FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Single Entry Point:                                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  python -m scripts.orchestrate --providers chicago         │ │
│  │  python -m scripts.orchestrate --providers all --ingest    │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                 │
│                               ▼                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                  PROVIDER REGISTRY                          │ │
│  │  datapipelines/providers/registry.py                        │ │
│  │                                                             │ │
│  │  Discovers from provider.yaml files:                        │ │
│  │  - alpha_vantage → feeds: stocks, company                   │ │
│  │  - bls → feeds: macro                                       │ │
│  │  - chicago → feeds: city_finance                            │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                 │
│         ┌─────────────────────┼─────────────────────┐           │
│         │                     │                     │           │
│         ▼                     ▼                     ▼           │
│  ┌──────────────┐    ┌───────────────┐    ┌───────────────────┐ │
│  │ Alpha        │    │ BLS           │    │ Chicago           │ │
│  │ Vantage      │    │ Ingestor      │    │ Ingestor          │ │
│  │ Ingestor     │    │               │    │                   │ │
│  │              │    │ Endpoint:     │    │ Endpoints:        │ │
│  │ Endpoints:   │    │ - series_data │    │ - budget          │ │
│  │ - overview   │    │ - catalog     │    │ - employees       │ │
│  │ - prices     │    │               │    │ - contracts       │ │
│  │ - income     │    │ Facets:       │    │ - tax_assessment  │ │
│  │ - balance    │    │ - BLSSeries   │    │ - community_areas │ │
│  │ - cash_flow  │    │               │    │                   │ │
│  │ - earnings   │    │               │    │ Facets:           │ │
│  │              │    │               │    │ - ChicagoBudget   │ │
│  │ Facets:      │    │               │    │ - TaxAssessment   │ │
│  │ - Reference  │    │               │    │ - CommunityArea   │ │
│  │ - Prices     │    │               │    │                   │ │
│  │ - Income     │    │               │    │                   │ │
│  │ etc.         │    │               │    │                   │ │
│  └──────┬───────┘    └───────┬───────┘    └─────────┬─────────┘ │
│         │                    │                      │           │
│         └────────────────────┼──────────────────────┘           │
│                              ▼                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    BRONZE SINK                              │ │
│  │  datapipelines/ingestors/bronze_sink.py                     │ │
│  │                                                             │ │
│  │  Writes to: storage/bronze/{provider}/{table}/              │ │
│  │  Format: Delta Lake (ACID, time travel, schema evolution)   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Provider-to-Model Mapping

```
┌────────────────────────────────────────────────────────────────────┐
│                  PROVIDER → MODEL RELATIONSHIP                      │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Provider          Bronze Tables              Models Fed           │
│  ──────────────────────────────────────────────────────────────── │
│  alpha_vantage  →  securities_reference    →  stocks, company      │
│                    securities_prices_daily →  stocks               │
│                    income_statements       →  company              │
│                    balance_sheets          →  company              │
│                    cash_flows              →  company              │
│                    earnings                →  company              │
│                                                                    │
│  bls            →  bls_series_data         →  macro                │
│                    bls_series_catalog      →  macro                │
│                                                                    │
│  chicago        →  chicago_budget          →  city_finance         │
│                    chicago_employees       →  city_finance         │
│                    chicago_contracts       →  city_finance         │
│                    chicago_tax_assessment  →  city_finance (future)│
│                    chicago_community_areas →  city_finance (future)│
│                                                                    │
│  Encoded in: datapipelines/providers/{name}/provider.yaml          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Part 5: Files to Remove

| File | Reason | Action |
|------|--------|--------|
| `configs/models/company.yaml` | Deprecated v1.x, v2.0 exists in `company/` | DELETE |
| `configs/models/etf.yaml` | Deprecated v1.x, v2.0 exists in `etfs/` | DELETE |
| `models/implemented/company/services.py` | Orphaned - not used by model.py | DELETE |
| `scripts/build_company_model.py` | Fragmented - use orchestrate.py | DELETE after migration |
| `scripts/build_silver_duckdb.py` | Fragmented - use orchestrate.py | DELETE after migration |

**Note:** Keep `run_full_pipeline.py` temporarily as deprecated wrapper, then delete.

---

## Part 6: Files to Create

### New Files Needed

| File | Purpose | Priority |
|------|---------|----------|
| `configs/models/core/model.yaml` | v2.0 modular config for core | High |
| `configs/models/core/schema.yaml` | Core schema definition | High |
| `configs/models/core/graph.yaml` | Core graph definition | High |
| `configs/models/forecast/model.yaml` | v2.0 modular config for forecast | Medium |
| `configs/models/forecast/schema.yaml` | Forecast schema | Medium |
| `configs/models/forecast/graph.yaml` | Forecast graph | Medium |
| `configs/models/_base/financial/schema.yaml` | Chart of Accounts base schema | High |
| `configs/models/_base/financial/graph.yaml` | Financial model graph base | High |
| `configs/models/_base/financial/measures.yaml` | NPV, CAGR, YoY measures | High |
| `models/base/financial/__init__.py` | Financial measures package | High |
| `models/base/financial/measures.py` | NPV, CAGR Python implementations | High |
| `models/implemented/etf/model.py` | ETF model implementation | Medium |
| `models/implemented/etf/measures.py` | ETF Python measures | Medium |
| `models/implemented/options/model.py` | Options model implementation | Medium |
| `models/implemented/options/measures.py` | Options Python measures | Medium |
| `models/implemented/futures/model.py` | Futures model implementation | Low |
| `models/implemented/futures/measures.py` | Futures Python measures | Low |
| `models/base/query_helpers.py` | Backend-agnostic query operations | High |
| `orchestration/builders/model_builder.py` | Single model build logic | High |
| `datapipelines/providers/chicago/facets/tax_assessment.py` | Tax assessment facet | High |
| `datapipelines/providers/chicago/facets/community_area.py` | Community area facet | High |
| `configs/exhibits/presets/base_exhibit.yaml` | Base exhibit defaults | Medium |
| `configs/exhibits/presets/markdown.yaml` | Markdown exhibit config | Medium |

---

## Part 7: Files to Modify

### Refactoring Required

| File | Changes Needed | Effort |
|------|----------------|--------|
| `models/implemented/company/model.py` | Replace 6 backend if-statements with QueryHelper | 2 hrs |
| `models/implemented/stocks/model.py` | Replace 9 backend if-statements with QueryHelper | 3 hrs |
| `models/implemented/stocks/measures.py` | Replace 6 backend if-statements with QueryHelper | 2 hrs |
| `models/implemented/core/model.py` | Add DuckDB support via QueryHelper | 2 hrs |
| `configs/models/etfs/` | Rename to `etf/` (singular convention) | 1 hr |
| `scripts/run_full_pipeline.py` | Add deprecation warning, delegate to orchestrate.py | 1 hr |

---

## Part 8: Step-by-Step Implementation Tasks

### Phase 1: Cleanup (Day 1)

**Goal:** Remove deprecated files, fix naming inconsistencies

| # | Task | Files Affected |
|---|------|----------------|
| 1.1 | Delete deprecated v1.x YAML files | `configs/models/company.yaml`, `etf.yaml` |
| 1.2 | Delete orphaned services file | `models/implemented/company/services.py` |
| 1.3 | Rename `etfs/` to `etf/` for consistency | `configs/models/etfs/` → `etf/` |
| 1.4 | Update any imports referencing renamed dirs | Search and replace |

### Phase 2: Backend Abstraction (Days 2-3)

**Goal:** Eliminate backend branching in model implementations

| # | Task | Files Affected |
|---|------|----------------|
| 2.1 | Create QueryHelper class | NEW: `models/base/query_helpers.py` |
| 2.2 | Refactor CompanyModel to use QueryHelper | `models/implemented/company/model.py` |
| 2.3 | Refactor StocksModel to use QueryHelper | `models/implemented/stocks/model.py` |
| 2.4 | Refactor StocksMeasures to use QueryHelper | `models/implemented/stocks/measures.py` |
| 2.5 | Refactor CoreModel to use QueryHelper | `models/implemented/core/model.py` |
| 2.6 | Test all models with both backends | Run test suite |

### Phase 3: Configuration Standardization (Days 4-6)

**Goal:** All configs use v2.0 modular YAML pattern + complete exhibit presets

| # | Task | Files Affected |
|---|------|----------------|
| 3.1 | Create `core/` modular config from core.yaml | NEW: `configs/models/core/*.yaml` |
| 3.2 | Create `forecast/` modular config from forecast.yaml | NEW: `configs/models/forecast/*.yaml` |
| 3.3 | Delete old v1.x files after migration | DELETE: `core.yaml`, `forecast.yaml` |
| 3.4 | Update ModelConfigLoader if needed | `config/model_loader.py` |
| 3.5 | Create base exhibit preset | NEW: `configs/exhibits/presets/base_exhibit.yaml` |
| 3.6 | Create markdown exhibit preset | NEW: `configs/exhibits/presets/markdown.yaml` |
| 3.7 | Create grid exhibit preset | NEW: `configs/exhibits/presets/grid.yaml` |
| 3.8 | Update exhibit registry | `configs/exhibits/registry.yaml` |

### Phase 4: Core Geography Model (Days 7-9)

**Goal:** Foundational geography dimension for all location-based analysis

| # | Task | Files Affected |
|---|------|----------------|
| 4.1 | Create geography model config | NEW: `configs/models/geography/*.yaml` |
| 4.2 | Define dim_geography (multi-level) | schema.yaml |
| 4.3 | Define dim_census_tract | schema.yaml |
| 4.4 | Define dim_zip_code | schema.yaml |
| 4.5 | Create GeographyModel class | NEW: `models/implemented/geography/model.py` |
| 4.6 | Create Census data provider | NEW: `datapipelines/providers/census/` |
| 4.7 | Create geography facets | NEW: `census/facets/geography.py` |

**Geography Hierarchy:**
```
State (Illinois)
  └── County (Cook)
       └── City (Chicago)
            └── Community Area (77 areas)
                 └── Census Tract (~800 tracts)
                      └── Block Group
```

### Phase 5: Orchestration Layer (Days 10-11)

**Goal:** Unified build/ingest system

| # | Task | Files Affected |
|---|------|----------------|
| 5.1 | Create DependencyGraph class | NEW: `orchestration/dependency_graph.py` |
| 5.2 | Create ProviderRegistry class | NEW: `datapipelines/providers/registry.py` |
| 5.3 | Create provider.yaml for each provider | NEW: `providers/{name}/provider.yaml` |
| 5.4 | Create model_builder module | NEW: `orchestration/builders/model_builder.py` |
| 5.5 | Create unified orchestrate.py CLI | NEW: `scripts/orchestrate.py` |
| 5.6 | Deprecate old scripts | Add warnings to old scripts |

### Phase 6: Economic Series Model (Days 12-18)

**Goal:** Generalized time series model for federal/state economic data

This phase creates a **reusable series model** that can ingest time series data from multiple federal and state sources. This is foundational for the Chicago actuarial analysis.

| # | Task | Files Affected |
|---|------|----------------|
| 6.1 | Create series model config | NEW: `configs/models/economic_series/*.yaml` |
| 6.2 | Create FRED provider | NEW: `datapipelines/providers/fred/` |
| 6.3 | Create BEA provider | NEW: `datapipelines/providers/bea/` |
| 6.4 | Create Census ACS provider | NEW: `datapipelines/providers/census_acs/` |
| 6.5 | Create EconomicSeriesModel class | NEW: `models/implemented/economic_series/model.py` |
| 6.6 | Define series catalog dimension | schema.yaml |
| 6.7 | Define series observations fact | schema.yaml |
| 6.8 | Create series measures | measures.py |

**Series Model Schema:**
```
dim_series_catalog
├── series_id (PK)
├── source (FRED, BEA, BLS, Census)
├── series_name
├── frequency (daily, monthly, quarterly, annual)
├── units
├── seasonal_adjustment
└── geography_level (national, state, metro, county)

fact_series_observation
├── observation_id (PK)
├── series_id (FK)
├── observation_date
├── value
├── revision_date
└── vintage
```

### Phase 7: Chart of Accounts Base Class (Days 19-24)

**Goal:** Implement shared financial model base for city_finance and company

| # | Task | Files Affected |
|---|------|----------------|
| 7.1 | Create _base/financial config templates | NEW: `configs/models/_base/financial/*.yaml` |
| 7.2 | Create FinancialMeasures base class | NEW: `models/base/financial/measures.py` |
| 7.3 | Update city_finance to inherit from _base.financial | `configs/models/city_finance/*.yaml` |
| 7.4 | Update company to inherit from _base.financial | `configs/models/company/*.yaml` |
| 7.5 | Add NPV, CAGR, YoY measures to financial base | `measures.py` |
| 7.6 | Test inheritance works correctly | Run test suite |
| 7.7 | Update company model for financial statements | `company/model.py` |

### Phase 8: Complete Missing Securities Models (Days 25-31)

**Goal:** All securities models have working implementations

| # | Task | Files Affected |
|---|------|----------------|
| 8.1 | Implement ETF model | NEW: `models/implemented/etf/model.py`, `measures.py` |
| 8.2 | Implement Options model | NEW: `models/implemented/options/model.py`, `measures.py` |
| 8.3 | Implement Futures model | NEW: `models/implemented/futures/model.py`, `measures.py` |
| 8.4 | Test all model builds | Run orchestrate.py --all |

---

## Part 12: Chicago Economic Data Sources

### Comprehensive Data Source Inventory

**Note**: These data sources feed into **existing models** (city_finance, macro, company) via the Chart of Accounts pattern. There is no separate "actuarial model" - this is economic data composition.

The Chicago economic analysis requires data from **multiple government levels**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA SOURCE HIERARCHY                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  FEDERAL SOURCES                                                    │
│  ════════════════                                                   │
│  Bureau of Economic Analysis (BEA)                                  │
│  ├── GDP by metro area (Chicago-Naperville-Elgin MSA)              │
│  ├── Personal income by county                                      │
│  ├── Regional price parities                                        │
│  └── Industry employment by region                                  │
│                                                                     │
│  Federal Reserve (FRED)                                             │
│  ├── Interest rates (Fed Funds, Treasury yields)                   │
│  ├── Inflation expectations                                         │
│  ├── Municipal bond indices                                         │
│  ├── Chicago metro unemployment rate                                │
│  └── Housing price indices (Case-Shiller Chicago)                  │
│                                                                     │
│  Census Bureau                                                      │
│  ├── Decennial Census (population, demographics)                   │
│  ├── American Community Survey (ACS) - annual estimates            │
│  │   ├── Population by tract/block group                           │
│  │   ├── Median household income                                   │
│  │   ├── Age distribution                                          │
│  │   ├── Housing characteristics                                   │
│  │   └── Migration flows                                           │
│  └── County Business Patterns (employment, establishments)         │
│                                                                     │
│  Bureau of Labor Statistics (BLS) - EXISTING                       │
│  ├── Employment by industry (Chicago MSA)                          │
│  ├── Consumer Price Index (CPI-U Chicago)                          │
│  ├── Quarterly Census of Employment and Wages                      │
│  └── Occupational Employment and Wage Statistics                   │
│                                                                     │
│  Treasury Department                                                │
│  ├── Municipal bond yields                                         │
│  └── State & local government finances                             │
│                                                                     │
│  STATE OF ILLINOIS                                                  │
│  ═════════════════                                                  │
│  Illinois Department of Revenue                                     │
│  ├── Income tax collections by county                              │
│  ├── Sales tax distributions                                       │
│  └── Property tax statistics                                       │
│                                                                     │
│  Illinois Comptroller                                               │
│  ├── State payments to Chicago                                     │
│  ├── Intergovernmental transfers                                   │
│  └── Warehouse financial data                                      │
│                                                                     │
│  COOK COUNTY                                                        │
│  ═══════════                                                        │
│  Cook County Assessor's Office                                      │
│  ├── Property assessments (all parcels)                            │
│  ├── Assessment appeals                                            │
│  ├── Property characteristics                                       │
│  ├── Sales data (for ratio studies)                                │
│  └── Exemptions (homeowner, senior, disabled)                      │
│                                                                     │
│  Cook County Treasurer                                              │
│  ├── Tax rates by taxing district                                  │
│  ├── Tax collections and delinquencies                             │
│  ├── Tax increment financing (TIF) districts                       │
│  └── Payment status                                                │
│                                                                     │
│  Cook County Clerk                                                  │
│  ├── Property tax extensions                                       │
│  ├── Tax code rates                                                │
│  └── Taxing district levies                                        │
│                                                                     │
│  CITY OF CHICAGO - EXISTING + EXPANDED                             │
│  ════════════════════════════════════                               │
│  Chicago Data Portal (Existing)                                     │
│  ├── Budget appropriations                                         │
│  ├── Employee salaries                                             │
│  ├── Contracts                                                     │
│  └── Various operational data                                      │
│                                                                     │
│  Chicago Data Portal (To Add)                                       │
│  ├── Building permits                                              │
│  ├── Business licenses                                             │
│  ├── TIF district reports                                          │
│  └── Capital improvement plans                                     │
│                                                                     │
│  Chicago Pension Funds (4 funds)                                   │
│  ├── Municipal Employees (MEABF)                                   │
│  ├── Police                                                        │
│  ├── Fire                                                          │
│  └── Laborers                                                      │
│  Data: Assets, liabilities, funded ratios, contributions           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Source Details

#### Federal Sources

| Source | API/Method | Key Series | Frequency |
|--------|------------|------------|-----------|
| **FRED** | REST API | FEDFUNDS, DGS10, CHIURN, CHXRSA | Daily/Monthly |
| **BEA** | REST API | CAGDP2 (GDP by metro), CAINC1 (personal income) | Annual/Quarterly |
| **Census ACS** | REST API | B01001 (pop), B19013 (income), B25001 (housing) | Annual (1yr/5yr) |
| **BLS** | REST API (existing) | LAUCN170310000000003 (Chicago unemp) | Monthly |
| **Treasury** | CSV downloads | Municipal yields, state finances | Monthly/Annual |

#### State of Illinois Sources

| Source | API/Method | Key Data | Frequency |
|--------|------------|----------|-----------|
| **IL Dept of Revenue** | Data portal | Tax collections, distributions | Monthly/Annual |
| **IL Comptroller** | Warehouse API | State payments, transfers | Annual |

#### Cook County Sources

| Source | API/Method | Key Data | Frequency |
|--------|------------|----------|-----------|
| **Assessor** | Data portal / bulk | Parcel assessments, sales, appeals | Triennial + updates |
| **Treasurer** | Data portal | Tax rates, collections, delinquencies | Annual |
| **Clerk** | Data portal | Extensions, levies | Annual |

#### Chicago Sources

| Source | Socrata ID | Key Data | Frequency |
|--------|------------|----------|-----------|
| **Budget** | `g867-z4xg` | Appropriations by dept | Annual |
| **Salaries** | `xzkq-xp2w` | Employee compensation | Annual |
| **Contracts** | `rsxa-ify5` | Vendor contracts | Ongoing |
| **Building Permits** | `ydr8-5enu` | Construction activity | Daily |
| **Business Licenses** | `r5kz-chrr` | Business formation | Daily |
| **TIF Reports** | Multiple | TIF district finances | Annual |
| **Pension CAFRs** | Manual/PDF | Fund financials | Annual |

### Provider Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    NEW PROVIDERS NEEDED                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  datapipelines/providers/                                           │
│  ├── alpha_vantage/     # EXISTING - securities                    │
│  ├── bls/               # EXISTING - employment, CPI               │
│  ├── chicago/           # EXISTING - city data portal              │
│  │                                                                  │
│  ├── fred/              # NEW - Federal Reserve Economic Data      │
│  │   ├── provider.yaml                                             │
│  │   ├── fred_ingestor.py                                          │
│  │   └── facets/                                                   │
│  │       ├── interest_rates.py                                     │
│  │       ├── housing_indices.py                                    │
│  │       └── regional_indicators.py                                │
│  │                                                                  │
│  ├── bea/               # NEW - Bureau of Economic Analysis        │
│  │   ├── provider.yaml                                             │
│  │   ├── bea_ingestor.py                                           │
│  │   └── facets/                                                   │
│  │       ├── regional_gdp.py                                       │
│  │       └── personal_income.py                                    │
│  │                                                                  │
│  ├── census/            # NEW - Census Bureau                      │
│  │   ├── provider.yaml                                             │
│  │   ├── census_ingestor.py                                        │
│  │   └── facets/                                                   │
│  │       ├── geography.py        # Geography hierarchies           │
│  │       ├── population.py       # Decennial/ACS population        │
│  │       ├── demographics.py     # Age, race, housing              │
│  │       └── economics.py        # Income, employment              │
│  │                                                                  │
│  ├── cook_county/       # NEW - Cook County Assessor/Treasurer     │
│  │   ├── provider.yaml                                             │
│  │   ├── cook_county_ingestor.py                                   │
│  │   └── facets/                                                   │
│  │       ├── assessments.py      # Property assessments            │
│  │       ├── parcels.py          # Parcel characteristics          │
│  │       ├── sales.py            # Property sales                  │
│  │       ├── tax_rates.py        # Tax rates by district           │
│  │       └── collections.py      # Tax collections                 │
│  │                                                                  │
│  └── illinois/          # NEW - State of Illinois                  │
│      ├── provider.yaml                                             │
│      ├── illinois_ingestor.py                                      │
│      └── facets/                                                   │
│          ├── tax_revenue.py      # State tax collections           │
│          └── transfers.py        # Intergovernmental transfers     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Schema Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                 CHICAGO ACTUARIAL SCHEMA                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  DIMENSIONS (from geography model):                                 │
│  ─────────────────────────────────                                  │
│  dim_geography (inherited - 77 Chicago community areas + hierarchy)│
│  dim_census_tract (inherited - ~800 Chicago census tracts)         │
│                                                                     │
│  DIMENSIONS (chicago_actuarial specific):                          │
│  ─────────────────────────────────────────                          │
│  dim_property_class                                                │
│  ├── property_class_id (PK)                                        │
│  ├── class_code (2-00, 2-11, etc.)                                │
│  ├── class_description                                             │
│  ├── assessment_level (10%, 25%, etc.)                            │
│  └── property_type (residential, commercial, industrial)           │
│                                                                     │
│  dim_taxing_district                                               │
│  ├── district_id (PK)                                              │
│  ├── district_name                                                 │
│  ├── district_type (city, county, school, park, etc.)             │
│  └── tax_code                                                      │
│                                                                     │
│  dim_pension_fund                                                  │
│  ├── fund_id (PK)                                                  │
│  ├── fund_name (MEABF, Police, Fire, Laborers)                    │
│  ├── tier (Tier 1, Tier 2)                                        │
│  └── governing_statute                                             │
│                                                                     │
│  dim_department                                                    │
│  ├── department_id (PK)                                            │
│  ├── department_code                                               │
│  ├── department_name                                               │
│  └── fund_type (corporate, enterprise, special)                    │
│                                                                     │
│  FACTS:                                                            │
│  ──────                                                             │
│  fact_parcel_assessment                                            │
│  ├── parcel_id (PK)                                                │
│  ├── pin (property index number)                                   │
│  ├── community_area_id (FK)                                        │
│  ├── census_tract_id (FK)                                          │
│  ├── property_class_id (FK)                                        │
│  ├── assessment_year                                               │
│  ├── land_assessed_value                                           │
│  ├── building_assessed_value                                       │
│  ├── total_assessed_value                                          │
│  ├── market_value_estimate                                         │
│  └── exemption_amount                                              │
│                                                                     │
│  fact_tax_bill                                                     │
│  ├── tax_bill_id (PK)                                              │
│  ├── parcel_id (FK)                                                │
│  ├── tax_year                                                      │
│  ├── district_id (FK)                                              │
│  ├── tax_amount                                                    │
│  ├── paid_amount                                                   │
│  └── delinquent_flag                                               │
│                                                                     │
│  fact_pension_status                                               │
│  ├── pension_id (PK)                                               │
│  ├── fund_id (FK)                                                  │
│  ├── fiscal_year                                                   │
│  ├── actuarial_assets                                              │
│  ├── market_assets                                                 │
│  ├── actuarial_liability                                           │
│  ├── unfunded_liability                                            │
│  ├── funded_ratio_actuarial                                        │
│  ├── funded_ratio_market                                           │
│  ├── employer_contribution_required                                │
│  ├── employer_contribution_actual                                  │
│  ├── member_count_active                                           │
│  ├── member_count_retired                                          │
│  └── amortization_period_years                                     │
│                                                                     │
│  fact_budget_line_item                                             │
│  ├── budget_line_id (PK)                                           │
│  ├── department_id (FK)                                            │
│  ├── fiscal_year                                                   │
│  ├── appropriation_amount                                          │
│  ├── expenditure_actual                                            │
│  ├── revenue_budgeted                                              │
│  ├── revenue_actual                                                │
│  └── fund_balance_impact                                           │
│                                                                     │
│  fact_economic_indicator (from economic_series model)              │
│  ├── Links to: dim_series_catalog, dim_geography                   │
│  ├── Provides: GDP, unemployment, income, CPI, housing prices      │
│  └── By: Chicago MSA, Cook County, Illinois, and national          │
│                                                                     │
│  fact_demographic_snapshot (from census data)                      │
│  ├── snapshot_id (PK)                                              │
│  ├── community_area_id (FK)                                        │
│  ├── census_tract_id (FK)                                          │
│  ├── year                                                          │
│  ├── total_population                                              │
│  ├── median_age                                                    │
│  ├── median_household_income                                       │
│  ├── poverty_rate                                                  │
│  ├── owner_occupied_pct                                            │
│  └── net_migration                                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Actuarial Measures (Python)

| Category | Measure | Description | Data Sources |
|----------|---------|-------------|--------------|
| **Tax Base** | `tax_base_cagr` | Compound annual growth rate of assessed values | Assessor |
| | `tax_base_projection` | Project future EAV using growth models | Assessor, BEA |
| | `assessment_ratio` | Assessed value / market value | Assessor, sales |
| | `assessment_uniformity` | COD (coefficient of dispersion) | Assessor |
| **Revenue** | `revenue_volatility` | Variance in revenue streams | Budget |
| | `revenue_concentration` | HHI of revenue sources | Budget |
| | `collection_rate` | Actual / billed taxes | Treasurer |
| | `delinquency_rate` | Delinquent / total taxes | Treasurer |
| **Pension** | `funded_ratio_trend` | Trajectory of funded status | Pension CAFRs |
| | `pension_solvency_index` | Combined health metric (all 4 funds) | Pension CAFRs |
| | `contribution_adequacy` | Actual / required contributions | Pension CAFRs |
| | `liability_growth_rate` | YoY change in liabilities | Pension CAFRs |
| **Fiscal Health** | `fiscal_stress_index` | Composite score (0-100) | Multiple |
| | `debt_service_ratio` | Debt service / revenues | Budget, CAFR |
| | `fund_balance_ratio` | Fund balance / expenditures | Budget, CAFR |
| | `liquidity_days` | Cash / daily expenditures | CAFR |
| **Demographic** | `population_growth_rate` | YoY population change | Census |
| | `income_growth_rate` | YoY median income change | Census, BEA |
| | `demographic_dependency` | (Young + Old) / Working age | Census |
| | `migration_net_rate` | Net migration / population | Census |
| **Economic** | `gdp_per_capita` | Metro GDP / population | BEA, Census |
| | `unemployment_trend` | Trajectory of unemployment | BLS |
| | `housing_price_index` | Case-Shiller Chicago | FRED |
| | `business_formation_rate` | New licenses / existing | Chicago |

### Model Dependencies

```
┌─────────────────────────────────────────────────────────────────────┐
│                 MODEL DEPENDENCY GRAPH                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Tier 0 (Foundation):                                               │
│  └── core (calendar dimension)                                      │
│                                                                     │
│  Tier 1 (Geography):                                                │
│  └── geography (dim_geography, dim_census_tract, dim_zip)          │
│      └── depends_on: core                                           │
│                                                                     │
│  Tier 2 (Series Data):                                              │
│  ├── economic_series (all federal/state time series)               │
│  │   └── depends_on: core, geography                               │
│  └── macro (existing BLS data)                                      │
│      └── depends_on: core                                           │
│                                                                     │
│  Tier 3 (Chicago Specific):                                         │
│  ├── city_finance (existing Chicago budget data)                   │
│  │   └── depends_on: core, geography                               │
│  └── chicago_actuarial (full actuarial model)                      │
│      └── depends_on: core, geography, economic_series, city_finance│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Summary

### What Already Exists (Created This Session)

These components were created and are **NOT duplicates** of existing functionality:

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| `ProviderRegistry` | `datapipelines/providers/registry.py` | ✅ Keep | Different from BaseRegistry (providers vs endpoints) |
| `DependencyGraph` | `orchestration/dependency_graph.py` | ✅ Keep | New - topological sort for build ordering |
| `orchestrate.py` | `scripts/orchestrate.py` | ✅ Keep | Unified CLI replacing fragmented scripts |
| `provider.yaml` | `providers/{name}/provider.yaml` | ✅ Keep | Metadata for provider discovery |

### What's Left to Build

1. **Phase 1-2**: Cleanup and backend abstraction (QueryHelper)
2. **Phase 3**: Configuration standardization (v1.x migration + exhibits)
3. **Phase 4**: Core geography model (foundational)
4. **Phase 5**: Orchestration layer (partially complete)
5. **Phase 6**: Economic series model (federal/state data)
6. **Phase 7**: Chart of Accounts base class (financial model inheritance)
7. **Phase 8**: Missing securities models (ETF, Options, Futures)

### New Providers Needed

| Provider | Priority | Data | Model(s) Fed |
|----------|----------|------|--------------|
| `census` | High | Geography, population, demographics | geography, city_finance |
| `fred` | High | Interest rates, housing indices | macro, city_finance |
| `bea` | High | GDP, personal income | macro |
| `cook_county` | Medium | Property assessments, tax rates | city_finance |
| `illinois` | Low | State tax revenue, transfers | city_finance |

### Total Estimated Effort

| Phase | Days | Priority |
|-------|------|----------|
| Phase 1: Cleanup | 1 | High |
| Phase 2: Backend Abstraction | 2 | High |
| Phase 3: Config Standardization | 3 | High |
| Phase 4: Core Geography | 3 | High |
| Phase 5: Orchestration | 2 | High (partially done) |
| Phase 6: Economic Series | 7 | High |
| Phase 7: Chart of Accounts | 6 | High |
| Phase 8: Securities Models | 7 | Medium |
| **Total** | **31 days** | |

---

## Appendix A: Model Registry Pattern

How models are discovered and instantiated:

```
┌────────────────────────────────────────────────────────────────────┐
│                    MODEL DISCOVERY FLOW                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  1. Scan configs/models/ for directories with model.yaml           │
│                                                                    │
│  2. For each model.yaml found:                                     │
│     - Read depends_on field                                        │
│     - Read storage config                                          │
│     - Read component references                                    │
│                                                                    │
│  3. Build dependency graph                                         │
│     core → geography → city_finance (via Chart of Accounts)        │
│                                                                    │
│  4. To instantiate a model:                                        │
│     a. Map model name to class:                                    │
│        'stocks' → models.implemented.stocks.model.StocksModel      │
│        'city_finance' → models.implemented.city_finance.model.CityFinanceModel │
│                                                                    │
│     b. Convention: {name}/model.py contains {Name}Model class      │
│                                                                    │
│     c. Fallback: Explicit registry mapping for exceptions          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

