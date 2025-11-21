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


def main():
    parser = argparse.ArgumentParser(description='Diagnose silver layer data')
    parser.add_argument('--top-n', type=int, default=3,
                        help='Number of rows to show per table (default: 3)')
    parser.add_argument('--models', nargs='*',
                        help='Specific models to check (default: all)')
    args = parser.parse_args()

    print("=" * 80)
    print("SILVER LAYER DIAGNOSTICS")
    print("=" * 80)

    # Load config
    loader = ConfigLoader()
    config = loader.load()

    silver_root = config.repo_root / "storage" / "silver"
    duckdb_path = config.connection.duckdb.database_path

    if not silver_root.exists():
        print(f"\n❌ Silver directory not found: {silver_root}")
        print("\nYou need to build models first:")
        print("  python -m scripts.build_all_models")
        return

    # Find all model directories
    model_dirs = [d for d in silver_root.iterdir() if d.is_dir() and not d.name.startswith('.')]

    if args.models:
        model_dirs = [d for d in model_dirs if d.name in args.models]

    if not model_dirs:
        print(f"\n❌ No model directories found in {silver_root}")
        return

    print(f"\n✓ Found {len(model_dirs)} model(s): {[d.name for d in model_dirs]}")
    print(f"✓ DuckDB database: {duckdb_path}")

    # Connect to DuckDB
    try:
        conn = duckdb.connect(str(duckdb_path))
        print(f"✓ Connected to DuckDB")
    except Exception as e:
        print(f"\n❌ Failed to connect to DuckDB: {e}")
        return

    # Check each model
    total_tables = 0
    working_tables = 0

    for model_dir in sorted(model_dirs):
        model_name = model_dir.name

        print(f"\n{'=' * 80}")
        print(f"MODEL: {model_name}")
        print(f"{'=' * 80}")

        # Find all parquet tables for this model
        parquet_files = list(model_dir.rglob("*.parquet"))

        if not parquet_files:
            print(f"⚠️  No parquet files found in {model_dir}")
            continue

        # Group by table (immediate subdirectory of model)
        by_table = defaultdict(list)
        for pf in parquet_files:
            rel_path = pf.relative_to(model_dir)
            table = rel_path.parts[0]
            by_table[table].append(pf)

        print(f"\nTables found: {list(by_table.keys())}")

        # Check each table
        for table_name, files in sorted(by_table.items()):
            total_tables += 1

            print(f"\n{'-' * 80}")
            print(f"TABLE: {model_name}.{table_name}")
            print(f"{'-' * 80}")
            print(f"Files: {len(files)}")
            print(f"Path: {model_dir / table_name}")

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

            except Exception as e:
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
                            print(f"   ⚠️  Row count mismatch! Parquet: {count:,}, View: {view_count:,}")
                    except Exception as e:
                        print(f"   ❌ Error querying view: {e}")
                else:
                    print(f"⚠️  DuckDB view NOT created: {view_name}")
                    print(f"   To create:")
                    print(f"   CREATE OR REPLACE VIEW {view_name} AS")
                    print(f"   SELECT * FROM read_parquet('{pattern}', hive_partitioning=true)")

            except Exception as e:
                print(f"❌ Error checking view: {e}")

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total tables found: {total_tables}")
    print(f"Working tables: {working_tables}")
    print(f"Failed tables: {total_tables - working_tables}")

    if working_tables == total_tables:
        print(f"\n✅ All tables readable!")
    else:
        print(f"\n⚠️  Some tables have issues - see details above")

    # Check cross-model relationships
    print(f"\n{'=' * 80}")
    print("CROSS-MODEL RELATIONSHIPS")
    print(f"{'=' * 80}")

    # Test stocks → company join (if both exist)
    if 'stocks' in [d.name for d in model_dirs] and 'company' in [d.name for d in model_dirs]:
        print("\n[1] Testing stocks → company join (via CIK)...")
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

        except Exception as e:
            print(f"❌ Join failed: {e}")

    # Test stocks prices aggregation
    if 'stocks' in [d.name for d in model_dirs]:
        print("\n[2] Testing stocks price aggregation...")
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

        except Exception as e:
            print(f"❌ Aggregation failed: {e}")

    print(f"\n{'=' * 80}")
    print("RECOMMENDATIONS")
    print(f"{'=' * 80}")

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
            print(f"\n⚠️  Only {view_count} views created for {working_tables} tables")
            print("Consider creating missing views for easier querying")
    except Exception as e:
        print(f"⚠️  Could not check views: {e}")

    print(f"\n{'=' * 80}")
    print("DIAGNOSTIC COMPLETE")
    print(f"{'=' * 80}")

    conn.close()


if __name__ == "__main__":
    main()
