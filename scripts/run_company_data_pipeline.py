"""
Company Data Pipeline Script

This script runs the complete data ingestion pipeline from Polygon API to Silver layer.
It can be configured via command-line arguments for flexible execution.

Usage:
    python scripts/run_company_data_pipeline.py [options]

Examples:
    # Ingest last 30 days for all active tickers
    python scripts/run_company_data_pipeline.py --days 30

    # Ingest specific date range for 100 tickers
    python scripts/run_company_data_pipeline.py --from 2024-01-01 --to 2024-12-31 --max-tickers 100

    # Full historical ingest (all tickers, all available data)
    python scripts/run_company_data_pipeline.py --from 2020-01-01 --to 2024-12-31
"""

from __future__ import annotations
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.context import RepoContext
from utils.pipeline_tracker import PipelineRunTracker
from utils.api_validator import APIValidator


def run_company_data_pipeline(
    date_from: str,
    date_to: str,
    max_tickers: int = None,
    include_news: bool = True,
    skip_if_exists: bool = True,
    skip_validation: bool = False
) -> None:
    """
    Run the complete company data pipeline.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        max_tickers: Optional limit on number of tickers to process
        include_news: Whether to include news data
        skip_if_exists: Whether to skip partitions that already exist
        skip_validation: Whether to skip API validation (not recommended)
    """
    # Initialize run tracker
    tracker = PipelineRunTracker()
    tracker.start_run("data_ingestion", {
        "date_from": date_from,
        "date_to": date_to,
        "max_tickers": max_tickers,
        "include_news": include_news
    })

    print("=" * 80)
    print("COMPANY DATA PIPELINE")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print(f"Date range: {date_from} to {date_to}")
    if max_tickers:
        print(f"Max tickers: {max_tickers}")
    print(f"Include news: {include_news}")
    print(f"Skip existing partitions: {skip_if_exists}")
    print("=" * 80)
    print()

    # Initialize context
    print("Step 1: Initializing context...")
    print("-" * 80)
    try:
        ctx = RepoContext.from_repo_root()
        print("  ✓ Context initialized")
        print(f"  ✓ Spark session: {ctx.spark.sparkContext.appName}")
        print(f"  ✓ Storage root: {ctx.storage.get('roots', {}).get('bronze', 'N/A')}")
        tracker.log_stage("initialization", "success", {"spark_app": ctx.spark.sparkContext.appName})
    except Exception as e:
        print(f"  ✗ Failed to initialize context: {e}")
        tracker.log_error(str(e), "initialization")
        tracker.end_run("failed")
        sys.exit(1)
    print()

    # Validate API access and date range
    if not skip_validation:
        print("Step 2: Validating API access...")
        print("-" * 80)
        try:
            validator = APIValidator(ctx.polygon_cfg)

            # Test basic connection
            is_connected, conn_msg = validator.test_api_connection()
            if not is_connected:
                print(f"  ✗ API connection failed: {conn_msg}")
                tracker.log_error(f"API connection failed: {conn_msg}", "validation")
                tracker.end_run("failed")
                sys.exit(1)

            # Validate date range
            is_valid, val_msg, suggested_from = validator.validate_date_range(
                date_from, date_to, auto_adjust=True
            )

            if not is_valid:
                tracker.log_warning(f"Date range validation: {val_msg}", "validation")

                if suggested_from:
                    # Prompt user for adjustment
                    adjusted_from, adjusted_to, continue_flag = APIValidator.prompt_user_for_adjusted_range(
                        date_from, date_to, suggested_from
                    )

                    if not continue_flag:
                        tracker.end_run("aborted")
                        sys.exit(0)

                    # Update date range
                    date_from = adjusted_from
                    date_to = adjusted_to

                    # Re-validate adjusted range
                    is_valid, val_msg, _ = validator.validate_date_range(
                        date_from, date_to, auto_adjust=False
                    )

                    if not is_valid:
                        print(f"  ✗ Adjusted range still invalid: {val_msg}")
                        tracker.log_error(f"Validation failed: {val_msg}", "validation")
                        tracker.end_run("failed")
                        sys.exit(1)
                else:
                    print(f"  ✗ Date range validation failed: {val_msg}")
                    print("\nOptions:")
                    print("  1. Abort")
                    print("  2. Continue anyway (may fail during ingestion)")
                    choice = input("\nSelect option (1/2): ").strip()
                    if choice != '2':
                        tracker.end_run("aborted")
                        sys.exit(0)

            tracker.log_stage("validation", "success" if is_valid else "warning", {
                "date_from": date_from,
                "date_to": date_to
            })

        except Exception as e:
            tracker.log_warning(f"Validation error: {str(e)}", "validation")
            print(f"  ⚠ Validation error: {e}")
            print("  Continuing anyway...")

        print()
    else:
        print("Step 2: API validation skipped")
        print()
        tracker.log_stage("validation", "skipped")

    # Run ingestion pipeline
    step_num = 3 if not skip_validation else 2
    print(f"Step {step_num}: Running ingestion pipeline...")
    print("-" * 80)
    try:
        from orchestration.orchestrator import Orchestrator

        orchestrator = Orchestrator(ctx)
        final_df = orchestrator.run_company_pipeline(
            date_from=date_from,
            date_to=date_to,
            max_tickers=max_tickers
        )

        print()
        print("  ✓ Ingestion completed successfully!")
        print()

        # Show sample of results
        print("Sample of ingested data:")
        final_df.show(10, truncate=False)

        # Count records
        record_count = final_df.count()
        print()
        print(f"Total records: {record_count:,}")

        tracker.log_stage("ingestion", "success", {
            "record_count": record_count,
            "date_from": date_from,
            "date_to": date_to
        })
        tracker.update_results({"record_count": record_count})

    except Exception as e:
        print(f"  ✗ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        tracker.log_error(str(e), "ingestion")
        tracker.end_run("failed")
        sys.exit(1)

    print()
    print("=" * 80)
    print("✓ PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # End run tracking
    tracker.end_run("success", {
        "records_ingested": record_count,
        "date_range": f"{date_from} to {date_to}"
    })


def main():
    parser = argparse.ArgumentParser(
        description="Run company data ingestion pipeline from Polygon API to Silver layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest last 30 days for all tickers
  python scripts/run_company_data_pipeline.py --days 30

  # Ingest specific date range
  python scripts/run_company_data_pipeline.py --from 2024-01-01 --to 2024-12-31

  # Ingest with ticker limit (for testing)
  python scripts/run_company_data_pipeline.py --days 7 --max-tickers 10

  # Ingest without news (faster)
  python scripts/run_company_data_pipeline.py --days 30 --no-news
        """
    )

    # Date range options
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument(
        '--days',
        type=int,
        default=None,
        help='Number of recent days to ingest (e.g., --days 30)'
    )
    date_group.add_argument(
        '--from-to',
        nargs=2,
        metavar=('FROM', 'TO'),
        help='Specific date range (e.g., --from-to 2024-01-01 2024-12-31)'
    )

    # Individual date arguments (legacy support)
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
        help='Maximum number of tickers to process (default: all active tickers)'
    )

    # Data options
    parser.add_argument(
        '--no-news',
        action='store_true',
        help='Skip news data ingestion (faster processing)'
    )

    # Validation options
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip API validation (not recommended, may fail during ingestion)'
    )

    args = parser.parse_args()

    # Determine date range
    if args.from_to:
        date_from, date_to = args.from_to
    elif args.days:
        date_to = datetime.now().date()
        date_from = date_to - timedelta(days=args.days)
        date_from = date_from.isoformat()
        date_to = date_to.isoformat()
    elif args.date_from and args.date_to:
        date_from = args.date_from
        date_to = args.date_to
    else:
        # Default: last 90 days
        date_to = datetime.now().date()
        date_from = date_to - timedelta(days=90)
        date_from = date_from.isoformat()
        date_to = date_to.isoformat()
        print(f"No date range specified, using last 90 days: {date_from} to {date_to}")
        print()

    # Run pipeline
    try:
        run_company_data_pipeline(
            date_from=date_from,
            date_to=date_to,
            max_tickers=args.max_tickers,
            include_news=not args.no_news,
            skip_validation=args.skip_validation
        )
    except Exception as e:
        print(f"\n✗ Pipeline failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
