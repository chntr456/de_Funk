"""
Chicago Data Portal Provider Implementation.

Implements the BaseProvider interface for Chicago Data Portal (Socrata) API.
Supports city-level data including budget, unemployment, building permits, etc.

Features:
- Socrata API integration with offset-based pagination
- Multiple endpoints per fiscal year → single partitioned table
- No ticker-based data (city-level datasets)

Usage:
    from datapipelines.providers.chicago.provider import ChicagoProvider
    from datapipelines.base.provider import ProviderConfig

    config = ProviderConfig(
        name="chicago",
        base_url="https://data.cityofchicago.org",
        rate_limit=5.0,
    )
    provider = ChicagoProvider(config, spark=spark_session)

Author: de_Funk Team
Date: January 2026
"""

from __future__ import annotations

import threading
from enum import Enum
from typing import List, Optional, Callable, Any, Dict

from datapipelines.base.provider import (
    BaseProvider, DataType, TickerData, ProviderConfig, FetchResult
)
from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool
from config.logging import get_logger

logger = get_logger(__name__)


class ChicagoDataType(Enum):
    """Data types available from Chicago Data Portal."""
    BUDGET = "budget"
    UNEMPLOYMENT = "unemployment"
    BUILDING_PERMITS = "building_permits"
    BUSINESS_LICENSES = "business_licenses"
    ECONOMIC_INDICATORS = "economic_indicators"
    AFFORDABLE_HOUSING = "affordable_housing"
    PER_CAPITA_INCOME = "per_capita_income"


