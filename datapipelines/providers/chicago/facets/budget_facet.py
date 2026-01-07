"""
Budget Facet for Chicago Data Portal.

Handles Chicago budget data from multiple fiscal year endpoints,
normalizing them into a single table partitioned by fiscal_year.

Pattern: Multiple endpoints → Single Delta table
- budget_fy2024 → chicago_budget/fiscal_year=2024/
- budget_fy2023 → chicago_budget/fiscal_year=2023/
- budget_fy2022 → chicago_budget/fiscal_year=2022/

The fiscal_year is extracted from endpoint metadata, not hardcoded.

Author: de_Funk Team
Date: January 2026
"""

from __future__ import annotations

from typing import Dict, List, Any

from pyspark.sql import DataFrame
from pyspark.sql.functions import lit, col, trim, upper
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    IntegerType, TimestampType
)

from .chicago_base_facet import ChicagoBaseFacet
from config.logging import get_logger

logger = get_logger(__name__)


class BudgetFacet(ChicagoBaseFacet):
    """
    Normalize Chicago budget data with fiscal year from metadata.

    All budget fiscal year endpoints use this single facet.
    The fiscal_year column is added from endpoint metadata.
    """

    TABLE_NAME = "chicago_budget"

    # Output schema for budget data
    OUTPUT_SCHEMA = StructType([
        StructField("fund_code", StringType(), True),
        StructField("fund_description", StringType(), True),
        StructField("department_code", StringType(), True),
        StructField("department_description", StringType(), True),
        StructField("appropriation_account", StringType(), True),
        StructField("appropriation_account_description", StringType(), True),
        StructField("amount", DoubleType(), True),
        StructField("fiscal_year", StringType(), False),  # From metadata
        StructField("ingestion_timestamp", TimestampType(), True),
    ])

    def normalize(
        self,
        raw_data: List[Dict],
        endpoint_config: Dict = None
    ) -> DataFrame:
        """
        Transform raw budget API response to DataFrame.

        Args:
            raw_data: List of budget records from Socrata API
            endpoint_config: Endpoint configuration containing metadata.fiscal_year

        Returns:
            Spark DataFrame with normalized budget schema
        """
        if not raw_data:
            logger.warning("No budget data received")
            return self.create_empty_df(self.OUTPUT_SCHEMA)

        # Extract fiscal_year from endpoint metadata
        metadata = endpoint_config.get("metadata", {}) if endpoint_config else {}
        fiscal_year = metadata.get("fiscal_year")

        if not fiscal_year:
            logger.warning("No fiscal_year in endpoint metadata, using 'unknown'")
            fiscal_year = "unknown"

        logger.info(f"Normalizing {len(raw_data)} budget records for FY{fiscal_year}")

        # Transform records
        rows = []
        for record in raw_data:
            rows.append({
                "fund_code": self.safe_string(
                    record.get("fund_code") or record.get("fund_type")
                ),
                "fund_description": self.safe_string(
                    record.get("fund_description") or record.get("fund_type_description")
                ),
                "department_code": self.safe_string(
                    record.get("department_code") or record.get("department_number")
                ),
                "department_description": self.safe_string(
                    record.get("department_description") or record.get("department_name")
                ),
                "appropriation_account": self.safe_string(
                    record.get("appropriation_account") or record.get("account")
                ),
                "appropriation_account_description": self.safe_string(
                    record.get("appropriation_account_description") or
                    record.get("account_description")
                ),
                "amount": self.safe_float(
                    record.get("amount") or
                    record.get("appropriation") or
                    record.get("revised_appropriation") or
                    record.get("expenditure")
                ),
                "fiscal_year": fiscal_year,
                "ingestion_timestamp": None,  # Added by add_ingestion_metadata
            })

        if not rows:
            return self.create_empty_df(self.OUTPUT_SCHEMA)

        # Create DataFrame
        df = self.spark.createDataFrame(rows, schema=self.OUTPUT_SCHEMA)

        # Add ingestion metadata
        df = self.add_ingestion_metadata(df)

        logger.info(f"Created DataFrame with {df.count()} budget rows for FY{fiscal_year}")

        return df
