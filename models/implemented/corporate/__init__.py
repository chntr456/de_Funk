"""
Corporate model - Corporate entities and fundamentals.

This model represents legal business entities (companies) with SEC filings,
financial statements, and fundamental data.

For trading data (prices, volume, technical indicators), see the equity model.
"""

from .model import CorporateModel

__all__ = ['CorporateModel']