class ChicagoProvider(BaseProvider):
    """
    Chicago Data Portal implementation of BaseProvider.

    Handles all API interactions with Chicago's Socrata API including:
    - Budget data (multiple fiscal years → single table)
    - Unemployment statistics
    - Building permits
    - Business licenses
    - Economic indicators
    """

    # Map ChicagoDataType to Bronze table names (must match storage.json)
    TABLE_NAMES = {
        ChicagoDataType.BUDGET: "chicago_budget",
        ChicagoDataType.UNEMPLOYMENT: "chicago_unemployment",
        ChicagoDataType.BUILDING_PERMITS: "chicago_building_permits",
        ChicagoDataType.BUSINESS_LICENSES: "chicago_business_licenses",
        ChicagoDataType.ECONOMIC_INDICATORS: "chicago_economic_indicators",
        ChicagoDataType.AFFORDABLE_HOUSING: "chicago_affordable_housing",
        ChicagoDataType.PER_CAPITA_INCOME: "chicago_per_capita_income",
    }

    # Key columns for upsert (must match storage.json)
    KEY_COLUMNS = {
        ChicagoDataType.BUDGET: ["fund_code", "department_code", "fiscal_year"],
        ChicagoDataType.UNEMPLOYMENT: ["community_area", "period"],
        ChicagoDataType.BUILDING_PERMITS: ["permit_id"],
        ChicagoDataType.BUSINESS_LICENSES: ["license_id"],
        ChicagoDataType.ECONOMIC_INDICATORS: ["indicator", "date"],
        ChicagoDataType.AFFORDABLE_HOUSING: ["property_id"],
        ChicagoDataType.PER_CAPITA_INCOME: ["community_area_number"],
    }

    def __init__(
        self,
        config: ProviderConfig,
        spark=None,
        chicago_cfg: Dict = None
    ):
        """
        Initialize Chicago provider.

        Args:
            config: Provider configuration
            spark: SparkSession
            chicago_cfg: Raw Chicago endpoints config dict
        """
        self._chicago_cfg = chicago_cfg or {}
        super().__init__(config, spark)

    def _setup(self) -> None:
        """Setup HTTP client and API key pool."""
        from .chicago_registry import ChicagoRegistry

        # Create registry from config
        self.registry = ChicagoRegistry(self._chicago_cfg)

        # Create API key pool (optional for Socrata)
        credentials = self._chicago_cfg.get("credentials", {})
        api_keys = credentials.get("api_keys", [])
        self.key_pool = ApiKeyPool(api_keys, cooldown_seconds=60.0) if api_keys else None

        # Create HTTP client
        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.config.rate_limit,
            self.key_pool
        )

        # Thread lock for HTTP requests
        self._http_lock = threading.Lock()

    def fetch_endpoint_data(
        self,
        endpoint_name: str,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> FetchResult:
        """
        Fetch data for a specific endpoint.

        Args:
            endpoint_name: Name of the endpoint (e.g., 'budget_fy2024')
            progress_callback: Optional callback for progress
            **kwargs: Additional query parameters

        Returns:
            FetchResult with data or error
        """
        try:
            # Render endpoint
            ep, path, query = self.registry.render(endpoint_name, **kwargs)

            # Add app token if available
            if self.key_pool:
                api_key = self.key_pool.next_key()
                if api_key:
                    query["$$app_token"] = api_key

            # Make request
            with self._http_lock:
                payload = self.http.request(ep.base, path, query, ep.method)

            # Socrata returns list of records directly
            if not isinstance(payload, list):
                return FetchResult(
                    ticker=endpoint_name,
                    data_type=DataType.REFERENCE,  # Placeholder
                    success=False,
                    error=f"Unexpected response type: {type(payload)}"
                )

            return FetchResult(
                ticker=endpoint_name,
                data_type=DataType.REFERENCE,
                success=True,
                data=payload,
                api_calls=1
            )

        except Exception as e:
            logger.error(f"Failed to fetch {endpoint_name}: {e}")
            return FetchResult(
                ticker=endpoint_name,
                data_type=DataType.REFERENCE,
                success=False,
                error=str(e)[:100]
            )

    def fetch_ticker_data(
        self,
        ticker: str,
        data_types: List[DataType],
        progress_callback: Optional[Callable[[str, DataType, bool, Optional[str]], None]] = None,
        **kwargs
    ) -> TickerData:
        """
        Fetch data - for Chicago, ticker is actually the endpoint name.

        Note: Chicago data is city-level, not ticker-level. The 'ticker'
        parameter is used as an endpoint identifier.
        """
        result = TickerData(ticker=ticker)

        # For Chicago, we treat 'ticker' as endpoint name
        fetch_result = self.fetch_endpoint_data(ticker, **kwargs)

        if fetch_result.success:
            result.reference = fetch_result.data
        else:
            result.errors.append(fetch_result.error or "Unknown error")

        return result

    def normalize_data(
        self,
        ticker_data: TickerData,
        data_type: DataType,
        endpoint_config: Dict = None
    ) -> Optional[Any]:
        """
        Normalize raw data to a Spark DataFrame.

        Args:
            ticker_data: TickerData from fetch_ticker_data
            data_type: Data type to normalize
            endpoint_config: Endpoint configuration with metadata

        Returns:
            Spark DataFrame or None
        """
        endpoint_name = ticker_data.ticker
        raw_data = ticker_data.reference

        if not raw_data:
            return None

        # Get endpoint config if not provided
        if not endpoint_config:
            endpoint_config = self._chicago_cfg.get("endpoints", {}).get(endpoint_name, {})

        # Determine facet based on endpoint name
        facet = self._get_facet_for_endpoint(endpoint_name, endpoint_config)
        if not facet:
            logger.warning(f"No facet found for endpoint: {endpoint_name}")
            return None

        try:
            return facet.normalize(raw_data, endpoint_config)
        except Exception as e:
            logger.warning(f"Failed to normalize {endpoint_name}: {e}")
            return None

    def _get_facet_for_endpoint(self, endpoint_name: str, endpoint_config: Dict):
        """Get the appropriate facet for an endpoint."""
        from .facets.budget_facet import BudgetFacet
        from .facets.unemployment_facet import UnemploymentFacet
        from .facets.building_permits_facet import BuildingPermitsFacet
        from .facets.business_licenses_facet import BusinessLicensesFacet

        # Budget endpoints all use BudgetFacet
        if endpoint_name.startswith("budget_fy"):
            return BudgetFacet(self.spark)

        # Map other endpoints to facets
        facet_map = {
            "unemployment_rates": UnemploymentFacet,
            "building_permits": BuildingPermitsFacet,
            "business_licenses": BusinessLicensesFacet,
        }

        facet_class = facet_map.get(endpoint_name)
        if facet_class:
            return facet_class(self.spark)

        return None

    def get_bronze_table_name(self, data_type: DataType) -> str:
        """Get bronze table name for a data type."""
        # For Chicago, we override this based on endpoint metadata
        return "chicago_data"

    def get_bronze_table_name_for_endpoint(self, endpoint_name: str) -> str:
        """Get bronze table name for a specific endpoint."""
        endpoint_config = self._chicago_cfg.get("endpoints", {}).get(endpoint_name, {})
        metadata = endpoint_config.get("metadata", {})

        # Check if metadata specifies table name
        if "table_name" in metadata:
            return metadata["table_name"]

        # Default mappings
        if endpoint_name.startswith("budget_fy"):
            return "chicago_budget"

        endpoint_to_table = {
            "unemployment_rates": "chicago_unemployment",
            "building_permits": "chicago_building_permits",
            "business_licenses": "chicago_business_licenses",
            "economic_indicators": "chicago_economic_indicators",
            "affordable_rental_housing": "chicago_affordable_housing",
            "per_capita_income": "chicago_per_capita_income",
        }

        return endpoint_to_table.get(endpoint_name, f"chicago_{endpoint_name}")

    def get_key_columns(self, data_type: DataType) -> List[str]:
        """Get key columns for upsert."""
        return ["id"]  # Default

    def get_key_columns_for_endpoint(self, endpoint_name: str) -> List[str]:
        """Get key columns for a specific endpoint."""
        if endpoint_name.startswith("budget_fy"):
            return ["fund_code", "department_code", "fiscal_year"]

        endpoint_to_keys = {
            "unemployment_rates": ["community_area", "year", "month"],
            "building_permits": ["id"],
            "business_licenses": ["id"],
            "economic_indicators": ["indicator_type", "date"],
        }

        return endpoint_to_keys.get(endpoint_name, ["id"])

    def get_available_endpoints(self) -> List[str]:
        """Get list of available endpoints."""
        return list(self._chicago_cfg.get("endpoints", {}).keys())

    def get_budget_endpoints(self) -> List[str]:
        """Get list of budget fiscal year endpoints."""
        return [ep for ep in self.get_available_endpoints() if ep.startswith("budget_fy")]


def create_chicago_provider(
    chicago_cfg: Dict,
    spark=None
) -> ChicagoProvider:
    """
    Factory function to create a ChicagoProvider.

    Args:
        chicago_cfg: Chicago endpoints configuration
        spark: SparkSession

    Returns:
        Configured ChicagoProvider
    """
    config = ProviderConfig(
        name="chicago",
        base_url=chicago_cfg.get("base_urls", {}).get("core", "https://data.cityofchicago.org"),
        rate_limit=chicago_cfg.get("rate_limit_per_sec", 5.0),
        batch_size=1,  # City-level data, process one endpoint at a time
        credentials_env_var="CHICAGO_API_KEYS",
    )

    return ChicagoProvider(
        config=config,
        spark=spark,
        chicago_cfg=chicago_cfg
    )
