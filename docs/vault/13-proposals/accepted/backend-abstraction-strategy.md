# Backend Abstraction Strategy

**Date:** 2025-11-12
**Context:** Company Model Architecture Review - Backend Execution

---

## Problem Statement

With a unified measure framework, we need a clean way to execute measures across multiple backends (DuckDB, Spark) without duplicating logic in every measure class.

**Anti-pattern (What to Avoid):**
```python
class WeightedMeasure(BaseMeasure):
    def execute_duckdb(self, ...):
        # DuckDB-specific code
        # 50 lines of logic

    def execute_spark(self, ...):
        # Spark-specific code
        # 50 lines of nearly identical logic

    # If we add Polars, need execute_polars()
    # If we add DataFusion, need execute_datafusion()
    # etc... 🚫 NOT SUSTAINABLE
```

## Recommended Solution: SQL-First Architecture

### Core Principle

**Generate SQL as the universal interface. Both backends execute SQL natively.**

```
Measure Definition (YAML)
    ↓
Measure Class
    ↓
SQL Generation (with dialect support)
    ↓
Backend Adapter (execute SQL)
    ↓
Results (DataFrame/Arrow)
```

### Architecture

```
models/
├── base/
│   ├── measures/
│   │   ├── base_measure.py       # Abstract base
│   │   ├── executor.py           # Unified executor
│   │   └── registry.py           # Measure registry
│   └── backend/                   # NEW: Backend abstraction
│       ├── __init__.py
│       ├── adapter.py            # BackendAdapter interface
│       ├── duckdb_adapter.py     # DuckDB implementation
│       ├── spark_adapter.py      # Spark implementation
│       └── sql_builder.py        # SQL generation utilities
└── measures/
    ├── simple.py                 # Just generates SQL!
    ├── weighted.py               # Just generates SQL!
    └── window.py                 # Just generates SQL!
```

---

## Implementation

### Component 1: Backend Adapter Interface

**File:** `models/base/backend/adapter.py`

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass

@dataclass
class QueryResult:
    """Unified query result wrapper."""
    data: Any  # DataFrame (Pandas, Spark, Polars, etc.)
    backend: str
    query_time_ms: float
    rows: int

class BackendAdapter(ABC):
    """
    Abstract interface for backend execution.

    All backends must implement this interface.
    Measures generate SQL, adapters execute it.
    """

    def __init__(self, connection, model):
        self.connection = connection
        self.model = model
        self.dialect = self.get_dialect()

    @abstractmethod
    def get_dialect(self) -> str:
        """Get SQL dialect name (duckdb, spark, etc.)."""
        pass

    @abstractmethod
    def execute_sql(self, sql: str, params: Optional[Dict] = None) -> QueryResult:
        """
        Execute SQL query and return results.

        Args:
            sql: SQL query string
            params: Optional query parameters

        Returns:
            QueryResult with data and metadata
        """
        pass

    @abstractmethod
    def get_table_reference(self, table_name: str) -> str:
        """
        Get backend-specific table reference.

        Examples:
            DuckDB: "read_parquet('/path/to/table/*.parquet')"
            Spark: "silver.fact_prices"

        Args:
            table_name: Logical table name from model

        Returns:
            Backend-specific table reference string
        """
        pass

    @abstractmethod
    def supports_feature(self, feature: str) -> bool:
        """
        Check if backend supports a feature.

        Features: 'window_functions', 'cte', 'lateral_join', etc.
        """
        pass

    def format_limit(self, limit: int) -> str:
        """Format LIMIT clause (backend-specific)."""
        return f"LIMIT {limit}"

    def format_date_literal(self, date_str: str) -> str:
        """Format date literal (backend-specific)."""
        return f"DATE '{date_str}'"
```

### Component 2: DuckDB Adapter

**File:** `models/base/backend/duckdb_adapter.py`

```python
from pathlib import Path
import time
from .adapter import BackendAdapter, QueryResult

