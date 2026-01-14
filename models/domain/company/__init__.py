"""
Company model - BACKWARD COMPATIBILITY LAYER.

DEPRECATED: Import from models.domains.corporate.company instead.

Example:
    # Old (deprecated)
    from models.domain.company import CompanyModel

    # New (recommended)
    from models.domains.corporate.company import CompanyModel
"""

from models.domains.corporate.company import CompanyModel, CompanyBuilder

__all__ = ['CompanyModel', 'CompanyBuilder']
