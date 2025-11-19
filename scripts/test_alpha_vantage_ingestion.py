#!/usr/bin/env python3
"""
Alpha Vantage Ingestion Test Script

This script tests the Alpha Vantage provider integration by ingesting
reference data and prices for a small set of tickers.

Usage:
    python -m scripts.test_alpha_vantage_ingestion

    # Or with custom tickers:
    python -m scripts.test_alpha_vantage_ingestion --tickers AAPL MSFT GOOGL

Requirements:
    - Set ALPHA_VANTAGE_API_KEYS in .env file
    - Free tier: 25 requests/day, 5 requests/minute
    - Get free key at: https://www.alphavantage.co/support/#api-key
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Setup repo imports
from utils.repo import setup_repo_imports
setup_repo_imports()

from config import ConfigLoader
from pyspark.sql import SparkSession


def check_api_key(config):
    """Check if Alpha Vantage API key is configured."""
    alpha_vantage_cfg = config.apis.get('alpha_vantage', {})
    api_keys = alpha_vantage_cfg.get('credentials', {}).get('api_keys', [])

    if not api_keys:
        print("❌ ERROR: No Alpha Vantage API key found!")
        print("\nTo fix this:")
        print("1. Get a free API key: https://www.alphavantage.co/support/#api-key")
        print("2. Add to .env file:")
        print("   ALPHA_VANTAGE_API_KEYS=your_api_key_here")
        print()
        return False

    print(f"✓ Found {len(api_keys)} Alpha Vantage API key(s)")
    return True


def create_spark_session():
    """Create Spark session for ingestion."""
    print("\n📊 Creating Spark session...")

    spark = (SparkSession.builder
             .appName("AlphaVantage_Test_Ingestion")
             .config("spark.driver.memory", "4g")
             .config("spark.sql.shuffle.partitions", "10")
             .getOrCreate())

    print(f"✓ Spark session created (version {spark.version})")
    return spark


def test_reference_data_ingestion(ingestor, tickers, output_dir):
    """Test ingesting reference data (company overview)."""
    print(f"\n{'='*60}")
    print("📋 STEP 1: Ingesting Reference Data (Company Overview)")
    print(f"{'='*60}")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Endpoint: Alpha Vantage OVERVIEW")
    print(f"Rate Limit: 5 calls/minute (free tier)")
    print()

    try:
        table_path = ingestor.ingest_reference_data(
            tickers=tickers,
            use_concurrent=False  # Sequential for free tier
        )

        print(f"\n✅ SUCCESS: Reference data written to:")
        print(f"   {table_path}")
        print()

        # Show sample data
        print("Sample data (first 3 rows):")
        df = ingestor.spark.read.parquet(table_path)
        df.select("ticker", "security_name", "asset_type", "sector", "market_cap", "pe_ratio").show(3, truncate=False)

        return True

    except Exception as e:
        print(f"\n❌ ERROR: Reference data ingestion failed!")
        print(f"   {type(e).__name__}: {e}")
        return False


def test_prices_ingestion(ingestor, tickers, date_from, date_to, output_dir):
    """Test ingesting daily prices."""
    print(f"\n{'='*60}")
    print("📈 STEP 2: Ingesting Daily Prices")
    print(f"{'='*60}")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Date Range: {date_from} to {date_to}")
    print(f"Endpoint: Alpha Vantage TIME_SERIES_DAILY_ADJUSTED")
    print(f"Rate Limit: 5 calls/minute (free tier)")
    print()

    try:
        table_path = ingestor.ingest_prices(
            tickers=tickers,
            date_from=date_from,
            date_to=date_to,
            adjusted=True,
            outputsize='full',  # Full history
            use_concurrent=False  # Sequential for free tier
        )

        print(f"\n✅ SUCCESS: Prices written to:")
        print(f"   {table_path}")
        print()

        # Show sample data
        print("Sample data (first 5 rows):")
        df = ingestor.spark.read.parquet(table_path)
        df.select("ticker", "trade_date", "open", "high", "low", "close", "volume", "adjusted_close").show(5, truncate=False)

        # Show summary stats
        print("\nData Summary:")
        print(f"  Total rows: {df.count()}")
        print(f"  Date range: {df.agg({'trade_date': 'min'}).collect()[0][0]} to {df.agg({'trade_date': 'max'}).collect()[0][0]}")
        print(f"  Tickers: {df.select('ticker').distinct().count()}")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: Prices ingestion failed!")
        print(f"   {type(e).__name__}: {e}")
        return False


def main():
    """Main test execution."""
    parser = argparse.ArgumentParser(
        description='Test Alpha Vantage data ingestion',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--tickers',
        nargs='+',
        default=['AAPL', 'MSFT'],
        help='Ticker symbols to fetch (default: AAPL MSFT)'
    )
    parser.add_argument(
        '--days-back',
        type=int,
        default=90,
        help='Number of days of history to fetch (default: 90)'
    )
    parser.add_argument(
        '--skip-reference',
        action='store_true',
        help='Skip reference data ingestion (only prices)'
    )
    parser.add_argument(
        '--skip-prices',
        action='store_true',
        help='Skip prices ingestion (only reference)'
    )

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("🚀 Alpha Vantage Ingestion Test")
    print(f"{'='*60}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Calculate date range
    date_to = datetime.now().strftime('%Y-%m-%d')
    date_from = (datetime.now() - timedelta(days=args.days_back)).strftime('%Y-%m-%d')

    # Load configuration
    print("⚙️  Loading configuration...")
    try:
        loader = ConfigLoader()
        config = loader.load()
        print(f"✓ Configuration loaded")
        print(f"  Repo root: {config.repo_root}")
        print(f"  Bronze path: {config.storage.get('roots', {}).get('bronze', 'storage/bronze')}")
    except Exception as e:
        print(f"❌ ERROR: Failed to load configuration: {e}")
        return 1

    # Check API key
    if not check_api_key(config):
        return 1

    # Create Spark session
    try:
        spark = create_spark_session()
    except Exception as e:
        print(f"❌ ERROR: Failed to create Spark session: {e}")
        return 1

    # Initialize Alpha Vantage ingestor
    print("\n🔌 Initializing Alpha Vantage ingestor...")
    try:
        from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

        ingestor = AlphaVantageIngestor(
            alpha_vantage_cfg=config.apis.get('alpha_vantage', {}),
            storage_cfg=config.storage,
            spark=spark
        )
        print("✓ Ingestor initialized")
        print(f"  Rate limit: {ingestor.registry.rate_limit} calls/sec")
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize ingestor: {e}")
        spark.stop()
        return 1

    # Determine output directory
    bronze_root = config.storage.get('roots', {}).get('bronze', 'storage/bronze')
    output_dir = Path(config.repo_root) / bronze_root

    # Run ingestion tests
    success = True

    if not args.skip_reference:
        if not test_reference_data_ingestion(ingestor, args.tickers, output_dir):
            success = False

    if not args.skip_prices:
        if not test_prices_ingestion(ingestor, args.tickers, date_from, date_to, output_dir):
            success = False

    # Cleanup
    print(f"\n{'='*60}")
    print("🧹 Cleaning up...")
    spark.stop()
    print("✓ Spark session stopped")

    # Final summary
    print(f"\n{'='*60}")
    if success:
        print("✅ ALL TESTS PASSED")
        print(f"{'='*60}")
        print("\n📁 Bronze Data Location:")
        print(f"   {output_dir}")
        print("\n📝 Next Steps:")
        print("   1. Build silver models: python -m scripts.rebuild_model --model stocks")
        print("   2. Query data: python -m scripts.query_stocks")
        print("   3. Test Python measures: model.calculate_measure('sharpe_ratio', ticker='AAPL')")
    else:
        print("❌ SOME TESTS FAILED")
        print(f"{'='*60}")
        print("\n🔍 Troubleshooting:")
        print("   - Check API key is valid")
        print("   - Verify rate limit not exceeded (5 calls/min for free tier)")
        print("   - Check network connectivity")
        print("   - Review error messages above")
    print()

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
