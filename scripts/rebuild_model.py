#!/usr/bin/env python3
"""
Rebuild model from Bronze layer data.

This script performs a complete model rebuild:
1. Resets Silver layer tables
2. Rebuilds from Bronze layer data
3. Validates data integrity

Usage:
    # Rebuild entire model from Bronze
    python -m scripts.rebuild_model --model equity

    # Rebuild specific tables
    python -m scripts.rebuild_model --model equity --tables fact_equity_prices

    # Rebuild with backup and validation
    python -m scripts.rebuild_model --model equity --backup --validate

    # Dry run (show what would be done)
    python -m scripts.rebuild_model --model equity --dry-run

    # Use custom Bronze path
    python -m scripts.rebuild_model --model equity --bronze-path storage/bronze/polygon
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Dict
import logging
from datetime import datetime


from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

try:
    from core.duckdb_connection import DuckDBConnection
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

from models.registry import ModelRegistry
from scripts.reset_model import ModelResetter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelRebuilder:
    """Rebuild model from Bronze layer data."""

    def __init__(
        self,
        model_name: str,
        config_dir: str = "configs/models",
        bronze_path: Optional[str] = None
    ):
        """
        Initialize model rebuilder.

        Args:
            model_name: Name of the model
            config_dir: Directory containing model configs
            bronze_path: Path to Bronze layer (optional, inferred from model if not provided)
        """
        self.model_name = model_name
        self.config_dir = Path(config_dir)
        self.bronze_path = Path(bronze_path) if bronze_path else None

        # Load model
        self.registry = ModelRegistry(str(self.config_dir))
        # Get raw config dict (not ModelConfig object)
        self.model_cfg = self.registry.get_model_config(model_name)

        # Load storage configuration to get bronze root and table mappings
        from config.loader import ConfigLoader
        config_loader = ConfigLoader(repo_root=repo_root)
        self.storage_config = config_loader._load_json_config("storage.json")
        self.bronze_root = Path(self.storage_config.get('roots', {}).get('bronze', 'storage/bronze'))

        # Initialize connection if available
        self.conn = None
        if DUCKDB_AVAILABLE:
            self.conn = DuckDBConnection()

        logger.info(f"Initialized rebuilder for model: {model_name}")
        logger.info(f"Bronze root: {repo_root / self.bronze_root}")

    def rebuild_model(
        self,
        tables: Optional[List[str]] = None,
        backup: bool = True,
        validate: bool = True,
        dry_run: bool = False
    ) -> bool:
        """
        Rebuild model from Bronze data.

        Args:
            tables: Specific tables to rebuild (None = all tables)
            backup: Whether to backup existing data before rebuild
            validate: Whether to validate rebuilt data
            dry_run: If True, only show what would be done

        Returns:
            True if rebuild successful, False otherwise
        """
        logger.info(f"=== Rebuilding model: {self.model_name} ===")

        # Get tables to rebuild
        if tables:
            tables_to_rebuild = tables
        else:
            tables_to_rebuild = self._get_all_tables()

        logger.info(f"Tables to rebuild: {', '.join(tables_to_rebuild)}")

        if dry_run:
            logger.info("DRY RUN - No changes will be made")
            return self._dry_run_report(tables_to_rebuild, backup, validate)

        try:
            # Step 1: Reset existing Silver tables
            logger.info("Step 1/4: Resetting Silver layer tables...")
            resetter = ModelResetter(self.model_name, str(self.config_dir))

            if not resetter.reset_model(
                tables=tables_to_rebuild,
                backup=backup,
                reinit=True,  # Create empty structure
                dry_run=False,
                force=False
            ):
                logger.error("Failed to reset Silver layer")
                return False

            # Step 2: Rebuild from Bronze
            logger.info("Step 2/4: Rebuilding from Bronze layer...")
            rebuild_results = {}

            for table_name in tables_to_rebuild:
                try:
                    result = self._rebuild_table(table_name)
                    rebuild_results[table_name] = result
                    if result['success']:
                        logger.info(f"  ✓ Rebuilt {table_name}: {result['rows']} rows")
                    else:
                        logger.error(f"  ✗ Failed to rebuild {table_name}: {result['error']}")
                except Exception as e:
                    logger.error(f"  ✗ Error rebuilding {table_name}: {e}")
                    rebuild_results[table_name] = {'success': False, 'error': str(e)}

            # Step 3: Validate if requested
            if validate:
                logger.info("Step 3/4: Validating rebuilt data...")
                validation_results = self._validate_rebuild(tables_to_rebuild, rebuild_results)
            else:
                logger.info("Step 3/4: Skipping validation (not requested)")
                validation_results = {}

            # Step 4: Build weighted aggregate views (for equity model only)
            if self.model_name == 'equity':
                logger.info("Step 4/4: Building weighted aggregate views...")
                self._build_weighted_views()
            else:
                logger.info("Step 4/4: No post-build steps for this model")

            # Summary
            self._print_summary(tables_to_rebuild, rebuild_results, validation_results)

            # Check if all successful
            all_success = all(r.get('success', False) for r in rebuild_results.values())
            return all_success

        except Exception as e:
            logger.error(f"Rebuild failed: {e}", exc_info=True)
            return False

    def _get_all_tables(self) -> List[str]:
        """Get all table names in the model."""
        schema = self.model_cfg.get('schema', {})
        dimensions = list(schema.get('dimensions', {}).keys())
        facts = list(schema.get('facts', {}).keys())
        return dimensions + facts

    def _rebuild_table(self, table_name: str) -> Dict:
        """
        Rebuild a single table from Bronze data.

        Args:
            table_name: Table name to rebuild

        Returns:
            Dict with rebuild results
        """
        # This is a placeholder - actual implementation would depend on:
        # 1. Bronze data structure
        # 2. Transformation logic
        # 3. Model-specific requirements

        logger.info(f"    Rebuilding {table_name}...")

        # Map Silver table name to Bronze source table using heuristics
        bronze_source_candidates = self._get_bronze_source_candidates(table_name)

        bronze_table_path = None
        bronze_source_name = None

        for candidate in bronze_source_candidates:
            # Look up candidate in storage.json
            table_config = self.storage_config.get('tables', {}).get(candidate, {})

            if table_config and table_config.get('root') == 'bronze':
                # Found a bronze source
                bronze_rel_path = table_config.get('rel', candidate)
                candidate_path = repo_root / self.bronze_root / bronze_rel_path

                if candidate_path.exists():
                    bronze_table_path = candidate_path
                    bronze_source_name = candidate
                    logger.info(f"    Mapped {table_name} → Bronze source: {bronze_source_name}")
                    break

        if not bronze_table_path:
            # Check if this is a derived table (needs transformation from other Silver tables)
            if any(keyword in table_name for keyword in ['_with_', 'aggregated', 'enriched']):
                return {
                    'success': False,
                    'error': f'Table {table_name} is a derived view - requires transformation logic (not yet implemented)'
                }
            else:
                return {
                    'success': False,
                    'error': f'No Bronze source found for {table_name}. Tried: {", ".join(bronze_source_candidates)}'
                }

        # Read Bronze data
        try:
            if not DUCKDB_AVAILABLE:
                return {
                    'success': False,
                    'error': 'DuckDB not available for rebuild'
                }

            # Read Bronze data
            logger.info(f"    Reading Bronze data from {bronze_table_path}...")
            bronze_df = self.conn.read_table(str(bronze_table_path), format='parquet').df()

            # Apply transformations (placeholder - would be model-specific)
            silver_df = self._transform_to_silver(table_name, bronze_df)

            # Write to Silver
            silver_path = self._get_silver_path(table_name)
            logger.info(f"    Writing to Silver layer at {silver_path}...")

            # Determine format (Delta if extension available, else Parquet)
            if self.conn.delta_enabled:
                self.conn.write_delta_table(
                    silver_df,
                    str(silver_path),
                    mode='overwrite'
                )
                format_used = 'Delta'
            else:
                # Write as Parquet
                import pyarrow.parquet as pq
                import pyarrow as pa
                table = pa.Table.from_pandas(silver_df)
                pq.write_table(table, str(silver_path / 'data.parquet'))
                format_used = 'Parquet'

            return {
                'success': True,
                'rows': len(silver_df),
                'format': format_used,
                'bronze_path': str(bronze_table_path),
                'silver_path': str(silver_path)
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _get_bronze_source_candidates(self, table_name: str) -> List[str]:
        """
        Generate candidate Bronze source table names for a Silver table.

        Args:
            table_name: Silver table name (e.g., 'dim_equity', 'fact_equity_prices')

        Returns:
            List of candidate Bronze table names to try

        Examples:
            'dim_equity' → ['ref_equity', 'equity', 'ref_ticker']
            'fact_equity_prices' → ['prices_daily', 'equity_prices', 'prices']
            'dim_exchange' → ['exchanges', 'ref_exchange', 'exchange']
        """
        candidates = []

        # Common transformation patterns
        base_name = table_name

        # Remove prefixes
        for prefix in ['fact_', 'dim_', 'ref_']:
            if base_name.startswith(prefix):
                base_name = base_name[len(prefix):]
                break

        # Specific known mappings
        known_mappings = {
            'equity': ['ref_ticker', 'ref_equity', 'equity'],
            'exchange': ['exchanges', 'ref_exchange'],
            'equity_prices': ['prices_daily'],
            'equity_news': ['news'],
            'equity_technicals': ['prices_daily'],  # Derived from prices
        }

        if base_name in known_mappings:
            candidates.extend(known_mappings[base_name])

        # Generic patterns
        candidates.extend([
            f'ref_{base_name}',  # ref_equity
            f'{base_name}s',  # exchanges
            f'{base_name}_daily',  # prices_daily
            base_name,  # equity
        ])

        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                unique_candidates.append(candidate)

        return unique_candidates

    def _find_bronze_data(self, table_name: str) -> Optional[Path]:
        """
        Find Bronze data for a table (legacy method - kept for compatibility).

        Args:
            table_name: Table name

        Returns:
            Path to Bronze data if found, None otherwise
        """
        # Common Bronze naming patterns
        patterns = [
            table_name,  # exact match
            table_name.replace('fact_', ''),  # without fact_ prefix
            table_name.replace('dim_', ''),   # without dim_ prefix
            table_name.replace('_', '/'),     # with subdirectories
        ]

        for pattern in patterns:
            candidate = self.bronze_path / pattern
            if candidate.exists():
                return candidate

        # Try searching subdirectories
        for subdir in self.bronze_path.rglob('*'):
            if subdir.is_dir() and table_name in subdir.name:
                return subdir

        return None

    def _transform_to_silver(self, table_name: str, bronze_df):
        """
        Transform Bronze data to Silver format.

        Args:
            table_name: Table name
            bronze_df: Bronze DataFrame

        Returns:
            Transformed DataFrame

        Note: This is a placeholder - actual transformations would be model-specific
        """
        # Placeholder: just return Bronze data as-is
        # In reality, you'd apply:
        # - Schema mapping
        # - Data cleaning
        # - Type conversions
        # - Business logic
        # - Denormalization

        logger.info(f"    Applying transformations for {table_name}...")

        # Get target schema from model
        schema = self.model_cfg.get('schema', {})
        target_schema = None

        if table_name in schema.get('dimensions', {}):
            target_schema = schema['dimensions'][table_name].get('columns', {})
        elif table_name in schema.get('facts', {}):
            target_schema = schema['facts'][table_name].get('columns', {})

        if target_schema:
            # Filter to only columns in target schema
            available_cols = [col for col in target_schema.keys() if col in bronze_df.columns]
            bronze_df = bronze_df[available_cols]
            logger.info(f"    Filtered to {len(available_cols)} target columns")

        return bronze_df

    def _get_silver_path(self, table_name: str) -> Path:
        """Get Silver layer path for a table."""
        schema = self.model_cfg.get('schema', {})

        if table_name in schema.get('dimensions', {}):
            relative_path = schema['dimensions'][table_name]['path']
        elif table_name in schema.get('facts', {}):
            relative_path = schema['facts'][table_name]['path']
        else:
            raise ValueError(f"Table {table_name} not found in schema")

        storage_root = Path(self.model_cfg['storage']['root'])
        return storage_root / relative_path

    def _validate_rebuild(
        self,
        tables: List[str],
        rebuild_results: Dict
    ) -> Dict:
        """
        Validate rebuilt tables.

        Args:
            tables: Tables that were rebuilt
            rebuild_results: Results from rebuild

        Returns:
            Dict with validation results
        """
        validation_results = {}

        for table_name in tables:
            if not rebuild_results.get(table_name, {}).get('success'):
                validation_results[table_name] = {
                    'valid': False,
                    'reason': 'Rebuild failed'
                }
                continue

            try:
                # Basic validation checks
                silver_path = self._get_silver_path(table_name)

                checks = {
                    'path_exists': silver_path.exists(),
                    'has_data': self._check_has_data(silver_path),
                    'row_count': rebuild_results[table_name].get('rows', 0)
                }

                is_valid = all([
                    checks['path_exists'],
                    checks['has_data'],
                    checks['row_count'] > 0
                ])

                validation_results[table_name] = {
                    'valid': is_valid,
                    'checks': checks
                }

                if is_valid:
                    logger.info(f"  ✓ {table_name} validation passed")
                else:
                    logger.warning(f"  ✗ {table_name} validation failed: {checks}")

            except Exception as e:
                logger.error(f"  ✗ Error validating {table_name}: {e}")
                validation_results[table_name] = {
                    'valid': False,
                    'error': str(e)
                }

        return validation_results

    def _check_has_data(self, path: Path) -> bool:
        """Check if a path contains data files."""
        if not path.exists():
            return False

        # Check for Parquet files
        parquet_files = list(path.rglob('*.parquet'))
        if parquet_files:
            return True

        # Check for Delta table (_delta_log)
        if (path / "_delta_log").exists():
            return True

        return False

    def _print_summary(
        self,
        tables: List[str],
        rebuild_results: Dict,
        validation_results: Dict
    ):
        """Print rebuild summary."""
        logger.info("\n" + "=" * 70)
        logger.info("REBUILD SUMMARY")
        logger.info("=" * 70)

        success_count = sum(1 for r in rebuild_results.values() if r.get('success'))
        logger.info(f"\nTables: {len(tables)}")
        logger.info(f"Success: {success_count}")
        logger.info(f"Failed: {len(tables) - success_count}")

        total_rows = sum(r.get('rows', 0) for r in rebuild_results.values() if r.get('success'))
        logger.info(f"Total rows: {total_rows:,}")

        logger.info("\nPer-table results:")
        for table in tables:
            result = rebuild_results.get(table, {})
            status = "✓" if result.get('success') else "✗"
            rows = result.get('rows', 0)

            if validation_results:
                validation = validation_results.get(table, {})
                valid = "VALID" if validation.get('valid') else "INVALID"
                logger.info(f"  {status} {table}: {rows:,} rows [{valid}]")
            else:
                logger.info(f"  {status} {table}: {rows:,} rows")

        logger.info("=" * 70)

    def _dry_run_report(self, tables: List[str], backup: bool, validate: bool) -> bool:
        """Show what would be done in dry run."""
        print("\n" + "=" * 70)
        print("DRY RUN - No changes will be made")
        print("=" * 70)
        print(f"\nModel: {self.model_name}")
        print(f"Bronze path: {self.bronze_path or 'Not specified (will try to infer)'}")

        print(f"\nWould rebuild {len(tables)} table(s):")
        for table in tables:
            bronze_data = self._find_bronze_data(table) if self.bronze_path else None
            status = "FOUND" if bronze_data else "NOT FOUND"
            print(f"  - {table} [Bronze data: {status}]")

        print("\nActions that would be performed:")
        if backup:
            print("  1. ✓ Backup existing Silver data")
        else:
            print("  1. ✗ Skip backup (not requested)")

        print("  2. ✓ Reset Silver tables")
        print("  3. ✓ Rebuild from Bronze data")

        if validate:
            print("  4. ✓ Validate rebuilt data")
        else:
            print("  4. ✗ Skip validation (not requested)")

        print("\n" + "=" * 70)

        return True

    def _build_weighted_views(self):
        """Build weighted aggregate views for equity model (DuckDB only)."""
        try:
            from models.builders import WeightedAggregateBuilder

            # Get storage path
            storage_root = self.model_cfg.get('storage', {}).get('root', 'storage/silver/equity')
            storage_path = Path(storage_root)

            # Create builder
            builder = WeightedAggregateBuilder(
                connection=self.conn.conn,  # Unwrap DuckDBConnection to get raw DuckDB conn
                model_config=self.model_cfg,
                storage_path=storage_path
            )

            # Build all weighted aggregate views
            builder.build_all_weighted_aggregates(materialize=False)
            logger.info("  ✓ Weighted aggregate views created successfully")

        except Exception as e:
            logger.warning(f"  ⚠️  Could not build weighted aggregate views: {e}")
            logger.warning("  Weighted indices may not work in exhibits until views are created")
            # Don't fail the rebuild if this fails - it's an optional feature


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Rebuild model from Bronze layer data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--model',
        required=True,
        help='Model name (e.g., equity, corporate)'
    )

    parser.add_argument(
        '--tables',
        nargs='+',
        help='Specific tables to rebuild (default: all tables)'
    )

    parser.add_argument(
        '--bronze-path',
        help='Path to Bronze layer data'
    )

    parser.add_argument(
        '--backup',
        action='store_true',
        default=True,
        help='Create backup before rebuild (default: True)'
    )

    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip backup before rebuild'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        default=True,
        help='Validate rebuilt data (default: True)'
    )

    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip validation'
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

    # Handle backup/validate flags
    backup = args.backup and not args.no_backup
    validate = args.validate and not args.no_validate

    try:
        # Initialize rebuilder
        rebuilder = ModelRebuilder(
            model_name=args.model,
            config_dir=args.config_dir,
            bronze_path=args.bronze_path
        )

        # Rebuild model
        success = rebuilder.rebuild_model(
            tables=args.tables,
            backup=backup,
            validate=validate,
            dry_run=args.dry_run
        )

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
