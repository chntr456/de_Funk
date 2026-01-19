#!/usr/bin/env python
"""
Debug script to isolate the Spark session issue when reading stocks from forecast.

This replicates exactly what ForecastBuilder does - nothing more.

Usage:
    spark-submit --packages io.delta:delta-spark_2.13:4.0.0 scripts/debug/debug_forecast_read.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add repo to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))


def main():
    print("=" * 60)
    print("DEBUG: Replicate ForecastBuilder._get_stocks_model()")
    print("=" * 60)

    # Step 1: Get Spark session (same as ForecastBuilder)
    print("\n[1] Getting Spark session...")
    from orchestration.common.spark_session import get_spark
    spark = get_spark()
    print(f"    Got: {spark}")

    # Step 2: Create connection wrapper (same as ForecastBuilder)
    print("\n[2] Creating SparkConnection...")
    from core.connection import get_spark_connection
    connection = get_spark_connection(spark)
    print(f"    Got: {connection}")

    # Step 3: Load storage config (same as ForecastBuilder)
    print("\n[3] Loading storage config...")
    storage_root = Path("/shared/storage")
    if not storage_root.exists():
        storage_root = repo_root / "storage"

    # This matches what build_models.py passes to builders
    storage_cfg = {
        'root': str(storage_root),
        'silver_root': str(storage_root / 'silver'),
        'bronze_root': str(storage_root / 'bronze'),
    }
    print(f"    storage_cfg: {storage_cfg}")

    # Step 4: Load model config (same as ForecastBuilder)
    print("\n[4] Loading stocks model config...")
    from config.domain_loader import ModelConfigLoader
    domains_dir = repo_root / "domains"
    loader = ModelConfigLoader(domains_dir)
    stocks_config = loader.load_model_config("stocks")
    print(f"    Config keys: {list(stocks_config.keys()) if stocks_config else 'NONE'}")

    # Step 5: Create StocksModel (same as ForecastBuilder._get_stocks_model)
    print("\n[5] Creating StocksModel...")
    from models.domains.securities.stocks.model import StocksModel
    stocks_model = StocksModel(
        connection=connection,
        storage_cfg=storage_cfg,
        model_cfg=stocks_config,
        params={},
        repo_root=repo_root
    )
    print(f"    Created: {stocks_model}")
    print(f"    model_name: {stocks_model.model_name}")
    print(f"    backend: {stocks_model.backend}")

    # Step 6: Call ensure_built (this is what triggers the reads)
    print("\n[6] Calling stocks_model.ensure_built()...")
    try:
        stocks_model.ensure_built()
        print("    SUCCESS")
    except Exception as e:
        print(f"    FAILED: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 7: Get tickers (same as ForecastBuilder.get_available_tickers)
    print("\n[7] Calling stocks_model.get_top_by_market_cap(10)...")
    try:
        tickers = stocks_model.get_top_by_market_cap(10)
        if hasattr(tickers, 'collect'):
            ticker_list = [r.ticker for r in tickers.select("ticker").collect()]
        else:
            ticker_list = tickers["ticker"].tolist() if hasattr(tickers, "__getitem__") else list(tickers)
        print(f"    Got tickers: {ticker_list}")
    except Exception as e:
        print(f"    FAILED: {e}")
        import traceback
        traceback.print_exc()

        # Fallback like ForecastBuilder does
        print("\n[7b] Fallback: stocks_model.list_tickers()...")
        try:
            tickers = stocks_model.list_tickers(active_only=False)
            print(f"    Got {len(tickers)} tickers: {tickers[:10]}")
        except Exception as e2:
            print(f"    FAILED: {e2}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("DEBUG COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
