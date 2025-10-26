from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class NewsItem:
    publish_date: str
    ticker: str
    title: str
    source: Optional[str]
    sentiment: Optional[str]
    company_name: Optional[str] = None
    exchange_code: Optional[str] = None

@dataclass
class PriceBar:
    trade_date: str
    ticker: str
    open: float
    high: float
    low: float
    close: float
    volume_weighted: float
    volume: float
