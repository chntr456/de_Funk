#!/usr/bin/env python3
"""
Bronze Ingestion Script.

Fetches data from Alpha Vantage APIs and writes to Bronze layer.
Uses AlphaVantageProvider + IngestorEngine for proper API handling and Delta Lake writes.

NOTE: For full pipeline testing, prefer using ./scripts/test/test_pipeline.sh
This script is for standalone Bronze ingestion only.

Usage:
    python -m scripts.ingest.run_bronze_ingestion
    python -m scripts.ingest.run_bronze_ingestion --max-tickers 100
    python -m scripts.ingest.run_bronze_ingestion --endpoints prices
    python -m scripts.ingest.run_bronze_ingestion --endpoints reference,income_statement
    python -m scripts.ingest.run_bronze_ingestion --save-raw --max-tickers 10

Endpoints (work item names):
    prices             - Daily OHLCV prices (time_series_daily_adjusted)
    reference          - Company overview data (company_overview)
    income_statement   - Income statements (income)
    balance_sheet      - Balance sheets (balance)
    cash_flow          - Cash flow statements (cashflow)
    earnings           - Earnings reports

Raw Data Dump:
    Use --save-raw to save raw API responses before transformation.
    Saved to: {storage_path}/raw/alpha_vantage/{endpoint}/{ticker}.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)

# Map user-friendly endpoint names to DataType values used by provider
ENDPOINT_TO_WORK_ITEM = {
    'time_series_daily': 'prices',
    'time_series_daily_adjusted': 'prices',
    'prices': 'prices',
    'company_overview': 'reference',
    'overview': 'reference',
    'reference': 'reference',
    'income_statement': 'income',
    'income': 'income',
    'balance_sheet': 'balance',
    'balance': 'balance',
    'cash_flow': 'cashflow',
    'cashflow': 'cashflow',
    'earnings': 'earnings',
}


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--storage-path', type=str, default='/shared/storage',
                        help='Storage path (default: /shared/storage)')
    parser.add_argument('--max-tickers', type=int, help='Max tickers to process')
    parser.add_argument('--endpoints', type=str, default='prices,reference',
                        help='Comma-separated endpoints (default: prices,reference)')
    parser.add_argument('--use-market-cap', action='store_true',
                        help='Select tickers by market cap instead of alphabetically')
    parser.add_argument('--save-raw', action='store_true',
                        help='Save raw API responses before transformation')
    parser.add_argument('--tickers', type=str,
                        help='Comma-separated list of specific tickers to process')

    args = parser.parse_args()
    setup_logging()

    storage_path = Path(args.storage_path)
    endpoints_input = [e.strip().lower() for e in args.endpoints.split(',')]

    # Resolve endpoint names to work item types
    work_items = []
    for ep in endpoints_input:
        if ep in ENDPOINT_TO_WORK_ITEM:
            work_item = ENDPOINT_TO_WORK_ITEM[ep]
            if work_item not in work_items:
                work_items.append(work_item)
        else:
            logger.warning(f"Unknown endpoint: {ep}, skipping")

    if not work_items:
        logger.error("No valid endpoints specified")
        return 1

    logger.info("Starting Bronze ingestion")
    logger.info(f"Storage path: {storage_path}")
    logger.info(f"Work items: {work_items}")
    if args.max_tickers:
        logger.info(f"Max tickers: {args.max_tickers}")
    if args.save_raw:
        logger.info("Raw data dump ENABLED")

    try:
        # Initialize Spark
        from orchestration.common.spark_session import get_spark
        spark = get_spark(app_name='run_bronze_ingestion')

        # Load storage config
        with open(repo_root / 'configs' / 'storage.json') as f:
            storage_cfg = json.load(f)
        storage_cfg['roots'] = {
            k: str(storage_path / v.replace('storage/', ''))
            for k, v in storage_cfg['roots'].items()
        }

        # Initialize provider (pass storage_path for raw layer when --save-raw)
        from datapipelines.providers.alpha_vantage import create_alpha_vantage_provider
        from datapipelines.base.ingestor_engine import IngestorEngine

        raw_storage = storage_path if args.save_raw else None
        provider = create_alpha_vantage_provider(spark=spark, docs_path=repo_root, storage_path=raw_storage)
        if args.save_raw:
            logger.info(f"Raw data dump path: {storage_path}/raw/alpha_vantage/")

        # Get tickers
        if args.tickers:
            tickers = [t.strip().upper() for t in args.tickers.split(',')]
            logger.info(f"Using {len(tickers)} explicit tickers")
        else:
            tickers = _get_tickers(
                storage_path=storage_path,
                spark=spark,
                max_tickers=args.max_tickers,
                use_market_cap=args.use_market_cap
            )

        if not tickers:
            logger.error("No tickers available. Run seed_tickers first or provide --tickers")
            spark.stop()
            return 1

        logger.info(f"Processing {len(tickers)} tickers")
        provider.set_tickers(tickers)

        # Create engine and run
        engine = IngestorEngine(provider, storage_cfg)
        results = engine.run(work_items=work_items, silent=False)

        spark.stop()

        return 0 if results.total_errors == 0 else 1

    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        return 1


def _get_tickers(
    storage_path: Path,
    spark,
    max_tickers: int = None,
    use_market_cap: bool = False
) -> list:
    """Get tickers from Bronze layer."""

    # Try listing_status first (new path)
    listing_path = storage_path / 'bronze' / 'alpha_vantage' / 'listing_status'
    if not listing_path.exists():
        # Fall back to old path
        listing_path = storage_path / 'bronze' / 'securities_reference'

    if not listing_path.exists():
        logger.error(f"No ticker data at {listing_path}")
        return []

    logger.info(f"Loading tickers from {listing_path}")

    # Read with Spark
    if (listing_path / '_delta_log').exists():
        df = spark.read.format('delta').load(str(listing_path))
    else:
        df = spark.read.parquet(str(listing_path))

    # Filter to stocks
    if 'asset_type' in df.columns:
        df = df.filter(df.asset_type == 'stocks')

    # Get unique tickers
    ticker_rows = df.select('ticker').distinct().collect()
    all_tickers = [row.ticker for row in ticker_rows]

    logger.info(f"Found {len(all_tickers)} unique stock tickers")

    # Sort by market cap if requested
    if use_market_cap and max_tickers:
        sorted_tickers = _sort_by_market_cap(storage_path, spark, max_tickers)
        if sorted_tickers:
            return sorted_tickers
        logger.warning("Market cap ranking unavailable, using alphabetical")

    # Apply limit
    if max_tickers:
        return all_tickers[:max_tickers]

    return all_tickers


def _sort_by_market_cap(storage_path: Path, spark, max_tickers: int) -> list:
    """Sort tickers by market cap."""
    # Try new path first
    company_path = storage_path / 'bronze' / 'alpha_vantage' / 'company_overview'
    if not company_path.exists():
        company_path = storage_path / 'bronze' / 'company_reference'

    if not company_path.exists():
        return []

    try:
        from pyspark.sql.functions import col, desc, isnan

        if (company_path / '_delta_log').exists():
            df = spark.read.format('delta').load(str(company_path))
        else:
            df = spark.read.parquet(str(company_path))

        ranked = (df
                  .filter((col('market_cap').isNotNull()) &
                          (~isnan(col('market_cap'))) &
                          (col('market_cap') > 0))
                  .select('ticker', 'market_cap')
                  .dropDuplicates(['ticker'])
                  .orderBy(desc('market_cap'))
                  .limit(max_tickers))

        rows = ranked.collect()
        tickers = [row.ticker for row in rows]
        logger.info(f"Selected {len(tickers)} tickers by market cap")
        return tickers

    except Exception as e:
        logger.warning(f"Failed to sort by market cap: {e}")
        return []


if __name__ == "__main__":
    sys.exit(main())
