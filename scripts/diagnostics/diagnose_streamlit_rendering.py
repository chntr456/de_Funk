#!/usr/bin/env python3
"""
Diagnose Streamlit Rendering Issues

This script helps diagnose "[object Object]" rendering issues by:
1. Connecting to DuckDB and querying data
2. Checking DataFrame data types
3. Identifying problematic columns
4. Testing JSON serialization

Usage:
    python -m scripts.test.diagnose_streamlit_rendering
"""

import sys
from pathlib import Path
from de_funk.utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

def diagnose_rendering():
    """Diagnose Streamlit rendering issues."""

    print("=" * 80)
    print("STREAMLIT RENDERING DIAGNOSTICS")
    print("=" * 80)

    # Step 1: Connect to DuckDB
    print("\n[1] Connecting to DuckDB...")
    print("-" * 80)

    try:
        import duckdb
        import pandas as pd
        import json

        db_path = repo_root / "storage" / "duckdb" / "analytics.db"
        if not db_path.exists():
            print(f"❌ Database not found: {db_path}")
            print("\nCreate database first:")
            print("  python -m scripts.setup.setup_duckdb_views")
            return

        conn = duckdb.connect(str(db_path), read_only=True)
        print(f"✓ Connected to: {db_path}")

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    # Step 2: Query sample data
    print("\n[2] Querying sample data...")
    print("-" * 80)

    try:
        # Try the first exhibit query
        sql = """
        SELECT
            s.ticker,
            s.security_name,
            s.sector,
            s.industry,
            p.close,
            p.volume,
            p.trade_date
        FROM stocks.dim_stock s
        JOIN stocks.fact_stock_prices p ON s.ticker = p.ticker
        WHERE p.trade_date = (SELECT MAX(trade_date) FROM stocks.fact_stock_prices)
        LIMIT 5
        """

        result = conn.execute(sql)
        df = result.fetch_df()  # This is what DuckDB adapter does

        print(f"✓ Query executed successfully")
        print(f"  Rows: {len(df)}")
        print(f"  Columns: {len(df.columns)}")

    except Exception as e:
        print(f"❌ Query failed: {e}")
        conn.close()
        return

    # Step 3: Inspect data types
    print("\n[3] Inspecting DataFrame data types...")
    print("-" * 80)

    print("\nColumn data types:")
    for col in df.columns:
        dtype = df[col].dtype
        print(f"  {col:20s} {str(dtype):15s}", end="")

        # Check if problematic
        if dtype == 'object':
            # Check what's actually in the column
            sample = df[col].iloc[0] if len(df) > 0 else None
            sample_type = type(sample).__name__
            print(f"  [object dtype - contains {sample_type}]", end="")

            # Flag if it's not a string
            if sample_type not in ['str', 'NoneType', 'float', 'int']:
                print(f"  ⚠️ PROBLEMATIC")
            else:
                print()
        else:
            print()

    # Step 4: Display sample data
    print("\n[4] Sample data:")
    print("-" * 80)
    print(df.to_string(index=False))

    # Step 5: Test JSON serialization
    print("\n[5] Testing JSON serialization...")
    print("-" * 80)

    try:
        # Try to convert to JSON (what Streamlit does internally)
        json_str = df.to_json(orient='records', date_format='iso')
        print(f"✓ DataFrame serializes to JSON successfully")
        print(f"  JSON length: {len(json_str)} characters")

        # Try to parse it back
        data = json.loads(json_str)
        print(f"✓ JSON parses successfully")
        print(f"  First record: {data[0] if data else 'N/A'}")

    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")
        print("\nThis is likely causing the '[object Object]' error!")

        # Find problematic columns
        print("\nTesting individual columns...")
        for col in df.columns:
            try:
                test_df = df[[col]]
                test_json = test_df.to_json(orient='records')
                print(f"  ✓ {col}")
            except Exception as col_e:
                print(f"  ❌ {col}: {col_e}")

    # Step 6: Test Streamlit dataframe conversion
    print("\n[6] Testing Streamlit compatibility...")
    print("-" * 80)

    try:
        # Check if data types are Streamlit-compatible
        incompatible = []

        for col in df.columns:
            dtype = df[col].dtype

            # Check for known incompatible types
            if dtype == 'object':
                sample = df[col].iloc[0] if len(df) > 0 else None
                if sample is not None and not isinstance(sample, (str, int, float, bool)):
                    incompatible.append((col, type(sample).__name__))

        if incompatible:
            print("⚠️ Found potentially incompatible columns:")
            for col, dtype in incompatible:
                print(f"  - {col}: {dtype}")
            print("\nRecommendation: Convert these columns to strings or primitives")
        else:
            print("✓ All columns appear Streamlit-compatible")

    except Exception as e:
        print(f"❌ Compatibility check failed: {e}")

    # Step 7: Recommendations
    print("\n[7] Recommendations:")
    print("-" * 80)

    # Check for common issues
    has_object_cols = any(df[col].dtype == 'object' for col in df.columns)
    has_datetime_cols = any('datetime' in str(df[col].dtype) for col in df.columns)

    if has_object_cols:
        print("⚠️ DataFrame contains object-dtype columns")
        print("   → Ensure these contain only strings, not Python objects")
        print("   → Consider: df = df.astype({col: 'str'}) for problematic columns")

    if has_datetime_cols:
        print("ℹ️  DataFrame contains datetime columns")
        print("   → These should serialize fine, but ensure timezone-aware")
        print("   → Consider: df[col] = df[col].dt.strftime('%Y-%m-%d') if needed")

    print("\n✓ Diagnostics complete")
    conn.close()


if __name__ == "__main__":
    diagnose_rendering()
