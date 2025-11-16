#!/usr/bin/env python3
"""
Test script to verify weighted aggregate views are created correctly.

Run this after rebuilding the equity model to verify the views exist.
"""

from pathlib import Path
import sys

# Setup imports
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext

def test_weighted_views():
    """Test that weighted aggregate views exist and are queryable."""
    print("=" * 70)
    print("Testing Weighted Aggregate Views")
    print("=" * 70)

    # Initialize context
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    conn = ctx.connection.conn

    # Expected weighted views
    expected_views = [
        'equal_weighted_index',
        'volume_weighted_index',
        'market_cap_weighted_index',
        'price_weighted_index',
        'volume_deviation_weighted_index',
        'volatility_weighted_index'
    ]

    print("\n1. Checking if views exist in database...")
    print("-" * 70)

    # Get all views
    all_views = conn.execute("SELECT name FROM duckdb_views()").fetchdf()
    view_names = set(all_views['name'].tolist())

    results = {}
    for view_name in expected_views:
        exists = view_name in view_names
        results[view_name] = exists
        status = "✓" if exists else "✗"
        print(f"  {status} {view_name}")

    # Test querying each view
    print("\n2. Testing view queries...")
    print("-" * 70)

    query_results = {}
    for view_name in expected_views:
        if not results[view_name]:
            print(f"  ⊘ {view_name} - skipped (view doesn't exist)")
            query_results[view_name] = False
            continue

        try:
            # Try to query the view
            df = conn.execute(f"SELECT * FROM {view_name} LIMIT 5").fetchdf()
            rows = len(df)
            query_results[view_name] = True
            print(f"  ✓ {view_name} - {rows} rows returned")

            # Show sample data
            if rows > 0:
                print(f"     Columns: {', '.join(df.columns.tolist())}")
                if 'weighted_value' in df.columns:
                    print(f"     Sample weighted_value: {df['weighted_value'].iloc[0]:.2f}")

        except Exception as e:
            query_results[view_name] = False
            print(f"  ✗ {view_name} - query failed: {str(e)[:60]}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    views_exist = sum(results.values())
    queries_work = sum(query_results.values())
    total = len(expected_views)

    print(f"  Views created: {views_exist}/{total}")
    print(f"  Views queryable: {queries_work}/{total}")

    if views_exist == total and queries_work == total:
        print("\n  ✓ All weighted aggregate views are working!")
        return True
    elif views_exist == 0:
        print("\n  ✗ No views found - model needs to be rebuilt")
        print("\n  Run: python scripts/rebuild_model.py --model equity")
        return False
    else:
        print(f"\n  ⚠ {total - queries_work} views have issues")
        return False


if __name__ == '__main__':
    try:
        success = test_weighted_views()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
