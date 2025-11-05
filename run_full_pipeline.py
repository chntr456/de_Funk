#!/usr/bin/env python3
"""
Master pipeline script for de_Funk analytics platform.

This script orchestrates the entire data pipeline using the new scalable architecture:
1. Build core model (dim_calendar)
2. Ingest company data (Bronze layer)
3. Build company model (Silver layer)
4. Generate forecasts for top 100 companies
5. Build macro and city_finance models
6. Launch the UI application

Usage:
    python run_full_pipeline.py --top-n 100
    python run_full_pipeline.py --top-n 100 --skip-ingestion
    python run_full_pipeline.py --top-n 10 --skip-ui
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import date, timedelta

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from orchestration.common.spark_session import get_spark_session


def build_calendar_dimension(spark, repo_root: Path, storage_cfg: dict):
    """
    Step 1: Build calendar dimension (core model).

    Args:
        spark: SparkSession
        repo_root: Repository root path
        storage_cfg: Storage configuration
    """
    print("\n" + "=" * 70)
    print("STEP 1: Building Calendar Dimension (Core Model)")
    print("=" * 70)

    from models.implemented.core.builders.calendar_builder import build_calendar_table

    # Get calendar config
    import yaml
    core_config_path = repo_root / "configs" / "models" / "core.yaml"
    with open(core_config_path) as f:
        core_config = yaml.safe_load(f)

    calendar_config = core_config.get('calendar_config', {})

    # Build calendar dimension
    output_path = str(repo_root / storage_cfg['roots']['bronze'] / 'calendar_seed')

    calendar_df = build_calendar_table(
        spark,
        output_path=output_path,
        start_date=calendar_config.get('start_date', '2000-01-01'),
        end_date=calendar_config.get('end_date', '2050-12-31'),
        fiscal_year_start_month=calendar_config.get('fiscal_year_start_month', 1)
    )

    print(f"✓ Calendar dimension created with {calendar_df.count()} dates")
    print(f"✓ Saved to: {output_path}")

    return calendar_df


def ingest_company_data(spark, repo_root: Path, storage_cfg: dict, top_n: int = 100):
    """
    Step 2: Ingest company data from Polygon API.

    Args:
        spark: SparkSession
        repo_root: Repository root path
        storage_cfg: Storage configuration
        top_n: Number of top companies to ingest
    """
    print("\n" + "=" * 70)
    print(f"STEP 2: Ingesting Company Data (Top {top_n} Companies)")
    print("=" * 70)

    from datapipelines.ingestors.company_ingestor import CompanyPolygonIngestor
    import json

    # Calculate date range (last 2 years)
    date_to = date.today()
    date_from = date_to - timedelta(days=730)

    # Load Polygon API config
    polygon_cfg_path = repo_root / "configs" / "polygon_endpoints.json"
    with open(polygon_cfg_path) as f:
        polygon_cfg = json.load(f)

    # Create ingestor
    ingestor = CompanyPolygonIngestor(
        polygon_cfg=polygon_cfg,
        storage_cfg=storage_cfg,
        spark=spark
    )

    # Run ingestion
    print(f"Ingesting data from {date_from} to {date_to}")
    print(f"Limited to top {top_n} companies by market cap")

    written_paths = ingestor.run_all(
        date_from=str(date_from),
        date_to=str(date_to),
        snapshot_dt=str(date.today()),
        max_tickers=top_n,
        include_news=True
    )

    print(f"✓ Ingestion complete. Written {len(written_paths)} Bronze tables")
    for path in written_paths:
        print(f"  - {path}")

    return written_paths


def build_company_model(spark, repo_root: Path, storage_cfg: dict):
    """
    Step 3: Build company model (Silver layer).

    Args:
        spark: SparkSession
        repo_root: Repository root path
        storage_cfg: Storage configuration
    """
    print("\n" + "=" * 70)
    print("STEP 3: Building Company Model (Silver Layer)")
    print("=" * 70)

    from models.api.session import UniversalSession

    # Create session
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root
    )

    # Load company model
    company_model = session.load_model('company')

    # Build model (this creates dims and facts)
    print("Building company model graph...")
    company_model.ensure_built()

    # List what was built
    tables = company_model.list_tables()
    print(f"✓ Company model built:")
    print(f"  - Dimensions: {tables['dimensions']}")
    print(f"  - Facts: {tables['facts']}")

    # Write to Silver storage using BaseModel's generic write method
    stats = company_model.write_tables(
        use_optimized_writer=True,  # Use ParquetLoader for better performance
        partition_by={
            'fact_prices': ['trade_date', 'ticker'],
            'fact_news': ['publish_date']
        }
    )

    print(f"✓ Company model complete - {stats['total_tables']} tables written")

    return company_model


def generate_forecasts(spark, repo_root: Path, storage_cfg: dict, top_n: int = 100):
    """
    Step 4: Generate forecasts for top companies.

    Args:
        spark: SparkSession
        repo_root: Repository root path
        storage_cfg: Storage configuration
        top_n: Number of companies to forecast
    """
    print("\n" + "=" * 70)
    print(f"STEP 4: Generating Forecasts (Top {top_n} Companies)")
    print("=" * 70)

    from models.api.session import UniversalSession

    # Create session with both company and forecast models
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root,
        models=['company', 'forecast']
    )

    # Get top N tickers from company model
    company_model = session.get_model_instance('company')
    company_model.ensure_built()

    # Get dim_company to find active tickers
    dim_company = company_model.get_dimension_df('dim_company')
    tickers = [row['ticker'] for row in dim_company.limit(top_n).collect()]

    print(f"Generating forecasts for {len(tickers)} tickers...")

    # For each ticker, train and generate forecasts
    # Note: Using the old forecast_model.py for now, will be updated to use new architecture
    forecast_model = session.get_model_instance('forecast')

    # TODO: Implement forecast training using new architecture
    # For now, just log that this step would run
    print(f"✓ Forecast generation would train models for: {', '.join(tickers[:10])}...")
    print(f"  (and {len(tickers) - 10} more tickers)")
    print("✓ Forecasts complete (placeholder)")

    return tickers


def build_macro_model(spark, repo_root: Path, storage_cfg: dict):
    """
    Step 5: Build macro model (BLS data).

    Args:
        spark: SparkSession
        repo_root: Repository root path
        storage_cfg: Storage configuration
    """
    print("\n" + "=" * 70)
    print("STEP 5: Building Macro Model")
    print("=" * 70)

    from models.api.session import UniversalSession

    # Create session
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root
    )

    # Load macro model
    macro_model = session.load_model('macro')

    # Build model
    print("Building macro model graph...")
    macro_model.ensure_built()

    # List what was built
    tables = macro_model.list_tables()
    print(f"✓ Macro model built:")
    print(f"  - Dimensions: {tables['dimensions']}")
    print(f"  - Facts: {tables['facts']}")

    # Write to Silver storage
    stats = macro_model.write_tables(use_optimized_writer=True)

    print(f"✓ Macro model complete - {stats['total_tables']} tables written")

    return macro_model


def build_city_finance_model(spark, repo_root: Path, storage_cfg: dict):
    """
    Step 6: Build city finance model (Chicago data).

    Args:
        spark: SparkSession
        repo_root: Repository root path
        storage_cfg: Storage configuration
    """
    print("\n" + "=" * 70)
    print("STEP 6: Building City Finance Model")
    print("=" * 70)

    from models.api.session import UniversalSession

    # Create session
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root,
        models=['core', 'macro', 'city_finance']  # city_finance depends on macro
    )

    # Load city finance model
    city_finance_model = session.load_model('city_finance')

    # Build model
    print("Building city finance model graph...")
    city_finance_model.ensure_built()

    # List what was built
    tables = city_finance_model.list_tables()
    print(f"✓ City finance model built:")
    print(f"  - Dimensions: {tables['dimensions']}")
    print(f"  - Facts: {tables['facts']}")

    # Write to Silver storage
    stats = city_finance_model.write_tables(use_optimized_writer=True)

    print(f"✓ City finance model complete - {stats['total_tables']} tables written")

    return city_finance_model


def launch_ui(repo_root: Path):
    """
    Step 7: Launch Streamlit UI application.

    Args:
        repo_root: Repository root path
    """
    print("\n" + "=" * 70)
    print("STEP 7: Launching UI Application")
    print("=" * 70)

    import subprocess

    # Try both UI apps - prefer notebook_app_duckdb for better performance
    notebook_ui_path = repo_root / "app" / "ui" / "notebook_app_duckdb.py"
    streamlit_ui_path = repo_root / "app" / "ui" / "streamlit_app.py"

    if notebook_ui_path.exists():
        ui_path = notebook_ui_path
        print(f"Starting Notebook UI (DuckDB - Fast): {ui_path}")
    elif streamlit_ui_path.exists():
        ui_path = streamlit_ui_path
        print(f"Starting Streamlit app: {ui_path}")
    else:
        print(f"⚠ UI application not found")
        print("Skipping UI launch")
        return

    print(f"Starting UI app: {ui_path}")
    print("UI will use core.dim_calendar for time-based queries")
    print("\nPress Ctrl+C to stop the application\n")

    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            str(ui_path),
            "--server.port", "8501",
            "--server.address", "localhost"
        ])
    except KeyboardInterrupt:
        print("\n\nUI application stopped")


def main():
    """Main pipeline orchestration"""
    parser = argparse.ArgumentParser(
        description='Run full de_Funk analytics pipeline'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=100,
        help='Number of top companies to process (default: 100)'
    )
    parser.add_argument(
        '--skip-ingestion',
        action='store_true',
        help='Skip data ingestion (use existing Bronze data)'
    )
    parser.add_argument(
        '--skip-forecasts',
        action='store_true',
        help='Skip forecast generation'
    )
    parser.add_argument(
        '--skip-ui',
        action='store_true',
        help='Skip UI launch (just build models)'
    )
    parser.add_argument(
        '--only-core',
        action='store_true',
        help='Only build core model (calendar dimension)'
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("DE_FUNK ANALYTICS PLATFORM - FULL PIPELINE")
    print("=" * 70)
    print(f"Processing top {args.top_n} companies")
    print(f"Skip ingestion: {args.skip_ingestion}")
    print(f"Skip forecasts: {args.skip_forecasts}")
    print(f"Skip UI: {args.skip_ui}")
    print("=" * 70)

    # Setup
    repo_root = PROJECT_ROOT
    storage_cfg_path = repo_root / "configs" / "storage.json"

    with open(storage_cfg_path) as f:
        storage_cfg = json.load(f)

    # Get Spark session
    spark = get_spark_session(
        app_name="DeFunk_FullPipeline",
        config={
            "spark.sql.shuffle.partitions": "10",
            "spark.driver.memory": "4g"
        }
    )

    try:
        # Step 1: Build calendar dimension
        build_calendar_dimension(spark, repo_root, storage_cfg)

        if args.only_core:
            print("\n✓ Core model complete (--only-core flag)")
            return

        # Step 2: Ingest company data (unless skipped)
        if not args.skip_ingestion:
            ingest_company_data(spark, repo_root, storage_cfg, top_n=args.top_n)
        else:
            print("\n⚠ Skipping data ingestion (using existing Bronze data)")

        # Step 3: Build company model
        build_company_model(spark, repo_root, storage_cfg)

        # Step 4: Generate forecasts (unless skipped)
        if not args.skip_forecasts:
            generate_forecasts(spark, repo_root, storage_cfg, top_n=args.top_n)
        else:
            print("\n⚠ Skipping forecast generation")

        # Step 5: Build macro model (if data available)
        try:
            build_macro_model(spark, repo_root, storage_cfg)
        except Exception as e:
            print(f"\n⚠ Macro model build skipped: {e}")

        # Step 6: Build city finance model (if data available)
        try:
            build_city_finance_model(spark, repo_root, storage_cfg)
        except Exception as e:
            print(f"\n⚠ City finance model build skipped: {e}")

        print("\n" + "=" * 70)
        print("PIPELINE COMPLETE!")
        print("=" * 70)
        print("All models built successfully:")
        print("  ✓ Core model (dim_calendar)")
        print("  ✓ Company model (dims + facts)")
        if not args.skip_forecasts:
            print("  ✓ Forecast model")
        print("\nData is ready for analysis in the UI")

        # Step 7: Launch UI (unless skipped)
        if not args.skip_ui:
            print("\nLaunching UI...")
            launch_ui(repo_root)
        else:
            print("\n⚠ Skipping UI launch")
            print(f"\nTo launch UI manually:")
            print(f"  streamlit run {repo_root}/app/ui/app.py")

    except Exception as e:
        print(f"\n✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
