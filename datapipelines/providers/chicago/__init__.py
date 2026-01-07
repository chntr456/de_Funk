"""
Chicago Data Portal Provider.

Provides access to Chicago city data through the Socrata API.
Supports multiple endpoint types including budget data by fiscal year.

Features:
- Multi-year budget endpoints → single partitioned table
- Unemployment, building permits, business licenses
- Socrata API with offset pagination

Usage:
    from datapipelines.providers.chicago.provider import (
        ChicagoProvider,
        create_chicago_provider
    )

    provider = create_chicago_provider(chicago_cfg, spark)
    result = provider.fetch_endpoint_data("budget_fy2024")

Author: de_Funk Team
Date: January 2026
"""

from .provider import ChicagoProvider, create_chicago_provider
from .chicago_registry import ChicagoRegistry

__all__ = [
    "ChicagoProvider",
    "create_chicago_provider",
    "ChicagoRegistry",
]
