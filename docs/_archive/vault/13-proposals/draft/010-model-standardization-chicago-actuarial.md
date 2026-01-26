# Proposal 010: Model Standardization & Chicago Economic Analysis

**Status**: In Progress (Foundation 4/8 Complete)
**Created**: 2025-12-15
**Updated**: 2026-01-06
**Author**: Claude (AI Assistant)
**Priority**: High

**Progress Summary**:
- ✅ Phase 1: Cleanup - Complete
- ✅ Phase 2: Backend Abstraction - Complete
- ✅ Phase 3: Config Standardization - Complete
- ⏸️ Phase 4: Core Geography - Pending (geography model build)
- ✅ Phase 5: Spark Cluster - Complete
- 🔜 **Phase 6: Multi-Source Data Expansion - NEXT STEPS**
  - 6.1: Raw Layer (new concept for raw files: CSVs, PDFs, Access DBs)
  - 6.2: Data Sources (Census Bureau, Chicago, Cook County, FRED, BLS, Alpha Vantage)
  - **First task:** Create exhaustive dataset inventories (including public safety)
- ⏸️ Phase 7: Silver Model Builds - After Phase 6 (use multi-source Bronze data)
- ⏸️ Phase 8: Airflow Orchestration - After Phase 7 (orchestrate multiple providers)
- ⏸️ Phases 9-17: Enhancement & Cleanup

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
| `ProviderRegistry` | `datapipelines/providers/registry.py` | Discovers data **providers**, instantiates ingestors | ✅ Exists |

**Key Distinction:**
- `BaseRegistry` + subclasses = API endpoint management (how to call APIs)
- `ModelRegistry` = Model class discovery (how to build models)
- `ProviderRegistry` = Data provider discovery (which data sources exist)

These serve **different purposes** and are NOT duplicates.

### Orchestration Components

| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| `DependencyGraph` | `orchestration/dependency_graph.py` | Model build order via topological sort (431 lines) | ✅ Exists |
| `CheckpointManager` | `orchestration/checkpoint.py` | Resume from failure | ✅ Exists |
| `orchestrate.py` | `scripts/orchestrate.py` | Unified CLI (760 lines) | ✅ Exists |
| `FilterEngine` | `core/session/filters.py` | Backend-agnostic filter application (356 lines) | ✅ Exists |

### Build Scripts (Current - Fragmented)

| Script | Purpose | Status |
|--------|---------|--------|
| `build_company_model.py` | Build company model only (hardcoded) | ⚠️ To deprecate |
| `build_silver_duckdb.py` | Build with DuckDB (hardcoded model list) | ⚠️ To deprecate |
| `run_full_pipeline.py` | Full pipeline (Alpha Vantage only) | ⚠️ To deprecate |
| `orchestrate.py` | Unified replacement | ✅ Exists - extend for queue |

**Key Issue**: `orchestrate.py` exists but fragmented scripts are still used. Phase 1 cleanup should ensure consistent usage of the unified orchestrator.

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

### Phase 1: Cleanup (Days 1-2) ✅ COMPLETE

**Goal:** Remove deprecated files, fix naming inconsistencies, ensure consistent utilization of existing tools

**Status:** ✅ Completed December 2025

#### 1A: File Cleanup (Day 1)

| # | Task | Files Affected |
|---|------|----------------|
| 1.1 | Delete deprecated v1.x YAML files | `configs/models/company.yaml`, `etf.yaml` |
| 1.2 | Delete orphaned services file | `models/implemented/company/services.py` |
| 1.3 | Rename `etfs/` to `etf/` for consistency | `configs/models/etfs/` → `etf/` |
| 1.4 | Update any imports referencing renamed dirs | Search and replace |

#### 1B: Tool Utilization Audit (Day 2)

Existing tools that MUST be consistently used - not recreated or bypassed:

| # | Task | Tool | Current Issue |
|---|------|------|---------------|
| 1.5 | Audit FilterEngine usage in models | `core/session/filters.py` | Models bypass FilterEngine with inline `if self._backend` |
| 1.6 | Audit orchestrate.py usage | `scripts/orchestrate.py` | Fragmented scripts still called directly |
| 1.7 | Audit DependencyGraph usage | `orchestration/dependency_graph.py` | May not be used by all build paths |
| 1.8 | Audit ProviderRegistry usage | `datapipelines/providers/registry.py` | Ingestors may instantiate directly |
| 1.9 | Deprecate fragmented scripts | `build_company_model.py`, `build_silver_duckdb.py`, `run_full_pipeline.py` | Add deprecation warnings pointing to `orchestrate.py` |

**Deliverable**: Audit report showing:
- Which models use FilterEngine vs inline backend checks
- Which scripts bypass orchestrate.py
- Which ingestors bypass ProviderRegistry

This audit informs Phase 2 - we need to know the full scope of inconsistent usage before refactoring.

### Phase 2: Backend Abstraction via UniversalSession (Days 3-5) ✅ COMPLETE

**Goal:** Models become backend-agnostic by using UniversalSession for all data operations

**Status:** ✅ Completed December 2025

**Principle:** Models should NEVER know or care what backend is running. All backend-specific logic lives in UniversalSession.

**Key Insight**: `FilterEngine` (356 lines) already exists in `core/session/filters.py` and provides backend-agnostic filtering. Phase 2 should:
1. Make UniversalSession use FilterEngine internally
2. Add additional query helper methods to UniversalSession
3. Refactor models to use session methods (which internally use FilterEngine)

| # | Task | Files Affected | Status |
|---|------|----------------|--------|
| 2.1 | Add query helper methods to UniversalSession | `models/api/session.py` | ✅ Done |
| 2.2 | Remove `self._backend` from all models | All `models/implemented/*/model.py` | ⏳ **Deferred to Phase 5** |
| 2.3 | Refactor CompanyModel to use session methods | `models/implemented/company/model.py` | ✅ Done |
| 2.4 | Refactor StocksModel to use session methods | `models/implemented/stocks/model.py` | ✅ Done |
| 2.5 | Refactor StocksMeasures to use session methods | `models/implemented/stocks/measures.py` | ✅ Done |
| 2.6 | Refactor CoreModel to use session methods | `models/implemented/core/model.py` | ✅ Done |
| 2.6a | Refactor MacroModel to use session methods | `models/implemented/macro/model.py` | ✅ Done |
| 2.6b | Refactor ETFModel to use session methods | `models/implemented/etf/model.py` | ✅ Done |
| 2.6c | Refactor CityFinanceModel to use session methods | `models/implemented/city_finance/model.py` | ✅ Done |
| 2.7 | Test all models with both backends | Run test suite | Pending |

**Note on Task 2.2**: Removing `_backend` is deferred to Phase 5 (Orchestrator Standardization). Currently, models need the fallback `_backend` code because:
1. Session is injected via `set_session()` **after** model instantiation
2. During `build()`, session may not be available yet
3. Phase 5 will ensure session is always injected at instantiation, allowing removal of fallback code

---

#### Architecture: Before vs After

**BEFORE (Current - Models know about backend):**
```python
# models/implemented/stocks/model.py
class StocksModel(BaseModel):
    def __init__(self, connection, backend='spark', ...):
        self._backend = backend  # ❌ Model knows about backend

    def get_prices(self, tickers):
        if self._backend == 'spark':           # ❌ Backend branching in model
            return df.join(ticker_df, ...)
        else:
            return df.filter(df.ticker.isin(tickers))
```

**AFTER (Target - Models are backend-agnostic):**
```python
# models/implemented/stocks/model.py
class StocksModel(BaseModel):
    def __init__(self, session: UniversalSession, ...):
        self.session = session  # ✅ Just uses session

    def get_prices(self, tickers):
        df = self.session.get_table('stocks', 'fact_prices')
        return self.session.filter_by_values(df, 'ticker', tickers)  # ✅ Session handles backend
```

---

#### UniversalSession Query Helper Methods

Add these methods to UniversalSession - they handle backend differences internally:

```python
# models/api/session.py

class UniversalSession:
    """
    Backend-agnostic session for all model operations.
    Models call these methods - they never need to know
    whether Spark or DuckDB is running underneath.
    """

    def __init__(self, backend: str = 'duckdb', ...):
        self._backend = backend  # Only session knows backend
        self._connection = self._init_connection()

    # === Filtering ===

    def filter_by_values(self, df, column: str, values: list):
        """
        Filter DataFrame where column is in values list.
        Handles: Spark semi-join vs DuckDB isin()
        """
        if self._backend == 'spark':
            values_df = self._connection.createDataFrame([(v,) for v in values], [column])
            return df.join(values_df, column, 'semi')
        else:
            return df.filter(df[column].isin(values))

    def filter_by_range(self, df, column: str, min_val=None, max_val=None):
        """Filter DataFrame by range (dates, numbers)."""
        # Backend-specific implementation inside

    # === Joins ===

    def join(self, left_df, right_df, on: list, how: str = 'inner'):
        """Join two DataFrames - handles syntax differences."""

    def semi_join(self, df, filter_df, on: str):
        """Efficient filtering via semi-join."""

    # === Aggregations ===

    def aggregate(self, df, group_by: list, aggregations: dict):
        """
        Aggregate DataFrame with grouping.
        Args:
            aggregations: {'new_col': ('source_col', 'sum'|'avg'|'count'|'min'|'max')}
        """

    def window_aggregate(self, df, partition_by: list, order_by: str, aggregations: dict):
        """Window functions (rolling averages, ranks, etc.)."""

    # === Column Operations ===

    def select_columns(self, df, columns: list):
        """Select specific columns."""

    def add_column(self, df, name: str, expression: str):
        """Add computed column using SQL expression."""

    def rename_columns(self, df, mapping: dict):
        """Rename columns: {'old_name': 'new_name'}"""

    def cast_column(self, df, column: str, dtype: str):
        """Cast column to type: 'string', 'int', 'double', 'date'"""

    # === Output ===

    def to_pandas(self, df) -> 'pd.DataFrame':
        """Convert to pandas DataFrame."""

    def collect(self, df) -> list:
        """Collect all rows as list of dicts."""

    def row_count(self, df) -> int:
        """Get row count."""

    def distinct_values(self, df, column: str) -> list:
        """Get distinct values from column."""

    # === Read/Write ===

    def read_table(self, path: str):
        """Read table with format auto-detection (Delta/Parquet)."""

    def write_table(self, df, path: str, mode: str = 'overwrite', partition_by: list = None):
        """Write table to storage."""
```

---

#### Model Refactoring Pattern