class DuckDBAdapter(BackendAdapter):
    """DuckDB backend adapter."""

    def get_dialect(self) -> str:
        return 'duckdb'

    def execute_sql(self, sql: str, params: Optional[Dict] = None) -> QueryResult:
        """Execute SQL in DuckDB."""
        start = time.time()

        # DuckDB execution
        result_df = self.connection.execute(sql).fetch_df()

        elapsed_ms = (time.time() - start) * 1000

        return QueryResult(
            data=result_df,
            backend='duckdb',
            query_time_ms=elapsed_ms,
            rows=len(result_df)
        )

    def get_table_reference(self, table_name: str) -> str:
        """
        Get DuckDB table reference.

        DuckDB reads directly from Parquet files.
        """
        # Get table path from model storage config
        table_path = self._resolve_table_path(table_name)

        if table_path.is_dir():
            # Read all parquet files in directory
            return f"read_parquet('{table_path}/*.parquet')"
        else:
            # Single file
            return f"read_parquet('{table_path}')"

    def supports_feature(self, feature: str) -> bool:
        """DuckDB feature support."""
        supported = {
            'window_functions': True,
            'cte': True,
            'lateral_join': True,
            'array_agg': True,
            'qualify': True,  # DuckDB-specific!
        }
        return supported.get(feature, False)

    def _resolve_table_path(self, table_name: str) -> Path:
        """Resolve logical table name to physical path."""
        # Get schema from model config
        schema = self.model.model_cfg.get('schema', {})

        # Check dimensions
        if table_name in schema.get('dimensions', {}):
            relative_path = schema['dimensions'][table_name]['path']
        # Check facts
        elif table_name in schema.get('facts', {}):
            relative_path = schema['facts'][table_name]['path']
        else:
            raise ValueError(f"Table '{table_name}' not found in model schema")

        # Build full path
        storage_root = Path(self.model.model_cfg['storage']['root'])
        return storage_root / relative_path
```

### Component 3: Spark Adapter

**File:** `models/base/backend/spark_adapter.py`

```python
import time
from .adapter import BackendAdapter, QueryResult

class SparkAdapter(BackendAdapter):
    """Spark backend adapter."""

    def get_dialect(self) -> str:
        return 'spark'

    def execute_sql(self, sql: str, params: Optional[Dict] = None) -> QueryResult:
        """Execute SQL in Spark."""
        start = time.time()

        # Spark execution
        spark_df = self.connection.sql(sql)

        # Optionally convert to Pandas (or keep as Spark DF)
        # result_df = spark_df.toPandas()

        elapsed_ms = (time.time() - start) * 1000

        return QueryResult(
            data=spark_df,  # Return Spark DataFrame
            backend='spark',
            query_time_ms=elapsed_ms,
            rows=spark_df.count()  # Expensive! Cache if needed
        )

    def get_table_reference(self, table_name: str) -> str:
        """
        Get Spark table reference.

        Spark uses catalog tables (database.table).
        """
        # In Spark, tables are registered in catalog
        # Typically: "silver.fact_prices"

        database = self.model.model_cfg.get('storage', {}).get('database', 'silver')
        return f"{database}.{table_name}"

    def supports_feature(self, feature: str) -> bool:
        """Spark feature support."""
        supported = {
            'window_functions': True,
            'cte': True,
            'lateral_join': True,
            'array_agg': True,
            'qualify': False,  # Not in Spark SQL
        }
        return supported.get(feature, False)

    def format_limit(self, limit: int) -> str:
        """Spark uses LIMIT."""
        return f"LIMIT {limit}"
```

### Component 4: SQL Builder Utilities

**File:** `models/base/backend/sql_builder.py`

```python
from typing import List, Optional
from .adapter import BackendAdapter

