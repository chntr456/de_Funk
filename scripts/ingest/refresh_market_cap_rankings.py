"""
Refresh Market Cap Data

Fetches OVERVIEW for ALL US tickers to populate market cap in securities_reference.
This is expensive (~10,000 API calls) but necessary to know true rankings.

Usage:
    python -m scripts.ingest.refresh_market_cap_rankings
"""

from __future__ import annotations

import sys
from datetime import datetime

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def main():
    print("=" * 80)
    print("REFRESH MARKET CAP DATA (ALL TICKERS)")
    print("=" * 80)
    print()

    from core.context import RepoContext
    from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

    ctx = RepoContext.from_repo_root(connection_type="spark")
    ingestor = AlphaVantageIngestor(
        alpha_vantage_cfg=ctx.get_api_config('alpha_vantage'),
        storage_cfg=ctx.storage,
        spark=ctx.spark
    )

    # Get ALL tickers from LISTING_STATUS
    print("Step 1: Fetching ALL tickers from LISTING_STATUS...")
    _, all_tickers, ticker_exchanges = ingestor.ingest_bulk_listing()

    us_exchanges = ["NYSE", "NASDAQ", "NYSEAMERICAN", "NYSEMKT", "BATS", "NYSEARCA"]
    us_tickers = [t for t in all_tickers if ticker_exchanges.get(t) in us_exchanges]
    print(f"  Found {len(us_tickers)} US tickers")
    print()
    print(f"This will make {len(us_tickers)} OVERVIEW API calls.")
    print(f"Estimated time: ~{len(us_tickers) // 60} minutes at 1 call/sec")
    print()

    confirm = input("Continue? [y/N]: ")
    if confirm.lower() != 'y':
        print("Aborted.")
        sys.exit(0)

    # Fetch OVERVIEW for ALL
    print(f"\nStep 2: Fetching OVERVIEW for {len(us_tickers)} tickers...")
    ingestor.ingest_reference_data(tickers=us_tickers, show_progress=True)

    # Show results
    print(f"\nStep 3: Checking results...")
    ranked = ingestor.get_tickers_by_market_cap(max_tickers=100)
    print(f"\nTop 20 by market cap:")
    for i, t in enumerate(ranked[:20], 1):
        print(f"  {i:3}. {t}")

    print()
    print("=" * 80)
    print("Done. Market cap data populated in bronze/securities_reference")
    print("Now run: python -m scripts.ingest.run_full_pipeline --max-tickers 500")
    print("=" * 80)


if __name__ == "__main__":
    main()
