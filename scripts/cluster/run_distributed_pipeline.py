#!/usr/bin/env python3
"""
de_Funk Distributed Pipeline Runner

Runs the full data ingestion pipeline across the Ray cluster with:
- Distributed API key management with rate limiting
- Parallel ticker ingestion across workers
- Progress reporting to Ray dashboard
- Logging to both console and Ray

Usage:
    python scripts/cluster/run_distributed_pipeline.py [options]

Options:
    --max-tickers N     Maximum tickers to ingest (default: all)
    --provider NAME     Provider to ingest (alpha_vantage, bls, chicago, all)
    --dry-run          Simulate without API calls
    --skip-bronze      Skip bronze layer ingestion
    --skip-silver      Skip silver layer build
    --log-level LEVEL  Logging level (DEBUG, INFO, WARNING, ERROR)
"""

import sys
import os
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import ray
from ray.util.state import list_actors


# =============================================================================
# Logging Configuration
# =============================================================================

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure logging for Ray distributed execution."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [console_handler]

    # Ray logger
    ray_logger = logging.getLogger("ray")
    ray_logger.setLevel(log_level)

    return logging.getLogger("de_funk.pipeline")


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
        import logging
        self.logger = logging.getLogger("ray.key_manager")
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
                "successful_requests": 0,
                "failed_requests": 0,
                "wait_time_total": 0,
            }

        self.logger.info(f"DistributedKeyManager initialized with {len(self.providers)} providers")
        for provider, state in self.providers.items():
            self.logger.info(f"  {provider}: {len(state['keys'])} keys, {state['rate_limit']} req/{state['period']}s")

    def _refill_tokens(self, provider: str):
        """Refill tokens based on elapsed time."""
        state = self.providers[provider]
        now = time.time()
        elapsed = now - state["last_refill"]

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
        self._refill_tokens(provider)

        wait_time = 0
        wait_start = time.time()

        while state["tokens"] < 1:
            sleep_time = 0.1
            time.sleep(sleep_time)
            wait_time = time.time() - wait_start
            self._refill_tokens(provider)

            if wait_time > 0 and int(wait_time) % 10 == 0:
                self.logger.debug(f"Waiting for rate limit... {wait_time:.1f}s")

        state["tokens"] -= 1
        state["total_requests"] += 1
        state["wait_time_total"] += wait_time

        key = state["keys"][state["current_key_idx"]] if state["keys"] else None
        state["current_key_idx"] = (state["current_key_idx"] + 1) % max(len(state["keys"]), 1)

        if wait_time > 1:
            self.logger.info(f"Rate limited {provider} request, waited {wait_time:.1f}s")

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
                "tokens_remaining": state["tokens"],
            }
        return stats


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

        # Log progress every 10% or every 10 tasks
        if self.completed % max(self.total // 10, 10) == 0 or self.completed == self.total:
            pct = (self.completed / self.total) * 100
            elapsed = time.time() - self.start_time
            rate = self.completed / elapsed if elapsed > 0 else 0
            eta = (self.total - self.completed) / rate if rate > 0 else 0

            self.logger.info(
                f"{self.description}: {self.completed}/{self.total} ({pct:.0f}%) | "
                f"Success: {self.successful} | Failed: {self.failed} | "
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
def ingest_ticker_prices(
    ticker: str,
    key_manager,
    progress_tracker,
    storage_path: str,
    dry_run: bool = False
) -> dict:
    """
    Ingest daily price data for a single ticker.
    """
    import socket
    import logging
    import json
    from pathlib import Path
    from datetime import datetime

    logger = logging.getLogger("ray.ingest")
    hostname = socket.gethostname()
    start_time = time.time()

    result = {
        "ticker": ticker,
        "hostname": hostname,
        "success": False,
        "data_points": 0,
        "error": None,
    }

    try:
        # Acquire API key with rate limiting
        key_info = ray.get(key_manager.acquire_key.remote("alpha_vantage"))
        api_key = key_info["key"]

        if dry_run:
            # Simulate API response
            import random
            time.sleep(random.uniform(0.1, 0.3))
            data_points = random.randint(100, 252)
            success = random.random() > 0.02  # 98% success

            if success:
                result["success"] = True
                result["data_points"] = data_points
            else:
                result["error"] = "Simulated API error"
        else:
            # Real API call
            import requests

            url = "https://www.alphavantage.co/query"
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": "full",
                "apikey": api_key,
            }

            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if "Time Series (Daily)" in data:
                time_series = data["Time Series (Daily)"]
                result["success"] = True
                result["data_points"] = len(time_series)

                # Write to storage
                output_dir = Path(storage_path) / "bronze" / "alpha_vantage" / "prices_daily"
                output_dir.mkdir(parents=True, exist_ok=True)

                output_file = output_dir / f"{ticker}.json"
                with open(output_file, "w") as f:
                    json.dump(data, f)

                logger.debug(f"Wrote {result['data_points']} records for {ticker}")
            else:
                result["error"] = data.get("Note", data.get("Error Message", "Unknown error"))
                logger.warning(f"API error for {ticker}: {result['error']}")

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Exception for {ticker}: {e}")

    # Calculate elapsed time
    elapsed = time.time() - start_time
    result["elapsed"] = elapsed
    result["wait_time"] = key_info.get("wait_time", 0) if 'key_info' in dir() else 0

    # Report to key manager and progress tracker
    ray.get(key_manager.report_result.remote("alpha_vantage", result["success"]))
    ray.get(progress_tracker.update.remote(result["success"], elapsed))

    return result


@ray.remote
def ingest_company_overview(
    ticker: str,
    key_manager,
    progress_tracker,
    storage_path: str,
    dry_run: bool = False
) -> dict:
    """
    Ingest company overview data for a single ticker.
    """
    import socket
    import logging
    import json
    from pathlib import Path

    logger = logging.getLogger("ray.ingest")
    hostname = socket.gethostname()
    start_time = time.time()

    result = {
        "ticker": ticker,
        "hostname": hostname,
        "success": False,
        "error": None,
    }

    try:
        key_info = ray.get(key_manager.acquire_key.remote("alpha_vantage"))
        api_key = key_info["key"]

        if dry_run:
            import random
            time.sleep(random.uniform(0.05, 0.2))
            result["success"] = random.random() > 0.02
            if not result["success"]:
                result["error"] = "Simulated error"
        else:
            import requests

            url = "https://www.alphavantage.co/query"
            params = {
                "function": "OVERVIEW",
                "symbol": ticker,
                "apikey": api_key,
            }

            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if "Symbol" in data:
                result["success"] = True

                output_dir = Path(storage_path) / "bronze" / "alpha_vantage" / "company_overview"
                output_dir.mkdir(parents=True, exist_ok=True)

                output_file = output_dir / f"{ticker}.json"
                with open(output_file, "w") as f:
                    json.dump(data, f)
            else:
                result["error"] = data.get("Note", data.get("Error Message", "No data"))

    except Exception as e:
        result["error"] = str(e)

    elapsed = time.time() - start_time
    result["elapsed"] = elapsed

    ray.get(key_manager.report_result.remote("alpha_vantage", result["success"]))
    ray.get(progress_tracker.update.remote(result["success"], elapsed))

    return result


# =============================================================================
# Pipeline Orchestration
# =============================================================================

def get_ticker_list(max_tickers: Optional[int] = None) -> List[str]:
    """Get list of tickers to ingest."""
    # Default ticker list - in production, read from config or existing data
    default_tickers = [
        # Large Cap
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "BRK.B", "JPM", "V",
        "JNJ", "WMT", "PG", "MA", "UNH", "HD", "DIS", "PYPL", "BAC", "NFLX",
        # Tech
        "INTC", "AMD", "CRM", "ORCL", "CSCO", "IBM", "ADBE", "QCOM", "TXN", "AVGO",
        # Finance
        "GS", "MS", "C", "WFC", "AXP", "BLK", "SCHW", "USB", "PNC", "COF",
        # Healthcare
        "PFE", "MRK", "ABBV", "TMO", "ABT", "DHR", "BMY", "LLY", "AMGN", "GILD",
        # Consumer
        "KO", "PEP", "COST", "NKE", "MCD", "SBUX", "TGT", "LOW", "TJX", "BKNG",
        # Industrial
        "BA", "CAT", "HON", "UPS", "RTX", "DE", "MMM", "GE", "LMT", "UNP",
        # Energy
        "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "KMI",
        # Real Estate
        "PLD", "AMT", "CCI", "EQIX", "SPG", "O", "WELL", "DLR", "AVB", "EQR",
        # Utilities
        "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "ED", "WEC",
    ]

    if max_tickers:
        return default_tickers[:max_tickers]
    return default_tickers


def load_api_keys() -> dict:
    """Load API keys from environment."""
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")

    config = {
        "alpha_vantage": {
            "keys": [],
            "rate_limit": 5,  # Free tier: 5/min
            "period": 60,
        },
        "bls": {
            "keys": [],
            "rate_limit": 10,
            "period": 60,
        },
    }

    # Load Alpha Vantage keys
    av_keys = os.getenv("ALPHA_VANTAGE_API_KEYS", "")
    if av_keys:
        config["alpha_vantage"]["keys"] = [k.strip() for k in av_keys.split(",") if k.strip()]
        # Adjust rate limit based on key tier
        if os.getenv("ALPHA_VANTAGE_PREMIUM"):
            config["alpha_vantage"]["rate_limit"] = 75

    # Load BLS keys
    bls_keys = os.getenv("BLS_API_KEYS", "")
    if bls_keys:
        config["bls"]["keys"] = [k.strip() for k in bls_keys.split(",") if k.strip()]

    return config


def run_bronze_ingestion(
    tickers: List[str],
    key_manager,
    storage_path: str,
    dry_run: bool = False,
    logger: logging.Logger = None
) -> dict:
    """Run bronze layer ingestion for all tickers."""

    logger.info(f"Starting bronze ingestion for {len(tickers)} tickers")

    # Create progress tracker
    progress = ProgressTracker.remote(len(tickers) * 2, "Bronze Ingestion")

    # Submit all tasks
    price_futures = []
    overview_futures = []

    for ticker in tickers:
        price_futures.append(
            ingest_ticker_prices.remote(ticker, key_manager, progress, storage_path, dry_run)
        )
        overview_futures.append(
            ingest_company_overview.remote(ticker, key_manager, progress, storage_path, dry_run)
        )

    # Wait for all to complete
    logger.info("Waiting for price ingestion...")
    price_results = ray.get(price_futures)

    logger.info("Waiting for company overview ingestion...")
    overview_results = ray.get(overview_futures)

    # Get final status
    status = ray.get(progress.get_status.remote())

    # Aggregate results
    results = {
        "prices": {
            "total": len(price_results),
            "successful": sum(1 for r in price_results if r["success"]),
            "failed": sum(1 for r in price_results if not r["success"]),
            "data_points": sum(r.get("data_points", 0) for r in price_results),
        },
        "overviews": {
            "total": len(overview_results),
            "successful": sum(1 for r in overview_results if r["success"]),
            "failed": sum(1 for r in overview_results if not r["success"]),
        },
        "timing": {
            "elapsed": status["elapsed"],
            "rate": status["rate"],
            "avg_task_time": status["avg_task_time"],
        },
        "distribution": {},
    }

    # Count by host
    for r in price_results + overview_results:
        host = r.get("hostname", "unknown")
        results["distribution"][host] = results["distribution"].get(host, 0) + 1

    return results


def run_silver_build(storage_path: str, logger: logging.Logger) -> dict:
    """Build silver layer models from bronze data."""

    logger.info("Building silver layer models...")

    # Import model building components
    try:
        from models.api.registry import get_model_registry

        registry = get_model_registry()
        models_built = []

        for model_name in ["core", "company", "stocks"]:
            try:
                logger.info(f"Building model: {model_name}")
                model = registry.get_model(model_name)
                model.build()
                models_built.append(model_name)
                logger.info(f"Successfully built: {model_name}")
            except Exception as e:
                logger.error(f"Failed to build {model_name}: {e}")

        return {"models_built": models_built, "success": len(models_built) > 0}

    except ImportError as e:
        logger.warning(f"Could not import model registry: {e}")
        logger.info("Skipping silver build - run manually with: python scripts/build_all_models.py")
        return {"models_built": [], "success": False, "skipped": True}


def main():
    """Main pipeline entry point."""
    parser = argparse.ArgumentParser(description="Run distributed ingestion pipeline")
    parser.add_argument("--max-tickers", type=int, default=None, help="Max tickers to ingest")
    parser.add_argument("--provider", default="alpha_vantage", help="Provider to ingest")
    parser.add_argument("--dry-run", action="store_true", help="Simulate API calls")
    parser.add_argument("--skip-bronze", action="store_true", help="Skip bronze ingestion")
    parser.add_argument("--skip-silver", action="store_true", help="Skip silver build")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument("--storage-path", default="/shared/storage", help="Storage path")
    args = parser.parse_args()

    # Setup logging
    logger = setup_logging(args.log_level)

    print("\n" + "=" * 70)
    print("  de_Funk Distributed Pipeline")
    print("=" * 70)

    # Connect to Ray cluster
    logger.info("Connecting to Ray cluster...")
    try:
        ray.init(address="auto", ignore_reinit_error=True, logging_level=logging.INFO)
        resources = ray.cluster_resources()
        logger.info(f"Connected: {resources.get('CPU', 0):.0f} CPUs, {resources.get('memory', 0) / 1e9:.1f} GB")
    except Exception as e:
        logger.error(f"Failed to connect to Ray cluster: {e}")
        return 1

    # Load configuration
    api_config = load_api_keys()
    tickers = get_ticker_list(args.max_tickers)

    logger.info(f"Configuration:")
    logger.info(f"  Tickers: {len(tickers)}")
    logger.info(f"  Dry run: {args.dry_run}")
    logger.info(f"  Storage: {args.storage_path}")
    for provider, cfg in api_config.items():
        logger.info(f"  {provider}: {len(cfg['keys'])} keys, {cfg['rate_limit']} req/min")

    # Create key manager
    logger.info("Initializing distributed key manager...")
    key_manager = DistributedKeyManager.remote(api_config)

    results = {}

    # Run bronze ingestion
    if not args.skip_bronze:
        logger.info("\n" + "-" * 50)
        logger.info("PHASE 1: Bronze Layer Ingestion")
        logger.info("-" * 50)

        bronze_results = run_bronze_ingestion(
            tickers=tickers,
            key_manager=key_manager,
            storage_path=args.storage_path,
            dry_run=args.dry_run,
            logger=logger
        )
        results["bronze"] = bronze_results

        logger.info("\nBronze Ingestion Complete:")
        logger.info(f"  Prices: {bronze_results['prices']['successful']}/{bronze_results['prices']['total']} successful")
        logger.info(f"  Overviews: {bronze_results['overviews']['successful']}/{bronze_results['overviews']['total']} successful")
        logger.info(f"  Data points: {bronze_results['prices']['data_points']:,}")
        logger.info(f"  Time: {bronze_results['timing']['elapsed']:.1f}s")
        logger.info(f"  Distribution: {bronze_results['distribution']}")

    # Run silver build
    if not args.skip_silver and not args.dry_run:
        logger.info("\n" + "-" * 50)
        logger.info("PHASE 2: Silver Layer Build")
        logger.info("-" * 50)

        silver_results = run_silver_build(args.storage_path, logger)
        results["silver"] = silver_results

    # Get final key manager stats
    key_stats = ray.get(key_manager.get_stats.remote())
    results["key_manager"] = key_stats

    # Print summary
    print("\n" + "=" * 70)
    print("  Pipeline Complete")
    print("=" * 70)

    for provider, stats in key_stats.items():
        print(f"\n  {provider}:")
        print(f"    Requests: {stats['total_requests']}")
        print(f"    Success rate: {stats['success_rate']*100:.1f}%")
        print(f"    Avg wait: {stats['avg_wait_time']:.2f}s")

    print("\n  View dashboard: http://192.168.1.212:8265")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
