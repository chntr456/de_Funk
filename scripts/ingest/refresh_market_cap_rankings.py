"""
Refresh Market Cap Data

Fetches OVERVIEW for ALL US tickers to populate market cap in securities_reference.

Usage:
    python -m scripts.ingest.refresh_market_cap_rankings
    python -m scripts.ingest.refresh_market_cap_rankings --yes  # Skip confirmation
"""

from __future__ import annotations

import argparse

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def main():
    parser = argparse.ArgumentParser(description="Refresh market cap data for all US tickers")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    print("=" * 80)
    print("REFRESH MARKET CAP DATA (OVERVIEW endpoint)")
    print("=" * 80)

    from core.context import RepoContext
    from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

    ctx = RepoContext.from_repo_root(connection_type="spark")
    ingestor = AlphaVantageIngestor(
        alpha_vantage_cfg=ctx.get_api_config('alpha_vantage'),
        storage_cfg=ctx.storage,
        spark=ctx.spark
    )

    # Get ALL tickers
    print("\nFetching ticker list via LISTING_STATUS...")
    _, all_tickers, ticker_exchanges = ingestor.ingest_bulk_listing()

    us_exchanges = ["NYSE", "NASDAQ", "NYSEAMERICAN", "NYSEMKT", "BATS", "NYSEARCA"]
    us_tickers = [t for t in all_tickers if ticker_exchanges.get(t) in us_exchanges]
    print(f"Found {len(us_tickers)} US tickers")

    # Estimate time
    rate_limit = ingestor.registry.rate_limit  # calls per second
    estimated_seconds = len(us_tickers) / rate_limit
    estimated_minutes = estimated_seconds / 60
    estimated_hours = estimated_minutes / 60

    print(f"\n⏱️  Estimated time: {estimated_hours:.1f} hours ({estimated_minutes:.0f} minutes)")
    print(f"   Rate limit: {rate_limit} calls/sec")
    print(f"   API calls needed: {len(us_tickers)}")

    if not args.yes:
        response = input("\nProceed? (y/n): ").strip().lower()
        if response != 'y':
            print("Aborted.")
            return

    # Fetch OVERVIEW for all
    print(f"\nFetching OVERVIEW for all {len(us_tickers)} tickers...")
    ingestor.ingest_reference_data(tickers=us_tickers, show_progress=True)

    # Show top results
    print("\nTop 20 by market cap:")
    ranked = ingestor.get_tickers_by_market_cap(max_tickers=20)
    for i, t in enumerate(ranked, 1):
        print(f"  {i:3}. {t}")

    print("\n" + "=" * 80)
    print("Done.")
    print("=" * 80)


if __name__ == "__main__":
    main()
