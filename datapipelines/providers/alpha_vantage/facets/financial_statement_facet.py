"""
Generic Financial Statement Facet - Transform Alpha Vantage financial statements to normalized schema.

v2.7: Fully markdown-driven - no endpoint-specific code needed.
Reads all configuration from endpoint markdown frontmatter:
- facet_config.response_arrays: Which arrays to extract and their report_type values
- facet_config.fixed_fields: Fields to extract from response root or report
- schema: Field mappings, types, and coercion rules
- computed_fields: Expressions for derived fields (e.g., free_cash_flow)

This facet can handle income_statement, balance_sheet, cash_flow, and earnings
without any code changes - just update the endpoint markdown.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Any, Optional

from datapipelines.providers.alpha_vantage.facets.alpha_vantage_base_facet import (
    AlphaVantageFacet
)
from config.markdown_loader import get_markdown_loader
from utils.repo import get_repo_root

try:
    from pyspark.sql import DataFrame, functions as F
    HAS_SPARK = True
except ImportError:
    HAS_SPARK = False
    DataFrame = None


class FinancialStatementFacet(AlphaVantageFacet):
    """
    Generic facet for Alpha Vantage financial statement endpoints.

    Fully driven by endpoint markdown configuration - no endpoint-specific code.

    Configuration (from endpoint markdown frontmatter):
        facet_config:
          response_arrays:
            annualReports: annual     # array_name: report_type_value
            quarterlyReports: quarterly
          fixed_fields:
            ticker: symbol            # output_name: source_field
            fiscal_date_ending: fiscalDateEnding

    Usage:
        facet = FinancialStatementFacet(spark, endpoint_id="income_statement")
        df = facet.normalize(api_response)
    """

    def __init__(self, spark, endpoint_id: str, ticker: str = None, **kwargs):
        """
        Initialize with endpoint_id to load config from markdown.

        Args:
            spark: SparkSession
            endpoint_id: Endpoint identifier (e.g., "income_statement", "balance_sheet")
            ticker: Optional ticker symbol (fallback if not in response)
        """
        # Set ENDPOINT_ID before calling super().__init__() so schema loading works
        self.ENDPOINT_ID = endpoint_id
        super().__init__(spark, **kwargs)
        self.ticker = ticker
        self._facet_config = None

    def _get_facet_config(self) -> Dict[str, Any]:
        """Load facet_config from endpoint markdown."""
        if self._facet_config is not None:
            return self._facet_config

        try:
            repo_root = get_repo_root()
            loader = get_markdown_loader(repo_root)
            config = loader.get_endpoint_config(self.ENDPOINT_ID)
            self._facet_config = config.get('facet_config', {})
        except Exception:
            self._facet_config = {}

        return self._facet_config

    def normalize(self, raw_response: dict) -> DataFrame:
        """
        Normalize financial statement response using markdown config.

        Args:
            raw_response: API response (e.g., with annualReports and quarterlyReports)

        Returns:
            DataFrame with normalized data
        """
        if not raw_response:
            return self._empty_df()

        facet_config = self._get_facet_config()
        response_arrays = facet_config.get('response_arrays', {})
        fixed_fields = facet_config.get('fixed_fields', {})

        if not response_arrays:
            # Fallback: try common array patterns
            if 'annualReports' in raw_response or 'quarterlyReports' in raw_response:
                response_arrays = {'annualReports': 'annual', 'quarterlyReports': 'quarterly'}
            elif 'annualEarnings' in raw_response or 'quarterlyEarnings' in raw_response:
                response_arrays = {'annualEarnings': 'annual', 'quarterlyEarnings': 'quarterly'}

        # Get ticker from response root
        ticker = raw_response.get('symbol', self.ticker)

        all_reports = []
        for array_name, report_type in response_arrays.items():
            for report in raw_response.get(array_name, []):
                all_reports.append(
                    self._transform_report(report, ticker, report_type, fixed_fields)
                )

        if not all_reports:
            return self._empty_df()

        # Create DataFrame - let Spark infer types initially
        df = self.spark.createDataFrame(all_reports, samplingRatio=1.0)
        df = self.postprocess(df)

        # Apply type coercion from markdown schema {coerce: type} options
        spark_casts = self.get_spark_casts()
        if spark_casts:
            for col_name, cast_type in spark_casts.items():
                if col_name in df.columns:
                    df = df.withColumn(col_name, F.col(col_name).cast(cast_type))

        # Apply computed fields from markdown schema
        df = self._apply_computed_fields(df)

        # Apply final columns from markdown
        final_cols = self.get_final_columns()
        if final_cols:
            self.FINAL_COLUMNS = final_cols
        df = self._apply_final_columns(df)

        return df

    def _transform_report(
        self,
        report: dict,
        ticker: str,
        report_type: str,
        fixed_fields: Dict[str, str]
    ) -> dict:
        """
        Transform a single report using markdown schema mappings.

        Type coercion is NOT done here - handled by Spark casts from markdown.
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
            'report_type': report_type,
        }

        # Add fixed fields from config
        for output_name, source_field in fixed_fields.items():
            if source_field == 'symbol':
                result[output_name] = ticker
            else:
                result[output_name] = clean_value(report.get(source_field))

        # Map all other fields from API response using markdown schema
        for api_field, output_field in mappings.items():
            # Skip already handled fields
            if output_field in result:
                continue
            if api_field in fixed_fields.values():
                continue

            # Get value and clean (but don't coerce type - let Spark do that)
            val = report.get(api_field)
            result[output_field] = clean_value(val)

        # Add metadata
        result["ingestion_timestamp"] = now
        result["snapshot_date"] = now.date()

        return result

    def _apply_computed_fields(self, df: DataFrame) -> DataFrame:
        """Apply computed fields from markdown schema."""
        computed_fields = self.get_computed_fields()

        for field in computed_fields:
            name = field['name']
            expr = field.get('expr')
            if expr and name not in df.columns:
                try:
                    df = df.withColumn(name, F.expr(expr))
                except Exception:
                    # If expression fails, add null column
                    field_type = field.get('type', 'double')
                    df = df.withColumn(name, F.lit(None).cast(field_type))

        return df

    def postprocess(self, df: DataFrame) -> DataFrame:
        """Apply any post-processing transformations."""
        # Convert string dates to date type
        md_info = self._load_markdown_schema()
        schema = md_info.get('schema', [])

        for field in schema:
            name = field['name']
            field_type = field.get('type', 'string')
            source = field.get('source', '')

            # Date fields from API need conversion
            if field_type == 'date' and source and not source.startswith('_'):
                if name in df.columns:
                    df = df.withColumn(
                        name,
                        F.to_date(F.col(name), "yyyy-MM-dd")
                    )

        return df

    def _empty_df(self) -> DataFrame:
        """Create empty DataFrame with schema from markdown."""
        final_cols = self.get_final_columns()
        if final_cols:
            self.FINAL_COLUMNS = final_cols
        return super()._empty_df()
