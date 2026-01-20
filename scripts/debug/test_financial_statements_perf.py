#!/usr/bin/env python3
"""
Performance Test for Financial Statements Notebook

This script recreates the exact data loading done by the financial_statements_gt
notebook to identify performance bottlenecks.

Usage:
    python -m scripts.debug.test_financial_statements_perf
"""

import sys
import time
from pathlib import Path

# Setup imports
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from config.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def time_operation(name: str, func):
    """Time an operation and print results."""
    start = time.time()
    result = func()
    elapsed = time.time() - start
    status = "🐌 SLOW" if elapsed > 0.5 else "✅"
    print(f"  {status} {name}: {elapsed:.3f}s")
    return result, elapsed


def test_financial_statements_performance():
    """Test the performance of loading financial statements data."""
    print("=" * 70)
    print("FINANCIAL STATEMENTS NOTEBOOK - PERFORMANCE TEST")
    print("=" * 70)

    total_start = time.time()
    timings = {}

    # ============================================================
    # 1. SETUP - Create context and session (same as UI startup)
    # ============================================================
    print("\n[1] SETUP - Creating context and session...")
    print("-" * 70)

    from core.context import RepoContext
    from models.api.session import UniversalSession

    ctx, timings['create_context'] = time_operation(
        "Create RepoContext",
        lambda: RepoContext.from_repo_root(connection_type="duckdb")
    )

    session, timings['create_session'] = time_operation(
        "Create UniversalSession",
        lambda: UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
    )

    # ============================================================
    # 2. FILTER DATA - Get ticker list for dropdown (dim_company)
    # ============================================================
    print("\n[2] FILTER DATA - Loading ticker filter options...")
    print("-" * 70)

    def get_ticker_filter():
        df = session.get_table('company', 'dim_company')
        # Simulate what the filter does - get distinct tickers
        if hasattr(df, 'select'):
            return df.select('ticker').distinct()
        return df

    ticker_df, timings['get_ticker_filter'] = time_operation(
        "Get dim_company for ticker filter",
        get_ticker_filter
    )

    # ============================================================
    # 3. EXHIBIT DATA - Load each financial statement table
    # ============================================================
    print("\n[3] EXHIBIT DATA - Loading financial statement tables...")
    print("-" * 70)

    # These are the tables used by the notebook with ticker filter
    tables_to_test = [
        ('company', 'fact_income_statement', ['date', 'ticker', 'total_revenue', 'gross_profit', 'operating_income', 'net_income']),
        ('company', 'fact_balance_sheet', ['date', 'ticker', 'total_assets', 'total_liabilities', 'total_shareholder_equity']),
        ('company', 'fact_cash_flow', ['date', 'ticker', 'operating_cashflow', 'cashflow_from_investment', 'cashflow_from_financing', 'free_cash_flow']),
        ('company', 'fact_earnings', ['date', 'ticker', 'reported_eps', 'estimated_eps', 'surprise_percentage']),
    ]

    ticker_filter = {'ticker': 'AAPL'}  # Default filter from notebook

    for model, table, columns in tables_to_test:
        def load_table(m=model, t=table, c=columns):
            df = session.get_table(m, t, required_columns=c, filters=ticker_filter)
            # Convert to pandas to simulate what exhibit rendering does
            if hasattr(df, 'df'):
                return df.df()
            elif hasattr(df, 'fetchdf'):
                return df.fetchdf()
            return df

        key = f"get_{table}"
        _, timings[key] = time_operation(f"Get {model}.{table}", load_table)

    # ============================================================
    # 4. STOCK PRICES - Load for chart (with auto-join)
    # ============================================================
    print("\n[4] STOCK PRICES - Loading for chart (requires auto-join)...")
    print("-" * 70)

    def load_stock_prices():
        # This is the problematic one - requires auto-join for 'date' and 'ticker'
        required = ['date', 'ticker', 'close', 'open', 'high', 'low', 'volume']
        df = session.get_table('stocks', 'fact_stock_prices',
                               required_columns=required,
                               filters=ticker_filter)
        if hasattr(df, 'df'):
            return df.df()
        elif hasattr(df, 'fetchdf'):
            return df.fetchdf()
        return df

    _, timings['get_stock_prices'] = time_operation(
        "Get stocks.fact_stock_prices (with auto-join)",
        load_stock_prices
    )

    # ============================================================
    # 5. SUMMARY
    # ============================================================
    total_time = time.time() - total_start

    print("\n" + "=" * 70)
    print("PERFORMANCE SUMMARY")
    print("=" * 70)

    print(f"\nTotal time: {total_time:.3f}s")
    print("\nBreakdown by operation:")

    sorted_timings = sorted(timings.items(), key=lambda x: x[1], reverse=True)
    for name, elapsed in sorted_timings:
        pct = (elapsed / total_time) * 100
        bar = "█" * int(pct / 2)
        print(f"  {name:40s} {elapsed:6.3f}s ({pct:5.1f}%) {bar}")

    # Identify bottlenecks
    print("\n" + "-" * 70)
    print("BOTTLENECK ANALYSIS:")
    print("-" * 70)

    slow_ops = [(k, v) for k, v in timings.items() if v > 0.5]
    if slow_ops:
        print("\n⚠️  Slow operations (>0.5s):")
        for name, elapsed in sorted(slow_ops, key=lambda x: x[1], reverse=True):
            print(f"  - {name}: {elapsed:.3f}s")
    else:
        print("\n✅ No operations slower than 0.5s")

    # Check if session caching is working
    print("\n" + "-" * 70)
    print("CACHING TEST - Second load should be faster:")
    print("-" * 70)

    def second_load():
        return session.get_table('company', 'fact_income_statement',
                                 required_columns=['date', 'ticker', 'total_revenue'],
                                 filters=ticker_filter)

    _, second_time = time_operation(
        "Second load of fact_income_statement",
        second_load
    )

    first_time = timings.get('get_fact_income_statement', 0)
    if second_time < first_time * 0.5:
        print(f"  ✅ Caching working: {first_time:.3f}s -> {second_time:.3f}s")
    else:
        print(f"  ⚠️  Caching may not be effective: {first_time:.3f}s -> {second_time:.3f}s")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_financial_statements_performance()
