"""
Business Licenses Facet for Chicago Data Portal.

Normalizes business license data.

Author: de_Funk Team
Date: January 2026
"""

from __future__ import annotations

from typing import Dict, List

from pyspark.sql import DataFrame
from pyspark.sql.types import (
    StructType, StructField, StringType, DateType, TimestampType
)

from .chicago_base_facet import ChicagoBaseFacet
from config.logging import get_logger

logger = get_logger(__name__)


class BusinessLicensesFacet(ChicagoBaseFacet):
    """Normalize Chicago business licenses data."""

    TABLE_NAME = "chicago_business_licenses"

    OUTPUT_SCHEMA = StructType([
        StructField("id", StringType(), True),
        StructField("license_id", StringType(), True),
        StructField("account_number", StringType(), True),
        StructField("legal_name", StringType(), True),
        StructField("doing_business_as", StringType(), True),
        StructField("license_description", StringType(), True),
        StructField("license_start_date", DateType(), True),
        StructField("license_expiration_date", DateType(), True),
        StructField("address", StringType(), True),
        StructField("city", StringType(), True),
        StructField("state", StringType(), True),
        StructField("zip_code", StringType(), True),
        StructField("ward", StringType(), True),
        StructField("license_status", StringType(), True),
        StructField("ingestion_timestamp", TimestampType(), True),
    ])

    def normalize(
        self,
        raw_data: List[Dict],
        endpoint_config: Dict = None
    ) -> DataFrame:
        """Transform raw business licenses data to DataFrame."""
        if not raw_data:
            return self.create_empty_df(self.OUTPUT_SCHEMA)

        rows = []
        for record in raw_data:
            rows.append({
                "id": self.safe_string(record.get("id")),
                "license_id": self.safe_string(record.get("license_id")),
                "account_number": self.safe_string(record.get("account_number")),
                "legal_name": self.safe_string(record.get("legal_name")),
                "doing_business_as": self.safe_string(
                    record.get("doing_business_as_name") or record.get("dba")
                ),
                "license_description": self.safe_string(record.get("license_description")),
                "license_start_date": self.safe_date(record.get("license_start_date")),
                "license_expiration_date": self.safe_date(
                    record.get("expiration_date") or record.get("license_term_expiration_date")
                ),
                "address": self.safe_string(record.get("address")),
                "city": self.safe_string(record.get("city")),
                "state": self.safe_string(record.get("state")),
                "zip_code": self.safe_string(record.get("zip_code")),
                "ward": self.safe_string(record.get("ward")),
                "license_status": self.safe_string(
                    record.get("license_status") or record.get("application_type")
                ),
                "ingestion_timestamp": None,
            })

        if not rows:
            return self.create_empty_df(self.OUTPUT_SCHEMA)

        df = self.spark.createDataFrame(rows, schema=self.OUTPUT_SCHEMA)
        df = self.add_ingestion_metadata(df)

        logger.info(f"Normalized {df.count()} business license records")
        return df
