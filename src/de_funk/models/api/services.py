"""
Backward compatibility layer for services.

Note: Legacy services (NewsAPI, PricesAPI, CompanyAPI) have been deprecated
as part of the v2.6 domain reorganization. The company model now uses
standard model patterns without separate service classes.

This file is kept for backward compatibility but exports nothing.
"""

from __future__ import annotations

# Legacy services removed in v2.6 domain reorganization
# Use models.domains.corporate.company.CompanyModel directly

__all__ = []
