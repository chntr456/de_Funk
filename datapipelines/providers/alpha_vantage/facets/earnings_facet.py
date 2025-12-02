"""
Earnings Facet - Transform Alpha Vantage EARNINGS to normalized schema.

Handles both annual and quarterly earnings data from the API response.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from datetime import datetime

from datapipelines.facets.base_facet import Facet

try:
    from pyspark.sql import DataFrame, functions as F
    HAS_SPARK = True
except ImportError:
    HAS_SPARK = False
    DataFrame = None


class EarningsFacet(Facet):
    """
    Transform Alpha Vantage earnings data to normalized schema.

    API returns:
    {
        "symbol": "AAPL",
        "annualEarnings": [...],
        "quarterlyEarnings": [...]
    }

    Each report contains EPS actual, estimate, and surprise percentage.
    """

    # Numeric fields that need type coercion
    NUMERIC_COERCE: Dict[str, str] = {
        "reportedEPS": "double",
        "estimatedEPS": "double",
        "surprise": "double",
        "surprisePercentage": "double",
    }

    # Final schema columns
    FINAL_COLUMNS: Optional[List[Tuple[str, str]]] = [
        ("ticker", "string"),
        ("fiscal_date_ending", "date"),
        ("report_type", "string"),
        ("reported_date", "date"),  # When earnings were announced
        ("reported_eps", "double"),
        ("estimated_eps", "double"),
        ("surprise", "double"),
        ("surprise_percentage", "double"),
        # Calculated fields
        ("beat_estimate", "boolean"),  # Did actual beat estimate?
        # Metadata
        ("ingestion_timestamp", "timestamp"),
        ("snapshot_date", "date"),
    ]

    def __init__(self, spark, ticker: str = None, **kwargs):
        super().__init__(spark, **kwargs)
        self.ticker = ticker

    def get_input_schema(self):
        """Get explicit schema to avoid CANNOT_DETERMINE_TYPE errors."""
        from pyspark.sql.types import (
            StructType, StructField, StringType, LongType, DoubleType,
            DateType, TimestampType, BooleanType
        )

        type_map = {
            "string": StringType(),
            "long": LongType(),
            "double": DoubleType(),
            "date": DateType(),
            "timestamp": TimestampType(),
            "boolean": BooleanType(),
        }

        fields = []
        for col_name, col_type in self.FINAL_COLUMNS:
            if col_name in ("fiscal_date_ending", "reported_date"):
                fields.append(StructField(col_name, StringType(), True))
            elif col_name == "snapshot_date":
                fields.append(StructField(col_name, DateType(), True))
            else:
                spark_type = type_map.get(col_type, StringType())
                fields.append(StructField(col_name, spark_type, True))

        return StructType(fields)

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

        # Coerce numeric types
        all_reports = self._coerce_rows(all_reports)

        # Create DataFrame with explicit schema
        schema = self.get_input_schema()
        df = self.spark.createDataFrame(all_reports, schema=schema)
        df = self.postprocess(df)
        df = self._apply_final_casts(df)
        df = self._apply_final_columns(df)

        return df

    def _transform_report(self, report: dict, ticker: str, report_type: str) -> dict:
        """Transform a single earnings report to normalized schema."""

        def safe_double(val):
            """Convert to double, handling None and 'None' strings."""
            if val is None or val == "None" or val == "":
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        now = datetime.now()

        reported_eps = safe_double(report.get("reportedEPS"))
        estimated_eps = safe_double(report.get("estimatedEPS"))

        # Calculate if beat estimate
        if reported_eps is not None and estimated_eps is not None:
            beat_estimate = reported_eps > estimated_eps
        else:
            beat_estimate = None

        return {
            "ticker": ticker,
            "fiscal_date_ending": report.get("fiscalDateEnding"),
            "report_type": report_type,
            "reported_date": report.get("reportedDate"),
            "reported_eps": reported_eps,
            "estimated_eps": estimated_eps,
            "surprise": safe_double(report.get("surprise")),
            "surprise_percentage": safe_double(report.get("surprisePercentage")),
            "beat_estimate": beat_estimate,
            "ingestion_timestamp": now,
            "snapshot_date": now.date(),
        }

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
