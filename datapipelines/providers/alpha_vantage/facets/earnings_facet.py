"""
Earnings Facet - Transform Alpha Vantage EARNINGS to normalized schema.

v2.6: Schema-driven from markdown endpoint file.
Handles both annual and quarterly earnings data from the API response.
"""
from __future__ import annotations

from datetime import datetime

from datapipelines.providers.alpha_vantage.facets.alpha_vantage_base_facet import (
    AlphaVantageFacet
)

try:
    from pyspark.sql import DataFrame, functions as F
    HAS_SPARK = True
except ImportError:
    HAS_SPARK = False
    DataFrame = None


class EarningsFacet(AlphaVantageFacet):
    """
    Transform Alpha Vantage earnings data to normalized schema.

    Schema loaded from: Documents/Data Sources/Endpoints/Alpha Vantage/Fundamentals/Earnings.md

    API returns:
    {
        "symbol": "AAPL",
        "annualEarnings": [...],
        "quarterlyEarnings": [...]
    }

    Each report contains EPS actual, estimate, and surprise percentage.

    Note: beat_estimate is a computed field (reported_eps > estimated_eps)
    """

    # Load schema from markdown endpoint file (v2.6)
    ENDPOINT_ID = "earnings"

    def __init__(self, spark, ticker: str = None, **kwargs):
        super().__init__(spark, **kwargs)
        self.ticker = ticker

    def normalize(self, raw_response: dict) -> DataFrame:
        """
        Normalize earnings response.

        Args:
            raw_response: API response with annualEarnings and quarterlyEarnings

        Returns:
            DataFrame with normalized earnings data
        """
        if not raw_response:
            return self._empty_df()

        ticker = raw_response.get("symbol", self.ticker)
        all_reports = []

        # Process annual earnings
        for report in raw_response.get("annualEarnings", []):
            all_reports.append(self._transform_report(report, ticker, "annual"))

        # Process quarterly earnings
        for report in raw_response.get("quarterlyEarnings", []):
            all_reports.append(self._transform_report(report, ticker, "quarterly"))

        if not all_reports:
            return self._empty_df()

        # Create DataFrame with explicit schema from markdown
        schema = self.get_input_schema()
        df = self.spark.createDataFrame(all_reports, schema=schema)
        df = self.postprocess(df)
        df = self._apply_final_casts(df)

        # Apply final columns from markdown
        final_cols = self.get_final_columns()
        if final_cols:
            self.FINAL_COLUMNS = final_cols
        df = self._apply_final_columns(df)

        return df

    def _transform_report(self, report: dict, ticker: str, report_type: str) -> dict:
        """Transform a single earnings report using markdown schema mappings."""

        def safe_double(val):
            """Convert to double, handling None and 'None' strings."""
            if val is None or val == "None" or val == "":
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        now = datetime.now()

        # Get field mappings from markdown schema (source -> output)
        mappings = self.get_field_mappings()

        # Start with fixed fields
        result = {
            "ticker": ticker,
            "fiscal_date_ending": report.get("fiscalDateEnding"),
            "report_type": report_type,
            "reported_date": report.get("reportedDate"),
        }

        # Map all other fields from API response using markdown schema
        for api_field, output_field in mappings.items():
            # Skip already handled fields
            if output_field in result:
                continue
            if api_field in ('symbol', 'fiscalDateEnding', 'reportedDate'):
                continue

            # Get value and apply coercion for double fields
            val = report.get(api_field)
            result[output_field] = safe_double(val)

        # Compute beat_estimate = reported_eps > estimated_eps
        # Note: This is a computed field marked in markdown schema
        reported_eps = result.get('reported_eps')
        estimated_eps = result.get('estimated_eps')
        if reported_eps is not None and estimated_eps is not None:
            result['beat_estimate'] = reported_eps > estimated_eps
        else:
            result['beat_estimate'] = None

        # Add metadata
        result["ingestion_timestamp"] = now
        result["snapshot_date"] = now.date()

        return result

    def postprocess(self, df: DataFrame) -> DataFrame:
        """Apply any post-processing transformations."""
        # Convert string dates to date type
        for date_col in ["fiscal_date_ending", "reported_date"]:
            if date_col in df.columns:
                df = df.withColumn(
                    date_col,
                    F.to_date(F.col(date_col), "yyyy-MM-dd")
                )
        return df

    def _empty_df(self) -> DataFrame:
        """Create empty DataFrame with schema from markdown."""
        final_cols = self.get_final_columns()
        if final_cols:
            self.FINAL_COLUMNS = final_cols
        return super()._empty_df()
