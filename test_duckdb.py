#!/usr/bin/env python3
"""
Test DuckDB connection with existing Parquet files.

This script demonstrates:
1. Creating a DuckDB connection
2. Reading Parquet files directly
3. Applying filters
4. Converting to pandas
5. Performance comparison
"""

import sys
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("DuckDB Connection Test")
print("=" * 60)

try:
    # Check if DuckDB is installed
    import duckdb
    print("\n✓ DuckDB is installed")
    print(f"  Version: {duckdb.__version__}")
except ImportError:
    print("\n✗ DuckDB is not installed")
    print("\nInstall it with:")
    print("  pip install duckdb")
    sys.exit(1)

try:
    # Import connection
    print("\n1. Loading connection factory...")
    from src.core import ConnectionFactory
    print("   ✓ Connection factory loaded")

    # Create DuckDB connection
    print("\n2. Creating DuckDB connection...")
    start = time.time()
    conn = ConnectionFactory.create("duckdb")
    elapsed = time.time() - start
    print(f"   ✓ Connection created in {elapsed:.3f}s")

    # Check if Silver layer exists
    print("\n3. Checking for Silver layer data...")
    silver_root = Path("storage/silver/company")

    if not silver_root.exists():
        print(f"   ✗ Silver layer not found at {silver_root}")
        print("\n   Run this first:")
        print("     python test_build_silver.py")
        sys.exit(1)

    # Find a table to query
    dim_company_path = silver_root / "dims" / "dim_company"
    fact_prices_path = silver_root / "facts" / "fact_prices"

    if dim_company_path.exists():
        test_path = str(dim_company_path)
        table_name = "dim_company"
    elif fact_prices_path.exists():
        test_path = str(fact_prices_path)
        table_name = "fact_prices"
    else:
        print("   ✗ No tables found in Silver layer")
        sys.exit(1)

    print(f"   ✓ Found table: {table_name}")
    print(f"   ✓ Path: {test_path}")

    # Query the table
    print(f"\n4. Querying {table_name}...")
    start = time.time()
    df = conn.read_table(test_path)
    elapsed_read = time.time() - start
    print(f"   ✓ Table read in {elapsed_read:.3f}s")

    # Convert to pandas
    print("\n5. Converting to pandas...")
    start = time.time()
    pdf = conn.to_pandas(df)
    elapsed_convert = time.time() - start
    print(f"   ✓ Converted in {elapsed_convert:.3f}s")
    print(f"   ✓ Rows: {len(pdf):,}")
    print(f"   ✓ Columns: {len(pdf.columns)}")

    # Show schema
    print(f"\n6. Table schema:")
    for col in pdf.columns:
        dtype = pdf[col].dtype
        print(f"     • {col}: {dtype}")

    # Show sample data
    print(f"\n7. Sample data (first 5 rows):")
    print(pdf.head().to_string(index=False))

    # Test filtering (if applicable columns exist)
    print(f"\n8. Testing filters...")
    if 'ticker' in pdf.columns:
        # Filter by ticker
        start = time.time()
        filtered_df = conn.apply_filters(df, {'ticker': ['AAPL', 'GOOGL']})
        filtered_pdf = conn.to_pandas(filtered_df)
        elapsed_filter = time.time() - start

        print(f"   ✓ Filter applied in {elapsed_filter:.3f}s")
        print(f"   ✓ Filtered rows: {len(filtered_pdf):,}")
        print(f"\n   Filtered data:")
        print(filtered_pdf.head().to_string(index=False))
    elif 'trade_date' in pdf.columns:
        # Filter by date range
        start = time.time()
        filtered_df = conn.apply_filters(df, {
            'trade_date': {
                'start': '2024-01-01',
                'end': '2024-01-05'
            }
        })
        filtered_pdf = conn.to_pandas(filtered_df)
        elapsed_filter = time.time() - start

        print(f"   ✓ Date filter applied in {elapsed_filter:.3f}s")
        print(f"   ✓ Filtered rows: {len(filtered_pdf):,}")
    else:
        print("   ⚠ No filterable columns found (skipping)")

    # Performance summary
    total_time = elapsed_read + elapsed_convert
    if 'elapsed_filter' in locals():
        total_time += elapsed_filter

    print("\n" + "=" * 60)
    print("✓ SUCCESS: DuckDB connection works!")
    print("=" * 60)

    print(f"\nPerformance Summary:")
    print(f"  • Read time:    {elapsed_read:.3f}s")
    print(f"  • Convert time: {elapsed_convert:.3f}s")
    if 'elapsed_filter' in locals():
        print(f"  • Filter time:  {elapsed_filter:.3f}s")
    print(f"  • Total time:   {total_time:.3f}s")

    print(f"\nData Summary:")
    print(f"  • Table: {table_name}")
    print(f"  • Rows:  {len(pdf):,}")
    print(f"  • Cols:  {len(pdf.columns)}")

    print("\nNext Steps:")
    print("  1. Compare performance with Spark (test_build_silver.py)")
    print("  2. Update StorageService to use DuckDB")
    print("  3. Update notebook app to use DuckDB connection")

    # Clean up
    conn.stop()

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
