"""
DuckDB connection implementation.

DuckDB is excellent for analytics workloads and can read Parquet files directly.
Much faster startup than Spark for single-node operations.
"""

from typing import Dict, Any, Optional
import pandas as pd
from pathlib import Path

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

from .connection import DataConnection


class DuckDBConnection(DataConnection):
    """
    DuckDB connection for analytics queries.

    Benefits:
    - Fast startup (no Spark overhead)
    - Native Parquet support
    - Great for interactive/notebook workloads
    - SQL-based queries
    - Can still use Spark for heavy ETL
    """

    def __init__(self, db_path: str = ":memory:", read_only: bool = False):
        """
        Initialize DuckDB connection.

        Args:
            db_path: Path to DuckDB database file (":memory:" for in-memory)
            read_only: Whether to open in read-only mode
        """
        if not DUCKDB_AVAILABLE:
            raise ImportError(
                "DuckDB is not installed. Install it with: pip install duckdb"
            )

        self.conn = duckdb.connect(db_path, read_only=read_only)
        self._cached_tables = {}

    def read_table(self, path: str, format: str = "parquet") -> Any:
        """
        Read a table from storage.

        DuckDB can query Parquet files directly without loading into memory!

        Args:
            path: Path to the table (file or directory)
            format: Format of the data (currently only parquet supported)

        Returns:
            DuckDB relation (lazy query result)
        """
        if format != "parquet":
            raise ValueError(f"DuckDB connection only supports parquet format, got {format}")

        # DuckDB can query Parquet files directly
        # This is lazy - no data loaded until needed
        path_obj = Path(path)

        if path_obj.is_dir():
            # Read all parquet files in directory
            pattern = f"{path}/**/*.parquet"
            # Use from_parquet to get a relation object
            return self.conn.from_parquet(pattern, union_by_name=True)
        else:
            # Read single file
            return self.conn.from_parquet(path)

    def apply_filters(self, df: Any, filters: Dict[str, Any]) -> Any:
        """
        Apply filters to a DuckDB relation.

        Args:
            df: DuckDB relation
            filters: Dictionary of column -> filter value

        Returns:
            Filtered DuckDB relation
        """
        if not filters:
            return df

        # Build WHERE clause
        conditions = []
        for column, value in filters.items():
            if isinstance(value, dict):
                # Date range filter
                if 'start' in value and 'end' in value:
                    conditions.append(
                        f"{column} BETWEEN '{value['start']}' AND '{value['end']}'"
                    )
            elif isinstance(value, list):
                # IN filter
                if value:  # Only add if list is not empty
                    values_str = ", ".join(f"'{v}'" for v in value)
                    conditions.append(f"{column} IN ({values_str})")
            else:
                # Equality filter
                conditions.append(f"{column} = '{value}'")

        if conditions:
            where_clause = " AND ".join(conditions)
            # Use DuckDB relation's filter method
            return df.filter(where_clause)

        return df

    def to_pandas(self, df: Any) -> pd.DataFrame:
        """
        Convert DuckDB relation to pandas DataFrame.

        Args:
            df: DuckDB relation

        Returns:
            Pandas DataFrame
        """
        # DuckDB relation has direct pandas conversion
        return df.df()

    def count(self, df: Any) -> int:
        """
        Get row count from DuckDB relation.

        Args:
            df: DuckDB relation

        Returns:
            Number of rows
        """
        # DuckDB relation has count() method
        return df.count('*').fetchone()[0]

    def cache(self, df: Any, name: Optional[str] = None) -> Any:
        """
        Cache a DuckDB relation.

        Args:
            df: DuckDB relation to cache
            name: Optional name for the cached table

        Returns:
            Cached relation
        """
        # Generate a name if not provided
        if not name:
            name = f"_cached_{id(df)}"

        # Create a temporary table from the relation
        df.create(name)
        self._cached_tables[name] = df
        return self.conn.table(name)

    def uncache(self, df: Any):
        """
        Remove cached table.

        Args:
            df: DuckDB relation to uncache
        """
        # Find the name associated with this dataframe
        name_to_remove = None
        for name, cached_df in self._cached_tables.items():
            if cached_df is df:
                name_to_remove = name
                break

        if name_to_remove:
            self.conn.execute(f"DROP TABLE IF EXISTS {name_to_remove}")
            del self._cached_tables[name_to_remove]

    def stop(self):
        """Close the DuckDB connection."""
        # Clear cached tables
        for name in list(self._cached_tables.keys()):
            self.conn.execute(f"DROP TABLE IF EXISTS {name}")
        self._cached_tables.clear()

        # Close connection
        if self.conn:
            self.conn.close()
            self.conn = None

    def execute_sql(self, query: str) -> Any:
        """
        Execute raw SQL query.

        Args:
            query: SQL query string

        Returns:
            DuckDB relation with results
        """
        return self.conn.execute(query)

    def __del__(self):
        """Cleanup on deletion."""
        self.stop()
