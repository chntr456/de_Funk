"""Base service abstractions for domain APIs"""

from abc import ABC
from typing import Dict, Any


class BaseAPI(ABC):
    """
    Base class for domain APIs.

    Domain APIs provide typed, high-level access to model data.
    They wrap model session operations with domain-specific logic.

    Usage:
        class PricesAPI(BaseAPI):
            def get_prices(self, ticker: str):
                df = self._get_table('fact_prices')
                return df.filter(df.ticker == ticker)
    """

    def __init__(self, session, model_name: str):
        """
        Initialize API.

        Args:
            session: UniversalSession or ModelSession
            model_name: Name of the model this API operates on
        """
        self.session = session
        self.model_name = model_name

    def _get_table(self, table_name: str):
        """
        Helper to get table from model.

        Args:
            table_name: Table identifier

        Returns:
            DataFrame
        """
        # Support both UniversalSession and ModelSession
        if hasattr(self.session, 'get_table'):
            return self.session.get_table(self.model_name, table_name)
        else:
            # Legacy ModelSession
            if table_name.startswith('dim_'):
                dims, _ = self.session.ensure_built()
                return dims[table_name]
            else:
                _, facts = self.session.ensure_built()
                return facts[table_name]

    def _apply_filters(self, df, filters: Dict[str, Any]):
        """
        Apply filters to DataFrame.

        Args:
            df: Input DataFrame
            filters: Filter specifications

        Returns:
            Filtered DataFrame
        """
        # Delegate to connection if available
        if hasattr(self.session, 'connection'):
            return self.session.connection.apply_filters(df, filters)
        else:
            # Manual filtering (Spark)
            from pyspark.sql import functions as F
            for col_name, value in filters.items():
                if isinstance(value, dict):
                    # Range filter
                    if 'min' in value:
                        df = df.filter(F.col(col_name) >= value['min'])
                    if 'max' in value:
                        df = df.filter(F.col(col_name) <= value['max'])
                elif isinstance(value, list):
                    # IN filter
                    df = df.filter(F.col(col_name).isin(value))
                else:
                    # Exact match
                    df = df.filter(F.col(col_name) == value)
            return df
