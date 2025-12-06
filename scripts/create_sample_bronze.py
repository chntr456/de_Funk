"""
Create sample Bronze layer data for testing.

This script creates sample securities_reference and securities_prices_daily
tables using pandas/pyarrow when PySpark is not available.

Usage:
    python -m scripts.create_sample_bronze --tickers 20
"""
from __future__ import annotations

import sys
from pathlib import Path
import argparse
from datetime import datetime, timedelta
import random

# Setup repo imports
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


# Sample stock data
SAMPLE_STOCKS = [
    {"ticker": "AAPL", "name": "Apple Inc.", "cik": "0000320193", "sector": "Technology", "industry": "Consumer Electronics", "market_cap": 3000000000000},
    {"ticker": "MSFT", "name": "Microsoft Corporation", "cik": "0000789019", "sector": "Technology", "industry": "Software", "market_cap": 2800000000000},
    {"ticker": "GOOGL", "name": "Alphabet Inc.", "cik": "0001652044", "sector": "Technology", "industry": "Internet Services", "market_cap": 1800000000000},
    {"ticker": "AMZN", "name": "Amazon.com Inc.", "cik": "0001018724", "sector": "Consumer Cyclical", "industry": "Internet Retail", "market_cap": 1600000000000},
    {"ticker": "NVDA", "name": "NVIDIA Corporation", "cik": "0001045810", "sector": "Technology", "industry": "Semiconductors", "market_cap": 1400000000000},
    {"ticker": "META", "name": "Meta Platforms Inc.", "cik": "0001326801", "sector": "Technology", "industry": "Internet Services", "market_cap": 1200000000000},
    {"ticker": "TSLA", "name": "Tesla Inc.", "cik": "0001318605", "sector": "Consumer Cyclical", "industry": "Auto Manufacturers", "market_cap": 800000000000},
    {"ticker": "BRK.B", "name": "Berkshire Hathaway Inc.", "cik": "0001067983", "sector": "Financial Services", "industry": "Insurance", "market_cap": 780000000000},
    {"ticker": "UNH", "name": "UnitedHealth Group Inc.", "cik": "0000731766", "sector": "Healthcare", "industry": "Healthcare Plans", "market_cap": 500000000000},
    {"ticker": "JNJ", "name": "Johnson & Johnson", "cik": "0000200406", "sector": "Healthcare", "industry": "Drug Manufacturers", "market_cap": 450000000000},
    {"ticker": "JPM", "name": "JPMorgan Chase & Co.", "cik": "0000019617", "sector": "Financial Services", "industry": "Banks", "market_cap": 400000000000},
    {"ticker": "V", "name": "Visa Inc.", "cik": "0001403161", "sector": "Financial Services", "industry": "Credit Services", "market_cap": 380000000000},
    {"ticker": "PG", "name": "Procter & Gamble Co.", "cik": "0000080424", "sector": "Consumer Defensive", "industry": "Household Products", "market_cap": 350000000000},
    {"ticker": "MA", "name": "Mastercard Inc.", "cik": "0001141391", "sector": "Financial Services", "industry": "Credit Services", "market_cap": 340000000000},
    {"ticker": "HD", "name": "Home Depot Inc.", "cik": "0000354950", "sector": "Consumer Cyclical", "industry": "Home Improvement", "market_cap": 320000000000},
    {"ticker": "CVX", "name": "Chevron Corporation", "cik": "0000093410", "sector": "Energy", "industry": "Oil & Gas Integrated", "market_cap": 280000000000},
    {"ticker": "MRK", "name": "Merck & Co. Inc.", "cik": "0000310158", "sector": "Healthcare", "industry": "Drug Manufacturers", "market_cap": 260000000000},
    {"ticker": "ABBV", "name": "AbbVie Inc.", "cik": "0001551152", "sector": "Healthcare", "industry": "Drug Manufacturers", "market_cap": 250000000000},
    {"ticker": "PEP", "name": "PepsiCo Inc.", "cik": "0000077476", "sector": "Consumer Defensive", "industry": "Beverages", "market_cap": 240000000000},
    {"ticker": "KO", "name": "Coca-Cola Co.", "cik": "0000021344", "sector": "Consumer Defensive", "industry": "Beverages", "market_cap": 230000000000},
]


