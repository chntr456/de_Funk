#!/usr/bin/env python3
"""
Build All Models - Build Silver layer from Bronze data.

This script builds Silver dimensional models from existing Bronze data.
It does NOT handle data ingestion - use run_full_pipeline.py for ingestion.

Separation of Concerns:
- run_full_pipeline.py: Orchestrates ingestion + build + forecast (full pipeline)
- build_all_models.py: Only builds Silver layer from Bronze data (this script)
- run_forecasts.py: Only runs forecasts on Silver data

This script:
1. Discovers all models in configs/models/
2. Builds Silver layer from existing Bronze data
3. Reports progress with minimal single-line status updates

Usage:
    # Build all models from existing Bronze data
    python -m scripts.build.build_all_models

    # Build specific models
    python -m scripts.build.build_all_models --models stocks company

    # With verbose logging (instead of progress bar)
    python -m scripts.build.build_all_models --verbose

    # Dry run (show what would be done)
    python -m scripts.build.build_all_models --dry-run

Examples:
    # Full production build from Bronze
    python -m scripts.build.build_all_models

    # Development build (specific models)
    python -m scripts.build.build_all_models --models stocks company

    # See detailed logging
    python -m scripts.build.build_all_models --verbose
"""

from __future__ import annotations

import sys
from pathlib import Path
import argparse
from typing import List, Dict, Optional, Set
import logging
from datetime import datetime, date, timedelta
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.model_loader import ModelConfigLoader
from core.context import RepoContext
from datapipelines.base.progress_tracker import StepProgressTracker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AllModelBuilder:
    """Build all models with paginated ingestion from real data sources."""

    # Model categorization by data source
    ALPHA_VANTAGE_MODELS = {'company', 'stocks'}  # v2.0 implemented models only
    ALPHA_VANTAGE_SKELETON = {'options', 'etfs', 'futures'}  # v2.0 planned (not implemented)
    BLS_MODELS = {'macro'}  # Bureau of Labor Statistics API
    CHICAGO_MODELS = {'city_finance'}  # Chicago Data Portal
    DERIVED_MODELS = {'forecast'}  # Derived from other models (no direct ingestion)
    CORE_MODELS = {'core'}  # Reference data (calendar, etc.)
    LEGACY_MODELS = {'equity', 'corporate', 'etf'}  # v1.x deprecated models

    def __init__(self, config_dir: str = "configs/models"):
        """
        Initialize all models builder.

        Args:
            config_dir: Model config directory
        """
        self.config_dir = Path(config_dir)
        self.loader = ModelConfigLoader(self.config_dir)
        self.ctx = None  # Lazy init
        self.session = None  # Lazy init UniversalSession for cross-model refs

        # Track ingestion state (avoid re-ingesting same data source)
        self.ingestion_completed = set()

        # Overall results
        self.results = {
            'start_time': None,
            'end_time': None,
            'models_processed': 0,
            'models_succeeded': 0,
            'models_failed': 0,
            'model_results': {}
        }

        logger.info("Initialized all models builder (v2.0 - ModelConfigLoader)")

    def _init_context(self):
        """Lazy initialize RepoContext and UniversalSession."""
        if self.ctx is None:
            logger.info("Initializing RepoContext with Spark (required for data pipelines)...")
            # IMPORTANT: Use Spark for all data processing (facets + model builds)
            self.ctx = RepoContext.from_repo_root(connection_type="spark")
            logger.info("  ✓ Context initialized (Spark)")

            # Initialize UniversalSession for cross-model references
            from models.api.session import UniversalSession
            self.session = UniversalSession(
                connection=self.ctx.connection,  # Use SparkConnection wrapper, not raw spark
                storage_cfg=self.ctx.storage,
                repo_root=repo_root,
                models=None  # Don't pre-load, load on demand
            )
            logger.info("  ✓ Universal session initialized")

    def discover_models(self, include_models: Optional[List[str]] = None) -> List[str]:
        """
        Discover all models in config directory.

        Args:
            include_models: Specific models to build (None = all)

        Returns:
            List of model names
        """
        # Get all available models from loader
        all_models = self.loader.list_models()

        # Remove duplicates and skeleton/legacy models
        all_models = list(set(all_models))  # Deduplicate
        all_models = [m for m in all_models if m not in self.ALPHA_VANTAGE_SKELETON]  # Remove skeletons
        all_models = [m for m in all_models if m not in self.LEGACY_MODELS]  # Remove legacy

        if include_models:
            # Filter to specified models
            models = [m for m in all_models if m in include_models]
            missing = set(include_models) - set(models)
            if missing:
                logger.warning(f"Models not found: {missing}")
        else:
            models = all_models

        # Sort by dependency order
        # Core models first, then data models, then derived models
        def sort_key(model_name):
            if model_name in self.CORE_MODELS:
                return 0
            elif model_name in self.ALPHA_VANTAGE_MODELS:
                return 1
            elif model_name in self.BLS_MODELS:
                return 2
            elif model_name in self.CHICAGO_MODELS:
                return 3
            elif model_name in self.DERIVED_MODELS:
                return 4
            else:
                return 5

        models_sorted = sorted(models, key=sort_key)

        logger.info(f"Discovered {len(models_sorted)} model(s): {', '.join(models_sorted)}")
        return models_sorted

    def build_all_models(
        self,
        models: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        days: Optional[int] = None,
        max_tickers: Optional[int] = None,
        tickers: Optional[List[str]] = None,
        skip_ingestion: bool = False,
        parallel: bool = False,
        max_workers: int = 3,
        dry_run: bool = False,
        use_bulk_discovery: bool = True,
        skip_reference_refresh: bool = False,
        outputsize: str = "full",
        use_concurrent: bool = True,
        minimal_progress: bool = True
    ) -> bool:
        """
        Build all models with ingestion and Silver layer creation.

        Args:
            models: Specific models to build (None = all)
            date_from: Start date for market data (YYYY-MM-DD)
            date_to: End date for market data (YYYY-MM-DD)
            days: Alternative to date_from/date_to - number of recent days
            max_tickers: Limit number of tickers (for development/testing)
            tickers: Specific ticker symbols to ingest (overrides bulk discovery and max_tickers)
            skip_ingestion: Skip Bronze ingestion (use existing Bronze data)
            parallel: Build models in parallel
            max_workers: Max parallel workers
            dry_run: Show what would be done without executing
            use_bulk_discovery: Use bulk endpoints to discover all available tickers (default: True)
            skip_reference_refresh: Skip reference data refresh (saves ~50% time for daily updates)
            outputsize: 'compact' (100 days) or 'full' (20+ years) for price data
            use_concurrent: Use concurrent API requests (premium tier only, default: True)
            minimal_progress: Use clean single-line progress bar (default: True). False for verbose logging.

        Returns:
            True if all builds succeed
        """
        self.results['start_time'] = datetime.now()
        self.use_bulk_discovery = use_bulk_discovery
        self.skip_reference_refresh = skip_reference_refresh
        self.outputsize = outputsize
        self.use_concurrent = use_concurrent
        self.tickers = tickers  # Explicit ticker list (overrides discovery)

        # Determine date range for market data
        if days:
            # Use days parameter: calculate date_from and date_to
            date_to_obj = date.today() - timedelta(days=1)  # Exclude today
            date_from_obj = date_to_obj - timedelta(days=days)
            date_from = date_from_obj.isoformat()
            date_to = date_to_obj.isoformat()
        else:
            # Use provided dates or defaults
            if not date_to:
                # Default date_to: yesterday
                date_to = (date.today() - timedelta(days=1)).isoformat()
            if not date_from:
                # Default date_from: 1 year before date_to
                date_to_obj = date.fromisoformat(date_to)
                date_from = (date_to_obj - timedelta(days=365)).isoformat()

        # Discover models
        models_to_build = self.discover_models(models)

        if not models_to_build:
            logger.error("No models found to build")
            return False

        logger.info("=" * 70)
        logger.info("BUILDING ALL MODELS")
        logger.info("=" * 70)
        logger.info(f"Models: {len(models_to_build)}")
        logger.info(f"Date range: {date_from} to {date_to}")
        if max_tickers:
            logger.info(f"Max tickers: {max_tickers}")
        logger.info(f"Skip ingestion: {skip_ingestion}")
        logger.info(f"Parallel: {parallel}")
        logger.info(f"Dry run: {dry_run}")

        if dry_run:
            logger.info("\n" + "=" * 70)
            logger.info("DRY RUN - No changes will be made")
            logger.info("=" * 70)
            for model_name in models_to_build:
                source_type = self._get_source_type(model_name)
                logger.info(f"\nModel: {model_name}")
                logger.info(f"  Source type: {source_type}")
                logger.info(f"  Ingestion: {'Skipped' if skip_ingestion else source_type}")
                logger.info(f"  Silver build: Yes")
            return True

        # Store minimal_progress preference
        self.minimal_progress = minimal_progress

        # Build each model
        if parallel and len(models_to_build) > 1:
            success = self._build_models_parallel(
                models_to_build,
                date_from,
                date_to,
                max_tickers,
                skip_ingestion,
                max_workers
            )
        else:
            success = self._build_models_sequential(
                models_to_build,
                date_from,
                date_to,
                max_tickers,
                skip_ingestion,
                minimal_progress=minimal_progress
            )

        self.results['end_time'] = datetime.now()
        self._print_summary()

        return success

    def _build_models_sequential(
        self,
        models: List[str],
        date_from: str,
        date_to: str,
        max_tickers: Optional[int],
        skip_ingestion: bool,
        minimal_progress: bool = True
    ) -> bool:
        """Build models sequentially with progress tracking."""
        all_passed = True

        # Initialize progress tracker
        tracker = StepProgressTracker(
            total_steps=len(models),
            description="Building models",
            silent=not minimal_progress
        )

        for i, model_name in enumerate(models, 1):
            # Update progress tracker
            tracker.update(i, f"Building {model_name}...")

            success = self._build_single_model(
                model_name,
                date_from,
                date_to,
                max_tickers,
                skip_ingestion,
                minimal_progress=minimal_progress
            )

            self.results['model_results'][model_name] = {
                'success': success,
                'timestamp': datetime.now().isoformat()
            }

            if success:
                self.results['models_succeeded'] += 1
                tracker.step_complete(f"{model_name} ✓")
            else:
                self.results['models_failed'] += 1
                tracker.step_complete(f"{model_name} ✗")
                all_passed = False

            self.results['models_processed'] += 1

        # Final summary
        tracker.finish(success=all_passed)

        return all_passed

    def _build_models_parallel(
        self,
        models: List[str],
        date_from: str,
        date_to: str,
        max_tickers: Optional[int],
        skip_ingestion: bool,
        max_workers: int
    ) -> bool:
        """Build models in parallel."""
        logger.info(f"\nRunning builds in parallel with {max_workers} workers...")

        all_passed = True
        futures = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all model builds
            for model_name in models:
                future = executor.submit(
                    self._build_single_model,
                    model_name,
                    date_from,
                    date_to,
                    max_tickers,
                    skip_ingestion
                )
                futures[future] = model_name

            # Collect results as they complete
            for future in as_completed(futures):
                model_name = futures[future]
                try:
                    success = future.result()

                    self.results['model_results'][model_name] = {
                        'success': success,
                        'timestamp': datetime.now().isoformat()
                    }

                    if success:
                        self.results['models_succeeded'] += 1
                        logger.info(f"✓ {model_name} - SUCCESS")
                    else:
                        self.results['models_failed'] += 1
                        all_passed = False
                        logger.error(f"✗ {model_name} - FAILED")

                    self.results['models_processed'] += 1

                except Exception as e:
                    logger.error(f"✗ {model_name} - ERROR: {e}")
                    self.results['model_results'][model_name] = {
                        'success': False,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
                    self.results['models_failed'] += 1
                    self.results['models_processed'] += 1
                    all_passed = False

        return all_passed

    def _build_single_model(
        self,
        model_name: str,
        date_from: str,
        date_to: str,
        max_tickers: Optional[int],
        skip_ingestion: bool = True,  # Ignored - ingestion handled separately
        minimal_progress: bool = True
    ) -> bool:
        """
        Build a single model's Silver layer from Bronze data.

        Note: Ingestion is handled separately by run_full_pipeline.py.
        This script only builds Silver layer from existing Bronze data.

        Args:
            model_name: Model to build
            date_from: Start date
            date_to: End date
            max_tickers: Max tickers (for Alpha Vantage models)
            skip_ingestion: Ignored (kept for API compatibility)
            minimal_progress: If True, suppress verbose logging (for clean progress display)

        Returns:
            True if build succeeds
        """
        try:
            # Build Silver layer from Bronze data
            if not minimal_progress:
                logger.info(f"Building {model_name} Silver layer...")
            build_success = self._build_silver_layer(
                model_name,
                date_from,
                date_to,
                max_tickers,
                minimal_progress=minimal_progress
            )
            if not build_success:
                logger.error(f"Silver build failed for {model_name}")
                return False
            if not minimal_progress:
                logger.info(f"  ✓ Silver layer built for {model_name}")

            return True

        except Exception as e:
            logger.error(f"Error building {model_name}: {e}", exc_info=True)
            return False

    def _get_source_type(self, model_name: str) -> str:
        """Get the data source type for a model."""
        if model_name in self.ALPHA_VANTAGE_MODELS:
            return "Alpha Vantage API"
        elif model_name in self.BLS_MODELS:
            return "BLS API"
        elif model_name in self.CHICAGO_MODELS:
            return "Chicago Data Portal"
        elif model_name in self.DERIVED_MODELS:
            return "Derived (no ingestion)"
        elif model_name in self.CORE_MODELS:
            return "Core/Reference"
        else:
            return "Unknown"

    def _run_ingestion(
        self,
        model_name: str,
        date_from: str,
        date_to: str,
        max_tickers: Optional[int]
    ) -> bool:
        """
        Run data ingestion for a model.

        Returns:
            True if ingestion succeeds
        """
        # Initialize context if needed
        self._init_context()

        try:
            # Check if ingestion for this data source already completed
            if model_name in self.ALPHA_VANTAGE_MODELS:
                if 'alpha_vantage' in self.ingestion_completed:
                    logger.info(f"  Alpha Vantage ingestion already completed (shared with other models), skipping...")
                    return True
                success = self._run_alpha_vantage_ingestion(date_from, date_to, max_tickers)
                if success:
                    self.ingestion_completed.add('alpha_vantage')
                return success
            elif model_name in self.BLS_MODELS:
                if 'bls' in self.ingestion_completed:
                    logger.info(f"  BLS ingestion already completed, skipping...")
                    return True
                success = self._run_bls_ingestion(date_from, date_to)
                if success:
                    self.ingestion_completed.add('bls')
                return success
            elif model_name in self.CHICAGO_MODELS:
                if 'chicago' in self.ingestion_completed:
                    logger.info(f"  Chicago ingestion already completed, skipping...")
                    return True
                success = self._run_chicago_ingestion()
                if success:
                    self.ingestion_completed.add('chicago')
                return success
            elif model_name in self.DERIVED_MODELS:
                logger.info(f"  {model_name} is derived, no ingestion needed")
                return True
            elif model_name in self.CORE_MODELS:
                if 'calendar_seed' in self.ingestion_completed:
                    logger.info(f"  Calendar seed already generated, skipping...")
                    return True
                success = self._generate_calendar_seed()
                if success:
                    self.ingestion_completed.add('calendar_seed')
                return success
            else:
                logger.warning(f"  Unknown model type: {model_name}, skipping ingestion")
                return True

        except Exception as e:
            logger.error(f"Ingestion failed: {e}", exc_info=True)
            return False

    def _run_alpha_vantage_ingestion(
        self,
        date_from: str,
        date_to: str,
        max_tickers: Optional[int]
    ) -> bool:
        """Run Alpha Vantage API ingestion (v2.0 securities models)."""
        from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

        logger.info("  Running Alpha Vantage ingestion...")
        ingestor = AlphaVantageIngestor(
            alpha_vantage_cfg=self.ctx.get_api_config('alpha_vantage'),
            storage_cfg=self.ctx.storage,
            spark=self.ctx.spark
        )

        # Run full ingestion using run_all method
        # Note: Premium tier supports concurrent requests (75 calls/min)
        # tickers: If provided, uses explicit list (no discovery)
        # use_bulk_listing: Discovers ALL tickers via LISTING_STATUS (1 call), then gets full data
        # skip_reference_refresh: Skip OVERVIEW calls for daily updates (saves ~50% time)
        # outputsize: 'compact' (100 days) for daily updates, 'full' (20+ years) for initial load
        # use_concurrent: Concurrent requests (premium: True, free: False)
        ingested_tickers = ingestor.run_all(
            tickers=self.tickers,  # Explicit ticker list (overrides discovery if provided)
            date_from=date_from,
            date_to=date_to,
            max_tickers=max_tickers,
            use_concurrent=self.use_concurrent,  # Controlled via --no-concurrent flag
            use_bulk_listing=self.use_bulk_discovery,  # Bulk discovery enabled by default
            skip_reference_refresh=self.skip_reference_refresh,  # Skip fundamentals for daily updates
            outputsize=self.outputsize  # compact for daily updates, full for initial load
        )

        logger.info(f"  ✓ Ingested data for {len(ingested_tickers)} tickers")
        return True

    def _run_bls_ingestion(self, date_from: str, date_to: str) -> bool:
        """Run BLS API ingestion (Macro model)."""
        # TODO: Implement BLS ingestion
        # This would use datapipelines.providers.bls.bls_ingestor
        logger.info("  BLS ingestion not yet implemented, skipping...")
        return True

    def _run_chicago_ingestion(self) -> bool:
        """Run Chicago Data Portal ingestion (City Finance model)."""
        # TODO: Implement Chicago ingestion
        # This would use datapipelines.providers.chicago.chicago_ingestor
        logger.info("  Chicago ingestion not yet implemented, skipping...")
        return True

    def _generate_calendar_seed(self) -> bool:
        """Generate calendar seed data for core model."""
        from models.implemented.core.builders.calendar_builder import build_calendar_table

        # Initialize context if needed
        self._init_context()

        try:
            # Load core model config to get calendar generation settings
            core_cfg = self.loader.load_model_config('core')
            calendar_config = core_cfg.get('calendar_config', {})

            # Get calendar generation parameters
            start_date = calendar_config.get('start_date', '2000-01-01')
            end_date = calendar_config.get('end_date', '2050-12-31')
            fiscal_year_start_month = calendar_config.get('fiscal_year_start_month', 1)

            # Determine output path
            bronze_root = Path(self.ctx.storage.get('bronze_root', 'storage/bronze'))
            calendar_seed_path = bronze_root / 'calendar_seed'

            logger.info(f"  Generating calendar seed data...")
            logger.info(f"    Date range: {start_date} to {end_date}")
            logger.info(f"    Fiscal year starts: Month {fiscal_year_start_month}")
            logger.info(f"    Output path: {calendar_seed_path}")

            # Build calendar table
            build_calendar_table(
                spark=self.ctx.spark,
                output_path=str(calendar_seed_path),
                start_date=start_date,
                end_date=end_date,
                fiscal_year_start_month=fiscal_year_start_month
            )

            logger.info(f"  ✓ Calendar seed data generated successfully")
            return True

        except Exception as e:
            logger.error(f"  ✗ Calendar seed generation failed: {e}", exc_info=True)
            return False

    def _build_silver_layer(
        self,
        model_name: str,
        date_from: str,
        date_to: str,
        max_tickers: Optional[int],
        minimal_progress: bool = True
    ) -> bool:
        """
        Build Silver layer from Bronze data.

        Args:
            model_name: Model to build
            date_from: Start date
            date_to: End date
            max_tickers: Max tickers limit
            minimal_progress: If True, suppress verbose logging

        Returns:
            True if build succeeds
        """
        # Initialize context if needed
        self._init_context()

        try:
            # Get model configuration using ModelConfigLoader
            model_cfg = self.loader.load_model_config(model_name)

            # Get model class (v2.0 models)
            model_class = None
            if model_name == 'company':
                from models.implemented.company.model import CompanyModel
                model_class = CompanyModel
            elif model_name == 'stocks':
                from models.implemented.stocks.model import StocksModel
                model_class = StocksModel
            elif model_name == 'options':
                from models.implemented.options.model import OptionsModel
                model_class = OptionsModel
            elif model_name == 'etfs':
                from models.implemented.etfs.model import ETFsModel
                model_class = ETFsModel
            elif model_name == 'futures':
                from models.implemented.futures.model import FuturesModel
                model_class = FuturesModel
            elif model_name == 'core':
                from models.implemented.core.model import CoreModel
                model_class = CoreModel
            else:
                # Fall back to BaseModel for other models
                if not minimal_progress:
                    logger.warning(f"  No specific model class for {model_name}, using BaseModel")
                from models.base.model import BaseModel
                model_class = BaseModel

            # Instantiate model
            model = model_class(
                connection=self.ctx.connection,  # Use SparkConnection wrapper
                storage_cfg=self.ctx.storage,
                model_cfg=model_cfg,
                params={
                    "DATE_FROM": date_from,
                    "DATE_TO": date_to,
                    "UNIVERSE_SIZE": max_tickers or 0
                }
            )

            # Inject session for cross-model references
            if hasattr(model, 'set_session'):
                model.set_session(self.session)
                if not minimal_progress:
                    logger.info(f"  ✓ Session injected for cross-model references")

            # Build Silver layer
            if not minimal_progress:
                logger.info(f"  Building {model_name} graph...")
            dims, facts = model.build()

            # Report results (only in verbose mode)
            if not minimal_progress:
                logger.info(f"  ✓ Built {len(dims)} dimensions, {len(facts)} facts")
                for table_name, df in {**dims, **facts}.items():
                    try:
                        count = df.count() if hasattr(df, 'count') else len(df)
                        logger.info(f"    - {table_name}: {count:,} rows")
                    except Exception as e:
                        logger.warning(f"    - {table_name}: Unable to get row count ({e})")

            # Write tables to Silver storage (persist parquet files)
            if not minimal_progress:
                logger.info(f"  Writing {model_name} tables to Silver storage...")
            stats = model.write_tables(use_optimized_writer=True)
            if not minimal_progress:
                logger.info(f"  ✓ Tables written to Silver layer")

            return True

        except Exception as e:
            logger.error(f"Silver build failed: {e}", exc_info=True)
            return False

    def _print_summary(self):
        """Print build summary."""
        logger.info("\n" + "=" * 70)
        logger.info("ALL MODELS BUILD SUMMARY")
        logger.info("=" * 70)

        # Timing
        start = self.results['start_time']
        end = self.results['end_time']
        if start and end:
            duration = (end - start).total_seconds()
            logger.info(f"\nTotal duration: {duration:.2f}s")

        # Overall stats
        logger.info(f"\nModels processed: {self.results['models_processed']}")
        logger.info(f"Succeeded: {self.results['models_succeeded']}")
        logger.info(f"Failed: {self.results['models_failed']}")

        # Per-model results
        logger.info("\nPer-model results:")
        for model_name, result in self.results['model_results'].items():
            status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
            error = f" - {result.get('error', '')}" if 'error' in result else ""
            logger.info(f"  {status} - {model_name}{error}")

        # Overall result
        logger.info("\n" + "=" * 70)
        if self.results['models_failed'] == 0:
            logger.info("✓ ALL MODELS BUILT SUCCESSFULLY")
        else:
            logger.info(f"✗ {self.results['models_failed']} MODEL(S) FAILED")
        logger.info("=" * 70)

    def save_results(self, output_file: str):
        """
        Save results to JSON file.

        Args:
            output_file: Output file path
        """
        # Make results JSON serializable
        serializable_results = {
            'start_time': self.results['start_time'].isoformat() if self.results['start_time'] else None,
            'end_time': self.results['end_time'].isoformat() if self.results['end_time'] else None,
            'models_processed': self.results['models_processed'],
            'models_succeeded': self.results['models_succeeded'],
            'models_failed': self.results['models_failed'],
            'model_results': self.results['model_results']
        }

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(serializable_results, f, indent=2)

        logger.info(f"\nResults saved to: {output_path}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Build all models with paginated ingestion from real data sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--models',
        nargs='+',
        help='Specific models to build (default: all models)'
    )

    parser.add_argument(
        '--date-from',
        help='Start date for market data (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--date-to',
        help='End date for market data (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--days',
        type=int,
        help='Number of recent days (alternative to --date-from/--date-to)'
    )

    parser.add_argument(
        '--max-tickers',
        type=int,
        help='Limit number of tickers for development/testing (Alpha Vantage models only)'
    )

    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Specific ticker symbols to ingest (e.g., --tickers AAPL MSFT ABI). Overrides bulk discovery and max-tickers.'
    )

    parser.add_argument(
        '--skip-ingestion',
        action='store_true',
        default=True,  # Ingestion now handled separately by run_full_pipeline.py
        help='(Deprecated) Ingestion is handled separately. This script only builds Silver layer.'
    )

    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Build models in parallel'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=3,
        help='Max parallel workers (default: 3)'
    )

    parser.add_argument(
        '--output',
        help='Save results to JSON file'
    )

    parser.add_argument(
        '--config-dir',
        default='configs/models',
        help='Model config directory (default: configs/models)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without executing'
    )

    parser.add_argument(
        '--no-bulk-discovery',
        action='store_true',
        help='Disable bulk ticker discovery (uses default tickers instead of discovering all available)'
    )

    parser.add_argument(
        '--skip-reference-refresh',
        action='store_true',
        help='Skip reference data refresh (OVERVIEW endpoint) - saves ~50%% time for daily updates'
    )

    parser.add_argument(
        '--outputsize',
        choices=['compact', 'full'],
        default='full',
        help='Price data size: compact (100 days) or full (20+ years). Use compact for daily updates.'
    )

    parser.add_argument(
        '--no-concurrent',
        action='store_true',
        help='Disable concurrent API requests (use for free tier to respect rate limits)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show verbose output (detailed logging instead of progress bar)'
    )

    args = parser.parse_args()

    try:
        # Initialize builder
        builder = AllModelBuilder(config_dir=args.config_dir)

        # Build all models
        success = builder.build_all_models(
            models=args.models,
            date_from=args.date_from,
            date_to=args.date_to,
            days=args.days,
            max_tickers=args.max_tickers,
            tickers=args.tickers,  # Explicit ticker list (overrides discovery)
            skip_ingestion=args.skip_ingestion,
            parallel=args.parallel,
            max_workers=args.max_workers,
            dry_run=args.dry_run,
            use_bulk_discovery=not args.no_bulk_discovery,  # Enabled by default
            skip_reference_refresh=args.skip_reference_refresh,  # Skip OVERVIEW for daily updates
            outputsize=args.outputsize,  # compact for daily updates, full for initial load
            use_concurrent=not args.no_concurrent,  # Enabled by default (premium tier)
            minimal_progress=not args.verbose  # Use progress bar by default, --verbose for detailed logging
        )

        # Save results if requested
        if args.output:
            builder.save_results(args.output)

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
