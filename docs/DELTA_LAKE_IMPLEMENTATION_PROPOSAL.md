# Delta Lake Storage Implementation Proposal

**Version:** 1.0
**Date:** 2025-11-13
**Status:** Proposed - Ready for Implementation

---

## 🎯 Executive Summary

Migrate from Parquet to **Delta Lake** format using DuckDB's new Delta extension for ACID transactions, time travel, and schema evolution.

**Key Benefits:**
- ✅ ACID transactions (atomic writes, no partial failures)
- ✅ Time travel (query historical data, rollback changes)
- ✅ Schema evolution (add/remove columns without rewrites)
- ✅ Optimized writes (merge, upsert, delete operations)
- ✅ DuckDB native support (fast queries, no Spark overhead)
- ✅ Audit trail (track all changes with versioning)

**Migration Strategy:** Parallel storage during transition, then cutover

**Timeline:** 1-2 weeks for implementation + testing

---

## 📊 Current vs. Proposed Architecture

### Current (Parquet)

```
storage/
├── bronze/
│   └── prices_daily/
│       ├── trade_date=2024-01-01/
│       │   └── part-00000.snappy.parquet  ← Single file per partition
│       └── trade_date=2024-01-02/
│           └── part-00000.snappy.parquet
└── silver/
    ├── equity/
    │   └── facts/fact_equity_prices/
    │       ├── trade_date=2024-01-01/
    │       │   └── part-00000.parquet      ← Overwrite only
    │       └── trade_date=2024-01-02/
    │           └── part-00000.parquet
```

