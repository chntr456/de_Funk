# Model Reset and Rebuild Guide

Quick reference for resetting and rebuilding models in the de_Funk framework.

## Overview

Two scripts are provided for model data management:

1. **`reset_model.py`** - Clears existing model data (destructive)
2. **`rebuild_model.py`** - Rebuilds model from Bronze layer data

## Quick Start

### Reset a Model

```bash
# Dry run (see what would be deleted)
python scripts/reset_model.py --model equity --dry-run

# Reset with backup
python scripts/reset_model.py --model equity --backup

# Reset and reinitialize empty structure
python scripts/reset_model.py --model equity --backup --reinit

# Reset specific tables only
python scripts/reset_model.py --model equity --tables fact_equity_prices dim_equity
```

### Rebuild a Model

```bash
# Dry run (see what would be rebuilt)
python scripts/rebuild_model.py --model equity --dry-run

# Full rebuild with backup and validation
python scripts/rebuild_model.py --model equity

# Rebuild without backup (faster)
python scripts/rebuild_model.py --model equity --no-backup

# Rebuild specific tables
python scripts/rebuild_model.py --model equity --tables fact_equity_prices
```

## Script Details

### reset_model.py

**Purpose:** Delete model data and optionally reinitialize empty structure.

**Options:**
- `--model MODEL` - Model to reset (required)
- `--tables TABLE [TABLE ...]` - Specific tables (default: all)
- `--backup` - Create backup before reset
- `--reinit` - Create empty table structure after reset
- `--dry-run` - Show what would be done without changes
- `--force` - Skip confirmation prompt
- `--config-dir DIR` - Model config directory (default: configs/models)

**Examples:**

```bash
# See what would be deleted
python scripts/reset_model.py --model equity --dry-run

# Reset all tables with confirmation
python scripts/reset_model.py --model equity

# Reset with backup
python scripts/reset_model.py --model equity --backup

# Reset and create empty structure
python scripts/reset_model.py --model equity --reinit

# Reset specific table
python scripts/reset_model.py --model equity --tables fact_equity_prices

# Force reset without confirmation (dangerous!)
python scripts/reset_model.py --model equity --force
```

**Confirmation:**

By default, you must type `DELETE` to confirm:

```
⚠️  WARNING: DESTRUCTIVE OPERATION
==================================================
Model: equity
Storage: storage/silver/equity

The following 5 table(s) will be DELETED:
  - dim_equity (Delta) [EXISTS]
  - fact_equity_prices (Delta) [EXISTS]
  - fact_equity_news (Parquet) [EXISTS]
  - dim_equity_exchange (Parquet) [NOT FOUND]
  - fact_equity_splits (Delta) [EXISTS]

⚠️  ALL DATA IN THESE TABLES WILL BE PERMANENTLY DELETED!

Type 'DELETE' to confirm:
```

### rebuild_model.py

**Purpose:** Rebuild model from Bronze layer data.

**Options:**
- `--model MODEL` - Model to rebuild (required)
- `--tables TABLE [TABLE ...]` - Specific tables (default: all)
- `--bronze-path PATH` - Path to Bronze data (auto-detected if not specified)
- `--backup` - Create backup before rebuild (default: True)
- `--no-backup` - Skip backup
- `--validate` - Validate rebuilt data (default: True)
- `--no-validate` - Skip validation
- `--dry-run` - Show what would be done without changes
- `--config-dir DIR` - Model config directory (default: configs/models)

**Examples:**

```bash
# See what would be rebuilt
python scripts/rebuild_model.py --model equity --dry-run

# Full rebuild (backup + validation)
python scripts/rebuild_model.py --model equity

# Rebuild without backup (faster)
python scripts/rebuild_model.py --model equity --no-backup

# Rebuild without validation
python scripts/rebuild_model.py --model equity --no-validate

# Rebuild specific tables
python scripts/rebuild_model.py --model equity --tables fact_equity_prices

# Specify Bronze path explicitly
python scripts/rebuild_model.py --model equity --bronze-path storage/bronze/polygon
```

**Output Example:**

```
2025-11-13 10:30:00 - INFO - === Rebuilding model: equity ===
2025-11-13 10:30:00 - INFO - Tables to rebuild: fact_equity_prices, dim_equity
2025-11-13 10:30:00 - INFO - Step 1/3: Resetting Silver layer tables...
2025-11-13 10:30:05 - INFO - Step 2/3: Rebuilding from Bronze layer...
2025-11-13 10:30:10 - INFO -   ✓ Rebuilt fact_equity_prices: 1,523,450 rows
2025-11-13 10:30:12 - INFO -   ✓ Rebuilt dim_equity: 8,234 rows
2025-11-13 10:30:12 - INFO - Step 3/3: Validating rebuilt data...
2025-11-13 10:30:13 - INFO -   ✓ fact_equity_prices validation passed
2025-11-13 10:30:13 - INFO -   ✓ dim_equity validation passed

======================================================================
REBUILD SUMMARY
======================================================================

Tables: 2
Success: 2
Failed: 0
Total rows: 1,531,684

Per-table results:
  ✓ fact_equity_prices: 1,523,450 rows [VALID]
  ✓ dim_equity: 8,234 rows [VALID]
======================================================================
```

## Common Workflows

### 1. Corrupted Data - Need Fresh Start

```bash
# Reset and rebuild from Bronze
python scripts/rebuild_model.py --model equity
```

