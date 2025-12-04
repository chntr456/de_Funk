#!/usr/bin/env python3
"""
Build Silver Layer - Pure model building from existing Bronze data.

This script ONLY builds Silver layer from Bronze. It does NOT ingest data.
For data ingestion, use scripts in scripts/ingest/.

Separation of Concerns:
- scripts/ingest/   → Bronze layer filling (API calls, data ingestion)
- scripts/build/    → Silver layer building (this script)
- scripts/forecast/ → Predictive model building
- run_full_pipeline.py → Orchestrates all of the above

Usage:
    # Build all models from existing Bronze
    python -m scripts.build.build_silver

    # Build specific models
    python -m scripts.build.build_silver --models stocks company

    # With date range
    python -m scripts.build.build_silver --date-from 2024-01-01 --date-to 2024-12-31

    # Dry run
    python -m scripts.build.build_silver --dry-run
"""

from __future__ import annotations

import sys
from pathlib import Path
import argparse
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date, timedelta
import json

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger
from config.model_loader import ModelConfigLoader
from core.context import RepoContext

logger = get_logger(__name__)


class SilverBuilder:
    """
    Pure Silver layer builder - builds models from existing Bronze data.

    This class does NOT do any data ingestion. It assumes Bronze data already exists.
    """

    # Model categorization
    CORE_MODELS = {'core'}  # Foundation models (calendar, etc.)
    ALPHA_VANTAGE_MODELS = {'company', 'stocks'}  # v2.0 implemented models
    ALPHA_VANTAGE_SKELETON = {'options', 'etfs', 'futures'}  # Not yet implemented
    BLS_MODELS = {'macro'}
    CHICAGO_MODELS = {'city_finance'}
    DERIVED_MODELS = {'forecast'}  # Depends on other Silver models
    LEGACY_MODELS = {'equity', 'corporate', 'etf'}  # Deprecated

    def __init__(self, config_dir: str = "configs/models"):
        """Initialize Silver builder."""
        self.config_dir = Path(config_dir)
        self.loader = ModelConfigLoader(self.config_dir)
        self.ctx = None
        self.session = None

        self.results = {
            'start_time': None,
            'end_time': None,
            'models_processed': 0,
            'models_succeeded': 0,
            'models_failed': 0,
            'model_results': {}
        }

        logger.info("SilverBuilder initialized (pure build mode - no ingestion)")

    def _init_context(self):
        """Lazy initialize RepoContext and UniversalSession."""
        if self.ctx is None:
            logger.info("Initializing Spark context for model building...")
            self.ctx = RepoContext.from_repo_root(connection_type="spark")
            logger.info("  ✓ Spark context initialized")

            from models.api.session import UniversalSession
            self.session = UniversalSession(
                connection=self.ctx.connection,
                storage_cfg=self.ctx.storage,
                repo_root=repo_root,
                models=None
            )
            logger.info("  ✓ Universal session initialized")

    def discover_models(self, include_models: Optional[List[str]] = None) -> List[str]:
        """
        Discover available models.

        Args:
            include_models: Specific models to build (None = all)

        Returns:
            List of model names in dependency order
        """
        all_models = self.loader.list_models()

        # Remove skeletons and legacy
        all_models = [m for m in all_models if m not in self.ALPHA_VANTAGE_SKELETON]
        all_models = [m for m in all_models if m not in self.LEGACY_MODELS]
        all_models = list(set(all_models))  # Deduplicate

        if include_models:
            models = [m for m in all_models if m in include_models]
            missing = set(include_models) - set(models)
            if missing:
                logger.warning(f"Models not found: {missing}")
        else:
            models = all_models

        # Sort by dependency order (core first, then data models, then derived)
        def sort_key(model_name):
            if model_name in self.CORE_MODELS:
                return 0
            elif model_name == 'company':
                return 1  # Company before stocks (stocks depends on company)
            elif model_name in self.ALPHA_VANTAGE_MODELS:
                return 2
            elif model_name in self.BLS_MODELS:
                return 3
            elif model_name in self.CHICAGO_MODELS:
                return 4
            elif model_name in self.DERIVED_MODELS:
                return 5
            else:
                return 6

        models_sorted = sorted(models, key=sort_key)
        logger.info(f"Discovered {len(models_sorted)} model(s): {', '.join(models_sorted)}")
        return models_sorted

    def build(
        self,
        models: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_tickers: Optional[int] = None,
        dry_run: bool = False
    ) -> bool:
        """
        Build Silver layer from existing Bronze data.

        Args:
            models: Specific models to build (None = all)
            date_from: Start date filter
            date_to: End date filter
            max_tickers: Universe size limit
            dry_run: Show what would be done

        Returns:
            True if all builds succeed
        """
        self.results['start_time'] = datetime.now()

        # Default date range
        if not date_to:
            date_to = (date.today() - timedelta(days=1)).isoformat()
        if not date_from:
            date_to_obj = date.fromisoformat(date_to)
            date_from = (date_to_obj - timedelta(days=365)).isoformat()

        models_to_build = self.discover_models(models)

        if not models_to_build:
            logger.error("No models found to build")
            return False

        logger.info("=" * 70)
        logger.info("BUILDING SILVER LAYER (from existing Bronze)")
        logger.info("=" * 70)
        logger.info(f"Models: {len(models_to_build)}")
        logger.info(f"Date range: {date_from} to {date_to}")
        if max_tickers:
            logger.info(f"Max tickers: {max_tickers}")
        logger.info(f"Dry run: {dry_run}")

        if dry_run:
            logger.info("\n" + "=" * 70)
            logger.info("DRY RUN - No changes will be made")
            logger.info("=" * 70)
            for model_name in models_to_build:
                logger.info(f"\nWould build: {model_name}")
            return True

        # Build each model
        all_passed = True
        for i, model_name in enumerate(models_to_build, 1):
            logger.info(f"\n{'=' * 70}")
            logger.info(f"MODEL {i}/{len(models_to_build)}: {model_name}")
            logger.info(f"{'=' * 70}")

            success = self._build_model(model_name, date_from, date_to, max_tickers)

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

        self.results['end_time'] = datetime.now()
        self._print_summary()

        return all_passed

    def _build_model(
        self,
        model_name: str,
        date_from: str,
        date_to: str,
        max_tickers: Optional[int]
    ) -> bool:
        """
        Build a single model's Silver layer.

        Args:
            model_name: Model to build
            date_from: Start date
            date_to: End date
            max_tickers: Universe size limit

        Returns:
            True if build succeeds
        """
        self._init_context()

        try:
            # Load model config
            model_cfg = self.loader.load_model_config(model_name)

            # Get model class
            model_class = self._get_model_class(model_name)

            # Instantiate model
            model = model_class(
                connection=self.ctx.connection,
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

            # Write to Silver storage
            logger.info(f"  Writing {model_name} tables to Silver storage...")
            model.write_tables(use_optimized_writer=True)
            logger.info(f"  ✓ Tables written to Silver layer")

            return True

        except Exception as e:
            logger.error(f"Build failed for {model_name}: {e}", exc_info=True)
            return False

    def _get_model_class(self, model_name: str):
        """Get the model class for a model name."""
        if model_name == 'company':
            from models.implemented.company.model import CompanyModel
            return CompanyModel
        elif model_name == 'stocks':
            from models.implemented.stocks.model import StocksModel
            return StocksModel
        elif model_name == 'options':
            from models.implemented.options.model import OptionsModel
            return OptionsModel
        elif model_name == 'etfs':
            from models.implemented.etfs.model import ETFsModel
            return ETFsModel
        elif model_name == 'futures':
            from models.implemented.futures.model import FuturesModel
            return FuturesModel
        elif model_name == 'core':
            from models.implemented.core.model import CoreModel
            return CoreModel
        else:
            logger.warning(f"No specific model class for {model_name}, using BaseModel")
            from models.base.model import BaseModel
            return BaseModel

    def _print_summary(self):
        """Print build summary."""
        logger.info("\n" + "=" * 70)
        logger.info("SILVER BUILD SUMMARY")
        logger.info("=" * 70)

        start = self.results['start_time']
        end = self.results['end_time']
        if start and end:
            duration = (end - start).total_seconds()
            logger.info(f"\nTotal duration: {duration:.2f}s")

        logger.info(f"\nModels processed: {self.results['models_processed']}")
        logger.info(f"Succeeded: {self.results['models_succeeded']}")
        logger.info(f"Failed: {self.results['models_failed']}")

        logger.info("\nPer-model results:")
        for model_name, result in self.results['model_results'].items():
            status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
            logger.info(f"  {status} - {model_name}")

        logger.info("\n" + "=" * 70)
        if self.results['models_failed'] == 0:
            logger.info("✓ ALL SILVER LAYERS BUILT SUCCESSFULLY")
        else:
            logger.info(f"✗ {self.results['models_failed']} MODEL(S) FAILED")
        logger.info("=" * 70)

    def save_results(self, output_file: str):
        """Save results to JSON file."""
        serializable = {
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
            json.dump(serializable, f, indent=2)

        logger.info(f"\nResults saved to: {output_path}")


def main():
    """CLI entry point."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Build Silver layer from existing Bronze data (no ingestion)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--models',
        nargs='+',
        help='Specific models to build (default: all)'
    )

    parser.add_argument(
        '--date-from',
        help='Start date filter (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--date-to',
        help='End date filter (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--max-tickers',
        type=int,
        help='Universe size limit'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without executing'
    )

    parser.add_argument(
        '--output',
        help='Save results to JSON file'
    )

    args = parser.parse_args()

    try:
        builder = SilverBuilder()

        success = builder.build(
            models=args.models,
            date_from=args.date_from,
            date_to=args.date_to,
            max_tickers=args.max_tickers,
            dry_run=args.dry_run
        )

        if args.output:
            builder.save_results(args.output)

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
