#!/usr/bin/env python3
"""
de_Funk Distributed Pipeline Runner

Runs the full data ingestion pipeline distributed across the Ray cluster.
All parameters are configurable via configs/pipelines/run_config.json.
CLI arguments override config file defaults.

Usage:
    python scripts/cluster/run_distributed_pipeline.py [options]

Options:
    --profile NAME      Load named profile from config (quick_test, dev, staging, production)
    --max-tickers N     Maximum tickers to ingest
    --days N            Number of days of data
    --dry-run           Simulate without API calls
    --skip-bronze       Skip bronze layer ingestion
    --skip-silver       Skip silver layer build
    --log-level LEVEL   Logging level (DEBUG, INFO, WARNING, ERROR)
    --endpoints LIST    Comma-separated endpoints to ingest
    --show-config       Show effective configuration and exit

Examples:
    # Quick test with profile
    python scripts/cluster/run_distributed_pipeline.py --profile quick_test

    # Override profile settings
    python scripts/cluster/run_distributed_pipeline.py --profile dev --max-tickers 100

    # Show what would run
    python scripts/cluster/run_distributed_pipeline.py --profile staging --show-config
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
from copy import deepcopy

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import ray

# Import existing infrastructure
from config import ConfigLoader
from config.logging import setup_logging, get_logger


# =============================================================================
# Configuration Loading
# =============================================================================

def load_run_config() -> dict:
    """
    Load the pipeline run configuration from configs/pipelines/run_config.json.

    Returns:
        Full run configuration dict
    """
    config_path = project_root / "configs" / "pipelines" / "run_config.json"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Run config not found: {config_path}\n"
            "Create this file or copy from run_config.json.example"
        )

    with open(config_path) as f:
        return json.load(f)


def load_pipeline_config(provider: str) -> dict:
    """
    Load pipeline configuration for a specific provider.

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


def build_effective_config(run_config: dict, args: argparse.Namespace) -> dict:
    """
    Build effective configuration by merging: defaults <- profile <- CLI args.

    Priority (highest to lowest):
    1. CLI arguments (if explicitly provided)
    2. Profile settings (if --profile specified)
    3. Default values from config file

    Args:
        run_config: Full run configuration from file
        args: Parsed CLI arguments

    Returns:
        Merged effective configuration
    """
    # Start with defaults
    effective = deepcopy(run_config.get("defaults", {}))

    # Add other sections
    effective["providers"] = deepcopy(run_config.get("providers", {}))
    effective["silver_models"] = deepcopy(run_config.get("silver_models", {}))
    effective["cluster"] = deepcopy(run_config.get("cluster", {}))
    effective["ticker_source"] = deepcopy(run_config.get("ticker_source", {}))
    effective["retry"] = deepcopy(run_config.get("retry", {}))

    # Apply profile if specified
    if args.profile:
        profiles = run_config.get("profiles", {})
        if args.profile not in profiles:
            available = [k for k in profiles.keys() if not k.startswith("_")]
            raise ValueError(
                f"Unknown profile: {args.profile}\n"
                f"Available profiles: {', '.join(available)}"
            )

        profile = profiles[args.profile]
        for key, value in profile.items():
            if not key.startswith("_"):
                effective[key] = value

    # Override with CLI arguments (only if explicitly provided)
    cli_overrides = {
        "max_tickers": args.max_tickers,
        "days": args.days,
        "dry_run": args.dry_run if args.dry_run else None,  # Only if flag set
        "skip_bronze": args.skip_bronze if args.skip_bronze else None,
        "skip_silver": args.skip_silver if args.skip_silver else None,
        "log_level": args.log_level if args.log_level != "INFO" else None,
        "storage_path": args.storage_path,
    }

    for key, value in cli_overrides.items():
        if value is not None:
            effective[key] = value

    # Handle endpoints override
    if args.endpoints:
        effective["providers"]["alpha_vantage"]["endpoints"] = [
            e.strip() for e in args.endpoints.split(",")
        ]

    return effective


