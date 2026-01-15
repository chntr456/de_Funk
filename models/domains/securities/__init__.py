"""
Securities domain - tradable financial instruments.

Models:
- stocks: Common stock equities with prices and technicals

Future models (not yet implemented):
- options: Options contracts with Greeks and Black-Scholes pricing
- etfs: Exchange-traded funds with holdings
- futures: Futures contracts
"""

from .stocks import StocksModel

__all__ = [
    'StocksModel',
]