This will:
1. Backup existing Silver data
2. Reset all tables
3. Rebuild from Bronze
4. Validate results

### 2. Testing Schema Changes

```bash
# Reset to empty state
python scripts/reset_model.py --model equity --reinit --backup

# Run your ETL process to test new schema
python scripts/etl/load_equity_prices.py
```

### 3. Clear Model for Development

```bash
# Quick reset without backup (development only!)
python scripts/reset_model.py --model equity --force
```

### 4. Selective Table Rebuild

```bash
# Rebuild just prices table
python scripts/rebuild_model.py --model equity --tables fact_equity_prices
```

### 5. Delta Migration Testing

```bash
# Reset model
python scripts/reset_model.py --model equity --backup --reinit

# Rebuild with Delta format
python scripts/rebuild_model.py --model equity

# Tables will use Delta if extension is enabled
```

## Safety Features

### Backups

Both scripts support automatic backups:

```bash
# Creates timestamped backup
storage/silver/equity_backup_20251113_103000/
├── fact_equity_prices/
│   ├── _delta_log/
│   └── *.parquet
└── dim_equity/
    └── *.parquet
```

### Dry Run

Always test with `--dry-run` first:

```bash
# See exactly what would happen
python scripts/reset_model.py --model equity --dry-run
python scripts/rebuild_model.py --model equity --dry-run
```

### Confirmation Prompts

`reset_model.py` requires typing `DELETE` to confirm destructive operations (unless `--force` is used).

### Validation

`rebuild_model.py` validates rebuilt data by default:
- Path exists
- Data files present
- Row count > 0
- Schema compliance (if specified)

## Format Support

Both scripts support:
- **Parquet** - Standard columnar format
- **Delta Lake** - ACID transactions, time travel

Format is auto-detected based on directory structure (`_delta_log` presence).

## Bronze Layer Requirements

For `rebuild_model.py` to work:

1. **Bronze data must exist** at expected path
2. **Bronze structure** should match one of these patterns:
   - `{bronze_path}/{table_name}/`
   - `{bronze_path}/{table_name_without_prefix}/`
   - Specified via `--bronze-path`

3. **Data format** should be Parquet or Delta

Example Bronze structure:

```
storage/bronze/polygon/
├── prices_daily/           # Bronze for fact_equity_prices
│   └── *.parquet
├── company/                # Bronze for dim_equity
│   └── *.parquet
└── news/                   # Bronze for fact_equity_news
    └── *.parquet
```

## Troubleshooting

### Error: "Bronze path does not exist"

Specify Bronze path explicitly:

```bash
python scripts/rebuild_model.py --model equity --bronze-path storage/bronze/polygon
```

### Error: "No Bronze data found for table"

Check Bronze directory structure matches expected patterns, or add custom mapping logic to `_find_bronze_data()`.

### Error: "DuckDB not available"

Install DuckDB:

```bash
pip install duckdb
```

### Reset confirmation not working

Make sure you type exactly `DELETE` (all caps).

Or use `--force` to skip:

```bash
python scripts/reset_model.py --model equity --force
```

### Validation fails after rebuild

Check logs for specific validation failures:
- Path issues
- Empty data
- Schema mismatches

Run with verbose logging:

```bash
python scripts/rebuild_model.py --model equity 2>&1 | tee rebuild.log
```

## Advanced Usage

### Custom Bronze Mapping

Edit `rebuild_model.py` → `_find_bronze_data()` to add custom path resolution:

```python
def _find_bronze_data(self, table_name: str) -> Optional[Path]:
    # Add custom mapping
    custom_map = {
        'fact_equity_prices': self.bronze_path / 'daily_prices',
        'dim_equity': self.bronze_path / 'ticker_master',
    }

    if table_name in custom_map:
        return custom_map[table_name]

    # Fall back to default logic...
```

### Custom Transformations

Edit `rebuild_model.py` → `_transform_to_silver()` to add model-specific transformations:

```python
def _transform_to_silver(self, table_name: str, bronze_df):
    # Apply business logic
    if table_name == 'fact_equity_prices':
        # Calculate derived columns
        bronze_df['daily_return'] = bronze_df['close'].pct_change()

        # Filter invalid data
        bronze_df = bronze_df[bronze_df['volume'] > 0]

    return bronze_df
```

### Parallel Rebuilds

Rebuild multiple models concurrently:

```bash
# Rebuild both models in parallel
python scripts/rebuild_model.py --model equity &
python scripts/rebuild_model.py --model corporate &
wait

echo "All rebuilds complete"
```

## Best Practices

1. **Always backup production data** before reset/rebuild
2. **Test with dry-run** first
3. **Validate** rebuilt data (enabled by default)
4. **Monitor disk space** - backups can be large
5. **Use Bronze layer** as source of truth
6. **Document custom transformations** in rebuild logic
7. **Test reset/rebuild** in development first
8. **Schedule regular rebuilds** for data integrity
9. **Keep Bronze data** - don't delete source data
10. **Version control** model configs and transformation logic

## See Also

- [Delta Lake Usage Guide](DELTA_LAKE_USAGE_GUIDE.md) - Delta format details
- [Delta Migration Script](../scripts/migrate_to_delta.py) - Parquet → Delta migration
- [Model Documentation](../configs/models/) - Model configurations

## Support

For issues:
1. Check logs in detail
2. Try with `--dry-run` first
3. Verify Bronze data exists and is accessible
4. Check disk space availability
5. Review model configuration YAML
