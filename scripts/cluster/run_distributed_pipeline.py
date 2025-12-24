#!/usr/bin/env python3
"""
de_Funk Distributed Pipeline Runner

Runs the full data pipeline distributed across the Ray cluster.
Both Bronze ingestion and Silver layer builds run on Ray workers by default.
All parameters are configurable via configs/pipelines/run_config.json.

Usage:
    python scripts/cluster/run_distributed_pipeline.py [options]

Options:
    --profile NAME      Load named profile from config (quick_test, dev, staging, production)
    --max-tickers N     Maximum tickers to ingest
    --days N            Number of days of data
    --dry-run           Simulate without API calls
    --skip-bronze       Skip bronze layer ingestion
    --skip-silver       Skip silver layer build
    --local-silver      Run Silver build on head node only (default is distributed)
    --log-level LEVEL   Logging level (DEBUG, INFO, WARNING, ERROR)
    --endpoints LIST    Comma-separated endpoints to ingest
    --show-config       Show effective configuration and exit

Examples:
    # Full distributed pipeline (default)
    python scripts/cluster/run_distributed_pipeline.py --max-tickers 100

    # Quick test with profile
    python scripts/cluster/run_distributed_pipeline.py --profile quick_test

    # Run Silver build on head node only
    python scripts/cluster/run_distributed_pipeline.py --local-silver

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

# Module-level logger
logger = get_logger(__name__)


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
        "local_silver": args.local_silver if args.local_silver else None,
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

    Configs are passed in from head node (not loaded on workers).
    """

    def __init__(self, provider_configs: Dict[str, dict], retry_config: dict = None):
        """
        Initialize key manager with pre-loaded configs.

        Args:
            provider_configs: Dict of {provider_name: {config, keys}} loaded on head node
            retry_config: Retry configuration from run_config
        """
        import logging
        self.logger = logging.getLogger("ray.key_manager")
        self.providers = {}
        self.retry_config = retry_config or {"max_retries": 3, "retry_delay_seconds": 2.0}

        for provider, provider_data in provider_configs.items():
            try:
                config = provider_data.get("config", {})
                keys = provider_data.get("keys", [])

                # Read rate limit from config
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
                self.logger.error(f"Failed to init provider {provider}: {e}")

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

# =============================================================================
# Endpoint Registry - Maps endpoints to facets and Delta tables
# =============================================================================

# Endpoint -> (facet_module, facet_class, bronze_table, is_batched)
# is_batched=True: facet.normalize(List[List[dict]]) - for prices
# is_batched=False: facet.normalize(dict) - for financial statements
ENDPOINT_REGISTRY = {
    "time_series_daily": ("securities_prices_facet", "SecuritiesPricesFacetAV", "securities_prices_daily", True),
    "time_series_daily_adjusted": ("securities_prices_facet", "SecuritiesPricesFacetAV", "securities_prices_daily", True),
    "income_statement": ("income_statement_facet", "IncomeStatementFacet", "income_statements", False),
    "balance_sheet": ("balance_sheet_facet", "BalanceSheetFacet", "balance_sheets", False),
    "cash_flow": ("cash_flow_facet", "CashFlowFacet", "cash_flows", False),
    "earnings": ("earnings_facet", "EarningsFacet", "earnings", False),
}


def write_to_delta_rs(table_path: str, data: list, schema: dict, mode: str = "append"):
    """
    Write data to Delta table using delta-rs (no JVM required).

    Args:
        table_path: Path to Delta table
        data: List of dicts to write
        schema: PyArrow schema dict
        mode: "append" or "overwrite"
    """
    import pyarrow as pa
    from deltalake import write_deltalake, DeltaTable
    from pathlib import Path

    if not data:
        return 0

    # Convert to PyArrow table
    df = pa.Table.from_pylist(data)

    # Ensure directory exists
    Path(table_path).mkdir(parents=True, exist_ok=True)

    # Write to Delta
    write_deltalake(
        table_path,
        df,
        mode=mode,
        schema_mode="merge",  # Allow schema evolution
    )

    return len(data)


