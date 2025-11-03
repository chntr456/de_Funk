"""
Data Refresh Script

This script runs the data ingestion pipeline to refresh the most recent data
before executing forecast models. It ensures that the latest price and volume
data is available for forecasting.

Usage:
    python scripts/refresh_data.py [--days DAYS] [--max-tickers N]
"""

from __future__ import annotations
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from src.orchestration.context import RepoContext
from src.orchestration.orchestrator import Orchestrator


def refresh_recent_data(days: int = 7, max_tickers: int = None) -> None:
    """
    Refresh the most recent data from Polygon API.

    Args:
        days: Number of recent days to refresh (default: 7)
        max_tickers: Optional limit on number of tickers to process
    """
    # Calculate date range
    date_to = datetime.now().date()
    date_from = date_to - timedelta(days=days)

    print("=" * 80)
    print("DATA REFRESH PIPELINE")
    print("=" * 80)
    print(f"Date range: {date_from} to {date_to}")
    print(f"Days to refresh: {days}")
    if max_tickers:
        print(f"Max tickers: {max_tickers}")
    print("=" * 80)
    print()

    # Build context (repo paths, configs, spark)
    print("Initializing context...")
    ctx = RepoContext.from_repo_root()

    # Run ingestion pipeline
    print("Running ingestion pipeline...")
    orchestrator = Orchestrator(ctx)

    try:
        final_df = orchestrator.run_company_pipeline(
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            max_tickers=max_tickers,
            include_news=False  # Skip news for faster refresh
        )

        print()
        print("=" * 80)
        print("✓ Data refresh completed successfully!")
        print("=" * 80)
        print()
        print("Sample of refreshed data:")
        final_df.show(10, truncate=False)

        # Count records
        record_count = final_df.count()
        print(f"\nTotal records: {record_count:,}")

    except Exception as e:
        print()
        print("=" * 80)
        print("✗ Data refresh failed!")
        print("=" * 80)
        print(f"Error: {str(e)}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Refresh recent data from Polygon API"
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of recent days to refresh (default: 7)'
    )
    parser.add_argument(
        '--max-tickers',
        type=int,
        default=None,
        help='Maximum number of tickers to process (default: all active)'
    )

    args = parser.parse_args()

    refresh_recent_data(days=args.days, max_tickers=args.max_tickers)


if __name__ == "__main__":
    main()
