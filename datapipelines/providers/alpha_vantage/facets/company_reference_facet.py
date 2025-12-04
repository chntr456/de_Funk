"""
CompanyReferenceFacet - Alpha Vantage company data facet.

Extracts company-specific data from OVERVIEW endpoint for the company model.
This is SEPARATE from securities_reference to avoid the bulk listing overwrite problem.

Key Fields:
- CIK (SEC Central Index Key) - permanent company identifier
- sector, industry, description
- market_cap, shares_outstanding
- PE ratio, EPS, dividend info

Bronze table: bronze/company_reference/
Partitions: snapshot_dt
"""

from typing import List
import pandas as pd
from datetime import datetime
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, DoubleType, TimestampType, BooleanType
)
from datapipelines.providers.alpha_vantage.facets.alpha_vantage_base_facet import AlphaVantageFacet


class CompanyReferenceFacet(AlphaVantageFacet):
    """
    Company reference data facet - extracts company-specific fields from OVERVIEW.

    This facet produces data for the company model's dim_company table.
    It is kept separate from securities_reference so that:
    1. Bulk listing (LISTING_STATUS) doesn't overwrite company data
    2. Company data can accumulate across multiple ingestion runs
    3. Data model is cleaner (securities ≠ companies)

    Usage:
        facet = CompanyReferenceFacet(spark, tickers=['AAPL', 'MSFT'])
        df = facet.normalize(raw_data)
    """

    name = "company_reference"

    # Company-specific fields from OVERVIEW
    FINAL_COLUMNS = [
        ("ticker", "string"),           # Primary trading symbol
        ("cik", "string"),              # SEC Central Index Key (10 digits)
        ("company_name", "string"),     # Company name
        ("sector", "string"),           # GICS Sector
        ("industry", "string"),         # GICS Industry
        ("description", "string"),      # Business description
        ("exchange_code", "string"),    # Primary exchange
        ("country", "string"),          # Country of incorporation
        ("currency", "string"),         # Reporting currency
        ("fiscal_year_end", "string"),  # Fiscal year end month
        ("shares_outstanding", "long"), # Shares outstanding
        ("market_cap", "double"),       # Market capitalization
        ("pe_ratio", "double"),         # Price to earnings ratio
        ("peg_ratio", "double"),        # PEG ratio
        ("book_value", "double"),       # Book value per share
        ("dividend_per_share", "double"),  # Dividend per share
        ("dividend_yield", "double"),   # Dividend yield
        ("eps", "double"),              # Earnings per share
        ("ebitda", "double"),           # EBITDA
        ("revenue_ttm", "double"),      # Trailing 12 month revenue
        ("profit_margin", "double"),    # Profit margin
        ("is_active", "boolean"),       # Currently active
        ("snapshot_dt", "string"),      # Ingestion date
    ]

    def __init__(self, spark, *, tickers: List[str]):
        """
        Initialize company reference facet.

        Args:
            spark: SparkSession
            tickers: List of ticker symbols to process
        """
        super().__init__(spark, tickers=tickers)

    def _get_output_schema(self):
        """Get the output schema for company reference data."""
        return StructType([
            StructField("ticker", StringType(), True),
            StructField("cik", StringType(), True),
            StructField("company_name", StringType(), True),
            StructField("sector", StringType(), True),
            StructField("industry", StringType(), True),
            StructField("description", StringType(), True),
            StructField("exchange_code", StringType(), True),
            StructField("country", StringType(), True),
            StructField("currency", StringType(), True),
            StructField("fiscal_year_end", StringType(), True),
            StructField("shares_outstanding", LongType(), True),
            StructField("market_cap", DoubleType(), True),
            StructField("pe_ratio", DoubleType(), True),
            StructField("peg_ratio", DoubleType(), True),
            StructField("book_value", DoubleType(), True),
            StructField("dividend_per_share", DoubleType(), True),
            StructField("dividend_yield", DoubleType(), True),
            StructField("eps", DoubleType(), True),
            StructField("ebitda", DoubleType(), True),
            StructField("revenue_ttm", DoubleType(), True),
            StructField("profit_margin", DoubleType(), True),
            StructField("is_active", BooleanType(), True),
            StructField("snapshot_dt", StringType(), True),
        ])

    def postprocess(self, df):
        """
        Transform Alpha Vantage OVERVIEW response to company reference schema.

        Only extracts company-specific fields. Securities-specific fields
        (like asset_type, 52-week high/low) stay in securities_reference.
        """
        # Convert to pandas for transformation
        pdf = df.toPandas()

        # Filter out error responses
        if 'Error Message' in pdf.columns:
            pdf = pdf[pdf['Error Message'].isna()]

        # Remove rows without ticker or CIK
        pdf = pdf[pdf['Symbol'].notna()].copy()

        if pdf.empty:
            return self.spark.createDataFrame([], schema=self._get_output_schema())

        # Helper for safe CIK extraction (pad to 10 digits)
        def extract_cik(x):
            if pd.isna(x) or str(x) == 'None' or str(x) == '':
                return None
            try:
                return str(int(x)).zfill(10)
            except (ValueError, TypeError):
                return None

        # Build result DataFrame with company-specific fields
        result = pd.DataFrame({
            'ticker': pdf['Symbol'],
            'cik': pdf.get('CIK').apply(extract_cik),
            'company_name': pdf.get('Name'),
            'sector': pdf.get('Sector'),
            'industry': pdf.get('Industry'),
            'description': pdf.get('Description'),
            'exchange_code': pdf.get('Exchange'),
            'country': pdf.get('Country', 'US').fillna('US'),
            'currency': pdf.get('Currency', 'USD').fillna('USD'),
            'fiscal_year_end': pdf.get('FiscalYearEnd'),
            'shares_outstanding': pd.to_numeric(pdf.get('SharesOutstanding'), errors='coerce').astype('Int64'),
            'market_cap': pd.to_numeric(pdf.get('MarketCapitalization'), errors='coerce').astype('float64'),
            'pe_ratio': pd.to_numeric(pdf.get('PERatio'), errors='coerce').astype('float64'),
            'peg_ratio': pd.to_numeric(pdf.get('PEGRatio'), errors='coerce').astype('float64'),
            'book_value': pd.to_numeric(pdf.get('BookValue'), errors='coerce').astype('float64'),
            'dividend_per_share': pd.to_numeric(pdf.get('DividendPerShare'), errors='coerce').astype('float64'),
            'dividend_yield': pd.to_numeric(pdf.get('DividendYield'), errors='coerce').astype('float64'),
            'eps': pd.to_numeric(pdf.get('EPS'), errors='coerce').astype('float64'),
            'ebitda': pd.to_numeric(pdf.get('EBITDA'), errors='coerce').astype('float64'),
            'revenue_ttm': pd.to_numeric(pdf.get('RevenueTTM'), errors='coerce').astype('float64'),
            'profit_margin': pd.to_numeric(pdf.get('ProfitMargin'), errors='coerce').astype('float64'),
            'is_active': True,
            'snapshot_dt': datetime.now().strftime('%Y-%m-%d'),
        })

        # Only keep rows with CIK (companies we can actually track)
        result = result[result['cik'].notna()].copy()

        # Deduplicate by ticker
        result = result.drop_duplicates(subset=['ticker'])

        return self.spark.createDataFrame(result, schema=self._get_output_schema())

    def validate(self, df):
        """Validate company reference data."""
        from pyspark.sql.functions import col

        # Check for null tickers
        null_count = df.filter(col("ticker").isNull()).count()
        if null_count > 0:
            raise ValueError(f"Found {null_count} rows with null ticker")

        # Check for null CIK (required for company table)
        null_cik = df.filter(col("cik").isNull()).count()
        if null_cik > 0:
            print(f"Warning: Found {null_cik} rows with null CIK (these will be filtered)")

        return df
