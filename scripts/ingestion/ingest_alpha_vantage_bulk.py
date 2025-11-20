#!/usr/bin/env python3
"""
Alpha Vantage Bulk Ingestion Script

Ingests ALL active tickers from Alpha Vantage with full fundamentals and prices.

This is a dedicated script for Alpha Vantage full-scale ingestion:
  1. LISTING_STATUS (1 API call) → discover ALL active tickers (~8000+)
  2. OVERVIEW per ticker → get CIK + fundamentals (8000+ calls)
  3. TIME_SERIES_DAILY per ticker → get prices (8000+ calls)

Total: ~16,000 API calls @ 75 calls/min (premium) = ~3.5 hours

Usage:
    # Full universe (all active tickers)
    python -m scripts.ingestion.ingest_alpha_vantage_bulk --date-from 2015-01-01

    # Test with limited tickers
    python -m scripts.ingestion.ingest_alpha_vantage_bulk --date-from 2015-01-01 --max-tickers 100

    # Concurrent mode (premium tier only)
    python -m scripts.ingestion.ingest_alpha_vantage_bulk --date-from 2015-01-01 --concurrent

    # Skip if already have ticker list
    python -m scripts.ingestion.ingest_alpha_vantage_bulk --date-from 2015-01-01 --skip-listing
"""

import argparse
import sys
import logging
from datetime import date, timedelta
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest ALL tickers from Alpha Vantage with full fundamentals and prices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--date-from',
        required=True,
        help='Start date for price data (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--date-to',
        help='End date for price data (YYYY-MM-DD, default: yesterday)'
    )

    parser.add_argument(
        '--max-tickers',
        type=int,
        help='Limit number of tickers to ingest (for testing, default: all)'
    )

    parser.add_argument(
        '--concurrent',
        action='store_true',
        help='Use concurrent requests (premium tier only, 75 calls/min)'
    )

    parser.add_argument(
        '--skip-listing',
        action='store_true',
        help='Skip LISTING_STATUS call (assumes reference data already exists)'
    )

    parser.add_argument(
        '--outputsize',
        choices=['compact', 'full'],
        default='full',
        help='Output size for prices: compact (100 days) or full (20+ years)'
    )

    args = parser.parse_args()

    try:
        # Initialize context with Spark (required for data processing)
        logger.info("=" * 80)
        logger.info("ALPHA VANTAGE BULK INGESTION")
        logger.info("=" * 80)
        logger.info("")

        ctx = RepoContext.from_repo_root(connection_type="spark")
        alpha_vantage_cfg = ctx.get_api_config('alpha_vantage')

        # Initialize ingestor
        from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

        ingestor = AlphaVantageIngestor(
            alpha_vantage_cfg=alpha_vantage_cfg,
            storage_cfg=ctx.storage,
            spark=ctx.spark
        )

        # Set date_to to yesterday if not provided
        date_to = args.date_to or (date.today() - timedelta(days=1)).isoformat()

        logger.info(f"Configuration:")
        logger.info(f"  Date range: {args.date_from} to {date_to}")
        logger.info(f"  Max tickers: {args.max_tickers or 'ALL (~8000+)'}")
        logger.info(f"  Concurrent mode: {args.concurrent}")
        logger.info(f"  Output size: {args.outputsize}")
        logger.info(f"  Skip listing: {args.skip_listing}")
        logger.info("")

        # Step 1: Discover all tickers (or skip if already have data)
        if args.skip_listing:
            logger.info("Skipping LISTING_STATUS (using existing reference data)")
            logger.info("Note: This assumes bronze.securities_reference already exists")
            logger.info("")
            # Read existing tickers from bronze
            # TODO: Implement reading from existing bronze data
            logger.error("--skip-listing not yet implemented")
            sys.exit(1)
        else:
            # Use bulk listing mode
            logger.info("Step 1: Discovering ALL active tickers...")
            logger.info("-" * 80)
            tickers = ingestor.run_all(
                date_from=args.date_from,
                date_to=date_to,
                max_tickers=args.max_tickers,
                use_concurrent=args.concurrent,
                use_bulk_listing=True  # This is the key!
            )

        logger.info("")
        logger.info("=" * 80)
        logger.info("INGESTION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total tickers ingested: {len(tickers)}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run build_all_models.py to build silver layer:")
        logger.info("     python -m scripts.build.build_all_models --skip-ingestion")
        logger.info("")

        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("\nIngestion interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
