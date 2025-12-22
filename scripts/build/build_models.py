#!/usr/bin/env python3
"""
Build Models - Clean builder-based model build script.

Uses the new BaseModelBuilder architecture where each model defines
its own builder with dependencies.

Usage:
    # Build all models (discovers builders automatically)
    python -m scripts.build.build_models

    # Build specific models
    python -m scripts.build.build_models --models stocks company

    # Dry run
    python -m scripts.build.build_models --dry-run

    # Verbose output
    python -m scripts.build.build_models --verbose
"""

from __future__ import annotations

import sys
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger
from models.base.builder import (
    BaseModelBuilder,
    BuilderRegistry,
    BuildContext,
    BuildResult
)

logger = get_logger(__name__)


def get_spark_session(app_name: str = "ModelBuilder"):
    """
    Create and return a Spark session with Delta Lake support.

    Returns:
        SparkSession
    """
    from orchestration.common.spark_session import get_spark

    return get_spark(
        app_name=app_name,
        config={
            "spark.driver.memory": "8g",
            "spark.sql.parquet.compression.codec": "snappy",
        }
    )


def load_storage_config(repo_root: Path) -> Dict:
    """
    Load storage configuration with resolved paths.

    Uses ConfigLoader as the single source of truth for path resolution.
    All relative paths are resolved to absolute based on repo_root.
    """
    from config import ConfigLoader

    loader = ConfigLoader(repo_root=repo_root)
    config = loader.load()
    return config.storage  # Already has resolved absolute paths


def discover_builders(repo_root: Path) -> None:
    """Discover and register all model builders."""
    models_path = repo_root / "models" / "domain"

    if models_path.exists():
        BuilderRegistry.discover(models_path)
        logger.info(f"Discovered {len(BuilderRegistry.all())} builders")
    else:
        logger.warning(f"Models path not found: {models_path}")


def build_models(
    models: Optional[List[str]] = None,
    dry_run: bool = False,
    verbose: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    max_tickers: Optional[int] = None
) -> Dict[str, BuildResult]:
    """
    Build specified models (or all) using the builder registry.

    Args:
        models: List of model names to build (None = all)
        dry_run: If True, don't actually build
        verbose: If True, show detailed output
        date_from: Start date for data
        date_to: End date for data
        max_tickers: Max tickers to process

    Returns:
        Dict mapping model name to BuildResult
    """
    repo_root_path = Path(repo_root)

    # Set default dates
    if not date_to:
        date_to = date.today().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    # Discover builders
    discover_builders(repo_root_path)

    # Get models to build
    available_builders = BuilderRegistry.all()

    if not available_builders:
        logger.error("No builders discovered. Check models/domain/*/builder.py files.")
        return {}

    if models:
        # Filter to requested models
        models_to_build = [m for m in models if m in available_builders]
        missing = [m for m in models if m not in available_builders]
        if missing:
            logger.warning(f"No builders for: {missing}")
    else:
        models_to_build = list(available_builders.keys())

    if not models_to_build:
        logger.error("No models to build")
        return {}

    # Get build order (respects dependencies)
    build_order = BuilderRegistry.get_build_order(models_to_build)
    logger.info(f"Build order: {' -> '.join(build_order)}")

    # Initialize Spark
    if not dry_run:
        logger.info("Initializing Spark session...")
        spark = get_spark_session()
        logger.info("  ✓ Spark session ready")
    else:
        spark = None
        logger.info("[DRY RUN] Skipping Spark initialization")

    # Load storage config
    storage_config = load_storage_config(repo_root_path)

    # Create build context
    context = BuildContext(
        spark=spark,
        storage_config=storage_config,
        repo_root=repo_root_path,
        date_from=date_from,
        date_to=date_to,
        max_tickers=max_tickers,
        dry_run=dry_run,
        verbose=verbose
    )

    # Build each model in order
    results = {}
    total_start = datetime.now()

    print("\n" + "=" * 70)
    print("  Building Silver Layer Models")
    print("=" * 70 + "\n")

    for model_name in build_order:
        builder_class = available_builders[model_name]
        builder = builder_class(context)

        logger.info(f"Building: {model_name}")
        if builder.depends_on:
            logger.info(f"  Dependencies: {', '.join(builder.depends_on)}")

        result = builder.build()
        results[model_name] = result

        if result.success:
            print(f"  ✓ {model_name}: {result.dimensions} dims, "
                  f"{result.facts} facts ({result.duration_seconds:.1f}s)")
        else:
            print(f"  ✗ {model_name}: {result.error}")

    # Summary
    total_duration = (datetime.now() - total_start).total_seconds()
    successful = sum(1 for r in results.values() if r.success)
    failed = len(results) - successful

    print("\n" + "-" * 70)
    print(f"  Complete: {successful}/{len(results)} models built ({total_duration:.1f}s)")
    if failed > 0:
        print(f"  Failed: {failed} models")
    print("-" * 70 + "\n")

    # Cleanup Spark
    if spark and not dry_run:
        spark.stop()

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build Silver layer models using builder architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Build all discovered models
    python -m scripts.build.build_models

    # Build specific models
    python -m scripts.build.build_models --models company stocks

    # Dry run (show what would be done)
    python -m scripts.build.build_models --dry-run

    # Verbose output
    python -m scripts.build.build_models --verbose
        """
    )

    parser.add_argument(
        '--models',
        nargs='+',
        help='Models to build (default: all discovered)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without building'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )
    parser.add_argument(
        '--date-from',
        type=str,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--date-to',
        type=str,
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--max-tickers',
        type=int,
        help='Maximum tickers to process'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    try:
        results = build_models(
            models=args.models,
            dry_run=args.dry_run,
            verbose=args.verbose,
            date_from=args.date_from,
            date_to=args.date_to,
            max_tickers=args.max_tickers
        )

        # Exit with error if any builds failed
        failed = sum(1 for r in results.values() if not r.success)
        return 1 if failed > 0 else 0

    except Exception as e:
        logger.error(f"Build failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
