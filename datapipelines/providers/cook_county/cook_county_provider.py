"""
Cook County Data Portal Provider Implementation.

Implements data ingestion from Cook County's Socrata Open Data API.
This provider fetches bulk datasets (property data, assessments, etc.).

v2.7 UNIFIED INTERFACE (January 2026):
- Implements BaseProvider unified interface
- Work items = endpoint IDs (e.g., "property_locations", "assessments")
- All writes go through IngestorEngine + StreamingBronzeWriter
- Removed duplicate ingest_endpoint/ingest_all methods

Features:
- Offset-based pagination for large datasets
- SoQL query support ($where, $select, $order, etc.)
- Rate limiting with app token support
- Schema-driven transformation using markdown configs
- PIN-based property lookups

Usage:
    from datapipelines.providers.cook_county import create_cook_county_provider
    from datapipelines.base.ingestor_engine import IngestorEngine

    provider = create_cook_county_provider(config, storage_cfg, spark, docs_path)
    engine = IngestorEngine(provider, storage_cfg)

    # Ingest all endpoints
    results = engine.run(write_batch_size=500000)

    # Ingest specific endpoints
    results = engine.run(work_items=["property_locations", "assessments"])

Author: de_Funk Team
Date: January 2026
Updated: January 2026 - Unified interface implementation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Generator
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

from datapipelines.base.provider import BaseProvider, ProviderConfig
from datapipelines.base.socrata_client import SocrataClient
from datapipelines.ingestors.bronze_sink import BronzeSink
from config.logging import get_logger
from config.markdown_loader import MarkdownConfigLoader, EndpointConfig

logger = get_logger(__name__)


@dataclass
class CookCountyProviderConfig:
    """Configuration for Cook County Data Portal provider."""
    base_url: str = "https://datacatalog.cookcountyil.gov"
    app_token: Optional[str] = None
    rate_limit_per_sec: float = 5.0
    default_limit: int = 50000
    timeout: int = 120


class CookCountyProvider(BaseProvider):
    """
    Provider for Cook County Data Portal (Socrata API).

    Implements the unified BaseProvider interface (v2.7).
    Work items are endpoint IDs (e.g., "property_locations", "assessments").
    """

    PROVIDER_ID = "cook_county_data_portal"
    PROVIDER_NAME = "Cook County Data Portal"

    def __init__(
        self,
        provider_config: CookCountyProviderConfig,
        spark,
        storage_cfg: Dict,
        docs_path: Optional[Path] = None
    ):
        """
        Initialize Cook County provider.

        Args:
            provider_config: Provider-specific configuration
            spark: SparkSession
            storage_cfg: Storage configuration for Bronze paths
            docs_path: Path to Documents folder (for loading endpoint configs)
        """
        self._provider_config = provider_config
        self.spark = spark
        self.storage_cfg = storage_cfg
        self.sink = BronzeSink(storage_cfg)

        # Create ProviderConfig for BaseProvider compatibility
        self.config = ProviderConfig(
            name=self.PROVIDER_ID,
            base_url=provider_config.base_url,
            rate_limit=provider_config.rate_limit_per_sec,
        )

        # Initialize Socrata client
        self.client = SocrataClient(
            base_url=provider_config.base_url,
            app_token=provider_config.app_token,
            rate_limit_per_sec=provider_config.rate_limit_per_sec,
            timeout=provider_config.timeout
        )

        # Load endpoint configs from markdown
        self._endpoints: Dict[str, EndpointConfig] = {}
        if docs_path:
            self._load_endpoint_configs(docs_path)

        logger.info(
            f"CookCountyProvider initialized: {len(self._endpoints)} endpoints, "
            f"rate_limit={provider_config.rate_limit_per_sec}"
        )

    def _setup(self) -> None:
        """Setup is done in __init__ for this provider."""
        pass

    def _load_endpoint_configs(self, docs_path: Path) -> None:
        """Load endpoint configurations from markdown files."""
        try:
            loader = MarkdownConfigLoader(docs_path)
            self._endpoints = loader.load_endpoints(provider=self.PROVIDER_NAME)
            logger.debug(f"Loaded {len(self._endpoints)} Cook County endpoints")
        except Exception as e:
            logger.warning(f"Failed to load Cook County endpoint configs: {e}")

    # =========================================================================
    # UNIFIED INTERFACE IMPLEMENTATION (v2.7)
    # =========================================================================

    def list_work_items(self, status: str = 'active', **kwargs) -> List[str]:
        """
        List available endpoint IDs for ingestion.

        Args:
            status: Filter by endpoint status ('active', 'all')
            **kwargs: Additional filters

        Returns:
            List of endpoint IDs
        """
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
        """
        Fetch data for an endpoint, yielding batches of records.

        Handles both single-resource and multi-year (view_id) endpoints.

        Args:
            work_item: Endpoint ID (e.g., "property_locations")
            max_records: Maximum records to fetch (None = no limit)
            **kwargs: Additional query parameters

        Yields:
            List[Dict] - Batches of raw records
        """
        endpoint = self._endpoints.get(work_item)
        if not endpoint:
            logger.warning(f"Unknown endpoint: {work_item}")
            return

        # Check if this is a multi-year endpoint with view_ids
        if endpoint.view_ids:
            yield from self._fetch_multi_year(endpoint, max_records, **kwargs)
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

        # Merge default query with provided params
        params = dict(endpoint.default_query or {})

        for batch in self.client.fetch_all(
            resource_id=resource_id,
            query_params=params,
            limit=self._provider_config.default_limit,
            max_records=max_records
        ):
            yield batch

    def _fetch_multi_year(
        self,
        endpoint: EndpointConfig,
        max_records: Optional[int] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """Fetch from multiple year-based view_ids."""
        params = dict(endpoint.default_query or {})

        for view_id_entry in endpoint.view_ids:
            year = view_id_entry.get('year')
            resource_id = view_id_entry.get('view_id')

            if not resource_id:
                continue

            logger.info(f"Fetching year {year} from {resource_id}")

            for batch in self.client.fetch_all(
                resource_id=resource_id,
                query_params=params,
                limit=self._provider_config.default_limit,
                max_records=max_records
            ):
                # Add year to each record for partitioning
                for record in batch:
                    record['year'] = year
                yield batch

    def normalize(self, records: List[Dict], work_item: str) -> DataFrame:
        """
        Normalize raw records to a Spark DataFrame.

        Args:
            records: List of raw record dicts from API
            work_item: Endpoint ID

        Returns:
            Spark DataFrame with proper schema
        """
        endpoint = self._endpoints.get(work_item)
        if not endpoint:
            # Fallback: create DataFrame with schema inference
            return self.spark.createDataFrame(records, samplingRatio=1.0)

        return self._create_dataframe(records, endpoint)

    def get_table_name(self, work_item: str) -> str:
        """Get Bronze table name for an endpoint."""
        endpoint = self._endpoints.get(work_item)
        if endpoint and endpoint.bronze:
            return endpoint.bronze.table
        # Default: use endpoint_id as table name
        return f"cook_county_{work_item}"

    def get_partitions(self, work_item: str) -> Optional[List[str]]:
        """Get partition columns for an endpoint."""
        endpoint = self._endpoints.get(work_item)
        if endpoint and endpoint.bronze:
            return endpoint.bronze.partitions or None
        return None

    def get_key_columns(self, work_item: str) -> List[str]:
        """Get key columns for upsert operations."""
        endpoint = self._endpoints.get(work_item)
        if endpoint and endpoint.bronze:
            return endpoint.bronze.key_columns or []
        return []

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

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

    def get_endpoint_config(self, endpoint_id: str) -> Optional[EndpointConfig]:
        """Get configuration for an endpoint."""
        return self._endpoints.get(endpoint_id)

    def _safe_parse_date(self, col_val):
        """
        Normalize date strings to yyyy-MM-dd format for ANSI-safe parsing.
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

        return F.to_date(normalized, "yyyy-MM-dd")

    def _safe_parse_timestamp(self, col_val):
        """
        Normalize timestamp strings for ANSI-safe parsing.
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

        return F.to_timestamp(normalized, "yyyy-MM-dd HH:mm:ss")

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

        # Map source fields to target fields (keep as strings initially)
        transformed_records = []
        for record in records:
            transformed = {}
            for field_def in endpoint.schema:
                source_val = record.get(field_def.source)
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
                    F.col(field_def.name).try_cast('double').cast(target_type))
            elif target_type in ('double', 'float'):
                df = df.withColumn(field_def.name, F.col(field_def.name).try_cast('double'))
            elif target_type == 'date':
                df = df.withColumn(field_def.name,
                    self._safe_parse_date(F.col(field_def.name)))
            elif target_type == 'timestamp':
                df = df.withColumn(field_def.name,
                    self._safe_parse_timestamp(F.col(field_def.name)))
            elif target_type == 'boolean':
                df = df.withColumn(field_def.name, F.col(field_def.name).cast('boolean'))

        return df

    # =========================================================================
    # PIN-BASED LOOKUP (Cook County specific)
    # =========================================================================

    def fetch_parcel_data(
        self,
        pins: Optional[List[str]] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """
        Fetch parcel data for specific PINs.

        This is a convenience method for property-specific lookups.

        Args:
            pins: List of Property Index Numbers (PINs)
            **kwargs: Additional query parameters

        Yields:
            List[Dict] - Batches of parcel records
        """
        if not pins:
            return

        # Find the property_locations endpoint
        endpoint = self._endpoints.get("property_locations")
        if not endpoint:
            logger.warning("property_locations endpoint not configured")
            return

        resource_id = self._get_resource_id(endpoint)
        if not resource_id:
            return

        # Build PIN filter
        pin_list = ",".join(f"'{p}'" for p in pins)
        params = {"$where": f"pin IN ({pin_list})"}

        for batch in self.client.fetch_all(
            resource_id=resource_id,
            query_params=params,
            limit=self._provider_config.default_limit
        ):
            yield batch


def create_cook_county_provider(
    api_cfg: Dict[str, Any],
    storage_cfg: Dict,
    spark,
    docs_path: Optional[Path] = None
) -> CookCountyProvider:
    """
    Factory function to create a CookCountyProvider.

    Args:
        api_cfg: API configuration (from markdown loader)
        storage_cfg: Storage configuration
        spark: SparkSession
        docs_path: Path to Documents folder

    Returns:
        Configured CookCountyProvider
    """
    base_url = api_cfg.get('base_urls', {}).get('core', 'https://datacatalog.cookcountyil.gov')

    credentials = api_cfg.get('credentials', {})
    api_keys = credentials.get('api_keys', [])
    app_token = api_keys[0] if api_keys else None

    config = CookCountyProviderConfig(
        base_url=base_url,
        app_token=app_token,
        rate_limit_per_sec=api_cfg.get('rate_limit_per_sec', 5.0)
    )

    return CookCountyProvider(
        provider_config=config,
        spark=spark,
        storage_cfg=storage_cfg,
        docs_path=docs_path
    )
