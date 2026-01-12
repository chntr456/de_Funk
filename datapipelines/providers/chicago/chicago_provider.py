"""
Chicago Data Portal Provider Implementation.

Implements data ingestion from Chicago's Socrata Open Data API.
This provider fetches bulk datasets (no per-ticker iteration needed).

Features:
- Offset-based pagination for large datasets
- SoQL query support ($where, $select, $order, etc.)
- Rate limiting with app token support (5 req/sec)
- Schema-driven transformation using markdown configs

Usage:
    from datapipelines.providers.chicago.chicago_provider import ChicagoProvider

    provider = ChicagoProvider(config, spark)
    df = provider.fetch_dataset("crimes")
    provider.write_to_bronze(df, "crimes")

Author: de_Funk Team
Date: January 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Generator
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, IntegerType,
    LongType, DateType, TimestampType, BooleanType
)

from datapipelines.base.socrata_client import SocrataClient
from datapipelines.ingestors.bronze_sink import BronzeSink
from config.logging import get_logger
from config.markdown_loader import MarkdownConfigLoader, EndpointConfig

logger = get_logger(__name__)


@dataclass
class ChicagoProviderConfig:
    """Configuration for Chicago Data Portal provider."""
    base_url: str = "https://data.cityofchicago.org"
    app_token: Optional[str] = None
    rate_limit_per_sec: float = 5.0
    default_limit: int = 50000
    timeout: int = 120


@dataclass
class DatasetFetchResult:
    """Result from fetching a dataset."""
    endpoint_id: str
    success: bool
    record_count: int = 0
    error: Optional[str] = None
    df: Optional[DataFrame] = None


class ChicagoProvider:
    """
    Provider for Chicago Data Portal (Socrata API).

    Unlike ticker-based providers (Alpha Vantage), this provider
    fetches bulk datasets. Each endpoint returns a complete dataset
    that can be paginated.
    """

    PROVIDER_ID = "chicago_data_portal"
    PROVIDER_NAME = "Chicago Data Portal"

    # Map endpoint_id to Socrata resource IDs
    # These come from the endpoint markdown files (endpoint_pattern: /resource/{id}.json)
    # Format: endpoint_id -> 4x4 resource ID

    def __init__(
        self,
        config: ChicagoProviderConfig,
        spark,
        storage_cfg: Dict,
        docs_path: Optional[Path] = None
    ):
        """
        Initialize Chicago provider.

        Args:
            config: Provider configuration
            spark: SparkSession
            storage_cfg: Storage configuration for Bronze paths
            docs_path: Path to Documents folder (for loading endpoint configs)
        """
        self.config = config
        self.spark = spark
        self.storage_cfg = storage_cfg
        self.sink = BronzeSink(storage_cfg)

        # Initialize Socrata client
        self.client = SocrataClient(
            base_url=config.base_url,
            app_token=config.app_token,
            rate_limit_per_sec=config.rate_limit_per_sec,
            timeout=config.timeout
        )

        # Load endpoint configs from markdown
        self._endpoints: Dict[str, EndpointConfig] = {}
        if docs_path:
            self._load_endpoint_configs(docs_path)

        logger.info(
            f"ChicagoProvider initialized: {len(self._endpoints)} endpoints, "
            f"rate_limit={config.rate_limit_per_sec}"
        )

    def _load_endpoint_configs(self, docs_path: Path) -> None:
        """Load endpoint configurations from markdown files."""
        try:
            loader = MarkdownConfigLoader(docs_path)
            self._endpoints = loader.load_endpoints(provider=self.PROVIDER_NAME)
            logger.debug(f"Loaded {len(self._endpoints)} Chicago endpoints")
        except Exception as e:
            logger.warning(f"Failed to load Chicago endpoint configs: {e}")

    def get_resource_id(self, endpoint_id: str) -> Optional[str]:
        """
        Get Socrata resource ID for an endpoint.

        Extracts the 4x4 ID from the endpoint_pattern.

        Args:
            endpoint_id: Endpoint identifier

        Returns:
            Resource ID or None if not found
        """
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            logger.warning(f"Unknown endpoint: {endpoint_id}")
            return None

        # Extract resource ID from pattern like "/resource/ijzp-q8t2.json"
        pattern = endpoint.endpoint_pattern
        if "/resource/" in pattern and ".json" in pattern:
            start = pattern.find("/resource/") + len("/resource/")
            end = pattern.find(".json")
            return pattern[start:end]

        return None

    def list_endpoints(self) -> List[str]:
        """List all available endpoint IDs."""
        return list(self._endpoints.keys())

    def get_endpoint_config(self, endpoint_id: str) -> Optional[EndpointConfig]:
        """Get configuration for an endpoint."""
        return self._endpoints.get(endpoint_id)

    def fetch_dataset(
        self,
        endpoint_id: str,
        query_params: Optional[Dict[str, Any]] = None,
        max_records: Optional[int] = None,
        progress_callback: Optional[callable] = None
    ) -> DatasetFetchResult:
        """
        Fetch a complete dataset from Chicago Data Portal.

        Args:
            endpoint_id: Endpoint identifier (e.g., "crimes", "building_permits")
            query_params: Additional SoQL query parameters
            max_records: Maximum records to fetch (None = all)
            progress_callback: Optional callback(batch_num, record_count)

        Returns:
            DatasetFetchResult with DataFrame or error
        """
        resource_id = self.get_resource_id(endpoint_id)
        if not resource_id:
            return DatasetFetchResult(
                endpoint_id=endpoint_id,
                success=False,
                error=f"Unknown endpoint: {endpoint_id}"
            )

        endpoint = self._endpoints[endpoint_id]

        # Merge default query with provided params
        params = dict(endpoint.default_query or {})
        if query_params:
            params.update(query_params)

        try:
            # Fetch all records with pagination
            all_records = []
            batch_num = 0

            for batch in self.client.fetch_all(
                resource_id=resource_id,
                query_params=params,
                limit=self.config.default_limit,
                max_records=max_records
            ):
                all_records.extend(batch)
                batch_num += 1

                if progress_callback:
                    progress_callback(batch_num, len(all_records))

            if not all_records:
                logger.warning(f"No records fetched for {endpoint_id}")
                return DatasetFetchResult(
                    endpoint_id=endpoint_id,
                    success=True,
                    record_count=0
                )

            # Convert to Spark DataFrame
            df = self._create_dataframe(all_records, endpoint)

            return DatasetFetchResult(
                endpoint_id=endpoint_id,
                success=True,
                record_count=len(all_records),
                df=df
            )

        except Exception as e:
            logger.error(f"Failed to fetch {endpoint_id}: {e}")
            return DatasetFetchResult(
                endpoint_id=endpoint_id,
                success=False,
                error=str(e)
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
        # If no schema defined, use inference
        if not endpoint.schema:
            return self.spark.createDataFrame(records, samplingRatio=1.0)

        # Build schema from endpoint config
        type_map = {
            'string': StringType(),
            'int': IntegerType(),
            'long': LongType(),
            'double': DoubleType(),
            'float': DoubleType(),
            'boolean': BooleanType(),
            'date': DateType(),
            'timestamp': TimestampType(),
        }

        fields = []
        for field_def in endpoint.schema:
            spark_type = type_map.get(field_def.type.lower(), StringType())
            fields.append(StructField(field_def.name, spark_type, field_def.nullable))

        schema = StructType(fields)

        # Map source fields to target fields
        transformed_records = []
        for record in records:
            transformed = {}
            for field_def in endpoint.schema:
                source_val = record.get(field_def.source)

                # Apply coercion if specified
                if source_val is not None and field_def.coerce:
                    source_val = self._coerce_value(source_val, field_def.coerce)

                transformed[field_def.name] = source_val

            transformed_records.append(transformed)

        # Create DataFrame
        df = self.spark.createDataFrame(transformed_records, schema)

        # Apply transforms
        df = self._apply_transforms(df, endpoint)

        return df

    def _coerce_value(self, value: Any, target_type: str) -> Any:
        """Coerce a value to target type."""
        if value is None:
            return None

        try:
            if target_type in ('double', 'float'):
                return float(value)
            elif target_type in ('int', 'integer'):
                return int(float(value))
            elif target_type in ('long', 'bigint'):
                return int(float(value))
            elif target_type == 'string':
                return str(value)
        except (ValueError, TypeError):
            return None

        return value

    def _apply_transforms(self, df: DataFrame, endpoint: EndpointConfig) -> DataFrame:
        """Apply field transforms from schema config."""
        for field_def in endpoint.schema:
            if not field_def.transform:
                continue

            col_name = field_def.name
            transform = field_def.transform

            try:
                if transform.startswith("zfill("):
                    # Zero-pad to N digits
                    n = int(transform[6:-1])
                    df = df.withColumn(col_name, F.lpad(F.col(col_name), n, "0"))

                elif transform.startswith("to_date("):
                    # Parse date with format
                    fmt = transform[8:-1]
                    df = df.withColumn(col_name, F.to_date(F.col(col_name), fmt))

                elif transform.startswith("to_timestamp("):
                    # Parse timestamp with format
                    fmt = transform[13:-1]
                    df = df.withColumn(col_name, F.to_timestamp(F.col(col_name), fmt))

            except Exception as e:
                logger.warning(f"Failed to apply transform {transform} to {col_name}: {e}")

        return df

    def write_to_bronze(
        self,
        df: DataFrame,
        endpoint_id: str,
        write_strategy: str = None
    ) -> Optional[str]:
        """
        Write DataFrame to Bronze layer.

        Uses endpoint config for table name, partitions, and key columns.

        Args:
            df: DataFrame to write
            endpoint_id: Endpoint identifier
            write_strategy: Override write strategy ('upsert', 'append', 'overwrite')

        Returns:
            Path to written data or None on failure
        """
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint or not endpoint.bronze:
            logger.error(f"No bronze config for endpoint: {endpoint_id}")
            return None

        bronze_cfg = endpoint.bronze
        table_name = bronze_cfg.table
        strategy = write_strategy or bronze_cfg.write_strategy or 'upsert'

        try:
            if strategy == 'upsert':
                path = self.sink.upsert(
                    df,
                    table_name,
                    key_columns=bronze_cfg.key_columns,
                    partitions=bronze_cfg.partitions or None
                )
            elif strategy == 'append':
                path = self.sink.append_immutable(
                    df,
                    table_name,
                    key_columns=bronze_cfg.key_columns,
                    partitions=bronze_cfg.partitions or None,
                    date_column=bronze_cfg.date_column
                )
            else:  # overwrite
                path = self.sink.overwrite(
                    df,
                    table_name,
                    partitions=bronze_cfg.partitions or None
                )

            logger.info(f"Wrote {df.count()} records to {table_name}")
            return path

        except Exception as e:
            logger.error(f"Failed to write to bronze: {e}")
            return None

    def ingest_endpoint(
        self,
        endpoint_id: str,
        query_params: Optional[Dict[str, Any]] = None,
        max_records: Optional[int] = None
    ) -> DatasetFetchResult:
        """
        Fetch and write a single endpoint to Bronze.

        Convenience method that combines fetch + write.

        Args:
            endpoint_id: Endpoint identifier
            query_params: Additional query parameters
            max_records: Maximum records to fetch

        Returns:
            DatasetFetchResult with status
        """
        # Fetch
        result = self.fetch_dataset(endpoint_id, query_params, max_records)

        if not result.success or result.df is None:
            return result

        # Write
        path = self.write_to_bronze(result.df, endpoint_id)
        if not path:
            result.success = False
            result.error = "Failed to write to Bronze"

        return result

    def ingest_all(
        self,
        endpoint_ids: Optional[List[str]] = None,
        max_records_per_endpoint: Optional[int] = None,
        silent: bool = False
    ) -> Dict[str, DatasetFetchResult]:
        """
        Ingest multiple endpoints.

        Args:
            endpoint_ids: List of endpoints to ingest (None = all active)
            max_records_per_endpoint: Limit per endpoint
            silent: Suppress progress output

        Returns:
            Dict mapping endpoint_id to result
        """
        if endpoint_ids is None:
            # Get all active endpoints
            endpoint_ids = [
                eid for eid, ep in self._endpoints.items()
                if ep.status == 'active'
            ]

        if not silent:
            print(f"\nIngesting {len(endpoint_ids)} Chicago endpoints...")

        results = {}
        for i, eid in enumerate(endpoint_ids):
            if not silent:
                print(f"  [{i+1}/{len(endpoint_ids)}] {eid}...", end=" ", flush=True)

            result = self.ingest_endpoint(eid, max_records=max_records_per_endpoint)
            results[eid] = result

            if not silent:
                if result.success:
                    print(f"✓ {result.record_count} records")
                else:
                    print(f"✗ {result.error}")

        return results


def create_chicago_provider(
    api_cfg: Dict[str, Any],
    storage_cfg: Dict,
    spark,
    docs_path: Optional[Path] = None
) -> ChicagoProvider:
    """
    Factory function to create a ChicagoProvider.

    Args:
        api_cfg: API configuration (from markdown loader)
        storage_cfg: Storage configuration
        spark: SparkSession
        docs_path: Path to Documents folder

    Returns:
        Configured ChicagoProvider
    """
    # Extract config from api_cfg
    base_url = api_cfg.get('base_urls', {}).get('core', 'https://data.cityofchicago.org')

    # Get app token from credentials
    credentials = api_cfg.get('credentials', {})
    api_keys = credentials.get('api_keys', [])
    app_token = api_keys[0] if api_keys else None

    config = ChicagoProviderConfig(
        base_url=base_url,
        app_token=app_token,
        rate_limit_per_sec=api_cfg.get('rate_limit_per_sec', 5.0)
    )

    return ChicagoProvider(
        config=config,
        spark=spark,
        storage_cfg=storage_cfg,
        docs_path=docs_path
    )