def ensure_calendar_seed(storage_path: str) -> bool:
    """
    Ensure calendar_seed exists in Bronze layer.

    Calendar is static data (2000-2050) that temporal model needs.
    Generate it if missing.
    """
    from pathlib import Path
    from datetime import datetime, timedelta

    calendar_path = Path(storage_path) / "bronze" / "calendar_seed"

    # Check if already exists
    if (calendar_path / "_delta_log").exists():
        return True

    logger.info("Seeding calendar dimension (2000-2050)...")

    # Generate calendar data
    start_date = datetime(2000, 1, 1)
    end_date = datetime(2050, 12, 31)

    records = []
    current = start_date
    while current <= end_date:
        records.append({
            "date": current.strftime("%Y-%m-%d"),
            "year": current.year,
            "month": current.month,
            "day": current.day,
            "day_of_week": current.weekday(),
            "day_of_year": current.timetuple().tm_yday,
            "week_of_year": current.isocalendar()[1],
            "quarter": (current.month - 1) // 3 + 1,
            "is_weekend": current.weekday() >= 5,
            "is_month_start": current.day == 1,
            "is_month_end": (current + timedelta(days=1)).day == 1,
            "is_quarter_start": current.month in [1, 4, 7, 10] and current.day == 1,
            "is_quarter_end": current.month in [3, 6, 9, 12] and (current + timedelta(days=1)).day == 1,
            "is_year_start": current.month == 1 and current.day == 1,
            "is_year_end": current.month == 12 and current.day == 31,
        })
        current += timedelta(days=1)

    # Write to Delta
    rows = write_to_delta_rs(str(calendar_path), records, {}, mode="overwrite")
    logger.info(f"  Calendar seeded: {rows:,} days")

    return True


def transform_time_series(ticker: str, data: dict) -> list:
    """Transform TIME_SERIES_DAILY response to list of dicts."""
    from datetime import datetime

    # Find the time series key
    ts_key = None
    for key in data.keys():
        if "Time Series" in key:
            ts_key = key
            break

    if not ts_key or ts_key not in data:
        return []

    records = []

    for date_str, values in data[ts_key].items():
        records.append({
            "ticker": ticker,
            "trade_date": date_str,
            "open": float(values.get("1. open", 0)),
            "high": float(values.get("2. high", 0)),
            "low": float(values.get("3. low", 0)),
            "close": float(values.get("4. close", 0)),
            "volume": int(float(values.get("5. volume", 0))),
            "adjusted_close": float(values.get("5. adjusted close", values.get("4. close", 0))),
            "year": int(date_str[:4]),
        })

    return records


