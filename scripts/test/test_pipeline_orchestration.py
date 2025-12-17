#!/usr/bin/env python3
"""
Test Pipeline Orchestration with Alpha Vantage.

Verifies that Phase 5 and Phase 6 components work correctly:
- BaseProvider / AlphaVantageProvider
- IngestorEngine
- MetricsCollector
- BatchProgressTracker
- Ray cluster (if available)

Usage:
    # Quick test (3 tickers, reference only)
    python -m scripts.test.test_pipeline_orchestration --quick

    # Full test (20 tickers, reference + prices)
    python -m scripts.test.test_pipeline_orchestration

    # Test with specific tickers
    python -m scripts.test.test_pipeline_orchestration --tickers AAPL,MSFT,GOOGL

Author: de_Funk Team
Date: December 2025
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def test_metrics_collector():
    """Test MetricsCollector functionality."""
    print("\n" + "=" * 60)
    print("TEST: MetricsCollector")
    print("=" * 60)

    from datapipelines.base.metrics import MetricsCollector
    import time

    metrics = MetricsCollector(name="test_pipeline")

    # Simulate some operations
    for i in range(5):
        with metrics.time("fetch_data"):
            time.sleep(0.1)

        with metrics.time("transform"):
            time.sleep(0.05)

    # Print report
    metrics.print_report()

    # Verify
    summary = metrics.summary()
    assert 'steps' in summary
    assert 'fetch_data' in summary['steps']
    assert summary['steps']['fetch_data']['count'] == 5

    print("✓ MetricsCollector test passed")
    return True


def test_progress_tracker():
    """Test BatchProgressTracker functionality."""
    print("\n" + "=" * 60)
    print("TEST: BatchProgressTracker")
    print("=" * 60)

    from datapipelines.base.progress_tracker import BatchProgressTracker
    import time

    tracker = BatchProgressTracker(
        total_tickers=10,
        batch_size=5,
        data_types=['reference', 'prices'],
        minimal=True
    )

    # Simulate batch processing
    tickers = [f"TEST{i}" for i in range(10)]

    for batch_idx in range(0, 10, 5):
        batch_num = batch_idx // 5 + 1
        batch_tickers = tickers[batch_idx:batch_idx + 5]

        tracker.start_batch(batch_num, 2, batch_tickers)

        for ticker in batch_tickers:
            tracker.update(ticker, 'reference', success=True)
            time.sleep(0.05)
            tracker.update(ticker, 'prices', success=True)
            tracker.complete_ticker(ticker)

        tracker.complete_batch(write_time_ms=100)

    stats = tracker.finish()

    # Verify
    assert stats['completed_tickers'] == 10
    assert stats['num_batches'] == 2

    print("✓ BatchProgressTracker test passed")
    return True


def test_provider_interface():
    """Test BaseProvider interface with AlphaVantageProvider."""
    print("\n" + "=" * 60)
    print("TEST: AlphaVantageProvider Interface")
    print("=" * 60)

    from datapipelines.base.provider import DataType
    from datapipelines.providers.alpha_vantage.provider import create_alpha_vantage_provider
    from core.context import RepoContext

    ctx = RepoContext.from_repo_root(connection_type="spark")
    provider = create_alpha_vantage_provider(
        ctx.get_api_config('alpha_vantage'),
        ctx.spark
    )

    # Verify interface methods
    assert provider.config.name == "alpha_vantage"
    assert DataType.REFERENCE in provider.get_supported_data_types()
    assert DataType.PRICES in provider.get_supported_data_types()

    # Verify table names
    assert provider.get_bronze_table_name(DataType.REFERENCE) == "securities_reference"
    assert provider.get_bronze_table_name(DataType.PRICES) == "securities_prices_daily"

    # Verify key columns
    assert provider.get_key_columns(DataType.REFERENCE) == ["ticker"]
    assert provider.get_key_columns(DataType.PRICES) == ["ticker", "trade_date"]

    print("  Provider name:", provider.config.name)
    print("  Supported types:", [dt.value for dt in provider.get_supported_data_types()])
    print("✓ Provider interface test passed")

    ctx.spark.stop()
    return True


def test_ingestor_engine(tickers: list, data_types: list, quick: bool = False):
    """Test IngestorEngine with actual API calls."""
    print("\n" + "=" * 60)
    print("TEST: IngestorEngine with Alpha Vantage")
    print("=" * 60)

    from datapipelines.base.provider import DataType
    from datapipelines.base.ingestor_engine import create_engine
    from core.context import RepoContext

    ctx = RepoContext.from_repo_root(connection_type="spark")

    # Create engine
    engine = create_engine(
        provider_name="alpha_vantage",
        api_cfg=ctx.get_api_config('alpha_vantage'),
        storage_cfg=ctx.storage,
        spark=ctx.spark
    )

    # Convert string data types to enums
    type_map = {
        'reference': DataType.REFERENCE,
        'prices': DataType.PRICES,
        'income': DataType.INCOME_STATEMENT,
        'balance': DataType.BALANCE_SHEET,
        'cashflow': DataType.CASH_FLOW,
    }
    enum_types = [type_map.get(dt, DataType.REFERENCE) for dt in data_types]

    print(f"\n  Tickers: {tickers}")
    print(f"  Data types: {data_types}")
    print()

    # Run ingestion
    results = engine.run(
        tickers=tickers,
        data_types=enum_types,
        batch_size=min(len(tickers), 10),
        auto_compact=False  # Skip compaction for test
    )

    print(f"\n  Results:")
    print(f"    Completed: {results.completed_tickers}/{results.total_tickers}")
    print(f"    Errors: {results.total_errors}")
    print(f"    Tables written: {list(results.tables_written.keys())}")

    # Verify
    assert results.completed_tickers == len(tickers)

    ctx.spark.stop()
    print("✓ IngestorEngine test passed")
    return True


def test_ray_cluster():
    """Test Ray cluster connectivity (if Ray is available)."""
    print("\n" + "=" * 60)
    print("TEST: Ray Cluster")
    print("=" * 60)

    try:
        from orchestration.distributed.ray_cluster import RayCluster, get_ray

        ray = get_ray()
        if ray is None:
            print("  Ray not installed, skipping test")
            return True

        # Test local mode
        cluster = RayCluster(num_cpus=2)

        with cluster:
            resources = cluster.resources
            print(f"  CPUs: {resources.total_cpus}")
            print(f"  Memory: {resources.total_memory_gb:.1f} GB")
            print(f"  Nodes: {resources.num_nodes}")

        print("✓ Ray cluster test passed")
        return True

    except Exception as e:
        print(f"  Ray test failed: {e}")
        return False


def test_scheduler():
    """Test APScheduler integration (without starting daemon)."""
    print("\n" + "=" * 60)
    print("TEST: APScheduler")
    print("=" * 60)

    try:
        from orchestration.scheduler import PipelineScheduler

        scheduler = PipelineScheduler(blocking=False)
        scheduler.register_default_jobs()

        jobs = scheduler.scheduler.get_jobs()
        print(f"  Registered jobs: {len(jobs)}")
        for job in jobs:
            print(f"    - {job.id}: {job.name}")

        scheduler.stop()
        print("✓ APScheduler test passed")
        return True

    except ImportError:
        print("  APScheduler not installed, skipping test")
        return True
    except Exception as e:
        print(f"  Scheduler test failed: {e}")
        return False


def main():
    setup_logging()

    parser = argparse.ArgumentParser(description="Test pipeline orchestration")
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick test with 3 tickers, reference only'
    )
    parser.add_argument(
        '--tickers',
        default='AAPL,MSFT,GOOGL',
        help='Comma-separated list of tickers (default: AAPL,MSFT,GOOGL)'
    )
    parser.add_argument(
        '--data-types',
        default='reference',
        help='Comma-separated data types (default: reference)'
    )
    parser.add_argument(
        '--skip-api',
        action='store_true',
        help='Skip API tests (useful for CI without API keys)'
    )

    args = parser.parse_args()

    tickers = args.tickers.split(',')
    data_types = args.data_types.split(',')

    if args.quick:
        tickers = tickers[:3]
        data_types = ['reference']

    print("=" * 60)
    print("PIPELINE ORCHESTRATION TESTS")
    print("=" * 60)
    print(f"  Quick mode: {args.quick}")
    print(f"  Tickers: {tickers}")
    print(f"  Data types: {data_types}")
    print(f"  Skip API: {args.skip_api}")

    results = {}

    # Run tests
    results['metrics'] = test_metrics_collector()
    results['progress'] = test_progress_tracker()
    results['ray'] = test_ray_cluster()
    results['scheduler'] = test_scheduler()

    if not args.skip_api:
        results['provider'] = test_provider_interface()
        results['engine'] = test_ingestor_engine(tickers, data_types, args.quick)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        icon = "✓" if result else "✗"
        print(f"  {icon} {name}")

    print(f"\n  {passed}/{total} tests passed")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
