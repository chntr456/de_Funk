#!/usr/bin/env python3
"""
Check which tickers have forecast data.
"""

import duckdb
from pathlib import Path

def check_available_tickers():
    """Check which tickers have forecasts."""

    print("=" * 70)
    print("AVAILABLE FORECAST TICKERS")
    print("=" * 70)

    forecast_path = "storage/silver/forecast/facts/forecast_price"

    try:
        con = duckdb.connect(database=':memory:')
        query = f"""
        SELECT
            ticker,
            COUNT(DISTINCT model_name) as num_models,
            COUNT(*) as num_forecasts,
            MIN(prediction_date) as earliest_prediction,
            MAX(prediction_date) as latest_prediction,
            MAX(forecast_date) as last_forecast_date
        FROM read_parquet('{forecast_path}/**/*.parquet')
        GROUP BY ticker
        ORDER BY ticker
        """

        df = con.execute(query).fetchdf()
        con.close()

        if df.empty:
            print("❌ No forecasts found")
        else:
            print(f"\nFound forecasts for {len(df)} tickers:\n")
            print(df.to_string(index=False))

            print("\n" + "=" * 70)
            print(f"Total tickers: {len(df)}")
            print(f"Total forecast records: {df['num_forecasts'].sum()}")

    except Exception as e:
        print(f"❌ Error: {e}")

    print("=" * 70)

if __name__ == "__main__":
    check_available_tickers()
