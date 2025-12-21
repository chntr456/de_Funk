#!/usr/bin/env python3
"""
de_Funk Distributed Pipeline Runner

Runs the full data ingestion pipeline distributed across the Ray cluster.
Uses existing config files for rate limits and API configuration.

This is a cluster-aware wrapper around the existing pipeline infrastructure.

Usage:
    python scripts/cluster/run_distributed_pipeline.py [options]

Options:
    --max-tickers N     Maximum tickers to ingest (default: from config or all)
    --days N            Number of days of data (default: 30)
    --dry-run           Simulate without API calls
    --skip-bronze       Skip bronze layer ingestion
    --skip-silver       Skip silver layer build
    --log-level LEVEL   Logging level (DEBUG, INFO, WARNING, ERROR)
"""

from __future__ import annotations

import sys
import os
import time
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import ray

# Import existing infrastructure
from config import ConfigLoader
from config.logging import setup_logging, get_logger


# =============================================================================
# Load configuration from existing config files
# =============================================================================

def load_pipeline_config(provider: str) -> dict:
    """
    Load pipeline configuration from existing config files.

    Args:
        provider: Provider name (alpha_vantage, bls, chicago)

    Returns:
        Config dict with rate_limit_per_sec, endpoints, etc.
    """
    config_path = project_root / "configs" / "pipelines" / f"{provider}_endpoints.json"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        return json.load(f)


def load_api_keys(provider: str) -> List[str]:
    """
    Load API keys from environment variables.

    Args:
        provider: Provider name

    Returns:
        List of API keys
    """
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")

    env_var_map = {
        "alpha_vantage": "ALPHA_VANTAGE_API_KEYS",
        "bls": "BLS_API_KEYS",
        "chicago": "CHICAGO_API_KEYS",
    }

    env_var = env_var_map.get(provider)
    if not env_var:
        return []

    keys = os.getenv(env_var, "")
    return [k.strip() for k in keys.split(",") if k.strip()]


# =============================================================================
# Distributed Key Manager (Ray Actor)
# =============================================================================

@ray.remote
class DistributedKeyManager:
    """
    Ray Actor for coordinated API key management across workers.

    Reads rate limits from existing config files - does NOT hardcode values.
    """

    def __init__(self, providers: List[str]):
        """
        Initialize key manager from existing config files.

        Args:
            providers: List of provider names to initialize
        """
        import logging
        self.logger = logging.getLogger("ray.key_manager")
        self.providers = {}

        for provider in providers:
            try:
                config = load_pipeline_config(provider)
                keys = load_api_keys(provider)

                # Read rate limit from config file
                rate_limit_per_sec = config.get("rate_limit_per_sec", 1.0)

                self.providers[provider] = {
                    "keys": keys,
                    "rate_limit_per_sec": rate_limit_per_sec,
                    "current_key_idx": 0,
                    "tokens": rate_limit_per_sec,  # Start with full bucket
                    "last_refill": time.time(),
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "wait_time_total": 0,
                    "config": config,
                }

                self.logger.info(
                    f"{provider}: {len(keys)} keys, "
                    f"{rate_limit_per_sec} req/sec ({rate_limit_per_sec * 60:.0f}/min)"
                )

            except Exception as e:
                self.logger.error(f"Failed to load config for {provider}: {e}")

    def _refill_tokens(self, provider: str):
        """Refill tokens based on elapsed time (token bucket algorithm)."""
        state = self.providers[provider]
        now = time.time()
        elapsed = now - state["last_refill"]

        # Refill at rate_limit_per_sec tokens per second
        tokens_to_add = elapsed * state["rate_limit_per_sec"]
        state["tokens"] = min(state["rate_limit_per_sec"], state["tokens"] + tokens_to_add)
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
        self._refill_tokens(provider)

        wait_time = 0
        wait_start = time.time()

        # Wait until a token is available
        while state["tokens"] < 1:
            time.sleep(0.05)  # 50ms check interval
            wait_time = time.time() - wait_start
            self._refill_tokens(provider)

        # Consume a token
        state["tokens"] -= 1
        state["total_requests"] += 1
        state["wait_time_total"] += wait_time

        # Round-robin key selection
        key = state["keys"][state["current_key_idx"]] if state["keys"] else None
        state["current_key_idx"] = (state["current_key_idx"] + 1) % max(len(state["keys"]), 1)

        return {
            "key": key,
            "provider": provider,
            "wait_time": wait_time,
            "request_num": state["total_requests"],
        }

    def report_result(self, provider: str, success: bool):
        """Report request result for tracking."""
        if provider in self.providers:
            if success:
                self.providers[provider]["successful_requests"] += 1
            else:
                self.providers[provider]["failed_requests"] += 1

    def get_stats(self) -> dict:
        """Get usage statistics for all providers."""
        stats = {}
        for provider, state in self.providers.items():
            total = state["total_requests"]
            stats[provider] = {
                "total_requests": total,
                "successful_requests": state["successful_requests"],
                "failed_requests": state["failed_requests"],
                "success_rate": state["successful_requests"] / max(total, 1),
                "total_wait_time": state["wait_time_total"],
                "avg_wait_time": state["wait_time_total"] / max(total, 1),
                "rate_limit_per_sec": state["rate_limit_per_sec"],
            }
        return stats

    def get_config(self, provider: str) -> dict:
        """Get the full config for a provider."""
        if provider in self.providers:
            return self.providers[provider]["config"]
        return {}


