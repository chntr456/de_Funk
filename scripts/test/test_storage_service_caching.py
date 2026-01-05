#!/usr/bin/env python
"""
Test storage service caching behavior.

Verifies that:
1. Filtered queries skip caching (prevents 22M row cache)
2. Unfiltered queries cache small dimension tables
3. Filters are properly applied to large fact tables
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.logging import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)


def get_storage_root() -> Path:
    """Get storage root path."""
    storage_root = Path("/shared/storage")
    if not storage_root.exists():
        storage_root = Path(__file__).parent.parent.parent / "storage"
    return storage_root


def test_storage_service():
    """Test storage service with DuckDB connection."""
    from core.connection import get_duckdb_connection
    from models.registry import ModelRegistry
    from app.services.storage_service import SilverStorageService
    from utils.repo import get_repo_root

    repo_root = get_repo_root()
    storage_root = get_storage_root()
    print(f"Repo root: {repo_root}")
    print(f"Storage root: {storage_root}")

    # Initialize connection and registry
    print("\n" + "=" * 70)
    print("INITIALIZING")
    print("=" * 70)

    conn = get_duckdb_connection(auto_init_views=False)
    print("✓ DuckDB connection created")

    # ModelRegistry needs configs/models directory (YAML definitions)
    models_config_dir = repo_root / "configs" / "models"
    registry = ModelRegistry(models_config_dir)
    print(f"✓ Model registry initialized with models: {registry.list_models()}")

    service = SilverStorageService(conn, registry)
    print("✓ Storage service created")

    # Test 1: Unfiltered dimension table (should cache)
    print("\n" + "=" * 70)
    print("TEST 1: Unfiltered dimension table (should cache)")
    print("=" * 70)

    start = time.time()
    df = service.get_table("company", "dim_company")
    elapsed = time.time() - start
    count = conn.count(df)
    print(f"  First call: {count:,} rows in {elapsed:.3f}s")
    print(f"  Cache size: {len(service._cache)} tables")

    start = time.time()
    df = service.get_table("company", "dim_company")
    elapsed = time.time() - start
    count = conn.count(df)
    print(f"  Second call (cached): {count:,} rows in {elapsed:.3f}s")

    assert "company.dim_company" in service._cache, "Dimension table should be cached"
    print("  ✓ Dimension table correctly cached")

    # Test 2: Filtered fact table (should NOT cache full table)
    print("\n" + "=" * 70)
    print("TEST 2: Filtered fact table (should NOT cache)")
    print("=" * 70)

    service.clear_cache()
    print(f"  Cleared cache, size: {len(service._cache)}")

    filters = {"ticker": "AAPL"}
    start = time.time()
    df = service.get_table("stocks", "fact_stock_prices", filters=filters)
    elapsed = time.time() - start
    count = conn.count(df)
    print(f"  Filtered query (ticker=AAPL): {count:,} rows in {elapsed:.3f}s")
    print(f"  Cache size after filtered query: {len(service._cache)} tables")

    assert "stocks.fact_stock_prices" not in service._cache, "Filtered query should NOT cache"
    print("  ✓ Filtered query correctly skipped caching")

    # Test 3: Verify filter is actually applied
    print("\n" + "=" * 70)
    print("TEST 3: Verify filter reduces row count")
    print("=" * 70)

    # Get count without filter (just count, don't cache full table)
    count_query = f"SELECT COUNT(*) as cnt FROM delta_scan('{storage_root}/silver/stocks/facts/fact_stock_prices')"
    total_count = conn.execute(count_query).fetchone()[0]
    print(f"  Total rows in fact_stock_prices: {total_count:,}")

    # Get filtered count
    filters = {"ticker": "AAPL"}
    df = service.get_table("stocks", "fact_stock_prices", filters=filters)
    filtered_count = conn.count(df)
    print(f"  Filtered rows (ticker=AAPL): {filtered_count:,}")

    reduction = (1 - filtered_count / total_count) * 100
    print(f"  Reduction: {reduction:.1f}%")

    assert filtered_count < total_count, "Filter should reduce row count"
    assert filtered_count < 10000, f"AAPL should have <10k rows, got {filtered_count:,}"
    print("  ✓ Filter correctly reduces data")

    # Test 4: Multiple tickers
    print("\n" + "=" * 70)
    print("TEST 4: Multiple ticker filter")
    print("=" * 70)

    filters = {"ticker": ["AAPL", "MSFT", "GOOGL"]}
    start = time.time()
    df = service.get_table("stocks", "fact_stock_prices", filters=filters)
    elapsed = time.time() - start
    count = conn.count(df)
    print(f"  Filtered query (3 tickers): {count:,} rows in {elapsed:.3f}s")

    # Should be roughly 3x single ticker
    assert count < 30000, f"3 tickers should have <30k rows, got {count:,}"
    print("  ✓ Multi-ticker filter works")

    # Test 5: Date range filter
    print("\n" + "=" * 70)
    print("TEST 5: Date range + ticker filter")
    print("=" * 70)

    filters = {
        "ticker": "AAPL",
        "trade_date": {"start": "2024-01-01", "end": "2024-12-31"}
    }
    start = time.time()
    df = service.get_table("stocks", "fact_stock_prices", filters=filters)
    elapsed = time.time() - start
    count = conn.count(df)
    print(f"  AAPL 2024 only: {count:,} rows in {elapsed:.3f}s")

    assert count < 300, f"AAPL 2024 should have ~252 trading days, got {count:,}"
    print("  ✓ Date range filter works")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("✓ All tests passed!")
    print("✓ Caching is skipped when filters are present")
    print("✓ Filters are correctly applied to reduce data")
    print(f"✓ 22M row table filtered to ~{filtered_count:,} rows for single ticker")

    conn.stop()


if __name__ == "__main__":
    test_storage_service()