**Before (21+ backend if-statements across codebase):**
```python
def get_prices_for_tickers(self, tickers: list, start_date=None, end_date=None):
    df = self._get_table('fact_prices')

    if self._backend == 'spark':
        from pyspark.sql import functions as F
        ticker_df = self._spark.createDataFrame([(t,) for t in tickers], ['ticker'])
        df = df.join(ticker_df, 'ticker', 'semi')
        if start_date:
            df = df.filter(F.col('trade_date') >= start_date)
    else:
        df = df.filter(df.ticker.isin(tickers))
        if start_date:
            df = df.filter(f"trade_date >= '{start_date}'")
    return df
```

**After (clean, backend-agnostic):**
```python
def get_prices_for_tickers(self, tickers: list, start_date=None, end_date=None):
    df = self.session.get_table('stocks', 'fact_prices')
    df = self.session.filter_by_values(df, 'ticker', tickers)
    df = self.session.filter_by_range(df, 'trade_date', min_val=start_date, max_val=end_date)
    return df
```

---

#### Files Changed Summary

| File | Changes |
|------|---------|
| `models/api/session.py` | Add ~15 query helper methods |
| `models/base/model.py` | Remove `_backend` parameter, require `session` injection |
| `models/implemented/stocks/model.py` | Remove 9 backend if-statements |
| `models/implemented/stocks/measures.py` | Remove 6 backend if-statements |
| `models/implemented/company/model.py` | Remove 6 backend if-statements |
| `models/implemented/core/model.py` | Remove backend-specific code |

---

#### Benefits

| Benefit | Description |
|---------|-------------|
| **Single source of truth** | All backend logic in UniversalSession |
| **Models are simpler** | Just call session methods, no branching |
| **Easier testing** | Mock session to test model logic in isolation |
| **Backend swappable** | Change backend in one config, models unchanged |
| **New backends easier** | Add Polars/DataFusion by extending session only |
| **Consistent API** | Same method calls regardless of backend |

---

#### Session Architecture Clarification

**UniversalSession supports BOTH backends** - models don't know which is running:

```python
# For batch builds (orchestration uses Spark)
session = UniversalSession(backend='spark')
model = StocksModel(session)
model.build()  # Heavy ETL work via Spark

# For interactive queries (UI/notebooks use DuckDB)
session = UniversalSession(backend='duckdb')
model = StocksModel(session)
df = model.get_prices(...)  # Fast analytics via DuckDB
```

**Key distinction:**
- `backend='spark'` → SparkSession for heavy ETL, Delta writes
- `backend='duckdb'` → DuckDB for fast reads, analytics, UI queries

**Same model code works either way** - the abstraction handles differences.

**Session lifecycle:**

| Backend | Weight | Lifecycle | Notes |
|---------|--------|-----------|-------|
| Spark | Heavy | Per-worker (reused) | One SparkSession per JVM, expensive to create |
| DuckDB | Light | Per-task or per-worker | Cheap to create, can have many |

This means:
- **Orchestration workers** create ONE session at startup, reuse for all tasks
- **Interactive queries** can create sessions as needed (DuckDB is cheap)

### Phase 3: Configuration Standardization (Days 5-7) ✅ COMPLETE

**Goal:** All configs use v2.0 modular YAML pattern + complete exhibit presets + context-aware model graph

**Status:** ✅ Completed December 2025

| # | Task | Files Affected |
|---|------|----------------|
| 3.1 | Create `core/` modular config from core.yaml | NEW: `configs/models/core/*.yaml` |
| 3.2 | Create `forecast/` modular config from forecast.yaml | NEW: `configs/models/forecast/*.yaml` |
| 3.3 | Delete old v1.x files after migration | DELETE: `core.yaml`, `forecast.yaml` |
| 3.4 | Update ModelConfigLoader if needed | `config/model_loader.py` |
| 3.5 | Create base exhibit preset | NEW: `configs/exhibits/_base/exhibit.yaml` |
| 3.6 | Create Plotly base preset | NEW: `configs/exhibits/presets/plotly_base.yaml` |
| 3.7 | Create line chart preset | NEW: `configs/exhibits/presets/line_chart.yaml` (referenced by registry, missing) |
| 3.8 | Create bar chart preset | NEW: `configs/exhibits/presets/bar_chart.yaml` (referenced by registry, missing) |
| 3.8a | Update exhibit registry | `configs/exhibits/registry.yaml` - add inheritance fields |
| 3.9 | Create hierarchical model graph component | REFACTOR: `app/ui/components/model_graph_viewer.py` |
| 3.10 | Add global model graph to home page | UPDATE: `app/ui/notebook_app_duckdb.py` |
| 3.11 | Add context-aware graph for notebook view | UPDATE: `app/ui/components/notebook_viewer.py` |
| 3.12 | Create model node with dim/fact sub-nodes | NEW: `app/ui/components/model_node_graph.py` |

---

#### Context-Aware Model Graph Visualization

**Problem:** Current graph viewer shows flat table-level relationships. Users need to:
- See which models are relevant to their current notebook
- Understand the hierarchical structure (model → dims/facts)
- Navigate between global view (all models) and focused view (notebook models)

**Solution:** Hierarchical, context-aware model graph with two modes:

**1. Global View (Home Page):**
- Shows ALL registered models as expandable nodes
- Each model node can expand to show its dimensions and facts
- Cross-model edges shown at model level
- Useful for understanding overall data architecture

**2. Notebook View (When Notebook Selected):**
- Shows ONLY models declared in notebook `properties.models`
- Automatically includes dependent models (from `depends_on`)
- Highlights active tables used by notebook filters/exhibits
- Shows relevant cross-model paths for filter propagation

**Hierarchical Node Structure:**
```
┌─────────────────────────────────────────────────────────────────────┐
│                      MODEL GRAPH VISUALIZATION                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐         ┌──────────────────┐                  │
│  │   stocks (model) │─────────│  company (model) │                  │
│  ├──────────────────┤         ├──────────────────┤                  │
│  │ ○ dim_stock      │         │ ○ dim_company    │                  │
│  │ ○ fact_prices    │         │ ○ fact_income    │                  │
│  │ ○ fact_technicals│         │ ○ fact_balance   │                  │
│  └────────┬─────────┘         └────────┬─────────┘                  │
│           │                            │                             │
│           └────────────┬───────────────┘                             │
│                        │                                             │
│                        ▼                                             │
│               ┌──────────────────┐                                   │
│               │   core (model)   │                                   │
│               ├──────────────────┤                                   │
│               │ ○ dim_calendar   │                                   │
│               └──────────────────┘                                   │
│                                                                      │
│  Legend:                                                             │
│  ─────── Cross-model edge (join relationship)                       │
│  ○       Dimension or Fact table (sub-node)                         │
│  (model) Collapsible model container                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation Approach:**

```python
# app/ui/components/model_node_graph.py

class ModelNodeGraph:
    """Hierarchical model graph with expandable nodes."""

    def __init__(self, model_registry, mode: str = "global"):
        """
        Args:
            model_registry: Registry to discover models
            mode: "global" (all models) or "notebook" (filtered)
        """
        self.registry = model_registry
        self.mode = mode
        self.selected_models: List[str] = []  # For notebook mode

    def set_notebook_context(self, notebook_properties: dict):
        """Filter to models declared in notebook properties."""
        declared = notebook_properties.get('models', [])
        # Include declared models + their dependencies
        self.selected_models = self._resolve_with_dependencies(declared)

    def _resolve_with_dependencies(self, models: List[str]) -> List[str]:
        """Expand model list to include depends_on models."""
        result = set(models)
        for model in models:
            config = self.registry.get_model_config(model)
            deps = config.get('depends_on', [])
            result.update(deps)
        return list(result)

    def build_hierarchical_graph(self) -> nx.DiGraph:
        """Create graph with model nodes containing dim/fact sub-nodes."""
        G = nx.DiGraph()

        models = self.selected_models if self.mode == "notebook" else self.registry.list_models()

        for model_name in models:
            # Add model as parent node
            G.add_node(model_name, type="model", expanded=True)

            # Add dims/facts as child nodes
            schema = self.registry.get_schema(model_name)
            for dim in schema.get('dimensions', {}):
                node_id = f"{model_name}.{dim}"
                G.add_node(node_id, type="dimension", parent=model_name)
                G.add_edge(model_name, node_id, type="contains")

            for fact in schema.get('facts', {}):
                node_id = f"{model_name}.{fact}"
                G.add_node(node_id, type="fact", parent=model_name)
                G.add_edge(model_name, node_id, type="contains")

        # Add cross-model edges at model level
        self._add_cross_model_edges(G, models)

        return G

    def render(self, container):
        """Render interactive Plotly graph with collapsible nodes."""
        G = self.build_hierarchical_graph()
        # ... Plotly rendering with node colors by type
        # ... Click handlers for expand/collapse
```

**UI Integration:**

```python
# Home page - global view
def render_home_page():
    st.header("Data Model Overview")
    graph = ModelNodeGraph(registry, mode="global")
    graph.render(st.container())

# Notebook view - context-aware
def render_notebook(notebook):
    # ... notebook content ...

    with st.expander("📊 Model Graph", expanded=False):
        graph = ModelNodeGraph(registry, mode="notebook")
        graph.set_notebook_context(notebook.properties)
        graph.render(st.container())
