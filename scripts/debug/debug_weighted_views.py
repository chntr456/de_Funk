#!/usr/bin/env python3
"""
Debug weighted aggregate views - check SQL and data.
"""

from pathlib import Path
import sys

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext
from models.builders import WeightedAggregateBuilder
import yaml

def debug_weighted_views():
    """Debug weighted aggregate view SQL and results."""
    print("=" * 70)
    print("Debugging Weighted Aggregate Views")
    print("=" * 70)

    # Load equity model config
    model_config_path = Path("configs/models/equity.yaml")
    with open(model_config_path, 'r') as f:
        model_cfg = yaml.safe_load(f)

    # Get DuckDB connection
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    conn = ctx.connection.conn

    # Get storage path
    storage_root = model_cfg.get('storage', {}).get('root', 'storage/silver/equity')
    storage_path = Path(storage_root)

    # Create builder
    builder = WeightedAggregateBuilder(
        connection=conn,
        model_config=model_cfg,
        storage_path=storage_path
    )

    # Check equal_weighted_index as example
    measure_id = 'equal_weighted_index'
    measure = model_cfg['measures'][measure_id]

    print(f"\n1. Measure Configuration for '{measure_id}':")
    print(f"   - Type: {measure.get('type')}")
    print(f"   - Source: {measure.get('source')}")
    print(f"   - Weighting method: {measure.get('weighting_method')}")
    print(f"   - Group by: {measure.get('group_by')}")

    # Generate SQL
    print(f"\n2. Generated SQL for view:")
    print("-" * 70)
    sql = builder._generate_weighted_aggregate_sql(measure_id, measure)
    print(sql)
    print("-" * 70)

    # Check if view exists
    print(f"\n3. Checking if view exists in database:")
    try:
        result = conn.execute(f"SELECT name FROM duckdb_views() WHERE name = '{measure_id}'").fetchone()
        if result:
            print(f"   ✓ View '{measure_id}' exists")
        else:
            print(f"   ✗ View '{measure_id}' does NOT exist")
            print(f"   Run: python scripts/build_weighted_views.py")
            return
    except Exception as e:
        print(f"   ✗ Error checking view: {e}")
        return

    # Query the view
    print(f"\n4. Querying view (first 10 rows):")
    try:
        df = conn.execute(f"""
            SELECT * FROM {measure_id}
            ORDER BY trade_date
            LIMIT 10
        """).fetchdf()

        print(f"   Rows returned: {len(df)}")
        print(f"   Columns: {list(df.columns)}")
        print("\n   Sample data:")
        print(df.to_string(index=False))

        # Check for uniqueness (should be one row per trade_date)
        total_rows = conn.execute(f"SELECT COUNT(*) FROM {measure_id}").fetchone()[0]
        unique_dates = conn.execute(f"SELECT COUNT(DISTINCT trade_date) FROM {measure_id}").fetchone()[0]

        print(f"\n5. Data integrity check:")
        print(f"   Total rows: {total_rows:,}")
        print(f"   Unique dates: {unique_dates:,}")

        if total_rows == unique_dates:
            print(f"   ✓ CORRECT: One row per date (properly aggregated)")
        else:
            print(f"   ✗ PROBLEM: Multiple rows per date (NOT properly aggregated!)")
            print(f"   This explains the jagged lines - showing multiple values per date")

            # Show example of duplicate dates
            print(f"\n   Example dates with multiple rows:")
            dupes = conn.execute(f"""
                SELECT trade_date, COUNT(*) as cnt
                FROM {measure_id}
                GROUP BY trade_date
                HAVING COUNT(*) > 1
                ORDER BY trade_date
                LIMIT 5
            """).fetchdf()
            print(dupes.to_string(index=False))

    except Exception as e:
        print(f"   ✗ Error querying view: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)


if __name__ == '__main__':
    try:
        debug_weighted_views()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
