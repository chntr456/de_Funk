"""News data types for company model"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class NewsItem:
    """News article with company context"""
    publish_date: str
    ticker: str
    title: str
    source: Optional[str]
    sentiment: Optional[str]
    company_name: Optional[str] = None
    exchange_code: Optional[str] = None
