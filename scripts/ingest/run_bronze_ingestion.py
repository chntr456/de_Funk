#!/usr/bin/env python3
"""
Simple Bronze Ingestion Script.

Fetches data from Alpha Vantage APIs and writes to Bronze layer.
Designed to run standalone (no Ray/Spark needed) since API rate limits
are the bottleneck, not compute.

Usage:
    python -m scripts.ingest.run_bronze_ingestion
    python -m scripts.ingest.run_bronze_ingestion --max-tickers 100
    python -m scripts.ingest.run_bronze_ingestion --endpoints prices,overview

Endpoints:
    prices     - Daily OHLCV (TIME_SERIES_DAILY)
    overview   - Company overview (OVERVIEW)
    income     - Income statements (INCOME_STATEMENT)
    balance    - Balance sheets (BALANCE_SHEET)
    cashflow   - Cash flow statements (CASH_FLOW)
    earnings   - Earnings reports (EARNINGS)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger
from config import ConfigLoader

logger = get_logger(__name__)

# Rate limiting
CALLS_PER_MINUTE = 5  # Free tier: 5, Premium: 75
CALL_DELAY = 60.0 / CALLS_PER_MINUTE + 0.5  # Add buffer


def get_tickers_from_bronze(storage_path: Path, max_tickers: Optional[int] = None) -> List[str]:
    """Get list of tickers from seeded Bronze reference data."""
    from deltalake import DeltaTable

    ref_path = storage_path / "bronze" / "securities_reference"

    if not ref_path.exists():
        raise ValueError(
            f"No securities_reference table at {ref_path}. "
            "Run: python -m scripts.seed.seed_tickers first"
        )

    dt = DeltaTable(str(ref_path))
    df = dt.to_pandas()

    # Filter to stocks only
    tickers = df[df['asset_type'] == 'Stock']['ticker'].unique().tolist()

    if max_tickers:
        tickers = tickers[:max_tickers]

    logger.info(f"Found {len(tickers)} tickers to process")
    return tickers


def fetch_with_rate_limit(api_func, *args, **kwargs) -> Optional[Dict]:
    """Call API function with rate limiting and error handling."""
    try:
        result = api_func(*args, **kwargs)
        time.sleep(CALL_DELAY)
        return result
    except Exception as e:
        logger.warning(f"API call failed: {e}")
        time.sleep(CALL_DELAY)
        return None


def ingest_prices(
    tickers: List[str],
    storage_path: Path,
    api_key: str
) -> int:
    """Ingest daily prices for tickers."""
    from datapipelines.providers.alpha_vantage.client import AlphaVantageClient
    from deltalake import write_deltalake
    import pandas as pd

    client = AlphaVantageClient(api_key=api_key)
    bronze_path = storage_path / "bronze" / "securities_prices_daily"

    records = []
    success_count = 0

    for i, ticker in enumerate(tickers):
        logger.info(f"[{i+1}/{len(tickers)}] Fetching prices for {ticker}")

        try:
            data = client.get_daily_prices(ticker)
            if data:
                for date_str, values in data.items():
                    records.append({
                        'ticker': ticker,
                        'trade_date': date_str,
                        'open': float(values.get('1. open', 0)),
                        'high': float(values.get('2. high', 0)),
                        'low': float(values.get('3. low', 0)),
                        'close': float(values.get('4. close', 0)),
                        'volume': int(values.get('5. volume', 0)),
                        'asset_type': 'stocks',
                        'snapshot_dt': datetime.now().strftime('%Y-%m-%d'),
                    })
                success_count += 1

            time.sleep(CALL_DELAY)

            # Write in batches
            if len(records) >= 10000:
                df = pd.DataFrame(records)
                write_deltalake(
                    str(bronze_path),
                    df,
                    mode='append',
                    schema_mode='merge'
                )
                records = []
                logger.info(f"  Wrote batch to Bronze")

        except Exception as e:
            logger.warning(f"  Failed: {e}")
            time.sleep(CALL_DELAY)

    # Write remaining records
    if records:
        df = pd.DataFrame(records)
        write_deltalake(
            str(bronze_path),
            df,
            mode='append',
            schema_mode='merge'
        )

    return success_count


def ingest_company_data(
    tickers: List[str],
    storage_path: Path,
    api_key: str,
    endpoint: str
) -> int:
    """Ingest company data (overview, income, balance, cashflow, earnings)."""
    from datapipelines.providers.alpha_vantage.client import AlphaVantageClient
    from deltalake import write_deltalake
    import pandas as pd

    client = AlphaVantageClient(api_key=api_key)

    # Map endpoint to table and client method
    endpoint_config = {
        'overview': ('company_overview', 'get_company_overview'),
        'income': ('income_statements', 'get_income_statement'),
        'balance': ('balance_sheets', 'get_balance_sheet'),
        'cashflow': ('cash_flows', 'get_cash_flow'),
        'earnings': ('earnings', 'get_earnings'),
    }

    table_name, method_name = endpoint_config[endpoint]
    bronze_path = storage_path / "bronze" / table_name

    records = []
    success_count = 0

    for i, ticker in enumerate(tickers):
        logger.info(f"[{i+1}/{len(tickers)}] Fetching {endpoint} for {ticker}")

        try:
            method = getattr(client, method_name)
            data = method(ticker)

            if data:
                if isinstance(data, list):
                    for item in data:
                        item['ticker'] = ticker
                        item['snapshot_dt'] = datetime.now().strftime('%Y-%m-%d')
                        records.append(item)
                else:
                    data['ticker'] = ticker
                    data['snapshot_dt'] = datetime.now().strftime('%Y-%m-%d')
                    records.append(data)
                success_count += 1

            time.sleep(CALL_DELAY)

            # Write in batches
            if len(records) >= 100:
                df = pd.DataFrame(records)
                write_deltalake(
                    str(bronze_path),
                    df,
                    mode='append',
                    schema_mode='merge'
                )
                records = []
                logger.info(f"  Wrote batch to Bronze")

        except Exception as e:
            logger.warning(f"  Failed: {e}")
            time.sleep(CALL_DELAY)

    # Write remaining
    if records:
        df = pd.DataFrame(records)
        write_deltalake(
            str(bronze_path),
            df,
            mode='append',
            schema_mode='merge'
        )

    return success_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage-path', type=str, default='/shared/storage',
                        help='Storage path')
    parser.add_argument('--max-tickers', type=int, help='Max tickers to process')
    parser.add_argument('--endpoints', type=str, default='prices,overview',
                        help='Comma-separated endpoints: prices,overview,income,balance,cashflow,earnings')

    args = parser.parse_args()
    setup_logging()

    storage_path = Path(args.storage_path)
    endpoints = [e.strip() for e in args.endpoints.split(',')]

    # Load API key
    import os
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('ALPHA_VANTAGE_API_KEY') or os.getenv('ALPHA_VANTAGE_API_KEYS', '').split(',')[0]
    if not api_key:
        logger.error("No ALPHA_VANTAGE_API_KEY in environment")
        return 1

    # Get tickers
    tickers = get_tickers_from_bronze(storage_path, args.max_tickers)

    logger.info(f"Starting ingestion for {len(tickers)} tickers")
    logger.info(f"Endpoints: {endpoints}")
    logger.info(f"Rate limit: {CALLS_PER_MINUTE} calls/min")

    # Estimate time
    total_calls = len(tickers) * len(endpoints)
    est_minutes = (total_calls * CALL_DELAY) / 60
    logger.info(f"Estimated time: {est_minutes:.0f} minutes")

    results = {}

    for endpoint in endpoints:
        logger.info(f"\n{'='*60}")
        logger.info(f"Ingesting: {endpoint}")
        logger.info(f"{'='*60}\n")

        if endpoint == 'prices':
            count = ingest_prices(tickers, storage_path, api_key)
        else:
            count = ingest_company_data(tickers, storage_path, api_key, endpoint)

        results[endpoint] = count
        logger.info(f"\n{endpoint}: {count}/{len(tickers)} successful\n")

    # Summary
    logger.info("\n" + "="*60)
    logger.info("Ingestion Complete")
    logger.info("="*60)
    for endpoint, count in results.items():
        logger.info(f"  {endpoint}: {count}/{len(tickers)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