def transform_financial_statement(ticker: str, data: dict, report_key: str) -> list:
    """Transform financial statement response (income, balance, cash_flow, earnings)."""
    records = []

    # Handle both annual and quarterly reports
    for report_type in ["annualReports", "quarterlyReports"]:
        if report_type not in data:
            continue

        for report in data[report_type]:
            record = {
                "ticker": ticker,
                "report_type": "annual" if report_type == "annualReports" else "quarterly",
            }
            # Copy all fields from the report - keep as strings to avoid type issues
            for key, value in report.items():
                # Convert camelCase to snake_case
                snake_key = ''.join(['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
                # Keep as string to avoid Int64 cast errors with "None" and decimal values
                record[snake_key] = str(value) if value is not None else None

            records.append(record)

    return records


def transform_company_overview(ticker: str, data: dict) -> tuple:
    """Transform OVERVIEW response to company_reference and securities_reference records."""
    # Extract CIK (pad to 10 digits)
    cik = data.get("CIK", "")
    if cik:
        cik = cik.zfill(10)

    # Company reference - for company model dim_company
    company_record = {
        "cik": cik,
        "ticker": ticker,
        "company_name": data.get("Name", ""),
        "sector": data.get("Sector", ""),
        "industry": data.get("Industry", ""),
        "description": data.get("Description", ""),
        "address": data.get("Address", ""),
        "fiscal_year_end": data.get("FiscalYearEnd", ""),
        "exchange_code": data.get("Exchange", ""),
        "country": data.get("Country", ""),
        "currency": data.get("Currency", ""),
        "is_active": True,  # If we got data, it's active
        # Numeric fields from Alpha Vantage
        "shares_outstanding": data.get("SharesOutstanding", ""),
        "market_cap": data.get("MarketCapitalization", ""),
        "pe_ratio": data.get("PERatio", ""),
        "peg_ratio": data.get("PEGRatio", ""),
        "book_value": data.get("BookValue", ""),
        "dividend_per_share": data.get("DividendPerShare", ""),
        "dividend_yield": data.get("DividendYield", ""),
        "eps": data.get("EPS", ""),
        "ebitda": data.get("EBITDA", ""),
        "revenue_ttm": data.get("RevenueTTM", ""),
        "profit_margin": data.get("ProfitMargin", ""),
    }

    # Securities reference - for stocks model dim_stock
    securities_record = {
        "ticker": ticker,
        "security_name": data.get("Name", ""),
        "type": data.get("AssetType", "Common Stock"),  # Raw AV type
        "primary_exchange": data.get("Exchange", ""),
        "cik": cik,
        "country": data.get("Country", ""),
        "currency": data.get("Currency", ""),
        "is_active": True,
        # Additional fields for stocks model
        "shares_outstanding": data.get("SharesOutstanding", ""),
        "market_cap": data.get("MarketCapitalization", ""),
        "sector": data.get("Sector", ""),
        "industry": data.get("Industry", ""),
    }

    return [company_record], [securities_record]


@ray.remote(num_cpus=0.25)  # Small CPU cost limits concurrent workers to ~4x cluster CPUs
def ingest_ticker_data(
    ticker: str,
    key_manager,
    progress_tracker,
    endpoints: List[str],
    storage_path: str,
    dry_run: bool = False
) -> dict:
    """
    Ingest all data for a single ticker and write directly to Delta tables.

    v3.0: Workers write directly to Bronze Delta tables (no staging files).
    Uses ACID transactions for concurrent writes from multiple workers.
    """
    import socket
    import logging
    import requests
    import importlib
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
        "rows_written": 0,
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
                        "rows": 0,
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
                            "rows": 0,
                        }
                        result["errors"].append(f"{endpoint}: {error_msg}")
                    else:
                        # =====================================================
                        # v3.1: Write directly to Delta using delta-rs (NO JVM)
                        # =====================================================
                        rows_written = 0
                        bronze_path = Path(storage_path) / "bronze"

                        try:
                            # company_overview is special - produces 2 tables
                            if endpoint == "company_overview":
                                company_records, securities_records = transform_company_overview(ticker, data)

                                if company_records:
                                    table_path = str(bronze_path / "company_reference")
                                    rows_written += write_to_delta_rs(table_path, company_records, {})

                                if securities_records:
                                    table_path = str(bronze_path / "securities_reference")
                                    rows_written += write_to_delta_rs(table_path, securities_records, {})

                            elif endpoint in ["time_series_daily", "time_series_daily_adjusted"]:
                                records = transform_time_series(ticker, data)
                                if records:
                                    table_path = str(bronze_path / "securities_prices_daily")
                                    rows_written = write_to_delta_rs(table_path, records, {})

                            elif endpoint == "income_statement":
                                records = transform_financial_statement(ticker, data, "income")
                                if records:
                                    table_path = str(bronze_path / "income_statements")
                                    rows_written = write_to_delta_rs(table_path, records, {})

                            elif endpoint == "balance_sheet":
                                records = transform_financial_statement(ticker, data, "balance")
                                if records:
                                    table_path = str(bronze_path / "balance_sheets")
                                    rows_written = write_to_delta_rs(table_path, records, {})

                            elif endpoint == "cash_flow":
                                records = transform_financial_statement(ticker, data, "cashflow")
                                if records:
                                    table_path = str(bronze_path / "cash_flows")
                                    rows_written = write_to_delta_rs(table_path, records, {})

                            elif endpoint == "earnings":
                                records = transform_financial_statement(ticker, data, "earnings")
                                if records:
                                    table_path = str(bronze_path / "earnings")
                                    rows_written = write_to_delta_rs(table_path, records, {})

                            else:
                                logger.warning(f"Unknown endpoint {endpoint} - skipping Delta write")

                        except Exception as write_err:
                            logger.error(f"Delta write error for {ticker}/{endpoint}: {write_err}")
                            raise

                        result["endpoints"][endpoint] = {
                            "success": True,
                            "rows": rows_written,
                        }
                        result["rows_written"] += rows_written

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
                    result["endpoints"][endpoint] = {"success": False, "error": "Timeout after retries", "rows": 0}
                    result["errors"].append(f"{endpoint}: Timeout")

            except Exception as e:
                result["endpoints"][endpoint] = {"success": False, "error": str(e), "rows": 0}
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
    max_tickers: Optional[int] = None,
    dry_run: bool = False
) -> List[str]:
    """
    Get list of tickers based on configured sources.

    Uses v2.0 Delta/Parquet tables with fallback to test_tickers for dry-run.

    Args:
        storage_path: Path to storage directory
        ticker_source_config: Ticker source configuration
        max_tickers: Optional limit
        dry_run: If true, allows test_tickers fallback

    Returns:
        List of ticker symbols
    """
    priority = ticker_source_config.get(
        "priority",
        ["securities_reference", "company_reference", "test_tickers"]
    )

    for source in priority:
        tickers = []

        if source == "securities_reference":
            ref_path = Path(storage_path) / ticker_source_config.get(
                "securities_reference_path", "bronze/securities_reference"
            )
            tickers = _read_tickers_from_delta_table(ref_path, "ticker")
            if tickers:
                logger.info(f"Found {len(tickers)} tickers in securities_reference")

        elif source == "company_reference":
            ref_path = Path(storage_path) / ticker_source_config.get(
                "company_reference_path", "bronze/company_reference"
            )
            tickers = _read_tickers_from_delta_table(ref_path, "ticker")
            if tickers:
                logger.info(f"Found {len(tickers)} tickers in company_reference")

        elif source == "test_tickers":
            # Fallback: Use configured test tickers for initial bootstrap
            # This is used when Bronze layer is empty (first run)
            tickers = ticker_source_config.get("test_tickers", [])
            if tickers:
                if dry_run:
                    logger.info(f"Using test_tickers (dry-run mode): {len(tickers)} tickers")
                else:
                    logger.warning(
                        f"Bronze layer empty - using test_tickers for bootstrap: {len(tickers)} tickers. "
                        "Subsequent runs will use Bronze data."
                    )

        if tickers:
            tickers = sorted(set(tickers))
            if max_tickers:
                return tickers[:max_tickers]
            return tickers

    # No tickers found from any source
    return []


