# Delta Lake Usage Guide

This guide shows how to use Delta Lake storage with DuckDB in the de_Funk framework.

## Overview

Delta Lake provides:
- **ACID transactions** - Atomic, consistent, isolated, durable operations
- **Time travel** - Query historical versions of data
- **Schema evolution** - Modify schema without breaking existing queries
- **Merge/upsert operations** - Efficient updates to large tables
- **Audit history** - Track all changes to tables

## Installation

```bash
# Install DuckDB (if not already installed)
pip install duckdb

# Install Delta Lake library
pip install deltalake
```

## Configuration

### Model Configuration

Delta tables are automatically detected based on directory structure (presence of `_delta_log` directory). No configuration changes are required in YAML files - simply store your data in Delta format and the framework will use it.

However, you can optionally specify the storage format explicitly:

```yaml
# configs/models/equity.yaml
model: equity
storage:
  root: storage/silver/equity
  format: delta  # Optional - auto-detected if _delta_log exists

schema:
  facts:
    fact_equity_prices:
      path: fact_equity_prices  # Will use Delta if _delta_log exists
      columns:
        ticker: string
        trade_date: date
        close: double
        volume: long
```

### Bronze Layer Example

```yaml
# configs/bronze/prices.yaml
source: polygon_api
destination:
  format: delta  # Store in Delta format
  path: storage/bronze/prices_daily
  mode: merge  # Use merge mode for upserts
  merge_keys: [ticker, trade_date]
  partition_by: [ticker]
```

## Usage Examples

### 1. Reading Delta Tables

Delta tables are read automatically - no code changes needed:

```python
from models.implemented.equity.model import EquityModel
from core.duckdb_connection import DuckDBConnection

# Initialize connection with Delta support (enabled by default)
conn = DuckDBConnection()

# Initialize model
equity = EquityModel(connection=conn, storage=storage, repo=repo)

# Read data normally - Delta format auto-detected
df = equity.get_table('fact_equity_prices', filters={'ticker': ['AAPL', 'GOOGL']})
```

### 2. Time Travel Queries

Query historical versions of data:

```python
# Read specific version
df = conn.read_table(
    'storage/silver/equity/fact_equity_prices',
    format='delta',
    version=5  # Version 5 of the table
)

# Read at specific timestamp
df = conn.read_table(
    'storage/silver/equity/fact_equity_prices',
    format='delta',
    timestamp='2024-01-15 10:00:00'
)

# View version history
history = conn.get_delta_table_history('storage/silver/equity/fact_equity_prices')
print(history[['version', 'timestamp', 'operation', 'operationMetrics']])
```

### 3. Writing Delta Tables

#### Overwrite Mode

```python
import pandas as pd

# Create sample data
df = pd.DataFrame({
    'ticker': ['AAPL', 'GOOGL', 'MSFT'],
    'trade_date': ['2024-01-15', '2024-01-15', '2024-01-15'],
    'close': [185.50, 150.20, 420.30],
    'volume': [50000000, 25000000, 30000000]
})

# Write to Delta (overwrites existing data)
conn.write_delta_table(
    df,
    'storage/silver/equity/fact_equity_prices',
    mode='overwrite',
    partition_by=['ticker']  # Optional partitioning
)
```

#### Append Mode

```python
# New data for next day
new_df = pd.DataFrame({
    'ticker': ['AAPL', 'GOOGL', 'MSFT'],
    'trade_date': ['2024-01-16', '2024-01-16', '2024-01-16'],
    'close': [186.20, 151.50, 422.10],
    'volume': [48000000, 24000000, 28000000]
})

# Append to Delta table
conn.write_delta_table(
    new_df,
    'storage/silver/equity/fact_equity_prices',
    mode='append'
)
```

#### Merge Mode (Upsert)

```python
# Updated data (some dates overlap with existing)
updated_df = pd.DataFrame({
    'ticker': ['AAPL', 'AAPL', 'TSLA'],
    'trade_date': ['2024-01-15', '2024-01-17', '2024-01-17'],
    'close': [185.75, 187.50, 215.30],  # AAPL 2024-01-15 updated
    'volume': [51000000, 49000000, 35000000]
})

# Merge into Delta table (update existing, insert new)
conn.write_delta_table(
    updated_df,
    'storage/silver/equity/fact_equity_prices',
    mode='merge',
    merge_keys=['ticker', 'trade_date']  # Keys to match on
)
```

### 4. Optimization

#### Compaction

Compact small files for better query performance:

```python
# Basic compaction
conn.optimize_delta_table('storage/silver/equity/fact_equity_prices')

# With z-ordering (data clustering for better filtering)
conn.optimize_delta_table(
    'storage/silver/equity/fact_equity_prices',
    zorder_by=['ticker', 'trade_date']
)
```

#### Vacuum

Remove old files no longer needed (frees disk space but disables time travel to removed versions):

```python
# Vacuum files older than 7 days (default)
conn.vacuum_delta_table('storage/silver/equity/fact_equity_prices')

# Custom retention (24 hours)
conn.vacuum_delta_table(
    'storage/silver/equity/fact_equity_prices',
    retention_hours=24
)
```

**Warning:** Vacuuming permanently deletes old data files. You won't be able to time travel to versions older than the retention period!

## Migration from Parquet to Delta

### Option 1: In-Place Migration (Recommended)

Migrate existing Parquet data to Delta format:

