"""
Income Statement Facet - Transform Alpha Vantage INCOME_STATEMENT to normalized schema.

Handles both annual and quarterly reports from the API response.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from datetime import datetime

from datapipelines.base.facet import Facet

try:
    from pyspark.sql import DataFrame, functions as F
    HAS_SPARK = True
except ImportError:
    HAS_SPARK = False
    DataFrame = None


class IncomeStatementFacet(Facet):
    """
    Transform Alpha Vantage income statement data to normalized schema.

    API returns:
    {
        "symbol": "AAPL",
        "annualReports": [...],
        "quarterlyReports": [...]
    }

    Each report contains revenue, expenses, net income, EPS, etc.
    """

    # Numeric fields that need type coercion
    NUMERIC_COERCE: Dict[str, str] = {
        "grossProfit": "long",
        "totalRevenue": "long",
        "costOfRevenue": "long",
        "costofGoodsAndServicesSold": "long",
        "operatingIncome": "long",
        "sellingGeneralAndAdministrative": "long",
        "researchAndDevelopment": "long",
        "operatingExpenses": "long",
        "investmentIncomeNet": "long",
        "netInterestIncome": "long",
        "interestIncome": "long",
        "interestExpense": "long",
        "nonInterestIncome": "long",
        "otherNonOperatingIncome": "long",
        "depreciation": "long",
        "depreciationAndAmortization": "long",
        "incomeBeforeTax": "long",
        "incomeTaxExpense": "long",
        "interestAndDebtExpense": "long",
        "netIncomeFromContinuingOperations": "long",
        "comprehensiveIncomeNetOfTax": "long",
        "ebit": "long",
        "ebitda": "long",
        "netIncome": "long",
    }

    # Final schema columns
    FINAL_COLUMNS: Optional[List[Tuple[str, str]]] = [
        ("ticker", "string"),
        ("fiscal_date_ending", "date"),
        ("report_type", "string"),  # 'annual' or 'quarterly'
        ("reported_currency", "string"),
        ("gross_profit", "long"),
        ("total_revenue", "long"),
        ("cost_of_revenue", "long"),
        ("cost_of_goods_sold", "long"),
        ("operating_income", "long"),
        ("sg_and_a", "long"),
        ("research_and_development", "long"),
        ("operating_expenses", "long"),
        ("investment_income_net", "long"),
        ("net_interest_income", "long"),
        ("interest_income", "long"),
        ("interest_expense", "long"),
        ("non_interest_income", "long"),
        ("other_non_operating_income", "long"),
        ("depreciation", "long"),
        ("depreciation_and_amortization", "long"),
        ("income_before_tax", "long"),
        ("income_tax_expense", "long"),
        ("interest_and_debt_expense", "long"),
        ("net_income_from_continuing_ops", "long"),
        ("comprehensive_income_net_of_tax", "long"),
        ("ebit", "long"),
        ("ebitda", "long"),
        ("net_income", "long"),
        ("ingestion_timestamp", "timestamp"),
        ("snapshot_date", "date"),
    ]

    def __init__(self, spark, ticker: str = None, **kwargs):
        super().__init__(spark, **kwargs)
        self.ticker = ticker

    def get_input_schema(self):
        """
        Get explicit schema to avoid CANNOT_DETERMINE_TYPE errors.

        When all values in a column are NULL, Spark can't infer the type.
        This provides explicit types for all columns.
        """
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
            # For date fields that come in as strings initially
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
        Normalize income statement response.

        Args:
            raw_response: API response with annualReports and quarterlyReports

        Returns:
            DataFrame with normalized income statement data
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

        # Create DataFrame with explicit schema to avoid CANNOT_DETERMINE_TYPE errors
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
            "gross_profit": safe_long(report.get("grossProfit")),
            "total_revenue": safe_long(report.get("totalRevenue")),
            "cost_of_revenue": safe_long(report.get("costOfRevenue")),
            "cost_of_goods_sold": safe_long(report.get("costofGoodsAndServicesSold")),
            "operating_income": safe_long(report.get("operatingIncome")),
            "sg_and_a": safe_long(report.get("sellingGeneralAndAdministrative")),
            "research_and_development": safe_long(report.get("researchAndDevelopment")),
            "operating_expenses": safe_long(report.get("operatingExpenses")),
            "investment_income_net": safe_long(report.get("investmentIncomeNet")),
            "net_interest_income": safe_long(report.get("netInterestIncome")),
            "interest_income": safe_long(report.get("interestIncome")),
            "interest_expense": safe_long(report.get("interestExpense")),
            "non_interest_income": safe_long(report.get("nonInterestIncome")),
            "other_non_operating_income": safe_long(report.get("otherNonOperatingIncome")),
            "depreciation": safe_long(report.get("depreciation")),
            "depreciation_and_amortization": safe_long(report.get("depreciationAndAmortization")),
            "income_before_tax": safe_long(report.get("incomeBeforeTax")),
            "income_tax_expense": safe_long(report.get("incomeTaxExpense")),
            "interest_and_debt_expense": safe_long(report.get("interestAndDebtExpense")),
            "net_income_from_continuing_ops": safe_long(report.get("netIncomeFromContinuingOperations")),
            "comprehensive_income_net_of_tax": safe_long(report.get("comprehensiveIncomeNetOfTax")),
            "ebit": safe_long(report.get("ebit")),
            "ebitda": safe_long(report.get("ebitda")),
            "net_income": safe_long(report.get("netIncome")),
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
