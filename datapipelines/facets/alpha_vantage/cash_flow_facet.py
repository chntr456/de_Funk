"""
Cash Flow Facet - Transform Alpha Vantage CASH_FLOW to normalized schema.

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


class CashFlowFacet(Facet):
    """
    Transform Alpha Vantage cash flow statement data to normalized schema.

    API returns:
    {
        "symbol": "AAPL",
        "annualReports": [...],
        "quarterlyReports": [...]
    }

    Each report contains operating, investing, and financing cash flows.
    """

    # Numeric fields that need type coercion
    NUMERIC_COERCE: Dict[str, str] = {
        "operatingCashflow": "long",
        "paymentsForOperatingActivities": "long",
        "proceedsFromOperatingActivities": "long",
        "changeInOperatingLiabilities": "long",
        "changeInOperatingAssets": "long",
        "depreciationDepletionAndAmortization": "long",
        "capitalExpenditures": "long",
        "changeInReceivables": "long",
        "changeInInventory": "long",
        "profitLoss": "long",
        "cashflowFromInvestment": "long",
        "cashflowFromFinancing": "long",
        "proceedsFromRepaymentsOfShortTermDebt": "long",
        "paymentsForRepurchaseOfCommonStock": "long",
        "paymentsForRepurchaseOfEquity": "long",
        "paymentsForRepurchaseOfPreferredStock": "long",
        "dividendPayout": "long",
        "dividendPayoutCommonStock": "long",
        "dividendPayoutPreferredStock": "long",
        "proceedsFromIssuanceOfCommonStock": "long",
        "proceedsFromIssuanceOfLongTermDebtAndCapitalSecuritiesNet": "long",
        "proceedsFromIssuanceOfPreferredStock": "long",
        "proceedsFromRepurchaseOfEquity": "long",
        "proceedsFromSaleOfTreasuryStock": "long",
        "changeInCashAndCashEquivalents": "long",
        "changeInExchangeRate": "long",
        "netIncome": "long",
    }

    # Final schema columns
    FINAL_COLUMNS: Optional[List[Tuple[str, str]]] = [
        ("ticker", "string"),
        ("fiscal_date_ending", "date"),
        ("report_type", "string"),
        ("reported_currency", "string"),
        # Operating activities
        ("operating_cashflow", "long"),
        ("payments_for_operating_activities", "long"),
        ("proceeds_from_operating_activities", "long"),
        ("change_in_operating_liabilities", "long"),
        ("change_in_operating_assets", "long"),
        ("depreciation_depletion_amortization", "long"),
        ("change_in_receivables", "long"),
        ("change_in_inventory", "long"),
        ("profit_loss", "long"),
        ("net_income", "long"),
        # Investing activities
        ("cashflow_from_investment", "long"),
        ("capital_expenditures", "long"),
        # Financing activities
        ("cashflow_from_financing", "long"),
        ("proceeds_repayments_short_term_debt", "long"),
        ("payments_repurchase_common_stock", "long"),
        ("payments_repurchase_equity", "long"),
        ("payments_repurchase_preferred_stock", "long"),
        ("dividend_payout", "long"),
        ("dividend_payout_common_stock", "long"),
        ("dividend_payout_preferred_stock", "long"),
        ("proceeds_issuance_common_stock", "long"),
        ("proceeds_issuance_long_term_debt", "long"),
        ("proceeds_issuance_preferred_stock", "long"),
        ("proceeds_repurchase_equity", "long"),
        ("proceeds_sale_treasury_stock", "long"),
        # Net change
        ("change_in_cash", "long"),
        ("change_in_exchange_rate", "long"),
        # Derived: Free Cash Flow = Operating Cash Flow - CapEx
        ("free_cash_flow", "long"),
        # Metadata
        ("ingestion_timestamp", "timestamp"),
        ("snapshot_date", "date"),
    ]

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

        # Coerce numeric types
        all_reports = self._coerce_rows(all_reports)

        # Create DataFrame
        df = self.spark.createDataFrame(all_reports, samplingRatio=1.0)
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

        operating_cf = safe_long(report.get("operatingCashflow"))
        capex = safe_long(report.get("capitalExpenditures"))

        # Calculate Free Cash Flow = Operating Cash Flow - CapEx
        # CapEx is typically negative in Alpha Vantage, so we add it
        if operating_cf is not None and capex is not None:
            # If capex is positive, subtract it; if negative, add it (subtract negative)
            free_cf = operating_cf - abs(capex)
        else:
            free_cf = None

        return {
            "ticker": ticker,
            "fiscal_date_ending": report.get("fiscalDateEnding"),
            "report_type": report_type,
            "reported_currency": report.get("reportedCurrency"),
            # Operating activities
            "operating_cashflow": operating_cf,
            "payments_for_operating_activities": safe_long(report.get("paymentsForOperatingActivities")),
            "proceeds_from_operating_activities": safe_long(report.get("proceedsFromOperatingActivities")),
            "change_in_operating_liabilities": safe_long(report.get("changeInOperatingLiabilities")),
            "change_in_operating_assets": safe_long(report.get("changeInOperatingAssets")),
            "depreciation_depletion_amortization": safe_long(report.get("depreciationDepletionAndAmortization")),
            "change_in_receivables": safe_long(report.get("changeInReceivables")),
            "change_in_inventory": safe_long(report.get("changeInInventory")),
            "profit_loss": safe_long(report.get("profitLoss")),
            "net_income": safe_long(report.get("netIncome")),
            # Investing activities
            "cashflow_from_investment": safe_long(report.get("cashflowFromInvestment")),
            "capital_expenditures": capex,
            # Financing activities
            "cashflow_from_financing": safe_long(report.get("cashflowFromFinancing")),
            "proceeds_repayments_short_term_debt": safe_long(report.get("proceedsFromRepaymentsOfShortTermDebt")),
            "payments_repurchase_common_stock": safe_long(report.get("paymentsForRepurchaseOfCommonStock")),
            "payments_repurchase_equity": safe_long(report.get("paymentsForRepurchaseOfEquity")),
            "payments_repurchase_preferred_stock": safe_long(report.get("paymentsForRepurchaseOfPreferredStock")),
            "dividend_payout": safe_long(report.get("dividendPayout")),
            "dividend_payout_common_stock": safe_long(report.get("dividendPayoutCommonStock")),
            "dividend_payout_preferred_stock": safe_long(report.get("dividendPayoutPreferredStock")),
            "proceeds_issuance_common_stock": safe_long(report.get("proceedsFromIssuanceOfCommonStock")),
            "proceeds_issuance_long_term_debt": safe_long(report.get("proceedsFromIssuanceOfLongTermDebtAndCapitalSecuritiesNet")),
            "proceeds_issuance_preferred_stock": safe_long(report.get("proceedsFromIssuanceOfPreferredStock")),
            "proceeds_repurchase_equity": safe_long(report.get("proceedsFromRepurchaseOfEquity")),
            "proceeds_sale_treasury_stock": safe_long(report.get("proceedsFromSaleOfTreasuryStock")),
            # Net change
            "change_in_cash": safe_long(report.get("changeInCashAndCashEquivalents")),
            "change_in_exchange_rate": safe_long(report.get("changeInExchangeRate")),
            # Derived
            "free_cash_flow": free_cf,
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
