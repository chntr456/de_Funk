#!/usr/bin/env python3
"""
Build Weighted Aggregate Views (DuckDB).

This script builds weighted aggregate measure views in DuckDB from existing silver layer data.
These views provide pre-calculated weighted indices across multiple stocks.

Usage:
    python scripts/build_weighted_aggregates_duckdb.py
    python scripts/build_weighted_aggregates_duckdb.py --materialize  # Create tables instead of views
"""

import argparse
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.context import RepoContext
from models.builders.weighted_aggregate_builder import WeightedAggregateBuilder, load_model_config


def main():
    parser = argparse.ArgumentParser(description="Build weighted aggregate views")
    parser.add_argument(
        "--materialize",
        action="store_true",
        help="Materialize as tables (default: create views)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="company",
        help="Model name (default: company)"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Weighted Aggregate Builder (DuckDB)")
    print("=" * 70)

    # Initialize context with DuckDB
    print("\n1. Initializing DuckDB context...")
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    print(f"   ✓ Repo root: {ctx.repo}")
    print(f"   ✓ Connection type: DuckDB")

    # Load model config
    print(f"\n2. Loading model configuration...")
    model_path = ctx.repo / "configs" / "models" / f"{args.model}.yaml"
    if not model_path.exists():
        print(f"   ✗ ERROR: Model config not found: {model_path}")
        sys.exit(1)

    model_config = load_model_config(model_path)
    print(f"   ✓ Model loaded: {model_config.get('model')}")

    # Check silver layer exists
    print("\n3. Checking silver layer...")
    silver_path = Path(model_config['storage']['root'])
    if not silver_path.exists():
        print(f"   ✗ ERROR: Silver layer not found: {silver_path}")
        print("   Run test_build_silver.py first to create silver layer")
        sys.exit(1)

    fact_prices_path = silver_path / "facts" / "fact_prices"
    if not fact_prices_path.exists():
        print(f"   ✗ ERROR: fact_prices not found: {fact_prices_path}")
        sys.exit(1)

    print(f"   ✓ Silver layer found: {silver_path}")

    # Register fact_prices table with DuckDB
    print("\n4. Registering tables with DuckDB...")
    ctx.connection.conn.execute(f"""
        CREATE OR REPLACE VIEW fact_prices AS
        SELECT * FROM read_parquet('{fact_prices_path}/*.parquet')
    """)

    # Count rows
    row_count = ctx.connection.conn.execute("SELECT COUNT(*) FROM fact_prices").fetchone()[0]
    print(f"   ✓ fact_prices registered: {row_count:,} rows")

    # Build weighted aggregates
    print("\n5. Building weighted aggregate measures...")
    builder = WeightedAggregateBuilder(
        connection=ctx.connection.conn,  # Pass raw DuckDB connection
        model_config=model_config,
        storage_path=silver_path
    )

    mode = "tables" if args.materialize else "views"
    print(f"   Mode: {mode}")
    print()

    builder.build_all_weighted_aggregates(materialize=args.materialize)

    # Verify and show results
    print("\n6. Verifying weighted aggregates...")
    weighted_measures = [
        'equal_weighted_index',
        'volume_weighted_index',
        'market_cap_weighted_index',
        'price_weighted_index',
        'volume_deviation_weighted_index',
        'volatility_weighted_index',
    ]

    print("\n   Sample data from each aggregate:\n")
    for measure_id in weighted_measures:
        try:
            result = ctx.connection.conn.execute(f"""
                SELECT COUNT(*) as row_count,
                       MIN(weighted_value) as min_value,
                       MAX(weighted_value) as max_value,
                       AVG(weighted_value) as avg_value
                FROM {measure_id}
            """).fetchone()

            if result:
                count, min_val, max_val, avg_val = result
                print(f"   {measure_id}:")
                print(f"     Rows: {count:,}")
                print(f"     Range: ${min_val:.2f} - ${max_val:.2f}")
                print(f"     Average: ${avg_val:.2f}")
                print()
        except Exception as e:
            print(f"   ✗ {measure_id}: {str(e)}\n")

    # Show sample comparison
    print("\n7. Sample comparison (first 5 dates):")
    print("   " + "-" * 66)
    try:
        result = ctx.connection.conn.execute("""
            SELECT
                trade_date,
                ROUND(ew.weighted_value, 2) as equal_weighted,
                ROUND(vw.weighted_value, 2) as volume_weighted,
                ROUND(mc.weighted_value, 2) as market_cap_weighted
            FROM equal_weighted_index ew
            LEFT JOIN volume_weighted_index vw USING (trade_date)
            LEFT JOIN market_cap_weighted_index mc USING (trade_date)
            ORDER BY trade_date
            LIMIT 5
        """).fetchdf()

        print(result.to_string(index=False))
    except Exception as e:
        print(f"   Error: {e}")

    # Success
    print("\n" + "=" * 70)
    print("✓ SUCCESS: Weighted aggregates built successfully!")
    print("=" * 70)

    print(f"\nCreated {mode} for {len(weighted_measures)} weighted measures:")
    for measure_id in weighted_measures:
        print(f"  • {measure_id}")

    print("\nYou can now:")
    print("  1. Query aggregates directly: SELECT * FROM equal_weighted_index")
    print("  2. Use in notebooks via model-defined measures")
    print("  3. Run the UI: streamlit run app/ui/notebook_app_duckdb.py")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
