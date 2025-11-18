"""
SecuritiesReferenceFacet - Unified reference data for all security types.

This facet normalizes ticker reference data from Polygon with:
- CIK extraction from SEC identifiers
- Asset type classification (stocks, options, etfs, futures)
- Unified schema for all security types

Replaces: RefTickerFacet, RefAllTickersFacet
Bronze table: bronze/securities_reference/
"""

from typing import Iterable, List
from pyspark.sql import functions as F
from pyspark.sql.types import StringType
from datapipelines.providers.polygon.facets.polygon_base_facet import PolygonFacet
from datapipelines.facets.base_facet import coalesce_existing, first_existing


class SecuritiesReferenceFacet(PolygonFacet):
    """
    Unified reference data facet for all security types (stocks, options, ETFs, futures).

    Key Features:
    - Extracts CIK from SEC identifiers for company linkage
    - Classifies securities by asset_type
    - Normalizes ticker, name, exchange across all types
    - Includes key metadata (shares outstanding, contract specs, etc.)

    Usage:
        facet = SecuritiesReferenceFacet(
            spark,
            tickers=['AAPL', 'MSFT'],  # Optional: specific tickers
            asset_types=['stocks', 'options'],  # Optional: filter by type
            include_inactive=False  # Optional: include delisted securities
        )
    """

    name = "securities_reference"

    # Numeric coercion for API response fields
    NUMERIC_COERCE = {
        "share_class_shares_outstanding": "long",
        "market_cap": "double",
        "shares_outstanding": "long",
        "weighted_shares_outstanding": "long"
    }

    # Final Spark schema
    SPARK_CASTS = {
        "ticker": "string",
        "security_name": "string",
        "asset_type": "string",
        "cik": "string",
        "composite_figi": "string",
        "exchange_code": "string",
        "currency": "string",
        "market": "string",
        "locale": "string",
        "type": "string",
        "primary_exchange": "string",
        "shares_outstanding": "long",
        "market_cap": "double",
        "sic_code": "string",
        "sic_description": "string",
        "ticker_root": "string",
        "base_currency_symbol": "string",
        "currency_symbol": "string",
        "delisted_utc": "timestamp",
        "last_updated_utc": "timestamp",
        "is_active": "boolean"
    }

    FINAL_COLUMNS = [
        ("ticker", "string"),
        ("security_name", "string"),
        ("asset_type", "string"),
        ("cik", "string"),
        ("composite_figi", "string"),
        ("exchange_code", "string"),
        ("currency", "string"),
        ("market", "string"),
        ("locale", "string"),
        ("type", "string"),
        ("primary_exchange", "string"),
        ("shares_outstanding", "long"),
        ("market_cap", "double"),
        ("sic_code", "string"),
        ("sic_description", "string"),
        ("ticker_root", "string"),
        ("base_currency_symbol", "string"),
        ("currency_symbol", "string"),
        ("delisted_utc", "timestamp"),
        ("last_updated_utc", "timestamp"),
        ("is_active", "boolean")
    ]

    def __init__(self, spark, *,
                 tickers: List[str] = None,
                 asset_types: List[str] = None,
                 include_inactive: bool = False):
        """
        Initialize SecuritiesReferenceFacet.

        Args:
            spark: SparkSession
            tickers: Optional list of specific tickers to fetch
            asset_types: Optional filter by asset type (stocks, options, etfs, futures)
            include_inactive: Whether to include delisted/inactive securities
        """
        super().__init__(spark,
                        tickers=tickers or [],
                        asset_types=asset_types or [],
                        include_inactive=include_inactive)
        self.asset_types = asset_types or []
        self.include_inactive = include_inactive

    def calls(self) -> Iterable[dict]:
        """
        Generate API calls for reference data.

        Strategy:
        - If tickers specified: Use /v3/reference/tickers/{ticker} for each
        - Otherwise: Use /v3/reference/tickers with pagination
        """
        if self.tickers:
            # Fetch specific tickers
            for ticker in self.tickers:
                yield {
                    "ep_name": "ref_ticker_detailed",
                    "params": {"ticker": ticker}
                }
        else:
            # Fetch all tickers with pagination
            # Note: Polygon returns max 1000 per request, need pagination
            asset_class_map = {
                "stocks": "stocks",
                "options": "options",
                "etfs": "stocks",  # ETFs classified as stocks in Polygon
                "futures": "fx"  # Futures often in fx/crypto markets
            }

            if self.asset_types:
                # Fetch each asset type separately
                for asset_type in self.asset_types:
                    asset_class = asset_class_map.get(asset_type, "stocks")
                    yield {
                        "ep_name": "ref_all_tickers",
                        "params": {
                            "market": asset_class,
                            "active": "true" if not self.include_inactive else None,
                            "limit": 1000
                        }
                    }
            else:
                # Fetch all stocks by default
                yield {
                    "ep_name": "ref_all_tickers",
                    "params": {
                        "market": "stocks",
                        "active": "true" if not self.include_inactive else None,
                        "limit": 1000
                    }
                }

    def postprocess(self, df):
        """
        Transform Polygon reference data to unified securities schema.

        Key transformations:
        1. Extract CIK from cik field (10-digit SEC identifier)
        2. Classify asset_type from Polygon's type field
        3. Normalize exchange codes
        4. Extract shares outstanding and market cap
        """
        from pyspark.sql.functions import (
            col, when, lit, trim, regexp_extract,
            coalesce, upper, concat, lpad
        )

        # --- CIK Extraction ---
        # Polygon provides CIK in the 'cik' field
        # Format: "0001234567" (10 digits with leading zeros)
        # We want: "1234567" or keep as-is for consistency
        cik_expr = (
            when(col("cik").isNotNull(),
                 lpad(regexp_extract(col("cik"), r"(\d+)", 1), 10, "0"))
            .otherwise(lit(None))
            .cast("string")
        )

        # --- Asset Type Classification ---
        # Polygon type field examples: "CS" (common stock), "ADRC" (ADR), "ETF", "OS" (option)
        # Map to our canonical asset_type
        asset_type_expr = (
            when(col("type").isin("CS", "ADRC", "GDR", "PFD", "REIT", "RIGHT", "UNIT", "WARRANT"),
                 lit("stocks"))
            .when(col("type") == "ETF", lit("etfs"))
            .when(col("type").isin("OS", "OC"), lit("options"))  # OS=stock option, OC=currency option
            .when(col("type").contains("FUND"), lit("etfs"))
            .when(col("market") == "fx", lit("futures"))  # Futures often in FX market
            .otherwise(lit("stocks"))  # Default to stocks
            .cast("string")
        )

        # --- Exchange Code Normalization ---
        # Try multiple exchange fields in order of preference
        exchange_expr = coalesce_existing(df, [
            "primary_exchange",
            "primary_exchange_code",
            "exchange"
        ]).cast("string")

        # --- Security Name ---
        # Prefer 'name', fall back to 'ticker'
        name_expr = coalesce_existing(df, ["name", "ticker"]).cast("string")

        # --- Ticker Root Extraction ---
        # For options: Extract underlying ticker (e.g., "AAPL250117C00150000" -> "AAPL")
        # For stocks: Use ticker as-is
        ticker_root_expr = (
            when(asset_type_expr == lit("options"),
                 regexp_extract(col("ticker"), r"^([A-Z]+)", 1))
            .otherwise(col("ticker"))
            .cast("string")
        )

        # --- Build Final DataFrame ---
        result_df = df.select(
            col("ticker").cast("string").alias("ticker"),
            name_expr.alias("security_name"),
            asset_type_expr.alias("asset_type"),
            cik_expr.alias("cik"),
            col("composite_figi").cast("string").alias("composite_figi"),
            exchange_expr.alias("exchange_code"),
            coalesce(col("currency_name"), lit("USD")).cast("string").alias("currency"),
            coalesce(col("market"), lit("stocks")).cast("string").alias("market"),
            coalesce(col("locale"), lit("us")).cast("string").alias("locale"),
            col("type").cast("string").alias("type"),
            col("primary_exchange").cast("string").alias("primary_exchange"),

            # Market data fields
            first_existing(df, [
                "share_class_shares_outstanding",
                "shares_outstanding",
                "weighted_shares_outstanding"
            ]).cast("long").alias("shares_outstanding"),
            col("market_cap").cast("double").alias("market_cap"),

            # Company classification
            col("sic_code").cast("string").alias("sic_code"),
            col("sic_description").cast("string").alias("sic_description"),

            # Additional metadata
            ticker_root_expr.alias("ticker_root"),
            col("base_currency_symbol").cast("string").alias("base_currency_symbol"),
            col("currency_symbol").cast("string").alias("currency_symbol"),
            col("delisted_utc").cast("timestamp").alias("delisted_utc"),
            col("last_updated_utc").cast("timestamp").alias("last_updated_utc"),
            coalesce(col("active"), lit(True)).cast("boolean").alias("is_active")
        )

        # --- Filters ---
        # Remove rows without ticker
        result_df = result_df.filter(col("ticker").isNotNull())

        # Deduplicate by ticker (keep most recent)
        result_df = result_df.dropDuplicates(["ticker"])

        # Optional: Filter by asset type
        if self.asset_types:
            result_df = result_df.filter(col("asset_type").isin(self.asset_types))

        return result_df

    def validate(self, df):
        """
        Validate the output DataFrame.

        Assertions:
        - ticker is not null
        - asset_type is one of: stocks, options, etfs, futures
        - CIK is 10 digits when present
        """
        from pyspark.sql.functions import col, length

        # Check for null tickers
        null_count = df.filter(col("ticker").isNull()).count()
        if null_count > 0:
            raise ValueError(f"Found {null_count} rows with null ticker")

        # Check asset_type validity
        valid_types = ["stocks", "options", "etfs", "futures"]
        invalid_types = df.filter(~col("asset_type").isin(valid_types)).select("asset_type").distinct()
        if invalid_types.count() > 0:
            invalid_list = [row.asset_type for row in invalid_types.collect()]
            raise ValueError(f"Found invalid asset types: {invalid_list}")

        # Check CIK format (should be 10 digits when present)
        invalid_cik = df.filter(
            col("cik").isNotNull() & (length(col("cik")) != 10)
        ).count()
        if invalid_cik > 0:
            print(f"Warning: Found {invalid_cik} rows with invalid CIK format (not 10 digits)")

        return df
