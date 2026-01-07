"""
Chicago Data Portal Endpoint Registry.

Renders endpoint configurations from chicago_endpoints.json into
callable endpoint specifications.

Author: de_Funk Team
Date: January 2026
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Tuple

from config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Endpoint:
    """Rendered endpoint specification."""
    name: str
    base: str
    method: str
    path: str
    query: Dict[str, Any]
    headers: Dict[str, str]
    metadata: Dict[str, Any]


class ChicagoRegistry:
    """
    Registry for Chicago Data Portal endpoints.

    Handles endpoint rendering with path templates, default queries,
    and metadata for multi-year budget pattern.
    """

    def __init__(self, config: Dict = None):
        """
        Initialize registry with configuration.

        Args:
            config: Chicago endpoints configuration dict
        """
        self.config = config or {}
        self.base_urls = self.config.get("base_urls", {
            "core": "https://data.cityofchicago.org"
        })
        self.headers = self.config.get("headers", {
            "Content-Type": "application/json"
        })
        self._endpoints = self.config.get("endpoints", {})

    def render(
        self,
        endpoint_name: str,
        **kwargs
    ) -> Tuple[Endpoint, str, Dict]:
        """
        Render an endpoint with parameters.

        Args:
            endpoint_name: Name of the endpoint to render
            **kwargs: Override parameters (query params, path params)

        Returns:
            Tuple of (Endpoint, path, query_params)
        """
        if endpoint_name not in self._endpoints:
            raise KeyError(f"Unknown endpoint: {endpoint_name}")

        ep_cfg = self._endpoints[endpoint_name]

        # Resolve base URL
        base_key = ep_cfg.get("base", "core")
        base_url = self.base_urls.get(base_key, self.base_urls.get("core"))

        # Build path from template
        path_template = ep_cfg.get("path_template", "")
        default_path_params = ep_cfg.get("default_path_params", {})
        path_params = {**default_path_params, **kwargs.get("path_params", {})}

        try:
            path = path_template.format(**path_params) if path_params else path_template
        except KeyError as e:
            logger.warning(f"Missing path param for {endpoint_name}: {e}")
            path = path_template

        # Build query params
        default_query = ep_cfg.get("default_query", {})
        query_overrides = kwargs.get("query", {})
        query = {**default_query, **query_overrides}

        # Add any direct kwargs that aren't special keys
        special_keys = {"path_params", "query"}
        for key, value in kwargs.items():
            if key not in special_keys:
                query[key] = value

        # Create endpoint object
        endpoint = Endpoint(
            name=endpoint_name,
            base=base_key,
            method=ep_cfg.get("method", "GET"),
            path=path,
            query=query,
            headers={**self.headers, **ep_cfg.get("headers", {})},
            metadata=ep_cfg.get("metadata", {})
        )

        return endpoint, path, query

    def get_endpoint_config(self, endpoint_name: str) -> Dict:
        """Get raw endpoint configuration."""
        return self._endpoints.get(endpoint_name, {})

    def get_metadata(self, endpoint_name: str) -> Dict:
        """Get metadata for an endpoint (e.g., fiscal_year for budget)."""
        return self._endpoints.get(endpoint_name, {}).get("metadata", {})

    def get_table_name(self, endpoint_name: str) -> str:
        """Get target Bronze table name from metadata."""
        metadata = self.get_metadata(endpoint_name)
        return metadata.get("table_name", f"chicago_{endpoint_name}")

    def list_endpoints(self) -> list:
        """List all available endpoint names."""
        return list(self._endpoints.keys())

    def list_budget_endpoints(self) -> list:
        """List all budget fiscal year endpoints."""
        return [ep for ep in self._endpoints.keys() if ep.startswith("budget_fy")]
