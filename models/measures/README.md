# Measures Framework

This directory contains the de_Funk measure calculation framework. Measures are reusable calculations that can be applied to model data.

## Architecture Overview

```
models/measures/
├── README.md              # This file
├── __init__.py            # Public exports
├── base_measure.py        # BaseMeasure abstract class, MeasureType enum
├── registry.py            # MeasureRegistry - discovers and stores measures
├── executor.py            # MeasureExecutor - runs measure calculations
├── simple.py              # SimpleMeasure - single-column aggregations
├── computed.py            # ComputedMeasure - multi-column expressions
└── domain_measures.py     # DomainMeasures - base class for complex Python measures
```

## Measure Types

### 1. YAML Measures (Simple & Computed)

Defined in `configs/models/{model}/measures.yaml`. Best for declarative, SQL-expressible calculations.

**Simple Measures** - Single column aggregations:
```yaml
simple_measures:
  avg_close:
    type: simple
    source: fact_prices.close
    aggregation: avg
    format: "#,##0.00"

  total_volume:
    type: simple
    source: fact_prices.volume
    aggregation: sum
```

**Computed Measures** - Multi-column expressions:
```yaml
computed_measures:
  price_range:
    type: computed
    expression: "high - low"
    sources:
      - fact_prices.high
      - fact_prices.low

  volume_weighted_price:
    type: computed
    expression: "(close * volume) / SUM(volume)"
    sources:
      - fact_prices.close
      - fact_prices.volume
```

### 2. Python Measures (Domain-Specific)

Defined in `models/domains/{category}/{model}/measures.py`. Best for complex calculations requiring:
- Rolling windows with custom logic
- Cross-ticker calculations (correlations, rankings)
- Multi-step algorithms (technical indicators, risk metrics)
- External library integrations (numpy, scipy, sklearn)

**YAML Reference:**
```yaml
python_measures:
  sharpe_ratio:
    function: "stocks.measures.calculate_sharpe_ratio"
    params:
      risk_free_rate: 0.045
      window_days: 252
```

**Python Implementation:**
```python
from models.measures import DomainMeasures

class StocksMeasures(DomainMeasures):
    def calculate_sharpe_ratio(self, ticker=None, risk_free_rate=0.045, **kwargs):
        # Implementation here
        pass
```

## When to Use Each Type

| Scenario | Measure Type | Why |
|----------|--------------|-----|
| SUM, AVG, MIN, MAX on a column | Simple | Declarative, no code needed |
| Column math (A + B, A / B) | Computed | SQL handles it efficiently |
| Rolling calculations | **Python** | Window functions need custom logic |
| Cross-entity comparisons | **Python** | Requires pivoting/grouping |
| Risk metrics (Sharpe, Beta) | **Python** | Statistical libraries needed |
| Composite scores | **Python** | Multi-step normalization |
| External API calls | **Python** | Can't do in SQL |

## Creating Domain Measures

### Step 1: Create the measures.py file

Location: `models/domains/{category}/{model}/measures.py`

```python
"""
Complex measures for {model} model.

These functions are referenced from {model}/measures.yaml via python_measures.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List

from models.measures import DomainMeasures


class {Model}Measures(DomainMeasures):
    """
    Complex measure calculations for {model}.

    Inherits from DomainMeasures which provides:
    - get_table(): Backend-agnostic data access with filtering
    - _to_pandas(): DataFrame conversion (Spark, DuckDB, pandas)
    - rolling_apply(): Grouped rolling calculations
    - normalize_to_range(): Min-max normalization
    - calculate_returns(): Return calculations
    - log_start/log_result: Logging helpers
    """

    def calculate_my_measure(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        param1: float = 1.0,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate my custom measure.

        Args:
            ticker: Optional ticker filter
            filters: Optional additional filters
            param1: Example parameter from YAML
            **kwargs: Additional runtime parameters

        Returns:
            DataFrame with measure results
        """
        self.log_start("my_measure", ticker=ticker, param1=param1)

        # 1. Get data from model (backend-agnostic)
        df = self.get_table('fact_prices', ticker=ticker, filters=filters)

        # 2. Perform calculation
        df['result'] = df['close'] * param1

        # 3. Select output columns
        result = df[['ticker', 'trade_date', 'result']]

        self.log_result("my_measure", result)
        return result
```

### Step 2: Reference in YAML

Add to `configs/models/{model}/measures.yaml`:

```yaml
python_measures:
  my_measure:
    function: "{model}.measures.calculate_my_measure"
    description: "Description of what this measure calculates"
    params:
      param1: 1.0
    output_columns:
      - ticker
      - trade_date
      - result
```

