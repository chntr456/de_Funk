"""
Refresh Market Cap Data

Fetches OVERVIEW for ALL US tickers to populate market cap in securities_reference.

Usage:
    python -m scripts.ingest.refresh_market_cap_rankings
"""

from __future__ import annotations

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def main():
    print("=" * 80)
    print("REFRESH MARKET CAP DATA")
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
    print("\nFetching ticker list...")
    _, all_tickers, ticker_exchanges = ingestor.ingest_bulk_listing()

    us_exchanges = ["NYSE", "NASDAQ", "NYSEAMERICAN", "NYSEMKT", "BATS", "NYSEARCA"]
    us_tickers = [t for t in all_tickers if ticker_exchanges.get(t) in us_exchanges]
    print(f"Found {len(us_tickers)} US tickers")

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
