#!/usr/bin/env python3
"""
Forecast Execution Script for Large Cap Companies

This script runs time series forecasts only for companies above a specified
market cap threshold. It:
1. Loads recent price data from Silver layer
2. Calculates market cap as (close price × volume) for most recent trade date
3. Filters companies above the market cap threshold (default: $100M)
4. Runs forecasts for filtered tickers using configured model types

Market Cap Calculation:
    Market Cap ≈ Close Price × Volume
    (This is a proxy - true market cap = shares outstanding × share price)

Usage:
    # Run for companies > $100M market cap (default)
    python scripts/run_forecasts_large_cap.py

    # Run for companies > $500M market cap
    python scripts/run_forecasts_large_cap.py --min-market-cap 500000000

    # Run for companies > $1B market cap, specific models only
    python scripts/run_forecasts_large_cap.py --min-market-cap 1000000000 --models arima_30d,prophet_30d

    # Dry run - show which companies would be processed
    python scripts/run_forecasts_large_cap.py --dry-run
"""

from __future__ import annotations
import argparse
import sys
from datetime import datetime
from pathlib import Path
import yaml
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.implemented.forecast.model import ForecastModel
from models.base.session import UniversalSession


def load_config(config_path: str) -> dict:
    """Load configuration file (YAML or JSON)."""
    config_path = Path(config_path)

    with open(config_path, 'r') as f:
        if config_path.suffix == '.json':
            return json.load(f)
        else:
            return yaml.safe_load(f)


def get_large_cap_tickers(
    storage_cfg: dict,
    min_market_cap: float = 100_000_000,  # $100M default
    lookback_days: int = 30
) -> list[tuple[str, float]]:
    """
    Get list of tickers with market cap above threshold.

    Market cap is calculated as: close_price × volume (proxy for true market cap)
    Uses the most recent trade date available in the data.

    Args:
        storage_cfg: Storage configuration
        min_market_cap: Minimum market cap in dollars (default: $100M)
        lookback_days: Number of days to look back for price data

    Returns:
        List of tuples: (ticker, market_cap) sorted by market cap descending
    """
    import duckdb

    company_root = storage_cfg["roots"].get("company_silver", "storage/silver/company")
    fact_prices_path = f"{company_root}/facts/fact_prices"

    try:
        con = duckdb.connect(database=':memory:')

        # Query to calculate market cap from most recent trade date
        # Market Cap ≈ Close Price × Volume (proxy calculation)
        query = f"""
        WITH latest_prices AS (
            -- Get most recent trade date per ticker
            SELECT
                ticker,
                trade_date,
                close,
                volume,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date DESC) as rn
            FROM read_parquet('{fact_prices_path}/**/*.parquet')
            WHERE close IS NOT NULL
              AND volume IS NOT NULL
              AND volume > 0
        ),
        market_caps AS (
            SELECT
                ticker,
                trade_date,
                close,
                volume,
                (close * volume) as market_cap
            FROM latest_prices
            WHERE rn = 1
        )
        SELECT
            ticker,
            market_cap,
            close as latest_close,
            volume as latest_volume,
            trade_date as latest_trade_date
        FROM market_caps
        WHERE market_cap >= {min_market_cap}
        ORDER BY market_cap DESC
        """

        df = con.execute(query).fetchdf()
        con.close()

        if df.empty:
            print(f"⚠️  Warning: No companies found with market cap >= ${min_market_cap:,.0f}")
            return []

        # Return list of (ticker, market_cap) tuples
        result = list(zip(df['ticker'].tolist(), df['market_cap'].tolist()))

        return result

    except Exception as e:
        print(f"✗ Error loading tickers: {e}")
        import traceback
        traceback.print_exc()
        return []


def format_market_cap(market_cap: float) -> str:
    """Format market cap in human-readable format (e.g., $1.5B)."""
    if market_cap >= 1_000_000_000:
        return f"${market_cap / 1_000_000_000:.2f}B"
    elif market_cap >= 1_000_000:
        return f"${market_cap / 1_000_000:.2f}M"
    elif market_cap >= 1_000:
        return f"${market_cap / 1_000:.2f}K"
    else:
        return f"${market_cap:.2f}"