def show_config(effective: dict, run_config: dict):
    """Display effective configuration for debugging."""
    print("\n" + "=" * 70)
    print("  Effective Configuration")
    print("=" * 70)

    print("\nRun Parameters:")
    print(f"  max_tickers:  {effective.get('max_tickers', 'all')}")
    print(f"  days:         {effective.get('days', 30)}")
    print(f"  dry_run:      {effective.get('dry_run', False)}")
    print(f"  skip_bronze:  {effective.get('skip_bronze', False)}")
    print(f"  skip_silver:  {effective.get('skip_silver', False)}")
    print(f"  log_level:    {effective.get('log_level', 'INFO')}")
    print(f"  storage_path: {effective.get('storage_path', 'auto-detect')}")

    print("\nProviders:")
    for provider, settings in effective.get("providers", {}).items():
        if isinstance(settings, dict):
            enabled = settings.get("enabled", False)
            endpoints = settings.get("endpoints", settings.get("series", []))
            print(f"  {provider}: {'ENABLED' if enabled else 'disabled'}")
            if enabled and endpoints:
                print(f"    endpoints: {', '.join(endpoints)}")

    print("\nSilver Models:")
    silver = effective.get("silver_models", {})
    if silver.get("enabled", True):
        models = silver.get("models", [])
        print(f"  models: {', '.join(models)}")
        print(f"  skip_on_dry_run: {silver.get('skip_on_dry_run', True)}")
    else:
        print("  disabled")

    print("\nCluster:")
    cluster = effective.get("cluster", {})
    print(f"  ray_address: {cluster.get('ray_address', 'auto')}")
    print(f"  fallback_to_local: {cluster.get('fallback_to_local', True)}")

    print("\nRate Limits (from provider configs):")
    for provider in ["alpha_vantage", "bls"]:
        try:
            config = load_pipeline_config(provider)
            rate = config.get("rate_limit_per_sec", "not set")
            print(f"  {provider}: {rate} req/sec ({float(rate) * 60:.0f}/min)")
        except FileNotFoundError:
            print(f"  {provider}: config not found")

    print("\nAvailable Profiles:")
    for name, profile in run_config.get("profiles", {}).items():
        if not name.startswith("_"):
            desc = ", ".join(f"{k}={v}" for k, v in profile.items() if not k.startswith("_"))
            print(f"  {name}: {desc}")

    print()


# =============================================================================
# Distributed Key Manager (Ray Actor)
# =============================================================================

