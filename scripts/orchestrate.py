"""
Unified Pipeline Orchestrator

Purpose:
    Single entry point for all data ingestion and model building operations.
    Replaces fragmented scripts with unified CLI supporting:
    - Multi-provider data ingestion with dynamic discovery
    - Dependency-aware model building with topological sort
    - Checkpoint/resume capability for fault tolerance
    - Parallel execution where possible

Usage:
    # Full pipeline (all providers, all models)
    python -m scripts.orchestrate --all

    # Selective providers (ingest only)
    python -m scripts.orchestrate --providers chicago --ingest-only

    # Selective models with auto-dependency resolution
    python -m scripts.orchestrate --models city_finance --build-only
    # Automatically builds: core → macro → city_finance

    # Resume a failed pipeline
    python -m scripts.orchestrate --resume

    # Show what would be executed (dry run)
    python -m scripts.orchestrate --models stocks,city_finance --dry-run

    # Show dependency graph
    python -m scripts.orchestrate --show-dependencies

Examples:
    # Full pipeline with Chicago data for actuarial analysis
    python -m scripts.orchestrate --providers chicago --models city_finance --days 365

    # Securities pipeline only
    python -m scripts.orchestrate --providers alpha_vantage --models stocks,company --max-tickers 500

    # Quick test run
    python -m scripts.orchestrate --providers alpha_vantage --models stocks --max-tickers 20 --days 30

Note:
    This script is designed to eventually replace run_full_pipeline.py.
    During transition, both scripts are supported.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger, LogTimer
from orchestration.dependency_graph import DependencyGraph
from orchestration.checkpoint import CheckpointManager
from datapipelines.providers.registry import ProviderRegistry

logger = get_logger(__name__)


# ============================================================================
# Model Building Functions
# ============================================================================

def load_storage_config() -> Dict:
    """Load storage configuration from storage.json."""
    storage_path = Path(repo_root) / "configs" / "storage.json"
    with open(storage_path, 'r') as f:
        return json.load(f)


def build_model(
    model_name: str,
    spark_session: Any,
    storage_cfg: Dict,
    repo_root_path: Path
) -> Dict[str, Any]:
    """
    Build a single model.

    Args:
        model_name: Name of the model to build
        spark_session: Spark session
        storage_cfg: Storage configuration
        repo_root_path: Repository root path

    Returns:
        Build results dict
    """
    from core.connection import ConnectionFactory
    from config.model_loader import ModelConfigLoader

    # Create connection
    connection = ConnectionFactory.create("spark", spark_session=spark_session)

    # Load model config
    config_root = repo_root_path / "configs" / "models"
    loader = ModelConfigLoader(config_root)
    model_cfg = loader.load_model_config(model_name)

    # Get model class
    model_class = get_model_class(model_name)

    # Instantiate and build
    model = model_class(
        connection=connection,
        storage_cfg=storage_cfg,
        model_cfg=model_cfg,
        params={},
        repo_root=str(repo_root_path)
    )

    dims, facts = model.build()
    stats = model.write_tables(quiet=True)

    return {
        'model': model_name,
        'dimensions': stats.get('dimensions', {}),
        'facts': stats.get('facts', {}),
        'status': 'success'
    }


def get_model_class(model_name: str) -> type:
    """
    Get the model class for a given model name.

    This function dynamically imports the appropriate model class.
    """
    # Model name to class mapping
    model_map = {
        # Foundation models
        'temporal': ('models.foundation.temporal.model', 'TemporalModel'),
        'geography': ('models.foundation.geography.model', 'GeographyModel'),
        # Domain models
        'company': ('models.domain.company.model', 'CompanyModel'),
        'stocks': ('models.domain.stocks.model', 'StocksModel'),
        'macro': ('models.domain.macro.model', 'MacroModel'),
        'city_finance': ('models.domain.city_finance.model', 'CityFinanceModel'),
        'forecast': ('models.domain.forecast.model', 'ForecastModel'),
        'options': ('models.domain.options.model', 'OptionsModel'),
        'etf': ('models.domain.etf.model', 'ETFModel'),
        # Add more as needed
    }

    if model_name not in model_map:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(model_map.keys())}")

    module_path, class_name = model_map[model_name]

    try:
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Cannot import {class_name} from {module_path}: {e}")


# ============================================================================
# Ingestion Functions
# ============================================================================

def run_provider_ingestion(
    provider_name: str,
    ctx: Any,
    days: int = 30,
    max_tickers: int = None,
    date_from: str = None,
    date_to: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Run ingestion for a single provider.

    Args:
        provider_name: Name of the provider (e.g., 'alpha_vantage', 'chicago')
        ctx: RepoContext with spark session
        days: Number of days of data to ingest
        max_tickers: Maximum tickers (for alpha_vantage)
        date_from: Start date override
        date_to: End date override
        **kwargs: Additional provider-specific kwargs

    Returns:
        Ingestion results dict
    """
    logger.info(f"Starting ingestion for provider: {provider_name}")

    # Calculate date range
    if date_from and date_to:
        pass  # Use provided dates
    elif days:
        date_to = datetime.now().date().isoformat()
        date_from = (datetime.now().date() - timedelta(days=days)).isoformat()
    else:
        # Default: last 30 days
        date_to = datetime.now().date().isoformat()
        date_from = (datetime.now().date() - timedelta(days=30)).isoformat()

    # Provider-specific ingestion
    if provider_name == 'alpha_vantage':
        return _run_alpha_vantage_ingestion(
            ctx, date_from, date_to, max_tickers, **kwargs
        )
    elif provider_name == 'chicago':
        return _run_chicago_ingestion(ctx, **kwargs)
    elif provider_name == 'bls':
        return _run_bls_ingestion(ctx, **kwargs)
    else:
        logger.warning(f"No specific ingestion handler for {provider_name}, using generic")
        return _run_generic_ingestion(provider_name, ctx, **kwargs)