def _read_tickers_from_delta_table(table_path: Path, ticker_column: str = "ticker") -> List[str]:
    """
    Read unique ticker values from a Delta/Parquet table.

    Args:
        table_path: Path to Delta or Parquet table
        ticker_column: Column name containing ticker symbols

    Returns:
        List of unique ticker symbols
    """
    if not table_path.exists():
        return []

    try:
        import pyarrow.parquet as pq
        import pyarrow.dataset as ds

        # Check if it's a Delta table (has _delta_log)
        delta_log = table_path / "_delta_log"
        if delta_log.exists():
            # Delta table - read using dataset API
            # Delta tables store data in Parquet files, we can read them directly
            parquet_files = list(table_path.glob("**/*.parquet"))
            if not parquet_files:
                return []

            # Read just the ticker column for efficiency
            dataset = ds.dataset(table_path, format="parquet")
            table = dataset.to_table(columns=[ticker_column])
            tickers = table.column(ticker_column).to_pylist()
            return [t for t in set(tickers) if t]  # Unique, non-null

        else:
            # Plain Parquet directory
            parquet_files = list(table_path.glob("**/*.parquet"))
            if not parquet_files:
                return []

            dataset = ds.dataset(table_path, format="parquet")
            table = dataset.to_table(columns=[ticker_column])
            tickers = table.column(ticker_column).to_pylist()
            return [t for t in set(tickers) if t]

    except Exception as e:
        logger.warning(f"Failed to read tickers from {table_path}: {e}")
        return []


