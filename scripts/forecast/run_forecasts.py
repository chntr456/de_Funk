"""
Forecast Execution Script

This script orchestrates the execution of time series forecasting models for
stock prices and volumes. It:
1. Refreshes recent data using the ingestion pipeline
2. Loads the forecast model configuration
3. Runs forecasts for specified tickers using multiple model types
4. Stores forecast results and accuracy metrics in the Silver layer

Usage:
    python -m scripts.forecast.run_forecasts [--tickers AAPL,GOOGL] [--refresh-days 7] [--models arima_30d,prophet_30d]
"""
from __future__ import annotations

import sys
from pathlib import Path
import argparse
from datetime import datetime
import yaml
import json
import traceback

from utils.repo import setup_repo_imports, get_repo_root
repo_root = setup_repo_imports()

from config.logging import get_logger, setup_logging
from models.implemented.forecast import ForecastModel
from models.api.session import UniversalSession

logger = get_logger(__name__)


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
    Get list of active tickers from the stocks Silver layer.

    Falls back to bronze layer if silver not available.

    Args:
        storage_cfg: Storage configuration
        limit: Optional limit on number of tickers

    Returns:
        List of ticker symbols
    """
    from pathlib import Path
    import pyarrow.dataset as ds

    # Try stocks Silver layer first
    stocks_root = storage_cfg["roots"].get("stocks_silver", "storage/silver/stocks")
    dim_stock_path = Path(stocks_root) / "dims" / "dim_stock"

    if dim_stock_path.exists():
        try:
            dataset = ds.dataset(dim_stock_path, format='parquet')
            table = dataset.to_table(columns=['ticker'])
            tickers = table.column('ticker').unique().to_pylist()

            if limit:
                tickers = tickers[:limit]

            logger.info(f"Loaded {len(tickers)} tickers from stocks Silver layer")
            return tickers
        except Exception as e:
            logger.warning(f"Could not load tickers from stocks Silver: {e}")

    # Fallback: Bronze prices_daily
    bronze_root = storage_cfg["roots"].get("bronze", "storage/bronze")
    prices_path = Path(bronze_root) / "prices_daily"

    if prices_path.exists():
        try:
            dataset = ds.dataset(prices_path, format='parquet')
            table = dataset.to_table(columns=['ticker'])
            tickers = table.column('ticker').unique().to_pylist()

            if limit:
                tickers = tickers[:limit]

            logger.info(f"Loaded {len(tickers)} tickers from Bronze layer")
            return tickers
        except Exception as e:
            logger.warning(f"Could not load tickers from Bronze layer: {e}")

    # Return empty list if no data sources available
    logger.warning("No ticker data sources available")
    return []


def print_header(text: str, char: str = "=") -> None:
    """Print a formatted header line."""
    line = char * 80
    print(line)
    print(text)
    print(line)


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
    print_header("TIME SERIES FORECAST PIPELINE")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    logger.info("Starting time series forecast pipeline")

    # Initialize Spark connection (required for ETL operations)
    from orchestration.common.spark_session import get_spark
    from core.connection import ConnectionFactory
    spark_session = get_spark("ForecastPipeline")
    spark = ConnectionFactory.create("spark", spark_session=spark_session)

    # Load configurations
    print("Loading configurations...")
    config_root = get_repo_root() / "configs"

    storage_cfg = load_config(config_root / "storage.json")
    forecast_cfg = load_config(config_root / "models" / "forecast.yaml")

    logger.debug("Configurations loaded")
    print(f"  Loaded storage config")
    print(f"  Loaded forecast config")
    print()

    # Step 1: Refresh data if requested
    if refresh_data:
        print("Step 1: Refreshing recent data...")
        print("-" * 80)
        logger.info(f"Refreshing data for {refresh_days} days")
        try:
            from scripts.refresh_data import refresh_recent_data
            refresh_recent_data(days=refresh_days, max_tickers=max_tickers)
        except Exception as e:
            logger.warning(f"Data refresh failed: {e}")
            print(f"Warning: Data refresh failed: {e}")
            print("Continuing with existing data...")
        print()

    # Step 2: Get tickers to process
    print("Step 2: Determining tickers to forecast...")
    print("-" * 80)

    if tickers is None:
        tickers = get_active_tickers(storage_cfg, limit=max_tickers)

    logger.info(f"Processing {len(tickers)} tickers")
    print(f"  Processing {len(tickers)} tickers: {', '.join(tickers[:5])}")
    if len(tickers) > 5:
        print(f"    ... and {len(tickers) - 5} more")
    print()

    # Step 3: Initialize forecast model
    print("Step 3: Initializing forecast model...")
    print("-" * 80)

    # Create universal session for cross-model access
    repo_root_path = get_repo_root()
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root_path
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

    logger.info(f"Forecast model initialized, output: {forecast_root}")
    print(f"  Forecast model initialized")
    print(f"  Session configured for cross-model access")
    print(f"  Output directory: {forecast_root}")
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
        logger.debug(f"Processing ticker {i}/{len(tickers)}: {ticker}")

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

            print(f"  {ticker}: {ticker_results['models_trained']} models, {ticker_results['forecasts_generated']} forecasts")
            logger.info(f"{ticker}: {ticker_results['models_trained']} models, {ticker_results['forecasts_generated']} forecasts")

        except Exception as e:
            error_msg = f"{ticker}: {str(e)}"
            logger.error(f"Forecast failed for {ticker}: {e}")
            print(f"  Error: {error_msg}")
            results['tickers_failed'] += 1
            results['errors'].append(error_msg)

    results['end_time'] = datetime.now()
    results['duration'] = (results['end_time'] - results['start_time']).total_seconds()

    # Step 5: Print summary
    print()
    print_header("FORECAST PIPELINE SUMMARY")
    print(f"Duration: {results['duration']:.1f} seconds")
    print(f"Tickers processed: {results['tickers_processed']}/{len(tickers)}")
    print(f"Tickers failed: {results['tickers_failed']}")
    print(f"Total models trained: {results['total_models']}")
    print(f"Total forecasts generated: {results['total_forecasts']}")

    logger.info(f"Pipeline complete: {results['tickers_processed']}/{len(tickers)} tickers, "
               f"{results['total_forecasts']} forecasts in {results['duration']:.1f}s")

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
    logger.debug("Spark session stopped")

    return results


def main():
    setup_logging()

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
    logger.info(f"Starting forecast script with args: {args}")

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

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"\nPipeline failed with error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
