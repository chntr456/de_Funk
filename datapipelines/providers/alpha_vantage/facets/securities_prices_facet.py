"""
SecuritiesPricesFacetAV - Alpha Vantage daily prices facet.

Maps Alpha Vantage TIME_SERIES_DAILY_ADJUSTED endpoint to unified
securities_prices_daily schema.

Key Differences from Polygon:
- Response is nested dict (date -> OHLCV fields)
- Field names prefixed with numbers (1. open, 2. high, etc.)
- Includes split/dividend columns
- Full history in single call (vs paginated)
- No VWAP field (need to calculate or approximate)

Bronze table: bronze/securities_prices_daily/
Partitions: trade_date, asset_type
"""

from __future__ import annotations
from typing import Iterable, List
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.functions import col, lit, when, coalesce, to_date
from datapipelines.providers.alpha_vantage.facets.alpha_vantage_base_facet import AlphaVantageFacet


class SecuritiesPricesFacetAV(AlphaVantageFacet):
    """
    Unified daily OHLCV prices from Alpha Vantage TIME_SERIES_DAILY_ADJUSTED.

    Maps to same schema as Polygon's SecuritiesPricesFacet for compatibility.

    Alpha Vantage Response Format:
    {
      "Time Series (Daily)": {
        "2024-01-15": {
          "1. open": "185.00",
          "2. high": "187.50",
          "3. low": "184.25",
          "4. close": "186.75",
          "5. adjusted close": "186.75",
          "6. volume": "52341200",
          "7. dividend amount": "0.0000",
          "8. split coefficient": "1.0"
        },
        ...
      }
    }

    Usage:
        facet = SecuritiesPricesFacetAV(
            spark,
            tickers=['AAPL', 'MSFT'],
            date_from='2024-01-01',
            date_to='2024-12-31',
            adjusted=True
        )
    """

    name = "securities_prices_daily"

    # Numeric coercion for Alpha Vantage response
    NUMERIC_COERCE = {
        "1. open": "double",
        "2. high": "double",
        "3. low": "double",
        "4. close": "double",
        "5. adjusted close": "double",
        "6. volume": "double",
        "7. dividend amount": "double",
        "8. split coefficient": "double"
    }

    # Final output schema (matches Polygon schema for compatibility)
    OUTPUT_SCHEMA = [
        ("trade_date", "date"),
        ("ticker", "string"),
        ("asset_type", "string"),
        ("open", "double"),
        ("high", "double"),
        ("low", "double"),
        ("close", "double"),
        ("volume", "double"),
        ("volume_weighted", "double"),  # Calculated as (H+L+C)/3
        ("transactions", "long"),  # Not available in Alpha Vantage, set to NULL
        ("otc", "boolean"),  # Not available, set to False
        # Alpha Vantage specific fields (optional)
        ("adjusted_close", "double"),
        ("dividend_amount", "double"),
        ("split_coefficient", "double")
    ]

    def __init__(self, spark: SparkSession, *,
                 tickers: List[str],
                 date_from: str = None,
                 date_to: str = None,
                 adjusted: bool = True,
                 outputsize: str = "full"):
        """
        Initialize Alpha Vantage prices facet.

        Args:
            spark: SparkSession
            tickers: List of ticker symbols
            date_from: Start date (YYYY-MM-DD) - used for filtering after fetch
            date_to: End date (YYYY-MM-DD) - used for filtering after fetch
            adjusted: Use adjusted prices (recommended)
            outputsize: 'compact' (100 days) or 'full' (20+ years)
        """
        super().__init__(spark,
                        tickers=tickers,
                        date_from=date_from,
                        date_to=date_to,
                        adjusted=adjusted,
                        outputsize=outputsize)
        self.adjusted = adjusted
        self.outputsize = outputsize
        self._call_contexts: List[dict] = []

    def calls(self) -> Iterable[dict]:
        """
        Generate API calls for daily price data.

        Alpha Vantage TIME_SERIES_DAILY_ADJUSTED returns full history
        in single call. Date filtering happens in postprocess().

        Rate limit: 5 calls/minute for free tier.
        """
        self._call_contexts = []

        endpoint = "time_series_daily_adjusted" if self.adjusted else "time_series_daily"

        for ticker in self.tickers:
            # Infer asset type from ticker (same heuristic as Polygon facet)
            asset_type = self._infer_asset_type(ticker)

            params = {
                "symbol": ticker,
                "outputsize": self.outputsize
            }

            self._call_contexts.append({
                "ticker": ticker,
                "asset_type": asset_type
            })

            yield {
                "ep_name": endpoint,
                "params": params
            }

    def _infer_asset_type(self, ticker: str) -> str:
        """
        Infer asset type from ticker pattern.

        Same heuristic as Polygon facet for consistency.
        """
        ticker = ticker.upper()

        # Options pattern
        if len(ticker) > 10 and ticker[-9] in ('C', 'P'):
            return "options"

        # Common ETF tickers
        etf_tickers = {'SPY', 'QQQ', 'IWM', 'DIA', 'GLD', 'SLV', 'TLT', 'EEM', 'VTI', 'VOO'}
        if ticker in etf_tickers:
            return "etfs"

        # Futures codes
        futures_codes = {'CL', 'GC', 'ES', 'NQ', 'ZB', 'ZN', 'ZT', 'HG', 'SI'}
        if ticker in futures_codes:
            return "futures"

        return "stocks"

    def normalize(self, raw_batches: List[List[dict]]):
        """
        Normalize Alpha Vantage time series response.

        Alpha Vantage returns nested structure:
        { "Time Series (Daily)": { "2024-01-15": {...}, ... } }

        Need to:
        1. Flatten nested date dict to rows
        2. Inject ticker and asset_type
        3. Parse date strings to date type

        This overrides base normalize() to handle the nested structure.
        """
        # Alpha Vantage returns nested dict, need to flatten
        flattened_batches: List[List[dict]] = []

        for i, batch in enumerate(raw_batches):
            ctx = None
            if i < len(self._call_contexts):
                ctx = self._call_contexts[i]

            if not ctx or not batch:
                flattened_batches.append([])
                continue

            ticker = ctx.get("ticker")
            asset_type = ctx.get("asset_type", "stocks")

            # Alpha Vantage wraps time series data
            # batch is a list with single dict: [{"Time Series (Daily)": {...}}]
            flattened_rows = []

            for response_dict in batch:
                # Check for error messages
                if "Error Message" in response_dict or "Note" in response_dict:
                    print(f"Warning: Alpha Vantage error for {ticker}: {response_dict}")
                    continue

                # Get the time series data
                time_series_key = None
                for key in response_dict.keys():
                    if "Time Series" in key:
                        time_series_key = key
                        break

                if not time_series_key:
                    continue

                time_series = response_dict[time_series_key]

                # Flatten: one row per date
                for date_str, ohlcv_data in time_series.items():
                    row = {
                        "ticker": ticker,
                        "asset_type": asset_type,
                        "trade_date": date_str,  # Will be parsed to date in postprocess
                        **ohlcv_data  # Include all OHLCV fields
                    }
                    flattened_rows.append(row)

            flattened_batches.append(flattened_rows)

        # Call base normalize() with flattened batches
        return super().normalize(flattened_batches)

    def postprocess(self, df):
        """
        Transform normalized DataFrame to final output schema.

        Transformations:
        1. Parse trade_date string to date type
        2. Rename Alpha Vantage fields (1. open -> open, etc.)
        3. Calculate volume-weighted price (VWAP approximation)
        4. Filter by date range if specified
        5. Handle missing fields (transactions, otc)
        6. Deduplicate by (ticker, trade_date)
        """
        # --- Parse trade_date ---
        df = df.withColumn("trade_date", to_date(col("trade_date"), "yyyy-MM-dd"))

        # --- Rename columns (remove numeric prefixes) ---
        # Alpha Vantage uses "1. open", "2. high", etc.
        rename_map = {
            "1. open": "open",
            "2. high": "high",
            "3. low": "low",
            "4. close": "close",
            "5. adjusted close": "adjusted_close",
            "6. volume": "volume",
            "7. dividend amount": "dividend_amount",
            "8. split coefficient": "split_coefficient"
        }

        for old_name, new_name in rename_map.items():
            if old_name in df.columns:
                df = df.withColumnRenamed(old_name, new_name)

        # --- Calculate VWAP ---
        # Alpha Vantage doesn't provide VWAP, so approximate as (H+L+C)/3
        df = df.withColumn(
            "volume_weighted",
            (col("high") + col("low") + col("close")) / 3.0
        )

        # --- Add missing fields ---
        if "transactions" not in df.columns:
            df = df.withColumn("transactions", lit(None).cast("long"))

        if "otc" not in df.columns:
            df = df.withColumn("otc", lit(False))

        # --- Date range filtering ---
        if self.date_from:
            df = df.filter(col("trade_date") >= lit(self.date_from))
        if self.date_to:
            df = df.filter(col("trade_date") <= lit(self.date_to))

        # --- Data Quality Filters ---
        df = df.filter(
            (col("ticker").isNotNull()) &
            (col("close").isNotNull()) &
            (col("close") > 0) &
            (col("trade_date").isNotNull())
        )

        # --- Select final columns in order ---
        final_cols = [col_name for col_name, _ in self.OUTPUT_SCHEMA]
        existing_cols = set(df.columns)

        # Add missing columns as NULL
        for col_name, col_type in self.OUTPUT_SCHEMA:
            if col_name not in existing_cols:
                df = df.withColumn(col_name, lit(None).cast(col_type))

        df = df.select(*final_cols)

        # --- Deduplicate ---
        df = df.dropDuplicates(["ticker", "trade_date"])

        return df

    def validate(self, df):
        """
        Validate the output DataFrame.

        Assertions:
        - No null tickers or trade_dates
        - Prices are positive
        - High >= Low
        - Volume is non-negative
        """
        # Check for nulls
        null_tickers = df.filter(col("ticker").isNull()).count()
        if null_tickers > 0:
            raise ValueError(f"Found {null_tickers} rows with null ticker")

        null_dates = df.filter(col("trade_date").isNull()).count()
        if null_dates > 0:
            raise ValueError(f"Found {null_dates} rows with null trade_date")

        # Check price validity
        invalid_prices = df.filter(
            (col("close") <= 0) |
            (col("high") < col("low"))
        ).count()
        if invalid_prices > 0:
            print(f"Warning: Found {invalid_prices} rows with invalid prices")

        # Check volume
        negative_volume = df.filter(col("volume") < 0).count()
        if negative_volume > 0:
            print(f"Warning: Found {negative_volume} rows with negative volume")

        return df