# =============================================================================
# Bronze Data Verification (Failsafe)
# =============================================================================

def verify_bronze_data_exists(storage_path: str, logger) -> bool:
    """
    Verify that Bronze data exists before attempting Silver build.

    This is a critical failsafe - we should NOT attempt to build Silver layer
    if there's no Bronze data to build from. This prevents confusing errors
    and aligns behavior with the original run_full_pipeline.py.

    Args:
        storage_path: Base storage path
        logger: Logger instance

    Returns:
        True if Bronze data exists and is valid, False otherwise
    """
    from pathlib import Path

    bronze_path = Path(storage_path) / "bronze"

    if not bronze_path.exists():
        logger.warning(f"Bronze directory does not exist: {bronze_path}")
        return False

    # Check for key v2.0 tables that Silver models depend on
    required_tables = [
        "securities_reference",
        "company_reference",
        "securities_prices_daily",
    ]

    found_tables = []
    for table in required_tables:
        table_path = bronze_path / table
        if table_path.exists():
            # Check if it's a valid Delta table or has parquet files
            delta_log = table_path / "_delta_log"
            parquet_files = list(table_path.glob("**/*.parquet"))

            if delta_log.exists() or parquet_files:
                found_tables.append(table)
                logger.debug(f"  ✓ Found: {table}")
            else:
                logger.debug(f"  ⚠ Empty: {table}")
        else:
            logger.debug(f"  ✗ Missing: {table}")

    if not found_tables:
        logger.warning(
            f"No valid Bronze tables found in {bronze_path}.\n"
            "Cannot build Silver layer without Bronze data.\n"
            "Run ingestion first: python -m scripts.run_full_pipeline --max-tickers 100"
        )
        return False

    logger.info(f"Bronze data verified: {len(found_tables)}/{len(required_tables)} tables found")
    return True


# =============================================================================
# Main Pipeline
# =============================================================================

