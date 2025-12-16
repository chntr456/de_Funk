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
├── securities/            # ✅ NEW - Securities model base classes
│   ├── __init__.py        # (placeholder for future shared logic)
│   └── measures.py        # Returns, volatility, Sharpe (move from stocks)
└── financial/             # ✅ NEW - Financial model base classes
    ├── __init__.py
    └── measures.py        # Cash flow, NPV, CAGR patterns
```

**Note**: `models/base/securities/` mirrors `_base/securities/` in configs. Even if initially sparse, this provides a consistent location for shared Python logic across stocks/options/etf/futures models.

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
    description: "Fiscal/reporting period dimension"
    columns:
      fiscal_period_id: string
      fiscal_year: int
      fiscal_quarter: int
      fiscal_month: int
      period_name: string  # "FY2024-Q1"
      period_start_date: date
      period_end_date: date
      is_actual: boolean  # actual vs budget/forecast

  _dim_incurred_period:
    description: "Incurred/accrual period dimension - when expense/revenue actually occurred"
    columns:
      incurred_period_id: string
      incurred_year: int
      incurred_quarter: int
      incurred_month: int
      incurred_date: date  # Specific date if known
      # This enables accrual accounting:
      # - Pension liability incurred in 2020, paid over 30 years
      # - Revenue recognized in Q1, cash received in Q3
      # - Multi-year capital projects

facts:
  _fact_financial_transaction:
    description: "Base fact for financial transactions"
    columns:
      transaction_id: string
      account_id: string  # FK to dim_account
      fiscal_period_id: string  # FK to dim_fiscal_period (when reported)
      incurred_period_id: string  # FK to dim_incurred_period (when incurred)
      transaction_date: date
      amount: double
      budget_amount: double  # budgeted/planned
      variance: double  # actual - budget
      transaction_type: string  # debit, credit
      accounting_basis: string  # 'cash', 'accrual', 'modified_accrual'
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

### Phase 4: Core Geography Model (Days 7-11)

**Goal:** Foundational US geography dimension - location-agnostic down to county level with GIS support

**IMPORTANT**: Geography model is US-agnostic. Chicago is an ANALYSIS target, not a model constraint. The model should work for any US city/county.

| # | Task | Files Affected |
|---|------|----------------|
| 4.1 | Create geography model config | NEW: `configs/models/geography/*.yaml` |
| 4.2 | Define dim_state | schema.yaml |
| 4.3 | Define dim_county | schema.yaml |
| 4.4 | Define dim_place (cities/towns) | schema.yaml |
| 4.5 | Define dim_census_tract | schema.yaml |
| 4.6 | Define dim_zip_code | schema.yaml |
| 4.7 | Define fact_geography_gis (optional GIS data) | schema.yaml |
| 4.8 | Create GeographyModel class | NEW: `models/implemented/geography/model.py` |
| 4.9 | Create Census data provider | NEW: `datapipelines/providers/census/` |
| 4.10 | Create TIGER/Line GIS provider | NEW: `datapipelines/providers/tiger/` |
| 4.11 | Create geography facets | NEW: `census/facets/geography.py` |

**US Geography Hierarchy (Standard - Works for ANY Location):**
```
┌─────────────────────────────────────────────────────────────────────┐
│                    US GEOGRAPHY HIERARCHY                            │
│                    (Location-Agnostic Model)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Level 1: Nation                                                    │
│  └── fips_code: 'US'                                               │
│                                                                     │
│  Level 2: State (50 states + territories)                          │
│  └── fips_code: '17' (Illinois), '06' (California), etc.           │
│                                                                     │
│  Level 3: County (~3,200 US counties)                              │
│  └── fips_code: '17031' (Cook County, IL)                          │
│  └── fips_code: '06037' (Los Angeles County, CA)                   │
│                                                                     │
│  Level 4: Place/City (Census-designated places)                    │
│  └── place_fips: '1714000' (Chicago)                               │
│  └── place_fips: '0644000' (Los Angeles)                           │
│                                                                     │
│  Level 5: Census Tract (~85,000 US tracts)                         │
│  └── tract_fips: '17031010100' (tract in Cook County)              │
│                                                                     │
│  Level 6: Block Group                                              │
│  └── bg_fips: '170310101001'                                       │
│                                                                     │
│  SUPPLEMENTAL (City-Specific - Loaded When Analyzing):             │
│  ─────────────────────────────────────────────────────              │
│  Chicago: Community Areas (77), Wards (50)                         │
│  NYC: Boroughs (5), Community Districts (59), NTAs                 │
│  LA: Council Districts (15), Neighborhoods                         │
│                                                                     │
│  These are loaded as supplemental dimensions when analyzing        │
│  a specific city, NOT hardcoded into the base model.               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Geography Schema (US-Agnostic):**

```yaml
# configs/models/geography/schema.yaml

dimensions:
  dim_state:
    primary_key: [state_fips]
    columns:
      state_fips: string  # '17' for Illinois
      state_name: string  # 'Illinois'
      state_abbr: string  # 'IL'
      region: string  # 'Midwest'
      division: string  # 'East North Central'

  dim_county:
    primary_key: [county_fips]
    columns:
      county_fips: string  # '17031' for Cook County
      state_fips: string  # FK to dim_state
      county_name: string  # 'Cook County'
      county_type: string  # 'county', 'parish', 'borough'
      land_area_sq_mi: double
      water_area_sq_mi: double

  dim_place:
    description: "Census-designated places (cities, towns, CDPs)"
    primary_key: [place_fips]
    columns:
      place_fips: string  # '1714000' for Chicago
      state_fips: string  # FK to dim_state
      county_fips: string  # FK to dim_county (primary county)
      place_name: string  # 'Chicago'
      place_type: string  # 'incorporated', 'cdp'
      legal_type: string  # 'city', 'village', 'town'
      population: long
      land_area_sq_mi: double

  dim_census_tract:
    primary_key: [tract_fips]
    columns:
      tract_fips: string  # '17031010100'
      county_fips: string  # FK to dim_county
      state_fips: string  # FK to dim_state
      tract_name: string  # '101' or 'Census Tract 101'
      land_area_sq_mi: double

  dim_zip_code:
    primary_key: [zip_code]
    columns:
      zip_code: string  # '60601'
      zip_type: string  # 'standard', 'po_box', 'unique'
      primary_city: string
      state_abbr: string
      # Note: ZIPs cross county/tract boundaries

  dim_block_group:
    primary_key: [bg_fips]
    columns:
      bg_fips: string  # '170310101001'
      tract_fips: string  # FK to dim_census_tract
      bg_number: string  # '1'

facts:
  fact_geography_crosswalk:
    description: "Many-to-many relationships between geographies"
    columns:
      crosswalk_id: string
      source_geo_type: string  # 'zip', 'tract', 'place'
      source_geo_id: string
      target_geo_type: string
      target_geo_id: string
      overlap_pct: double  # % of source in target
      population_weight: double  # population-weighted overlap

  fact_geography_gis:
    description: "GIS/spatial data (optional - requires GIS libraries)"
    columns:
      geo_id: string
      geo_type: string  # 'tract', 'county', 'place'
      geometry_wkt: string  # WKT representation
      centroid_lat: double
      centroid_lon: double
      bounding_box: string  # 'minx,miny,maxx,maxy'
```

**City-Specific Supplemental Tables (Loaded On Demand):**

```yaml
# configs/models/geography/supplemental/chicago.yaml
# Only loaded when analyzing Chicago

supplemental_dimensions:
  dim_chicago_community_area:
    primary_key: [community_area_id]
    columns:
      community_area_id: int  # 1-77
      community_area_name: string  # 'Rogers Park', 'Loop'
      side: string  # 'North Side', 'South Side', 'West Side'

  dim_chicago_ward:
    primary_key: [ward_id]
    columns:
      ward_id: int  # 1-50
      alderman_name: string
      # Wards change with redistricting

supplemental_crosswalks:
  fact_tract_to_community_area:
    columns:
      tract_fips: string
      community_area_id: int
      overlap_pct: double
```

### Phase 5: Orchestration Layer (Days 12-13)

**Goal:** Unified build/ingest system

| # | Task | Files Affected |
|---|------|----------------|
| 5.1 | Create DependencyGraph class | NEW: `orchestration/dependency_graph.py` |
| 5.2 | Create ProviderRegistry class | NEW: `datapipelines/providers/registry.py` |
| 5.3 | Create provider.yaml for each provider | NEW: `providers/{name}/provider.yaml` |
| 5.4 | Create model_builder module | NEW: `orchestration/builders/model_builder.py` |
| 5.5 | Create unified orchestrate.py CLI | NEW: `scripts/orchestrate.py` |
| 5.6 | Deprecate old scripts | Add warnings to old scripts |

### Phase 6: Economic Series Model (Days 14-20)

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

### Phase 7: Chart of Accounts Base Class (Days 21-26)

**Goal:** Implement shared financial model base for city_finance and company

| # | Task | Files Affected |
|---|------|----------------|
| 7.1 | Create _base/financial config templates | NEW: `configs/models/_base/financial/*.yaml` |
| 7.2 | Create FinancialMeasures base class | NEW: `models/base/financial/measures.py` |
| 7.3 | Update city_finance to inherit from _base.financial | `configs/models/city_finance/*.yaml` |
| 7.4 | Update company to inherit from _base.financial | `configs/models/company/*.yaml` |
| 7.5 | Add NPV, CAGR, YoY measures to financial base | `measures.py` |
| 7.6 | Add incurred_period dimension support | `schema.yaml` |
| 7.7 | Test inheritance works correctly | Run test suite |
| 7.8 | Update company model for financial statements | `company/model.py` |

### Phase 8: City Services & Departmental Performance (Days 27-33)

**Goal:** Model city departments, services, and performance metrics by geography

This phase adds the ability to analyze how well city services perform across different geographic areas - critical for understanding service equity and resource allocation.

| # | Task | Files Affected |
|---|------|----------------|
| 8.1 | Create city_services model config | NEW: `configs/models/city_services/*.yaml` |
| 8.2 | Define dim_department (Fire, Police, Admin, etc.) | schema.yaml |
| 8.3 | Define dim_service_type (emergency response, permits, etc.) | schema.yaml |
| 8.4 | Define fact_service_call (311, 911 calls by geo) | schema.yaml |
| 8.5 | Define fact_response_time (response metrics by geo) | schema.yaml |
| 8.6 | Define fact_department_budget (extends Chart of Accounts) | schema.yaml |
| 8.7 | Create CityServicesModel class | NEW: `models/implemented/city_services/model.py` |
| 8.8 | Create service performance measures | NEW: `city_services/measures.py` |
| 8.9 | Add Chicago 311/911 data endpoints | `chicago/chicago_ingestor.py` |
| 8.10 | Create analysis notebooks | NEW: `configs/notebooks/city_services/*.md` |

**City Services Schema:**

```yaml
# configs/models/city_services/schema.yaml
# Inherits from _base.financial for budget tracking

extends: _base.financial.schema

dimensions:
  dim_department:
    primary_key: [department_id]
    columns:
      department_id: string
      department_code: string  # 'CFD', 'CPD', 'DOB'
      department_name: string  # 'Fire Department', 'Police Department'
      department_type: string  # 'public_safety', 'administrative', 'infrastructure'
      parent_department_id: string  # For rollup (e.g., sub-bureaus)

  dim_service_type:
    primary_key: [service_type_id]
    columns:
      service_type_id: string
      service_code: string
      service_name: string  # 'Building Permit', 'Fire Response', 'Pothole Repair'
      department_id: string  # FK to dim_department
      service_category: string  # 'emergency', 'permit', 'maintenance', 'inspection'
      sla_target_hours: double  # Service level agreement target

  dim_call_type:
    primary_key: [call_type_id]
    columns:
      call_type_id: string
      call_type_code: string  # '311', '911'
      call_type_name: string
      priority_level: int  # 1=highest priority

facts:
  fact_service_call:
    description: "311/911 calls and service requests"
    columns:
      call_id: string
      call_type_id: string  # FK to dim_call_type
      service_type_id: string  # FK to dim_service_type
      department_id: string  # FK to dim_department
      geography_id: string  # FK to geography (tract, community area, etc.)
      call_datetime: timestamp
      created_date: date
      closed_date: date
      status: string  # 'open', 'in_progress', 'closed'
      resolution_time_hours: double
      latitude: double
      longitude: double

  fact_response_metric:
    description: "Aggregated response/performance metrics by geography"
    columns:
      metric_id: string
      department_id: string
      service_type_id: string
      geography_id: string  # FK to geography
      period_id: string  # FK to calendar
      metric_type: string  # 'response_time', 'completion_rate', 'volume'
      metric_value: double
      target_value: double
      variance_pct: double

  fact_department_budget:
    extends: _base.financial._fact_financial_transaction
    description: "Department budgets with incurred period tracking"
    columns:
      # Inherited: amount, budget_amount, variance, fiscal_period_id, incurred_period_id
      department_id: string
      program_id: string
      personnel_cost: double
      non_personnel_cost: double
      capital_cost: double
      headcount_budgeted: int
      headcount_actual: int
```

**City Services Measures:**

| Category | Measure | Description |
|----------|---------|-------------|
| **Response Time** | `avg_response_time` | Average time to respond by geography |
| | `response_time_p90` | 90th percentile response time |
| | `sla_compliance_rate` | % of calls meeting SLA target |
| **Service Volume** | `calls_per_capita` | 311/911 calls per 1000 residents |
| | `calls_by_type` | Call volume by service type |
| | `call_trend` | YoY change in call volume |
| **Service Equity** | `response_time_disparity` | Variance in response time across geographies |
| | `service_equity_index` | Composite equity score (0-100) |
| | `resource_allocation_ratio` | Budget per capita by area |
| **Department Performance** | `budget_utilization` | Actual spend / budget |
| | `cost_per_call` | Operating cost / calls handled |
| | `staff_efficiency` | Calls handled / FTE |

### Phase 9: Complete Missing Securities Models (Days 34-40)

**Goal:** All securities models have working implementations

| # | Task | Files Affected |
|---|------|----------------|
| 9.1 | Create _base/securities Python module | NEW: `models/base/securities/measures.py` |
| 9.2 | Move shared securities measures from stocks | Refactor `stocks/measures.py` |
| 9.3 | Implement ETF model | NEW: `models/implemented/etf/model.py`, `measures.py` |
| 9.4 | Implement Options model | NEW: `models/implemented/options/model.py`, `measures.py` |
| 9.5 | Implement Futures model | NEW: `models/implemented/futures/model.py`, `measures.py` |
| 9.6 | Test all model builds | Run orchestrate.py --all |

### Phase 10: Company Chart of Accounts from SEC Filings (Days 41-47)

**Goal:** Build company-level Chart of Accounts from SEC filings (10-K, 10-Q) and cash flow statements

This extends the company model to use the `_base.financial` Chart of Accounts pattern, mapping SEC XBRL filings to a standardized account structure. This enables:
- Cash flow analysis across periods
- Balance sheet change tracking
- Cross-company comparisons using standardized accounts

| # | Task | Files Affected |
|---|------|----------------|
| 10.1 | Update company model to inherit from _base.financial | `configs/models/company/model.yaml` |
| 10.2 | Map SEC XBRL tags to Chart of Accounts structure | `configs/models/company/account_mapping.yaml` |
| 10.3 | Create dim_sec_account (standardized account codes) | `configs/models/company/schema.yaml` |
| 10.4 | Create fact_financial_position (balance sheet changes) | `configs/models/company/schema.yaml` |
| 10.5 | Create fact_cash_flow_detail (cash flow line items) | `configs/models/company/schema.yaml` |
| 10.6 | Add SEC filing facets for XBRL parsing | `alpha_vantage/facets/sec_filing.py` |
| 10.7 | Implement CompanyAccountingMeasures | `company/measures.py` |
| 10.8 | Add period-over-period change calculations | `company/measures.py` |
| 10.9 | Test with sample company filings | Test suite |

**Company Chart of Accounts Schema:**

```yaml
# configs/models/company/schema.yaml
extends: _base.financial.schema

dimensions:
  dim_sec_account:
    description: "Standardized SEC XBRL account mapping"
    extends: _base.financial._dim_account
    columns:
      # Inherited: account_id, account_code, account_name, account_type, etc.
      xbrl_tag: string  # Original XBRL tag (e.g., 'us-gaap:Assets')
      xbrl_namespace: string  # 'us-gaap', 'dei', 'company-specific'
      gaap_category: string  # Current Assets, Long-term Liabilities, etc.
      cash_flow_section: string  # Operating, Investing, Financing, null
      is_monetary: boolean  # true for dollar amounts, false for shares/ratios

  dim_filing:
    description: "SEC filing metadata"
    primary_key: [filing_id]
    columns:
      filing_id: string
      cik: string
      ticker: string
      form_type: string  # '10-K', '10-Q', '8-K'
      filing_date: date
      period_end_date: date
      fiscal_year: int
      fiscal_quarter: int  # 0 for annual
      accession_number: string
      document_url: string

facts:
  fact_financial_position:
    description: "Balance sheet positions with period-over-period changes"
    extends: _base.financial._fact_financial_transaction
    columns:
      # Inherited: amount, fiscal_period_id, incurred_period_id, accounting_basis
      position_id: string
      cik: string
      filing_id: string  # FK to dim_filing
      account_id: string  # FK to dim_sec_account
      period_end_date: date
      amount: double  # Current period value
      prior_period_amount: double  # Prior period value
      change_amount: double  # Absolute change
      change_pct: double  # Percentage change
      is_restated: boolean

  fact_cash_flow_detail:
    description: "Cash flow statement line items"
    extends: _base.financial._fact_financial_transaction
    columns:
      # Inherited: amount, fiscal_period_id, incurred_period_id
      cash_flow_id: string
      cik: string
      filing_id: string
      account_id: string  # FK to dim_sec_account
      cash_flow_section: string  # 'operating', 'investing', 'financing'
      period_start_date: date
      period_end_date: date
      amount: double
      is_non_cash: boolean  # Non-cash adjustments
      adjustment_type: string  # 'add_back', 'deduction', 'direct'

  fact_accounting_ratio:
    description: "Derived financial ratios"
    columns:
      ratio_id: string
      cik: string
      filing_id: string
      period_end_date: date
      ratio_name: string  # 'current_ratio', 'debt_to_equity', 'roe'
      ratio_value: double
      numerator_account_id: string
      denominator_account_id: string
```

**Company Accounting Measures:**

| Category | Measure | Description |
|----------|---------|-------------|
| **Cash Flow** | `operating_cash_flow` | Net cash from operations |
| | `free_cash_flow` | OCF - CapEx |
| | `cash_burn_rate` | Monthly cash consumption |
| | `cash_runway_months` | Cash / Monthly burn |
| **Balance Sheet** | `working_capital` | Current Assets - Current Liabilities |
| | `working_capital_change` | Period-over-period change |
| | `asset_turnover` | Revenue / Average Assets |
| **Liquidity** | `current_ratio` | Current Assets / Current Liabilities |
| | `quick_ratio` | (Current - Inventory) / Current Liab |
| | `cash_ratio` | Cash / Current Liabilities |
| **Leverage** | `debt_to_equity` | Total Debt / Equity |
| | `interest_coverage` | EBIT / Interest Expense |
| **Profitability** | `gross_margin` | Gross Profit / Revenue |
| | `operating_margin` | Operating Income / Revenue |
| | `net_margin` | Net Income / Revenue |
| | `roe` | Net Income / Shareholders Equity |
| | `roa` | Net Income / Total Assets |

### Phase 11: Metadata Table Model (Days 48-52)

**Goal:** Create operational model for tracking table metadata, pipeline runs, and data freshness

This model provides visibility into the data warehouse itself - tracking when tables were last updated, row counts, schema changes, and pipeline execution history.

| # | Task | Files Affected |
|---|------|----------------|
| 11.1 | Create metadata model config | NEW: `configs/models/metadata/*.yaml` |
| 11.2 | Define dim_table (catalog of all tables) | schema.yaml |
| 11.3 | Define dim_pipeline (pipeline definitions) | schema.yaml |
| 11.4 | Define fact_table_stats (row counts, sizes) | schema.yaml |
| 11.5 | Define fact_pipeline_run (execution history) | schema.yaml |
| 11.6 | Create MetadataModel class | NEW: `models/implemented/metadata/model.py` |
| 11.7 | Create metadata collection hooks | `orchestration/hooks/metadata_collector.py` |
| 11.8 | Add auto-update on model builds | Integrate with orchestrate.py |
| 11.9 | Create metadata dashboard notebook | `configs/notebooks/metadata/*.md` |

**Metadata Model Schema:**

```yaml
# configs/models/metadata/schema.yaml

dimensions:
  dim_table:
    description: "Catalog of all Bronze/Silver tables"
    primary_key: [table_id]
    columns:
      table_id: string  # 'bronze.alpha_vantage.securities_prices_daily'
      layer: string  # 'bronze', 'silver'
      provider: string  # 'alpha_vantage', 'chicago', null for silver
      model_name: string  # null for bronze, 'stocks' for silver
      table_name: string  # 'securities_prices_daily'
      table_type: string  # 'dimension', 'fact', 'raw'
      storage_format: string  # 'delta', 'parquet'
      storage_path: string
      partition_columns: string  # JSON array
      primary_key_columns: string  # JSON array
      created_date: timestamp
      schema_version: int

  dim_pipeline:
    description: "Pipeline/job definitions"
    primary_key: [pipeline_id]
    columns:
      pipeline_id: string
      pipeline_name: string  # 'alpha_vantage_ingest', 'stocks_build'
      pipeline_type: string  # 'ingest', 'build', 'transform'
      provider: string  # For ingest pipelines
      model_name: string  # For build pipelines
      schedule: string  # Cron expression or 'manual'
      timeout_minutes: int
      retry_count: int
      created_date: timestamp

  dim_column:
    description: "Column-level metadata"
    primary_key: [column_id]
    columns:
      column_id: string
      table_id: string  # FK to dim_table
      column_name: string
      data_type: string
      is_nullable: boolean
      is_partition: boolean
      is_primary_key: boolean
      description: string
      source_column: string  # Original column before transform

facts:
  fact_table_stats:
    description: "Point-in-time table statistics"
    columns:
      stats_id: string
      table_id: string  # FK to dim_table
      snapshot_timestamp: timestamp
      row_count: long
      file_count: int
      total_size_bytes: long
      avg_row_size_bytes: double
      null_count_by_column: string  # JSON object
      distinct_count_by_column: string  # JSON object
      min_partition_date: date
      max_partition_date: date

  fact_pipeline_run:
    description: "Pipeline execution history"
    columns:
      run_id: string
      pipeline_id: string  # FK to dim_pipeline
      start_timestamp: timestamp
      end_timestamp: timestamp
      status: string  # 'running', 'success', 'failed', 'cancelled'
      records_processed: long
      records_written: long
      records_failed: long
      duration_seconds: double
      error_message: string  # null on success
      error_type: string  # Exception class name
      triggered_by: string  # 'schedule', 'manual', 'dependency'
      parent_run_id: string  # For dependent runs
      checkpoint_data: string  # JSON for resume

  fact_schema_change:
    description: "Track schema evolution"
    columns:
      change_id: string
      table_id: string
      change_timestamp: timestamp
      change_type: string  # 'column_added', 'column_removed', 'type_changed'
      column_name: string
      old_value: string  # Old type or null
      new_value: string  # New type
      schema_version_before: int
      schema_version_after: int

  fact_data_quality:
    description: "Data quality metrics per table"
    columns:
      quality_id: string
      table_id: string
      run_id: string  # FK to fact_pipeline_run
      check_timestamp: timestamp
      check_name: string  # 'null_check', 'unique_check', 'range_check'
      column_name: string
      passed: boolean
      expected_value: string
      actual_value: string
      records_checked: long
      records_failed: long
```

**Metadata Measures:**

| Category | Measure | Description |
|----------|---------|-------------|
| **Freshness** | `hours_since_update` | Time since last successful run |
| | `stale_tables` | Tables not updated in >24h |
| | `data_lag_hours` | Max date in table vs current date |
| **Volume** | `daily_row_growth` | New rows per day |
| | `storage_growth_rate` | GB growth per week |
| | `largest_tables` | Top N by size |
| **Pipeline Health** | `success_rate_7d` | % successful runs in 7 days |
| | `avg_duration` | Average pipeline duration |
| | `failure_trend` | Increasing/decreasing failures |
| **Data Quality** | `quality_score` | % of quality checks passing |
| | `null_rate` | % null values by column |
| | `duplicate_rate` | % duplicate rows |

### Phase 12: Logger Model - Run Analytics (Days 53-58)

**Goal:** Create operational model for analyzing logs, errors, and warnings across all pipeline runs

This model aggregates log data to provide easy filtering, categorization, and statistics on pipeline health. Enables quick identification of recurring issues and trend analysis.

| # | Task | Files Affected |
|---|------|----------------|
| 12.1 | Create logger model config | NEW: `configs/models/logger/*.yaml` |
| 12.2 | Define dim_log_source (where logs come from) | schema.yaml |
| 12.3 | Define dim_error_category (error classification) | schema.yaml |
| 12.4 | Define fact_log_entry (individual log records) | schema.yaml |
| 12.5 | Define fact_error_summary (aggregated errors) | schema.yaml |
| 12.6 | Create LoggerModel class | NEW: `models/implemented/logger/model.py` |
| 12.7 | Create log ingestion from de_funk.log | `logger/log_parser.py` |
| 12.8 | Create error categorization rules | `configs/models/logger/error_rules.yaml` |
| 12.9 | Create logger dashboard notebook | `configs/notebooks/logger/*.md` |
| 12.10 | Add log rotation and archival | `scripts/maintenance/archive_logs.py` |

**Logger Model Schema:**

```yaml
# configs/models/logger/schema.yaml

dimensions:
  dim_log_source:
    description: "Source of log entries"
    primary_key: [source_id]
    columns:
      source_id: string
      source_type: string  # 'pipeline', 'model', 'api', 'system'
      source_name: string  # 'alpha_vantage_ingestor', 'StocksModel'
      module_path: string  # 'datapipelines.providers.alpha_vantage'
      component: string  # 'ingestor', 'facet', 'model', 'measure'

  dim_error_category:
    description: "Error classification hierarchy"
    primary_key: [category_id]
    columns:
      category_id: string
      category_name: string  # 'API Error', 'Data Validation', 'Configuration'
      parent_category_id: string  # For hierarchy
      severity: string  # 'critical', 'error', 'warning', 'info'
      is_transient: boolean  # True for rate limits, network errors
      suggested_action: string  # 'Retry', 'Check config', 'Contact support'
      documentation_url: string

  dim_log_level:
    description: "Log level dimension"
    primary_key: [level_id]
    columns:
      level_id: int  # 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR, 50=CRITICAL
      level_name: string
      is_problem: boolean  # true for WARNING and above

facts:
  fact_log_entry:
    description: "Individual log records"
    columns:
      log_id: string
      timestamp: timestamp
      level_id: int  # FK to dim_log_level
      source_id: string  # FK to dim_log_source
      run_id: string  # FK to metadata.fact_pipeline_run (if applicable)
      message: string
      message_template: string  # Message with placeholders (for grouping)
      # Structured fields (extracted from log)
      ticker: string
      model_name: string
      table_name: string
      duration_ms: double
      record_count: long
      # Error details
      error_category_id: string  # FK to dim_error_category
      exception_type: string  # 'ValueError', 'ConnectionError'
      exception_message: string
      stack_trace: string
      # Context
      file_name: string
      line_number: int
      function_name: string

  fact_error_summary:
    description: "Aggregated error statistics by time period"
    columns:
      summary_id: string
      period_date: date
      period_hour: int  # 0-23, null for daily summaries
      source_id: string
      error_category_id: string
      level_id: int
      occurrence_count: long
      first_occurrence: timestamp
      last_occurrence: timestamp
      affected_runs: long  # Distinct run_ids
      affected_tickers: long  # Distinct tickers
      sample_message: string  # One example message
      is_resolved: boolean  # Manual flag

  fact_log_stats:
    description: "Log volume statistics"
    columns:
      stats_id: string
      period_date: date
      source_id: string
      total_entries: long
      debug_count: long
      info_count: long
      warning_count: long
      error_count: long
      critical_count: long
      unique_messages: long  # Distinct message_templates
      avg_entries_per_hour: double
```

**Error Categorization Rules:**

```yaml
# configs/models/logger/error_rules.yaml
# Rules for auto-categorizing errors

categories:
  api_rate_limit:
    name: "API Rate Limit"
    severity: warning
    is_transient: true
    patterns:
      - "rate limit"
      - "429"
      - "too many requests"
    suggested_action: "Wait and retry automatically"

  api_authentication:
    name: "API Authentication"
    severity: error
    is_transient: false
    patterns:
      - "401"
      - "unauthorized"
      - "invalid api key"
      - "authentication failed"
    suggested_action: "Check API key in .env file"

  api_not_found:
    name: "API Resource Not Found"
    severity: warning
    is_transient: false
    patterns:
      - "404"
      - "not found"
      - "no data"
      - "symbol not found"
    suggested_action: "Verify ticker/symbol exists"

  connection_error:
    name: "Network/Connection Error"
    severity: error
    is_transient: true
    patterns:
      - "connection refused"
      - "timeout"
      - "network unreachable"
      - "ConnectionError"
    suggested_action: "Check network connectivity, retry"

  data_validation:
    name: "Data Validation Error"
    severity: error
    is_transient: false
    patterns:
      - "validation failed"
      - "schema mismatch"
      - "invalid data type"
      - "null constraint"
    suggested_action: "Check source data quality"

  configuration:
    name: "Configuration Error"
    severity: critical
    is_transient: false
    patterns:
      - "config not found"
      - "missing required"
      - "invalid configuration"
      - "ConfigurationError"
    suggested_action: "Review configuration files"

  out_of_memory:
    name: "Memory Error"
    severity: critical
    is_transient: false
    patterns:
      - "out of memory"
      - "MemoryError"
      - "heap space"
    suggested_action: "Increase memory allocation or reduce batch size"
```

**Logger Measures:**

| Category | Measure | Description |
|----------|---------|-------------|
| **Volume** | `logs_per_hour` | Log entry rate |
| | `error_rate` | Errors / Total logs |
| | `warning_rate` | Warnings / Total logs |
| **Errors** | `errors_today` | Error count today |
| | `errors_7d_trend` | % change vs prior 7 days |
| | `top_errors` | Most frequent error categories |
| | `new_errors` | Errors first seen in last 24h |
| **Health** | `error_free_hours` | Hours since last error |
| | `mtbf` | Mean time between failures |
| | `mttr` | Mean time to resolution |
| **By Source** | `errors_by_pipeline` | Errors grouped by pipeline |
| | `errors_by_model` | Errors grouped by model |
| | `noisiest_source` | Source with most warnings |

**Logger Dashboard Features:**

```markdown
# Logger Dashboard Notebook Features

## Filters
- Date range (last hour, day, week, custom)
- Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Source (pipeline, model, component)
- Error category
- Run ID
- Ticker/Symbol

## Views
1. **Overview**
   - Error/warning count by hour (line chart)
   - Error rate trend
   - Current health status

2. **Error Deep Dive**
   - Top 10 errors by frequency
   - Error timeline
   - Stack trace viewer
   - Related logs (same run_id)

3. **Pipeline Health**
   - Success/failure by pipeline
   - Duration trends
   - Failure patterns

4. **Alerting**
   - New error types (not seen before)
   - Spike detection (>2x normal rate)
   - Critical errors
```

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
3. **Phase 4**: Core geography model (US-agnostic, down to tract level with GIS)
4. **Phase 5**: Orchestration layer (partially complete)
5. **Phase 6**: Economic series model (federal/state data)
6. **Phase 7**: Chart of Accounts base class (financial model inheritance with incurred period)
7. **Phase 8**: City Services & Departmental Performance (Fire, Police, Admin by geography)
8. **Phase 9**: Missing securities models (ETF, Options, Futures)
9. **Phase 10**: Company Chart of Accounts from SEC filings (cash flows, balance sheet changes)
10. **Phase 11**: Metadata Table Model (operational tracking, data freshness)
11. **Phase 12**: Logger Model (error/warning analytics, filtering, statistics)

### New Providers Needed

| Provider | Priority | Data | Model(s) Fed |
|----------|----------|------|--------------|
| `census` | High | Geography, population, demographics | geography, city_services |
| `tiger` | High | TIGER/Line GIS boundaries | geography |
| `fred` | High | Interest rates, housing indices | macro, city_finance |
| `bea` | High | GDP, personal income | macro |
| `cook_county` | Medium | Property assessments, tax rates | city_finance |
| `illinois` | Low | State tax revenue, transfers | city_finance |

### New Models Needed

| Model | Inherits From | Purpose |
|-------|---------------|---------|
| `geography` | (base) | US geography hierarchy, GIS data |
| `city_services` | `_base.financial` | Department performance by geography |
| `economic_series` | (base) | Federal/state time series data |
| `metadata` | (operational) | Table stats, pipeline runs, schema tracking |
| `logger` | (operational) | Log analytics, error categorization |

### Total Estimated Effort

| Phase | Days | Priority |
|-------|------|----------|
| Phase 1: Cleanup | 1 | High |
| Phase 2: Backend Abstraction | 2 | High |
| Phase 3: Config Standardization | 3 | High |
| Phase 4: Core Geography (US-Agnostic) | 5 | High |
| Phase 5: Orchestration | 2 | High (partially done) |
| Phase 6: Economic Series | 7 | High |
| Phase 7: Chart of Accounts (+ Incurred Period) | 6 | High |
| Phase 8: City Services & Departments | 7 | High |
| Phase 9: Securities Models | 7 | Medium |
| Phase 10: Company Chart of Accounts | 7 | High |
| Phase 11: Metadata Table Model | 5 | High |
| Phase 12: Logger Model | 6 | High |
| **Total** | **58 days** | |

---

## Commit Strategy

All commits during implementation will follow this naming convention:

```
Phase N: [Phase Name] - [Brief Description]

Example commits:
- "Phase 1: Cleanup - Delete deprecated v1.x YAML files"
- "Phase 1: Cleanup - Remove orphaned services.py"
- "Phase 2: Backend Abstraction - Create QueryHelper class"
- "Phase 3: Config Standardization - Migrate core.yaml to modular structure"
```

Each phase will be completed before moving to the next, with a thorough review at the end of each phase.

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

