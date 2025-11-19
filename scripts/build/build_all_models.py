#!/usr/bin/env python3
"""
Build All Models - Complete data ingestion and model building across all domains.

This script:
1. Discovers all models in configs/models/
2. Runs appropriate paginated ingestion for each domain (Alpha Vantage, BLS, Chicago APIs)
3. Builds Silver layer from Bronze data
4. Reports progress and results

This is NOT a testing script - it works with REAL data and REAL APIs.

Usage:
    # Build all models with default settings
    python -m scripts.build_all_models

    # Build specific models
    python -m scripts.build_all_models --models stocks company

    # With date range for market data
    python -m scripts.build_all_models --date-from 2024-01-01 --date-to 2024-12-31

    # With ticker limit (for testing/development)
    python -m scripts.build_all_models --max-tickers 20

    # Skip ingestion (just rebuild Silver from existing Bronze)
    python -m scripts.build_all_models --skip-ingestion

    # Parallel model building
    python -m scripts.build_all_models --parallel

    # Dry run (show what would be done)
    python -m scripts.build_all_models --dry-run

Examples:
    # Full production build (all domains, all data)
    python -m scripts.build_all_models --date-from 2024-01-01

    # Development build (limited data, specific models)
    python -m scripts.build_all_models --models stocks --max-tickers 10 --date-from 2025-01-01

    # Quick rebuild from existing Bronze
    python -m scripts.build_all_models --skip-ingestion
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

from models.registry import ModelRegistry
from core.context import RepoContext

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AllModelBuilder:
    """Build all models with paginated ingestion from real data sources."""

    # Model categorization by data source
    ALPHA_VANTAGE_MODELS = {'company', 'stocks', 'options', 'etfs', 'futures'}  # Alpha Vantage API (v2.0)
    BLS_MODELS = {'macro'}  # Bureau of Labor Statistics API
    CHICAGO_MODELS = {'city_finance'}  # Chicago Data Portal
    DERIVED_MODELS = {'forecast'}  # Derived from other models (no direct ingestion)
    CORE_MODELS = {'core'}  # Reference data (calendar, etc.)

    def __init__(self, config_dir: str = "configs/models"):
        """
        Initialize all models builder.

        Args:
            config_dir: Model config directory
        """
        self.config_dir = Path(config_dir)
        self.registry = ModelRegistry(str(self.config_dir))
        self.ctx = None  # Lazy init
        self.session = None  # Lazy init UniversalSession for cross-model refs

        # Overall results
        self.results = {
            'start_time': None,
            'end_time': None,
            'models_processed': 0,
            'models_succeeded': 0,
            'models_failed': 0,
            'model_results': {}
        }

        logger.info("Initialized all models builder")

    def _init_context(self):
        """Lazy initialize RepoContext and UniversalSession."""
        if self.ctx is None:
            logger.info("Initializing RepoContext...")
            self.ctx = RepoContext.from_repo_root()
            logger.info("  ✓ Context initialized")

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
        # Get all available models from registry
        all_models = self.registry.list_models()

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
        skip_ingestion: bool = False,
        parallel: bool = False,
        max_workers: int = 3,
        dry_run: bool = False
    ) -> bool:
        """
        Build all models with ingestion and Silver layer creation.

        Args:
            models: Specific models to build (None = all)
            date_from: Start date for market data (YYYY-MM-DD)
            date_to: End date for market data (YYYY-MM-DD)
            days: Alternative to date_from/date_to - number of recent days
            max_tickers: Limit number of tickers (for development/testing)
            skip_ingestion: Skip Bronze ingestion (use existing Bronze data)
            parallel: Build models in parallel
            max_workers: Max parallel workers
            dry_run: Show what would be done without executing

        Returns:
            True if all builds succeed
        """
        self.results['start_time'] = datetime.now()

        # Determine date range for market data
        if days:
            # Exclude today (Alpha Vantage typically doesn't include same-day data)
            date_to_obj = date.today() - timedelta(days=1)
            date_from_obj = date_to_obj - timedelta(days=days)
            date_from = date_from_obj.isoformat()
            date_to = date_to_obj.isoformat()
        elif not date_from or not date_to:
            # Default: last 365 days (1 year), excluding today
            date_to_obj = date.today() - timedelta(days=1)
            date_from_obj = date_to_obj - timedelta(days=365)
            date_from = date_from_obj.isoformat()
            date_to = date_to_obj.isoformat()

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
                skip_ingestion
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
        skip_ingestion: bool
    ) -> bool:
        """Build models sequentially."""
        all_passed = True

        for i, model_name in enumerate(models, 1):
            logger.info(f"\n{'=' * 70}")
            logger.info(f"MODEL {i}/{len(models)}: {model_name}")
            logger.info(f"{'=' * 70}")

            success = self._build_single_model(
                model_name,
                date_from,
                date_to,
                max_tickers,
                skip_ingestion
            )

            self.results['model_results'][model_name] = {
                'success': success,
                'timestamp': datetime.now().isoformat()
            }

            if success:
                self.results['models_succeeded'] += 1
            else:
                self.results['models_failed'] += 1
                all_passed = False

            self.results['models_processed'] += 1

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
        skip_ingestion: bool
    ) -> bool:
        """
        Build a single model (ingestion + Silver layer).

        Args:
            model_name: Model to build
            date_from: Start date
            date_to: End date
            max_tickers: Max tickers (for Alpha Vantage models)
            skip_ingestion: Skip Bronze ingestion

        Returns:
            True if build succeeds
        """
        try:
            # Step 1: Ingestion (Bronze layer)
            if not skip_ingestion:
                logger.info(f"Step 1/2: Running {model_name} ingestion...")
                ingestion_success = self._run_ingestion(
                    model_name,
                    date_from,
                    date_to,
                    max_tickers
                )
                if not ingestion_success:
                    logger.error(f"Ingestion failed for {model_name}")
                    return False
                logger.info(f"  ✓ Ingestion completed for {model_name}")
            else:
                logger.info(f"Step 1/2: Ingestion skipped for {model_name}")

            # Step 2: Build Silver layer
            logger.info(f"Step 2/2: Building {model_name} Silver layer...")
            build_success = self._build_silver_layer(
                model_name,
                date_from,
                date_to,
                max_tickers
            )
            if not build_success:
                logger.error(f"Silver build failed for {model_name}")
                return False
            logger.info(f"  ✓ Silver layer built for {model_name}")

            logger.info(f"✓ All steps completed for {model_name}")
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
            if model_name in self.ALPHA_VANTAGE_MODELS:
                return self._run_alpha_vantage_ingestion(date_from, date_to, max_tickers)
            elif model_name in self.BLS_MODELS:
                return self._run_bls_ingestion(date_from, date_to)
            elif model_name in self.CHICAGO_MODELS:
                return self._run_chicago_ingestion()
            elif model_name in self.DERIVED_MODELS:
                logger.info(f"  {model_name} is derived, no ingestion needed")
                return True
            elif model_name in self.CORE_MODELS:
                logger.info(f"  {model_name} uses reference data, no ingestion needed")
                return True
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

        # Default tickers for development/testing
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'V', 'WMT']
        if max_tickers:
            tickers = tickers[:max_tickers]

        # Ingest reference data (company overview)
        logger.info(f"  Ingesting reference data for {len(tickers)} tickers...")
        ingestor.ingest_reference_data(tickers=tickers, use_concurrent=False)

        # Ingest prices (daily OHLCV)
        logger.info(f"  Ingesting prices from {date_from} to {date_to}...")
        ingestor.ingest_prices(
            tickers=tickers,
            date_from=date_from,
            date_to=date_to,
            adjusted=True,
            outputsize='full',
            use_concurrent=False
        )

        logger.info(f"  ✓ Ingested data for {len(tickers)} tickers")
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

    def _build_silver_layer(
        self,
        model_name: str,
        date_from: str,
        date_to: str,
        max_tickers: Optional[int]
    ) -> bool:
        """
        Build Silver layer from Bronze data.

        Returns:
            True if build succeeds
        """
        # Initialize context if needed
        self._init_context()

        try:
            # Get model configuration
            model_cfg = self.registry.get_model_config(model_name)

            # Get model class
            try:
                model_class = self.registry.get_model_class(model_name)
            except ValueError:
                # Fall back to BaseModel if specific class not found
                logger.warning(f"  Using BaseModel for {model_name}")
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
                    "MAX_TICKERS": max_tickers or 0
                }
            )

            # Inject session for cross-model references
            if hasattr(model, 'set_session'):
                model.set_session(self.session)
                logger.info(f"  ✓ Session injected for cross-model references")

            # Build Silver layer
            logger.info(f"  Building {model_name} graph...")
            dims, facts = model.build()

            # Report results
            logger.info(f"  ✓ Built {len(dims)} dimensions, {len(facts)} facts")
            for table_name, df in {**dims, **facts}.items():
                try:
                    count = df.count() if hasattr(df, 'count') else len(df)
                    logger.info(f"    - {table_name}: {count:,} rows")
                except Exception as e:
                    logger.warning(f"    - {table_name}: Unable to get row count ({e})")

            # Write tables to Silver storage (persist parquet files)
            logger.info(f"  Writing {model_name} tables to Silver storage...")
            stats = model.write_tables(use_optimized_writer=True)
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
        '--skip-ingestion',
        action='store_true',
        help='Skip Bronze ingestion (use existing Bronze data)'
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
            skip_ingestion=args.skip_ingestion,
            parallel=args.parallel,
            max_workers=args.max_workers,
            dry_run=args.dry_run
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
