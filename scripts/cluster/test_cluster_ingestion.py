#!/usr/bin/env python3
"""
de_Funk Cluster Ingestion Test

Tests the distributed data ingestion pipeline including:
1. Distributed Key Manager initialization
2. API rate limiting across workers
3. Parallel ticker ingestion
4. Data writing to shared storage

Usage:
    python scripts/cluster/test_cluster_ingestion.py [--dry-run] [--tickers N]

Options:
    --dry-run       Simulate API calls without hitting real endpoints
    --tickers N     Number of tickers to test (default: 10)
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import ray


def print_header(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_result(test: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "\033[92mPASS\033[0m" if passed else "\033[91mFAIL\033[0m"
    print(f"  [{status}] {test}")
    if details:
        print(f"         {details}")


# =============================================================================
# Distributed Key Manager (Ray Actor)
# =============================================================================

@ray.remote
class DistributedKeyManager:
    """
    Ray Actor for coordinated API key management across workers.
    Implements token bucket rate limiting per provider.
    """

    def __init__(self, config: dict):
        """
        Initialize key manager with provider configurations.

        Args:
            config: Dict of provider -> {keys: [...], rate_limit: N, period: seconds}
        """
        self.config = config
        self.providers = {}

        for provider, settings in config.items():
            keys = settings.get("keys", [])
            rate_limit = settings.get("rate_limit", 5)
            period = settings.get("period", 60)

            self.providers[provider] = {
                "keys": keys,
                "rate_limit": rate_limit,
                "period": period,
                "current_key_idx": 0,
                "tokens": rate_limit,
                "last_refill": time.time(),
                "total_requests": 0,
                "wait_time_total": 0,
            }

        print(f"[KeyManager] Initialized with {len(self.providers)} providers")

    def _refill_tokens(self, provider: str):
        """Refill tokens based on elapsed time."""
        state = self.providers[provider]
        now = time.time()
        elapsed = now - state["last_refill"]

        # Refill rate: rate_limit tokens per period
        refill_rate = state["rate_limit"] / state["period"]
        tokens_to_add = elapsed * refill_rate

        state["tokens"] = min(state["rate_limit"], state["tokens"] + tokens_to_add)
        state["last_refill"] = now

    def acquire_key(self, provider: str) -> dict:
        """
        Acquire an API key with rate limiting.

        Returns:
            {key: str, wait_time: float, request_num: int}
        """
        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")

        state = self.providers[provider]

        # Refill tokens
        self._refill_tokens(provider)

        # Wait if no tokens available
        wait_time = 0
        while state["tokens"] < 1:
            sleep_time = 0.1
            time.sleep(sleep_time)
            wait_time += sleep_time
            self._refill_tokens(provider)

        # Consume a token
        state["tokens"] -= 1
        state["total_requests"] += 1
        state["wait_time_total"] += wait_time

        # Round-robin key selection
        key = state["keys"][state["current_key_idx"]] if state["keys"] else "DEMO_KEY"
        state["current_key_idx"] = (state["current_key_idx"] + 1) % max(len(state["keys"]), 1)

        return {
            "key": key,
            "wait_time": wait_time,
            "request_num": state["total_requests"],
        }

    def get_stats(self) -> dict:
        """Get usage statistics for all providers."""
        stats = {}
        for provider, state in self.providers.items():
            stats[provider] = {
                "total_requests": state["total_requests"],
                "total_wait_time": state["wait_time_total"],
                "avg_wait_time": state["wait_time_total"] / max(state["total_requests"], 1),
                "tokens_remaining": state["tokens"],
            }
        return stats


# =============================================================================
# Distributed Ingestion Tasks
# =============================================================================

@ray.remote
def ingest_ticker(ticker: str, key_manager, dry_run: bool = True) -> dict:
    """
    Ingest data for a single ticker.

    Args:
        ticker: Stock ticker symbol
        key_manager: Ray actor handle for key management
        dry_run: If True, simulate API call

    Returns:
        Dict with ingestion results
    """
    import socket
    import time
    import random

    hostname = socket.gethostname()
    start_time = time.time()

    # Acquire API key (with rate limiting)
    key_info = ray.get(key_manager.acquire_key.remote("alpha_vantage"))

    # Simulate or make real API call
    if dry_run:
        # Simulate API latency
        time.sleep(random.uniform(0.1, 0.3))
        data_points = random.randint(100, 500)
        success = random.random() > 0.05  # 95% success rate
    else:
        # Real API call would go here
        try:
            import requests
            api_key = key_info["key"]
            url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={api_key}"
            response = requests.get(url, timeout=10)
            data = response.json()

            if "Time Series (Daily)" in data:
                data_points = len(data["Time Series (Daily)"])
                success = True
            else:
                data_points = 0
                success = False
        except Exception as e:
            data_points = 0
            success = False

    elapsed = time.time() - start_time

    return {
        "ticker": ticker,
        "hostname": hostname,
        "success": success,
        "data_points": data_points,
        "elapsed": elapsed,
        "wait_time": key_info["wait_time"],
        "request_num": key_info["request_num"],
    }


@ray.remote
def write_to_storage(results: list, storage_path: str) -> dict:
    """
    Write ingestion results to shared storage.

    Args:
        results: List of ingestion result dicts
        storage_path: Path to write results

    Returns:
        Dict with write status
    """
    import socket
    import json
    from datetime import datetime
    from pathlib import Path

    hostname = socket.gethostname()
    path = Path(storage_path)
    path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = path / f"ingestion_test_{timestamp}.json"

    try:
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

        return {
            "success": True,
            "hostname": hostname,
            "file": str(output_file),
            "records": len(results),
        }
    except Exception as e:
        return {
            "success": False,
            "hostname": hostname,
            "error": str(e),
        }


# =============================================================================
# Test Functions
# =============================================================================

def test_key_manager_init():
    """Test 1: Initialize distributed key manager."""
    print_header("Test 1: Distributed Key Manager")

    try:
        config = {
            "alpha_vantage": {
                "keys": ["DEMO_KEY_1", "DEMO_KEY_2"],
                "rate_limit": 5,  # 5 requests per minute
                "period": 60,
            },
            "bls": {
                "keys": ["BLS_KEY_1"],
                "rate_limit": 10,
                "period": 60,
            },
        }

        key_manager = DistributedKeyManager.remote(config)

        # Test acquiring keys
        results = []
        for _ in range(3):
            result = ray.get(key_manager.acquire_key.remote("alpha_vantage"))
            results.append(result)

        print(f"  Acquired {len(results)} keys successfully")
        for i, r in enumerate(results):
            print(f"    Request {i+1}: key={r['key'][:10]}..., wait={r['wait_time']:.2f}s")

        print()
        print_result("Key manager initialized and working", True)

        return key_manager

    except Exception as e:
        print_result("Key manager initialization", False, str(e))
        return None


def test_parallel_ingestion(key_manager, num_tickers: int = 10, dry_run: bool = True):
    """Test 2: Run parallel ingestion across workers."""
    print_header("Test 2: Parallel Ingestion")

    # Sample tickers
    tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META",
        "TSLA", "NVDA", "JPM", "V", "WMT",
        "DIS", "NFLX", "PYPL", "INTC", "AMD",
        "CRM", "ORCL", "CSCO", "IBM", "QCOM",
    ][:num_tickers]

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"  Mode: {mode}")
    print(f"  Ingesting {len(tickers)} tickers in parallel...")

    try:
        start_time = time.time()

        # Launch parallel ingestion tasks
        futures = [
            ingest_ticker.remote(ticker, key_manager, dry_run)
            for ticker in tickers
        ]

        # Collect results
        results = ray.get(futures)
        elapsed = time.time() - start_time

        # Analyze results
        successful = [r for r in results if r["success"]]
        by_host = {}
        for r in results:
            host = r["hostname"]
            by_host[host] = by_host.get(host, 0) + 1

        total_data_points = sum(r["data_points"] for r in successful)
        total_wait_time = sum(r["wait_time"] for r in results)

        print(f"\n  Results:")
        print(f"    Total time:       {elapsed:.2f}s")
        print(f"    Successful:       {len(successful)}/{len(results)}")
        print(f"    Data points:      {total_data_points:,}")
        print(f"    Total wait time:  {total_wait_time:.2f}s")
        print(f"\n  Distribution by host:")
        for host, count in sorted(by_host.items()):
            print(f"    {host}: {count} tickers")

        # Get key manager stats
        stats = ray.get(key_manager.get_stats.remote())
        print(f"\n  Key Manager Stats:")
        for provider, s in stats.items():
            print(f"    {provider}: {s['total_requests']} requests, avg wait {s['avg_wait_time']:.2f}s")

        print()
        success_rate = len(successful) / len(results)
        distributed = len(by_host) >= 2

        print_result(f"Success rate >= 90%", success_rate >= 0.9, f"Got {success_rate*100:.0f}%")
        print_result(f"Distributed across workers", distributed, f"{len(by_host)} hosts used")

        return results, success_rate >= 0.9 and distributed

    except Exception as e:
        print_result("Parallel ingestion", False, str(e))
        return [], False


def test_storage_write(results: list):
    """Test 3: Write results to shared storage."""
    print_header("Test 3: Shared Storage Write")

    storage_path = "/shared/storage/bronze/test_ingestion"

    try:
        # Write from a worker
        write_result = ray.get(
            write_to_storage.remote(results, storage_path)
        )

        if write_result["success"]:
            print(f"  Written by:    {write_result['hostname']}")
            print(f"  File:          {write_result['file']}")
            print(f"  Records:       {write_result['records']}")
            print()
            print_result("Storage write successful", True)
            return True
        else:
            print_result("Storage write", False, write_result.get("error", "Unknown error"))
            return False

    except Exception as e:
        print_result("Storage write", False, str(e))
        return False


def test_rate_limiting(key_manager):
    """Test 4: Verify rate limiting works correctly."""
    print_header("Test 4: Rate Limiting")

    try:
        # Configure for fast rate limiting test
        # Try to exceed rate limit and measure wait times

        print("  Making 10 rapid requests (rate limit: 5/min)...")

        start_time = time.time()
        wait_times = []

        for i in range(10):
            result = ray.get(key_manager.acquire_key.remote("alpha_vantage"))
            wait_times.append(result["wait_time"])
            print(f"    Request {i+1}: wait={result['wait_time']:.2f}s")

        total_time = time.time() - start_time
        total_wait = sum(wait_times)

        print(f"\n  Total time:      {total_time:.2f}s")
        print(f"  Total wait time: {total_wait:.2f}s")

        # With 5 req/min rate limit, requests 6-10 should have to wait
        rate_limited = total_wait > 0.5  # Some waiting occurred

        print()
        print_result("Rate limiting enforced", rate_limited,
                    f"Wait time: {total_wait:.2f}s")

        return rate_limited

    except Exception as e:
        print_result("Rate limiting test", False, str(e))
        return False


def main():
    """Run all ingestion tests."""
    parser = argparse.ArgumentParser(description="Test cluster ingestion")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Simulate API calls (default: True)")
    parser.add_argument("--live", action="store_true",
                       help="Make real API calls")
    parser.add_argument("--tickers", type=int, default=10,
                       help="Number of tickers to test")
    args = parser.parse_args()

    dry_run = not args.live

    print("\n" + "="*60)
    print("  de_Funk Cluster Ingestion Test")
    print("="*60)

    # Connect to cluster
    try:
        ray.init(address="auto", ignore_reinit_error=True)
        print(f"\n  Connected to Ray cluster")
        print(f"  Resources: {ray.cluster_resources()}")
    except Exception as e:
        print(f"\n  Failed to connect to cluster: {e}")
        return 1

    results = {}

    # Test 1: Key Manager
    key_manager = test_key_manager_init()
    results["key_manager"] = key_manager is not None

    if key_manager:
        # Test 2: Parallel Ingestion
        ingestion_results, ingestion_ok = test_parallel_ingestion(
            key_manager, num_tickers=args.tickers, dry_run=dry_run
        )
        results["ingestion"] = ingestion_ok

        # Test 3: Storage Write
        if ingestion_results:
            results["storage"] = test_storage_write(ingestion_results)
        else:
            results["storage"] = False

        # Test 4: Rate Limiting
        results["rate_limiting"] = test_rate_limiting(key_manager)

    # Summary
    print_header("Test Summary")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for test, result in results.items():
        status = "\033[92mPASS\033[0m" if result else "\033[91mFAIL\033[0m"
        print(f"  [{status}] {test}")

    print()
    print(f"  Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n  \033[92mIngestion pipeline is working correctly!\033[0m\n")
        return 0
    else:
        print("\n  \033[91mSome tests failed. Check configuration.\033[0m\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
