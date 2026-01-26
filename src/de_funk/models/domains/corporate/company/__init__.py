"""
Company model - corporate legal entities.

Provides:
- CompanyModel: Domain model for company data (CIK-based)
- CompanyBuilder: Builder for company silver layer
"""

from .model import CompanyModel
from .builder import CompanyBuilder

__all__ = ['CompanyModel', 'CompanyBuilder']
