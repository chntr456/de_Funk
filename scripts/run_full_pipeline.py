"""
Full Pipeline Orchestrator

This script orchestrates the complete end-to-end pipeline:
1. Data Ingestion: Alpha Vantage API → Bronze layer (scripts/ingest/)
2. Silver Build: Bronze → Silver dimensional models (scripts/build/)
3. Forecasting: Generate time series forecasts (scripts/forecast/)

Separation of Concerns:
- scripts/ingest/      → Bronze layer filling (API calls)
- scripts/build/       → Silver layer building from Bronze
- scripts/forecast/    → Predictive model building
- scripts/run_full_pipeline.py → Orchestrates all stages (this script)

Usage:
    python -m scripts.run_full_pipeline [options]

Examples:
    # Run full pipeline for top 2000 stocks by market cap
    python -m scripts.run_full_pipeline --days 30 --max-tickers 2000

    # Run with minimum market cap filter ($1B+)
    python -m scripts.run_full_pipeline --days 30 --max-tickers 2000 --min-market-cap 1e9

    # Run for specific date range with ticker limit (testing)
    python -m scripts.run_full_pipeline --from 2024-01-01 --to 2024-12-31 --max-tickers 20

    # Run only forecasts (skip data refresh)
    python -m scripts.run_full_pipeline --skip-data-refresh

    # Include fundamentals (income statements, balance sheets, cash flows, earnings)
    python -m scripts.run_full_pipeline --days 90 --include-fundamentals

    # Run with specific models
    python -m scripts.run_full_pipeline --days 90 --models arima_30d,prophet_30d
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
import argparse
from datetime import datetime, timedelta

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def run_full_pipeline(
    date_from: str = None,
    date_to: str = None,
    days: int = None,
    max_tickers: int = None,
    skip_data_refresh: bool = False,
    skip_silver_build: bool = False,
    skip_forecasts: bool = False,
    skip_reference_refresh: bool = False,
    use_concurrent: bool = True,
    include_news: bool = False,
    include_fundamentals: bool = True,
    sort_by_market_cap: bool = True,
    min_market_cap: float = None,
    use_bulk_listing: bool = False,
    forecast_models: list = None,
    per_ticker: bool = True,  # v2.4: Default to per-ticker strategy
    batch_write_size: int = 20
) -> dict:
    """
    Run the complete pipeline: data ingestion + forecasting.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        days: Number of recent days (alternative to date_from/date_to)
        max_tickers: Optional limit on number of tickers
        skip_data_refresh: Skip data ingestion step
        skip_silver_build: Skip silver layer build
        skip_forecasts: Skip forecast generation step
        skip_reference_refresh: Skip OVERVIEW calls (use existing reference data).
                               Saves ~50% of API calls for daily price updates.
        use_concurrent: Use concurrent API requests (default: True)
        include_news: Whether to include news in data ingestion
        include_fundamentals: Whether to include fundamentals (income, balance, cash flow, earnings)
        sort_by_market_cap: Sort tickers by market cap descending (default: True)
        min_market_cap: Minimum market cap filter (e.g., 1e9 for $1B+)
        forecast_models: List of model names to run
        per_ticker: Use per-ticker ingestion strategy (v2.4). Completes all data
                   for each ticker before moving to next. Enables parallel
                   downstream processing. (default: True)
        batch_write_size: How many tickers to accumulate before writing to disk (default: 10)

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
        # --days takes precedence: calculate range from today
        date_to_obj = datetime.now().date()
        date_from_obj = date_to_obj - timedelta(days=days)
        date_from = date_from_obj.isoformat()
        date_to = date_to_obj.isoformat()
    elif date_from or date_to:
        # User specified at least one date - fill in the missing one
        if not date_to:
            # --from specified, default --to to today
            date_to = datetime.now().date().isoformat()
        if not date_from:
            # --to specified but not --from, default to 1 year before --to
            date_to_obj = datetime.fromisoformat(date_to).date()
            date_from = (date_to_obj - timedelta(days=365)).isoformat()
    else:
        # Neither specified: default to last 30 days
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
    print(f"  Sort by market cap: {sort_by_market_cap}")
    if min_market_cap:
        print(f"  Min market cap: ${min_market_cap:,.0f}")
    print(f"  Skip data refresh: {skip_data_refresh}")
    print(f"  Skip reference refresh: {skip_reference_refresh} {'(prices only - saves 50% API calls)' if skip_reference_refresh else ''}")
    print(f"  Concurrent requests: {use_concurrent}")
    print(f"  Skip forecasts: {skip_forecasts}")
    print(f"  Include news: {include_news}")
    print(f"  Include fundamentals: {include_fundamentals}")
    print(f"  Per-ticker strategy: {per_ticker} {'(v2.4 - clean progress, enables parallel downstream)' if per_ticker else ''}")
    if per_ticker:
        print(f"  Batch write size: {batch_write_size} tickers")
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

            print("Running comprehensive data ingestion pipeline...")
            if sort_by_market_cap:
                print("  (Sorting tickers by market cap descending)")

            # Choose ingestion strategy
            if per_ticker:
                # v2.4: Per-ticker strategy with clean progress bars
                print("  (Using per-ticker strategy with clean progress tracking)")
                ingestion_results = ingestor.run_comprehensive_per_ticker(
                    tickers=None,  # Will use default or market-cap sorted list
                    date_from=date_from,
                    date_to=date_to,
                    max_tickers=max_tickers,
                    sort_by_market_cap=sort_by_market_cap,
                    min_market_cap=min_market_cap,
                    include_fundamentals=include_fundamentals,
                    skip_reference_refresh=skip_reference_refresh,
                    use_bulk_listing=use_bulk_listing,
                    batch_write_size=batch_write_size
                )
            else:
                # Legacy: Horizontal batching (all prices, then all cashflows, etc.)
                ingestion_results = ingestor.run_comprehensive(
                    tickers=None,  # Will use default or market-cap sorted list
                    date_from=date_from,
                    date_to=date_to,
                    max_tickers=max_tickers,
                    sort_by_market_cap=sort_by_market_cap,
                    min_market_cap=min_market_cap,
                    include_fundamentals=include_fundamentals,
                    include_options=False,  # Options require premium tier
                    skip_reference_refresh=skip_reference_refresh,
                    use_concurrent=use_concurrent,
                    use_bulk_listing=use_bulk_listing
                )

            # Extract results
            ingested_tickers = ingestion_results.get('tickers', [])
            tickers_count = len(ingested_tickers) if ingested_tickers else 0

            print()
            print(f"✓ Data ingestion completed!")
            print(f"  Tickers processed: {tickers_count}")
            if include_fundamentals:
                print(f"  Income statements: {'✓' if ingestion_results.get('income_statements') else '✗'}")
                print(f"  Balance sheets: {'✓' if ingestion_results.get('balance_sheets') else '✗'}")
                print(f"  Cash flows: {'✓' if ingestion_results.get('cash_flows') else '✗'}")
                print(f"  Earnings: {'✓' if ingestion_results.get('earnings') else '✗'}")
            print()

            results['data_ingestion'] = {
                'status': 'success',
                'tickers_processed': tickers_count,
                'tickers': ingested_tickers,
                'fundamentals': {
                    'income_statements': ingestion_results.get('income_statements'),
                    'balance_sheets': ingestion_results.get('balance_sheets'),
                    'cash_flows': ingestion_results.get('cash_flows'),
                    'earnings': ingestion_results.get('earnings'),
                } if include_fundamentals else {},
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
    # STEP 2: BUILD SILVER LAYER
    # =========================================================================
    if not skip_silver_build:
        print("=" * 80)
        print("STEP 2: BUILDING SILVER LAYER")
        print("=" * 80)
        print()

        try:
            from config.model_loader import ModelConfigLoader
            from models.implemented.stocks.model import StocksModel
            from models.implemented.company.model import CompanyModel
            from orchestration.common.spark_session import get_spark
            from core.connection import ConnectionFactory

            print("Building models from bronze data...")
            print("  Note: StocksModel uses JOIN-based filtering (prices filtered to tickers in dim_stock)")
            print()

            # Load storage configuration
            import json
            import time
            storage_path = Path(repo_root) / "configs" / "storage.json"
            with open(storage_path, 'r') as f:
                storage_cfg = json.load(f)

            # Load model configurations
            config_root = Path(repo_root) / "configs" / "models"
            loader = ModelConfigLoader(config_root)

            # Initialize Spark connection
            spark_session = get_spark("SilverBuild")
            spark = ConnectionFactory.create("spark", spark_session=spark_session)

            # Track build metrics
            build_start = time.time()
            build_metrics = {}

            # Build Company model first (stocks depends on company)
            print("  Building company model...")
            company_start = time.time()
            company_cfg = loader.load_model_config("company")
            company_model = CompanyModel(
                connection=spark,
                storage_cfg=storage_cfg,
                model_cfg=company_cfg,
                params={},
                repo_root=repo_root
            )
            company_dims, company_facts = company_model.build()
            company_model.write_tables(quiet=True)
            company_elapsed = time.time() - company_start
            build_metrics['company'] = {
                'dims': len(company_dims),
                'facts': len(company_facts),
                'elapsed': company_elapsed
            }
            print(f"    ✓ Company model: {len(company_dims)} dims, {len(company_facts)} facts ({company_elapsed:.1f}s)")

            # Build Stocks model (uses JOIN-based filtering via after_build hook)
            print("  Building stocks model...")
            stocks_start = time.time()
            stocks_cfg = loader.load_model_config("stocks")
            stocks_model = StocksModel(
                connection=spark,
                storage_cfg=storage_cfg,
                model_cfg=stocks_cfg,
                params={},
                repo_root=repo_root
            )
            stocks_dims, stocks_facts = stocks_model.build()
            stocks_model.write_tables(quiet=True)
            stocks_elapsed = time.time() - stocks_start

            # Collect row counts
            stocks_rows = {}
            for name, df in {**stocks_dims, **stocks_facts}.items():
                try:
                    count = df.count() if hasattr(df, 'count') else len(df)
                    stocks_rows[name] = count
                except Exception:
                    stocks_rows[name] = 0

            build_metrics['stocks'] = {
                'dims': len(stocks_dims),
                'facts': len(stocks_facts),
                'rows': stocks_rows,
                'elapsed': stocks_elapsed
            }
            print(f"    ✓ Stocks model: {len(stocks_dims)} dims, {len(stocks_facts)} facts ({stocks_elapsed:.1f}s)")

            total_build_elapsed = time.time() - build_start

            # Print summary
            print()
            print("=" * 60)
            print("✓ SILVER BUILD COMPLETE")
            print("=" * 60)
            print(f"  Company: {build_metrics['company']['dims']} dims, {build_metrics['company']['facts']} facts | {build_metrics['company']['elapsed']:.1f}s")
            print(f"  Stocks:  {build_metrics['stocks']['dims']} dims, {build_metrics['stocks']['facts']} facts | {build_metrics['stocks']['elapsed']:.1f}s")
            total_rows = sum(build_metrics['stocks']['rows'].values())
            print(f"  Total rows: {total_rows:,}")
            print(f"  Elapsed: {total_build_elapsed:.0f}s")
            print("=" * 60)

            # Clean up Spark session
            spark_session.stop()

            results['silver_build'] = {'status': 'success', 'metrics': build_metrics}

        except Exception as e:
            error_msg = f"Silver layer build failed: {str(e)}"
            print(f"  ⚠ {error_msg}")
            import traceback
            traceback.print_exc()
            results['silver_build'] = {'status': 'failed', 'error': error_msg}
            # Continue anyway - forecasting may still work with existing data

        print()
    else:
        print("=" * 80)
        print("STEP 2: SILVER BUILD - SKIPPED")
        print("=" * 80)
        print()
        results['silver_build'] = {'status': 'skipped'}

    # =========================================================================
    # STEP 3: FORECASTING
    # =========================================================================
    if not skip_forecasts:
        print("=" * 80)
        print("STEP 3: TIME SERIES FORECASTING")
        print("=" * 80)
        print()

        try:
            # Import forecast pipeline
            from scripts.forecast.run_forecasts import run_forecast_pipeline

            # Get tickers from ingestion step (if available)
            ingested_tickers = results.get('data_ingestion', {}).get('tickers', None)
            if ingested_tickers:
                print(f"Using {len(ingested_tickers)} tickers from ingestion step...")

            print("Running forecast pipeline...")
            forecast_results = run_forecast_pipeline(
                tickers=ingested_tickers,  # Use tickers from ingestion step
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
            traceback.print_exc()
            results['forecasting'] = {
                'status': 'failed',
                'error': error_msg
            }
            results['errors'].append(error_msg)
    else:
        print("=" * 80)
        print("STEP 3: FORECASTING - SKIPPED")
        print("=" * 80)
        print()
        results['forecasting'] = {'status': 'skipped'}

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
            print(f"  Tickers processed: {results['data_ingestion'].get('tickers_processed', 0)}")
            fundamentals = results['data_ingestion'].get('fundamentals', {})
            if fundamentals:
                print(f"  Fundamentals:")
                for key, val in fundamentals.items():
                    if val:  # Path exists means it was written
                        print(f"    - {key}: ✓")
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
  # First-time ingestion: discover all tickers and ingest top 2000 by market cap
  python -m scripts.run_full_pipeline --days 30 --max-tickers 2000 --use-bulk-listing

  # First-time ingestion: ingest ALL tickers (no limit)
  python -m scripts.run_full_pipeline --from 2024-01-01 --use-bulk-listing

  # Subsequent runs (uses existing reference data for ticker list)
  python -m scripts.run_full_pipeline --days 30 --max-tickers 2000

  # Run with minimum market cap filter ($1B+)
  python -m scripts.run_full_pipeline --days 30 --max-tickers 2000 --min-market-cap 1e9

  # Quick test with 20 tickers
  python -m scripts.run_full_pipeline --days 90 --max-tickers 20 --use-bulk-listing

  # Skip data refresh, just run forecasts
  python -m scripts.run_full_pipeline --skip-data-refresh

  # Full production run (top 2000 by market cap, 90 days)
  python -m scripts.run_full_pipeline --days 90 --max-tickers 2000

Note: --max-tickers automatically enables market cap sorting (top N by market cap).
      --use-bulk-listing fetches ticker list from Alpha Vantage (required for first-time setup).
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
    parser.add_argument(
        '--use-bulk-listing',
        action='store_true',
        help='Discover all tickers from Alpha Vantage LISTING_STATUS endpoint (required for first-time ingestion)'
    )

    # Pipeline control
    parser.add_argument(
        '--skip-data-refresh',
        action='store_true',
        help='Skip data ingestion step (use existing bronze data)'
    )
    parser.add_argument(
        '--skip-silver-build',
        action='store_true',
        help='Skip silver layer build'
    )
    parser.add_argument(
        '--include-news',
        action='store_true',
        help='Include news data in ingestion (slower)'
    )
    parser.add_argument(
        '--include-fundamentals',
        action='store_true',
        default=True,
        help='Include fundamentals (income statements, balance sheets, cash flows, earnings) - default: True'
    )
    parser.add_argument(
        '--no-fundamentals',
        action='store_true',
        help='Skip fundamentals ingestion (only reference + prices)'
    )
    parser.add_argument(
        '--skip-reference-refresh',
        action='store_true',
        help='Skip OVERVIEW calls - only fetch prices (saves 50%% API calls for daily updates)'
    )
    parser.add_argument(
        '--concurrent',
        action='store_true',
        default=True,
        help='Use concurrent API requests (default: True)'
    )
    parser.add_argument(
        '--no-concurrent',
        action='store_true',
        help='Disable concurrent requests (sequential API calls)'
    )

    # Market cap options
    parser.add_argument(
        '--sort-by-market-cap',
        action='store_true',
        default=None,  # Will be auto-determined based on --max-tickers
        help='Sort tickers by market cap descending (auto-enabled when --max-tickers is set)'
    )
    parser.add_argument(
        '--min-market-cap',
        type=float,
        default=None,
        help='Minimum market cap filter in dollars (e.g., 1e9 for $1B+)'
    )

    # Forecasting options
    parser.add_argument(
        '--skip-forecasts',
        action='store_true',
        help='Skip forecast generation step'
    )
    parser.add_argument(
        '--models',
        type=str,
        default=None,
        help='Comma-separated list of models to run (e.g., arima_30d,prophet_30d)'
    )

    # Ingestion strategy options (v2.4)
    parser.add_argument(
        '--per-ticker',
        action='store_true',
        default=True,
        help='Use per-ticker ingestion strategy (default: True). Completes all data for each ticker before moving to next.'
    )
    parser.add_argument(
        '--no-per-ticker',
        action='store_true',
        help='Use legacy horizontal batching (all prices, then all cashflows, etc.)'
    )
    parser.add_argument(
        '--batch-write-size',
        type=int,
        default=20,
        help='Number of tickers to accumulate before writing to disk (default: 20)'
    )

    args = parser.parse_args()

    # Parse models
    models = args.models.split(',') if args.models else None

    # Handle market cap sorting: auto-enable when --max-tickers is set
    # This makes the common case simple: --max-tickers 2000 gets top 2000 by market cap
    if args.sort_by_market_cap is not None:
        # Explicit flag provided
        sort_by_market_cap = args.sort_by_market_cap
    else:
        # Auto-determine: sort by market cap if max_tickers is specified
        sort_by_market_cap = args.max_tickers is not None

    # Handle concurrent flag (--no-concurrent overrides default)
    use_concurrent = not args.no_concurrent

    # Handle fundamentals flag (--no-fundamentals overrides default)
    include_fundamentals = not args.no_fundamentals

    # Handle per-ticker flag (--no-per-ticker overrides default)
    per_ticker = not args.no_per_ticker

    # Run pipeline
    try:
        results = run_full_pipeline(
            date_from=args.date_from,
            date_to=args.date_to,
            days=args.days,
            max_tickers=args.max_tickers,
            skip_data_refresh=args.skip_data_refresh,
            skip_silver_build=args.skip_silver_build,
            skip_forecasts=args.skip_forecasts,
            skip_reference_refresh=args.skip_reference_refresh,
            use_concurrent=use_concurrent,
            include_news=args.include_news,
            include_fundamentals=include_fundamentals,
            sort_by_market_cap=sort_by_market_cap,
            min_market_cap=args.min_market_cap,
            use_bulk_listing=args.use_bulk_listing,
            forecast_models=models,
            per_ticker=per_ticker,
            batch_write_size=args.batch_write_size
        )

        # Exit with error code if there were critical failures
        if results['errors']:
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ Pipeline failed with error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
