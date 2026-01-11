"""
Base facet for Alpha Vantage API data transformations.

Alpha Vantage uses a different API structure than Polygon:
- Single base URL with function parameter
- API key passed as query parameter
- Response format varies by endpoint (some nested, some flat)
- Rate limits are more restrictive (5 calls/min for free tier)

Schema Loading (v2.6 - Markdown-Driven):
    Facets load schema from markdown endpoint files by setting ENDPOINT_ID:

        class MyFacet(AlphaVantageFacet):
            ENDPOINT_ID = "balance_sheet"  # Loads from Documents/Data Sources/Endpoints/Alpha Vantage/.../Balance Sheet.md

    The base class will automatically:
    - Load schema from markdown
    - Derive NUMERIC_COERCE from fields with coerce option
    - Derive FINAL_COLUMNS from schema fields
    - Generate field mappings (source -> output)

Legacy Support:
    INPUT_SCHEMA_KEY still works for facets not yet migrated to markdown.
"""
from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
import pandas as pd
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, LongType,
    IntegerType, BooleanType, DateType, TimestampType
)

from datapipelines.base.facet import Facet
from config.schema_loader import SchemaLoader
from config.markdown_loader import get_markdown_loader
from utils.repo import get_repo_root


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
        ENDPOINT_ID: Endpoint ID in markdown (e.g., "balance_sheet")
        INPUT_SCHEMA_KEY: Legacy schema key in configs/schemas/alpha_vantage.yaml
        tickers: List of ticker symbols to fetch
        date_from: Start date for time series data
        date_to: End date for time series data
        extra: Additional parameters (interval, outputsize, etc.)
    """

    # Set in subclass to load schema from markdown endpoint file
    ENDPOINT_ID: Optional[str] = None

    # Legacy: Schema key in configs/schemas/alpha_vantage.yaml (for facets not yet migrated)
    INPUT_SCHEMA_KEY: Optional[str] = None

    # Cache for markdown-derived schema info
    _md_schema_cache: Optional[Dict[str, Any]] = None

    @classmethod
    def _load_markdown_schema(cls) -> Dict[str, Any]:
        """
        Load and cache schema information from markdown endpoint file.

        Returns dict with:
            - schema: List of SchemaField dicts
            - coerce_rules: Dict[source_field, type]
            - final_columns: List[(output_name, type)]
            - field_mappings: Dict[source_field, output_name]
            - computed_fields: List of computed field defs
        """
        if cls._md_schema_cache is not None:
            return cls._md_schema_cache

        if not cls.ENDPOINT_ID:
            cls._md_schema_cache = {}
            return cls._md_schema_cache

        try:
            repo_root = get_repo_root()
            loader = get_markdown_loader(repo_root)

            # Get full schema
            schema = loader.get_endpoint_schema(cls.ENDPOINT_ID)
            if not schema:
                cls._md_schema_cache = {}
                return cls._md_schema_cache

            # Derive coercion rules (source_field -> type)
            coerce_rules = {}
            for f in schema:
                if f.get('coerce') and f.get('source') not in ('_computed', '_generated', '_param', '_key', '_na'):
                    coerce_rules[f['source']] = f['coerce']

            # Derive final columns (output_name, type)
            final_columns = []
            for f in schema:
                final_columns.append((f['name'], f['type']))

            # Derive field mappings (source -> output)
            field_mappings = {}
            for f in schema:
                src = f.get('source')
                if src and src not in ('_computed', '_generated', '_param', '_key', '_na'):
                    field_mappings[src] = f['name']

            # Get computed fields
            computed = []
            for f in schema:
                if f.get('source') == '_computed' and f.get('expr'):
                    computed.append({
                        'name': f['name'],
                        'type': f['type'],
                        'expr': f['expr'],
                        'default': f.get('default'),
                    })

            cls._md_schema_cache = {
                'schema': schema,
                'coerce_rules': coerce_rules,
                'final_columns': final_columns,
                'field_mappings': field_mappings,
                'computed_fields': computed,
            }
            return cls._md_schema_cache

        except Exception as e:
            # Log but don't fail - allow fallback to legacy
            import logging
            logging.getLogger(__name__).warning(f"Could not load markdown schema for {cls.ENDPOINT_ID}: {e}")
            cls._md_schema_cache = {}
            return cls._md_schema_cache

    @classmethod
    def get_coerce_rules(cls) -> Dict[str, str]:
        """Get source field -> type coercion rules from markdown schema."""
        md_info = cls._load_markdown_schema()
        return md_info.get('coerce_rules', {})

    @classmethod
    def get_final_columns(cls) -> List[Tuple[str, str]]:
        """Get final columns list from markdown schema."""
        md_info = cls._load_markdown_schema()
        return md_info.get('final_columns', [])

    @classmethod
    def get_field_mappings(cls) -> Dict[str, str]:
        """Get source -> output field name mappings from markdown schema."""
        md_info = cls._load_markdown_schema()
        return md_info.get('field_mappings', {})

    @classmethod
    def get_computed_fields(cls) -> List[Dict[str, Any]]:
        """Get computed field definitions from markdown schema."""
        md_info = cls._load_markdown_schema()
        return md_info.get('computed_fields', [])

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

    def _type_str_to_spark_type(self, type_str: str):
        """Convert type string to Spark type."""
        type_map = {
            "string": StringType(),
            "double": DoubleType(),
            "float": DoubleType(),
            "int": IntegerType(),
            "integer": IntegerType(),
            "long": LongType(),
            "bigint": LongType(),
            "boolean": BooleanType(),
            "date": DateType(),
            "timestamp": TimestampType(),
        }
        return type_map.get(type_str.lower(), StringType())

    def get_input_schema(self) -> Optional[StructType]:
        """
        Get the input schema for this facet's API response.

        Priority:
        1. ENDPOINT_ID (markdown) - New v2.6 approach
        2. INPUT_SCHEMA_KEY (YAML) - Legacy approach
        3. None - Let Spark infer

        This prevents CANNOT_DETERMINE_TYPE errors when columns have all NULL values.

        Returns:
            pyspark.sql.types.StructType or None
        """
        # Try markdown schema first (v2.6)
        if self.ENDPOINT_ID:
            final_cols = self.get_final_columns()
            if final_cols:
                fields = []
                for name, type_str in final_cols:
                    # Handle special cases for input schema
                    # fiscal_date_ending comes in as string, convert in postprocess
                    if name in ('fiscal_date_ending', 'trade_date') and type_str == 'date':
                        fields.append(StructField(name, StringType(), True))
                    else:
                        fields.append(StructField(name, self._type_str_to_spark_type(type_str), True))
                return StructType(fields)

        # Fallback to legacy YAML schema
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
