"""
Refresh Market Cap Rankings

Fetches OVERVIEW data for all US-listed tickers to populate market cap
rankings in bronze/securities_reference. Run this before using
--sort-by-market-cap in the pipeline.

Usage:
    python -m scripts.ingest.refresh_market_cap_rankings [options]

Examples:
    # Refresh top 1000 tickers (default)
    python -m scripts.ingest.refresh_market_cap_rankings

    # Refresh top 2000 tickers
    python -m scripts.ingest.refresh_market_cap_rankings --max-tickers 2000

    # Refresh all US tickers (slow - ~10,000 API calls)
    python -m scripts.ingest.refresh_market_cap_rankings --all
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def main():
    parser = argparse.ArgumentParser(
        description="Refresh market cap rankings by fetching OVERVIEW for all tickers"
    )
    parser.add_argument(
        "--max-tickers", type=int, default=1000,
        help="Maximum tickers to refresh (default: 1000)"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Refresh ALL US tickers (slow - thousands of API calls)"
    )
    parser.add_argument(
        "--concurrent", action="store_true",
        help="Use concurrent requests (premium tier only)"
    )
    args = parser.parse_args()

    max_tickers = None if args.all else args.max_tickers

    print("=" * 80)
    print("REFRESH MARKET CAP RANKINGS")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("This script fetches OVERVIEW data for US-listed tickers to populate")
    print("market cap rankings in bronze/securities_reference.")
    print()
    if max_tickers:
        print(f"Max tickers: {max_tickers}")
        print(f"Estimated API calls: {max_tickers} (OVERVIEW) + 1 (LISTING_STATUS)")
        print(f"Estimated time at 1 call/sec: ~{max_tickers // 60} minutes")
    else:
        print("Max tickers: ALL (this will take a long time)")
    print()

    try:
        from core.context import RepoContext
        from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

        print("Initializing context...")
        ctx = RepoContext.from_repo_root(connection_type="spark")
        print("  ✓ Context initialized (Spark mode)")
        print()

        print("Initializing Alpha Vantage ingestor...")
        ingestor = AlphaVantageIngestor(
            alpha_vantage_cfg=ctx.get_api_config('alpha_vantage'),
            storage_cfg=ctx.storage,
            spark=ctx.spark
        )
        print("  ✓ Ingestor initialized")
        print()

        # Run the refresh
        ranked_tickers = ingestor.refresh_market_cap_rankings(
            use_bulk_listing=True,
            max_tickers=max_tickers or 10000,
            show_progress=True
        )

        print()
        print("=" * 80)
        print(f"✓ Market cap rankings refreshed for {len(ranked_tickers)} tickers")
        print()
        print("You can now run the pipeline with market cap sorting:")
        print("  python -m scripts.ingest.run_full_pipeline --max-tickers 500")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
