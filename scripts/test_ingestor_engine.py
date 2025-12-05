#!/usr/bin/env python
"""
Test Script for Generic Ingestor Engine.

Tests the new provider-agnostic ingestion architecture with 20 tickers.

Usage:
    # Test with 20 tickers (default)
    python -m scripts.test_ingestor_engine

    # Test with specific ticker count
    python -m scripts.test_ingestor_engine --max-tickers 10

    # Test specific data types only
    python -m scripts.test_ingestor_engine --data-types reference,prices

    # Test with market cap ranking
    python -m scripts.test_ingestor_engine --use-market-cap --max-tickers 20

    # Full test with fundamentals
    python -m scripts.test_ingestor_engine --max-tickers 20 --include-fundamentals

Author: de_Funk Team
Date: December 2025
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def main():
    parser = argparse.ArgumentParser(
        description="Test the Generic Ingestor Engine with configurable options",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--max-tickers',
        type=int,
        default=20,
        help='Number of tickers to process (default: 20)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=20,
        help='Tickers per batch (default: 20)'
    )
    parser.add_argument(
        '--data-types',
        type=str,
        default=None,
        help='Comma-separated data types: reference,prices,income,balance,cashflow,earnings'
    )
    parser.add_argument(
        '--use-market-cap',
        action='store_true',
        help='Get tickers sorted by market cap (requires existing reference data)'
    )
    parser.add_argument(
        '--use-bulk-listing',
        action='store_true',
        help='Discover tickers from Alpha Vantage LISTING_STATUS'
    )
    parser.add_argument(
        '--include-fundamentals',
        action='store_true',
        help='Include income, balance, cashflow, earnings'
    )
    parser.add_argument(
        '--tickers',
        type=str,
        default=None,
        help='Comma-separated specific tickers to test (e.g., AAPL,MSFT,GOOGL)'
    )
    parser.add_argument(
        '--outputsize',
        type=str,
        default='compact',
        choices=['compact', 'full'],
        help='Price data size: compact (100 days) or full (20+ years)'
    )
    parser.add_argument(
        '--silent',
        action='store_true',
        help='Suppress progress output'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("GENERIC INGESTOR ENGINE TEST")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Import after setup_repo_imports
    from core.context import RepoContext
    from datapipelines.base import DataType, create_engine

    # Initialize context
    print("Initializing context...")
    ctx = RepoContext.from_repo_root(connection_type="spark")
    print("  ✓ Context initialized (Spark mode)")

    # Create engine
    print("Creating ingestor engine...")
    engine = create_engine(
        provider_name="alpha_vantage",
        api_cfg=ctx.get_api_config('alpha_vantage'),
        storage_cfg=ctx.storage,
        spark=ctx.spark
    )
    print("  ✓ Engine created")
    print()

    # Determine data types
    if args.data_types:
        type_map = {
            'reference': DataType.REFERENCE,
            'prices': DataType.PRICES,
            'income': DataType.INCOME_STATEMENT,
            'balance': DataType.BALANCE_SHEET,
            'cashflow': DataType.CASH_FLOW,
            'earnings': DataType.EARNINGS,
        }
        data_types = [type_map[t.strip()] for t in args.data_types.split(',') if t.strip() in type_map]
    elif args.include_fundamentals:
        data_types = [
            DataType.REFERENCE,
            DataType.PRICES,
            DataType.INCOME_STATEMENT,
            DataType.BALANCE_SHEET,
            DataType.CASH_FLOW,
            DataType.EARNINGS,
        ]
    else:
        # Default: just reference and prices
        data_types = [DataType.REFERENCE, DataType.PRICES]

    print(f"Configuration:")
    print(f"  Max tickers: {args.max_tickers}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Data types: {', '.join(dt.value for dt in data_types)}")
    print(f"  Output size: {args.outputsize}")
    print()

    # Determine tickers
    start_time = time.time()

    if args.tickers:
        # Explicit tickers provided
        tickers = [t.strip() for t in args.tickers.split(',')]
        print(f"Using explicit tickers: {', '.join(tickers)}")
        results = engine.run(
            tickers=tickers,
            data_types=data_types,
            batch_size=args.batch_size,
            silent=args.silent,
            outputsize=args.outputsize
        )
    elif args.use_bulk_listing:
        # Discover from API
        print("Discovering tickers from Alpha Vantage...")
        results = engine.run_with_discovery(
            max_tickers=args.max_tickers,
            use_market_cap=False,  # Fresh discovery
            data_types=data_types,
            batch_size=args.batch_size,
            silent=args.silent,
            outputsize=args.outputsize
        )
    elif args.use_market_cap:
        # Use market cap ranking
        print("Getting tickers by market cap...")
        results = engine.run_with_discovery(
            max_tickers=args.max_tickers,
            use_market_cap=True,
            data_types=data_types,
            batch_size=args.batch_size,
            silent=args.silent,
            outputsize=args.outputsize
        )
    else:
        # Default test tickers
        default_tickers = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
            'NVDA', 'TSLA', 'BRK-B', 'JPM', 'V',
            'UNH', 'MA', 'HD', 'PG', 'JNJ',
            'XOM', 'CVX', 'BAC', 'ABBV', 'KO'
        ]
        tickers = default_tickers[:args.max_tickers]
        print(f"Using default test tickers ({len(tickers)}): {', '.join(tickers[:5])}...")
        results = engine.run(
            tickers=tickers,
            data_types=data_types,
            batch_size=args.batch_size,
            silent=args.silent,
            outputsize=args.outputsize
        )

    elapsed = time.time() - start_time

    # Print summary
    print()
    print("=" * 80)
    print("TEST RESULTS")
    print("=" * 80)
    print(f"  Total time: {elapsed:.1f} seconds")
    print(f"  Tickers processed: {results.completed_tickers}/{results.total_tickers}")
    print(f"  Total errors: {results.total_errors}")
    print()

    print("Tables written:")
    for table, path in results.tables_written.items():
        print(f"  - {table}: {path}")
    print()

    # Print performance metrics
    if results.metrics:
        print("Performance breakdown:")
        for step, stats in results.metrics.items():
            if isinstance(stats, dict) and 'avg_ms' in stats:
                print(f"  - {step}: {stats['avg_ms']:.1f}ms avg ({stats['count']} calls)")
    print()

    print("=" * 80)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Return exit code
    if results.total_errors > results.total_tickers * 0.5:
        # More than 50% errors
        print("\n⚠ WARNING: High error rate detected")
        sys.exit(1)

    print("\n✓ Test completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
