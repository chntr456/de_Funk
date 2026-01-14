"""
Economic domain - macroeconomic indicators.

Models:
- macro: BLS economic indicators (unemployment, CPI, employment, wages)
"""

from .macro import MacroModel

__all__ = ['MacroModel']
