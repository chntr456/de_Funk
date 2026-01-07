"""
Building Permits Facet for Chicago Data Portal.

Normalizes building permit data.

Author: de_Funk Team
Date: January 2026
"""

from __future__ import annotations

from typing import Dict, List

from pyspark.sql import DataFrame
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    DateType, TimestampType
)

from .chicago_base_facet import ChicagoBaseFacet
from config.logging import get_logger

logger = get_logger(__name__)


class BuildingPermitsFacet(ChicagoBaseFacet):
    """Normalize Chicago building permits data."""

    TABLE_NAME = "chicago_building_permits"

    OUTPUT_SCHEMA = StructType([
        StructField("id", StringType(), True),
        StructField("permit_number", StringType(), True),
        StructField("permit_type", StringType(), True),
        StructField("issue_date", DateType(), True),
        StructField("street_number", StringType(), True),
        StructField("street_direction", StringType(), True),
        StructField("street_name", StringType(), True),
        StructField("work_description", StringType(), True),
        StructField("total_fee", DoubleType(), True),
        StructField("reported_cost", DoubleType(), True),
        StructField("community_area", StringType(), True),
        StructField("ward", StringType(), True),
        StructField("ingestion_timestamp", TimestampType(), True),
    ])

    def normalize(
        self,
        raw_data: List[Dict],
        endpoint_config: Dict = None
    ) -> DataFrame:
        """Transform raw building permits data to DataFrame."""
        if not raw_data:
            return self.create_empty_df(self.OUTPUT_SCHEMA)

        rows = []
        for record in raw_data:
            rows.append({
                "id": self.safe_string(record.get("id")),
                "permit_number": self.safe_string(record.get("permit_")),
                "permit_type": self.safe_string(record.get("permit_type")),
                "issue_date": self.safe_date(record.get("issue_date")),
                "street_number": self.safe_string(record.get("street_number")),
                "street_direction": self.safe_string(record.get("street_direction")),
                "street_name": self.safe_string(record.get("street_name")),
                "work_description": self.safe_string(record.get("work_description")),
                "total_fee": self.safe_float(record.get("total_fee")),
                "reported_cost": self.safe_float(record.get("reported_cost")),
                "community_area": self.safe_string(record.get("community_area")),
                "ward": self.safe_string(record.get("ward")),
                "ingestion_timestamp": None,
            })

        if not rows:
            return self.create_empty_df(self.OUTPUT_SCHEMA)

        df = self.spark.createDataFrame(rows, schema=self.OUTPUT_SCHEMA)
        df = self.add_ingestion_metadata(df)

        logger.info(f"Normalized {df.count()} building permit records")
        return df
