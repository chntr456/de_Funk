"""
Connection layer abstraction for data access.

Provides interface for different backend connections (Spark, DuckDB, graph DB, etc.)
Currently implements Spark, but designed for future extensibility.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path
import pandas as pd


class DataConnection(ABC):
    """
    Abstract base class for data connections.

    Future implementations:
    - SparkConnection (current)
    - DuckDBConnection
    - GraphDBConnection (Neo4j, etc.)
    - ArrowConnection
    """

    @abstractmethod
    def read_table(self, path: str, format: str = "parquet") -> Any:
        """
        Read a table from storage.

        Args:
            path: Path to table
            format: Format (parquet, delta, csv, etc.)

        Returns:
            DataFrame-like object (specific to connection type)
        """
        pass

    @abstractmethod
    def apply_filters(self, df: Any, filters: Dict[str, Any]) -> Any:
        """
        Apply filters to a dataframe.

        Args:
            df: DataFrame-like object
            filters: Dict of column -> value/condition

        Returns:
            Filtered dataframe
        """
        pass

    @abstractmethod
    def to_pandas(self, df: Any) -> pd.DataFrame:
        """
        Convert to Pandas DataFrame.

        Args:
            df: DataFrame-like object

        Returns:
            Pandas DataFrame
        """
        pass

    @abstractmethod
    def count(self, df: Any) -> int:
        """Get row count."""
        pass

    @abstractmethod
    def cache(self, df: Any) -> Any:
        """Cache dataframe in memory."""
        pass

    @abstractmethod
    def uncache(self, df: Any):
        """Remove from cache."""
        pass

    @abstractmethod
    def stop(self):
        """Close connection and cleanup resources."""
        pass


class SparkConnection(DataConnection):
    """
    Spark-based data connection.

    Current implementation using PySpark.
    """

    def __init__(self, spark_session):
        """
        Initialize Spark connection.

        Args:
            spark_session: PySpark SparkSession
        """
        self.spark = spark_session
        self._cached_dfs = []

    def read_table(self, path: str, format: str = "parquet"):
        """Read table using Spark."""
        return self.spark.read.format(format).load(path)

    def apply_filters(self, df, filters: Dict[str, Any]):
        """Apply filters using Spark SQL."""
        from pyspark.sql import functions as F

        for column, value in filters.items():
            if isinstance(value, dict):
                # Handle date range
                if 'start' in value and 'end' in value:
                    start = value['start']
                    end = value['end']

                    # Convert datetime to string if needed
                    if hasattr(start, 'strftime'):
                        start = start.strftime('%Y-%m-%d')
                    if hasattr(end, 'strftime'):
                        end = end.strftime('%Y-%m-%d')

                    df = df.filter((F.col(column) >= start) & (F.col(column) <= end))

            elif isinstance(value, list):
                # Handle list of values
                if value:  # Only filter if list is not empty
                    df = df.filter(F.col(column).isin(value))

            else:
                # Handle single value
                df = df.filter(F.col(column) == value)

        return df

    def to_pandas(self, df) -> pd.DataFrame:
        """Convert Spark DataFrame to Pandas."""
        return df.toPandas()

    def count(self, df) -> int:
        """Get row count."""
        return df.count()

    def cache(self, df):
        """Cache Spark DataFrame."""
        df.cache()
        self._cached_dfs.append(df)
        return df

    def uncache(self, df):
        """Uncache Spark DataFrame."""
        df.unpersist()
        if df in self._cached_dfs:
            self._cached_dfs.remove(df)

    def stop(self):
        """Stop Spark session and cleanup."""
        # Unpersist all cached dataframes
        for df in self._cached_dfs:
            df.unpersist()
        self._cached_dfs.clear()

        # Stop Spark session
        if self.spark:
            self.spark.stop()


class ConnectionFactory:
    """
    Factory for creating data connections.

    Supports different connection types based on configuration.
    """

    @staticmethod
    def create(connection_type: str = "spark", **kwargs) -> DataConnection:
        """
        Create a data connection.

        Args:
            connection_type: Type of connection ('spark', 'duckdb', 'graph', etc.)
            **kwargs: Connection-specific arguments

        Returns:
            DataConnection instance

        Raises:
            ValueError: If connection type is not supported
        """
        if connection_type == "spark":
            spark_session = kwargs.get('spark_session')
            if not spark_session:
                raise ValueError("spark_session required for Spark connection")
            return SparkConnection(spark_session)

        elif connection_type == "duckdb":
            try:
                from .duckdb_connection import DuckDBConnection
                return DuckDBConnection(**kwargs)
            except ImportError:
                raise ValueError(
                    "DuckDB connection requires 'duckdb' package. "
                    "Install it with: pip install duckdb"
                )

        # Future implementations:
        # elif connection_type == "graph":
        #     return GraphDBConnection(**kwargs)

        else:
            raise ValueError(f"Unsupported connection type: {connection_type}")


# Convenience function for getting a Spark connection
def get_spark_connection(spark_session) -> SparkConnection:
    """
    Get a Spark connection.

    Args:
        spark_session: PySpark SparkSession

    Returns:
        SparkConnection instance
    """
    return ConnectionFactory.create("spark", spark_session=spark_session)
