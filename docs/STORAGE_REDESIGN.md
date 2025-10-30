# Storage Layer Redesign for DuckDB Optimization

## Problem Analysis

### Current Issues (252 MB → 99 files)
1. **Over-partitioning**: Spark defaulting to 200 partitions for tiny data
2. **Tiny files**: Each file ~4 KB (metadata overhead > data!)
3. **Wrong partitioning**: `version=v1/snapshot_dt=2024-01-05` not used in queries
4. **No sorting**: Random data order prevents DuckDB optimizations
5. **Nested directories**: Unnecessary complexity

### Performance Impact
- **99 file opens** per query
- **Metadata overhead** >> actual data read
- **No partition pruning** (filters on trade_date/ticker, not snapshot_dt)
- **Result**: Sluggish queries on 252 MB data

## Optimal Design for DuckDB

### Principles
1. **Minimize files**: 1-5 large files better than 100 tiny files
2. **Sort by query columns**: Enable zone maps and predicate pushdown
3. **No partitioning**: For <1 GB data, single files are fastest
4. **Flat structure**: Simple paths for easy discovery

### New Structure

```
storage/silver/company/
├── dims/
│   ├── dim_company.parquet          # Single file, ~100 KB
│   └── dim_exchange.parquet         # Single file, ~10 KB
│
└── facts/
    ├── fact_prices.parquet          # Single file, ~125 MB
    │                                # Sorted by: trade_date, ticker
    │                                # Enables: Fast filtering, zone maps
    │
    └── prices_with_company.parquet  # Single file, ~125 MB
                                     # Sorted by: trade_date, ticker
```

### Benefits
- ✅ **4 files total** (vs 99 files)
- ✅ **No partitioning overhead**
- ✅ **Sorted data** for fast queries
- ✅ **Simple paths** matching model.table format
- ✅ **10-100x faster queries**

## Implementation

### 1. Updated ParquetLoader

```python
class ParquetLoaderOptimized:
    """Optimized Parquet writer for DuckDB analytics."""

    def _write(self, rel_path: str, df: Any, sort_by: list = None):
        """
        Write DataFrame to Parquet with DuckDB optimizations.

        Args:
            rel_path: Relative path (e.g., "company/facts/fact_prices")
            df: Spark DataFrame
            sort_by: Columns to sort by for query performance
        """
        out = self.root / "silver" / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)

        # Sort by query columns for zone maps
        if sort_by:
            df = df.sortWithinPartitions(*sort_by)

        # Coalesce to single file for small datasets
        # (use 2-5 files if >1 GB)
        num_files = 1 if df.count() < 10_000_000 else 2
        df = df.coalesce(num_files)

        # Write with snappy compression
        (df.write
         .mode("overwrite")
         .option("compression", "snappy")
         .parquet(str(out)))

        self._manifest(rel_path, out, df.count())

    def write_dim(self, name: str, df: Any):
        """Write dimension table (no sorting needed for small dims)."""
        rel = f"company/dims/{name}"
        self._write(rel, df.coalesce(1))  # Always single file for dims

    def write_fact(self, name: str, df: Any, sort_by: list):
        """Write fact table sorted by query columns."""
        rel = f"company/facts/{name}"
        self._write(rel, df, sort_by=sort_by)
```

### 2. Updated Silver Builder

```python
def build_and_write(self):
    """Build and write with optimizations."""

    # Build dimensions (no changes needed)
    dim_company = self.build_dim_company()
    dim_exchange = self.build_dim_exchange()

    # Build facts
    fact_prices = self.build_fact_prices()
    prices_with_company = self.build_prices_with_company(...)

    # Write with optimizations
    print("Writing dim_company...")
    self.loader.write_dim("dim_company", dim_company)

    print("Writing dim_exchange...")
    self.loader.write_dim("dim_exchange", dim_exchange)

    print("Writing fact_prices (sorted by trade_date, ticker)...")
    self.loader.write_fact(
        "fact_prices",
        fact_prices,
        sort_by=["trade_date", "ticker"]
    )

    print("Writing prices_with_company (sorted)...")
    self.loader.write_fact(
        "prices_with_company",
        prices_with_company,
        sort_by=["trade_date", "ticker"]
    )
```

### 3. Storage Configuration

Update `storage.json` to reflect new paths:

```json
{
  "connection": {
    "type": "spark",
    "comment": "Default for pipelines/builds"
  },
  "roots": {
    "bronze": "storage/bronze",
    "silver": "storage/silver"
  },
  "tables": {
    "dim_company": {
      "root": "silver",
      "rel": "company/dims/dim_company"
    },
    "dim_exchange": {
      "root": "silver",
      "rel": "company/dims/dim_exchange"
    },
    "fact_prices": {
      "root": "silver",
      "rel": "company/facts/fact_prices"
    },
    "prices_with_company": {
      "root": "silver",
      "rel": "company/facts/prices_with_company"
    }
  }
}
```

## Migration Plan

### Step 1: Clear Old Silver Layer
```bash
rm -rf storage/silver/company
rm -rf storage/silver/_meta
```

### Step 2: Install Dependencies
```bash
pip install pyspark
```

### Step 3: Rebuild with New Code
```bash
python scripts/build_silver_layer_optimized.py
```

### Step 4: Verify Structure
```bash
find storage/silver -name "*.parquet"
# Should show only 4 files

du -h storage/silver/company/facts/*.parquet
# Each file should be ~60-125 MB
```

### Step 5: Test Query Performance
```bash
python test_duckdb_pipeline.py
# Queries should be <100ms
```

## Expected Results

### Before
```
- Files: 99 tiny files (4 KB each)
- Structure: version=v1/snapshot_dt=2024-01-05/part-00000...part-00199
- Query time: 2-5 seconds (sluggish)
- File opens: 99 per query
```

### After
```
- Files: 4 large files (~60-125 MB each)
- Structure: company/dims/dim_company.parquet, company/facts/fact_prices.parquet
- Query time: 50-200ms (instant!)
- File opens: 1 per query
- Sorted: trade_date, ticker (zone maps enabled)
```

### Performance Gain
- **50-100x faster** queries
- **25x fewer** files
- **Better compression** (larger files)
- **DuckDB optimizations** (zone maps, predicate pushdown)

## Maintenance

### Re-running Pipeline
```bash
# Clear and rebuild (fresh start)
python scripts/rebuild_silver.py --clear

# Incremental update (append new dates)
python scripts/build_silver_layer_optimized.py --incremental
```

### Monitoring
```bash
# Check file sizes
du -h storage/silver/company/*/*.parquet

# Check row counts
python -c "
import duckdb
conn = duckdb.connect()
for table in ['fact_prices', 'prices_with_company']:
    count = conn.execute(f'''
        SELECT COUNT(*) FROM
        'storage/silver/company/facts/{table}.parquet'
    ''').fetchone()[0]
    print(f'{table}: {count:,} rows')
"
```

## Rollback Plan

If issues arise:
1. Keep backup: `cp -r storage/silver storage/silver.backup`
2. Revert code: `git checkout HEAD~1 src/model/loaders/parquet_loader.py`
3. Rebuild: `python scripts/build_silver_layer.py`
