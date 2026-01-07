"""
SecuritiesReferenceFacetAV - Alpha Vantage reference data facet.

Maps Alpha Vantage OVERVIEW endpoint to unified securities_reference schema.

Key Differences from Polygon:
- Includes CIK (SEC Central Index Key) for company identification
- Different field names (Symbol vs ticker, MarketCapitalization vs market_cap)
- More fundamental data (PE ratio, dividend yield, etc.)
- One API call per ticker (no bulk endpoint)

Bronze table: bronze/securities_reference/
Partitions: asset_type
"""

from typing import Iterable, List
from pyspark.sql import functions as F
from pyspark.sql.types import StringType
from datapipelines.providers.alpha_vantage.facets.alpha_vantage_base_facet import (
    AlphaVantageFacet, safe_long, safe_double
)
from datapipelines.base.facet import coalesce_existing, first_existing
from datetime import datetime


class SecuritiesReferenceFacetAV(AlphaVantageFacet):
    """
    Unified reference data facet using Alpha Vantage OVERVIEW endpoint.

    Maps to same schema as Polygon's SecuritiesReferenceFacet for compatibility.

    Alpha Vantage provides CIK (SEC Central Index Key) which is padded to 10 digits
    per SEC standard for use as a permanent company identifier.

    Usage:
        facet = SecuritiesReferenceFacetAV(
            spark,
            tickers=['AAPL', 'MSFT', 'GOOGL']
        )
    """

    name = "securities_reference"

    # Load schema from configs/schemas/alpha_vantage.yaml
    INPUT_SCHEMA_KEY = "overview"

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
        ("cik", "string"),  # SEC Central Index Key (padded to 10 digits)
        ("composite_figi", "string"),  # Will be NULL for Alpha Vantage
        ("exchange_code", "string"),
        ("currency", "string"),
        ("market", "string"),
        ("locale", "string"),
        ("type", "string"),
        ("primary_exchange", "string"),
        ("shares_outstanding", "long"),  # Converted via pandas
        ("market_cap", "double"),  # Converted via pandas
        ("sic_code", "string"),  # Will be NULL for Alpha Vantage
        ("sic_description", "string"),
        ("ticker_root", "string"),
        ("base_currency_symbol", "string"),
        ("currency_symbol", "string"),
        ("delisted_utc", "timestamp"),
        ("last_updated_utc", "timestamp"),
        ("is_active", "boolean"),
        # Additional Alpha Vantage fields
        ("sector", "string"),
        ("industry", "string"),
        ("description", "string"),
        ("pe_ratio", "double"),  # Converted via pandas
        ("peg_ratio", "double"),  # Converted via pandas
        ("book_value", "double"),  # Converted via pandas
        ("dividend_per_share", "double"),  # Converted via pandas
        ("dividend_yield", "double"),  # Converted via pandas
        ("eps", "double"),  # Converted via pandas
        ("week_52_high", "double"),  # Converted via pandas
        ("week_52_low", "double")  # Converted via pandas
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

    def _get_output_schema(self):
        """Get the output schema for the transformed DataFrame."""
        from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType, TimestampType, BooleanType

        return StructType([
            StructField("ticker", StringType(), True),
            StructField("security_name", StringType(), True),
            StructField("asset_type", StringType(), True),
            StructField("cik", StringType(), True),
            StructField("composite_figi", StringType(), True),
            StructField("exchange_code", StringType(), True),
            StructField("currency", StringType(), True),
            StructField("market", StringType(), True),
            StructField("locale", StringType(), True),
            StructField("type", StringType(), True),
            StructField("primary_exchange", StringType(), True),
            StructField("shares_outstanding", LongType(), True),
            StructField("market_cap", DoubleType(), True),
            StructField("sic_code", StringType(), True),
            StructField("sic_description", StringType(), True),
            StructField("ticker_root", StringType(), True),
            StructField("base_currency_symbol", StringType(), True),
            StructField("currency_symbol", StringType(), True),
            StructField("delisted_utc", TimestampType(), True),
            StructField("last_updated_utc", TimestampType(), True),
            StructField("is_active", BooleanType(), True),
            StructField("sector", StringType(), True),
            StructField("industry", StringType(), True),
            StructField("description", StringType(), True),
            StructField("pe_ratio", DoubleType(), True),
            StructField("peg_ratio", DoubleType(), True),
            StructField("book_value", DoubleType(), True),
            StructField("dividend_per_share", DoubleType(), True),
            StructField("dividend_yield", DoubleType(), True),
            StructField("eps", DoubleType(), True),
            StructField("week_52_high", DoubleType(), True),
            StructField("week_52_low", DoubleType(), True)
        ])

    def postprocess(self, df):
        """
        Transform Alpha Vantage OVERVIEW response to unified securities schema.

        Uses pandas for transformation to avoid Spark 4.0.1 optimizer issues.
        Pandas handles string-to-numeric conversion gracefully with pd.to_numeric().

        Key Transformations:
        1. Map Alpha Vantage field names to unified schema
        2. Set asset_type based on AssetType field
        3. Convert numeric fields using pandas (handles "None" strings gracefully)
        4. Extract CIK and pad to 10 digits per SEC standard

        Alpha Vantage OVERVIEW Response Fields:
        - Symbol, Name, Description, CIK
        - Exchange, Currency, Country, Sector, Industry
        - AssetType (Common Stock, ETF, etc.)
        - MarketCapitalization, SharesOutstanding
        - PERatio, PEGRatio, BookValue, EPS
        - DividendPerShare, DividendYield
        - 52WeekHigh, 52WeekLow
        """
        import pandas as pd
        from datetime import datetime

        # Convert Spark DataFrame to pandas (small data - API responses)
        pdf = df.toPandas()

        # Filter out error responses
        if 'Error Message' in pdf.columns:
            pdf = pdf[pdf['Error Message'].isna()]

        # Remove rows without ticker
        pdf = pdf[pdf['Symbol'].notna()].copy()

        if pdf.empty:
            # Return empty Spark DataFrame with correct schema
            return self.spark.createDataFrame([], schema=self._get_output_schema())

        # Map asset types
        def map_asset_type(asset_type):
            if pd.isna(asset_type):
                return "stocks"
            asset_type = str(asset_type)
            if asset_type == "Common Stock":
                return "stocks"
            elif asset_type in ("ETF", "Mutual Fund"):
                return "etfs"
            elif "Option" in asset_type:
                return "options"
            elif "Future" in asset_type:
                return "futures"
            else:
                return "stocks"

        # Build result DataFrame using Python native types
        # Uses safe_long/safe_double from base facet for Spark type compatibility
        result = pd.DataFrame({
            # Core identifiers
            'ticker': pdf['Symbol'].tolist(),
            'security_name': pdf['Name'].tolist(),
            'asset_type': pdf['AssetType'].apply(map_asset_type).tolist(),

            # CIK from Alpha Vantage (pad to 10 digits per SEC standard)
            'cik': pdf.get('CIK').apply(lambda x: str(x).zfill(10) if pd.notna(x) and str(x) != 'None' else None).tolist(),
            # FIGI not available in Alpha Vantage
            'composite_figi': [None] * len(pdf),

            # Exchange information
            'exchange_code': pdf['Exchange'].tolist(),
            'currency': pdf.get('Currency', pd.Series(['USD'] * len(pdf))).fillna('USD').tolist(),
            'market': ['stocks'] * len(pdf),
            'locale': pdf.get('Country', pd.Series(['US'] * len(pdf))).fillna('US').tolist(),
            'type': pdf['AssetType'].tolist(),
            'primary_exchange': pdf['Exchange'].tolist(),

            # Market data - use safe conversion to Python native types
            'shares_outstanding': safe_long(pdf.get('SharesOutstanding')),
            'market_cap': safe_double(pdf.get('MarketCapitalization')),

            # SIC codes (not available)
            'sic_code': [None] * len(pdf),
            'sic_description': pdf.get('Sector').tolist(),

            # Additional metadata
            'ticker_root': pdf['Symbol'].tolist(),
            'base_currency_symbol': pdf.get('Currency').tolist(),
            'currency_symbol': pdf.get('Currency').tolist(),

            # Timestamps
            'delisted_utc': [None] * len(pdf),
            'last_updated_utc': [datetime.now()] * len(pdf),
            'is_active': [True] * len(pdf),

            # Alpha Vantage specific fields
            'sector': pdf.get('Sector').tolist(),
            'industry': pdf.get('Industry').tolist(),
            'description': pdf.get('Description').tolist(),

            # Numeric fields - use safe conversion to Python native types
            'pe_ratio': safe_double(pdf.get('PERatio')),
            'peg_ratio': safe_double(pdf.get('PEGRatio')),
            'book_value': safe_double(pdf.get('BookValue')),
            'dividend_per_share': safe_double(pdf.get('DividendPerShare')),
            'dividend_yield': safe_double(pdf.get('DividendYield')),
            'eps': safe_double(pdf.get('EPS')),
            'week_52_high': safe_double(pdf.get('52WeekHigh')),
            'week_52_low': safe_double(pdf.get('52WeekLow'))
        })

        # Deduplicate
        result = result.drop_duplicates(subset=['ticker'])

        # Convert back to Spark DataFrame with explicit schema (avoids CANNOT_DETERMINE_TYPE)
        return self.spark.createDataFrame(result, schema=self._get_output_schema())

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
