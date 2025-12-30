#!/usr/bin/env python3
"""
Bronze Ingestion Script.

Fetches data from Alpha Vantage APIs and writes to Bronze layer.
Uses AlphaVantageIngestor for proper API handling and Delta Lake writes.

Usage:
    python -m scripts.ingest.run_bronze_ingestion
    python -m scripts.ingest.run_bronze_ingestion --max-tickers 100
    python -m scripts.ingest.run_bronze_ingestion --endpoints time_series_daily
    python -m scripts.ingest.run_bronze_ingestion --endpoints company_overview,income_statement

Endpoints:
    time_series_daily  - Daily OHLCV prices
    company_overview   - Company overview data
    income_statement   - Income statements
    balance_sheet      - Balance sheets
    cash_flow          - Cash flow statements
    earnings           - Earnings reports
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)

# Endpoint mapping to ingestor methods
ENDPOINT_METHODS = {
    'time_series_daily': 'ingest_prices',
    'prices': 'ingest_prices',
    'company_overview': 'ingest_reference_data',
    'overview': 'ingest_reference_data',
    'income_statement': 'ingest_income_statements',
    'income': 'ingest_income_statements',
    'balance_sheet': 'ingest_balance_sheets',
    'balance': 'ingest_balance_sheets',
    'cash_flow': 'ingest_cash_flows',
    'cashflow': 'ingest_cash_flows',
    'earnings': 'ingest_earnings',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage-path', type=str, default='/shared/storage',
                        help='Storage path')
    parser.add_argument('--max-tickers', type=int, help='Max tickers to process')
    parser.add_argument('--endpoints', type=str, default='time_series_daily',
                        help='Comma-separated endpoints')
    parser.add_argument('--days', type=int, default=None,
                        help='Days of historical data (not currently used - AV returns full history)')

    args = parser.parse_args()
    setup_logging()

    storage_path = Path(args.storage_path)
    endpoints = [e.strip().lower() for e in args.endpoints.split(',')]

    logger.info(f"Starting Bronze ingestion")
    logger.info(f"Storage path: {storage_path}")
    logger.info(f"Endpoints: {endpoints}")
    if args.max_tickers:
        logger.info(f"Max tickers: {args.max_tickers}")

    try:
        # Initialize context and ingestor
        from core.context import RepoContext
        from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

        ctx = RepoContext.from_repo_root(connection_type='spark')

        # Override storage path if provided
        ctx.storage['roots']['bronze'] = str(storage_path / 'bronze')
        ctx.storage['roots']['silver'] = str(storage_path / 'silver')

        ingestor = AlphaVantageIngestor(
            alpha_vantage_cfg=ctx.get_api_config('alpha_vantage'),
            storage_cfg=ctx.storage,
            spark=ctx.spark
        )

        # Get tickers from Bronze securities_reference
        logger.info("Fetching ticker list from securities_reference...")
        from deltalake import DeltaTable
        ref_path = storage_path / 'bronze' / 'securities_reference'

        if not ref_path.exists():
            logger.error(f"No securities_reference at {ref_path}")
            logger.error("Run: python -m scripts.seed.seed_tickers first")
            return 1

        dt = DeltaTable(str(ref_path))
        df = dt.to_pandas()
        tickers = df[df['asset_type'] == 'Stock']['ticker'].unique().tolist()

        if args.max_tickers:
            tickers = tickers[:args.max_tickers]

        logger.info(f"Processing {len(tickers)} tickers")

        # Process each endpoint
        results = {}
        for endpoint in endpoints:
            if endpoint not in ENDPOINT_METHODS:
                logger.warning(f"Unknown endpoint: {endpoint}, skipping")
                continue

            method_name = ENDPOINT_METHODS[endpoint]
            logger.info(f"\n{'='*60}")
            logger.info(f"Ingesting: {endpoint} ({method_name})")
            logger.info(f"{'='*60}")

            try:
                method = getattr(ingestor, method_name)

                if method_name == 'ingest_prices':
                    method(tickers=tickers, date_from=None, date_to=None)
                else:
                    method(tickers=tickers)

                results[endpoint] = 'success'
                logger.info(f"{endpoint}: completed")

            except Exception as e:
                logger.error(f"{endpoint} failed: {e}")
                results[endpoint] = f'error: {e}'

        # Stop Spark
        ctx.spark.stop()

        # Summary
        logger.info("\n" + "="*60)
        logger.info("Ingestion Complete")
        logger.info("="*60)
        for endpoint, status in results.items():
            logger.info(f"  {endpoint}: {status}")

        return 0

    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
