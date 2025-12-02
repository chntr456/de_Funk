#!/usr/bin/env python3
"""
Diagnose silver layer tables and DuckDB views.

This script checks:
- Silver Parquet files exist for each model
- DuckDB views are created and queryable
- Shows sample data (top N rows) for each table
- Validates cross-model relationships

Usage:
    python -m scripts.diagnose_silver_data
    python -m scripts.diagnose_silver_data --top-n 5
    python -m scripts.diagnose_silver_data --models stocks company
"""

import argparse
import sys
from pathlib import Path
from collections import defaultdict

# Setup repo imports
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

import duckdb
from config import ConfigLoader
from config.logging import get_logger, setup_logging

logger = get_logger(__name__)


def print_header(text: str, char: str = "=") -> None:
    """Print a formatted header line."""
    line = char * 80
    print(f"\n{line}")
    print(text)
    print(line)


def print_subheader(text: str) -> None:
    """Print a formatted subheader."""
    print(f"\n{'-' * 80}")
    print(text)
    print(f"{'-' * 80}")


def main():
    setup_logging()

    parser = argparse.ArgumentParser(description='Diagnose silver layer data')
    parser.add_argument('--top-n', type=int, default=3,
                        help='Number of rows to show per table (default: 3)')
    parser.add_argument('--models', nargs='*',
                        help='Specific models to check (default: all)')
    args = parser.parse_args()

    print_header("SILVER LAYER DIAGNOSTICS")
    logger.info("Starting silver layer diagnostics")

    # Load config
    loader = ConfigLoader()
    config = loader.load()

    silver_root = config.repo_root / "storage" / "silver"
    duckdb_path = config.connection.duckdb.database_path

    if not silver_root.exists():
        logger.error(f"Silver directory not found: {silver_root}")
        print(f"\n❌ Silver directory not found: {silver_root}")
        print("\nYou need to build models first:")
        print("  python -m scripts.build_all_models")
        return

    # Find all model directories
    model_dirs = [d for d in silver_root.iterdir() if d.is_dir() and not d.name.startswith('.')]

    if args.models:
        model_dirs = [d for d in model_dirs if d.name in args.models]

    if not model_dirs:
        logger.error(f"No model directories found in {silver_root}")
        print(f"\n❌ No model directories found in {silver_root}")
        return

    model_names = [d.name for d in model_dirs]
    logger.info(f"Found {len(model_dirs)} model(s): {model_names}")
    print(f"\n✓ Found {len(model_dirs)} model(s): {model_names}")
    print(f"✓ DuckDB database: {duckdb_path}")

    # Connect to DuckDB
    try:
        conn = duckdb.connect(str(duckdb_path))
        logger.debug(f"Connected to DuckDB at {duckdb_path}")
        print(f"✓ Connected to DuckDB")
    except Exception as e:
        logger.error(f"Failed to connect to DuckDB: {e}", exc_info=True)
        print(f"\n❌ Failed to connect to DuckDB: {e}")
        return

    # Check each model
    total_tables = 0
    working_tables = 0

    for model_dir in sorted(model_dirs):
        model_name = model_dir.name

        print_header(f"MODEL: {model_name}")
        logger.info(f"Checking model: {model_name}")

        # Find all parquet tables for this model
        parquet_files = list(model_dir.rglob("*.parquet"))

        if not parquet_files:
            logger.warning(f"No parquet files found in {model_dir}")
            print(f"⚠️  No parquet files found in {model_dir}")
            continue

        # Group by table (dims/table_name or facts/table_name)
        # Structure: model/dims/dim_name/... or model/facts/fact_name/...
        by_table = defaultdict(list)
        for pf in parquet_files:
            rel_path = pf.relative_to(model_dir)
            # Get the table type (dims/facts) and actual table name
            if len(rel_path.parts) >= 2:
                table_type = rel_path.parts[0]  # 'dims' or 'facts'
                table_name = rel_path.parts[1]  # actual table name
                table_key = f"{table_type}/{table_name}"
            else:
                table_key = rel_path.parts[0]
            by_table[table_key].append(pf)

        print(f"\nTables found: {list(by_table.keys())}")

        # Check each table
        for table_name, files in sorted(by_table.items()):
            total_tables += 1

            print_subheader(f"TABLE: {model_name}.{table_name}")
            print(f"Files: {len(files)}")
            print(f"Path: {model_dir / table_name}")
            logger.debug(f"Checking table {model_name}.{table_name} ({len(files)} files)")

            # Try to read from Parquet files directly
            try:
                pattern = str(model_dir / table_name / "**" / "*.parquet")
                df = conn.from_parquet(pattern, union_by_name=True, hive_partitioning=True)

                # Get column info
                columns = df.columns
                print(f"\nColumns ({len(columns)}):")
                for col in columns[:10]:  # Show first 10 columns
                    print(f"  - {col}")
                if len(columns) > 10:
                    print(f"  ... and {len(columns) - 10} more")

                # Get row count
                count = df.count('*').fetchone()[0]
                print(f"\nRows: {count:,}")
                logger.debug(f"Table {model_name}.{table_name}: {count:,} rows, {len(columns)} columns")

                # Show sample data
                if count > 0:
                    print(f"\nSample data (top {args.top_n} rows):")
                    sample = df.limit(args.top_n).df()

                    # Truncate wide output
                    pd_options = {
                        'display.max_columns': 8,
                        'display.width': 120,
                        'display.max_colwidth': 20
                    }

                    import pandas as pd
                    with pd.option_context(*[item for pair in pd_options.items() for item in pair]):
                        print(sample.to_string(index=False))

                working_tables += 1
                print(f"\n✅ Table readable from Parquet")
                logger.info(f"Table {model_name}.{table_name} OK: {count:,} rows")

            except Exception as e:
                logger.error(f"Error reading Parquet for {model_name}.{table_name}: {e}", exc_info=True)
                print(f"\n❌ Error reading Parquet: {e}")

            # Check if DuckDB view exists
            view_name = f"{model_name}.{table_name}"
            try:
                view_exists = conn.execute(f"""
                    SELECT COUNT(*) as cnt
                    FROM information_schema.views
                    WHERE table_schema = '{model_name}'
                    AND table_name = '{table_name}'
                """).fetchone()[0] > 0

                if view_exists:
                    print(f"✅ DuckDB view exists: {view_name}")

                    # Try to query the view
                    try:
                        view_count = conn.execute(f"SELECT COUNT(*) as cnt FROM {view_name}").fetchone()[0]
                        print(f"   View rows: {view_count:,}")

                        if view_count != count:
                            logger.warning(f"Row count mismatch for {view_name}: Parquet={count}, View={view_count}")
                            print(f"   ⚠️  Row count mismatch! Parquet: {count:,}, View: {view_count:,}")
                    except Exception as e:
                        logger.error(f"Error querying view {view_name}: {e}")
                        print(f"   ❌ Error querying view: {e}")
                else:
                    logger.warning(f"DuckDB view not created: {view_name}")
                    print(f"⚠️  DuckDB view NOT created: {view_name}")
                    print(f"   To create:")
                    print(f"   CREATE OR REPLACE VIEW {view_name} AS")
                    print(f"   SELECT * FROM read_parquet('{pattern}', hive_partitioning=true)")

            except Exception as e:
                logger.error(f"Error checking view {view_name}: {e}")
                print(f"❌ Error checking view: {e}")

    # Summary
    print_header("SUMMARY")
    print(f"Total tables found: {total_tables}")
    print(f"Working tables: {working_tables}")
    print(f"Failed tables: {total_tables - working_tables}")
    logger.info(f"Summary: {working_tables}/{total_tables} tables working")

    if working_tables == total_tables:
        print(f"\n✅ All tables readable!")
    else:
        logger.warning(f"{total_tables - working_tables} tables have issues")
        print(f"\n⚠️  Some tables have issues - see details above")

    # Check cross-model relationships
    print_header("CROSS-MODEL RELATIONSHIPS")

    # Test stocks → company join (if both exist)
    if 'stocks' in [d.name for d in model_dirs] and 'company' in [d.name for d in model_dirs]:
        print("\n[1] Testing stocks → company join (via CIK)...")
        logger.debug("Testing stocks → company join")
        try:
            result = conn.execute("""
                SELECT
                    s.ticker,
                    s.cik,
                    s.company_id,
                    c.company_name,
                    c.sector
                FROM stocks.dim_stock s
                LEFT JOIN company.dim_company c ON s.company_id = c.company_id
                LIMIT 3
            """).fetchdf()

            print(f"✅ Join successful! Sample:")
            print(result.to_string(index=False))

            # Check join coverage
            join_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_stocks,
                    COUNT(c.company_id) as with_company,
                    COUNT(*) - COUNT(c.company_id) as without_company
                FROM stocks.dim_stock s
                LEFT JOIN company.dim_company c ON s.company_id = c.company_id
            """).fetchone()

            total, with_co, without_co = join_stats
            print(f"\nJoin coverage:")
            print(f"  Total stocks: {total}")
            print(f"  With company: {with_co} ({with_co/total*100:.1f}%)")
            print(f"  Without company: {without_co} ({without_co/total*100:.1f}%)")
            logger.info(f"stocks→company join: {with_co}/{total} ({with_co/total*100:.1f}%) matched")

        except Exception as e:
            logger.error(f"stocks→company join failed: {e}", exc_info=True)
            print(f"❌ Join failed: {e}")

    # Test stocks prices aggregation
    if 'stocks' in [d.name for d in model_dirs]:
        print("\n[2] Testing stocks price aggregation...")
        logger.debug("Testing stocks price aggregation")
        try:
            result = conn.execute("""
                SELECT
                    ticker,
                    COUNT(*) as price_records,
                    MIN(trade_date) as earliest_date,
                    MAX(trade_date) as latest_date,
                    AVG(close) as avg_close_price
                FROM stocks.fact_stock_prices
                GROUP BY ticker
                ORDER BY price_records DESC
                LIMIT 5
            """).fetchdf()

            print(f"✅ Aggregation successful! Top 5 tickers by data:")
            print(result.to_string(index=False))
            logger.info("stocks price aggregation successful")

        except Exception as e:
            logger.error(f"stocks price aggregation failed: {e}", exc_info=True)
            print(f"❌ Aggregation failed: {e}")

    print_header("RECOMMENDATIONS")

    if working_tables < total_tables:
        print("\n⚠️  Some tables are not readable.")
        print("1. Check Parquet file integrity")
        print("2. Rebuild affected models:")
        print("   from models.api.registry import get_model_registry")
        print("   registry = get_model_registry()")
        print("   registry.get_model('model_name').build(force=True)")

    # Check for missing views
    try:
        view_count = conn.execute("""
            SELECT COUNT(*) as cnt
            FROM information_schema.views
        """).fetchone()[0]

        if view_count == 0:
            logger.warning("No DuckDB views found")
            print("\n⚠️  No DuckDB views found!")
            print("Create views to enable SQL queries:")
            print("""
    import duckdb
    conn = duckdb.connect('storage/duckdb/analytics.db')
    conn.execute("CREATE SCHEMA IF NOT EXISTS stocks")
    conn.execute('''
        CREATE OR REPLACE VIEW stocks.dim_stock AS
        SELECT * FROM read_parquet('storage/silver/stocks/dim_stock/*.parquet', hive_partitioning=true)
    ''')
            """)
        elif view_count < working_tables:
            logger.warning(f"Only {view_count} views created for {working_tables} tables")
            print(f"\n⚠️  Only {view_count} views created for {working_tables} tables")
            print("Consider creating missing views for easier querying")
    except Exception as e:
        logger.warning(f"Could not check views: {e}")
        print(f"⚠️  Could not check views: {e}")

    print_header("DIAGNOSTIC COMPLETE")
    logger.info("Silver layer diagnostics complete")

    conn.close()


if __name__ == "__main__":
    main()
