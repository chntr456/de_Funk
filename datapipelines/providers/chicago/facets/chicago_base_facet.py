"""
Base Facet for Chicago Data Portal.

Provides common functionality for all Chicago facets:
- Standard column type conversions
- Metadata extraction from endpoint config
- Common schema patterns for Socrata API responses

Author: de_Funk Team
Date: January 2026
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional

from pyspark.sql import DataFrame
from pyspark.sql.functions import lit, current_timestamp, col
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    IntegerType, DateType, TimestampType
)

from config.logging import get_logger

logger = get_logger(__name__)


class ChicagoBaseFacet:
    """
    Base facet for Chicago Data Portal transformations.

    All Chicago facets should inherit from this class and implement
    the normalize() method.
    """

    # Subclasses should define their target table name
    TABLE_NAME: str = "chicago_data"

    def __init__(self, spark):
        """
        Initialize the facet.

        Args:
            spark: SparkSession
        """
        self.spark = spark

    @abstractmethod
    def normalize(
        self,
        raw_data: List[Dict],
        endpoint_config: Dict = None
    ) -> DataFrame:
        """
        Transform raw API data to a Spark DataFrame.

        Args:
            raw_data: List of records from Socrata API
            endpoint_config: Endpoint configuration with metadata

        Returns:
            Spark DataFrame with normalized schema
        """
        pass

    def add_ingestion_metadata(self, df: DataFrame) -> DataFrame:
        """Add standard ingestion metadata columns."""
        return df.withColumn("ingestion_timestamp", current_timestamp())

    def add_metadata_columns(
        self,
        df: DataFrame,
        endpoint_config: Dict
    ) -> DataFrame:
        """
        Add columns from endpoint metadata.

        Args:
            df: Input DataFrame
            endpoint_config: Endpoint config with metadata field

        Returns:
            DataFrame with metadata columns added
        """
        metadata = endpoint_config.get("metadata", {}) if endpoint_config else {}

        for key, value in metadata.items():
            # Skip internal metadata keys
            if key in ("table_name",):
                continue

            # Add as literal column
            df = df.withColumn(key, lit(value))

        return df

    def safe_string(self, value: Any) -> Optional[str]:
        """Safely convert value to string."""
        if value is None:
            return None
        return str(value).strip() if value else None

    def safe_int(self, value: Any) -> Optional[int]:
        """Safely convert value to integer."""
        if value is None:
            return None
        try:
            # Handle string numbers with commas
            if isinstance(value, str):
                value = value.replace(",", "").strip()
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = value.replace(",", "").replace("$", "").strip()
            return float(value)
        except (ValueError, TypeError):
            return None

    def safe_date(self, value: Any, fmt: str = "%Y-%m-%d") -> Optional[datetime]:
        """Safely parse date string."""
        if value is None:
            return None
        try:
            # Handle ISO format with time component
            if isinstance(value, str):
                if "T" in value:
                    value = value.split("T")[0]
                return datetime.strptime(value, fmt).date()
            return None
        except (ValueError, TypeError):
            return None

    def create_empty_df(self, schema: StructType) -> DataFrame:
        """Create an empty DataFrame with the given schema."""
        return self.spark.createDataFrame([], schema=schema)