```

**Visual Differentiation:**
| Node Type | Color | Shape | Behavior |
|-----------|-------|-------|----------|
| Model | Blue | Rectangle | Expandable/collapsible |
| Dimension | Green | Circle | Shows columns on hover |
| Fact | Orange | Circle | Shows columns on hover |
| Cross-model edge | Gray dashed | Arrow | Shows join condition |
| Contains edge | Light gray | Line | Hierarchical relationship |

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

### Phase 5: Ingestor & Orchestrator Standardization (Days 12-15) ✅ COMPLETE

**Goal:** Standardize ingestor interfaces and create unified Orchestrator class

**Status:** ✅ Completed December 2025 - January 2026 (Implemented as Spark Cluster)

**Actual Implementation:** Instead of the class-based Orchestrator pattern below, a pure Spark cluster approach was implemented:
- `scripts/spark-cluster/` - Full cluster setup scripts (init, setup-head, setup-worker, etc.)
- `run_config.json` - Profile-based configuration (quick_test, dev, production)
- `test_full_pipeline_spark.sh` - Main pipeline execution script
- NFS shared storage at `/shared/storage` for Bronze/Silver layers

See **Appendix B: Phase 5: Spark Cluster Implementation** for full details.

**Original Design** (partially implemented - class patterns may be added later):
This phase creates a clean abstraction layer for data ingestion:
- Standardizes ingestor interface via BaseIngestor class
- Creates Orchestrator class to coordinate ingestors and model builds
- Simplifies scripts to thin wrappers around the Orchestrator
- Enables future queue-based distribution (Phase 6 → now Phase 7 Airflow)

| # | Task | Files Affected |
|---|------|----------------|
| 5.1 | Create standardized BaseIngestor class | NEW: `datapipelines/base/ingestor.py` |
| 5.2 | Refactor AlphaVantageIngestor to use BaseIngestor | REFACTOR: `providers/alpha_vantage/alpha_vantage_ingestor.py` |
| 5.3 | Refactor BLSIngestor to use BaseIngestor | REFACTOR: `providers/bls/bls_ingestor.py` |
| 5.4 | Refactor ChicagoIngestor to use BaseIngestor | REFACTOR: `providers/chicago/chicago_ingestor.py` |
| 5.5 | Create Orchestrator class | NEW: `orchestration/orchestrator.py` |
| 5.6 | Integrate DependencyGraph into Orchestrator | EXTEND: `orchestration/dependency_graph.py` (431 lines exists) |
| 5.7 | Integrate ProviderRegistry into Orchestrator | EXTEND: `datapipelines/providers/registry.py` (exists) |
| 5.8 | Update orchestrate.py to use Orchestrator class | REFACTOR: `scripts/orchestrate.py` (760 lines → thin wrapper) |
| 5.9 | Inject session at model instantiation | REFACTOR: `models/base/model.py`, `orchestration/orchestrator.py` |
| 5.10 | Remove `_backend` fallback code from all models | All `models/implemented/*/model.py` (deferred from Phase 2) |
| 5.11 | Wire model YAML configs into build logic | REFACTOR: CoreModel reads `calendar_config` from YAML |
| 5.12 | Wire forecast YAML configs into build logic | REFACTOR: ForecastModel reads `ml_models` config from YAML |
| 5.13 | Fix run_forecasts.py to use modular config | REFACTOR: `scripts/forecast/run_forecasts.py` uses ModelConfigLoader |

**Note on 5.9-5.10**: These tasks complete the backend abstraction started in Phase 2. Once Orchestrator ensures session is always available at model instantiation, we can remove the fallback `_backend` code from all models.

**Note on 5.11-5.13**: Phase 3 created modular YAML configs for core and forecast, but the model build classes still have hardcoded defaults. These tasks ensure:
- `CoreModel` / `CalendarBuilder` reads `calendar_config` from `core/graph.yaml`
- `ForecastModel` reads `ml_models` config from `forecast/model.yaml`
- Build logic lives within each model, not in separate scripts
- **KNOWN ERROR**: `run_forecasts.py` line 176 looks for `forecast.yaml` but file was migrated to `forecast/model.yaml`. Task 5.13 addresses this.

---

#### BaseIngestor Standardization

**Problem:** Current ingestors have inconsistent interfaces:
- `Ingestor` base class only requires `run_all()` (10 lines, too minimal)
- `BaseProvider` exists but isn't consistently used
- Alpha Vantage has 15+ methods, other ingestors have different patterns
- Orchestrator can't uniformly call ingestors

**Solution:** Standardized `BaseIngestor` that all providers implement:

```python
# datapipelines/base/ingestor.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class IngestResult:
    """Result from ingesting a single table."""
    table: str
    success: bool
    rows_written: int = 0
    error: Optional[str] = None
    duration_seconds: float = 0.0

class BaseIngestor(ABC):
    """
    Standard interface all data providers must implement.

    The Orchestrator calls these methods uniformly across all providers.
    Provider-specific logic is encapsulated in the implementation.
    """

    def __init__(self, spark, storage_cfg: Dict, provider_cfg: Dict):
        """
        Initialize ingestor with required dependencies.

        Args:
            spark: SparkSession for Delta Lake writes
            storage_cfg: Storage configuration (paths, tables)
            provider_cfg: Provider-specific config (from provider.yaml)
        """
        self.spark = spark
        self.storage_cfg = storage_cfg
        self.provider_cfg = provider_cfg
        self._setup()

    @abstractmethod
    def _setup(self) -> None:
        """Provider-specific initialization (HTTP client, API keys, etc.)"""
        pass

    @property
    def name(self) -> str:
        """Provider name from config."""
        return self.provider_cfg.get('name', 'unknown')

    @property
    def bronze_tables(self) -> List[str]:
        """Bronze tables this ingestor writes to (from provider.yaml)."""
        return self.provider_cfg.get('bronze_tables', [])

    @abstractmethod
    def ingest_table(
        self,
        table_name: str,
        tickers: List[str] = None,
        **kwargs
    ) -> IngestResult:
        """
        Ingest a specific bronze table.

        Args:
            table_name: Name of bronze table (must be in bronze_tables)
            tickers: Optional ticker filter (for securities providers)
            **kwargs: Provider-specific options (date_from, date_to, etc.)

        Returns:
            IngestResult with success/failure and metadata
        """
        pass

    def ingest_all(
        self,
        tables: List[str] = None,
        tickers: List[str] = None,
        **kwargs
    ) -> List[IngestResult]:
        """
        Ingest all or specified tables.

        Default implementation calls ingest_table for each table.
        Override if provider needs special handling.
        """
        tables = tables or self.bronze_tables
        results = []
        for table in tables:
            result = self.ingest_table(table, tickers=tickers, **kwargs)
            results.append(result)
        return results

    def validate_table(self, table_name: str) -> bool:
        """Check if table is valid for this provider."""
        return table_name in self.bronze_tables
```

**Refactored Alpha Vantage Ingestor Example:**

```python
# datapipelines/providers/alpha_vantage/alpha_vantage_ingestor.py

class AlphaVantageIngestor(BaseIngestor):
    """Alpha Vantage data provider."""

    def _setup(self):
        """Initialize HTTP client and API key pool."""
        self.http_client = HttpClient(...)
        self.key_pool = KeyPool(...)

    def ingest_table(self, table_name: str, tickers=None, **kwargs) -> IngestResult:
        """Route to appropriate ingestion method based on table name."""

        # Table name → method mapping
        table_methods = {
            'securities_reference': self._ingest_reference,
            'securities_prices_daily': self._ingest_prices,
            'income_statements': self._ingest_income_statements,
            'balance_sheets': self._ingest_balance_sheets,
            'cash_flows': self._ingest_cash_flows,
            'earnings': self._ingest_earnings,
        }

        if table_name not in table_methods:
            return IngestResult(table=table_name, success=False,
                              error=f"Unknown table: {table_name}")

        method = table_methods[table_name]
        return method(tickers=tickers, **kwargs)

    def _ingest_reference(self, tickers, **kwargs) -> IngestResult:
        """Internal: Ingest securities reference data."""
        # ... existing logic from ingest_reference_data() ...

    def _ingest_prices(self, tickers, **kwargs) -> IngestResult:
        """Internal: Ingest daily price data."""
        # ... existing logic from ingest_prices() ...
```

---

#### Orchestrator Class

**Problem:** Orchestration logic is scattered in scripts (760 lines in orchestrate.py)

**Solution:** `Orchestrator` class that coordinates ingestors and model builds:

```python
# orchestration/orchestrator.py

class Orchestrator:
    """
    Coordinates data ingestion and model building.

    Provides uniform interface for:
    - Running ingestors via BaseIngestor interface
    - Building models via DependencyGraph ordering
    - Managing task queue for distributed execution
    """

    def __init__(
        self,
        spark,
        storage_cfg: Dict,
        providers: List[str] = None,
        models: List[str] = None
    ):
        self.spark = spark
        self.storage_cfg = storage_cfg
        self.provider_registry = ProviderRegistry()
        self.dependency_graph = DependencyGraph()
        self.providers = providers or []
        self.models = models or []

    def ingest(
        self,
        providers: List[str] = None,
        tables: List[str] = None,
        tickers: List[str] = None,
        **kwargs
    ) -> Dict[str, List[IngestResult]]:
        """
        Run ingestion for specified providers.

        Args:
            providers: Provider names (default: all configured)
            tables: Specific tables to ingest (default: all from provider.yaml)
            tickers: Ticker filter (for securities providers)

        Returns:
            Dict mapping provider name to list of IngestResults
        """
        providers = providers or self.providers
        results = {}

        for provider_name in providers:
            ingestor = self.provider_registry.get_ingestor(
                provider_name,
                spark=self.spark,
                storage_cfg=self.storage_cfg
            )
            results[provider_name] = ingestor.ingest_all(
                tables=tables,
                tickers=tickers,
                **kwargs
            )

        return results

    def build(
        self,
        models: List[str] = None,
        **kwargs
    ) -> Dict[str, bool]:
        """
        Build models in dependency order.

        Args:
            models: Model names (default: all configured)

        Returns:
            Dict mapping model name to success/failure
        """
        models = models or self.models
        build_order = self.dependency_graph.resolve_order(models)
        results = {}

        for model_name in build_order:
            model = ModelRegistry.get_model(model_name, ...)
            try:
                model.build(**kwargs)
                results[model_name] = True
            except Exception as e:
                logger.error(f"Failed to build {model_name}: {e}")
                results[model_name] = False

        return results

    def run_pipeline(
        self,
        providers: List[str] = None,
        models: List[str] = None,
        skip_ingest: bool = False,
        skip_build: bool = False,
        **kwargs
    ) -> Dict:
        """
        Run full pipeline: ingest then build.

        Returns:
            Dict with 'ingest' and 'build' results
        """
        results = {'ingest': {}, 'build': {}}

        if not skip_ingest:
            results['ingest'] = self.ingest(providers=providers, **kwargs)

        if not skip_build:
            results['build'] = self.build(models=models, **kwargs)

        return results
```

**Scripts become thin wrappers:**

```python
# scripts/orchestrate.py (simplified)

def main():
    args = parse_args()
    spark = get_spark()
    storage_cfg = load_storage_config()

    orchestrator = Orchestrator(
        spark=spark,
        storage_cfg=storage_cfg,
        providers=args.providers,
        models=args.models
    )

    if args.ingest_only:
        results = orchestrator.ingest(tickers=args.tickers)
    elif args.build_only:
        results = orchestrator.build()
    else:
        results = orchestrator.run_pipeline(tickers=args.tickers)

    print_results(results)
```

---

### Phase 6: Multi-Source Data Expansion (NEXT STEPS)

**Goal:** Expand data sources and establish the Raw → Bronze → Silver pipeline architecture

**Status:** 🔜 NEXT STEPS

**WHY MULTI-SOURCE MATTERS:** Phase 8 (Airflow) will orchestrate multiple ingestion pipelines. Having only Alpha Vantage working means Airflow has nothing interesting to coordinate. This phase expands to multiple data sources so Phase 8 can demonstrate real orchestration value.

**First Task for Next Session:** Create exhaustive dataset inventory for each data source, including public safety datasets.

---

#### 6.1 The Raw Layer (NEW CONCEPT)

**Problem:** We have Bronze for cleaned API data, but no place for raw file downloads that need processing:
- CSV files from data portals
- PDF documents (financial reports, municipal budgets)
- Access databases (.mdb/.accdb)
- Excel files (.xlsx)
- Shapefiles and GIS data (TIGER/Line, etc.)

**Solution:** Add a **Raw layer** (sometimes called "ore" - unprocessed material) before Bronze for raw, unprocessed files.

**Data Flow:**
```
Raw (ore files)  →  Bronze (processed/normalized)  →  Silver (dimensional models)
     ↓                        ↓                              ↓
  CSVs, PDFs,           Delta Lake tables              Star/snowflake
  Access DBs,           from API responses             schemas for
  shapefiles            OR processed raw files         analytics
```

**Raw Layer Architecture:**
```
/shared/storage/raw/
├── chicago/
│   ├── budget_pdfs/           # Downloaded PDF budget documents
│   ├── employee_salary_csv/   # CSV exports from portal
│   └── gis_shapefiles/        # Geographic boundary files
├── cook_county/
│   ├── property_tax_db/       # Access database exports
│   ├── assessment_csv/        # CSV property assessments
│   └── parcel_shapefiles/     # Parcel boundary GIS
├── census/                    # US Census Bureau data
│   ├── tiger_shapefiles/      # TIGER/Line geographic boundaries
│   ├── acs_tables/            # American Community Survey tables
│   └── gazetteer/             # Place name files
└── fred/
    └── bulk_downloads/        # FRED bulk data files
```

**Raw Processing Scripts:**
```
scripts/raw/
├── download_raw.py              # Download raw files to Raw layer
├── process_csv_to_bronze.py     # CSV → Bronze Delta table
├── process_pdf_to_bronze.py     # PDF → extracted text/tables → Bronze
├── process_access_to_bronze.py  # Access DB → Bronze Delta tables
└── process_shapefile_to_bronze.py  # Shapefile → Bronze GIS table
```

---

#### 6.2 Data Sources Inventory

**TODO for next session:** Create exhaustive endpoint/dataset lists for each source. The lists below are starting points, not complete.

---

##### US Census Bureau (Geography Source)

**Portal:** https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
**API:** https://www.census.gov/data/developers/guidance/api-user-guide.html
**Current State:** States seeded from hardcoded data, need to pull from Census API/files

This is the **authoritative source** for US geography data used in seeding.

| Data Type | Source | Format | Notes |
|-----------|--------|--------|-------|
| **States** | FIPS codes | API/CSV | 50 states + DC + territories |
| **Counties** | TIGER/Line | Shapefiles/API | ~3,200 counties |
| **Places** (cities/towns) | TIGER/Line | Shapefiles/API | ~30,000 places |
| **Census Tracts** | TIGER/Line | Shapefiles | Statistical areas |
| **ZIP Code Tabulation Areas** | TIGER/Line | Shapefiles | ZCTA approximations |
| **Congressional Districts** | TIGER/Line | Shapefiles | 118th Congress |

**Key Census Resources:**
- **TIGER/Line Shapefiles**: Geographic boundaries (download to Raw, process to Bronze)
- **Gazetteer Files**: Place names with coordinates and FIPS codes
- **FIPS Codes**: Federal Information Processing Standard identifiers
- **GEOIDs**: Fully-qualified geographic identifiers (e.g., `050` prefix for counties)

**Current Implementation:**
- `models/foundation/geography/builders/state_builder.py` - Hardcoded 2020 Census data
- Future: Pull from Census API or TIGER/Line files in Raw layer

**Files to Create:**
```
configs/pipelines/census_endpoints.json      # Census API configuration
datapipelines/providers/census/
├── __init__.py
├── census_ingestor.py                       # Download TIGER files to Raw
└── facets/
    ├── tiger_states_facet.py                # Process state boundaries
    ├── tiger_counties_facet.py              # Process county boundaries
    └── gazetteer_facet.py                   # Process place names
```

---

##### Chicago Data Portal (Socrata API)

**Portal:** https://data.cityofchicago.org/
**API Type:** Socrata
**Current State:** 2 facets exist, 6 endpoints configured

| Category | Examples | Notes |
|----------|----------|-------|
| Economic | Business licenses, per capita income, economic indicators | Partially configured |
| Housing | Affordable housing, building permits | Partially configured |
| Public Safety | Crimes, 911 calls, fire incidents | **TODO: Add to endpoint config** |
| Transportation | Traffic crashes, divvy trips, CTA ridership | **TODO: Add to endpoint config** |
| Health | COVID data, food inspections | **TODO: Add to endpoint config** |

**Existing Files:**
- Config: `configs/pipelines/chicago_endpoints.json`
- Ingestor: `datapipelines/providers/chicago/chicago_ingestor.py`
- Facets: `datapipelines/providers/chicago/facets/`

---

##### Cook County Data Portal (NEW - Socrata API)

**Portal:** https://datacatalog.cookcountyil.gov/ (also: https://cookcounty.socrata.com/)
**API Type:** Socrata (same pattern as Chicago)
**Current State:** Provider does not exist - create from scratch

| Category | Examples | Notes |
|----------|----------|-------|
| Property | Parcels, sales, assessments, appeals | High value for city_finance model |
| Finance | Employee payroll, contracts, budget | Municipal analysis |
| Public Safety | Medical examiner cases, unclaimed persons | Public safety analysis |
| Performance | County performance measures | Government accountability |

**Files to Create:**
```
configs/pipelines/cook_county_endpoints.json
datapipelines/providers/cook_county/
├── __init__.py
├── provider.yaml
├── cook_county_registry.py
├── cook_county_ingestor.py
└── facets/
    ├── __init__.py
    ├── cook_county_base_facet.py
    ├── parcels_facet.py
    ├── property_sales_facet.py
    └── employee_payroll_facet.py
```

**Note:** Cook County uses Socrata, so provider pattern mirrors Chicago. Can potentially share base Socrata classes.

---

##### FRED - Federal Reserve Economic Data (NEW)

**Portal:** https://fred.stlouisfed.org/
**API Type:** REST API
**Current State:** Provider does not exist - create from scratch

| Category | Examples | Notes |
|----------|----------|-------|
| Interest Rates | Fed Funds, Treasury yields, mortgage rates | Daily/weekly |
| Employment | Unemployment rates (national, Chicago metro) | Monthly |
| Inflation | CPI, PCE | Monthly |
| GDP | Real GDP, GDP components | Quarterly |
| Housing | Case-Shiller indices, housing starts | Monthly |
| Regional | Chicago-specific economic indicators | Various |

**Files to Create:**
```
configs/pipelines/fred_endpoints.json
datapipelines/providers/fred/
├── __init__.py
├── provider.yaml
├── fred_registry.py
├── fred_ingestor.py
└── facets/
    ├── __init__.py
    ├── fred_base_facet.py
    └── observations_facet.py
```

---

##### BLS - Bureau of Labor Statistics

**Portal:** https://www.bls.gov/developers/
**API Type:** REST API
**Current State:** 2 facets exist (unemployment, CPI), 8 series configured

| Category | Examples | Notes |
|----------|----------|-------|
| Employment | Total nonfarm, industry-specific | Monthly |
| Prices | CPI, PPI | Monthly |
| Productivity | Labor productivity | Quarterly |
| Wages | Average hourly earnings | Monthly |
| Job Dynamics | JOLTS (openings, quits, hires) | Monthly |

**Existing Files:**
- Config: `configs/pipelines/bls_endpoints.json`
- Ingestor: `datapipelines/providers/bls/bls_ingestor.py`
- Facets: `datapipelines/providers/bls/facets/`

---

##### Alpha Vantage (Securities Data)

**Portal:** https://www.alphavantage.co/
**API Type:** REST API
**Current State:** Most complete provider, 8+ facets working

| Category | Examples | Notes |
|----------|----------|-------|
| Prices | Daily OHLCV, intraday | Working |
| Fundamentals | Income statement, balance sheet, cash flow | Working |
| Reference | Company overview, listing status | Working |
| Options | Historical options | Facet exists |
| Technical | SMA, RSI, MACD | TODO |

**Existing Files:**
- Config: `configs/pipelines/alpha_vantage_endpoints.json`
- Ingestor: `datapipelines/providers/alpha_vantage/alpha_vantage_ingestor.py`
- Facets: `datapipelines/providers/alpha_vantage/facets/` (8+ facets)

---

##### Reference Data Seeding

**Current State:** Scripts exist, need verification

| Seed | Script | Bronze Table | Notes |
|------|--------|--------------|-------|
| Calendar | `seed_calendar.py` | `calendar_seed` | 2000-2050, working |
| Geography (States) | `seed_geography.py` | `geography_states` | 56 records, working |
| Geography (Counties) | Future | `geography_counties` | Census data |
| Geography (Cities) | Future | `geography_cities` | Census data |

---

#### 6.3 Phase 6 Deliverables

**Part A: Raw Layer Setup**
- [ ] Create `storage/raw/` directory structure
- [ ] Create `scripts/raw/download_raw.py` base script
- [ ] Create `scripts/raw/process_csv_to_bronze.py`
- [ ] Document Raw → Bronze processing patterns

**Part B: Data Source Expansion**
- [ ] **Exhaustive inventory** of datasets for each source (including public safety)
- [ ] Create Cook County provider (mirrors Chicago Socrata pattern)
- [ ] Create FRED provider
- [ ] Expand Chicago endpoints (public safety, transportation, health)
- [ ] Expand BLS series coverage

**Part C: Integration**
- [ ] Update `configs/storage.json` with Raw paths
- [ ] Test multi-provider ingestion
- [ ] Document provider patterns for future sources

---

#### 6.4 Files to Create

| File | Description |
|------|-------------|
| **Raw Layer** | |
| `scripts/raw/download_raw.py` | Download raw files to Raw layer |
| `scripts/raw/process_csv_to_bronze.py` | Process CSV files to Bronze |
| `scripts/raw/process_pdf_to_bronze.py` | Extract data from PDFs |
| `scripts/raw/process_access_to_bronze.py` | Process Access databases |
| **Cook County Provider** | |
| `configs/pipelines/cook_county_endpoints.json` | Endpoint configuration |
| `datapipelines/providers/cook_county/*` | Provider implementation |
| **FRED Provider** | |
| `configs/pipelines/fred_endpoints.json` | Endpoint configuration |
| `datapipelines/providers/fred/*` | Provider implementation |
| **Infrastructure** | |
| `configs/storage.json` | Add Raw and new Bronze paths |

---

#### 6.5 Handoff Notes for Next Session

1. **First priority:** Create exhaustive dataset inventories for each data source
   - Chicago: Add public safety (crimes, 911, fire), transportation, health datasets
   - Cook County: Property, finance, public safety categories
   - Review each portal and document ALL available datasets

2. **Raw layer:** Start simple with CSV processing, expand to PDFs/Access DBs as needed

3. **Cook County:** Uses same Socrata API as Chicago - consider shared base classes

4. **Goal:** Multiple providers with comprehensive endpoint coverage so Airflow (Phase 8) has meaningful orchestration work

---

### Phase 7: Silver Model Builds

**Goal:** Build Silver layer models from Bronze data - create dimensional models for analytics

**Status:** Pending - After Phase 6

This phase transforms Bronze data into Silver dimensional models. Each model reads from Bronze and writes star/snowflake schemas to Silver.

#### Models to Build

| Model | Bronze Sources | Silver Tables | Builder Status |
|-------|---------------|---------------|----------------|
| `temporal` | `calendar_seed` | `dim_calendar` | ✅ Working |
| `company` | `company_overview`, `income_statements`, `balance_sheets`, `cash_flows` | `dim_company`, `fact_financials` | ⚠️ Partial |
| `stocks` | `securities_reference`, `securities_prices_daily`, `earnings` | `dim_stock`, `fact_stock_prices`, `fact_earnings` | ⚠️ Partial |
| `options` | `options_history` | `dim_option`, `fact_option_prices` | ❌ Skeleton |
| `etf` | `etf_profiles`, `securities_prices_daily` | `dim_etf`, `fact_etf_prices`, `fact_holdings` | ❌ Skeleton |
| `futures` | `securities_prices_daily` | `dim_future`, `fact_future_prices` | ❌ Skeleton |

#### Phase 7 Todo List

**7.1 Verify Existing Model Builds**
- [ ] Build temporal model: `python -m scripts.build.build_models --models temporal`
- [ ] Build company model: `python -m scripts.build.build_models --models company`
- [ ] Build stocks model: `python -m scripts.build.build_models --models stocks`
- [ ] Verify Silver tables at `/shared/storage/silver/`

**7.2 Complete Company Model**
- [ ] Update `company/graph.yaml` to include financial statement nodes
- [ ] Add `fact_income_statement` node from Bronze `income_statements`
- [ ] Add `fact_balance_sheet` node from Bronze `balance_sheets`
- [ ] Add `fact_cash_flow` node from Bronze `cash_flows`
- [ ] Update `CompanyBuilder` to build financial statement facts
- [ ] Test: `python -m scripts.build.build_models --models company`

**7.3 Complete Stocks Model**
- [ ] Update `stocks/graph.yaml` to include earnings node
- [ ] Add `fact_earnings` node from Bronze `earnings`
- [ ] Update `StocksBuilder` to build earnings facts
- [ ] Add earnings-related measures to `stocks/measures.yaml`
- [ ] Test: `python -m scripts.build.build_models --models stocks`

**7.4 Complete Options Model**
- [ ] Create `options/schema.yaml` with option dimensions (strike, expiry, type)
- [ ] Create `options/graph.yaml` with nodes from `options_history`
- [ ] Create `options/measures.yaml` with Greeks, IV measures
- [ ] Implement `OptionsBuilder` in `models/domain/options/builder.py`
- [ ] Test: `python -m scripts.build.build_models --models options`

**7.5 Complete ETF Model**
- [ ] Create `etf/schema.yaml` with ETF dimensions (holdings, sectors)
- [ ] Create `etf/graph.yaml` with nodes from `etf_profiles`
- [ ] Create `etf/measures.yaml` with NAV, expense ratio measures
- [ ] Implement `ETFBuilder` in `models/domain/etf/builder.py`
- [ ] Test: `python -m scripts.build.build_models --models etf`

**7.6 Complete Futures Model** (Lower Priority)
- [ ] Create futures schema, graph, measures YAML files
- [ ] Implement `FuturesBuilder`
- [ ] Test futures model build

**7.7 Full Pipeline Test**
- [ ] Run full build: `python -m scripts.build.build_models`
- [ ] Verify all Silver tables populated
- [ ] Test queries via DuckDB views
- [ ] Run `test_full_pipeline_spark.sh --profile dev`

#### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `configs/models/company/graph.yaml` | MODIFY | Add financial statement nodes |
| `configs/models/stocks/graph.yaml` | MODIFY | Add earnings node |
| `configs/models/options/schema.yaml` | CREATE | Option dimensions and facts |
| `configs/models/options/graph.yaml` | CREATE | Option graph structure |
| `configs/models/options/measures.yaml` | CREATE | Greeks, IV, P&L measures |
| `models/domain/options/builder.py` | CREATE | Options model builder |
| `configs/models/etf/schema.yaml` | CREATE | ETF dimensions |
| `configs/models/etf/graph.yaml` | CREATE | ETF graph structure |
| `models/domain/etf/builder.py` | CREATE | ETF model builder |

---

### Phase 8: Airflow Orchestration

**Goal:** Implement Apache Airflow to orchestrate Bronze ingestion and Silver model builds

**Status:** Pending - After Phase 7

With multiple endpoints and models now available, Airflow provides scheduled, monitored pipeline execution.

#### Proposed DAGs

| DAG | Schedule | Tasks | Description |
|-----|----------|-------|-------------|
| `bronze_daily_ingest` | Daily 6 AM EST | `ingest_prices`, `ingest_quotes` | Daily price updates |
| `bronze_weekly_reference` | Weekly Sunday | `ingest_listing_status`, `ingest_overview` | Reference data refresh |
| `bronze_quarterly_financials` | Quarterly | `ingest_income`, `ingest_balance`, `ingest_cashflow`, `ingest_earnings` | Financial statements |
| `silver_model_build` | After Bronze DAGs | `build_temporal`, `build_company`, `build_stocks`, `build_options`, `build_etf` | Model builds in dependency order |
| `silver_incremental` | Hourly (market hours) | `incremental_prices` | Near-realtime price updates |

#### Phase 8 Todo List

**8.1 Airflow Setup**
- [ ] Install Airflow on head node: `pip install apache-airflow`
- [ ] Initialize Airflow DB: `airflow db init`
- [ ] Create admin user: `airflow users create --role Admin ...`
- [ ] Configure `airflow.cfg` for production
- [ ] Start webserver and scheduler as services

**8.2 Create DAG Directory Structure**
- [ ] Create `dags/` directory in repo root
- [ ] Create `dags/bronze/` for ingestion DAGs
- [ ] Create `dags/silver/` for model build DAGs
- [ ] Create `dags/utils/` for shared utilities

**8.3 Implement Bronze DAGs**
- [ ] Create `dags/bronze/daily_ingest.py` - daily price ingestion
- [ ] Create `dags/bronze/weekly_reference.py` - reference data refresh
- [ ] Create `dags/bronze/quarterly_financials.py` - financial statements
- [ ] Test each DAG manually via Airflow UI

**8.4 Implement Silver DAGs**
- [ ] Create `dags/silver/model_build.py` - orchestrated model builds
- [ ] Implement dependency chain: temporal → company → stocks → options → etf
- [ ] Add failure alerting
- [ ] Test model build DAG

**8.5 Monitoring & Alerting**
- [ ] Configure email alerts for failures
- [ ] Set up Airflow web UI access
- [ ] Create dashboard for pipeline health
- [ ] Document runbook for common issues

**8.6 Integration Testing**
- [ ] Run full pipeline via Airflow (Bronze → Silver)
- [ ] Verify data quality post-pipeline
- [ ] Test failure recovery
- [ ] Document operational procedures

#### Files to Create

| File | Description |
|------|-------------|
| `dags/bronze/daily_ingest.py` | Daily price ingestion DAG |
| `dags/bronze/weekly_reference.py` | Weekly reference data DAG |
| `dags/bronze/quarterly_financials.py` | Quarterly financials DAG |
| `dags/silver/model_build.py` | Model build orchestration DAG |
| `dags/utils/spark_utils.py` | Spark session helpers for DAGs |
| `dags/utils/alerting.py` | Alert utilities |
| `configs/airflow/airflow.cfg` | Airflow configuration |
| `scripts/airflow/start_airflow.sh` | Airflow startup script |

---

### Phase 9: Validation & Testing

```python
# Usage:
# python -m scripts.validate_bronze --table securities_reference
# python -m scripts.validate_bronze --provider alpha_vantage
# python -m scripts.validate_bronze --all

# Output: JSON report + console summary
```

**Validation Metrics per Table:**

| Category | Metric | Description |
|----------|--------|-------------|
| **Row Stats** | `row_count` | Total rows in table |
| | `partition_count` | Number of partitions (if partitioned) |
| | `partition_row_distribution` | Min/max/avg rows per partition |
| **Column Stats** | `column_count` | Number of columns |
| | `column_types` | Data type of each column |
| **Null Analysis** | `null_count` | Nulls per column |
| | `null_pct` | Null percentage per column |
| | `columns_with_nulls` | List of columns with any nulls |
| | `fully_null_columns` | Columns that are 100% null (red flag) |
| **Diversity Stats** | `distinct_count` | Distinct values per column |
| | `distinct_pct` | Distinct % (distinct/total) |
| | `cardinality_class` | 'id' (>90%), 'category' (1-90%), 'constant' (<1%) |
| | `top_values` | Top 10 most frequent values per column |
| **Date Range** | `min_date` | Earliest date (for date columns) |
| | `max_date` | Latest date |
| | `date_gaps` | Missing dates in sequence |
| **Data Quality** | `duplicate_rows` | Count of exact duplicate rows |
| | `duplicate_keys` | Duplicates on expected unique columns |
| | `empty_strings` | Columns with empty string values |
| | `whitespace_only` | Columns with whitespace-only values |

**Validation Report Schema:**

```yaml
# Output: storage/reports/bronze_validation_{timestamp}.json

validation_report:
  generated_at: "2025-12-16T10:30:00Z"
  tables_validated: 12

  summary:
    total_rows: 1_500_000
    tables_with_issues: 3
    critical_issues: 1
    warnings: 5

  tables:
    - table: "bronze.alpha_vantage.securities_reference"
      path: "storage/bronze/alpha_vantage/securities_reference"
      format: "delta"

      row_stats:
        row_count: 8500
        partition_count: 45

      column_stats:
        column_count: 15
        columns:
          - name: "ticker"
            type: "string"
            null_count: 0
            null_pct: 0.0
            distinct_count: 8500
            distinct_pct: 100.0
            cardinality_class: "id"

          - name: "sector"
            type: "string"
            null_count: 234
            null_pct: 2.75
            distinct_count: 11
            distinct_pct: 0.13
            cardinality_class: "category"
            top_values:
              - value: "Technology"
                count: 2100
              - value: "Healthcare"
                count: 1500
              # ...

      date_analysis:
        date_columns: ["snapshot_dt"]
        snapshot_dt:
          min_date: "2024-01-01"
          max_date: "2025-12-15"
          date_gaps: []

      quality_issues:
        - severity: "warning"
          issue: "null_values"
          column: "sector"
          details: "234 rows (2.75%) have null sector"

        - severity: "info"
          issue: "low_cardinality"
          column: "asset_type"
          details: "Only 1 distinct value - may be constant"
```

**Console Output Example:**

```
╔══════════════════════════════════════════════════════════════════════╗
║                    BRONZE LAYER VALIDATION REPORT                     ║
╠══════════════════════════════════════════════════════════════════════╣
║ Generated: 2025-12-16 10:30:00                                        ║
║ Tables Validated: 12                                                  ║
╠══════════════════════════════════════════════════════════════════════╣

┌─ alpha_vantage.securities_reference ─────────────────────────────────┐
│ Rows: 8,500 │ Columns: 15 │ Partitions: 45 │ Format: delta           │
├──────────────────────────────────────────────────────────────────────┤
│ Column              │ Type    │ Nulls  │ Distinct │ Cardinality      │
│─────────────────────│─────────│────────│──────────│──────────────────│
│ ticker              │ string  │ 0%     │ 8,500    │ id (100%)        │
│ company_name        │ string  │ 0%     │ 8,495    │ id (99.9%)       │
│ sector              │ string  │ 2.75%  │ 11       │ category (0.1%)  │
│ industry            │ string  │ 3.1%   │ 142      │ category (1.7%)  │
│ market_cap          │ double  │ 5.2%   │ 8,100    │ id (95.3%)       │
│ cik                 │ string  │ 12.4%  │ 7,450    │ id (87.6%)       │
│ asset_type          │ string  │ 0%     │ 1        │ constant (0%)    │
├──────────────────────────────────────────────────────────────────────┤
│ ⚠ WARNING: 12.4% null CIK values - may impact company joins          │
│ ℹ INFO: asset_type is constant ('stocks') - expected for filtered    │
└──────────────────────────────────────────────────────────────────────┘

┌─ alpha_vantage.securities_prices_daily ──────────────────────────────┐
│ Rows: 1,250,000 │ Columns: 12 │ Partitions: 365 │ Format: delta      │
├──────────────────────────────────────────────────────────────────────┤
│ Date Range: 2024-01-02 to 2025-12-13 (347 trading days)              │
│ Tickers: 8,450 │ Avg rows/ticker: 148                                │
├──────────────────────────────────────────────────────────────────────┤
│ Column              │ Type    │ Nulls  │ Distinct │ Cardinality      │
│─────────────────────│─────────│────────│──────────│──────────────────│
│ ticker              │ string  │ 0%     │ 8,450    │ id               │
│ trade_date          │ date    │ 0%     │ 347      │ category         │
│ open                │ double  │ 0.02%  │ 892,000  │ id               │
│ close               │ double  │ 0%     │ 895,000  │ id               │
│ volume              │ long    │ 0.5%   │ 1,100K   │ id               │
├──────────────────────────────────────────────────────────────────────┤
│ ✓ No critical issues                                                 │
└──────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════
SUMMARY: 12 tables │ 1 critical │ 3 warnings │ 8 clean
═══════════════════════════════════════════════════════════════════════
```

**CLI Options:**

```bash
# Validate all Bronze tables
python -m scripts.validate_bronze --all

# Validate specific provider
python -m scripts.validate_bronze --provider alpha_vantage

# Validate specific table
python -m scripts.validate_bronze --table securities_reference

# Output formats
python -m scripts.validate_bronze --all --format json > report.json
python -m scripts.validate_bronze --all --format markdown > report.md

# Save to standard location
python -m scripts.validate_bronze --all --save
# Creates: storage/reports/bronze_validation_20251216_103000.json

# Fail on issues (for CI/CD)
python -m scripts.validate_bronze --all --fail-on-critical
python -m scripts.validate_bronze --all --fail-on-warnings
```

---

## Enhancement Phases

The following phases enhance the foundation with domain-specific models and features.

### Phase 9: Economic Series Enhancement (Days 25-29)

**Goal:** Generalized time series model for federal/state economic data

This phase creates a **reusable series model** that can ingest time series data from multiple federal and state sources. This is foundational for the Chicago actuarial analysis.

| # | Task | Files Affected |
|---|------|----------------|
| 8.1 | Create series model config | NEW: `configs/models/economic_series/*.yaml` |
| 8.2 | Create FRED provider | NEW: `datapipelines/providers/fred/` |
| 8.3 | Create BEA provider | NEW: `datapipelines/providers/bea/` |
| 8.4 | Create Census ACS provider | NEW: `datapipelines/providers/census_acs/` |
| 8.5 | Create EconomicSeriesModel class | NEW: `models/implemented/economic_series/model.py` |
| 8.6 | Define series catalog dimension | schema.yaml |
| 8.7 | Define series observations fact | schema.yaml |
| 8.8 | Create series measures | measures.py |

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

### Phase 10: Chart of Accounts Enhancement (Days 30-35)

**Goal:** Implement shared financial model base for city_finance and company

| # | Task | Files Affected |
|---|------|----------------|
| 9.1 | Create _base/financial config templates | NEW: `configs/models/_base/financial/*.yaml` |
| 9.2 | Create FinancialMeasures base class | NEW: `models/base/financial/measures.py` |
| 9.3 | Update city_finance to inherit from _base.financial | `configs/models/city_finance/*.yaml` |
| 9.4 | Update company to inherit from _base.financial | `configs/models/company/*.yaml` |
| 9.5 | Add NPV, CAGR, YoY measures to financial base | `measures.py` |
| 9.6 | Add incurred_period dimension support | `schema.yaml` |
| 9.7 | Test inheritance works correctly | Run test suite |
| 9.8 | Update company model for financial statements | `company/model.py` |

### Phase 11: City Services Enhancement (Days 36-42)

**Goal:** Model city departments, services, and performance metrics by geography

This phase adds the ability to analyze how well city services perform across different geographic areas - critical for understanding service equity and resource allocation.

| # | Task | Files Affected |
|---|------|----------------|
| 10.1 | Create city_services model config | NEW: `configs/models/city_services/*.yaml` |
| 10.2 | Define dim_department (Fire, Police, Admin, etc.) | schema.yaml |
| 10.3 | Define dim_service_type (emergency response, permits, etc.) | schema.yaml |
| 10.4 | Define fact_service_call (311, 911 calls by geo) | schema.yaml |
| 10.5 | Define fact_response_time (response metrics by geo) | schema.yaml |
| 10.6 | Define fact_department_budget (extends Chart of Accounts) | schema.yaml |
| 10.7 | Create CityServicesModel class | NEW: `models/implemented/city_services/model.py` |
| 10.8 | Create service performance measures | NEW: `city_services/measures.py` |
| 10.9 | Add Chicago 311/911 data endpoints | `chicago/chicago_ingestor.py` |
| 10.10 | Create analysis notebooks | NEW: `configs/notebooks/city_services/*.md` |

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

### Phase 12: Securities Models Enhancement (Days 43-49)

**Goal:** All securities models have working implementations

| # | Task | Files Affected |
|---|------|----------------|
| 11.1 | Create _base/securities Python module | NEW: `models/base/securities/measures.py` |
| 11.2 | Move shared securities measures from stocks | Refactor `stocks/measures.py` |
| 11.3 | Implement ETF model | NEW: `models/implemented/etf/model.py`, `measures.py` |
| 11.4 | Implement Options model | NEW: `models/implemented/options/model.py`, `measures.py` |
| 11.5 | Implement Futures model | NEW: `models/implemented/futures/model.py`, `measures.py` |
| 11.6 | Test all model builds | Run orchestrate.py --all |

### Phase 13: Company Chart of Accounts Enhancement (Days 50-56)

**Goal:** Build company-level Chart of Accounts from SEC filings (10-K, 10-Q) and cash flow statements

This extends the company model to use the `_base.financial` Chart of Accounts pattern, mapping SEC XBRL filings to a standardized account structure. This enables:
- Cash flow analysis across periods
- Balance sheet change tracking
- Cross-company comparisons using standardized accounts

| # | Task | Files Affected |
|---|------|----------------|
| 12.1 | Update company model to inherit from _base.financial | `configs/models/company/model.yaml` |
| 12.2 | Map SEC XBRL tags to Chart of Accounts structure | `configs/models/company/account_mapping.yaml` |
| 12.3 | Create dim_sec_account (standardized account codes) | `configs/models/company/schema.yaml` |
| 12.4 | Create fact_financial_position (balance sheet changes) | `configs/models/company/schema.yaml` |
| 12.5 | Create fact_cash_flow_detail (cash flow line items) | `configs/models/company/schema.yaml` |
| 12.6 | Add SEC filing facets for XBRL parsing | `alpha_vantage/facets/sec_filing.py` |
| 12.7 | Implement CompanyAccountingMeasures | `company/measures.py` |
| 12.8 | Add period-over-period change calculations | `company/measures.py` |
| 12.9 | Test with sample company filings | Test suite |

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

### Phase 14: Metadata Table Enhancement (Days 57-61)

**Goal:** Create operational model for tracking table metadata, pipeline runs, and data freshness

This model provides visibility into the data warehouse itself - tracking when tables were last updated, row counts, schema changes, and pipeline execution history.

| # | Task | Files Affected |
|---|------|----------------|
| 13.1 | Create metadata model config | NEW: `configs/models/metadata/*.yaml` |
| 13.2 | Define dim_table (catalog of all tables) | schema.yaml |
| 13.3 | Define dim_pipeline (pipeline definitions) | schema.yaml |
| 13.4 | Define fact_table_stats (row counts, sizes) | schema.yaml |
| 13.5 | Define fact_pipeline_run (execution history) | schema.yaml |
| 13.6 | Create MetadataModel class | NEW: `models/implemented/metadata/model.py` |
| 13.7 | Create metadata collection hooks | `orchestration/hooks/metadata_collector.py` |
| 13.8 | Add auto-update on model builds | Integrate with orchestrate.py |
| 13.9 | Create metadata dashboard notebook | `configs/notebooks/metadata/*.md` |

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

### Phase 15: Logger Model Enhancement (Days 62-67)

**Goal:** Create operational model for analyzing logs, errors, and warnings across all pipeline runs

This model aggregates log data to provide easy filtering, categorization, and statistics on pipeline health. Enables quick identification of recurring issues and trend analysis.

| # | Task | Files Affected |
|---|------|----------------|
| 14.1 | Create logger model config | NEW: `configs/models/logger/*.yaml` |
| 14.2 | Define dim_log_source (where logs come from) | schema.yaml |
| 14.3 | Define dim_error_category (error classification) | schema.yaml |
| 14.4 | Define fact_log_entry (individual log records) | schema.yaml |
| 14.5 | Define fact_error_summary (aggregated errors) | schema.yaml |
| 14.6 | Create LoggerModel class | NEW: `models/implemented/logger/model.py` |
| 14.7 | Create log ingestion from de_funk.log | `logger/log_parser.py` |
| 14.8 | Create error categorization rules | `configs/models/logger/error_rules.yaml` |
| 14.9 | Create logger dashboard notebook | `configs/notebooks/logger/*.md` |
| 14.10 | Add log rotation and archival | `scripts/maintenance/archive_logs.py` |

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

---

### Phase 16: Exhibit Enhancements (Days 68-72)

**Goal:** Wire exhibit YAML presets into rendering code and research/implement improved rendering methodology

This phase addresses the gap between Phase 3 (YAML preset definition) and actual exhibit rendering:
- Connect YAML presets to exhibit renderers (currently hardcoded defaults)
- Research and implement best practices for exhibit rendering architecture
- Standardize the exhibit inheritance pattern to match models
- Improve maintainability and configurability of exhibit components

| # | Task | Description | Status |
|---|------|-------------|--------|
| 15.1 | Audit current exhibit rendering | Document hardcoded values in all exhibit renderers | Pending |
| 15.2 | Create ExhibitConfigLoader | Load YAML presets similar to ModelConfigLoader | Pending |
| 15.3 | Wire presets into great_table.py | Connect `great_table.yaml` to renderer (currently unused) | Pending |
| 15.4 | Wire presets into line_chart.py | Load config from `line_chart.yaml` instead of hardcoded | Pending |
| 15.5 | Wire presets into bar_chart.py | Load config from `bar_chart.yaml` instead of hardcoded | Pending |
| 15.6 | Update BaseExhibitRenderer | Support preset loading in base class | Pending |
| 15.7 | Research rendering methodology | Evaluate Plotly vs alternatives, chart sizing, responsive design | Pending |
| 15.8 | Implement rendering improvements | Apply research findings to exhibit components | Pending |
| 15.9 | Update exhibit.py dispatcher | Use registry.yaml for dynamic renderer loading | Pending |
| 15.10 | Test exhibit rendering | Verify all exhibit types work with new preset system | Pending |

**Research Areas (Task 15.7):**
- Current rendering methodology (Plotly via `components.html()`)
- Alternative approaches (Streamlit native charts, Altair, etc.)
- Responsive design patterns for different screen sizes
- Chart interactivity and performance optimization
- Theme consistency between light/dark modes

**Current State Analysis:**
- `registry.yaml` exists but presets are NOT loaded by code
- `great_table.yaml` exists but is completely unused (hardcoded defaults in `great_table.py`)
- `line_chart.yaml`, `bar_chart.yaml` referenced in registry but don't exist
- `base_renderer.py` has hardcoded theme logic that should come from presets
- `exhibit.py` has hardcoded imports instead of using registry

---

### Phase 17: Final Cleanup & Validation (Days 73-75)

**Goal:** Address scope creep, deferred items, and perform final validation across all implemented phases

This phase is a catch-all for:
- Items deferred during earlier phases
- Scope creep that emerged during implementation
- Final integration testing across all models
- Performance validation and optimization
- Documentation updates

| # | Task | Description | Status |
|---|------|-------------|--------|
| 16.1 | Complete _backend removal from all models | Deferred from Phase 2 (requires Phase 5 session injection) | Pending |
| 16.2 | Optimize measure implementations | Consider Window Functions vs `_to_pandas()` for performance-critical measures | Pending |
| 16.3 | Final integration test suite | Run all models with both backends (Spark + DuckDB) | Pending |
| 16.4 | Performance benchmarking | Compare build times, query performance across backends | Pending |
| 16.5 | Documentation sync | Update CLAUDE.md, README, and guide docs with all changes | Pending |
| 16.6 | Deprecation cleanup | Remove all files marked with deprecation warnings in Phase 1 | Pending |
| 16.7 | **Scope creep backlog** | *(Items added during implementation go here)* | Backlog |

**Scope Creep Backlog:**
*(This section captures items that emerge during implementation but don't fit earlier phases)*

| Item | Source Phase | Description | Priority |
|------|-------------|-------------|----------|
| ETFs model config files | Phase 11 | Validate `etfs/schema.yaml`, `graph.yaml`, `measures.yaml` exist and errors resolved | High |
| Core YAML wiring | Phase 5 | Validate CoreModel/CalendarBuilder reads config from `core/graph.yaml` | High |
| Forecast YAML wiring | Phase 5 | Validate ForecastModel reads `ml_models` from `forecast/model.yaml` | High |

**Validation Checklist:**

- [ ] All models build successfully with DuckDB
- [ ] All models build successfully with Spark
- [ ] All measures calculate correctly on both backends
- [ ] No direct `import duckdb` or `import pyspark` in model code
- [ ] All deprecated files removed
- [ ] All tests passing
- [ ] Documentation up to date
- [ ] ETFs model config errors resolved (no missing schema/graph/measures.yaml)
- [ ] Exhibit YAML presets wired into renderers (Phase 15 validation)
- [ ] CoreModel reads calendar_config from YAML (Phase 5.11 validation)
- [ ] ForecastModel reads ml_models from YAML (Phase 5.12 validation)

---

### Total Estimated Effort

| Phase | Days | Priority | Type | Status |
|-------|------|----------|------|--------|
| Phase 1: Cleanup + Tool Utilization Audit | 2 | High | Foundation | ✅ COMPLETE |
| Phase 2: Backend Abstraction (UniversalSession) | 3 | High | Foundation | ✅ COMPLETE |
| Phase 3: Config Standardization | 3 | High | Foundation | ✅ COMPLETE |
| Phase 4: Core Geography (US-Agnostic) | 5 | High | Foundation | Pending |
| Phase 5: Spark Cluster Implementation | 4 | High | Foundation | ✅ COMPLETE |
| Phase 6: Multi-Source Data Expansion (Raw + providers) | 7 | High | Foundation | **NEXT STEPS** |
| Phase 7: Silver Model Builds (multi-source) | 5 | High | Foundation | Pending (after Phase 6) |
| Phase 8: Airflow Orchestration (4 providers) | 5 | High | Foundation | Pending (after Phase 7) |
| **Foundation Subtotal** | **32 days** | | | **4/8 Complete** |
| Phase 9: Economic Series Enhancement | 5 | High | Enhancement | |
| Phase 10: Chart of Accounts Enhancement | 6 | High | Enhancement | |
| Phase 11: City Services Enhancement | 7 | High | Enhancement | |
| Phase 12: Securities Models Enhancement | 7 | Medium | Enhancement | |
| Phase 13: Company Chart of Accounts Enhancement | 7 | High | Enhancement | |
| Phase 14: Metadata Table Enhancement | 5 | High | Enhancement | |
| Phase 15: Logger Model Enhancement | 6 | High | Enhancement | |
| **Enhancement Subtotal** | **43 days** | | | |
| Phase 16: Exhibit Enhancements | 5 | Medium | Exhibits | |
| **Exhibits Subtotal** | **5 days** | | | |
| Phase 17: Final Cleanup & Validation | 3 | Medium | Cleanup | |
| **Cleanup Subtotal** | **3 days** | | | |
| **Total** | **82 days** | | | |

---

## Commit Strategy

All commits during implementation will follow this naming convention:

```
Phase N: [Phase Name] - [Brief Description]

Example commits (Foundation phases - 1-3 ✅, 5 ✅ COMPLETE):
- "Phase 1: Cleanup - Delete deprecated v1.x YAML files" ✅
- "Phase 1: Cleanup - Rename etfs to etf directory" ✅
- "Phase 2: Backend Abstraction - Add query helper methods to UniversalSession" ✅
- "Phase 2: Backend Abstraction - Refactor StocksModel to use session methods" ✅
- "Phase 3: Config Standardization - Migrate core.yaml to modular structure" ✅
- "Phase 5: Spark Cluster - Implement cluster setup and pipeline scripts" ✅
- "Phase 5: Spark Cluster - Add profile-based run_config.json" ✅

Example commits (Foundation phases - NEXT STEPS):
- "Phase 6: Endpoints - Add OVERVIEW endpoint to alpha_vantage_endpoints.json"
- "Phase 6: Endpoints - Create IncomeStatementFacet for financial statements"
- "Phase 6: Models - Complete OptionsModel with Black-Scholes implementation"
- "Phase 7: Airflow - Create bronze_daily_ingest DAG"
- "Phase 7: Airflow - Set up Airflow web UI on head node"
- "Phase 8: Bronze Expansion - Validate all ingestors via Airflow"

Example commits (Enhancement phases 9-15):
- "Phase 9: Economic Series Enhancement - Create FRED provider"
- "Phase 10: Chart of Accounts Enhancement - Create _base/financial templates"
- "Phase 11: City Services Enhancement - Add 311/911 data endpoints"

Example commits (Exhibits phase 16):
- "Phase 16: Exhibits - Create ExhibitConfigLoader for preset loading"
- "Phase 16: Exhibits - Wire line_chart.yaml into renderer"

Example commits (Cleanup phase 17):
- "Phase 17: Final Cleanup - Remove _backend from all models"
- "Phase 17: Final Cleanup - Optimize rolling measures with Window Functions"
- "Phase 17: Final Cleanup - Run integration tests across both backends"
- "Phase 16: Final Cleanup - Remove deprecated scripts from Phase 1"
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

---

## Appendix B: Completed Steps Log

This log tracks all completed implementation steps as they are finished.

### Phase 1: Cleanup ✅ COMPLETE

#### 1A: File Cleanup ✅ COMPLETE

| Date | Commit | Task | Description |
|------|--------|------|-------------|
| 2025-12-16 | `40c558e` | 1.1 | Deleted deprecated v1.x `configs/models/company.yaml` |
| 2025-12-16 | `40c558e` | 1.1 | Deleted deprecated v1.x `configs/models/etf.yaml` |
| 2025-12-16 | `40c558e` | 1.2 | Verified `services.py` already deleted (not found) |
| 2025-12-16 | `40c558e` | 1.3 | Renamed `configs/models/etfs/` → `configs/models/etf/` |
| 2025-12-16 | `40c558e` | 1.4 | Updated doc references: `docs/vault/INDEX.md`, `010-alpha-vantage-expansion-unified-cashflow.md` |

**1A Summary:**
- Lines removed: 423 (deprecated v1.x configurations)
- Files deleted: 2 (company.yaml, etf.yaml)
- Directories renamed: 1 (etfs → etf)

#### 1B: Tool Utilization Audit ✅ COMPLETE

| Task | Description | Status |
|------|-------------|--------|
| 1.5 | Audit FilterEngine usage in models | ✅ Complete |
| 1.6 | Audit orchestrate.py usage | ✅ Complete |
| 1.7 | Audit DependencyGraph usage | ✅ Complete |
| 1.8 | Audit ProviderRegistry usage | ✅ Complete |
| 1.9 | Deprecate fragmented scripts | ✅ Complete |

**Audit Results:**

**1.5 FilterEngine Usage:**
- FilterEngine exists at `core/session/filters.py` (356 lines)
- **Used by**: `models/api/session.py` (4 uses), `models/api/auto_join.py` (6 uses)
- **NOT used by**: Domain models, base layer
- **Backend if-statements found**: 41 total instances
  - `models/implemented/stocks/model.py`: 9 instances
  - `models/implemented/company/model.py`: 6 instances
  - `models/implemented/etf/model.py`: 5 instances
  - `models/implemented/forecast/company_forecast_model.py`: 1 instance
  - `models/base/` layer: 11 instances
  - `models/api/` layer: 9 instances (some acceptable in session abstraction)
- **Phase 2 Target**: Remove 21 instances from domain models, push 11 from base layer to session

**1.6 orchestrate.py Usage:**
- Exists at `scripts/orchestrate.py` (760 lines)
- Uses DependencyGraph and ProviderRegistry internally
- **NOT called by**: Any other scripts (fragmented scripts bypass it)

**1.7 DependencyGraph Usage:**
- Exists at `orchestration/dependency_graph.py` (431 lines)
- **Used by**: `scripts/orchestrate.py` only
- **NOT used by**: Fragmented build scripts

**1.8 ProviderRegistry Usage:**
- Exists at `datapipelines/providers/registry.py`
- Provider.yaml files exist for: alpha_vantage, bls, chicago
- **Used by**: `scripts/orchestrate.py`, example scripts
- **NOT used by**: Fragmented pipeline scripts

**1.9 Deprecation Warnings Added:**
- `scripts/build_company_model.py` → use `orchestrate --models company --build-only`
- `scripts/build_silver_duckdb.py` → use `orchestrate --models <model> --build-only --backend duckdb`
- `scripts/run_full_pipeline.py` → use `orchestrate --all`

**Phase 1 Status:** ✅ COMPLETE - Ready for Phase 2

---

### Phase 2: Backend Abstraction (COMPLETE)

✅ **Completed 2025-12-17**

All session abstraction verified working. Models use UniversalSession without direct backend imports.

---

### Phase 3: Configuration Standardization (COMPLETE)

✅ **Completed 2025-12-17**

**Completed Tasks:**
- 3.5-3.10: Exhibit preset YAML files created (`_base/exhibit.yaml`, `plotly_base.yaml`, `line_chart.yaml`, `bar_chart.yaml`)
- 3.11: Registry updated with inheritance hierarchy
- 3.12: Model graph visualization on splash screen
- Core model migrated to modular YAML structure (`core/model.yaml`, `schema.yaml`, `graph.yaml`, `measures.yaml`)
- Forecast model migrated to modular YAML structure (`forecast/model.yaml`, etc.)

**Model Graph Visualization:**
- NetworkX spring_layout for force-directed positioning
- Interactive scroll zoom and pan via Plotly
- Shows inheritance, dependencies, and join key relationships
- Dims/facts fanned out around parent models
- Join keys displayed in edge hover tooltips

**Next Steps (Future Enhancements):**
- [ ] Add click interactivity to model nodes
- [ ] Create model profiling panel when node is clicked (show schema, measures, row counts)
- [ ] Add edge click to show full join definition

---

### Phase 5: Spark Cluster Implementation ✅ COMPLETE

✅ **Completed December 2025 - January 2026**

**Goal Achieved**: Pure Spark-based pipeline execution with cluster support, replacing the Delta Lake queue approach in favor of future Airflow integration.

**Implementation Summary:**

| Component | Location | Status |
|-----------|----------|--------|
| Cluster init script | `scripts/spark-cluster/init-cluster.sh` | ✅ Complete |
| Head node setup | `scripts/spark-cluster/setup-head.sh` | ✅ Complete |
| Worker node setup | `scripts/spark-cluster/setup-worker.sh` | ✅ Complete |
| Spark environment | `scripts/spark-cluster/spark-env.sh` | ✅ Complete |
| Master start/stop | `scripts/spark-cluster/start-master.sh`, `stop-cluster.sh` | ✅ Complete |
| Worker start/stop | `scripts/spark-cluster/start-worker.sh`, `start-all-workers.sh` | ✅ Complete |
| Cluster status | `scripts/spark-cluster/status.sh` | ✅ Complete |
| Job submission | `scripts/spark-cluster/submit-job.sh` | ✅ Complete |
| Pipeline runner | `scripts/spark-cluster/run_pipeline.sh` | ✅ Complete |
| Monitoring | `scripts/spark-cluster/monitoring/` | ✅ Complete |

**Profile-Based Configuration** (`run_config.json`):
- `quick_test`: 10 tickers for fast validation
- `dev`: 50 tickers for development
- `production`: All tickers from Bronze seed

**Main Pipeline Script**: `scripts/test/test_full_pipeline_spark.sh`
```bash
# Run with profile
./scripts/test/test_full_pipeline_spark.sh --profile dev

# Override ticker count
./scripts/test/test_full_pipeline_spark.sh --max-tickers 100
```

**Key Design Decisions:**
1. **Pure Spark execution** - No Ray cluster dependency
2. **NFS shared storage** at `/shared/storage` for Bronze/Silver layers
3. **Profile-based config** via `run_config.json` instead of CLI arguments
4. **Direct script execution** rather than Delta Lake queue (simpler for current scale)

**Scripts Consolidated (v2.6):**
- Removed Ray-based cluster scripts (migrated to pure Spark)
- Consolidated build scripts to `build_models.py`
- Consolidated ingest scripts to `run_bronze_ingestion.py`
- Main test script: `test_full_pipeline_spark.sh`

---

### Session: DuckDB Query Path Fixes (January 2026)

✅ **Completed 2026-01-06**

**Problem**: Financial statements notebook was crashing/freezing when displaying stock prices exhibit (22M+ rows). Root causes identified:

1. **Bronze reads during queries** - Session was falling back to `model.get_table()` which triggered `ensure_built()` → graph_builder → Bronze Delta reads
2. **fetchdf() loading all data** - DuckDB queries were calling `.fetchdf()` which materialized entire result sets into pandas memory
3. **Stale DuckDB views** - Views pointed to wrong storage paths and weren't auto-refreshed

**Files Modified:**

| File | Changes |
|------|---------|
| `models/api/auto_join.py` | Changed `fetchdf()` → `conn.sql()` for lazy evaluation; Removed Bronze fallbacks; Fixed `_build_select_cols()` to use DESCRIBE instead of `model.get_table()` |
| `models/api/session.py` | Removed Strategy 4 Bronze fallback; Fixed materialized view lookup to use session method |
| `core/duckdb_connection.py` | Added comprehensive view validation (dims AND facts); Added auto-refresh with correct storage paths |
| `scripts/setup/setup_duckdb_views.py` | Now reads `storage_path` from `run_config.json`; Added `--storage-path` CLI argument |

**Key Changes:**

1. **`_execute_duckdb_joins_via_views()`**: Returns lazy DuckDB relation via `conn.sql()` instead of `result.fetchdf()`
2. **`_execute_join_with_temp_tables()`**: Same lazy evaluation fix; Raises `RuntimeError` instead of Bronze fallback
3. **`_build_select_cols()`**: Uses `DESCRIBE {temp_table}` on already-registered temp tables instead of `model.get_table()`
4. **`_get_table_from_view_or_build()`**: Strategy 4 now raises `ValueError` with helpful error message instead of fallback
5. **View validation**: Checks BOTH dimensions AND facts (e.g., `dim_stock` AND `fact_stock_prices`)

**Query Path After Fixes:**
```
Query Request
  → Check DuckDB View
    → If valid: Return lazy DuckDB relation
    → If invalid: Auto-refresh views, retry
  → If no view: Read from Silver Delta files directly
    → Use delta_scan('/shared/storage/silver/...')
  → If no Silver: Raise ValueError with build instructions
  → NEVER: Read from Bronze (removed entirely)
```

**Commits:**
- `fix: Prevent memory crash and Bronze reads in auto-join`
- `fix: Auto-refresh stale DuckDB views on app load`
- `fix: Use DESCRIBE instead of model.get_table() in _build_select_cols`
- `fix: Remove Bronze fallbacks and improve view validation`
- `refactor: Remove all Bronze fallbacks from query paths`

---

---

## Pending Phases

**See Part 11: Step-by-Step Implementation Tasks** for detailed todo lists.

### Phase 6: Multi-Source Data Expansion (NEXT STEPS)

**Key Concepts:**
- **Raw Layer**: New storage tier for raw files (CSVs, PDFs, Access DBs, shapefiles) before Bronze processing
- **Data Sources**: Census Bureau, Chicago, Cook County (NEW), FRED (NEW), BLS, Alpha Vantage

**First Task for Next Session:**
Create exhaustive dataset inventories for each data source, including:
- Public safety datasets (crimes, 911 calls, fire incidents)
- Property/assessment data (Cook County)
- All categories from each portal

**Data Flow:**
```
Raw (ore) → Bronze (normalized) → Silver (dimensional)
```

### Phase 7: Silver Model Builds
Uses multi-source Bronze data from Phase 6

### Phase 8: Airflow Orchestration
Orchestrates multiple providers with different schedules (daily/weekly/quarterly)

### Phases 9-17: Enhancement & Cleanup
*Completion logs will be added here as phases are finished.*