def create_securities_reference(output_path: Path, stocks: list):
    """Create securities_reference Bronze table."""

    records = []
    for stock in stocks:
        records.append({
            "ticker": stock["ticker"],
            "security_name": stock["name"],
            "asset_type": "stocks",
            "type": "Common Stock",  # Raw Alpha Vantage value
            "cik": stock["cik"],
            "composite_figi": None,
            "exchange_code": "NYSE" if random.random() > 0.5 else "NASDAQ",
            "currency": "USD",
            "market": "stocks",
            "locale": "US",
            "primary_exchange": "NYSE" if random.random() > 0.5 else "NASDAQ",
            "shares_outstanding": random.randint(1000000000, 10000000000),
            "market_cap": float(stock["market_cap"]),
            "sic_code": None,
            "sic_description": stock["sector"],
            "ticker_root": stock["ticker"],
            "base_currency_symbol": "USD",
            "currency_symbol": "USD",
            "delisted_utc": None,
            "last_updated_utc": datetime.now(),
            "is_active": True,
            "sector": stock["sector"],
            "industry": stock["industry"],
            "description": f"{stock['name']} is a company in the {stock['industry']} industry.",
            "pe_ratio": random.uniform(10, 50),
            "peg_ratio": random.uniform(0.5, 3.0),
            "book_value": random.uniform(10, 100),
            "dividend_per_share": random.uniform(0, 5),
            "dividend_yield": random.uniform(0, 0.05),
            "eps": random.uniform(1, 20),
            "week_52_high": random.uniform(100, 500),
            "week_52_low": random.uniform(50, 400),
        })

    df = pd.DataFrame(records)

    # Write to partitioned path (partition by asset_type only)
    partition_path = output_path / "asset_type=stocks"
    partition_path.mkdir(parents=True, exist_ok=True)

    table = pa.Table.from_pandas(df)
    pq.write_table(table, partition_path / "data.parquet")

    print(f"  Created securities_reference: {len(records)} records")
    return df


def create_securities_prices_daily(output_path: Path, tickers: list, date_from: str, date_to: str):
    """Create securities_prices_daily Bronze table."""

    date_from_dt = datetime.strptime(date_from, "%Y-%m-%d")
    date_to_dt = datetime.strptime(date_to, "%Y-%m-%d")

    records = []
    current_date = date_from_dt

    # Generate price data for each ticker and date
    prices = {ticker: random.uniform(50, 500) for ticker in tickers}

    while current_date <= date_to_dt:
        # Skip weekends
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue

        for ticker in tickers:
            # Random walk for price
            change = random.uniform(-0.03, 0.03)
            prices[ticker] = prices[ticker] * (1 + change)
            price = prices[ticker]

            high = price * (1 + random.uniform(0, 0.02))
            low = price * (1 - random.uniform(0, 0.02))
            open_price = random.uniform(low, high)
            close_price = random.uniform(low, high)

            records.append({
                "trade_date": current_date.date(),
                "ticker": ticker,
                "asset_type": "stocks",
                "year": current_date.year,
                "month": current_date.month,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close_price,
                "volume": float(random.randint(1000000, 100000000)),
                "volume_weighted": (high + low + close_price) / 3,
                "transactions": random.randint(10000, 1000000),
                "otc": False,
                "adjusted_close": close_price,
                "dividend_amount": 0.0,
                "split_coefficient": 1.0,
            })

        current_date += timedelta(days=1)

    df = pd.DataFrame(records)

    # Group by year/month and write partitioned data
    for (year, month), group_df in df.groupby(['year', 'month']):
        partition_path = output_path / "asset_type=stocks" / f"year={year}" / f"month={month}"
        partition_path.mkdir(parents=True, exist_ok=True)

        # Drop partition columns from data (they're in the path)
        write_df = group_df.drop(columns=['year', 'month', 'asset_type'])
        table = pa.Table.from_pandas(write_df, preserve_index=False)
        pq.write_table(table, partition_path / "data.parquet")

    print(f"  Created securities_prices_daily: {len(records)} records")
    return df


def main():
    parser = argparse.ArgumentParser(description="Create sample Bronze data for testing")
    parser.add_argument('--tickers', type=int, default=20, help='Number of tickers to create')
    parser.add_argument('--days', type=int, default=30, help='Number of days of price data')
    args = parser.parse_args()

    print("=" * 60)
    print("Creating Sample Bronze Data")
    print("=" * 60)

    bronze_root = Path(repo_root) / "storage" / "bronze"

    # Select stocks
    stocks = SAMPLE_STOCKS[:args.tickers]
    tickers = [s["ticker"] for s in stocks]

    print(f"\nConfiguration:")
    print(f"  Tickers: {len(tickers)}")
    print(f"  Days: {args.days}")
    print()

    # Date range
    date_to = datetime.now().date()
    date_from = date_to - timedelta(days=args.days)

    print("Creating securities_reference...")
    ref_path = bronze_root / "securities_reference"
    ref_df = create_securities_reference(ref_path, stocks)

    print("\nCreating securities_prices_daily...")
    prices_path = bronze_root / "securities_prices_daily"
    prices_df = create_securities_prices_daily(prices_path, tickers, date_from.isoformat(), date_to.isoformat())

    print()
    print("=" * 60)
    print("Bronze Data Created Successfully!")
    print("=" * 60)
    print(f"\nNext steps:")
    print(f"  1. Verify: ls -la {bronze_root}/securities_reference/")
    print(f"  2. Build Silver: python -m scripts.build_silver_layer")
    print()


if __name__ == "__main__":
    main()
