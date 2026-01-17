"""
Cash Flow Facet - Transform Alpha Vantage CASH_FLOW to normalized schema.

v2.6: Schema-driven from markdown endpoint file.
Handles both annual and quarterly reports from the API response.
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


class CashFlowFacet(AlphaVantageFacet):
    """
    Transform Alpha Vantage cash flow statement data to normalized schema.

    Schema loaded from: Data Sources/Endpoints/Alpha Vantage/Fundamentals/Cash Flow.md

    API returns:
    {
        "symbol": "AAPL",
        "annualReports": [...],
        "quarterlyReports": [...]
    }

    Each report contains operating, investing, and financing cash flows.

    Note: free_cash_flow is a computed field (operating_cashflow - abs(capital_expenditures))
    """

    # Load schema from markdown endpoint file (v2.6)
    ENDPOINT_ID = "cash_flow"

    def __init__(self, spark, ticker: str = None, **kwargs):
        super().__init__(spark, **kwargs)
        self.ticker = ticker

    def normalize(self, raw_response: dict) -> DataFrame:
        """
        Normalize cash flow response.

        Args:
            raw_response: API response with annualReports and quarterlyReports

        Returns:
            DataFrame with normalized cash flow data
        """
        if not raw_response:
            return self._empty_df()

        ticker = raw_response.get("symbol", self.ticker)
        all_reports = []

        # Process annual reports
        for report in raw_response.get("annualReports", []):
            all_reports.append(self._transform_report(report, ticker, "annual"))

        # Process quarterly reports
        for report in raw_response.get("quarterlyReports", []):
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

        # Compute free_cash_flow after type casting
        # free_cash_flow = operating_cashflow - abs(capital_expenditures)
        if "operating_cashflow" in df.columns and "capital_expenditures" in df.columns:
            df = df.withColumn(
                "free_cash_flow",
                F.col("operating_cashflow") - F.abs(F.coalesce(F.col("capital_expenditures"), F.lit(0)))
            )

        # Apply final columns from markdown
        final_cols = self.get_final_columns()
        if final_cols:
            self.FINAL_COLUMNS = final_cols
        df = self._apply_final_columns(df)

        return df

    def _transform_report(self, report: dict, ticker: str, report_type: str) -> dict:
        """
        Transform a single report using markdown schema mappings.

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
            "reported_currency": report.get("reportedCurrency"),
        }

        # Map all other fields from API response using markdown schema
        # Pass raw string values - Spark will cast based on markdown schema
        for api_field, output_field in mappings.items():
            # Skip already handled fields
            if output_field in result:
                continue
            if api_field in ('symbol', 'fiscalDateEnding', 'reportedCurrency'):
                continue

            # Get value and clean (but don't coerce type - let Spark do that)
            val = report.get(api_field)
            result[output_field] = clean_value(val)

        # Note: free_cash_flow is computed in Spark after type casting

        # Add metadata
        result["ingestion_timestamp"] = now
        result["snapshot_date"] = now.date()

        return result

    def postprocess(self, df: DataFrame) -> DataFrame:
        """Apply any post-processing transformations."""
        # Convert string dates to date type
        if "fiscal_date_ending" in df.columns:
            df = df.withColumn(
                "fiscal_date_ending",
                F.to_date(F.col("fiscal_date_ending"), "yyyy-MM-dd")
            )
        return df

    def _empty_df(self) -> DataFrame:
        """Create empty DataFrame with schema from markdown."""
        final_cols = self.get_final_columns()
        if final_cols:
            self.FINAL_COLUMNS = final_cols
        return super()._empty_df()
