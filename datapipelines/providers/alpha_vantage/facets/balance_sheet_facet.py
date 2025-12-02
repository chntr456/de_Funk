"""
Balance Sheet Facet - Transform Alpha Vantage BALANCE_SHEET to normalized schema.

Handles both annual and quarterly reports from the API response.
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


class BalanceSheetFacet(Facet):
    """
    Transform Alpha Vantage balance sheet data to normalized schema.

    API returns:
    {
        "symbol": "AAPL",
        "annualReports": [...],
        "quarterlyReports": [...]
    }

    Each report contains assets, liabilities, equity items.
    """

    # Numeric fields that need type coercion
    NUMERIC_COERCE: Dict[str, str] = {
        "totalAssets": "long",
        "totalCurrentAssets": "long",
        "cashAndCashEquivalentsAtCarryingValue": "long",
        "cashAndShortTermInvestments": "long",
        "inventory": "long",
        "currentNetReceivables": "long",
        "totalNonCurrentAssets": "long",
        "propertyPlantEquipment": "long",
        "accumulatedDepreciationAmortizationPPE": "long",
        "intangibleAssets": "long",
        "intangibleAssetsExcludingGoodwill": "long",
        "goodwill": "long",
        "investments": "long",
        "longTermInvestments": "long",
        "shortTermInvestments": "long",
        "otherCurrentAssets": "long",
        "otherNonCurrentAssets": "long",
        "totalLiabilities": "long",
        "totalCurrentLiabilities": "long",
        "currentAccountsPayable": "long",
        "deferredRevenue": "long",
        "currentDebt": "long",
        "shortTermDebt": "long",
        "totalNonCurrentLiabilities": "long",
        "capitalLeaseObligations": "long",
        "longTermDebt": "long",
        "currentLongTermDebt": "long",
        "longTermDebtNoncurrent": "long",
        "shortLongTermDebtTotal": "long",
        "otherCurrentLiabilities": "long",
        "otherNonCurrentLiabilities": "long",
        "totalShareholderEquity": "long",
        "treasuryStock": "long",
        "retainedEarnings": "long",
        "commonStock": "long",
        "commonStockSharesOutstanding": "long",
    }

    # Final schema columns
    FINAL_COLUMNS: Optional[List[Tuple[str, str]]] = [
        ("ticker", "string"),
        ("fiscal_date_ending", "date"),
        ("report_type", "string"),
        ("reported_currency", "string"),
        # Assets
        ("total_assets", "long"),
        ("total_current_assets", "long"),
        ("cash_and_equivalents", "long"),
        ("cash_and_short_term_investments", "long"),
        ("inventory", "long"),
        ("current_net_receivables", "long"),
        ("total_non_current_assets", "long"),
        ("property_plant_equipment", "long"),
        ("accumulated_depreciation_ppe", "long"),
        ("intangible_assets", "long"),
        ("intangible_assets_ex_goodwill", "long"),
        ("goodwill", "long"),
        ("investments", "long"),
        ("long_term_investments", "long"),
        ("short_term_investments", "long"),
        ("other_current_assets", "long"),
        ("other_non_current_assets", "long"),
        # Liabilities
        ("total_liabilities", "long"),
        ("total_current_liabilities", "long"),
        ("current_accounts_payable", "long"),
        ("deferred_revenue", "long"),
        ("current_debt", "long"),
        ("short_term_debt", "long"),
        ("total_non_current_liabilities", "long"),
        ("capital_lease_obligations", "long"),
        ("long_term_debt", "long"),
        ("current_long_term_debt", "long"),
        ("long_term_debt_noncurrent", "long"),
        ("total_debt", "long"),
        ("other_current_liabilities", "long"),
        ("other_non_current_liabilities", "long"),
        # Equity
        ("total_shareholder_equity", "long"),
        ("treasury_stock", "long"),
        ("retained_earnings", "long"),
        ("common_stock", "long"),
        ("shares_outstanding", "long"),
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
            StructType, StructField, StringType, LongType,
            DateType, TimestampType
        )

        type_map = {
            "string": StringType(),
            "long": LongType(),
            "date": DateType(),
            "timestamp": TimestampType(),
        }

        fields = []
        for col_name, col_type in self.FINAL_COLUMNS:
            if col_name == "fiscal_date_ending":
                fields.append(StructField(col_name, StringType(), True))
            elif col_name == "snapshot_date":
                fields.append(StructField(col_name, DateType(), True))
            else:
                spark_type = type_map.get(col_type, StringType())
                fields.append(StructField(col_name, spark_type, True))

        return StructType(fields)

    def normalize(self, raw_response: dict) -> DataFrame:
        """
        Normalize balance sheet response.

        Args:
            raw_response: API response with annualReports and quarterlyReports

        Returns:
            DataFrame with normalized balance sheet data
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
        """Transform a single report to normalized schema."""

        def safe_long(val):
            """Convert to long, handling None and 'None' strings."""
            if val is None or val == "None" or val == "":
                return None
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return None

        now = datetime.now()

        return {
            "ticker": ticker,
            "fiscal_date_ending": report.get("fiscalDateEnding"),
            "report_type": report_type,
            "reported_currency": report.get("reportedCurrency"),
            # Assets
            "total_assets": safe_long(report.get("totalAssets")),
            "total_current_assets": safe_long(report.get("totalCurrentAssets")),
            "cash_and_equivalents": safe_long(report.get("cashAndCashEquivalentsAtCarryingValue")),
            "cash_and_short_term_investments": safe_long(report.get("cashAndShortTermInvestments")),
            "inventory": safe_long(report.get("inventory")),
            "current_net_receivables": safe_long(report.get("currentNetReceivables")),
            "total_non_current_assets": safe_long(report.get("totalNonCurrentAssets")),
            "property_plant_equipment": safe_long(report.get("propertyPlantEquipment")),
            "accumulated_depreciation_ppe": safe_long(report.get("accumulatedDepreciationAmortizationPPE")),
            "intangible_assets": safe_long(report.get("intangibleAssets")),
            "intangible_assets_ex_goodwill": safe_long(report.get("intangibleAssetsExcludingGoodwill")),
            "goodwill": safe_long(report.get("goodwill")),
            "investments": safe_long(report.get("investments")),
            "long_term_investments": safe_long(report.get("longTermInvestments")),
            "short_term_investments": safe_long(report.get("shortTermInvestments")),
            "other_current_assets": safe_long(report.get("otherCurrentAssets")),
            "other_non_current_assets": safe_long(report.get("otherNonCurrentAssets")),
            # Liabilities
            "total_liabilities": safe_long(report.get("totalLiabilities")),
            "total_current_liabilities": safe_long(report.get("totalCurrentLiabilities")),
            "current_accounts_payable": safe_long(report.get("currentAccountsPayable")),
            "deferred_revenue": safe_long(report.get("deferredRevenue")),
            "current_debt": safe_long(report.get("currentDebt")),
            "short_term_debt": safe_long(report.get("shortTermDebt")),
            "total_non_current_liabilities": safe_long(report.get("totalNonCurrentLiabilities")),
            "capital_lease_obligations": safe_long(report.get("capitalLeaseObligations")),
            "long_term_debt": safe_long(report.get("longTermDebt")),
            "current_long_term_debt": safe_long(report.get("currentLongTermDebt")),
            "long_term_debt_noncurrent": safe_long(report.get("longTermDebtNoncurrent")),
            "total_debt": safe_long(report.get("shortLongTermDebtTotal")),
            "other_current_liabilities": safe_long(report.get("otherCurrentLiabilities")),
            "other_non_current_liabilities": safe_long(report.get("otherNonCurrentLiabilities")),
            # Equity
            "total_shareholder_equity": safe_long(report.get("totalShareholderEquity")),
            "treasury_stock": safe_long(report.get("treasuryStock")),
            "retained_earnings": safe_long(report.get("retainedEarnings")),
            "common_stock": safe_long(report.get("commonStock")),
            "shares_outstanding": safe_long(report.get("commonStockSharesOutstanding")),
            # Metadata
            "ingestion_timestamp": now,
            "snapshot_date": now.date(),
        }

    def postprocess(self, df: DataFrame) -> DataFrame:
        """Apply any post-processing transformations."""
        # Convert string dates to date type
        if "fiscal_date_ending" in df.columns:
            df = df.withColumn(
                "fiscal_date_ending",
                F.to_date(F.col("fiscal_date_ending"), "yyyy-MM-dd")
            )
        return df
