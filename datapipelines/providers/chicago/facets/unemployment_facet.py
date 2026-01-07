"""
Unemployment Facet for Chicago Data Portal.

Normalizes unemployment rate data by community area.

Author: de_Funk Team
Date: January 2026
"""

from __future__ import annotations

from typing import Dict, List

from pyspark.sql import DataFrame
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    IntegerType, TimestampType
)

from .chicago_base_facet import ChicagoBaseFacet
from config.logging import get_logger

logger = get_logger(__name__)


class UnemploymentFacet(ChicagoBaseFacet):
    """Normalize Chicago unemployment data by community area."""

    TABLE_NAME = "chicago_unemployment"

    OUTPUT_SCHEMA = StructType([
        StructField("community_area", StringType(), True),
        StructField("community_area_name", StringType(), True),
        StructField("year", IntegerType(), True),
        StructField("month", IntegerType(), True),
        StructField("unemployment_rate", DoubleType(), True),
        StructField("percent_below_poverty", DoubleType(), True),
        StructField("per_capita_income", DoubleType(), True),
        StructField("ingestion_timestamp", TimestampType(), True),
    ])

    def normalize(
        self,
        raw_data: List[Dict],
        endpoint_config: Dict = None
    ) -> DataFrame:
        """Transform raw unemployment data to DataFrame."""
        if not raw_data:
            return self.create_empty_df(self.OUTPUT_SCHEMA)

        rows = []
        for record in raw_data:
            rows.append({
                "community_area": self.safe_string(
                    record.get("community_area_number") or record.get("ca")
                ),
                "community_area_name": self.safe_string(
                    record.get("community_area_name") or record.get("community_area")
                ),
                "year": self.safe_int(record.get("year")),
                "month": self.safe_int(record.get("month")),
                "unemployment_rate": self.safe_float(
                    record.get("unemployment") or record.get("unemployment_rate")
                ),
                "percent_below_poverty": self.safe_float(
                    record.get("below_poverty_level") or
                    record.get("percent_households_below_poverty")
                ),
                "per_capita_income": self.safe_float(
                    record.get("per_capita_income") or record.get("per_capita_income_")
                ),
                "ingestion_timestamp": None,
            })

        if not rows:
            return self.create_empty_df(self.OUTPUT_SCHEMA)

        df = self.spark.createDataFrame(rows, schema=self.OUTPUT_SCHEMA)
        df = self.add_ingestion_metadata(df)

        logger.info(f"Normalized {df.count()} unemployment records")
        return df