def run_forecast_pipeline(
    min_market_cap: float = 100_000_000,
    models: list = None,
    dry_run: bool = False,
    refresh_data: bool = False,
    refresh_days: int = 7
) -> dict:
    """
    Run forecast pipeline for large cap companies only.

    Args:
        min_market_cap: Minimum market cap threshold in dollars
        models: List of model names to run (None = all configured)
        dry_run: If True, show which companies would be processed without running forecasts
        refresh_data: Whether to refresh data before forecasting
        refresh_days: Number of days to refresh

    Returns:
        Dictionary with pipeline results
    """
    print("=" * 80)
    print("LARGE CAP FORECAST PIPELINE")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Market cap threshold: {format_market_cap(min_market_cap)}")
    if dry_run:
        print("Mode: DRY RUN (no forecasts will be generated)")
    print("=" * 80)
    print()

    # Initialize Spark
    from orchestration.common.spark_session import get_spark
    spark = get_spark("LargeCapForecastPipeline")

    # Load configurations
    print("Loading configurations...")
    config_root = Path(__file__).parent.parent / "configs"

    storage_cfg = load_config(config_root / "storage.json")
    forecast_cfg = load_config(config_root / "models" / "forecast.yaml")

    print(f"  ✓ Loaded storage config")
    print(f"  ✓ Loaded forecast config")
    print()

    # Step 1: Get large cap tickers
    print("Step 1: Identifying large cap companies...")
    print("-" * 80)

    ticker_data = get_large_cap_tickers(storage_cfg, min_market_cap)

    if not ticker_data:
        print("✗ No companies found matching criteria. Exiting.")
        return {
            'tickers_processed': 0,
            'tickers_failed': 0,
            'total_forecasts': 0,
            'total_models': 0,
            'errors': []
        }

    tickers = [t[0] for t in ticker_data]
    market_caps = {t[0]: t[1] for t in ticker_data}

    print(f"  ✓ Found {len(tickers)} companies above {format_market_cap(min_market_cap)}")
    print()
    print("  Top 10 companies by market cap:")
    for i, (ticker, mcap) in enumerate(ticker_data[:10], 1):
        print(f"    {i:2}. {ticker:6} - {format_market_cap(mcap)}")
    if len(ticker_data) > 10:
        print(f"    ... and {len(ticker_data) - 10} more")
    print()

    if dry_run:
        print("=" * 80)
        print("DRY RUN COMPLETE")
        print("=" * 80)
        print(f"Would process {len(tickers)} companies for forecasting")
        print("\nRun without --dry-run to execute forecasts")
        return {
            'tickers_processed': 0,
            'tickers_failed': 0,
            'total_forecasts': 0,
            'total_models': 0,
            'errors': [],
            'dry_run': True,
            'tickers_identified': len(tickers)
        }

    # Step 2: Refresh data if requested
    if refresh_data:
        print("Step 2: Refreshing recent data...")
        print("-" * 80)
        try:
            from scripts.refresh_data import refresh_recent_data
            refresh_recent_data(days=refresh_days, max_tickers=None)
        except Exception as e:
            print(f"⚠️  Warning: Data refresh failed: {e}")
            print("Continuing with existing data...")
        print()

    # Step 3: Initialize forecast model
    print(f"Step {3 if refresh_data else 2}: Initializing forecast model...")
    print("-" * 80)

    # Create universal session for cross-model access
    repo_root = Path(__file__).parent.parent
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root
    )

    forecast_model = ForecastModel(
        connection=spark,
        storage_cfg=storage_cfg,
        model_cfg=forecast_cfg,
        params={}
    )

    # Set session for cross-model data access
    forecast_model.set_session(session)

    # Get output directory from storage config
    forecast_root = storage_cfg['roots'].get('forecast_silver', 'storage/silver/forecast')

    print(f"  ✓ Forecast model initialized")
    print(f"  ✓ Session configured for cross-model access")
    print(f"  ✓ Output directory: {forecast_root}")
    print()

    # Step 4: Run forecasts for each ticker
    print(f"Step {4 if refresh_data else 3}: Running forecasts...")
    print("-" * 80)

    results = {
        'start_time': datetime.now(),
        'tickers_processed': 0,
        'tickers_failed': 0,
        'total_forecasts': 0,
        'total_models': 0,
        'errors': [],
        'min_market_cap': min_market_cap,
        'total_market_cap': sum(market_caps.values())
    }

    for i, ticker in enumerate(tickers, 1):
        mcap = market_caps[ticker]
        print(f"\n[{i}/{len(tickers)}] Processing {ticker} ({format_market_cap(mcap)})...")
        print("-" * 40)

        try:
            ticker_results = forecast_model.run_forecast_for_ticker(
                ticker=ticker,
                model_configs=models
            )

            results['tickers_processed'] += 1
            results['total_forecasts'] += ticker_results['forecasts_generated']
            results['total_models'] += ticker_results['models_trained']

            if ticker_results['errors']:
                results['errors'].extend(ticker_results['errors'])

            print(f"  ✓ {ticker}: {ticker_results['models_trained']} models, "
                  f"{ticker_results['forecasts_generated']} forecasts")

        except Exception as e:
            error_msg = f"{ticker}: {str(e)}"
            print(f"  ✗ {error_msg}")
            results['tickers_failed'] += 1
            results['errors'].append(error_msg)

    results['end_time'] = datetime.now()
    results['duration'] = (results['end_time'] - results['start_time']).total_seconds()

    # Step 5: Print summary
    print()
    print("=" * 80)
    print("FORECAST PIPELINE SUMMARY")
    print("=" * 80)
    print(f"Market cap threshold: {format_market_cap(min_market_cap)}")
    print(f"Total market cap coverage: {format_market_cap(results['total_market_cap'])}")
    print(f"Duration: {results['duration']:.1f} seconds")
    print(f"Tickers processed: {results['tickers_processed']}/{len(tickers)}")
    print(f"Tickers failed: {results['tickers_failed']}")
    print(f"Total models trained: {results['total_models']}")
    print(f"Total forecasts generated: {results['total_forecasts']}")

    if results['errors']:
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results['errors'][:10]:  # Show first 10
            print(f"  - {error}")
        if len(results['errors']) > 10:
            print(f"  ... and {len(results['errors']) - 10} more")

    print("=" * 80)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Clean up
    spark.stop()

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run time series forecasts for large cap companies only",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run for companies > $100M (default)
  python scripts/run_forecasts_large_cap.py

  # Run for companies > $500M
  python scripts/run_forecasts_large_cap.py --min-market-cap 500000000

  # Run for companies > $1B with specific models
  python scripts/run_forecasts_large_cap.py --min-market-cap 1000000000 --models arima_30d,prophet_30d

  # Dry run to see which companies would be processed
  python scripts/run_forecasts_large_cap.py --dry-run

  # Common market cap thresholds:
  #   $100M   = 100000000  (Small Cap)
  #   $500M   = 500000000
  #   $1B     = 1000000000 (Mid Cap)
  #   $10B    = 10000000000 (Large Cap)
  #   $200B   = 200000000000 (Mega Cap)
        """
    )
    parser.add_argument(
        '--min-market-cap',
        type=float,
        default=100_000_000,
        help='Minimum market cap in dollars (default: 100,000,000 = $100M)'
    )
    parser.add_argument(
        '--models',
        type=str,
        default=None,
        help='Comma-separated list of model names to run (default: all configured)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show which companies would be processed without running forecasts'
    )
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Refresh data before running forecasts'
    )
    parser.add_argument(
        '--refresh-days',
        type=int,
        default=7,
        help='Number of days to refresh (default: 7)'
    )

    args = parser.parse_args()

    # Parse comma-separated model list
    models = args.models.split(',') if args.models else None

    # Run pipeline
    try:
        results = run_forecast_pipeline(
            min_market_cap=args.min_market_cap,
            models=models,
            dry_run=args.dry_run,
            refresh_data=args.refresh,
            refresh_days=args.refresh_days
        )

        # Exit with error code if there were failures (but not for dry run)
        if not results.get('dry_run', False) and results['tickers_failed'] > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Pipeline failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
