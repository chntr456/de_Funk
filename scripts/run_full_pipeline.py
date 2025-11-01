"""
Full Pipeline Orchestrator

This script runs the complete end-to-end pipeline:
1. Data Ingestion: Polygon API → Bronze → Silver layer
2. Forecasting: Generate time series forecasts for all tickers

Usage:
    python scripts/run_full_pipeline.py [options]

Examples:
    # Run full pipeline for last 30 days, all tickers
    python scripts/run_full_pipeline.py --days 30

    # Run for specific date range with ticker limit (testing)
    python scripts/run_full_pipeline.py --from 2024-01-01 --to 2024-12-31 --max-tickers 20

    # Run only forecasts (skip data refresh)
    python scripts/run_full_pipeline.py --skip-data-refresh

    # Run with specific models
    python scripts/run_full_pipeline.py --days 90 --models arima_30d,prophet_30d
"""

from __future__ import annotations
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_full_pipeline(
    date_from: str = None,
    date_to: str = None,
    days: int = None,
    max_tickers: int = None,
    skip_data_refresh: bool = False,
    include_news: bool = False,
    forecast_models: list = None
) -> dict:
    """
    Run the complete pipeline: data ingestion + forecasting.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        days: Number of recent days (alternative to date_from/date_to)
        max_tickers: Optional limit on number of tickers
        skip_data_refresh: Skip data ingestion step
        include_news: Whether to include news in data ingestion
        forecast_models: List of model names to run

    Returns:
        Dictionary with pipeline results
    """
    start_time = datetime.now()

    print("=" * 80)
    print("FULL PIPELINE: DATA INGESTION + FORECASTING")
    print("=" * 80)
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    results = {
        'start_time': start_time,
        'data_ingestion': None,
        'forecasting': None,
        'total_duration': None,
        'errors': []
    }

    # Determine date range
    if days:
        date_to_obj = datetime.now().date()
        date_from_obj = date_to_obj - timedelta(days=days)
        date_from = date_from_obj.isoformat()
        date_to = date_to_obj.isoformat()
    elif not date_from or not date_to:
        # Default: last 30 days
        date_to_obj = datetime.now().date()
        date_from_obj = date_to_obj - timedelta(days=30)
        date_from = date_from_obj.isoformat()
        date_to = date_to_obj.isoformat()
        print(f"Using default date range: {date_from} to {date_to}")
        print()

    print(f"Configuration:")
    print(f"  Date range: {date_from} to {date_to}")
    if max_tickers:
        print(f"  Max tickers: {max_tickers}")
    else:
        print(f"  Max tickers: All active tickers")
    print(f"  Skip data refresh: {skip_data_refresh}")
    print(f"  Include news: {include_news}")
    if forecast_models:
        print(f"  Forecast models: {', '.join(forecast_models)}")
    else:
        print(f"  Forecast models: All configured models")
    print()

    # =========================================================================
    # STEP 1: DATA INGESTION
    # =========================================================================
    if not skip_data_refresh:
        print("=" * 80)
        print("STEP 1: DATA INGESTION")
        print("=" * 80)
        print()

        try:
            from core.context import RepoContext
            from orchestration.orchestrator import Orchestrator

            print("Initializing context...")
            ctx = RepoContext.from_repo_root()
            print("  ✓ Context initialized")
            print()

            print("Running data ingestion pipeline...")
            orchestrator = Orchestrator(ctx)
            final_df = orchestrator.run_company_pipeline(
                date_from=date_from,
                date_to=date_to,
                max_tickers=max_tickers
            )

            record_count = final_df.count()
            print()
            print(f"✓ Data ingestion completed!")
            print(f"  Total records: {record_count:,}")
            print()

            results['data_ingestion'] = {
                'status': 'success',
                'records': record_count,
                'date_from': date_from,
                'date_to': date_to
            }

        except Exception as e:
            error_msg = f"Data ingestion failed: {str(e)}"
            print(f"✗ {error_msg}")
            import traceback
            traceback.print_exc()
            results['data_ingestion'] = {
                'status': 'failed',
                'error': error_msg
            }
            results['errors'].append(error_msg)

            # Ask user if they want to continue
            print()
            response = input("Data ingestion failed. Continue with forecasting? (y/n): ")
            if response.lower() != 'y':
                print("Pipeline aborted.")
                return results
    else:
        print("=" * 80)
        print("STEP 1: DATA INGESTION - SKIPPED")
        print("=" * 80)
        print()
        results['data_ingestion'] = {
            'status': 'skipped'
        }

    # =========================================================================
    # STEP 2: FORECASTING
    # =========================================================================
    print("=" * 80)
    print("STEP 2: TIME SERIES FORECASTING")
    print("=" * 80)
    print()

    try:
        # Import forecast pipeline
        from scripts.run_forecasts import run_forecast_pipeline

        print("Running forecast pipeline...")
        forecast_results = run_forecast_pipeline(
            tickers=None,  # Use all available tickers
            refresh_data=False,  # We already refreshed in Step 1
            refresh_days=0,
            models=forecast_models,
            max_tickers=max_tickers
        )

        print()
        print(f"✓ Forecasting completed!")
        print(f"  Tickers processed: {forecast_results['tickers_processed']}")
        print(f"  Models trained: {forecast_results['total_models']}")
        print(f"  Forecasts generated: {forecast_results['total_forecasts']}")

        if forecast_results['errors']:
            print(f"  Errors: {len(forecast_results['errors'])}")

        results['forecasting'] = forecast_results

    except Exception as e:
        error_msg = f"Forecasting failed: {str(e)}"
        print(f"✗ {error_msg}")
        import traceback
        traceback.print_exc()
        results['forecasting'] = {
            'status': 'failed',
            'error': error_msg
        }
        results['errors'].append(error_msg)

    # =========================================================================
    # SUMMARY
    # =========================================================================
    end_time = datetime.now()
    results['end_time'] = end_time
    results['total_duration'] = (end_time - start_time).total_seconds()

    print()
    print("=" * 80)
    print("PIPELINE SUMMARY")
    print("=" * 80)
    print(f"Total duration: {results['total_duration']:.1f} seconds")
    print()

    # Data ingestion summary
    if results['data_ingestion']:
        print("Data Ingestion:")
        if results['data_ingestion']['status'] == 'success':
            print(f"  ✓ Status: Success")
            print(f"  Records: {results['data_ingestion']['records']:,}")
        elif results['data_ingestion']['status'] == 'skipped':
            print(f"  - Status: Skipped")
        else:
            print(f"  ✗ Status: Failed")
        print()

    # Forecasting summary
    if results['forecasting']:
        print("Forecasting:")
        if isinstance(results['forecasting'], dict) and 'status' in results['forecasting']:
            if results['forecasting']['status'] == 'failed':
                print(f"  ✗ Status: Failed")
        else:
            print(f"  ✓ Status: Success")
            print(f"  Tickers processed: {results['forecasting']['tickers_processed']}")
            print(f"  Models trained: {results['forecasting']['total_models']}")
            print(f"  Forecasts generated: {results['forecasting']['total_forecasts']}")
            if results['forecasting']['errors']:
                print(f"  Errors: {len(results['forecasting']['errors'])}")
        print()

    # Overall errors
    if results['errors']:
        print(f"Total errors: {len(results['errors'])}")
        for error in results['errors'][:5]:
            print(f"  - {error}")
        if len(results['errors']) > 5:
            print(f"  ... and {len(results['errors']) - 5} more")
    else:
        print("No errors!")

    print()
    print("=" * 80)
    print(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run full pipeline: data ingestion + forecasting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline for last 30 days
  python scripts/run_full_pipeline.py --days 30

  # Run with specific date range
  python scripts/run_full_pipeline.py --from 2024-01-01 --to 2024-12-31

  # Run with ticker limit (for testing)
  python scripts/run_full_pipeline.py --days 90 --max-tickers 20

  # Skip data refresh, just run forecasts
  python scripts/run_full_pipeline.py --skip-data-refresh

  # Run with specific models
  python scripts/run_full_pipeline.py --days 90 --models arima_30d,prophet_30d

  # Full production run (all tickers, all models, 90 days)
  python scripts/run_full_pipeline.py --days 90
        """
    )

    # Date range options
    parser.add_argument(
        '--days',
        type=int,
        default=None,
        help='Number of recent days to process (e.g., --days 30)'
    )
    parser.add_argument(
        '--from',
        dest='date_from',
        type=str,
        default=None,
        help='Start date in YYYY-MM-DD format'
    )
    parser.add_argument(
        '--to',
        dest='date_to',
        type=str,
        default=None,
        help='End date in YYYY-MM-DD format'
    )

    # Ticker options
    parser.add_argument(
        '--max-tickers',
        type=int,
        default=None,
        help='Maximum number of tickers to process (default: all)'
    )

    # Pipeline control
    parser.add_argument(
        '--skip-data-refresh',
        action='store_true',
        help='Skip data ingestion step (use existing data)'
    )
    parser.add_argument(
        '--include-news',
        action='store_true',
        help='Include news data in ingestion (slower)'
    )

    # Forecasting options
    parser.add_argument(
        '--models',
        type=str,
        default=None,
        help='Comma-separated list of models to run (e.g., arima_30d,prophet_30d)'
    )

    args = parser.parse_args()

    # Parse models
    models = args.models.split(',') if args.models else None

    # Run pipeline
    try:
        results = run_full_pipeline(
            date_from=args.date_from,
            date_to=args.date_to,
            days=args.days,
            max_tickers=args.max_tickers,
            skip_data_refresh=args.skip_data_refresh,
            include_news=args.include_news,
            forecast_models=models
        )

        # Exit with error code if there were critical failures
        if results['errors']:
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ Pipeline failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
