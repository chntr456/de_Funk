#!/usr/bin/env python
"""
Debug script to isolate the Spark session issue when reading stocks from forecast.

This script breaks down the exact sequence of calls to find where the session fails.

Usage:
    spark-submit --packages io.delta:delta-spark_2.13:4.0.0 scripts/debug/debug_forecast_read.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add repo to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def check_session_state(spark, label: str):
    """Check the current state of Spark session registration."""
    print(f"\n--- Session State: {label} ---")

    # Check if session is valid
    print(f"  spark object: {spark}")
    print(f"  spark.sparkContext: {spark.sparkContext if spark else 'N/A'}")

    if spark and hasattr(spark, '_jvm'):
        try:
            jvm = spark._jvm
            active = jvm.org.apache.spark.sql.SparkSession.getActiveSession()
            default = jvm.org.apache.spark.sql.SparkSession.getDefaultSession()
            print(f"  JVM active session: {active}")
            print(f"  JVM default session: {default}")
            print(f"  Active is present: {active.isDefined() if active else False}")
            print(f"  Default is present: {default.isDefined() if default else False}")
        except Exception as e:
            print(f"  Error checking JVM state: {e}")
    else:
        print(f"  Cannot access JVM")


def test_direct_delta_read(spark, path: str):
    """Test reading Delta table directly with spark.read."""
    print(f"\n--- Test: spark.read.format('delta').load('{path}') ---")
    try:
        df = spark.read.format("delta").load(path)
        count = df.count()
        print(f"  SUCCESS: Read {count} rows")
        return df
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def test_deltatable_api(spark, path: str):
    """Test reading Delta table using DeltaTable.forPath API."""
    print(f"\n--- Test: DeltaTable.forPath(spark, '{path}') ---")
    try:
        from delta.tables import DeltaTable
        dt = DeltaTable.forPath(spark, path)
        df = dt.toDF()
        count = df.count()
        print(f"  SUCCESS: Read {count} rows")
        return df
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def test_pyarrow_read(path: str):
    """Test reading Delta table using PyArrow (no Spark)."""
    print(f"\n--- Test: PyArrow/DeltaTable read '{path}' ---")
    try:
        from deltalake import DeltaTable as DeltaTableRS
        dt = DeltaTableRS(path)
        df = dt.to_pyarrow_table()
        print(f"  SUCCESS: Read {len(df)} rows via PyArrow")
        return df
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def force_register_session(spark):
    """Force register session in JVM thread-local storage."""
    print(f"\n--- Forcing session registration ---")
    try:
        jvm = spark._jvm
        jss = spark._jsparkSession
        jvm.org.apache.spark.sql.SparkSession.setActiveSession(jss)
        jvm.org.apache.spark.sql.SparkSession.setDefaultSession(jss)
        print(f"  Registration attempted")
        check_session_state(spark, "After forced registration")
    except Exception as e:
        print(f"  Registration failed: {e}")


def find_stocks_silver(storage_root: Path) -> Path | None:
    """Search for stocks Silver layer in various possible locations."""
    candidates = [
        storage_root / "silver" / "securities" / "stocks",
        storage_root / "silver" / "stocks",
        storage_root / "silver" / "securities",
    ]

    print("Searching for stocks Silver layer...")
    for candidate in candidates:
        print(f"  Checking: {candidate}")
        if candidate.exists():
            # Check if it has dim_stock or fact_stock_prices
            if (candidate / "dim_stock").exists() or (candidate / "fact_stock_prices").exists():
                print(f"  FOUND stocks at: {candidate}")
                return candidate
            # List what's there
            contents = list(candidate.iterdir()) if candidate.is_dir() else []
            print(f"    Contents: {[c.name for c in contents[:10]]}")

    # Also scan silver directory directly
    silver_root = storage_root / "silver"
    if silver_root.exists():
        print(f"\n  Scanning {silver_root}...")
        for item in silver_root.iterdir():
            print(f"    {item.name}/ : {[c.name for c in item.iterdir()][:5] if item.is_dir() else 'file'}")

    return None


def main():
    print_section("DEBUG: Forecast Stocks Read Issue")

    # Determine storage path
    storage_root = Path("/shared/storage")
    if not storage_root.exists():
        storage_root = repo_root / "storage"

    print(f"Storage root: {storage_root}")
    print(f"Storage root exists: {storage_root.exists()}")

    # Find where stocks actually is
    stocks_silver = find_stocks_silver(storage_root)

    if stocks_silver is None:
        print("\nERROR: Could not find stocks Silver layer!")
        print("Please run: ls -la /shared/storage/silver/")
        return

    dim_stock_path = stocks_silver / "dim_stock"
    fact_prices_path = stocks_silver / "fact_stock_prices"

    print(f"\nStocks silver: {stocks_silver}")
    print(f"dim_stock exists: {dim_stock_path.exists()}")
    print(f"fact_prices exists: {fact_prices_path.exists()}")

    # Step 1: Get Spark session
    print_section("Step 1: Create Spark Session")

    from orchestration.common.spark_session import get_spark
    spark = get_spark()
    print(f"Got spark session: {spark}")
    check_session_state(spark, "Initial")

    # Step 2: Read dim_stock - try both methods
    print_section("Step 2: Read dim_stock")

    check_session_state(spark, "Before dim_stock read")

    # Try spark.read first
    df1 = test_direct_delta_read(spark, str(dim_stock_path))
    if df1:
        print(f"\n  Sample tickers (spark.read): {[r.ticker for r in df1.select('ticker').limit(5).collect()]}")

    # Also try DeltaTable API
    df1b = test_deltatable_api(spark, str(dim_stock_path))
    if df1b:
        print(f"\n  Sample tickers (DeltaTable): {[r.ticker for r in df1b.select('ticker').limit(5).collect()]}")

    check_session_state(spark, "After dim_stock read")

    # Step 3: Read fact_stock_prices
    print_section("Step 3: Read fact_stock_prices")

    check_session_state(spark, "Before fact_prices read")

    # Try spark.read first
    df2 = test_direct_delta_read(spark, str(fact_prices_path))
    if df2:
        print(f"\n  Row count (spark.read): {df2.count()}")

    # Also try DeltaTable API
    df2b = test_deltatable_api(spark, str(fact_prices_path))
    if df2b:
        print(f"\n  Row count (DeltaTable): {df2b.count()}")

    check_session_state(spark, "After fact_prices read")

    # Step 4: Simulate what ForecastBuilder does - create StocksModel
    print_section("Step 4: Simulate ForecastBuilder._get_stocks_model()")

    print("Creating SparkConnection wrapper...")
    from core.connection import get_spark_connection
    connection = get_spark_connection(spark)
    print(f"  Connection: {connection}")
    print(f"  Connection.spark: {connection.spark}")

    check_session_state(spark, "After SparkConnection created")

    print("\nCreating StocksModel (exactly like ForecastBuilder does)...")
    from models.domains.securities.stocks.model import StocksModel
    from config.domain_loader import ModelConfigLoader

    # Load model config the same way ForecastBuilder does
    domains_dir = repo_root / "domains"
    print(f"  Loading config from: {domains_dir}")
    loader = ModelConfigLoader(domains_dir)
    stocks_config = loader.load_model_config("stocks")
    print(f"  stocks_config loaded: {list(stocks_config.keys()) if stocks_config else 'None'}")

    # Build storage_cfg - this is what ForecastBuilder uses
    storage_cfg = {
        'root': str(storage_root),
        'silver_root': str(storage_root / 'silver'),
        'bronze_root': str(storage_root / 'bronze'),
    }
    print(f"  storage_cfg: {storage_cfg}")

    stocks_model = StocksModel(
        connection=connection,
        storage_cfg=storage_cfg,
        model_cfg=stocks_config,
        params={},
        repo_root=repo_root
    )
    print(f"  StocksModel: {stocks_model}")
    print(f"  stocks_model.connection: {stocks_model.connection}")
    print(f"  stocks_model.backend: {stocks_model.backend}")

    check_session_state(spark, "After StocksModel created")

    # Step 5: Call ensure_built - this is where it might fail
    print_section("Step 5: Call stocks_model.ensure_built()")

    check_session_state(spark, "Before ensure_built")

    try:
        stocks_model.ensure_built()
        print("  ensure_built() succeeded")
    except Exception as e:
        print(f"  ensure_built() FAILED: {e}")
        import traceback
        traceback.print_exc()

    check_session_state(spark, "After ensure_built")

    # Step 6: Try to get tickers like ForecastBuilder does
    print_section("Step 6: Get tickers (ForecastBuilder.get_available_tickers)")

    check_session_state(spark, "Before get tickers")

    try:
        # Try get_top_by_market_cap first
        print("Trying stocks_model.get_top_by_market_cap(10)...")
        tickers = stocks_model.get_top_by_market_cap(10)
        print(f"  Got tickers: {tickers}")
    except Exception as e:
        print(f"  get_top_by_market_cap FAILED: {e}")

        # Fallback to list_tickers
        try:
            print("\nTrying stocks_model.list_tickers()...")
            tickers = stocks_model.list_tickers()
            print(f"  Got {len(tickers) if tickers else 0} tickers")
            if tickers:
                print(f"  First 10: {tickers[:10]}")
        except Exception as e2:
            print(f"  list_tickers FAILED: {e2}")
            import traceback
            traceback.print_exc()

    check_session_state(spark, "After get tickers")

    # Step 7: Try to get price data
    print_section("Step 7: Get price data for a ticker")

    try:
        print("Trying stocks_model.get_prices(ticker='AAPL', limit=5)...")
        prices = stocks_model.get_prices(ticker='AAPL', limit=5)
        if prices is not None:
            print(f"  Got prices DataFrame with {prices.count()} rows")
            prices.show()
        else:
            print(f"  get_prices returned None")
    except Exception as e:
        print(f"  get_prices FAILED: {e}")
        import traceback
        traceback.print_exc()

    check_session_state(spark, "Final state")

    print_section("DEBUG COMPLETE")


if __name__ == "__main__":
    main()
