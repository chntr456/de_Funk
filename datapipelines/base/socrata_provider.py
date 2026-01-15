"""
Socrata Base Provider.

Base class for Socrata-based data providers (Chicago, Cook County, etc.).
Contains shared functionality for date parsing and DataFrame creation.

Usage:
    from datapipelines.base.socrata_provider import SocrataBaseProvider

    class ChicagoProvider(SocrataBaseProvider):
        PROVIDER_NAME = "Chicago Data Portal"
        ...

Author: de_Funk Team
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Generator
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

from datapipelines.base.provider import BaseProvider
from datapipelines.base.socrata_client import SocrataClient
from config.logging import get_logger
from config.markdown_loader import EndpointConfig

logger = get_logger(__name__)


class SocrataBaseProvider(BaseProvider):
    """
    Base class for Socrata API providers.

    Provides common functionality:
    - Socrata client initialization
    - Date/timestamp parsing for various formats
    - DataFrame creation from endpoint schema
    - Resource ID extraction from endpoint patterns
    - Raw layer support for large CSV downloads
    """

    def __init__(
        self,
        provider_id: str,
        spark=None,
        docs_path: Optional[Path] = None,
        storage_path: Optional[Path] = None,
        preserve_raw: bool = False,
        load_from_raw: bool = False
    ):
        """
        Initialize Socrata provider.

        Args:
            provider_id: Provider identifier (e.g., 'chicago', 'cook_county')
            spark: SparkSession
            docs_path: Path to repo root
            storage_path: Path to storage root (for raw layer)
            preserve_raw: If True, keep raw CSV files after Bronze write (default: False)
            load_from_raw: If True, skip download and load from existing raw CSV files (default: False)
        """
        self._storage_path = Path(storage_path) if storage_path else None
        self._preserve_raw = preserve_raw
        self._load_from_raw = load_from_raw
        # Initialize base (loads markdown config)
        super().__init__(provider_id, spark, docs_path)

    def _setup(self) -> None:
        """Setup Socrata client using config from markdown."""
        # Get app token from environment
        import os
        app_token = None
        if self.env_api_key:
            env_value = os.environ.get(self.env_api_key, "")
            if env_value:
                # Handle comma-separated keys
                app_token = env_value.split(",")[0].strip()

        # Get settings from markdown
        default_limit = self.get_provider_setting('default_limit', 50000)
        timeout = self.get_provider_setting('timeout', 120)

        # Create Socrata client
        self.client = SocrataClient(
            base_url=self.base_url,
            app_token=app_token,
            rate_limit_per_sec=self.rate_limit,
            timeout=timeout
        )

        self._default_limit = default_limit

        logger.info(
            f"{self.__class__.__name__} initialized: {len(self._endpoints)} endpoints, "
            f"rate_limit={self.rate_limit}"
        )

    # =========================================================================
    # UNIFIED INTERFACE IMPLEMENTATION
    # =========================================================================

    def list_work_items(self, status: str = 'active', **kwargs) -> List[str]:
        """List available endpoint IDs for ingestion."""
        if status == 'active':
            return [
                eid for eid, ep in self._endpoints.items()
                if ep.status == 'active'
            ]
        return list(self._endpoints.keys())

    def fetch(
        self,
        work_item: str,
        max_records: Optional[int] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """Fetch data for an endpoint, yielding batches of records."""
        endpoint = self._endpoints.get(work_item)
        if not endpoint:
            logger.warning(f"Unknown endpoint: {work_item}")
            return

        # Check if this is a multi-year endpoint with view_ids
        if endpoint.view_ids:
            yield from self._fetch_multi_year(work_item, endpoint, max_records, **kwargs)
        else:
            yield from self._fetch_single_resource(work_item, endpoint, max_records, **kwargs)

    def _fetch_single_resource(
        self,
        endpoint_id: str,
        endpoint: EndpointConfig,
        max_records: Optional[int] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """Fetch from a single Socrata resource."""
        resource_id = self._get_resource_id(endpoint)
        if not resource_id:
            logger.warning(f"Could not extract resource_id for: {endpoint_id}")
            return

        # Use CSV with raw layer if configured
        if endpoint.download_method == 'csv':
            raw_path = self._get_raw_path(endpoint_id, resource_id)

            if raw_path:
                # Check if we should load from existing raw file
                if self._load_from_raw and raw_path.exists():
                    logger.info(f"Loading from existing raw CSV for {endpoint_id}: {raw_path}")
                elif self._load_from_raw and not raw_path.exists():
                    logger.warning(f"load_from_raw=True but no raw file found for {endpoint_id}, downloading...")
                    self.client.download_csv_to_file(
                        resource_id=resource_id,
                        output_path=str(raw_path),
                        label=endpoint_id
                    )
                else:
                    # Normal download
                    logger.info(f"Using CSV raw layer for {endpoint_id}")
                    self.client.download_csv_to_file(
                        resource_id=resource_id,
                        output_path=str(raw_path),
                        label=endpoint_id
                    )

                # Read from raw file
                for batch in self.client.fetch_csv_from_file(
                    file_path=str(raw_path),
                    batch_size=self._default_limit,
                    max_records=max_records,
                    label=endpoint_id
                ):
                    yield batch
                # Cleanup: delete raw CSV after Bronze write (unless preserve_raw is True)
                if not self._preserve_raw:
                    self._cleanup_raw_file(raw_path, endpoint_id)
            else:
                # Streaming approach (no storage path configured)
                logger.info(f"Using CSV streaming for {endpoint_id}")
                for batch in self.client.fetch_csv(
                    resource_id=resource_id,
                    batch_size=self._default_limit,
                    max_records=max_records,
                    label=endpoint_id
                ):
                    yield batch
            return

        # Default: JSON API with pagination
        params = dict(endpoint.default_query or {})

        for batch in self.client.fetch_all(
            resource_id=resource_id,
            query_params=params,
            limit=self._default_limit,
            max_records=max_records,
            label=endpoint_id
        ):
            yield batch

    def _fetch_multi_year(
        self,
        endpoint_id: str,
        endpoint: EndpointConfig,
        max_records: Optional[int] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """Fetch from multiple year-based view_ids."""
        use_csv = endpoint.download_method == 'csv'
        params = dict(endpoint.default_query or {})

        if use_csv:
            logger.info(f"Using CSV for multi-year {endpoint_id}")

        # view_ids is Dict[str, str] mapping year -> view_id
        for year, resource_id in endpoint.view_ids.items():
            if not resource_id:
                continue

            year_label = f"{endpoint_id}/{year}"

            if use_csv:
                raw_path = self._get_raw_path(endpoint_id, resource_id, year=year)

                if raw_path:
                    # Check if we should load from existing raw file
                    if self._load_from_raw and raw_path.exists():
                        logger.info(f"Loading from existing raw CSV for {year_label}: {raw_path}")
                    elif self._load_from_raw and not raw_path.exists():
                        logger.warning(f"load_from_raw=True but no raw file found for {year_label}, downloading...")
                        self.client.download_csv_to_file(
                            resource_id=resource_id,
                            output_path=str(raw_path),
                            label=year_label
                        )
                    else:
                        # Normal download
                        logger.info(f"Using CSV raw layer for {year_label}")
                        self.client.download_csv_to_file(
                            resource_id=resource_id,
                            output_path=str(raw_path),
                            label=year_label
                        )

                    # Read from raw file
                    for batch in self.client.fetch_csv_from_file(
                        file_path=str(raw_path),
                        batch_size=self._default_limit,
                        max_records=max_records,
                        label=year_label
                    ):
                        # Add year to each record for partitioning
                        for record in batch:
                            record['year'] = year
                        yield batch
                    # Cleanup: delete raw CSV after Bronze write (unless preserve_raw is True)
                    if not self._preserve_raw:
                        self._cleanup_raw_file(raw_path, year_label)
                else:
                    # Streaming approach (no storage path configured)
                    for batch in self.client.fetch_csv(
                        resource_id=resource_id,
                        batch_size=self._default_limit,
                        max_records=max_records,
                        label=year_label
                    ):
                        # Add year to each record for partitioning
                        for record in batch:
                            record['year'] = year
                        yield batch
            else:
                # Use JSON API with pagination
                for batch in self.client.fetch_all(
                    resource_id=resource_id,
                    query_params=params,
                    limit=self._default_limit,
                    max_records=max_records,
                    label=year_label
                ):
                    # Add year to each record for partitioning
                    for record in batch:
                        record['year'] = year
                    yield batch

    def normalize(self, records: List[Dict], work_item: str) -> DataFrame:
        """Normalize raw records to a Spark DataFrame."""
        endpoint = self._endpoints.get(work_item)
        if not endpoint:
            return self.spark.createDataFrame(records, samplingRatio=1.0)

        return self._create_dataframe(records, endpoint)

    def fetch_dataframe(
        self,
        work_item: str,
        max_records: Optional[int] = None,
        **kwargs
    ) -> Optional[DataFrame]:
        """
        Fetch data as a Spark DataFrame directly (bypasses Python batching).

        Uses spark.read.csv() for raw files, which is much faster than
        Python csv.DictReader for large files.

        Args:
            work_item: Endpoint ID
            max_records: Optional limit on records
            **kwargs: Additional options

        Returns:
            Spark DataFrame, or None if not supported for this endpoint
        """
        endpoint = self._endpoints.get(work_item)
        if not endpoint:
            return None

        # Only use for CSV endpoints with raw layer
        if endpoint.download_method != 'csv':
            return None

        resource_id = self._get_resource_id(endpoint)
        if not resource_id:
            return None

        raw_path = self._get_raw_path(work_item, resource_id)
        if not raw_path:
            return None

        # Download if needed
        if self._load_from_raw and raw_path.exists():
            logger.info(f"Spark CSV: loading from existing raw file for {work_item}")
        elif self._load_from_raw and not raw_path.exists():
            logger.warning(f"load_from_raw=True but no raw file for {work_item}, downloading...")
            self.client.download_csv_to_file(
                resource_id=resource_id,
                output_path=str(raw_path),
                label=work_item
            )
        else:
            logger.info(f"Spark CSV: downloading {work_item}")
            self.client.download_csv_to_file(
                resource_id=resource_id,
                output_path=str(raw_path),
                label=work_item
            )

        # Read with Spark
        df = self.read_csv_with_spark(str(raw_path), work_item)

        # Apply max_records limit
        if max_records and df.count() > max_records:
            df = df.limit(max_records)

        # Cleanup if not preserving
        if not self._preserve_raw:
            self._cleanup_raw_file(raw_path, work_item)

        return df

    def supports_dataframe_fetch(self, work_item: str) -> bool:
        """Check if endpoint supports direct DataFrame fetch (faster for large CSVs)."""
        endpoint = self._endpoints.get(work_item)
        if not endpoint:
            return False
        return endpoint.download_method == 'csv' and self._storage_path is not None

    def read_csv_with_spark(self, csv_path: str, work_item: str) -> DataFrame:
        """
        Read CSV file directly with Spark (much faster than Python csv module).

        Uses spark.read.csv() for parallelized reading, then applies schema
        transformations (column renames, type casting) based on endpoint config.

        Args:
            csv_path: Path to CSV file
            work_item: Endpoint ID for schema lookup

        Returns:
            Spark DataFrame with schema applied
        """
        endpoint = self._endpoints.get(work_item)

        # Read CSV with Spark - all columns as strings initially
        df = self.spark.read.csv(
            csv_path,
            header=True,
            inferSchema=False,  # Keep as strings, we'll cast manually
            mode="PERMISSIVE",
            multiLine=True,
            escape='"'
        )

        # Log actual CSV columns for debugging
        csv_columns = df.columns
        logger.info(f"Spark CSV read {work_item}: {len(csv_columns)} columns: {csv_columns[:20]}{'...' if len(csv_columns) > 20 else ''}")

        if not endpoint or not endpoint.schema:
            return df

        # Build column alias map for common variations (Socrata column names → schema names)
        # This handles cases where CSV has different column names than schema expects
        column_aliases = {
            'tax_year': 'year',        # Cook County uses tax_year
            'taxyr': 'year',           # Alternative
            'taxyear': 'year',         # Alternative
            'sale_year': 'year',       # For sales data
        }

        # Apply column aliases if the target column is in schema but source is not in CSV
        schema_cols = {f.name for f in endpoint.schema}
        for alias_source, alias_target in column_aliases.items():
            if alias_target in schema_cols and alias_target not in df.columns and alias_source in df.columns:
                logger.info(f"Column alias: '{alias_source}' → '{alias_target}'")
                df = df.withColumnRenamed(alias_source, alias_target)

        # Rename columns from source names to target names (as defined in schema)
        for field_def in endpoint.schema:
            if field_def.source in df.columns and field_def.source != field_def.name:
                df = df.withColumnRenamed(field_def.source, field_def.name)

        # If 'year' is needed for partitioning but not in DataFrame, derive from date column
        partitions = endpoint.partitions or []
        date_col = endpoint.date_column
        if 'year' in partitions and 'year' not in df.columns:
            # Try to derive year from date column
            if date_col and date_col in df.columns:
                logger.info(f"Deriving 'year' partition from date column '{date_col}'")
                df = df.withColumn('year', F.year(self._safe_parse_date(F.col(date_col))))
            # Or check for any date/timestamp columns we can extract year from
            elif not date_col:
                for col_name in df.columns:
                    if 'date' in col_name.lower() or col_name.lower() in ('time', 'timestamp'):
                        logger.info(f"Deriving 'year' partition from column '{col_name}'")
                        df = df.withColumn('year', F.year(self._safe_parse_date(F.col(col_name))))
                        break

        # Select only schema columns (drop extra columns from CSV)
        schema_cols_list = [f.name for f in endpoint.schema]
        # Also include derived partition columns that may not be in schema
        for p in partitions:
            if p not in schema_cols_list and p in df.columns:
                schema_cols_list.append(p)
        available_cols = [c for c in schema_cols_list if c in df.columns]
        df = df.select(available_cols)

        # Cast columns to target types
        for field_def in endpoint.schema:
            if field_def.name not in df.columns:
                continue

            target_type = field_def.type.lower()
            if target_type == 'string':
                continue
            elif target_type in ('int', 'long'):
                df = df.withColumn(field_def.name,
                    F.col(field_def.name).cast('double').cast(target_type))
            elif target_type in ('double', 'float'):
                df = df.withColumn(field_def.name, F.col(field_def.name).cast('double'))
            elif target_type == 'date':
                df = df.withColumn(field_def.name,
                    self._safe_parse_date(F.col(field_def.name)))
            elif target_type == 'timestamp':
                df = df.withColumn(field_def.name,
                    self._safe_parse_timestamp(F.col(field_def.name)))
            elif target_type == 'boolean':
                df = df.withColumn(field_def.name,
                    F.when(F.lower(F.col(field_def.name)).isin('true', '1', 'yes'), True)
                    .when(F.lower(F.col(field_def.name)).isin('false', '0', 'no'), False)
                    .otherwise(None).cast('boolean'))

        return df

    def get_table_name(self, work_item: str) -> str:
        """Get Bronze table name for an endpoint."""
        endpoint = self._endpoints.get(work_item)
        if endpoint and endpoint.bronze:
            return endpoint.bronze.table
        return f"{self.provider_id}_{work_item}"

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_raw_path(self, endpoint_id: str, resource_id: str, year: Optional[str] = None) -> Optional[Path]:
        """
        Get the raw layer file path for a CSV download.

        Raw layer structure:
            storage/raw/{provider}/{endpoint}_{resource_id}.csv
            storage/raw/{provider}/{endpoint}_{year}_{resource_id}.csv (for multi-year)

        Args:
            endpoint_id: Endpoint identifier
            resource_id: Socrata resource/view ID
            year: Optional year for multi-year endpoints

        Returns:
            Path to raw CSV file, or None if storage_path not configured
        """
        if not self._storage_path:
            return None

        raw_dir = self._storage_path / 'raw' / self.provider_id

        if year:
            filename = f"{endpoint_id}_{year}_{resource_id}.csv"
        else:
            filename = f"{endpoint_id}_{resource_id}.csv"

        return raw_dir / filename

    def _cleanup_raw_file(self, raw_path: Path, label: str) -> None:
        """
        Delete raw CSV file after successful Bronze write.

        Args:
            raw_path: Path to the raw CSV file
            label: Label for logging (endpoint_id or endpoint_id/year)
        """
        try:
            if raw_path.exists():
                file_size = raw_path.stat().st_size
                raw_path.unlink()
                logger.info(f"Cleaned up raw CSV: {label} ({file_size:,} bytes freed)")
        except OSError as e:
            logger.warning(f"Failed to cleanup raw CSV {label}: {e}")

    def _get_resource_id(self, endpoint: EndpointConfig) -> Optional[str]:
        """Extract Socrata 4x4 resource ID from endpoint pattern."""
        pattern = endpoint.endpoint_pattern
        if "/resource/" in pattern and ".json" in pattern:
            start = pattern.find("/resource/") + len("/resource/")
            end = pattern.find(".json")
            return pattern[start:end]
        return None

    def get_resource_id(self, endpoint_id: str) -> Optional[str]:
        """Get Socrata resource ID for an endpoint (public method)."""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return None
        return self._get_resource_id(endpoint)

    def list_endpoints(self) -> List[str]:
        """List all available endpoint IDs (alias for list_work_items)."""
        return self.list_work_items(status='all')

    # =========================================================================
    # DATE/TIMESTAMP PARSING (Shared by all Socrata providers)
    # =========================================================================

    def _safe_parse_date(self, col_val):
        """
        Normalize date strings to yyyy-MM-dd format for ANSI-safe parsing.

        Handles Socrata date formats:
        - ISO timestamp: 2025-02-26T00:00:00.000 -> 2025-02-26
        - ISO date: 2025-02-26 (no change)
        - US date: 01/16/2025 or 1/6/2025 -> 2025-01-16
        - Month name: January 16 2024, January 6 2024 -> 2024-01-16, 2024-01-06
        - Year only: 2020 -> 2020-01-01
        - NULL/empty: NULL
        """
        trimmed = F.trim(col_val)

        parts = F.split(trimmed, "/")
        us_date_formatted = F.concat(
            parts[2],
            F.lit("-"),
            F.lpad(parts[0], 2, "0"),
            F.lit("-"),
            F.lpad(parts[1], 2, "0")
        )

        normalized = (
            F.when(
                col_val.isNull() | (F.length(trimmed) == 0),
                F.lit(None).cast("string")
            ).when(
                trimmed.contains("T"),
                F.substring(trimmed, 1, 10)
            ).when(
                trimmed.contains("/"),
                us_date_formatted
            ).when(
                F.length(trimmed) == 4,
                F.concat(trimmed, F.lit("-01-01"))
            ).otherwise(
                trimmed
            )
        )

        # Try multiple date formats using coalesce
        # to_date returns null on parse failure (when spark.sql.ansi.enabled=false, which is default)
        # Order: ISO format, month name with 2-digit day, month name with 1-digit day
        return F.coalesce(
            F.to_date(normalized, "yyyy-MM-dd"),
            F.to_date(trimmed, "MMMM dd yyyy"),
            F.to_date(trimmed, "MMMM d yyyy")
        )

    def _safe_parse_timestamp(self, col_val):
        """
        Normalize timestamp strings for ANSI-safe parsing.

        Handles formats:
        - ISO: 2025-02-26T14:30:00.000 -> 2025-02-26 14:30:00
        - US: 01/16/2025 -> 2025-01-16 00:00:00
        - Month name: January 16 2024, January 6 2024 -> 2024-01-16 00:00:00
        - Date only: 2025-02-26 -> 2025-02-26 00:00:00
        - Year only: 2020 -> 2020-01-01 00:00:00
        """
        trimmed = F.trim(col_val)

        iso_normalized = F.regexp_replace(
            F.substring(trimmed, 1, 19),
            "T", " "
        )

        parts = F.split(trimmed, "/")
        us_timestamp = F.concat(
            parts[2], F.lit("-"),
            F.lpad(parts[0], 2, "0"), F.lit("-"),
            F.lpad(parts[1], 2, "0"),
            F.lit(" 00:00:00")
        )

        normalized = (
            F.when(
                col_val.isNull() | (F.length(trimmed) == 0),
                F.lit(None).cast("string")
            ).when(
                trimmed.contains("T"),
                iso_normalized
            ).when(
                trimmed.contains("/"),
                us_timestamp
            ).when(
                F.length(trimmed) == 10,
                F.concat(trimmed, F.lit(" 00:00:00"))
            ).when(
                F.length(trimmed) == 4,
                F.concat(trimmed, F.lit("-01-01 00:00:00"))
            ).otherwise(
                trimmed
            )
        )

        # Try multiple timestamp formats using coalesce
        # to_timestamp returns null on parse failure (when spark.sql.ansi.enabled=false, which is default)
        # Order: ISO format, month name with 2-digit day, month name with 1-digit day
        return F.coalesce(
            F.to_timestamp(normalized, "yyyy-MM-dd HH:mm:ss"),
            F.to_timestamp(trimmed, "MMMM dd yyyy"),
            F.to_timestamp(trimmed, "MMMM d yyyy")
        )

    def _create_dataframe(
        self,
        records: List[Dict],
        endpoint: EndpointConfig
    ) -> DataFrame:
        """
        Create Spark DataFrame from records using endpoint schema.

        Args:
            records: List of record dicts from API
            endpoint: Endpoint configuration with schema

        Returns:
            Spark DataFrame
        """
        if not endpoint.schema:
            return self.spark.createDataFrame(records, samplingRatio=1.0)

        # Build column alias map for common variations (Socrata → schema)
        column_aliases = {
            'tax_year': 'year',
            'taxyr': 'year',
            'taxyear': 'year',
            'sale_year': 'year',
        }

        # Map source fields to target fields (keep as strings initially)
        transformed_records = []
        schema_fields = {f.name for f in endpoint.schema}

        for record in records:
            transformed = {}
            for field_def in endpoint.schema:
                # Try primary source first
                source_val = record.get(field_def.source)
                # If not found and this is a field with known aliases, try aliases
                if source_val is None and field_def.name in column_aliases.values():
                    for alias_source, alias_target in column_aliases.items():
                        if alias_target == field_def.name and alias_source in record:
                            source_val = record.get(alias_source)
                            break
                transformed[field_def.name] = str(source_val) if source_val is not None else None
            transformed_records.append(transformed)

        # Create DataFrame with all strings first
        string_schema = StructType([
            StructField(f.name, StringType(), True) for f in endpoint.schema
        ])
        df = self.spark.createDataFrame(transformed_records, string_schema)

        # Cast columns to target types
        for field_def in endpoint.schema:
            target_type = field_def.type.lower()
            if target_type == 'string':
                continue
            elif target_type in ('int', 'long'):
                df = df.withColumn(field_def.name,
                    F.col(field_def.name).cast('double').cast(target_type))
            elif target_type in ('double', 'float'):
                df = df.withColumn(field_def.name, F.col(field_def.name).cast('double'))
            elif target_type == 'date':
                df = df.withColumn(field_def.name,
                    self._safe_parse_date(F.col(field_def.name)))
            elif target_type == 'timestamp':
                df = df.withColumn(field_def.name,
                    self._safe_parse_timestamp(F.col(field_def.name)))
            elif target_type == 'boolean':
                df = df.withColumn(field_def.name, F.col(field_def.name).cast('boolean'))

        # If 'year' is needed for partitioning but is null/missing, derive from date column
        partitions = endpoint.partitions or []
        date_col = endpoint.date_column
        if 'year' in partitions and 'year' in df.columns:
            # Check if year column is mostly null (meaning alias didn't work)
            # In that case, derive from date column
            if date_col and date_col in df.columns:
                # Add year derivation as fallback when year is null
                df = df.withColumn('year',
                    F.coalesce(
                        F.col('year').cast('int'),
                        F.year(self._safe_parse_date(F.col(date_col)))
                    )
                )

        return df