class SQLBuilder:
    """
    Utility for building SQL queries with dialect support.

    Provides common SQL patterns that work across backends.
    """

    def __init__(self, adapter: BackendAdapter):
        self.adapter = adapter
        self.dialect = adapter.get_dialect()

    def build_simple_aggregate(
        self,
        table_name: str,
        value_column: str,
        agg_function: str,
        group_by: List[str],
        filters: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> str:
        """
        Build simple aggregate query.

        Example:
            SELECT
                ticker,
                AVG(close) as avg_close
            FROM fact_prices
            WHERE close IS NOT NULL
            GROUP BY ticker
            ORDER BY avg_close DESC
            LIMIT 10
        """
        # Get table reference (backend-specific)
        table_ref = self.adapter.get_table_reference(table_name)

        # Build SELECT
        group_cols = ', '.join(group_by)
        select_clause = f"{group_cols}, {agg_function}({value_column}) as measure_value"

        # Build FROM
        from_clause = f"FROM {table_ref}"

        # Build WHERE
        where_clauses = [f"{value_column} IS NOT NULL"]
        if filters:
            where_clauses.extend(filters)
        where_clause = "WHERE " + " AND ".join(where_clauses)

        # Build GROUP BY
        group_clause = f"GROUP BY {group_cols}"

        # Build ORDER BY
        order_clause = ""
        if order_by:
            order_clause = "ORDER BY " + ", ".join(order_by)
        else:
            order_clause = "ORDER BY measure_value DESC"

        # Build LIMIT
        limit_clause = ""
        if limit:
            limit_clause = self.adapter.format_limit(limit)

        # Assemble query
        query = f"""
        SELECT
            {select_clause}
        {from_clause}
        {where_clause}
        {group_clause}
        {order_clause}
        {limit_clause}
        """

        return query.strip()

    def build_weighted_aggregate(
        self,
        table_name: str,
        value_column: str,
        weight_expression: str,
        group_by: List[str],
        filters: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None
    ) -> str:
        """
        Build weighted aggregate query.

        Example:
            SELECT
                trade_date,
                SUM(close * volume) / NULLIF(SUM(volume), 0) as weighted_value
            FROM fact_prices
            WHERE close IS NOT NULL AND volume > 0
            GROUP BY trade_date
            ORDER BY trade_date
        """
        table_ref = self.adapter.get_table_reference(table_name)
        group_cols = ', '.join(group_by)

        # Build weighted aggregation
        agg_clause = f"SUM({value_column} * {weight_expression}) / NULLIF(SUM({weight_expression}), 0) as weighted_value"

        # Build WHERE
        where_clauses = [
            f"{value_column} IS NOT NULL",
            f"{weight_expression} IS NOT NULL",
            f"{weight_expression} > 0"
        ]
        if filters:
            where_clauses.extend(filters)
        where_clause = "WHERE " + " AND ".join(where_clauses)

        # Build query
        query = f"""
        SELECT
            {group_cols},
            {agg_clause},
            COUNT(*) as entity_count
        FROM {table_ref}
        {where_clause}
        GROUP BY {group_cols}
        ORDER BY {group_cols}
        """

        return query.strip()
```

### Component 5: Updated Measure Implementation

**File:** `models/measures/weighted.py`

```python
from typing import Any, Dict
from models.base.measures.base_measure import BaseMeasure, MeasureType
from models.base.measures.registry import MeasureRegistry
from models.base.backend.sql_builder import SQLBuilder

@MeasureRegistry.register(MeasureType.WEIGHTED)
class WeightedMeasure(BaseMeasure):
    """
    Weighted aggregate measure.

    NOW: Just generates SQL, backend adapter executes it!
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.weighting_method = config.get('weighting_method', 'equal')
        self.group_by = config.get('group_by', ['trade_date'])

    def to_sql(self, adapter) -> str:
        """
        Generate SQL for weighted aggregate.

        Uses backend adapter to get correct table references
        and SQL dialect.
        """
        from models.domains.equities.weighting import get_weighting_strategy

        # Get weighting strategy
        strategy = get_weighting_strategy(self.weighting_method)

        # Parse source
        table_name, value_col = self._parse_source()

        # Generate SQL using strategy and adapter
        return strategy.generate_sql(
            adapter=adapter,
            table_name=table_name,
            value_column=value_col,
            group_by=self.group_by
        )

    def execute(self, adapter, **kwargs):
        """
        Execute measure using backend adapter.

        This is the ONLY execution method!
        No execute_duckdb() or execute_spark() needed!
        """
        # Generate SQL
        sql = self.to_sql(adapter)

        # Execute via adapter (works for any backend!)
        result = adapter.execute_sql(sql)

        return result
```

### Component 6: Updated Weighting Strategy

**File:** `models/domains/equities/weighting.py`

```python
from abc import ABC, abstractmethod

class WeightingStrategy(ABC):
    """Base class for weighting strategies."""

    @abstractmethod
    def generate_sql(
        self,
        adapter,        # BackendAdapter instance
        table_name: str,
        value_column: str,
        group_by: List[str]
    ) -> str:
        """Generate SQL using adapter for backend-specific references."""
        pass

class VolumeWeightStrategy(WeightingStrategy):
    """Volume-weighted average."""

    def generate_sql(self, adapter, table_name, value_column, group_by):
        """Generate SQL with backend-specific table references."""
        from models.base.backend.sql_builder import SQLBuilder

        builder = SQLBuilder(adapter)

        return builder.build_weighted_aggregate(
            table_name=table_name,
            value_column=value_column,
            weight_expression='volume',
            group_by=group_by
        )
```

### Component 7: Unified Measure Executor

**File:** `models/base/measures/executor.py`

```python
from typing import Optional
from models.base.backend.adapter import BackendAdapter
from models.base.backend.duckdb_adapter import DuckDBAdapter
from models.base.backend.spark_adapter import SparkAdapter
from .registry import MeasureRegistry

class MeasureExecutor:
    """
    Unified executor for all measure types.

    NOW: Uses backend adapters!
    """

    def __init__(self, model, backend: str = 'duckdb'):
        self.model = model
        self.backend = backend

        # Create appropriate backend adapter
        self.adapter = self._create_adapter()

    def _create_adapter(self) -> BackendAdapter:
        """Factory method for backend adapters."""
        if self.backend == 'duckdb':
            return DuckDBAdapter(self.model.connection, self.model)
        elif self.backend == 'spark':
            return SparkAdapter(self.model.connection, self.model)
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    def execute_measure(
        self,
        measure_name: str,
        entity_column: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs
    ):
        """
        Execute a measure from model configuration.

        NOW: Backend-agnostic! Same code path for all backends!
        """
        # Get measure config
        measure_config = self.model.model_cfg.get('measures', {}).get(measure_name)
        if not measure_config:
            raise ValueError(f"Measure '{measure_name}' not defined")

        # Add name to config
        measure_config = {**measure_config, 'name': measure_name}

        # Create measure instance using registry
        measure = MeasureRegistry.create_measure(measure_config)

        # Execute using adapter (works for ANY backend!)
        result = measure.execute(self.adapter, **kwargs)

        # Apply limit if needed
        if limit and result.rows > limit:
            result.data = result.data.head(limit)  # Works for Pandas/Spark

        return result
```

---

## Usage Examples

### Example 1: Same Code, Different Backends

```python
# DuckDB backend
company_model_duckdb = CompanyModel(duckdb_conn, storage, repo, backend='duckdb')
result1 = company_model_duckdb.calculate_measure('volume_weighted_index')
# → SQL executed in DuckDB, reads from Parquet

# Spark backend
company_model_spark = CompanyModel(spark_session, storage, repo, backend='spark')
result2 = company_model_spark.calculate_measure('volume_weighted_index')
# → SAME SQL executed in Spark, reads from catalog

# THE MEASURE CODE IS IDENTICAL!
# Only the adapter changes!
```

### Example 2: Backend-Specific Optimizations

```python
class VolumeWeightStrategy(WeightingStrategy):
    def generate_sql(self, adapter, table_name, value_column, group_by):
        # Check backend capabilities
        if adapter.supports_feature('qualify'):
            # Use DuckDB's QUALIFY clause (more efficient)
            return self._generate_with_qualify(adapter, ...)
        else:
            # Use standard SQL
            return self._generate_standard(adapter, ...)
```

### Example 3: Adding New Backend (Polars)

```python
# Just implement the adapter!
class PolarsAdapter(BackendAdapter):
    def get_dialect(self) -> str:
        return 'polars'

    def execute_sql(self, sql: str, params=None):
        # Polars doesn't have SQL yet, translate to LazyFrame operations
        # Or use polars.sql() when available
        ...

    def get_table_reference(self, table_name: str) -> str:
        return f"pl.scan_parquet('{self._resolve_path(table_name)}')"

# That's it! All measures now work with Polars!
```

---

## Benefits of SQL-First Approach

### ✅ Single Code Path
- Measures generate SQL once
- SQL works on both DuckDB and Spark
- No separate `execute_duckdb()` and `execute_spark()` methods

### ✅ Backend-Agnostic
- 90% of measure logic is backend-independent
- Only table references are backend-specific
- Easy to add new backends (just implement adapter)

### ✅ Inspectable & Debuggable
- Can print generated SQL
- Can test SQL independently
- Can optimize SQL with `EXPLAIN PLAN`

### ✅ Cacheable
- SQL queries can be cached
- Results can be materialized
- Query plans can be analyzed

### ✅ Standard & Familiar
- SQL is universal
- Easy for new developers to understand
- Can reuse existing SQL knowledge

---

## When to Use Custom Executors

For 10% of cases where SQL isn't sufficient:

```python
class ComplexMLMeasure(BaseMeasure):
    """Measure requiring custom Python/ML logic."""

    def to_sql(self, adapter) -> str:
        # Not applicable
        raise NotImplementedError("This measure requires custom execution")

    def execute(self, adapter, **kwargs):
        # Custom logic here
        # Fetch data via adapter
        data = adapter.execute_sql("SELECT * FROM fact_prices")

        # Run ML model
        predictions = self.ml_model.predict(data.data)

        # Return result
        return QueryResult(
            data=predictions,
            backend=adapter.dialect,
            ...
        )
```

---

## Recommended Migration Path

### Phase 1: Build Adapter Infrastructure
1. Implement `BackendAdapter` interface
2. Implement `DuckDBAdapter`
3. Implement `SparkAdapter`
4. Implement `SQLBuilder` utilities

### Phase 2: Migrate Simple Measures
1. Update `SimpleMeasure` to use adapters
2. Test with both backends
3. Validate results match

### Phase 3: Migrate Weighted Measures
1. Update `WeightedMeasure` to use adapters
2. Update weighting strategies to use `SQLBuilder`
3. Test with both backends

### Phase 4: Update MeasureExecutor
1. Replace backend-specific execution with adapters
2. Update CompanyModel to use new executor
3. Deprecate old methods

---

## Summary

**YAML = Measure Specification (WHAT)**
- Declarative definition of what to calculate

**Measure Class = SQL Generator (HOW)**
- Business logic in SQL generation
- No backend-specific code

**Backend Adapter = Execution Engine (WHERE)**
- Handles backend-specific details
- Executes SQL, returns results

**SQL = Universal Interface**
- Works on both DuckDB and Spark
- Standard, inspectable, cacheable

This approach:
- ✅ Eliminates code duplication
- ✅ Makes backends pluggable
- ✅ Keeps measure logic simple
- ✅ Easy to test and debug
- ✅ Follows separation of concerns

**Next Steps:**
1. Implement adapter infrastructure
2. Migrate one measure type as proof-of-concept
3. Validate performance
4. Roll out to all measures