# =============================================================================
# Progress Tracker (Ray Actor)
# =============================================================================

@ray.remote
class ProgressTracker:
    """Ray Actor for tracking pipeline progress across workers."""

    def __init__(self, total_tasks: int, description: str = "Processing"):
        import logging
        self.logger = logging.getLogger("ray.progress")
        self.total = total_tasks
        self.completed = 0
        self.successful = 0
        self.failed = 0
        self.description = description
        self.start_time = time.time()
        self.task_times = []

        self.logger.info(f"Starting: {description} ({total_tasks} tasks)")

    def update(self, success: bool = True, task_time: float = 0):
        """Update progress after a task completes."""
        self.completed += 1
        if success:
            self.successful += 1
        else:
            self.failed += 1
        self.task_times.append(task_time)

        # Log progress at intervals
        if self.completed % max(self.total // 10, 5) == 0 or self.completed == self.total:
            pct = (self.completed / self.total) * 100
            elapsed = time.time() - self.start_time
            rate = self.completed / elapsed if elapsed > 0 else 0
            eta = (self.total - self.completed) / rate if rate > 0 else 0

            self.logger.info(
                f"{self.description}: {self.completed}/{self.total} ({pct:.0f}%) | "
                f"OK: {self.successful} | Fail: {self.failed} | "
                f"Rate: {rate:.1f}/s | ETA: {eta:.0f}s"
            )

    def get_status(self) -> dict:
        """Get current progress status."""
        elapsed = time.time() - self.start_time
        return {
            "total": self.total,
            "completed": self.completed,
            "successful": self.successful,
            "failed": self.failed,
            "percent": (self.completed / self.total) * 100 if self.total > 0 else 0,
            "elapsed": elapsed,
            "rate": self.completed / elapsed if elapsed > 0 else 0,
            "avg_task_time": sum(self.task_times) / len(self.task_times) if self.task_times else 0,
        }


# =============================================================================
# Distributed Ingestion Tasks
# =============================================================================

@ray.remote
def ingest_ticker_data(
    ticker: str,
    key_manager,
    progress_tracker,
    endpoints: List[str],
    storage_path: str,
    dry_run: bool = False
) -> dict:
    """
    Ingest all data for a single ticker using existing infrastructure patterns.
    """
    import socket
    import logging
    import json
    import requests
    from pathlib import Path

    logger = logging.getLogger("ray.ingest")
    hostname = socket.gethostname()
    start_time = time.time()

    result = {
        "ticker": ticker,
        "hostname": hostname,
        "endpoints": {},
        "success": True,
        "errors": [],
    }

    # Get config from key manager
    config = ray.get(key_manager.get_config.remote("alpha_vantage"))
    base_url = config.get("base_urls", {}).get("core", "https://www.alphavantage.co/query")

    for endpoint in endpoints:
        endpoint_config = config.get("endpoints", {}).get(endpoint, {})
        if not endpoint_config:
            continue

        try:
            # Acquire API key with rate limiting
            key_info = ray.get(key_manager.acquire_key.remote("alpha_vantage"))
            api_key = key_info["key"]

            if dry_run:
                # Simulate API response
                import random
                time.sleep(random.uniform(0.05, 0.15))
                result["endpoints"][endpoint] = {
                    "success": random.random() > 0.02,
                    "simulated": True,
                }
            else:
                # Real API call
                params = {**endpoint_config.get("default_query", {})}
                params["symbol"] = ticker
                params["apikey"] = api_key

                response = requests.get(base_url, params=params, timeout=30)
                data = response.json()

                # Check for errors
                if "Error Message" in data or "Note" in data:
                    result["endpoints"][endpoint] = {
                        "success": False,
                        "error": data.get("Error Message") or data.get("Note"),
                    }
                    result["errors"].append(f"{endpoint}: {data.get('Error Message') or data.get('Note')}")
                else:
                    # Write to storage
                    output_dir = Path(storage_path) / "bronze" / "alpha_vantage" / endpoint
                    output_dir.mkdir(parents=True, exist_ok=True)

                    output_file = output_dir / f"{ticker}.json"
                    with open(output_file, "w") as f:
                        json.dump(data, f)

                    result["endpoints"][endpoint] = {
                        "success": True,
                        "file": str(output_file),
                    }

            # Report result
            success = result["endpoints"].get(endpoint, {}).get("success", False)
            ray.get(key_manager.report_result.remote("alpha_vantage", success))

        except Exception as e:
            result["endpoints"][endpoint] = {"success": False, "error": str(e)}
            result["errors"].append(f"{endpoint}: {str(e)}")
            logger.error(f"Error ingesting {ticker}/{endpoint}: {e}")

    # Calculate overall success
    endpoint_results = result["endpoints"].values()
    result["success"] = all(r.get("success", False) for r in endpoint_results) if endpoint_results else False

    # Update progress
    elapsed = time.time() - start_time
    result["elapsed"] = elapsed
    ray.get(progress_tracker.update.remote(result["success"], elapsed))

    return result


# =============================================================================
# Pipeline Orchestration
# =============================================================================

def get_ticker_list(storage_path: str, max_tickers: Optional[int] = None) -> List[str]:
    """
    Get list of tickers from existing bronze data or config.

    Args:
        storage_path: Path to storage directory
        max_tickers: Optional limit

    Returns:
        List of ticker symbols
    """
    # Try to read from existing reference data
    ref_path = Path(storage_path) / "bronze" / "alpha_vantage" / "company_overview"

    if ref_path.exists():
        tickers = [f.stem for f in ref_path.glob("*.json")]
        if tickers:
            if max_tickers:
                return sorted(tickers)[:max_tickers]
            return sorted(tickers)

    # Fallback: read from listing_status if available
    listing_path = Path(storage_path) / "bronze" / "alpha_vantage" / "listing_status"
    if listing_path.exists():
        import csv
        for csv_file in listing_path.glob("*.csv"):
            with open(csv_file) as f:
                reader = csv.DictReader(f)
                tickers = [row["symbol"] for row in reader if row.get("symbol")]
                if max_tickers:
                    return tickers[:max_tickers]
                return tickers

    # No existing data - return empty and let caller handle
    return []


def main():
    """Main pipeline entry point."""
    parser = argparse.ArgumentParser(
        description="Run distributed ingestion pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry run with 50 tickers
    python scripts/cluster/run_distributed_pipeline.py --dry-run --max-tickers 50

    # Live ingestion for 100 tickers
    python scripts/cluster/run_distributed_pipeline.py --max-tickers 100

    # Full pipeline with silver build
    python scripts/cluster/run_distributed_pipeline.py --max-tickers 500
        """
    )
    parser.add_argument("--max-tickers", type=int, default=None, help="Max tickers to ingest")
    parser.add_argument("--days", type=int, default=30, help="Days of historical data")
    parser.add_argument("--dry-run", action="store_true", help="Simulate API calls")
    parser.add_argument("--skip-bronze", action="store_true", help="Skip bronze ingestion")
    parser.add_argument("--skip-silver", action="store_true", help="Skip silver build")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument("--storage-path", default=None, help="Storage path (auto-detected)")
    parser.add_argument("--endpoints", default="time_series_daily,company_overview",
                       help="Comma-separated endpoints to ingest")
    args = parser.parse_args()

    # Setup logging
    setup_logging()
    logger = get_logger("de_funk.distributed_pipeline")

    print("\n" + "=" * 70)
    print("  de_Funk Distributed Pipeline")
    print("=" * 70)

    # Load config
    config_loader = ConfigLoader()
    config = config_loader.load()

    # Determine storage path
    storage_path = args.storage_path or str(config.repo_root / "storage")

    # Check for NFS mount on workers
    if Path("/shared/storage").exists():
        storage_path = "/shared/storage"

    logger.info(f"Storage path: {storage_path}")

    # Connect to Ray cluster
    logger.info("Connecting to Ray cluster...")
    try:
        ray.init(address="auto", ignore_reinit_error=True, logging_level=logging.INFO)
        resources = ray.cluster_resources()
        logger.info(f"Connected: {resources.get('CPU', 0):.0f} CPUs, {resources.get('memory', 0) / 1e9:.1f} GB")
    except Exception as e:
        logger.error(f"Failed to connect to Ray cluster: {e}")
        logger.info("Falling back to local execution...")
        ray.init(ignore_reinit_error=True)

    # Load pipeline config to show rate limits
    av_config = load_pipeline_config("alpha_vantage")
    rate_limit = av_config.get("rate_limit_per_sec", 1.0)

    logger.info(f"Configuration:")
    logger.info(f"  Alpha Vantage rate limit: {rate_limit} req/sec ({rate_limit * 60:.0f}/min)")
    logger.info(f"  Dry run: {args.dry_run}")
    logger.info(f"  Endpoints: {args.endpoints}")

    # Get tickers
    tickers = get_ticker_list(storage_path, args.max_tickers)

    if not tickers:
        logger.warning("No tickers found in storage. Using sample list for testing.")
        # Small sample for testing only
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"][:args.max_tickers or 5]

    logger.info(f"  Tickers: {len(tickers)}")

    # Parse endpoints
    endpoints = [e.strip() for e in args.endpoints.split(",")]

    # Create distributed key manager
    logger.info("Initializing distributed key manager...")
    key_manager = DistributedKeyManager.remote(["alpha_vantage", "bls"])

    results = {}

    # Run bronze ingestion
    if not args.skip_bronze:
        logger.info("\n" + "-" * 50)
        logger.info("PHASE 1: Bronze Layer Ingestion")
        logger.info("-" * 50)

        progress = ProgressTracker.remote(len(tickers), "Bronze Ingestion")

        # Submit all tasks
        futures = [
            ingest_ticker_data.remote(
                ticker, key_manager, progress, endpoints, storage_path, args.dry_run
            )
            for ticker in tickers
        ]

        # Wait for completion
        ingestion_results = ray.get(futures)

        # Get final status
        status = ray.get(progress.get_status.remote())

        # Summarize
        successful = sum(1 for r in ingestion_results if r["success"])

        logger.info(f"\nBronze Ingestion Complete:")
        logger.info(f"  Successful: {successful}/{len(tickers)}")
        logger.info(f"  Time: {status['elapsed']:.1f}s")
        logger.info(f"  Rate: {status['rate']:.2f} tickers/sec")

        # Distribution by host
        by_host = {}
        for r in ingestion_results:
            host = r.get("hostname", "unknown")
            by_host[host] = by_host.get(host, 0) + 1
        logger.info(f"  Distribution: {by_host}")

        results["bronze"] = {
            "total": len(tickers),
            "successful": successful,
            "elapsed": status["elapsed"],
            "distribution": by_host,
        }

    # Run silver build (if not dry run and not skipped)
    if not args.skip_silver and not args.dry_run:
        logger.info("\n" + "-" * 50)
        logger.info("PHASE 2: Silver Layer Build")
        logger.info("-" * 50)

        try:
            from models.api.registry import get_model_registry

            registry = get_model_registry()
            for model_name in ["core", "company", "stocks"]:
                try:
                    logger.info(f"Building model: {model_name}")
                    model = registry.get_model(model_name)
                    model.build()
                    logger.info(f"  Built: {model_name}")
                except Exception as e:
                    logger.error(f"  Failed {model_name}: {e}")

        except ImportError as e:
            logger.warning(f"Could not import model registry: {e}")
            logger.info("Run silver build manually: python scripts/build_all_models.py")

    # Get final key manager stats
    key_stats = ray.get(key_manager.get_stats.remote())
    results["key_manager"] = key_stats

    # Print summary
    print("\n" + "=" * 70)
    print("  Pipeline Complete")
    print("=" * 70)

    for provider, stats in key_stats.items():
        if stats["total_requests"] > 0:
            print(f"\n  {provider}:")
            print(f"    Requests: {stats['total_requests']}")
            print(f"    Success rate: {stats['success_rate']*100:.1f}%")
            print(f"    Avg wait: {stats['avg_wait_time']:.3f}s")
            print(f"    Rate limit: {stats['rate_limit_per_sec']} req/sec")

    print("\n  View dashboard: http://192.168.1.212:8265")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
