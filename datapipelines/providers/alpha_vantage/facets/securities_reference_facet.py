"""
SecuritiesReferenceFacetAV - Alpha Vantage reference data facet.

Maps Alpha Vantage OVERVIEW endpoint to unified securities_reference schema.

Key Differences from Polygon:
- No CIK field (Alpha Vantage doesn't provide SEC identifiers)
- Different field names (Symbol vs ticker, MarketCapitalization vs market_cap)
- More fundamental data (PE ratio, dividend yield, etc.)
- One API call per ticker (no bulk endpoint)

Bronze table: bronze/securities_reference/
Partitions: snapshot_dt, asset_type
"""

from typing import Iterable, List
from pyspark.sql import functions as F
from pyspark.sql.types import StringType
from datapipelines.providers.alpha_vantage.facets.alpha_vantage_base_facet import AlphaVantageFacet
from datapipelines.facets.base_facet import coalesce_existing, first_existing
from datetime import datetime


class SecuritiesReferenceFacetAV(AlphaVantageFacet):
    """
    Unified reference data facet using Alpha Vantage OVERVIEW endpoint.

    Maps to same schema as Polygon's SecuritiesReferenceFacet for compatibility.

    Note: CIK field will be NULL as Alpha Vantage doesn't provide it.
    Consider using a separate SEC EDGAR lookup if CIK is critical.

    Usage:
        facet = SecuritiesReferenceFacetAV(
            spark,
            tickers=['AAPL', 'MSFT', 'GOOGL']
        )
    """

    name = "securities_reference"

    # Numeric coercion for Alpha Vantage response
    NUMERIC_COERCE = {
        "MarketCapitalization": "long",
        "SharesOutstanding": "long",
        "PERatio": "double",
        "PEGRatio": "double",
        "BookValue": "double",
        "DividendPerShare": "double",
        "DividendYield": "double",
        "EPS": "double",
        "52WeekHigh": "double",
        "52WeekLow": "double"
    }

    # Final Spark schema (matches Polygon schema for compatibility)
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
        ("cik", "string"),  # Will be NULL for Alpha Vantage
        ("composite_figi", "string"),  # Will be NULL for Alpha Vantage
        ("exchange_code", "string"),
        ("currency", "string"),
        ("market", "string"),
        ("locale", "string"),
        ("type", "string"),
        ("primary_exchange", "string"),
        ("shares_outstanding", "long"),
        ("market_cap", "double"),
        ("sic_code", "string"),  # Will be NULL for Alpha Vantage
        ("sic_description", "string"),
        ("ticker_root", "string"),
        ("base_currency_symbol", "string"),
        ("currency_symbol", "string"),
        ("delisted_utc", "timestamp"),
        ("last_updated_utc", "timestamp"),
        ("is_active", "boolean"),
        # Additional Alpha Vantage fields (optional)
        ("sector", "string"),
        ("industry", "string"),
        ("description", "string"),
        ("pe_ratio", "double"),
        ("peg_ratio", "double"),
        ("book_value", "double"),
        ("dividend_per_share", "double"),
        ("dividend_yield", "double"),
        ("eps", "double"),
        ("week_52_high", "double"),
        ("week_52_low", "double")
    ]

    def __init__(self, spark, *, tickers: List[str]):
        """
        Initialize Alpha Vantage reference data facet.

        Args:
            spark: SparkSession
            tickers: List of ticker symbols to fetch
        """
        super().__init__(spark, tickers=tickers)

    def calls(self) -> Iterable[dict]:
        """
        Generate API calls for company overview data.

        Alpha Vantage requires one call per ticker (no bulk endpoint).
        Rate limit: 5 calls/minute for free tier.
        """
        for ticker in self.tickers:
            yield {
                "ep_name": "company_overview",
                "params": {"symbol": ticker}
            }

    def postprocess(self, df):
        """
        Transform Alpha Vantage OVERVIEW response to unified securities schema.

        Key Transformations:
        1. Map Alpha Vantage field names to unified schema
        2. Set asset_type based on AssetType field or infer from ticker
        3. Set CIK to NULL (not available in Alpha Vantage)
        4. Extract and normalize exchange codes
        5. Convert market cap and shares outstanding to proper types

        Alpha Vantage OVERVIEW Response Fields:
        - Symbol, Name, Description
        - Exchange, Currency, Country, Sector, Industry
        - AssetType (Common Stock, ETF, etc.)
        - MarketCapitalization, SharesOutstanding
        - PERatio, PEGRatio, BookValue, EPS
        - DividendPerShare, DividendYield
        - 52WeekHigh, 52WeekLow
        """
        from pyspark.sql.functions import (
            col, when, lit, trim, coalesce, upper, current_timestamp, expr
        )

        # Helper function for safe casting (compatible with all PySpark versions)
        def safe_cast(column_name, target_type):
            """Safely cast a column, returning NULL for invalid values."""
            invalid_values = "('', 'None', 'N/A', '-')"
            return expr(f"""
                CASE
                    WHEN {column_name} IN {invalid_values} OR {column_name} IS NULL
                    THEN NULL
                    ELSE CAST({column_name} AS {target_type})
                END
            """)

        # --- Asset Type Classification ---
        # Alpha Vantage provides AssetType field
        # Map to our canonical asset_type
        asset_type_expr = (
            when(col("AssetType") == "Common Stock", lit("stocks"))
            .when(col("AssetType") == "ETF", lit("etfs"))
            .when(col("AssetType") == "Mutual Fund", lit("etfs"))
            .when(col("AssetType").contains("Option"), lit("options"))
            .when(col("AssetType").contains("Future"), lit("futures"))
            .otherwise(lit("stocks"))  # Default to stocks
            .cast("string")
        )

        # --- Ticker Root Extraction ---
        # For options: Extract underlying ticker
        # For stocks: Use Symbol as-is
        ticker_root_expr = col("Symbol").cast("string")

        # --- Build Final DataFrame ---
        result_df = df.select(
            # Core identifiers
            col("Symbol").cast("string").alias("ticker"),
            col("Name").cast("string").alias("security_name"),
            asset_type_expr.alias("asset_type"),

            # CIK and FIGI (not available in Alpha Vantage)
            lit(None).cast("string").alias("cik"),
            lit(None).cast("string").alias("composite_figi"),

            # Exchange information
            col("Exchange").cast("string").alias("exchange_code"),
            coalesce(col("Currency"), lit("USD")).cast("string").alias("currency"),
            lit("stocks").cast("string").alias("market"),  # Alpha Vantage is primarily stocks
            coalesce(col("Country"), lit("US")).cast("string").alias("locale"),
            col("AssetType").cast("string").alias("type"),
            col("Exchange").cast("string").alias("primary_exchange"),

            # Market data - use safe_cast to handle invalid values gracefully
            safe_cast("SharesOutstanding", "LONG").alias("shares_outstanding"),
            safe_cast("MarketCapitalization", "DOUBLE").alias("market_cap"),

            # SIC codes (not available in Alpha Vantage)
            lit(None).cast("string").alias("sic_code"),
            col("Sector").cast("string").alias("sic_description"),  # Use Sector as proxy

            # Additional metadata
            ticker_root_expr.alias("ticker_root"),
            col("Currency").cast("string").alias("base_currency_symbol"),
            col("Currency").cast("string").alias("currency_symbol"),

            # Timestamps
            lit(None).cast("timestamp").alias("delisted_utc"),
            current_timestamp().alias("last_updated_utc"),
            lit(True).cast("boolean").alias("is_active"),  # Assume active if returned

            # Alpha Vantage specific fields (additional)
            col("Sector").cast("string").alias("sector"),
            col("Industry").cast("string").alias("industry"),
            col("Description").cast("string").alias("description"),

            # Alpha Vantage numeric fields - use safe_cast to handle invalid values gracefully
            safe_cast("PERatio", "DOUBLE").alias("pe_ratio"),
            safe_cast("PEGRatio", "DOUBLE").alias("peg_ratio"),
            safe_cast("BookValue", "DOUBLE").alias("book_value"),
            safe_cast("DividendPerShare", "DOUBLE").alias("dividend_per_share"),
            safe_cast("DividendYield", "DOUBLE").alias("dividend_yield"),
            safe_cast("EPS", "DOUBLE").alias("eps"),
            safe_cast("`52WeekHigh`", "DOUBLE").alias("week_52_high"),
            safe_cast("`52WeekLow`", "DOUBLE").alias("week_52_low")
        )

        # --- Filters ---
        # Remove rows without ticker
        result_df = result_df.filter(col("ticker").isNotNull())

        # Filter out rows where Alpha Vantage returned error or invalid data
        # (Alpha Vantage sometimes returns "Error Message" or "Note" fields)
        if "Error Message" in df.columns:
            result_df = result_df.filter(col("Error Message").isNull())

        # Deduplicate by ticker
        result_df = result_df.dropDuplicates(["ticker"])

        return result_df

    def validate(self, df):
        """
        Validate the output DataFrame.

        Assertions:
        - ticker is not null
        - asset_type is valid
        - market_cap and shares_outstanding are non-negative when present

        Note: CIK will always be NULL for Alpha Vantage data.
        """
        from pyspark.sql.functions import col

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

        # Check for negative market cap or shares (data quality issue)
        invalid_data = df.filter(
            (col("market_cap").isNotNull() & (col("market_cap") < 0)) |
            (col("shares_outstanding").isNotNull() & (col("shares_outstanding") < 0))
        ).count()
        if invalid_data > 0:
            print(f"Warning: Found {invalid_data} rows with negative market_cap or shares_outstanding")

        return df
