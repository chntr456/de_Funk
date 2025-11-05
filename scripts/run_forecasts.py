"""
Forecast Execution Script

This script orchestrates the execution of time series forecasting models for
stock prices and volumes. It:
1. Refreshes recent data using the ingestion pipeline
2. Loads the forecast model configuration
3. Runs forecasts for specified tickers using multiple model types
4. Stores forecast results and accuracy metrics in the Silver layer

Usage:
    python scripts/run_forecasts.py [--tickers AAPL,GOOGL] [--refresh-days 7] [--models arima_30d,prophet_30d]
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


def load_config(config_path: str) -> dict:
    """Load configuration file (YAML or JSON)."""
    config_path = Path(config_path)

    with open(config_path, 'r') as f:
        if config_path.suffix == '.json':
            return json.load(f)
        else:
            return yaml.safe_load(f)


def get_active_tickers(storage_cfg: dict, limit: int = None) -> list:
    """
    Get list of active tickers from the company Silver layer.

    Args:
        storage_cfg: Storage configuration
        limit: Optional limit on number of tickers

    Returns:
        List of ticker symbols
    """
    import duckdb

    company_root = storage_cfg["roots"].get("company_silver", "storage/silver/company")
    dim_company_path = f"{company_root}/dims/dim_company"

    try:
        con = duckdb.connect(database=':memory:')
        query = f"SELECT DISTINCT ticker FROM read_parquet('{dim_company_path}/**/*.parquet') ORDER BY ticker"

        if limit:
            query += f" LIMIT {limit}"

        df = con.execute(query).fetchdf()
        con.close()

        return df['ticker'].tolist()
    except Exception as e:
        print(f"Warning: Could not load tickers from Silver layer: {e}")
        print("Using default tickers...")
        return ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]


def run_forecast_pipeline(
    tickers: list = None,
    refresh_data: bool = True,
    refresh_days: int = 7,
    models: list = None,
    max_tickers: int = None
) -> dict:
    """
    Run the complete forecast pipeline.

    Args:
        tickers: List of ticker symbols to forecast (None = all active)
        refresh_data: Whether to refresh data before forecasting
        refresh_days: Number of days to refresh
        models: List of model names to run (None = all configured)
        max_tickers: Maximum number of tickers to process

    Returns:
        Dictionary with pipeline results
    """
    print("=" * 80)
    print("TIME SERIES FORECAST PIPELINE")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # Load configurations
    print("Loading configurations...")
    config_root = Path(__file__).parent.parent / "configs"

    storage_cfg = load_config(config_root / "storage.json")
    forecast_cfg = load_config(config_root / "models" / "forecast.yaml")

    print(f"  ✓ Loaded storage config")
    print(f"  ✓ Loaded forecast config")
    print()

    # Step 1: Refresh data if requested
    if refresh_data:
        print("Step 1: Refreshing recent data...")
        print("-" * 80)
        try:
            from scripts.refresh_data import refresh_recent_data
            refresh_recent_data(days=refresh_days, max_tickers=max_tickers)
        except Exception as e:
            print(f"Warning: Data refresh failed: {e}")
            print("Continuing with existing data...")
        print()

    # Step 2: Get tickers to process
    print("Step 2: Determining tickers to forecast...")
    print("-" * 80)

    if tickers is None:
        tickers = get_active_tickers(storage_cfg, limit=max_tickers)

    print(f"  ✓ Processing {len(tickers)} tickers: {', '.join(tickers[:5])}")
    if len(tickers) > 5:
        print(f"    ... and {len(tickers) - 5} more")
    print()

    # Step 3: Initialize forecast model
    print("Step 3: Initializing forecast model...")
    print("-" * 80)

    forecast_model = ForecastModel(
        storage_cfg=storage_cfg,
        model_cfg=forecast_cfg
    )

    print(f"  ✓ Forecast model initialized")
    print(f"  ✓ Output directory: {forecast_model.forecast_root}")
    print()

    # Step 4: Run forecasts for each ticker
    print("Step 4: Running forecasts...")
    print("-" * 80)

    results = {
        'start_time': datetime.now(),
        'tickers_processed': 0,
        'tickers_failed': 0,
        'total_forecasts': 0,
        'total_models': 0,
        'errors': []
    }

    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] Processing {ticker}...")
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

            print(f"  ✓ {ticker}: {ticker_results['models_trained']} models, {ticker_results['forecasts_generated']} forecasts")

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

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run time series forecasts for stock prices and volumes"
    )
    parser.add_argument(
        '--tickers',
        type=str,
        default=None,
        help='Comma-separated list of tickers (default: all active tickers)'
    )
    parser.add_argument(
        '--no-refresh',
        action='store_true',
        help='Skip data refresh step'
    )
    parser.add_argument(
        '--refresh-days',
        type=int,
        default=7,
        help='Number of days to refresh (default: 7)'
    )
    parser.add_argument(
        '--models',
        type=str,
        default=None,
        help='Comma-separated list of model names to run (default: all configured)'
    )
    parser.add_argument(
        '--max-tickers',
        type=int,
        default=None,
        help='Maximum number of tickers to process (default: all)'
    )

    args = parser.parse_args()

    # Parse comma-separated lists
    tickers = args.tickers.split(',') if args.tickers else None
    models = args.models.split(',') if args.models else None

    # Run pipeline
    try:
        results = run_forecast_pipeline(
            tickers=tickers,
            refresh_data=not args.no_refresh,
            refresh_days=args.refresh_days,
            models=models,
            max_tickers=args.max_tickers
        )

        # Exit with error code if there were failures
        if results['tickers_failed'] > 0:
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ Pipeline failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
