"""Base service abstractions for domain APIs"""

from abc import ABC
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from de_funk.models.api.session import UniversalSession


class BaseAPI(ABC):
    """
    Base class for domain APIs.

    Domain APIs provide typed, high-level access to model data.
    They wrap UniversalSession operations with domain-specific logic.

    Usage:
        class PricesAPI(BaseAPI):
            def get_prices(self, ticker: str):
                df = self._get_table('fact_prices')
                # Apply filters using connection-specific methods
                return self._apply_filters(df, {'ticker': ticker})
    """

    def __init__(self, session: 'UniversalSession', model_name: str):
        """
        Initialize API.

        Args:
            session: UniversalSession instance
            model_name: Name of the model this API operates on

        Raises:
            TypeError: If session is not a UniversalSession
        """
        # Enforce UniversalSession only (no backwards compatibility)
        from de_funk.models.api.session import UniversalSession
        if not isinstance(session, UniversalSession):
            raise TypeError(
                f"BaseAPI requires UniversalSession, got {type(session).__name__}. "
                "ModelSession is deprecated and no longer supported."
            )

        self.session = session
        self.model_name = model_name

    def _get_table(self, table_name: str):
        """
        Get table from model via UniversalSession.

        Args:
            table_name: Table identifier (e.g., 'fact_prices', 'dim_company')

        Returns:
            DataFrame from the model
        """
        return self.session.get_table(self.model_name, table_name)

    def _apply_filters(self, df, filters: Dict[str, Any]):
        """
        Apply filters to DataFrame using connection-specific logic.

        Delegates to the connection's apply_filters method, which handles
        backend-specific filter application (Spark vs DuckDB).

        Args:
            df: Input DataFrame
            filters: Filter specifications (dict mapping column names to values/conditions)

        Returns:
            Filtered DataFrame

        Raises:
            AttributeError: If connection doesn't support apply_filters
        """
        if hasattr(self.session.connection, 'apply_filters'):
            return self.session.connection.apply_filters(df, filters)
        else:
            raise AttributeError(
                f"Connection {type(self.session.connection).__name__} "
                "does not support apply_filters method"
            )
