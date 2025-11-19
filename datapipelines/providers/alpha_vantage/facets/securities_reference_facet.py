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

    def postprocess(self, df):
        """
        Transform Alpha Vantage OVERVIEW response to unified securities schema.

        Uses pandas for transformation to avoid Spark 4.0.1 optimizer issues.
        Pandas handles string-to-numeric conversion gracefully with pd.to_numeric().

        Key Transformations:
        1. Map Alpha Vantage field names to unified schema
        2. Set asset_type based on AssetType field
        3. Convert numeric fields using pandas (handles "None" strings gracefully)
        4. Set CIK to NULL (not available in Alpha Vantage)

        Alpha Vantage OVERVIEW Response Fields:
        - Symbol, Name, Description
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
            from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType, TimestampType, BooleanType
            schema = StructType([
                StructField("ticker", StringType()),
                StructField("security_name", StringType()),
                StructField("asset_type", StringType()),
                StructField("cik", StringType()),
                StructField("composite_figi", StringType()),
                StructField("exchange_code", StringType()),
                StructField("currency", StringType()),
                StructField("market", StringType()),
                StructField("locale", StringType()),
                StructField("type", StringType()),
                StructField("primary_exchange", StringType()),
                StructField("shares_outstanding", LongType()),
                StructField("market_cap", DoubleType()),
                StructField("sic_code", StringType()),
                StructField("sic_description", StringType()),
                StructField("ticker_root", StringType()),
                StructField("base_currency_symbol", StringType()),
                StructField("currency_symbol", StringType()),
                StructField("delisted_utc", TimestampType()),
                StructField("last_updated_utc", TimestampType()),
                StructField("is_active", BooleanType()),
                StructField("sector", StringType()),
                StructField("industry", StringType()),
                StructField("description", StringType()),
                StructField("pe_ratio", DoubleType()),
                StructField("peg_ratio", DoubleType()),
                StructField("book_value", DoubleType()),
                StructField("dividend_per_share", DoubleType()),
                StructField("dividend_yield", DoubleType()),
                StructField("eps", DoubleType()),
                StructField("week_52_high", DoubleType()),
                StructField("week_52_low", DoubleType())
            ])
            return self.spark.createDataFrame([], schema)

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

        # Build result DataFrame
        result = pd.DataFrame({
            # Core identifiers
            'ticker': pdf['Symbol'],
            'security_name': pdf['Name'],
            'asset_type': pdf['AssetType'].apply(map_asset_type),

            # CIK and FIGI (not available)
            'cik': None,
            'composite_figi': None,

            # Exchange information
            'exchange_code': pdf['Exchange'],
            'currency': pdf.get('Currency', 'USD').fillna('USD'),
            'market': 'stocks',
            'locale': pdf.get('Country', 'US').fillna('US'),
            'type': pdf['AssetType'],
            'primary_exchange': pdf['Exchange'],

            # Market data - use pd.to_numeric for safe conversion
            'shares_outstanding': pd.to_numeric(pdf.get('SharesOutstanding'), errors='coerce').astype('Int64'),
            'market_cap': pd.to_numeric(pdf.get('MarketCapitalization'), errors='coerce'),

            # SIC codes (not available)
            'sic_code': None,
            'sic_description': pdf.get('Sector'),

            # Additional metadata
            'ticker_root': pdf['Symbol'],
            'base_currency_symbol': pdf.get('Currency'),
            'currency_symbol': pdf.get('Currency'),

            # Timestamps
            'delisted_utc': None,
            'last_updated_utc': datetime.now(),
            'is_active': True,

            # Alpha Vantage specific fields
            'sector': pdf.get('Sector'),
            'industry': pdf.get('Industry'),
            'description': pdf.get('Description'),

            # Numeric fields - pd.to_numeric handles "None" gracefully
            'pe_ratio': pd.to_numeric(pdf.get('PERatio'), errors='coerce'),
            'peg_ratio': pd.to_numeric(pdf.get('PEGRatio'), errors='coerce'),
            'book_value': pd.to_numeric(pdf.get('BookValue'), errors='coerce'),
            'dividend_per_share': pd.to_numeric(pdf.get('DividendPerShare'), errors='coerce'),
            'dividend_yield': pd.to_numeric(pdf.get('DividendYield'), errors='coerce'),
            'eps': pd.to_numeric(pdf.get('EPS'), errors='coerce'),
            'week_52_high': pd.to_numeric(pdf.get('52WeekHigh'), errors='coerce'),
            'week_52_low': pd.to_numeric(pdf.get('52WeekLow'), errors='coerce')
        })

        # Deduplicate
        result = result.drop_duplicates(subset=['ticker'])

        # Convert back to Spark DataFrame
        return self.spark.createDataFrame(result)

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