@ray.remote
class DistributedKeyManager:
    """
    Ray Actor for coordinated API key management across workers.

    Reads rate limits from existing config files - does NOT hardcode values.
    """

    def __init__(self, providers: List[str], retry_config: dict = None):
        """
        Initialize key manager from existing config files.

        Args:
            providers: List of provider names to initialize
            retry_config: Retry configuration from run_config
        """
        import logging
        self.logger = logging.getLogger("ray.key_manager")
        self.providers = {}
        self.retry_config = retry_config or {"max_retries": 3, "retry_delay_seconds": 2.0}

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
                    "retried_requests": 0,
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

    def report_result(self, provider: str, success: bool, was_retry: bool = False):
        """Report request result for tracking."""
        if provider in self.providers:
            if success:
                self.providers[provider]["successful_requests"] += 1
            else:
                self.providers[provider]["failed_requests"] += 1
            if was_retry:
                self.providers[provider]["retried_requests"] += 1

    def get_stats(self) -> dict:
        """Get usage statistics for all providers."""
        stats = {}
        for provider, state in self.providers.items():
            total = state["total_requests"]
            stats[provider] = {
                "total_requests": total,
                "successful_requests": state["successful_requests"],
                "failed_requests": state["failed_requests"],
                "retried_requests": state["retried_requests"],
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

    def get_retry_config(self) -> dict:
        """Get retry configuration."""
        return self.retry_config


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

    # Get config and retry settings from key manager
    config = ray.get(key_manager.get_config.remote("alpha_vantage"))
    retry_config = ray.get(key_manager.get_retry_config.remote())
    base_url = config.get("base_urls", {}).get("core", "https://www.alphavantage.co/query")

    max_retries = retry_config.get("max_retries", 3)
    retry_delay = retry_config.get("retry_delay_seconds", 2.0)
    exponential_backoff = retry_config.get("exponential_backoff", True)

    for endpoint in endpoints:
        endpoint_config = config.get("endpoints", {}).get(endpoint, {})
        if not endpoint_config:
            continue

        retries = 0
        success = False

        while retries <= max_retries and not success:
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
                    success = True
                else:
                    # Real API call
                    params = {**endpoint_config.get("default_query", {})}
                    params["symbol"] = ticker
                    params["apikey"] = api_key

                    response = requests.get(base_url, params=params, timeout=30)
                    data = response.json()

                    # Check for errors
                    if "Error Message" in data or "Note" in data:
                        error_msg = data.get("Error Message") or data.get("Note")

                        # Rate limit hit - retry
                        if "rate limit" in str(error_msg).lower() or "Note" in data:
                            retries += 1
                            if retries <= max_retries:
                                delay = retry_delay * (2 ** (retries - 1)) if exponential_backoff else retry_delay
                                time.sleep(delay)
                                ray.get(key_manager.report_result.remote("alpha_vantage", False, True))
                                continue

                        result["endpoints"][endpoint] = {
                            "success": False,
                            "error": error_msg,
                        }
                        result["errors"].append(f"{endpoint}: {error_msg}")
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

                    success = True

                # Report result
                endpoint_success = result["endpoints"].get(endpoint, {}).get("success", False)
                ray.get(key_manager.report_result.remote("alpha_vantage", endpoint_success))

            except requests.exceptions.Timeout:
                retries += 1
                if retries <= max_retries:
                    delay = retry_delay * (2 ** (retries - 1)) if exponential_backoff else retry_delay
                    time.sleep(delay)
                else:
                    result["endpoints"][endpoint] = {"success": False, "error": "Timeout after retries"}
                    result["errors"].append(f"{endpoint}: Timeout")

            except Exception as e:
                result["endpoints"][endpoint] = {"success": False, "error": str(e)}
                result["errors"].append(f"{endpoint}: {str(e)}")
                logger.error(f"Error ingesting {ticker}/{endpoint}: {e}")
                success = True  # Don't retry on unknown errors

    # Calculate overall success
    endpoint_results = result["endpoints"].values()
    result["success"] = all(r.get("success", False) for r in endpoint_results) if endpoint_results else False

    # Update progress
    elapsed = time.time() - start_time
    result["elapsed"] = elapsed
    ray.get(progress_tracker.update.remote(result["success"], elapsed))

    return result


# =============================================================================
# Ticker Discovery
# =============================================================================

def get_ticker_list(
    storage_path: str,
    ticker_source_config: dict,
    max_tickers: Optional[int] = None
) -> List[str]:
    """
    Get list of tickers based on configured sources.

    Args:
        storage_path: Path to storage directory
        ticker_source_config: Ticker source configuration
        max_tickers: Optional limit

    Returns:
        List of ticker symbols
    """
    priority = ticker_source_config.get("priority", ["bronze_reference", "listing_status"])

    for source in priority:
        tickers = []

        if source == "bronze_reference":
            ref_path = Path(storage_path) / ticker_source_config.get(
                "bronze_reference_path", "bronze/alpha_vantage/company_overview"
            )
            if ref_path.exists():
                tickers = [f.stem for f in ref_path.glob("*.json")]

        elif source == "listing_status":
            listing_path = Path(storage_path) / ticker_source_config.get(
                "listing_status_path", "bronze/alpha_vantage/listing_status"
            )
            if listing_path.exists():
                import csv
                for csv_file in listing_path.glob("*.csv"):
                    with open(csv_file) as f:
                        reader = csv.DictReader(f)
                        tickers = [row["symbol"] for row in reader if row.get("symbol")]
                    break

        if tickers:
            tickers = sorted(set(tickers))
            if max_tickers:
                return tickers[:max_tickers]
            return tickers

    # No tickers found from any source
    return []


# =============================================================================
# Main Pipeline
# =============================================================================

def main():
    """Main pipeline entry point."""
    parser = argparse.ArgumentParser(
        description="Run distributed ingestion pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Use a profile
    python scripts/cluster/run_distributed_pipeline.py --profile quick_test

    # Override profile settings
    python scripts/cluster/run_distributed_pipeline.py --profile dev --max-tickers 100

    # Show effective config
    python scripts/cluster/run_distributed_pipeline.py --profile staging --show-config

    # Custom run
    python scripts/cluster/run_distributed_pipeline.py --max-tickers 50 --dry-run
        """
    )

    # Profile selection
    parser.add_argument("--profile", type=str, default=None,
                       help="Load named profile (quick_test, dev, staging, production)")

    # Run parameters (override config/profile)
    parser.add_argument("--max-tickers", type=int, default=None,
                       help="Max tickers to ingest")
    parser.add_argument("--days", type=int, default=None,
                       help="Days of historical data")
    parser.add_argument("--dry-run", action="store_true",
                       help="Simulate API calls")
    parser.add_argument("--skip-bronze", action="store_true",
                       help="Skip bronze ingestion")
    parser.add_argument("--skip-silver", action="store_true",
                       help="Skip silver build")
    parser.add_argument("--log-level", default="INFO",
                       help="Logging level")
    parser.add_argument("--storage-path", default=None,
                       help="Storage path (auto-detected)")
    parser.add_argument("--endpoints", default=None,
                       help="Comma-separated endpoints to ingest")

    # Utility options
    parser.add_argument("--show-config", action="store_true",
                       help="Show effective configuration and exit")

    args = parser.parse_args()

    # Load run configuration
    try:
        run_config = load_run_config()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    # Build effective configuration
    try:
        effective = build_effective_config(run_config, args)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    # Show config and exit if requested
    if args.show_config:
        show_config(effective, run_config)
        return 0

    # Setup logging
    setup_logging()
    logger = get_logger("de_funk.distributed_pipeline")

    print("\n" + "=" * 70)
    print("  de_Funk Distributed Pipeline")
    print("=" * 70)

    if args.profile:
        print(f"  Profile: {args.profile}")

    # Load app config for storage path
    config_loader = ConfigLoader()
    app_config = config_loader.load()

    # Determine storage path
    storage_path = effective.get("storage_path")
    if not storage_path:
        storage_path = str(app_config.repo_root / "storage")
        # Check for NFS mount on workers
        if Path("/shared/storage").exists():
            storage_path = "/shared/storage"

    logger.info(f"Storage path: {storage_path}")

    # Connect to Ray cluster
    cluster_config = effective.get("cluster", {})
    ray_address = cluster_config.get("ray_address", "auto")

    logger.info(f"Connecting to Ray cluster ({ray_address})...")
    try:
        ray.init(address=ray_address, ignore_reinit_error=True, logging_level=logging.INFO)
        resources = ray.cluster_resources()
        logger.info(f"Connected: {resources.get('CPU', 0):.0f} CPUs, {resources.get('memory', 0) / 1e9:.1f} GB")
    except Exception as e:
        if cluster_config.get("fallback_to_local", True):
            logger.warning(f"Failed to connect to cluster: {e}")
            logger.info("Falling back to local execution...")
            ray.init(ignore_reinit_error=True)
        else:
            logger.error(f"Failed to connect to Ray cluster: {e}")
            return 1

    # Show configuration
    av_config = load_pipeline_config("alpha_vantage")
    rate_limit = av_config.get("rate_limit_per_sec", 1.0)

    dry_run = effective.get("dry_run", False)
    max_tickers = effective.get("max_tickers")

    logger.info(f"Configuration:")
    logger.info(f"  Alpha Vantage rate limit: {rate_limit} req/sec ({rate_limit * 60:.0f}/min)")
    logger.info(f"  Dry run: {dry_run}")

    # Get endpoints from config
    provider_config = effective.get("providers", {}).get("alpha_vantage", {})
    endpoints = provider_config.get("endpoints", ["time_series_daily", "company_overview"])
    logger.info(f"  Endpoints: {', '.join(endpoints)}")

    # Get tickers
    ticker_source = effective.get("ticker_source", {})
    tickers = get_ticker_list(storage_path, ticker_source, max_tickers)

    if not tickers:
        if dry_run:
            # Use test tickers from config for dry-run testing
            test_tickers = ticker_source.get("test_tickers", [])
            if test_tickers:
                tickers = test_tickers[:max_tickers] if max_tickers else test_tickers
                logger.warning(
                    f"No tickers in storage. Using {len(tickers)} test tickers for dry-run."
                )
            else:
                logger.error("No tickers found and no test_tickers configured.")
                return 1
        else:
            logger.error(
                "No tickers found in storage. Run ingestion first:\n"
                "  python -m scripts.ingest.run_full_pipeline --max-tickers 100"
            )
            return 1

    logger.info(f"  Tickers: {len(tickers)}")

    # Create distributed key manager with retry config
    retry_config = effective.get("retry", {})
    enabled_providers = [
        name for name, cfg in effective.get("providers", {}).items()
        if isinstance(cfg, dict) and cfg.get("enabled", False)
    ]
    if not enabled_providers:
        enabled_providers = ["alpha_vantage"]  # Default

    logger.info("Initializing distributed key manager...")
    key_manager = DistributedKeyManager.remote(enabled_providers, retry_config)

    results = {}

    # Run bronze ingestion
    skip_bronze = effective.get("skip_bronze", False)
    if not skip_bronze:
        logger.info("\n" + "-" * 50)
        logger.info("PHASE 1: Bronze Layer Ingestion")
        logger.info("-" * 50)

        progress = ProgressTracker.remote(len(tickers), "Bronze Ingestion")

        # Submit all tasks
        futures = [
            ingest_ticker_data.remote(
                ticker, key_manager, progress, endpoints, storage_path, dry_run
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

    # Run silver build
    skip_silver = effective.get("skip_silver", False)
    silver_config = effective.get("silver_models", {})
    skip_on_dry_run = silver_config.get("skip_on_dry_run", True)

    should_build_silver = (
        not skip_silver and
        silver_config.get("enabled", True) and
        not (dry_run and skip_on_dry_run)
    )

    if should_build_silver:
        logger.info("\n" + "-" * 50)
        logger.info("PHASE 2: Silver Layer Build")
        logger.info("-" * 50)

        import subprocess

        models_to_build = silver_config.get("models", ["core", "company", "stocks"])

        for model_name in models_to_build:
            try:
                logger.info(f"Building model: {model_name}")

                # Use build_silver_duckdb.py which handles all model types
                result = subprocess.run(
                    [sys.executable, "-m", "scripts.build_silver_duckdb", "--model", model_name],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout per model
                )

                if result.returncode == 0:
                    logger.info(f"  Built: {model_name}")
                    # Show any important output
                    if result.stdout:
                        for line in result.stdout.split('\n'):
                            if '✓' in line or 'success' in line.lower():
                                logger.info(f"    {line.strip()}")
                else:
                    logger.error(f"  Failed {model_name}:")
                    if result.stderr:
                        logger.error(f"    {result.stderr[:500]}")
                    elif result.stdout:
                        logger.error(f"    {result.stdout[:500]}")

            except subprocess.TimeoutExpired:
                logger.error(f"  Timeout building {model_name}")
            except Exception as e:
                logger.error(f"  Failed {model_name}: {e}")

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
            print(f"    Retries: {stats['retried_requests']}")
            print(f"    Avg wait: {stats['avg_wait_time']:.3f}s")
            print(f"    Rate limit: {stats['rate_limit_per_sec']} req/sec")

    print("\n  View dashboard: http://192.168.1.212:8265")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
