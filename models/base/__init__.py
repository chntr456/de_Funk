"""Base model abstractions"""
from models.base.model import BaseModel
from models.base.parquet_loader import ParquetLoader

__all__ = ['BaseModel', 'ParquetLoader']
