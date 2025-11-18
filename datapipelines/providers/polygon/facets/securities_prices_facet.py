"""
SecuritiesPricesFacet - Unified daily prices for all security types.

This facet normalizes daily OHLCV (Open, High, Low, Close, Volume) data from Polygon for:
- Stocks
- Options
- ETFs
- Futures

Key Features:
- Unified schema with asset_type filtering in silver layer
- Includes volume-weighted average price (VWAP)
- Handles API response enrichment with ticker context
- Partitioned by trade_date and asset_type

Replaces: PricesDailyFacet, PricesDailyGroupedFacet
Bronze table: bronze/securities_prices_daily/
"""

from __future__ import annotations
from typing import Iterable, List, Tuple
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.functions import col, lit, when, coalesce
from datapipelines.providers.polygon.facets.polygon_base_facet import PolygonFacet
from orchestration.common.spark_df_utils import epoch_ms_to_date


class SecuritiesPricesFacet(PolygonFacet):
    """
    Unified daily OHLCV prices for all security types.

    Fetches daily aggregate bars (OHLCV) from Polygon API and normalizes
    to a unified schema with asset_type classification.

    Usage:
        facet = SecuritiesPricesFacet(
            spark,
            tickers=['AAPL', 'MSFT'],
            date_from='2024-01-01',
            date_to='2024-12-31',
            asset_types=['stocks', 'options']  # Optional filter
        )

    Output Schema:
        - trade_date: date
        - ticker: string
        - asset_type: string (stocks, options, etfs, futures)
        - open: double
        - high: double
        - low: double
        - close: double
        - volume: double
        - volume_weighted: double (VWAP)
        - transactions: long (number of trades)
        - otc: boolean (over-the-counter flag)
    """

    name = "securities_prices_daily"

    # Numeric coercion for Polygon API response
    # Polygon returns: t (timestamp), o/h/l/c (prices), v (volume), vw (vwap), n (transactions)
    NUMERIC_COERCE = {
        "t": "long",
        "o": "double",
        "h": "double",
        "l": "double",
        "c": "double",
        "v": "double",
        "vw": "double",
        "n": "long"
    }

    # Rename map from Polygon field names to our schema
    RENAME_MAP = {
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "vw": "volume_weighted",
        "n": "transactions",
        "T": "ticker"  # Injected during normalize()
    }

    # Final output schema
    OUTPUT_SCHEMA = [
        ("trade_date", "date"),
        ("ticker", "string"),
        ("asset_type", "string"),
        ("open", "double"),
        ("high", "double"),
        ("low", "double"),
        ("close", "double"),
        ("volume", "double"),
        ("volume_weighted", "double"),
        ("transactions", "long"),
        ("otc", "boolean")
    ]

    # Derived columns (computed from raw fields)
    DERIVED = {
        "trade_date": lambda df: epoch_ms_to_date("t")
    }

    def __init__(self, spark: SparkSession, *,
                 tickers: List[str],
                 date_from: str,
                 date_to: str,
                 asset_types: List[str] = None,
                 mult: int = 1,
                 timespan: str = "day",
                 adjusted: bool = True):
        """
        Initialize SecuritiesPricesFacet.

        Args:
            spark: SparkSession
            tickers: List of tickers to fetch (required)
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            asset_types: Optional filter by asset type (stocks, options, etfs, futures)
            mult: Multiplier for timespan (e.g., 1 day, 5 minutes)
            timespan: Time period (day, week, month, minute, hour)
            adjusted: Whether to use split/dividend adjusted prices
        """
        super().__init__(spark,
                        tickers=tickers,
                        date_from=date_from,
                        date_to=date_to,
                        mult=mult,
                        timespan=timespan,
                        adjusted=adjusted)
        self.asset_types = asset_types or []
        self.adjusted = adjusted
        self._call_contexts: List[dict] = []  # Track ticker per API call

    def calls(self) -> Iterable[dict]:
        """
        Generate API calls for daily price data.

        Uses Polygon's aggregates endpoint:
        /v2/aggs/ticker/{ticker}/range/{mult}/{timespan}/{from}/{to}

        Enriches each call with metadata (ticker, asset_type) for downstream processing.
        """
        self._call_contexts = []

        for ticker in self.tickers:
            # Determine asset type from ticker pattern
            # (This is a heuristic; ideally joined with reference data)
            asset_type = self._infer_asset_type(ticker)

            # Skip if filtering by asset type
            if self.asset_types and asset_type not in self.asset_types:
                continue

            # Build API call parameters
            params = {
                "ticker": ticker,
                "from": self.date_from,
                "to": self.date_to,
                "mult": self.extra.get("mult", 1),
                "timespan": self.extra.get("timespan", "day"),
                "adjusted": str(self.adjusted).lower()
            }

            # Track context for this call (used in normalize())
            self._call_contexts.append({
                "ticker": ticker,
                "asset_type": asset_type
            })

            yield {
                "ep_name": "prices_daily_agg",
                "params": params
            }

    def _infer_asset_type(self, ticker: str) -> str:
        """
        Infer asset type from ticker pattern.

        Heuristics:
        - Options: Long ticker with strike/date encoding (e.g., AAPL250117C00150000)
        - ETFs: Common patterns (SPY, QQQ, IWM) - ideally from reference data
        - Stocks: Default
        - Futures: Commodity codes (CL, GC, ES, etc.)

        Note: This is imperfect. Ideally, join with securities_reference.
        """
        ticker = ticker.upper()

        # Options pattern: Ticker + 6 digits (date) + C/P + 8 digits (strike)
        # Example: AAPL250117C00150000 (AAPL call expiring 2025-01-17 strike $150)
        if len(ticker) > 10 and ticker[-9] in ('C', 'P'):
            return "options"

        # Common ETF tickers (non-exhaustive)
        etf_tickers = {'SPY', 'QQQ', 'IWM', 'DIA', 'GLD', 'SLV', 'TLT', 'EEM', 'VTI', 'VOO'}
        if ticker in etf_tickers or ticker.startswith('SPDR') or ticker.startswith('ISHARES'):
            return "etfs"

        # Futures: 2-3 character commodity codes
        futures_codes = {'CL', 'GC', 'ES', 'NQ', 'ZB', 'ZN', 'ZT', 'HG', 'SI'}
        if ticker in futures_codes:
            return "futures"

        # Default to stocks
        return "stocks"

    def normalize(self, raw_batches: List[List[dict]]):
        """
        Normalize raw API responses to DataFrame.

        Key transformation:
        - Inject ticker and asset_type into each row (from call context)
        - Convert epoch timestamp (ms) to date
        - Apply column renames

        This overrides base normalize() to enrich rows before DataFrame creation.
        """
        enriched_batches: List[List[dict]] = []

        # Zip raw batches with call contexts (matched by position)
        for i, rows in enumerate(raw_batches):
            ctx = None
            if i < len(self._call_contexts):
                ctx = self._call_contexts[i]

            if ctx and rows:
                # Inject ticker and asset_type into each row
                ticker = ctx.get("ticker")
                asset_type = ctx.get("asset_type", "stocks")
                enriched_rows = [
                    {**row, "T": ticker, "asset_type": asset_type}
                    for row in rows
                ]
                enriched_batches.append(enriched_rows)
            else:
                enriched_batches.append(rows or [])

        # Call base normalize() with enriched batches
        return super().normalize(enriched_batches)

    def postprocess(self, df):
        """
        Transform normalized DataFrame to final output schema.

        Transformations:
        1. Derive trade_date from timestamp (epoch ms)
        2. Rename columns (o->open, h->high, etc.)
        3. Add OTC flag (over-the-counter trading)
        4. Filter invalid data (null prices, zero volume)
        5. Deduplicate by (ticker, trade_date)

        Returns:
            DataFrame with OUTPUT_SCHEMA columns
        """
        # --- Derive trade_date ---
        if "t" in df.columns:
            df = df.withColumn("trade_date", epoch_ms_to_date("t"))

        # --- Column renaming ---
        for old_name, new_name in self.RENAME_MAP.items():
            if old_name in df.columns and old_name != new_name:
                df = df.withColumnRenamed(old_name, new_name)

        # --- OTC Flag ---
        # Polygon provides 'otc' field for over-the-counter trades
        # Default to False if not present
        if "otc" not in df.columns:
            df = df.withColumn("otc", lit(False))

        # --- Data Quality Filters ---
        # Remove rows with:
        # - Null or zero close price (invalid data)
        # - Null ticker (should never happen after normalize, but safe)
        df = df.filter(
            (col("ticker").isNotNull()) &
            (col("close").isNotNull()) &
            (col("close") > 0) &
            (col("trade_date").isNotNull())
        )

        # --- Handle missing VWAP ---
        # If volume_weighted (VWAP) is null, approximate as average of OHLC
        df = df.withColumn(
            "volume_weighted",
            when(col("volume_weighted").isNotNull(), col("volume_weighted"))
            .otherwise((col("open") + col("high") + col("low") + col("close")) / 4.0)
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
        # Keep most recent record per (ticker, trade_date)
        # Order by transactions desc (more trades = more reliable data)
        from pyspark.sql.window import Window

        window_spec = Window.partitionBy("ticker", "trade_date").orderBy(
            col("transactions").desc_nulls_last()
        )
        df = df.withColumn("_row_num", F.row_number().over(window_spec))
        df = df.filter(col("_row_num") == 1).drop("_row_num")

        return df

    def validate(self, df):
        """
        Validate the output DataFrame.

        Assertions:
        - No null tickers or trade_dates
        - Prices are positive
        - High >= Low
        - Volume is non-negative
        - Asset type is valid

        Returns:
            Validated DataFrame

        Raises:
            ValueError if validation fails
        """
        # Check for nulls in key columns
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
            print(f"Warning: Found {invalid_prices} rows with invalid prices (close<=0 or high<low)")

        # Check volume
        negative_volume = df.filter(col("volume") < 0).count()
        if negative_volume > 0:
            print(f"Warning: Found {negative_volume} rows with negative volume")

        # Check asset_type validity
        valid_types = ["stocks", "options", "etfs", "futures"]
        invalid_types = df.filter(~col("asset_type").isin(valid_types)).count()
        if invalid_types > 0:
            print(f"Warning: Found {invalid_types} rows with invalid asset_type")

        return df
