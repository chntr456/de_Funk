"""
Corporate domain - legal business entities.

Models:
- company: Corporate entities with SEC registration (CIK-based)
"""

from .company import CompanyModel, CompanyBuilder

__all__ = ['CompanyModel', 'CompanyBuilder']
