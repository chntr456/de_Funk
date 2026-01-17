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

    Schema loaded from: Data Sources/Endpoints/Alpha Vantage/Fundamentals/Earnings.md

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

        # Create DataFrame - start with string types for numeric fields
        # (API returns all values as strings)
        df = self.spark.createDataFrame(all_reports, samplingRatio=1.0)
        df = self.postprocess(df)

        # Apply type coercion from markdown schema {coerce: type} options
        # This is the single source of truth for Bronze types
        spark_casts = self.get_spark_casts()
        if spark_casts:
            for col_name, cast_type in spark_casts.items():
                if col_name in df.columns:
                    df = df.withColumn(col_name, F.col(col_name).cast(cast_type))

        # Compute beat_estimate after type casting
        # beat_estimate = reported_eps > estimated_eps
        if "reported_eps" in df.columns and "estimated_eps" in df.columns:
            df = df.withColumn(
                "beat_estimate",
                F.col("reported_eps") > F.col("estimated_eps")
            )

        # Apply final columns from markdown
        final_cols = self.get_final_columns()
        if final_cols:
            self.FINAL_COLUMNS = final_cols
        df = self._apply_final_columns(df)

        return df

    def _transform_report(self, report: dict, ticker: str, report_type: str) -> dict:
        """
        Transform a single earnings report using markdown schema mappings.

        Type coercion is NOT done here - it's handled by Spark casts
        from the endpoint markdown frontmatter {coerce: type} options.
        This keeps Python code simple and markdown as single source of truth.
        """
        def clean_value(val):
            """Clean string value, converting 'None'/empty to None."""
            if val is None or val == "None" or val == "":
                return None
            return val

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
        # Pass raw string values - Spark will cast based on markdown schema
        for api_field, output_field in mappings.items():
            # Skip already handled fields
            if output_field in result:
                continue
            if api_field in ('symbol', 'fiscalDateEnding', 'reportedDate'):
                continue

            # Get value and clean (but don't coerce type - let Spark do that)
            val = report.get(api_field)
            result[output_field] = clean_value(val)

        # Note: beat_estimate is computed in Spark after type casting

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