### Step 3: Wire up in model (if needed)

If your model doesn't auto-load measures, add to the model class:

```python
from models.domains.{category}.{model}.measures import {Model}Measures

class {Model}Model(BaseModel):
    def __init__(self, ...):
        super().__init__(...)
        self._measures = {Model}Measures(self)

    def calculate_measure(self, measure_name: str, **kwargs):
        method = getattr(self._measures, f"calculate_{measure_name}", None)
        if method:
            return method(**kwargs)
        return super().calculate_measure(measure_name, **kwargs)
```

## DomainMeasures Base Class

The `DomainMeasures` class provides common utilities:

### Data Access

```python
# Get table with automatic backend conversion
df = self.get_table('fact_prices', ticker='AAPL', as_pandas=True)

# Get table with filters
filters = [{'column': 'trade_date', 'operator': '>=', 'value': '2024-01-01'}]
df = self.get_table('fact_prices', filters=filters)
```

### Calculation Utilities

```python
# Rolling calculations with grouping
df['rolling_mean'] = self.rolling_apply(
    df, 'close', np.mean, window=20, group_by='ticker'
)

# Normalize to [0, 1] range
df['normalized'] = self.normalize_to_range(df['value'])

# Calculate returns
df['returns'] = self.calculate_returns(df, price_column='close', log_returns=False)
```

### Logging

```python
# Log start with parameters
self.log_start("sharpe_ratio", ticker=ticker, window=252)

# Log result summary
self.log_result("sharpe_ratio", result_df)
# Output: "sharpe_ratio: 1,234 rows, columns: ['ticker', 'trade_date', 'sharpe_ratio']"
```

## Best Practices

### 1. Always be backend-agnostic

```python
# GOOD: Use get_table() which handles conversion
df = self.get_table('fact_prices')

# BAD: Assuming pandas directly
df = self.model.tables['fact_prices']  # Might be Spark DataFrame!
```

### 2. Support filtering consistently

```python
def calculate_measure(
    self,
    ticker: Optional[str] = None,        # Single ticker filter
    filters: Optional[List[Dict]] = None, # General filters
    **kwargs                              # YAML params + runtime overrides
) -> pd.DataFrame:
```

### 3. Return consistent output format

```python
# Always return DataFrame with clear columns
return df[['ticker', 'trade_date', 'measure_value']]

# Document output columns in YAML
output_columns:
  - ticker
  - trade_date
  - measure_value
```

### 4. Handle edge cases

```python
# Check for empty data
if df.empty:
    return pd.DataFrame(columns=['ticker', 'trade_date', 'result'])

# Handle division by zero
df['ratio'] = df['a'] / df['b'].replace(0, np.nan)

# Handle missing values in rolling
df['rolling'] = df['close'].rolling(window=20, min_periods=10).mean()
```

### 5. Use YAML params with runtime overrides

```yaml
# YAML default
params:
  window_days: 252
```

```python
# Runtime override
result = model.calculate_measure('sharpe_ratio', window_days=60)
```

## Real-World Examples

See `models/domains/securities/stocks/measures.py` for complete implementations:

- `calculate_sharpe_ratio()` - Risk-adjusted returns
- `calculate_correlation_matrix()` - Cross-ticker correlations
- `calculate_momentum_score()` - Composite momentum indicator
- `calculate_sector_rotation()` - Sector-level signals
- `calculate_rolling_beta()` - Market beta calculation
- `calculate_drawdown()` - Peak-to-trough decline

## Testing Measures

```python
# Unit test example
def test_sharpe_ratio_calculation():
    # Arrange
    model = create_test_model()
    measures = StocksMeasures(model)

    # Act
    result = measures.calculate_sharpe_ratio(ticker='AAPL', window_days=60)

    # Assert
    assert 'ticker' in result.columns
    assert 'sharpe_ratio' in result.columns
    assert len(result) > 0
```

## Troubleshooting

### "Table not found" error

Check that the table name matches your model's schema:
```python
# Check available tables
print(self.model.tables.keys())
```

### Backend conversion errors

Ensure you're using `get_table()` or `_to_pandas()`:
```python
# This handles Spark, DuckDB, and pandas automatically
df = self.get_table('fact_prices', as_pandas=True)
```

### Filter not applying

Filters require a session with filter engine:
```python
if self.model.session:
    df = self.model.session.apply_filters(df, filters)
else:
    # Manual filtering fallback
    for f in filters:
        df = df[df[f['column']] == f['value']]
```