```python
from pathlib import Path
from deltalake import write_deltalake
import duckdb

# Paths
parquet_path = 'storage/silver/equity/fact_equity_prices'
delta_path = 'storage/silver/equity/fact_equity_prices_delta'

# Read existing Parquet data
conn = duckdb.connect()
df = conn.execute(f"SELECT * FROM read_parquet('{parquet_path}/*.parquet')").df()

# Write to Delta
write_deltalake(
    delta_path,
    df,
    mode='overwrite',
    partition_by=['ticker']  # Optional
)

# Verify
print(f"Migrated {len(df)} rows to Delta format")

# After verification, rename directories:
# mv storage/silver/equity/fact_equity_prices storage/silver/equity/fact_equity_prices_parquet_backup
# mv storage/silver/equity/fact_equity_prices_delta storage/silver/equity/fact_equity_prices
```

### Option 2: Parallel Storage

Run both formats in parallel during transition:

```yaml
# configs/models/equity.yaml
schema:
  facts:
    fact_equity_prices:
      path: fact_equity_prices  # Parquet (legacy)
    fact_equity_prices_delta:
      path: fact_equity_prices_delta  # Delta (new)
```

Then gradually migrate queries to use the Delta version.

### Option 3: Migration Script

Use the provided migration utility:

```bash
python scripts/migrate_to_delta.py \
    --model equity \
    --table fact_equity_prices \
    --partition-by ticker \
    --verify
```

## Use Cases

### 1. Late-Arriving Data

Handle data that arrives after initial load:

```python
# Initial load (Jan 1-15)
initial_df = load_data('2024-01-01', '2024-01-15')
conn.write_delta_table(initial_df, table_path, mode='overwrite')

# Late arrival: corrected data for Jan 5
correction_df = load_corrected_data('2024-01-05')
conn.write_delta_table(
    correction_df,
    table_path,
    mode='merge',
    merge_keys=['ticker', 'trade_date']  # Updates Jan 5 data
)
```

### 2. Incremental Updates

Efficiently update large tables:

```python
# Daily update process
new_data = fetch_latest_prices()

# Merge new data (updates existing, inserts new)
conn.write_delta_table(
    new_data,
    'storage/silver/equity/fact_equity_prices',
    mode='merge',
    merge_keys=['ticker', 'trade_date']
)

# Compact weekly
if datetime.now().weekday() == 6:  # Sunday
    conn.optimize_delta_table('storage/silver/equity/fact_equity_prices')
```

### 3. Audit Trail

Track all changes to data:

```python
# View complete history
history = conn.get_delta_table_history('storage/silver/equity/fact_equity_prices')

# Find when specific data was added/changed
history[history['operation'] == 'MERGE'].sort_values('timestamp', ascending=False)

# Rollback to previous version if needed
old_df = conn.read_table(
    'storage/silver/equity/fact_equity_prices',
    format='delta',
    version=history.iloc[-2]['version']  # Previous version
)
```

### 4. Schema Evolution

Add columns without breaking existing queries:

```python
# Original schema: ticker, trade_date, close, volume

# Add new column
df_with_new_col = df.assign(market_cap=lambda x: x['close'] * x['volume'])

# Write with schema evolution
conn.write_delta_table(
    df_with_new_col,
    table_path,
    mode='append',
    schema_mode='merge'  # Merge schemas
)

# Old queries still work!
old_query_df = conn.read_table(table_path, format='delta')[['ticker', 'close']]
```

## Performance Tips

1. **Partitioning**: Partition by high-cardinality columns you frequently filter on
   ```python
   partition_by=['ticker']  # Good for ticker-based queries
   ```

2. **Z-Ordering**: Cluster data by commonly filtered columns
   ```python
   conn.optimize_delta_table(path, zorder_by=['ticker', 'trade_date'])
   ```

3. **Compaction**: Run optimize regularly to merge small files
   ```python
   # Weekly compaction
   conn.optimize_delta_table(path)
   ```

4. **Vacuuming**: Clean up old versions you don't need
   ```python
   # Keep 7 days for time travel, delete older
   conn.vacuum_delta_table(path, retention_hours=168)
   ```

5. **Predicate Pushdown**: Filter at read time when possible
   ```python
   # DuckDB pushes filters into Delta scan
   query = "SELECT * FROM delta_scan('path') WHERE ticker = 'AAPL'"
   ```

## Troubleshooting

### Delta Extension Not Found

```python
# Error: delta extension not found
# Solution: Install and load manually
conn.execute("INSTALL delta")
conn.execute("LOAD delta")
```

### Permission Issues

```python
# Error: Permission denied on _delta_log
# Solution: Check directory permissions
chmod -R 755 storage/silver/equity/fact_equity_prices
```

### Corrupt Delta Log

```python
# Error: Corrupt transaction log
# Solution: Repair using delta-rs
from deltalake import DeltaTable
dt = DeltaTable(path)
dt.repair()
```

### Performance Issues

```python
# Slow queries on large tables
# Solution: Check file count and compact
import os
file_count = len([f for f in os.listdir(path) if f.endswith('.parquet')])
print(f"File count: {file_count}")

if file_count > 100:
    conn.optimize_delta_table(path)
```

## References

- [Delta Lake Protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md)
- [DuckDB Delta Extension](https://duckdb.org/docs/extensions/delta.html)
- [delta-rs Python Package](https://delta-io.github.io/delta-rs/)
