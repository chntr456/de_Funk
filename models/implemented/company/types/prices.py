"""Price data types for company model"""
from dataclasses import dataclass


@dataclass
class PriceBar:
    """Daily price bar for a stock"""
    trade_date: str
    ticker: str
    open: float
    high: float
    low: float
    close: float
    volume_weighted: float
    volume: float
