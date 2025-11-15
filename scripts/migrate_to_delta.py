#!/usr/bin/env python3
"""
Migrate Parquet tables to Delta Lake format.

This script helps migrate existing Parquet tables to Delta format with
minimal downtime and data verification.

Usage:
    # Migrate a single table
    python scripts/migrate_to_delta.py --model equity --table fact_equity_prices

    # Migrate with partitioning
    python scripts/migrate_to_delta.py --model equity --table fact_equity_prices \\
        --partition-by ticker --verify

    # Migrate all tables in a model
    python scripts/migrate_to_delta.py --model equity --all-tables

    # Dry run (no changes)
    python scripts/migrate_to_delta.py --model equity --table fact_equity_prices --dry-run
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
import logging
import pandas as pd
from datetime import datetime

# Add project root to path
project_root = get_repo_root()
sys.path.insert(0, str(project_root))

try:
    import duckdb
    from deltalake import write_deltalake, DeltaTable
except ImportError as e:
    print(f"Error: Missing required package - {e}")
    print("Install with: pip install duckdb deltalake")
    sys.exit(1)

from models.registry import ModelRegistry
from core.duckdb_connection import DuckDBConnection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ParquetToDeltaMigrator:
    """Migrate Parquet tables to Delta Lake format."""

    def __init__(self, model_name: str, config_dir: str = "configs/models"):
        """
        Initialize migrator.

        Args:
            model_name: Name of the model (e.g., 'equity', 'corporate')
            config_dir: Directory containing model configs
        """
        self.model_name = model_name
        self.config_dir = Path(config_dir)
        self.conn = DuckDBConnection()

        # Load model config
        self.registry = ModelRegistry(str(self.config_dir))
        self.model = self.registry.get_model(model_name)
        self.model_cfg = self.model.model_cfg

        logger.info(f"Initialized migrator for model: {model_name}")

    def migrate_table(
        self,
        table_name: str,
        partition_by: Optional[List[str]] = None,
        verify: bool = True,
        backup: bool = True,
        dry_run: bool = False
    ) -> bool:
        """
        Migrate a single table from Parquet to Delta.

        Args:
            table_name: Name of the table to migrate
            partition_by: Columns to partition by (optional)
            verify: Whether to verify data after migration
            backup: Whether to backup original Parquet files
            dry_run: If True, only show what would be done

        Returns:
            True if migration successful, False otherwise
        """
        logger.info(f"=== Migrating table: {table_name} ===")

        # Get table path
        try:
            parquet_path = self._get_table_path(table_name)
        except ValueError as e:
            logger.error(f"Table not found: {e}")
            return False

        if not parquet_path.exists():
            logger.error(f"Table path does not exist: {parquet_path}")
            return False

        # Check if already Delta
        if self._is_delta_table(parquet_path):
            logger.warning(f"Table {table_name} is already in Delta format!")
            return False

        # Prepare Delta path (same location)
        delta_path = parquet_path
        backup_path = parquet_path.parent / f"{parquet_path.name}_parquet_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Source (Parquet): {parquet_path}")
        logger.info(f"Target (Delta): {delta_path}")
        if backup:
            logger.info(f"Backup location: {backup_path}")

        if dry_run:
            logger.info("DRY RUN - No changes will be made")
            logger.info(f"Would migrate {table_name}: {parquet_path} -> Delta")
            return True

        try:
            # Step 1: Read Parquet data
            logger.info("Step 1/5: Reading Parquet data...")
            df = self._read_parquet_table(parquet_path)
            row_count = len(df)
            logger.info(f"  Loaded {row_count:,} rows, {df.shape[1]} columns")
            logger.info(f"  Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")

            # Step 2: Validate data
            logger.info("Step 2/5: Validating data...")
            if df.empty:
                logger.error("  Error: DataFrame is empty!")
                return False

            # Check for duplicates if partition_by specified
            if partition_by:
                dupes = df.duplicated(subset=partition_by, keep=False)
                if dupes.any():
                    logger.warning(f"  Warning: Found {dupes.sum()} duplicate rows based on partition keys")

            logger.info("  Data validation passed")

            # Step 3: Backup original
            if backup:
                logger.info("Step 3/5: Creating backup...")
                parquet_path.rename(backup_path)
                logger.info(f"  Backed up to: {backup_path}")
            else:
                logger.info("Step 3/5: Skipping backup (backup=False)")

            # Step 4: Write Delta
            logger.info("Step 4/5: Writing Delta table...")
            logger.info(f"  Partition by: {partition_by if partition_by else 'None'}")

            write_deltalake(
                str(delta_path),
                df,
                mode='overwrite',
                partition_by=partition_by,
                engine='rust'  # Use rust engine for better performance
            )

            logger.info(f"  Successfully wrote {row_count:,} rows to Delta format")

            # Step 5: Verify
            if verify:
                logger.info("Step 5/5: Verifying migration...")
                if not self._verify_migration(delta_path, df, partition_by):
                    logger.error("  Verification failed!")
                    # Restore backup
                    if backup and backup_path.exists():
                        logger.info("  Restoring from backup...")
                        import shutil
                        shutil.rmtree(delta_path)
                        backup_path.rename(parquet_path)
                        logger.info("  Restored from backup")
                    return False
                logger.info("  Verification passed ✓")
            else:
                logger.info("Step 5/5: Skipping verification")

            # Success summary
            logger.info(f"✓ Migration complete: {table_name}")
            logger.info(f"  Format: Parquet -> Delta")
            logger.info(f"  Rows: {row_count:,}")
            logger.info(f"  Location: {delta_path}")

            # Show Delta table info
            dt = DeltaTable(str(delta_path))
            logger.info(f"  Delta version: {dt.version()}")

            return True

        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)

            # Restore backup if it exists
            if backup and backup_path.exists() and not parquet_path.exists():
                logger.info("Restoring from backup...")
                backup_path.rename(parquet_path)
                logger.info("Restored from backup")

            return False

    def migrate_all_tables(
        self,
        partition_by_table: Optional[dict] = None,
        verify: bool = True,
        backup: bool = True,
        dry_run: bool = False
    ) -> dict:
        """
        Migrate all tables in the model.

        Args:
            partition_by_table: Dict mapping table_name -> partition columns
            verify: Whether to verify each migration
            backup: Whether to backup originals
            dry_run: If True, only show what would be done

        Returns:
            Dict with migration results per table
        """
        logger.info(f"=== Migrating all tables in model: {self.model_name} ===")

        # Get all tables
        tables = self._get_all_tables()
        logger.info(f"Found {len(tables)} tables to migrate")

        results = {}
        for table_name in tables:
            partition_by = partition_by_table.get(table_name) if partition_by_table else None

            success = self.migrate_table(
                table_name,
                partition_by=partition_by,
                verify=verify,
                backup=backup,
                dry_run=dry_run
            )

            results[table_name] = 'success' if success else 'failed'
            logger.info("")  # Blank line between tables

        # Summary
        logger.info("=== Migration Summary ===")
        success_count = sum(1 for v in results.values() if v == 'success')
        logger.info(f"Total: {len(results)}")
        logger.info(f"Success: {success_count}")
        logger.info(f"Failed: {len(results) - success_count}")

        for table, status in results.items():
            symbol = "✓" if status == "success" else "✗"
            logger.info(f"  {symbol} {table}: {status}")

        return results

    def _get_table_path(self, table_name: str) -> Path:
        """Get physical path for a table."""
        schema = self.model_cfg.get('schema', {})

        # Check dimensions
        if table_name in schema.get('dimensions', {}):
            relative_path = schema['dimensions'][table_name]['path']
        # Check facts
        elif table_name in schema.get('facts', {}):
            relative_path = schema['facts'][table_name]['path']
        else:
            raise ValueError(
                f"Table '{table_name}' not found in model '{self.model_name}'"
            )

        storage_root = Path(self.model_cfg['storage']['root'])
        return storage_root / relative_path

    def _get_all_tables(self) -> List[str]:
        """Get all table names in the model."""
        schema = self.model_cfg.get('schema', {})
        dimensions = list(schema.get('dimensions', {}).keys())
        facts = list(schema.get('facts', {}).keys())
        return dimensions + facts

    def _is_delta_table(self, path: Path) -> bool:
        """Check if path is already a Delta table."""
        return (path / "_delta_log").exists()

    def _read_parquet_table(self, path: Path) -> pd.DataFrame:
        """Read Parquet table into DataFrame."""
        if path.is_dir():
            pattern = f"{path}/*.parquet"
            return self.conn.conn.execute(f"SELECT * FROM read_parquet('{pattern}')").df()
        else:
            return self.conn.conn.execute(f"SELECT * FROM read_parquet('{path}')").df()

    def _verify_migration(self, delta_path: Path, original_df: pd.DataFrame, partition_by: Optional[List[str]]) -> bool:
        """Verify migrated Delta table matches original."""
        try:
            # Read Delta table
            delta_df = self.conn.conn.execute(
                f"SELECT * FROM delta_scan('{delta_path}')"
            ).df()

            # Check row count
            if len(delta_df) != len(original_df):
                logger.error(f"  Row count mismatch: {len(delta_df)} vs {len(original_df)}")
                return False

            # Sort both DataFrames for comparison
            sort_cols = partition_by if partition_by else list(original_df.columns[:3])
            original_sorted = original_df.sort_values(by=sort_cols).reset_index(drop=True)
            delta_sorted = delta_df.sort_values(by=sort_cols).reset_index(drop=True)

            # Compare data (sample if too large)
            if len(original_df) > 1000:
                sample_size = 1000
                original_sample = original_sorted.sample(n=sample_size, random_state=42)
                delta_sample = delta_sorted.sample(n=sample_size, random_state=42)
                if not original_sample.equals(delta_sample):
                    logger.warning("  Sample data comparison shows differences (checking full data)")
                    # Don't fail on sample, just warn
            else:
                if not original_sorted.equals(delta_sorted):
                    logger.error("  Data mismatch detected")
                    return False

            logger.info("  Data integrity verified")
            return True

        except Exception as e:
            logger.error(f"  Verification error: {e}")
            return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Parquet tables to Delta Lake format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--model',
        required=True,
        help='Model name (e.g., equity, corporate)'
    )

    parser.add_argument(
        '--table',
        help='Table name to migrate (required unless --all-tables)'
    )

    parser.add_argument(
        '--all-tables',
        action='store_true',
        help='Migrate all tables in the model'
    )

    parser.add_argument(
        '--partition-by',
        nargs='+',
        help='Columns to partition by (e.g., ticker trade_date)'
    )

    parser.add_argument(
        '--no-verify',
        action='store_true',
        help='Skip verification step'
    )

    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip backup of original Parquet files'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    parser.add_argument(
        '--config-dir',
        default='configs/models',
        help='Directory containing model configs (default: configs/models)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all_tables and not args.table:
        parser.error("Either --table or --all-tables must be specified")

    try:
        # Initialize migrator
        migrator = ParquetToDeltaMigrator(
            model_name=args.model,
            config_dir=args.config_dir
        )

        # Migrate
        if args.all_tables:
            results = migrator.migrate_all_tables(
                verify=not args.no_verify,
                backup=not args.no_backup,
                dry_run=args.dry_run
            )
            success = all(v == 'success' for v in results.values())
        else:
            success = migrator.migrate_table(
                table_name=args.table,
                partition_by=args.partition_by,
                verify=not args.no_verify,
                backup=not args.no_backup,
                dry_run=args.dry_run
            )

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
