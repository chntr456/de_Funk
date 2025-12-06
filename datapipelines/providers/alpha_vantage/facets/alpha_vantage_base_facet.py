"""
Base facet for Alpha Vantage API data transformations.

Alpha Vantage uses a different API structure than Polygon:
- Single base URL with function parameter
- API key passed as query parameter
- Response format varies by endpoint (some nested, some flat)
- Rate limits are more restrictive (5 calls/min for free tier)

Schema Loading:
    Facets can use centralized schema definitions from configs/schemas/alpha_vantage.yaml
    by setting the INPUT_SCHEMA_KEY class attribute:

        class MyFacet(AlphaVantageFacet):
            INPUT_SCHEMA_KEY = "overview"  # References alpha_vantage.yaml key

    The base class get_input_schema() will automatically load the schema.
"""
from __future__ import annotations

from typing import Optional
import pandas as pd
from pyspark.sql.types import StructType

from datapipelines.facets.base_facet import Facet
from config.schema_loader import SchemaLoader


def safe_long(series: pd.Series) -> list:
    """
    Convert pandas Series to list of Python int or None.

    Avoids Spark CANNOT_DETERMINE_TYPE errors by using Python native types
    instead of pandas Int64/float64 which fail when all values are NaN.

    Args:
        series: pandas Series to convert

    Returns:
        List of Python int or None values
    """
    if series is None:
        return []
    return [int(x) if pd.notna(x) else None for x in pd.to_numeric(series, errors='coerce')]


def safe_double(series: pd.Series) -> list:
    """
    Convert pandas Series to list of Python float or None.

    Avoids Spark CANNOT_DETERMINE_TYPE errors by using Python native types
    instead of pandas Int64/float64 which fail when all values are NaN.

    Args:
        series: pandas Series to convert

    Returns:
        List of Python float or None values
    """
    if series is None:
        return []
    return [float(x) if pd.notna(x) else None for x in pd.to_numeric(series, errors='coerce')]


def safe_string(series: pd.Series) -> list:
    """
    Convert pandas Series to list of Python str or None.

    Args:
        series: pandas Series to convert

    Returns:
        List of Python str or None values
    """
    if series is None:
        return []
    return [str(x) if pd.notna(x) and str(x) != 'None' else None for x in series]


class AlphaVantageFacet(Facet):
    """
    Base facet for Alpha Vantage data providers.

    Key Differences from Polygon:
    - API key in query params (not headers)
    - Function-based endpoint selection
    - Varied response structures
    - Lower rate limits

    Attributes:
        INPUT_SCHEMA_KEY: Schema key in configs/schemas/alpha_vantage.yaml
        tickers: List of ticker symbols to fetch
        date_from: Start date for time series data
        date_to: End date for time series data
        extra: Additional parameters (interval, outputsize, etc.)
    """

    # Set in subclass to auto-load schema from configs/schemas/alpha_vantage.yaml
    INPUT_SCHEMA_KEY: Optional[str] = None

    def __init__(self, spark, tickers=None, date_from=None, date_to=None, **extra):
        """
        Initialize Alpha Vantage facet.

        Args:
            spark: SparkSession
            tickers: List of ticker symbols (optional)
            date_from: Start date for time series (YYYY-MM-DD)
            date_to: End date for time series (YYYY-MM-DD)
            **extra: Additional parameters:
                - interval: Time interval for intraday/technical indicators
                - outputsize: 'compact' (100 days) or 'full' (20+ years)
                - adjusted: Whether to use adjusted prices
        """
        super().__init__(spark)
        self.tickers = tickers or []
        self.date_from = date_from
        self.date_to = date_to
        self.extra = extra

    def calls(self):
        """
        Generate API calls for this facet.

        Must be implemented by subclass.
        Returns iterable of dicts with ep_name and params.
        """
        raise NotImplementedError

    def get_input_schema(self) -> Optional[StructType]:
        """
        Get the input schema for this facet's API response.

        If INPUT_SCHEMA_KEY is set, loads schema from configs/schemas/alpha_vantage.yaml.
        Otherwise, subclasses can override to provide custom schema.

        This prevents CANNOT_DETERMINE_TYPE errors when columns have all NULL values.

        Returns:
            pyspark.sql.types.StructType or None
        """
        if self.INPUT_SCHEMA_KEY:
            return SchemaLoader.load("alpha_vantage", self.INPUT_SCHEMA_KEY)
        return None

    def normalize(self, raw_batches):
        """
        Override normalize to clean Alpha Vantage data at Python level.

        Alpha Vantage data quality issues:
        - Returns literal string "None" for missing values
        - Uses "N/A" and "-" for unavailable data
        - Sometimes has extra whitespace
        - Empty strings for missing data

        This method performs bronze layer cleaning:
        - Replace invalid markers ("None", "N/A", "-") with Python None (becomes NULL)
        - Strip whitespace from all string values
        - Convert empty strings to None
        - Preserve valid data as-is
        """
        # Clean the raw data at Python level
        cleaned_batches = []
        for batch in raw_batches:
            cleaned_batch = []
            for item in batch:
                if isinstance(item, dict):
                    # Clean each field value
                    cleaned_item = {}
                    for key, value in item.items():
                        # Handle None/null values
                        if value is None:
                            cleaned_item[key] = None
                        # Handle string values
                        elif isinstance(value, str):
                            # Strip whitespace
                            cleaned_value = value.strip()
                            # Replace invalid markers with None
                            if cleaned_value in ("None", "N/A", "-", ""):
                                cleaned_item[key] = None
                            else:
                                cleaned_item[key] = cleaned_value
                        # Keep non-string values as-is
                        else:
                            cleaned_item[key] = value
                    cleaned_batch.append(cleaned_item)
                else:
                    cleaned_batch.append(item)
            cleaned_batches.append(cleaned_batch)

        # Flatten batches into single list
        rows = [item for batch in cleaned_batches for item in batch]

        # Get schema if provided by subclass
        schema = self.get_input_schema()

        # Create DataFrame with explicit schema (avoids type inference issues)
        if schema:
            df = self.spark.createDataFrame(rows, schema=schema)
        else:
            df = self.spark.createDataFrame(rows, samplingRatio=1.0)

        # Apply postprocessing
        df = self.postprocess(df)

        return df