def _run_alpha_vantage_ingestion(
    ctx: Any,
    date_from: str,
    date_to: str,
    max_tickers: int = None,
    **kwargs
) -> Dict[str, Any]:
    """Run Alpha Vantage data ingestion."""
    from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

    ingestor = AlphaVantageIngestor(
        alpha_vantage_cfg=ctx.get_api_config('alpha_vantage'),
        storage_cfg=ctx.storage,
        spark=ctx.spark
    )

    # Use per-ticker strategy
    results = ingestor.run_comprehensive_per_ticker(
        tickers=None,
        date_from=date_from,
        date_to=date_to,
        max_tickers=max_tickers,
        sort_by_market_cap=True,
        include_fundamentals=kwargs.get('include_fundamentals', True),
        skip_reference_refresh=kwargs.get('skip_reference_refresh', False),
        batch_write_size=kwargs.get('batch_write_size', 20)
    )

    return {
        'provider': 'alpha_vantage',
        'status': 'success',
        'tickers': results.get('tickers', []),
        'date_from': date_from,
        'date_to': date_to
    }


def _run_chicago_ingestion(ctx: Any, **kwargs) -> Dict[str, Any]:
    """Run Chicago Data Portal ingestion."""
    try:
        from datapipelines.providers.chicago import ChicagoIngestor

        ingestor = ChicagoIngestor(
            chicago_cfg=ctx.get_api_config('chicago'),
            storage_cfg=ctx.storage,
            spark=ctx.spark
        )

        results = ingestor.run()

        return {
            'provider': 'chicago',
            'status': 'success',
            'results': results
        }
    except ImportError:
        logger.warning("ChicagoIngestor not fully implemented")
        return {
            'provider': 'chicago',
            'status': 'not_implemented',
            'message': 'Chicago ingestor needs implementation'
        }


def _run_bls_ingestion(ctx: Any, **kwargs) -> Dict[str, Any]:
    """Run BLS data ingestion."""
    try:
        from datapipelines.providers.bls import BlsIngestor

        ingestor = BlsIngestor(
            bls_cfg=ctx.get_api_config('bls'),
            storage_cfg=ctx.storage,
            spark=ctx.spark
        )

        results = ingestor.run()

        return {
            'provider': 'bls',
            'status': 'success',
            'results': results
        }
    except ImportError:
        logger.warning("BlsIngestor not fully implemented")
        return {
            'provider': 'bls',
            'status': 'not_implemented',
            'message': 'BLS ingestor needs implementation'
        }