# NOTE: consolidate_staging_to_bronze() removed in v3.0
# Workers now write directly to Delta tables using ACID transactions.
# No staging files or consolidation phase needed.


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
    parser.add_argument("--local-silver", action="store_true",
                       help="Run Silver build on head node only (default is distributed on Ray workers)")
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

    # Get storage path from config (single source of truth: run_config.json)
    storage_path = effective.get("storage_path")
    if not storage_path:
        raise ValueError(
            "storage_path not configured.\n"
            "Set 'storage_path' in configs/pipelines/run_config.json\n"
            "Example: \"storage_path\": \"/shared/storage\""
        )

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
    # Default includes all endpoints needed for company model (financial statements)
    default_endpoints = [
        "time_series_daily",
        "company_overview",
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "earnings"
    ]
    endpoints = provider_config.get("endpoints", default_endpoints)
    logger.info(f"  Endpoints: {', '.join(endpoints)}")

    # Get tickers
    ticker_source = effective.get("ticker_source", {})
    tickers = get_ticker_list(storage_path, ticker_source, max_tickers, dry_run=dry_run)

    if not tickers:
        logger.error(
            "No tickers found. Either:\n"
            "  1. Run ingestion first: python -m scripts.ingest.run_full_pipeline --max-tickers 100\n"
            "  2. Use --dry-run to use test_tickers from config"
        )
        return 1

    logger.info(f"  Tickers: {len(tickers)}")

    # Create distributed key manager with retry config
    # IMPORTANT: Load configs on HEAD NODE, then pass to workers
    retry_config = effective.get("retry", {})
    enabled_providers = [
        name for name, cfg in effective.get("providers", {}).items()
        if isinstance(cfg, dict) and cfg.get("enabled", False)
    ]
    if not enabled_providers:
        enabled_providers = ["alpha_vantage"]  # Default

    # Load provider configs on head node (workers can't access config files)
    provider_configs = {}
    for provider in enabled_providers:
        try:
            config = load_pipeline_config(provider)
            keys = load_api_keys(provider)
            provider_configs[provider] = {"config": config, "keys": keys}
            logger.info(f"  Loaded {provider} config: {config.get('rate_limit_per_sec', 1.0)} req/sec")
        except Exception as e:
            logger.error(f"  Failed to load {provider} config: {e}")

    logger.info("Initializing distributed key manager...")
    key_manager = DistributedKeyManager.remote(provider_configs, retry_config)

    results = {}

    # Ensure calendar seed exists (needed by temporal model)
    ensure_calendar_seed(storage_path)

    # Run bronze ingestion
    skip_bronze = effective.get("skip_bronze", False)
    if not skip_bronze:
        logger.info("\n" + "-" * 50)
        logger.info("PHASE 1: Bronze Layer Ingestion")
        logger.info("-" * 50)

        progress = ProgressTracker.remote(len(tickers), "Bronze Ingestion")

        # Batch task submission to avoid overwhelming Ray scheduler
        # With num_cpus=0.25 and ~44 CPUs, max ~176 concurrent tasks
        # Smaller batches prevent memory spikes from too many Python workers
        batch_size = run_config.get("cluster", {}).get("task_batch_size", 15)

        # Memory optimization: Only keep counters, not full result dicts
        # With 12,499 tickers, accumulating full results causes memory issues
        successful = 0
        total_rows = 0
        by_host = {}

        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            futures = [
                ingest_ticker_data.remote(
                    ticker, key_manager, progress, endpoints, storage_path, dry_run
                )
                for ticker in batch
            ]
            # Wait for batch to complete before submitting next
            batch_results = ray.get(futures)

            # Extract only what we need, then discard full results
            for r in batch_results:
                if r["success"]:
                    successful += 1
                total_rows += r.get("rows_written", 0)
                host = r.get("hostname", "unknown")
                by_host[host] = by_host.get(host, 0) + 1

            # Clear batch results immediately
            del batch_results

        # Get final status
        status = ray.get(progress.get_status.remote())

        logger.info(f"\nBronze Ingestion Complete (v3.0 - Direct Delta Write):")
        logger.info(f"  Successful: {successful}/{len(tickers)}")
        logger.info(f"  Rows Written: {total_rows:,}")
        logger.info(f"  Time: {status['elapsed']:.1f}s")
        logger.info(f"  Rate: {status['rate']:.2f} tickers/sec")
        logger.info(f"  Distribution: {by_host}")

        results["bronze"] = {
            "total": len(tickers),
            "successful": successful,
            "elapsed": status["elapsed"],
            "distribution": by_host,
            "rows_written": total_rows,
        }

        # v3.0: No consolidation phase needed - workers write directly to Delta
        # Data is already in Bronze tables via ACID transactions

    # Run silver build
    skip_silver = effective.get("skip_silver", False)
    silver_config = effective.get("silver_models", {})
    skip_on_dry_run = silver_config.get("skip_on_dry_run", True)
    local_silver = effective.get("local_silver", False)  # Default is distributed

    # Determine if we should build silver
    # Key failsafe: Don't build if dry_run (no data) or if Bronze data doesn't exist
    should_build_silver = (
        not skip_silver and
        silver_config.get("enabled", True) and
        not (dry_run and skip_on_dry_run)
    )

    # Critical failsafe: Verify Bronze data exists before attempting Silver build
    # This aligns with original run_full_pipeline.py behavior
    if should_build_silver:
        if not verify_bronze_data_exists(storage_path, logger):
            logger.warning("Skipping Silver build - no valid Bronze data found")
            should_build_silver = False

    if should_build_silver:
        models_to_build = silver_config.get("models", ["company", "stocks"])

        if not local_silver:
            # Default: Run Silver build distributed on Ray workers
            logger.info("\n" + "-" * 50)
            logger.info("PHASE 2: Silver Layer Build (Distributed Ray + Spark)")
            logger.info("-" * 50)

            from orchestration.distributed.tasks import build_model_task

            logger.info(f"Building models: {', '.join(models_to_build)}")
            logger.info(f"Using storage root: {storage_path}")
            logger.info("Mode: Distributed (Ray workers)")

            build_results = {}
            for model_name in models_to_build:
                try:
                    logger.info(f"Submitting build task for: {model_name}")

                    future = build_model_task.remote(
                        model_name=model_name,
                        storage_path=storage_path,
                        repo_root=str(project_root),
                        verbose=True
                    )

                    result = ray.get(future, timeout=600)
                    build_results[model_name] = result

                    if result.get('status') == 'success':
                        dims = result.get('dimensions', 0)
                        facts = result.get('facts', 0)
                        duration = result.get('duration_seconds', 0)
                        logger.info(f"  ✓ {model_name}: {dims} dims, {facts} facts ({duration:.1f}s)")
                    else:
                        error = result.get('error', 'Unknown error')
                        logger.error(f"  ✗ {model_name}: {error}")
                        if result.get('traceback'):
                            tb_lines = result['traceback'].strip().split('\n')[-10:]
                            for line in tb_lines:
                                logger.error(f"    {line}")

                except ray.exceptions.GetTimeoutError:
                    logger.error(f"  ✗ {model_name}: Build timed out (10 min)")
                    build_results[model_name] = {'status': 'timeout'}
                except Exception as e:
                    logger.error(f"  ✗ {model_name}: {e}")
                    build_results[model_name] = {'status': 'error', 'error': str(e)}

            successful = sum(1 for r in build_results.values() if r.get('status') == 'success')
            logger.info(f"Silver build complete: {successful}/{len(models_to_build)} models built")

        else:
            # Run Silver build on head node via subprocess (default)
            logger.info("\n" + "-" * 50)
            logger.info("PHASE 2: Silver Layer Build (Spark)")
            logger.info("-" * 50)

            import subprocess

            try:
                logger.info(f"Building models: {', '.join(models_to_build)}")
                logger.info(f"Using storage root: {storage_path}")

                cmd = [
                    sys.executable, "-m", "scripts.build.build_models",
                    "--models", *models_to_build,
                    "--storage-root", storage_path,
                    "--verbose"
                ]

                result = subprocess.run(
                    cmd,
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    timeout=600
                )

                if result.returncode == 0:
                    logger.info("Silver layer build complete")
                    if result.stdout:
                        for line in result.stdout.split('\n'):
                            if any(x in line for x in ['✓', 'Built', 'Success', 'Complete', 'dim_', 'fact_']):
                                logger.info(f"  {line.strip()}")
                else:
                    logger.error("Silver layer build failed:")
                    noise_patterns = [
                        "WARNING: Using incubator", ":: loading settings ::",
                        ":: resolving dependencies", ":: resolution report",
                        "confs: [default]", "downloading https://",
                        "artifacts:", "evicted:", ":: retrieving",
                        "WARN NativeCodeLoader", "log4j",
                    ]

                    if result.stderr:
                        stderr_lines = [
                            line.strip() for line in result.stderr.split('\n')
                            if line.strip() and not any(p in line for p in noise_patterns)
                        ]
                        for line in stderr_lines[-30:]:
                            logger.error(f"  {line}")

                    if result.stdout:
                        stdout_lines = [
                            line.strip() for line in result.stdout.split('\n')
                            if line.strip() and not any(p in line for p in noise_patterns)
                        ]
                        error_lines = [
                            line for line in stdout_lines
                            if any(x in line.lower() for x in ['error', 'exception', 'traceback', 'failed', '✗'])
                        ]
                        if error_lines:
                            logger.error("  stdout errors:")
                            for line in error_lines[-20:]:
                                logger.error(f"    {line}")

            except subprocess.TimeoutExpired:
                logger.error("Silver layer build timed out (10 min)")
            except Exception as e:
                logger.error(f"Silver layer build failed: {e}")

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