**Issues:**
- ❌ No ACID (partial writes on failure)
- ❌ Overwrite only (can't merge/upsert)
- ❌ No versioning (can't rollback mistakes)
- ❌ Schema changes require full rewrites
- ❌ No audit trail

### Proposed (Delta Lake)

```
storage/
├── bronze/
│   └── prices_daily/                      ← Delta table
│       ├── _delta_log/
│       │   ├── 00000000000000000000.json  ← Transaction log (version 0)
│       │   ├── 00000000000000000001.json  ← Version 1
│       │   └── 00000000000000000002.json  ← Version 2 (current)
│       ├── trade_date=2024-01-01/
│       │   ├── part-00000-<uuid>.snappy.parquet
│       │   └── part-00001-<uuid>.snappy.parquet (after merge)
│       └── trade_date=2024-01-02/
│           └── part-00000-<uuid>.snappy.parquet
└── silver/
    ├── equity/
    │   └── facts/fact_equity_prices/       ← Delta table
    │       ├── _delta_log/
    │       │   ├── 00000000000000000000.json
    │       │   └── 00000000000000000001.json
    │       ├── trade_date=2024-01-01/
    │       │   └── part-00000-<uuid>.parquet
    │       └── trade_date=2024-01-02/
    │           └── part-00000-<uuid>.parquet
```

**Benefits:**
- ✅ ACID transactions (all or nothing)
- ✅ Merge/upsert/delete operations
- ✅ Time travel (`VERSION AS OF 5`, `TIMESTAMP AS OF`)
- ✅ Schema evolution (add columns seamlessly)
- ✅ Automatic compaction and optimization
- ✅ Full audit trail in transaction log

---

## 🔧 DuckDB Delta Lake Support

### Extension Installation

```python
import duckdb

# Install delta extension
conn = duckdb.connect()
conn.execute("INSTALL delta")
conn.execute("LOAD delta")

# Verify installation
result = conn.execute("SELECT * FROM duckdb_extensions() WHERE extension_name = 'delta'").fetchone()
print(f"✓ Delta extension installed: {result}")
```

### Delta Operations Supported

```python
# CREATE Delta table
conn.execute("""
    CREATE TABLE delta_prices AS
    SELECT * FROM read_parquet('prices.parquet')
""")

# Write to Delta (overwrite)
conn.execute("""
    COPY (SELECT * FROM new_data)
    TO 'storage/delta/prices'
    (FORMAT DELTA, OVERWRITE_OR_IGNORE)
""")

# Write to Delta (append)
conn.execute("""
    COPY (SELECT * FROM additional_data)
    TO 'storage/delta/prices'
    (FORMAT DELTA)
""")

# Read Delta table
df = conn.execute("SELECT * FROM delta_scan('storage/delta/prices')").df()

# Time travel - read specific version
df_v5 = conn.execute("""
    SELECT * FROM delta_scan('storage/delta/prices', version => 5)
""").df()

# Time travel - read at timestamp
df_yesterday = conn.execute("""
    SELECT * FROM delta_scan('storage/delta/prices',
                              timestamp => '2024-11-12 00:00:00')
""").df()

# Get table history/metadata
history = conn.execute("""
    SELECT * FROM delta_scan_metadata('storage/delta/prices')
""").df()
```

### Advanced Operations (via Delta-RS Python library)

```python
from deltalake import DeltaTable, write_deltalake
import pyarrow as pa

# MERGE operation (upsert)
dt = DeltaTable('storage/delta/prices')

dt.merge(
    source=new_data_df,
    predicate='target.ticker = source.ticker AND target.trade_date = source.trade_date',
    source_alias='source',
    target_alias='target'
).when_matched_update(
    updates={
        'close': 'source.close',
        'volume': 'source.volume',
        'updated_at': 'CURRENT_TIMESTAMP'
    }
).when_not_matched_insert(
    values={
        'ticker': 'source.ticker',
        'trade_date': 'source.trade_date',
        'close': 'source.close',
        'volume': 'source.volume',
        'created_at': 'CURRENT_TIMESTAMP'
    }
).execute()

# DELETE operation
dt.delete(predicate="trade_date < '2020-01-01'")

# VACUUM (remove old files)
dt.vacuum(retention_hours=168)  # Keep 7 days of history

# OPTIMIZE (compact small files)
dt.optimize.compact()
dt.optimize.z_order(['ticker', 'trade_date'])  # Z-order clustering
```

---

## 🏗️ Implementation Architecture

### 1. Delta Storage Service

```
core/storage/
├── __init__.py
├── base_storage.py          ← Base class
├── parquet_storage.py       ← Existing (keep for compatibility)
└── delta_storage.py         ← NEW: Delta Lake storage
```

**delta_storage.py:**
```python
class DeltaLakeStorage(BaseStorage):
    """
    Delta Lake storage service using DuckDB delta extension.

    Features:
    - ACID transactions
    - Time travel
    - Merge/upsert operations
    - Schema evolution
    - Automatic optimization
    """

    def __init__(self, connection, storage_root: str):
        super().__init__(connection, storage_root)
        self._ensure_delta_extension()

    def _ensure_delta_extension(self):
        """Ensure Delta extension is installed and loaded."""
        try:
            self.connection.execute("LOAD delta")
        except:
            self.connection.execute("INSTALL delta")
            self.connection.execute("LOAD delta")

    def write_table(
        self,
        df,
        table_path: str,
        mode: str = 'overwrite',
        partition_by: List[str] = None,
        **kwargs
    ):
        """
        Write DataFrame to Delta table.

        Args:
            df: DataFrame to write
            table_path: Path to Delta table (e.g., 'equity/fact_prices')
            mode: Write mode - 'overwrite', 'append', 'merge'
            partition_by: Partition columns
        """
        full_path = f"{self.storage_root}/{table_path}"

        if mode == 'overwrite':
            self._write_overwrite(df, full_path, partition_by)
        elif mode == 'append':
            self._write_append(df, full_path, partition_by)
        elif mode == 'merge':
            merge_keys = kwargs.get('merge_keys', [])
            self._write_merge(df, full_path, merge_keys, partition_by)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _write_overwrite(self, df, path, partition_by):
        """Overwrite Delta table."""
        partition_clause = f"PARTITION_BY ({', '.join(partition_by)})" if partition_by else ""

        # Register DataFrame as temp view
        self.connection.register('temp_df', df)

        # Write to Delta
        self.connection.execute(f"""
            COPY (SELECT * FROM temp_df)
            TO '{path}'
            (FORMAT DELTA, OVERWRITE_OR_IGNORE {partition_clause})
        """)

    def _write_append(self, df, path, partition_by):
        """Append to Delta table."""
        partition_clause = f"PARTITION_BY ({', '.join(partition_by)})" if partition_by else ""

        self.connection.register('temp_df', df)

        self.connection.execute(f"""
            COPY (SELECT * FROM temp_df)
            TO '{path}'
            (FORMAT DELTA {partition_clause})
        """)

    def _write_merge(self, df, path, merge_keys, partition_by):
        """
        Merge data into Delta table (upsert).

        Uses Delta-RS library for MERGE operations.
        """
        from deltalake import DeltaTable, write_deltalake

        # Convert to PyArrow if needed
        if hasattr(df, 'to_arrow'):
            arrow_table = df.to_arrow()
        else:
            import pyarrow as pa
            arrow_table = pa.Table.from_pandas(df)

        # Build merge predicate
        merge_predicate = ' AND '.join([
            f"target.{key} = source.{key}" for key in merge_keys
        ])

        # Get or create Delta table
        try:
            dt = DeltaTable(path)

            # Perform merge
            dt.merge(
                source=arrow_table,
                predicate=merge_predicate,
                source_alias='source',
                target_alias='target'
            ).when_matched_update_all().when_not_matched_insert_all().execute()

        except Exception as e:
            # Table doesn't exist - create it
            write_deltalake(
                path,
                arrow_table,
                mode='overwrite',
                partition_by=partition_by
            )

    def read_table(self, table_path: str, version: int = None, timestamp: str = None):
        """
        Read Delta table with optional time travel.

        Args:
            table_path: Path to Delta table
            version: Optional version number
            timestamp: Optional timestamp (ISO format)

        Returns:
            DataFrame
        """
        full_path = f"{self.storage_root}/{table_path}"

        # Build time travel clause
        if version is not None:
            time_travel = f", version => {version}"
        elif timestamp is not None:
            time_travel = f", timestamp => '{timestamp}'"
        else:
            time_travel = ""

        # Query Delta table
        query = f"SELECT * FROM delta_scan('{full_path}'{time_travel})"
        return self.connection.execute(query).df()

    def get_table_history(self, table_path: str):
        """
        Get Delta table version history.

        Returns:
            DataFrame with version, timestamp, operation, etc.
        """
        full_path = f"{self.storage_root}/{table_path}"

        return self.connection.execute(f"""
            SELECT * FROM delta_scan_metadata('{full_path}')
        """).df()

    def optimize_table(self, table_path: str, zorder_by: List[str] = None):
        """
        Optimize Delta table (compact + z-order).

        Args:
            table_path: Path to Delta table
            zorder_by: Columns for Z-order optimization
        """
        from deltalake import DeltaTable

        full_path = f"{self.storage_root}/{table_path}"
        dt = DeltaTable(full_path)

        # Compact small files
        dt.optimize.compact()

        # Z-order if specified
        if zorder_by:
            dt.optimize.z_order(zorder_by)

    def vacuum_table(self, table_path: str, retention_hours: int = 168):
        """
        Remove old Delta files (7 days default).

        Args:
            table_path: Path to Delta table
            retention_hours: Hours of history to retain
        """
        from deltalake import DeltaTable

        full_path = f"{self.storage_root}/{table_path}"
        dt = DeltaTable(full_path)

        dt.vacuum(retention_hours=retention_hours)
```

### 2. Delta Backend Adapter

```
models/base/backend/
├── adapter.py              ← Base interface
├── duckdb_adapter.py       ← Update for Delta
├── spark_adapter.py        ← Update for Delta (future)
└── delta_adapter.py        ← NEW: Delta-specific operations
```

**duckdb_adapter.py updates:**
```python
class DuckDBAdapter(BackendAdapter):
    """DuckDB backend adapter with Delta Lake support."""

    def __init__(self, connection):
        super().__init__(connection)
        self.storage_format = 'delta'  # or 'parquet' for legacy
        self._ensure_delta_extension()

    def _ensure_delta_extension(self):
        """Load Delta extension."""
        try:
            self.connection.execute("LOAD delta")
        except:
            self.connection.execute("INSTALL delta")
            self.connection.execute("LOAD delta")

    def get_table_reference(self, table_name: str, version: int = None) -> str:
        """
        Get backend-specific table reference.

        For Delta tables, uses delta_scan() function.
        For Parquet, uses read_parquet() (legacy).
        """
        # Determine if this is a Delta table
        table_path = self._resolve_table_path(table_name)

        if self._is_delta_table(table_path):
            # Delta table
            if version is not None:
                return f"delta_scan('{table_path}', version => {version})"
            else:
                return f"delta_scan('{table_path}')"
        else:
            # Legacy Parquet
            return f"read_parquet('{table_path}/*.parquet')"

    def _is_delta_table(self, path: str) -> bool:
        """Check if path contains a Delta table."""
        from pathlib import Path
        return (Path(path) / '_delta_log').exists()

    def write_table(
        self,
        df,
        table_name: str,
        mode: str = 'overwrite',
        **kwargs
    ):
        """Write table using Delta format."""
        table_path = self._resolve_table_path(table_name)

        if self.storage_format == 'delta':
            # Use Delta storage
            partition_by = kwargs.get('partition_by', [])
            merge_keys = kwargs.get('merge_keys', [])

            if mode == 'merge' and merge_keys:
                self._delta_merge(df, table_path, merge_keys, partition_by)
            elif mode == 'append':
                self._delta_append(df, table_path, partition_by)
            else:  # overwrite
                self._delta_overwrite(df, table_path, partition_by)
        else:
            # Legacy Parquet write
            self._parquet_write(df, table_path, mode, **kwargs)
```

### 3. Model Config Updates

**configs/models/equity.yaml:**
```yaml
version: 1
model: equity
tags: [equities, trading, market_data, polygon]

# Storage configuration - USE DELTA!
storage:
  root: storage/silver/equity
  format: delta  # ← Changed from 'parquet'
  options:
    enable_time_travel: true
    retention_hours: 720  # 30 days of history
    optimize_on_write: true
    zorder_columns:
      fact_equity_prices: [ticker, trade_date]
      fact_equity_technicals: [ticker, trade_date]

# Schema definitions
schema:
  dimensions:
    dim_equity:
      path: dims/dim_equity
      description: "Equity instrument master"
      columns: {...}
      primary_key: [ticker]
      write_mode: merge  # ← NEW: Use merge instead of overwrite
      merge_keys: [ticker]  # ← Upsert on ticker
      tags: [dim, entity, equity, ticker]

  facts:
    fact_equity_prices:
      path: facts/fact_equity_prices
      description: "Daily OHLCV equity prices"
      columns: {...}
      partitions: [trade_date]
      write_mode: merge  # ← NEW: Merge by ticker+date
      merge_keys: [ticker, trade_date]
      tags: [fact, prices, timeseries, ohlcv]

# Bronze sources with Delta support
bronze_sources:
  dim_equity:
    source: ref_ticker
    source_format: delta  # ← Bronze can also be Delta
    transforms: [...]
```

### 4. Write Operations with Delta

**BaseModel write_tables() updates:**
```python
class BaseModel:
    def write_tables(
        self,
        tables: List[str] = None,
        mode: str = None,  # Can override per-table mode
        optimize_after: bool = True
    ):
        """
        Write model tables to storage using Delta format.

        Args:
            tables: List of table names (None = all)
            mode: Override write mode ('overwrite', 'append', 'merge')
            optimize_after: Run OPTIMIZE after writes
        """
        tables_to_write = tables or list(self._all_tables.keys())

        for table_name in tables_to_write:
            df = self._all_tables[table_name]
            table_config = self._get_table_config(table_name)

            # Determine write mode
            write_mode = mode or table_config.get('write_mode', 'overwrite')

            # Get merge keys if mode is merge
            merge_keys = table_config.get('merge_keys', [])

            # Get partition columns
            partitions = table_config.get('partitions', [])

            # Write using backend adapter
            self.backend.write_table(
                df,
                table_name,
                mode=write_mode,
                partition_by=partitions,
                merge_keys=merge_keys
            )

            print(f"✓ Wrote {table_name} (mode={write_mode})")

            # Optimize if enabled
            if optimize_after and write_mode in ['merge', 'append']:
                self._optimize_table(table_name)

    def _optimize_table(self, table_name: str):
        """Run OPTIMIZE on Delta table."""
        table_config = self._get_table_config(table_name)
        zorder_columns = table_config.get('zorder_columns', [])

        if hasattr(self.storage, 'optimize_table'):
            self.storage.optimize_table(table_name, zorder_by=zorder_columns)
            print(f"✓ Optimized {table_name}")
```

---

## 🔄 Migration Strategy

### Phase 1: Parallel Storage (1 week)

**Goal:** Run both Parquet and Delta in parallel

1. **Add Delta support** without breaking existing Parquet
2. **Config flag** to choose format:
   ```yaml
   storage:
     format: delta  # or 'parquet' for legacy
   ```
3. **Write to both** during transition:
   ```python
   # Write to Parquet (legacy)
   model.write_tables(storage_format='parquet')

   # Write to Delta (new)
   model.write_tables(storage_format='delta')
   ```

### Phase 2: Testing & Validation (3-5 days)

**Goal:** Verify Delta works correctly

1. **Data integrity tests:**
   ```python
   # Write test data to both formats
   # Compare row counts, checksums
   parquet_df = read_parquet('table.parquet')
   delta_df = delta_scan('table')
   assert parquet_df.equals(delta_df)
   ```

2. **Performance benchmarks:**
   - Read performance
   - Write performance (overwrite, append, merge)
   - Query performance
   - Storage size

3. **Time travel tests:**
   ```python
   # Write version 1
   write_delta(df_v1, 'prices')

   # Write version 2
   write_delta(df_v2, 'prices', mode='append')

   # Query version 1
   v1 = delta_scan('prices', version=0)
   assert len(v1) < len(delta_scan('prices'))  # v2 has more data
   ```

### Phase 3: Cutover (2-3 days)

**Goal:** Switch all models to Delta

1. **Update all model configs:**
   ```bash
   # Update all .yaml files
   find configs/models -name "*.yaml" -exec sed -i 's/format: parquet/format: delta/g' {} \;
   ```

2. **Migrate existing Parquet → Delta:**
   ```python
   # One-time migration script
   for model in ['equity', 'corporate', 'etf']:
       for table in model.get_tables():
           # Read Parquet
           df = read_parquet(f'{model}/{table}')

           # Write to Delta
           write_delta(df, f'{model}/{table}_delta')

           # Swap paths
           rename(f'{model}/{table}', f'{model}/{table}_parquet_backup')
           rename(f'{model}/{table}_delta', f'{model}/{table}')
   ```

3. **Update documentation**
4. **Remove Parquet fallback code**

### Phase 4: Optimization (Ongoing)

1. **Run OPTIMIZE on all tables:**
   ```python
   for table in all_delta_tables:
       optimize_table(table, zorder_by=['ticker', 'trade_date'])
   ```

2. **Set up VACUUM schedule:**
   ```python
   # Weekly vacuum to remove old files
   vacuum_table('equity/fact_prices', retention_hours=720)  # 30 days
   ```

3. **Monitor storage size and performance**

---

## 📋 Configuration Examples

### Bronze Layer - Delta

```yaml
# core/storage/bronze.yaml
bronze:
  root: storage/bronze
  format: delta  # Use Delta for raw ingestion
  options:
    enable_time_travel: true
    retention_hours: 2160  # 90 days for raw data
    optimize_on_write: false  # Don't optimize on every ingestion

  tables:
    prices_daily:
      path: prices_daily
      partitions: [trade_date]
      write_mode: append  # Always append new data
      zorder_columns: [ticker, trade_date]

    news:
      path: news
      partitions: [publish_date]
      write_mode: merge  # Upsert by article_id
      merge_keys: [article_id]
```

### Silver Layer - Delta

```yaml
# configs/models/equity.yaml
storage:
  root: storage/silver/equity
  format: delta
  options:
    enable_time_travel: true
    retention_hours: 720  # 30 days
    optimize_on_write: true  # Auto-optimize after writes
    auto_vacuum: true
    vacuum_schedule: weekly

schema:
  facts:
    fact_equity_prices:
      path: facts/fact_equity_prices
      partitions: [trade_date]
      write_mode: merge  # Upsert - handle late-arriving data
      merge_keys: [ticker, trade_date]
      zorder_columns: [ticker, trade_date]  # Optimize for queries
      optimize_after_rows: 1000000  # Optimize after 1M rows
```

---

## 🎯 Use Cases Enabled by Delta

### 1. Late-Arriving Data (Backfill)

**Problem:** Data for 2024-01-01 arrives 3 days late

**Parquet Solution:** Overwrite entire partition (slow, risky)

**Delta Solution:** Merge seamlessly

```python
# Late data arrives
late_data = pd.DataFrame({
    'ticker': ['AAPL'],
    'trade_date': ['2024-01-01'],
    'close': [187.50],  # Corrected price
    'volume': [50000000]
})

# Merge into existing data
model.write_table(
    late_data,
    'fact_equity_prices',
    mode='merge',
    merge_keys=['ticker', 'trade_date']
)

# Old value is updated atomically!
```

### 2. Time Travel (Audit / Debugging)

**Use case:** User reports "wrong data on 2024-11-01"

```python
# Query current data
current = delta_scan('fact_equity_prices',
                     filter="trade_date = '2024-11-01'")

# Query data as it was yesterday
yesterday = delta_scan('fact_equity_prices',
                       timestamp='2024-11-12 00:00:00',
                       filter="trade_date = '2024-11-01'")

# Compare
diff = current.merge(yesterday, on='ticker', suffixes=('_now', '_then'))
changed = diff[diff['close_now'] != diff['close_then']]
print(f"Found {len(changed)} changes")
```

### 3. Rollback Bad Data

**Use case:** Accidentally loaded corrupted data

```python
# Check table history
history = equity_model.storage.get_table_history('fact_equity_prices')
print(history[['version', 'timestamp', 'operation']])

# Version 10 was bad, rollback to version 9
from deltalake import DeltaTable

dt = DeltaTable('storage/silver/equity/facts/fact_equity_prices')
dt.restore(version=9)

print("✓ Rolled back to version 9")
```

### 4. Schema Evolution

**Use case:** Add new column without rewriting entire table

```python
# Add 'adjusted_close' column to existing table
from deltalake import DeltaTable

dt = DeltaTable('storage/silver/equity/facts/fact_equity_prices')

# Add column with default value
dt.alter.add_columns([
    {
        'name': 'adjusted_close',
        'type': 'double',
        'nullable': True
    }
])

# Existing rows get NULL for new column
# New writes include the column
# No full table rewrite needed!
```

### 5. Incremental Processing

**Use case:** Process only new data since last run

```python
# Get latest processed version
last_version = get_checkpoint('fact_equity_prices_processed')

# Read only new data
new_data = delta_scan('fact_equity_prices', version=last_version + 1)

# Process new data
processed = transform(new_data)

# Write results
write_delta(processed, 'fact_equity_technicals', mode='append')

# Update checkpoint
save_checkpoint('fact_equity_prices_processed', current_version)
```

---

## 📊 Performance Considerations

### Delta vs. Parquet

| Operation | Parquet | Delta Lake | Winner |
|-----------|---------|------------|--------|
| **Read (full scan)** | 1.0x (baseline) | 1.0x (same) | Tie |
| **Read (filtered)** | 1.0x | 0.8x (better stats) | Delta |
| **Write (overwrite)** | 1.0x | 1.2x (overhead) | Parquet |
| **Write (append)** | 1.0x | 1.0x | Tie |
| **Write (merge)** | N/A | 1.5x | Delta (only option) |
| **Schema evolution** | Full rewrite | Instant | Delta |
| **Time travel** | N/A | Instant | Delta (only option) |

### Storage Size

```
Parquet:  100 GB
Delta:    105 GB (5% overhead from transaction logs)

After VACUUM (removing old versions):
Delta:    100 GB (same as Parquet)
```

### Optimization Best Practices

1. **Z-Order frequently queried columns:**
   ```python
   optimize_table('fact_prices', zorder_by=['ticker', 'trade_date'])
   ```

2. **Vacuum regularly:**
   ```python
   # Keep 30 days of history, remove older
   vacuum_table('fact_prices', retention_hours=720)
   ```

3. **Compact small files:**
   ```python
   # After many small writes, compact
   optimize_table('fact_prices')  # Compact only
   ```

4. **Partition wisely:**
   - Too few partitions: Slow queries
   - Too many partitions: Overhead
   - Sweet spot: 100-10,000 partitions

---

## 🧪 Testing Plan

### Unit Tests

```python
# tests/unit/test_delta_storage.py

def test_delta_write_overwrite():
    """Test Delta overwrite mode."""
    storage = DeltaLakeStorage(conn, 'test_storage')

    # Write version 1
    df1 = pd.DataFrame({'ticker': ['AAPL'], 'price': [150]})
    storage.write_table(df1, 'test_table', mode='overwrite')

    # Read back
    result = storage.read_table('test_table')
    assert len(result) == 1
    assert result['price'].iloc[0] == 150

def test_delta_write_append():
    """Test Delta append mode."""
    # ... append test ...

def test_delta_write_merge():
    """Test Delta merge (upsert)."""
    storage = DeltaLakeStorage(conn, 'test_storage')

    # Initial data
    df1 = pd.DataFrame({'ticker': ['AAPL'], 'date': ['2024-01-01'], 'price': [150]})
    storage.write_table(df1, 'test_table', mode='overwrite')

    # Update AAPL, add MSFT
    df2 = pd.DataFrame({
        'ticker': ['AAPL', 'MSFT'],
        'date': ['2024-01-01', '2024-01-01'],
        'price': [155, 400]
    })
    storage.write_table(df2, 'test_table', mode='merge', merge_keys=['ticker', 'date'])

    # Verify: AAPL updated, MSFT added
    result = storage.read_table('test_table')
    assert len(result) == 2
    assert result[result['ticker'] == 'AAPL']['price'].iloc[0] == 155
    assert result[result['ticker'] == 'MSFT']['price'].iloc[0] == 400

def test_delta_time_travel():
    """Test time travel queries."""
    # ... time travel test ...

def test_delta_optimization():
    """Test OPTIMIZE and VACUUM."""
    # ... optimization test ...
```

### Integration Tests

```python
# tests/integration/test_delta_model_pipeline.py

def test_equity_model_delta_end_to_end():
    """Test equity model with Delta storage."""
    from models.implemented.equity.model import EquityModel

    # Create model with Delta storage
    equity = EquityModel(duckdb_conn, delta_storage, repo)

    # Build model (writes to Delta)
    equity.build()

    # Verify tables exist as Delta
    assert is_delta_table('storage/silver/equity/dims/dim_equity')
    assert is_delta_table('storage/silver/equity/facts/fact_equity_prices')

    # Query data
    prices = equity.get_table('fact_equity_prices')
    assert len(prices) > 0

    # Time travel
    version_0 = equity.storage.read_table('fact_equity_prices', version=0)
    assert len(version_0) >= 0
```

---

## 📝 Migration Checklist

### Pre-Migration

- [ ] Install dependencies: `pip install deltalake duckdb`
- [ ] Test Delta extension: `duckdb -c "INSTALL delta; LOAD delta"`
- [ ] Backup existing Parquet data
- [ ] Document current storage size

### Implementation

- [ ] Create `DeltaLakeStorage` class
- [ ] Update `DuckDBAdapter` for Delta support
- [ ] Add Delta config options to model YAMLs
- [ ] Update `BaseModel.write_tables()` for merge mode
- [ ] Add time travel methods to models

### Testing

- [ ] Unit tests for Delta storage operations
- [ ] Integration tests for model pipeline
- [ ] Performance benchmarks (read/write)
- [ ] Storage size comparison
- [ ] Time travel verification

### Migration

- [ ] Migrate Bronze layer (prices_daily, news, etc.)
- [ ] Migrate Equity model Silver layer
- [ ] Migrate Corporate model Silver layer
- [ ] Migrate ETF model Silver layer
- [ ] Verify data integrity after migration

### Optimization

- [ ] Run OPTIMIZE on all tables
- [ ] Set up Z-order for query columns
- [ ] Configure auto-VACUUM schedule
- [ ] Monitor performance

### Cleanup

- [ ] Archive old Parquet files
- [ ] Update documentation
- [ ] Remove Parquet compatibility code (optional)
- [ ] Celebrate! 🎉

---

## 🚀 Next Steps

1. **Review this proposal** - Discuss approach and timeline
2. **Install dependencies** - `pip install deltalake duckdb`
3. **Create Delta storage class** - Implement core functionality
4. **Test with sample data** - Verify operations work
5. **Update one model** - Start with equity as pilot
6. **Measure performance** - Benchmark vs. Parquet
7. **Full migration** - Roll out to all models

---

## 📚 References

- [DuckDB Delta Extension](https://duckdb.org/docs/extensions/delta.html)
- [Delta Lake Documentation](https://delta.io/)
- [Delta-RS Python API](https://delta-io.github.io/delta-rs/python/)
- [Delta Lake Best Practices](https://docs.delta.io/latest/best-practices.html)
- [DuckDB Performance Tuning](https://duckdb.org/docs/guides/performance/)

---

**Ready to implement?** Let's start with Phase 1! 🚀