def _run_generic_ingestion(
    provider_name: str,
    ctx: Any,
    **kwargs
) -> Dict[str, Any]:
    """Run generic provider ingestion using ProviderRegistry."""
    try:
        ingestor = ProviderRegistry.get_ingestor(
            provider_name,
            spark=ctx.spark,
            storage_cfg=ctx.storage,
            api_config=ctx.get_api_config(provider_name)
        )

        results = ingestor.run(**kwargs)

        return {
            'provider': provider_name,
            'status': 'success',
            'results': results
        }
    except Exception as e:
        logger.error(f"Generic ingestion failed for {provider_name}: {e}")
        return {
            'provider': provider_name,
            'status': 'failed',
            'error': str(e)
        }


# ============================================================================
# Main Orchestration
# ============================================================================

def run_orchestration(
    providers: List[str],
    models: List[str],
    ingest_only: bool = False,
    build_only: bool = False,
    days: int = 30,
    max_tickers: int = None,
    date_from: str = None,
    date_to: str = None,
    resume: bool = False,
    dry_run: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Run the full orchestration pipeline.

    Args:
        providers: List of provider names to ingest from
        models: List of model names to build
        ingest_only: Only run ingestion (skip build)
        build_only: Only run build (skip ingestion)
        days: Days of data to ingest
        max_tickers: Max tickers for securities providers
        date_from: Start date override
        date_to: End date override
        resume: Resume from checkpoint
        dry_run: Show what would be done without executing
        **kwargs: Additional options

    Returns:
        Orchestration results
    """
    start_time = datetime.now()
    results = {
        'start_time': start_time.isoformat(),
        'providers': {},
        'models': {},
        'errors': [],
        'status': 'running'
    }

    # Initialize dependency graph
    configs_path = Path(repo_root) / "configs" / "models"
    dep_graph = DependencyGraph(configs_path)
    dep_graph.build()

    # Resolve model dependencies
    if models and models != ['all']:
        models_to_build = dep_graph.filter_buildable(models)
    else:
        models_to_build = dep_graph.topological_sort()

    # Initialize checkpoint manager
    checkpoint_dir = Path(repo_root) / "storage" / "checkpoints"
    checkpoint = CheckpointManager(checkpoint_dir=str(checkpoint_dir))

    # Handle resume
    if resume:
        existing = checkpoint.find_resumable_checkpoint('orchestrate')
        if existing:
            logger.info(f"Resuming from checkpoint: {existing.pipeline_id}")
            # Filter out completed items
            completed_providers = set(existing.metadata.get('completed_providers', []))
            completed_models = set(existing.metadata.get('completed_models', []))
            providers = [p for p in providers if p not in completed_providers]
            models_to_build = [m for m in models_to_build if m not in completed_models]

    # Dry run - just show what would be done
    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - No operations will be executed")
        print("=" * 60)

        if not build_only:
            print(f"\nProviders to ingest ({len(providers)}):")
            for p in providers:
                info = ProviderRegistry.get_info(p)
                desc = info.description[:50] + "..." if info and len(info.description) > 50 else (info.description if info else "")
                print(f"  • {p}: {desc}")

        if not ingest_only:
            print(f"\nModels to build ({len(models_to_build)}):")
            for i, m in enumerate(models_to_build, 1):
                deps = dep_graph.get_dependencies(m, recursive=False)
                deps_str = f" (deps: {', '.join(deps)})" if deps else ""
                print(f"  {i}. {m}{deps_str}")

        print("\n" + "=" * 60)
        return results

    # Create checkpoint for this run
    checkpoint.create_checkpoint(
        'orchestrate',
        tickers=[],  # Not ticker-based
        metadata={
            'providers': providers,
            'models': models_to_build,
            'completed_providers': [],
            'completed_models': []
        }
    )

    try:
        # ================================================================
        # PHASE 1: DATA INGESTION
        # ================================================================
        if not build_only and providers:
            print("\n" + "=" * 60)
            print("PHASE 1: DATA INGESTION")
            print("=" * 60)

            from core.context import RepoContext
            ctx = RepoContext.from_repo_root(connection_type="spark")

            for provider in providers:
                print(f"\nIngesting from {provider}...")

                with LogTimer(logger, f"Ingesting {provider}"):
                    try:
                        result = run_provider_ingestion(
                            provider,
                            ctx,
                            days=days,
                            max_tickers=max_tickers,
                            date_from=date_from,
                            date_to=date_to,
                            **kwargs
                        )
                        results['providers'][provider] = result

                        if result.get('status') == 'success':
                            # Update checkpoint
                            completed = checkpoint._current_checkpoint.metadata.get('completed_providers', [])
                            completed.append(provider)
                            checkpoint._current_checkpoint.metadata['completed_providers'] = completed
                            checkpoint._save_checkpoint(checkpoint._current_checkpoint)
                            print(f"  ✓ {provider} completed")
                        else:
                            print(f"  ⚠ {provider}: {result.get('status')}")

                    except Exception as e:
                        error_msg = f"{provider} ingestion failed: {e}"
                        logger.error(error_msg, exc_info=True)
                        results['providers'][provider] = {
                            'status': 'failed',
                            'error': str(e)
                        }
                        results['errors'].append(error_msg)

        # ================================================================
        # PHASE 2: MODEL BUILDING
        # ================================================================
        if not ingest_only and models_to_build:
            print("\n" + "=" * 60)
            print("PHASE 2: MODEL BUILDING")
            print("=" * 60)

            from orchestration.common.spark_session import get_spark

            storage_cfg = load_storage_config()
            spark_session = get_spark("Orchestrator")

            for model_name in models_to_build:
                print(f"\nBuilding model: {model_name}...")

                with LogTimer(logger, f"Building {model_name}"):
                    try:
                        result = build_model(
                            model_name,
                            spark_session,
                            storage_cfg,
                            Path(repo_root)
                        )
                        results['models'][model_name] = result

                        # Update checkpoint
                        completed = checkpoint._current_checkpoint.metadata.get('completed_models', [])
                        completed.append(model_name)
                        checkpoint._current_checkpoint.metadata['completed_models'] = completed
                        checkpoint._save_checkpoint(checkpoint._current_checkpoint)

                        print(f"  ✓ {model_name} built successfully")

                    except Exception as e:
                        error_msg = f"{model_name} build failed: {e}"
                        logger.error(error_msg, exc_info=True)
                        results['models'][model_name] = {
                            'status': 'failed',
                            'error': str(e)
                        }
                        results['errors'].append(error_msg)

            # Clean up Spark
            spark_session.stop()

        # Mark complete
        results['status'] = 'completed' if not results['errors'] else 'completed_with_errors'
        checkpoint.mark_pipeline_completed()

    except Exception as e:
        results['status'] = 'failed'
        results['errors'].append(str(e))
        checkpoint.mark_pipeline_failed(str(e))
        raise

    finally:
        end_time = datetime.now()
        results['end_time'] = end_time.isoformat()
        results['duration_seconds'] = (end_time - start_time).total_seconds()

    return results


def print_summary(results: Dict[str, Any]) -> None:
    """Print orchestration summary."""
    print("\n" + "=" * 60)
    print("ORCHESTRATION SUMMARY")
    print("=" * 60)

    print(f"\nStatus: {results.get('status', 'unknown')}")
    print(f"Duration: {results.get('duration_seconds', 0):.1f} seconds")

    # Provider results
    if results.get('providers'):
        print("\nProvider Ingestion:")
        for name, info in results['providers'].items():
            status = info.get('status', 'unknown')
            symbol = "✓" if status == 'success' else "✗"
            print(f"  {symbol} {name}: {status}")

    # Model results
    if results.get('models'):
        print("\nModel Building:")
        for name, info in results['models'].items():
            status = info.get('status', 'unknown')
            symbol = "✓" if status == 'success' else "✗"
            print(f"  {symbol} {name}: {status}")

    # Errors
    if results.get('errors'):
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results['errors'][:5]:
            print(f"  • {error}")
        if len(results['errors']) > 5:
            print(f"  ... and {len(results['errors']) - 5} more")

    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Unified Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (all providers, all models)
  python -m scripts.orchestrate --all

  # Securities data only
  python -m scripts.orchestrate --providers alpha_vantage --models stocks,company

  # Chicago municipal data
  python -m scripts.orchestrate --providers chicago --models city_finance

  # Build specific model (auto-resolves dependencies)
  python -m scripts.orchestrate --models city_finance --build-only

  # Show dependency graph
  python -m scripts.orchestrate --show-dependencies

  # Resume failed pipeline
  python -m scripts.orchestrate --resume
        """
    )

    # Provider selection
    parser.add_argument(
        '--providers', type=str, default=None,
        help='Comma-separated providers: alpha_vantage,bls,chicago or "all"'
    )

    # Model selection
    parser.add_argument(
        '--models', type=str, default=None,
        help='Comma-separated models or "all"'
    )

    # Convenience flags
    parser.add_argument(
        '--all', action='store_true',
        help='Run all providers and all models'
    )

    # Mode selection
    parser.add_argument(
        '--ingest-only', action='store_true',
        help='Only run data ingestion (skip model build)'
    )
    parser.add_argument(
        '--build-only', action='store_true',
        help='Only run model build (skip ingestion)'
    )

    # Resume/checkpoint
    parser.add_argument(
        '--resume', action='store_true',
        help='Resume from last checkpoint'
    )
    parser.add_argument(
        '--fresh', action='store_true',
        help='Clear checkpoint and start fresh'
    )

    # Date range
    parser.add_argument(
        '--days', type=int, default=30,
        help='Days of data to ingest (default: 30)'
    )
    parser.add_argument(
        '--from', dest='date_from', type=str,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--to', dest='date_to', type=str,
        help='End date (YYYY-MM-DD)'
    )

    # Ticker options
    parser.add_argument(
        '--max-tickers', type=int, default=None,
        help='Maximum tickers to process'
    )

    # Execution options
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be executed without running'
    )
    parser.add_argument(
        '--show-dependencies', action='store_true',
        help='Show model dependency graph and exit'
    )

    # Verbosity
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    # Handle --show-dependencies
    if args.show_dependencies:
        configs_path = Path(repo_root) / "configs" / "models"
        dep_graph = DependencyGraph(configs_path)
        dep_graph.build()
        print(dep_graph.visualize())
        print("\nTiers:")
        for tier, models in dep_graph.get_tiers().items():
            print(f"  Tier {tier}: {', '.join(models)}")
        return

    # Parse providers
    if args.all or args.providers == 'all':
        providers = ProviderRegistry.list_available()
    elif args.providers:
        providers = [p.strip() for p in args.providers.split(',')]
    elif args.build_only:
        providers = []
    else:
        # Default: alpha_vantage for securities
        providers = ['alpha_vantage']

    # Parse models
    if args.all or args.models == 'all':
        models = ['all']
    elif args.models:
        models = [m.strip() for m in args.models.split(',')]
    elif args.ingest_only:
        models = []
    else:
        # Default: stocks and company
        models = ['stocks', 'company']

    # Run orchestration
    try:
        results = run_orchestration(
            providers=providers,
            models=models,
            ingest_only=args.ingest_only,
            build_only=args.build_only,
            days=args.days,
            max_tickers=args.max_tickers,
            date_from=args.date_from,
            date_to=args.date_to,
            resume=args.resume,
            dry_run=args.dry_run
        )

        print_summary(results)

        # Exit with error code if there were failures
        if results.get('errors'):
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nOrchestration interrupted. Use --resume to continue.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Orchestration failed: {e}", exc_info=True)
        print(f"\n✗ Orchestration failed: {e}")
        print("Use --resume to retry from last checkpoint")
        sys.exit(1)


if __name__ == "__main__":
    main()
