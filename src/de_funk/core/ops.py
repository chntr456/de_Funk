"""
DataOps — backend-agnostic DataFrame operation interfaces.

DataOps defines the contract for all DataFrame operations.
DuckDBOps and SparkOps implement it for their respective backends.

Engine delegates all operations to the active DataOps implementation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class DataOps(ABC):
    """Abstract interface for backend-agnostic DataFrame operations."""

    @abstractmethod
    def read(self, path: str, format: str = "delta") -> Any:
        """Read a table from storage."""
        ...

    @abstractmethod
    def write(self, df: Any, path: str, format: str = "delta", mode: str = "overwrite") -> None:
        """Write a DataFrame to storage."""
        ...

    @abstractmethod
    def create_df(self, rows: list[list], schema: list[tuple[str, str]]) -> Any:
        """Create a DataFrame from rows and schema."""
        ...

    @abstractmethod
    def select(self, df: Any, columns: list[str]) -> Any:
        """Select columns from a DataFrame."""
        ...

    @abstractmethod
    def drop(self, df: Any, columns: list[str]) -> Any:
        """Drop columns from a DataFrame."""
        ...

    @abstractmethod
    def derive(self, df: Any, col: str, expr: str) -> Any:
        """Add a computed column via SQL expression."""
        ...

    @abstractmethod
    def filter(self, df: Any, conditions: list[str]) -> Any:
        """Filter rows by SQL conditions."""
        ...

    @abstractmethod
    def dedup(self, df: Any, subset: list[str]) -> Any:
        """Deduplicate rows by column subset."""
        ...

    @abstractmethod
    def join(self, left: Any, right: Any, on: list[str], how: str = "inner") -> Any:
        """Join two DataFrames."""
        ...

    @abstractmethod
    def union(self, dfs: list[Any]) -> Any:
        """Vertically stack multiple DataFrames."""
        ...

    @abstractmethod
    def unpivot(self, df: Any, id_cols: list[str], value_cols: list[str],
                var_name: str = "variable", val_name: str = "value") -> Any:
        """Melt wide columns into long format."""
        ...

    @abstractmethod
    def window(self, df: Any, partition: list[str], order: list[str],
               expr: str, alias: str) -> Any:
        """Add a window function column."""
        ...

    @abstractmethod
    def pivot(self, df: Any, rows: list[str], cols: list[str],
              measures: list[dict]) -> Any:
        """Pivot rows to columns with aggregation."""
        ...

    @abstractmethod
    def aggregate(self, df: Any, group_by: list[str], aggs: list[dict]) -> Any:
        """Group and aggregate."""
        ...

    @abstractmethod
    def count(self, df: Any) -> int:
        """Count rows."""
        ...

    @abstractmethod
    def to_pandas(self, df: Any) -> Any:
        """Convert to pandas DataFrame."""
        ...

    @abstractmethod
    def columns(self, df: Any) -> list[str]:
        """Get column names."""
        ...


class DuckDBOps(DataOps):
    """DuckDB implementation of DataOps using in-process SQL."""

    def __init__(self, conn=None, memory_limit: str = "3GB"):
        import duckdb
        self._conn = conn or duckdb.connect()
        if conn is None:
            self._conn.execute(f"SET memory_limit='{memory_limit}'")
        try:
            self._conn.execute("INSTALL delta; LOAD delta;")
            self._delta_available = True
        except Exception:
            self._delta_available = False

    def _scan_expr(self, path: str) -> str:
        """Return scan expression for a path."""
        if self._delta_available:
            try:
                self._conn.execute(f"SELECT 1 FROM delta_scan('{path}') LIMIT 0")
                return f"delta_scan('{path}')"
            except Exception:
                pass
        return f"read_parquet('{path}/*.parquet')"

    def read(self, path: str, format: str = "delta") -> Any:
        scan = self._scan_expr(path)
        return self._conn.execute(f"SELECT * FROM {scan}").fetchdf()

    def write(self, df: Any, path: str, format: str = "delta", mode: str = "overwrite") -> None:
        import os
        os.makedirs(path, exist_ok=True)
        if hasattr(df, 'to_parquet'):
            df.to_parquet(f"{path}/data.parquet", index=False)
        else:
            import pandas as pd
            pd.DataFrame(df).to_parquet(f"{path}/data.parquet", index=False)

    def create_df(self, rows: list[list], schema: list[tuple[str, str]]) -> Any:
        import pandas as pd
        cols = [s[0] for s in schema]
        return pd.DataFrame(rows, columns=cols)

    def select(self, df: Any, columns: list[str]) -> Any:
        return df[columns]

    def drop(self, df: Any, columns: list[str]) -> Any:
        return df.drop(columns=columns, errors="ignore")

    def derive(self, df: Any, col: str, expr: str) -> Any:
        rel = self._conn.from_df(df)
        result = rel.project(f"*, ({expr}) AS {col}")
        return result.fetchdf()

    def filter(self, df: Any, conditions: list[str]) -> Any:
        rel = self._conn.from_df(df)
        for cond in conditions:
            rel = rel.filter(cond)
        return rel.fetchdf()

    def dedup(self, df: Any, subset: list[str]) -> Any:
        return df.drop_duplicates(subset=subset)

    def join(self, left: Any, right: Any, on: list[str], how: str = "inner") -> Any:
        return left.merge(right, on=on, how=how)

    def union(self, dfs: list[Any]) -> Any:
        import pandas as pd
        return pd.concat(dfs, ignore_index=True)

    def unpivot(self, df: Any, id_cols: list[str], value_cols: list[str],
                var_name: str = "variable", val_name: str = "value") -> Any:
        return df.melt(id_vars=id_cols, value_vars=value_cols,
                       var_name=var_name, value_name=val_name)

    def window(self, df: Any, partition: list[str], order: list[str],
               expr: str, alias: str) -> Any:
        partition_str = ", ".join(f'"{c}"' for c in partition) if partition else "1"
        order_str = ", ".join(f'"{c}"' for c in order) if order else "1"
        all_cols = ", ".join(f'"{c}"' for c in df.columns)
        sql = (f"SELECT {all_cols}, {expr} OVER "
               f"(PARTITION BY {partition_str} ORDER BY {order_str}) AS \"{alias}\" "
               f"FROM __df")
        self._conn.register("__df", df)
        result = self._conn.execute(sql).fetchdf()
        self._conn.unregister("__df")
        return result

    def pivot(self, df: Any, rows: list[str], cols: list[str],
              measures: list[dict]) -> Any:
        group_cols = rows + cols
        agg_parts = []
        for m in measures:
            agg = m.get("aggregation", "SUM")
            field = m.get("field", "")
            name = m.get("name", field)
            agg_parts.append(f'{agg}("{field}") AS "{name}"')
        group_str = ", ".join(f'"{c}"' for c in group_cols)
        agg_str = ", ".join(agg_parts)
        self._conn.register("__pivot_df", df)
        sql = f"SELECT {group_str}, {agg_str} FROM __pivot_df GROUP BY {group_str}"
        result = self._conn.execute(sql).fetchdf()
        self._conn.unregister("__pivot_df")
        return result

    def aggregate(self, df: Any, group_by: list[str], aggs: list[dict]) -> Any:
        agg_parts = []
        for a in aggs:
            func = a.get("func", "SUM")
            col = a.get("col", "")
            alias = a.get("alias", f"{func}_{col}")
            agg_parts.append(f'{func}("{col}") AS "{alias}"')
        group_str = ", ".join(f'"{c}"' for c in group_by)
        agg_str = ", ".join(agg_parts)
        self._conn.register("__agg_df", df)
        if group_by:
            sql = f"SELECT {group_str}, {agg_str} FROM __agg_df GROUP BY {group_str}"
        else:
            sql = f"SELECT {agg_str} FROM __agg_df"
        result = self._conn.execute(sql).fetchdf()
        self._conn.unregister("__agg_df")
        return result

    def count(self, df: Any) -> int:
        if hasattr(df, '__len__'):
            return len(df)
        return 0

    def to_pandas(self, df: Any) -> Any:
        return df

    def columns(self, df: Any) -> list[str]:
        if hasattr(df, 'columns'):
            return list(df.columns)
        return []


class SparkOps(DataOps):
    """Spark implementation of DataOps."""

    def __init__(self, spark_session):
        self._spark = spark_session

    def read(self, path: str, format: str = "delta") -> Any:
        return self._spark.read.format(format).load(path)

    def write(self, df: Any, path: str, format: str = "delta", mode: str = "overwrite") -> None:
        df.write.format(format).mode(mode).save(path)

    def create_df(self, rows: list[list], schema: list[tuple[str, str]]) -> Any:
        from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, BooleanType
        type_map = {"string": StringType(), "int": IntegerType(), "float": FloatType(), "boolean": BooleanType()}
        fields = [StructField(name, type_map.get(dtype, StringType()), True) for name, dtype in schema]
        return self._spark.createDataFrame(rows, StructType(fields))

    def select(self, df: Any, columns: list[str]) -> Any:
        return df.select(*columns)

    def drop(self, df: Any, columns: list[str]) -> Any:
        return df.drop(*columns)

    def derive(self, df: Any, col: str, expr: str) -> Any:
        from pyspark.sql import functions as F
        return df.withColumn(col, F.expr(expr))

    def filter(self, df: Any, conditions: list[str]) -> Any:
        for cond in conditions:
            df = df.filter(cond)
        return df

    def dedup(self, df: Any, subset: list[str]) -> Any:
        return df.dropDuplicates(subset)

    def join(self, left: Any, right: Any, on: list[str], how: str = "inner") -> Any:
        return left.join(right, on=on, how=how)

    def union(self, dfs: list[Any]) -> Any:
        result = dfs[0]
        for df in dfs[1:]:
            result = result.unionByName(df, allowMissingColumns=True)
        return result

    def unpivot(self, df: Any, id_cols: list[str], value_cols: list[str],
                var_name: str = "variable", val_name: str = "value") -> Any:
        return df.unpivot(id_cols, value_cols, var_name, val_name)

    def window(self, df: Any, partition: list[str], order: list[str],
               expr: str, alias: str) -> Any:
        from pyspark.sql import functions as F, Window
        w = Window.partitionBy(*partition).orderBy(*order)
        return df.withColumn(alias, F.expr(expr).over(w))

    def pivot(self, df: Any, rows: list[str], cols: list[str],
              measures: list[dict]) -> Any:
        from pyspark.sql import functions as F
        grouped = df.groupBy(*rows)
        if cols:
            grouped = grouped.pivot(cols[0])
        agg_exprs = []
        for m in measures:
            agg_fn = getattr(F, m.get("aggregation", "sum").lower())
            agg_exprs.append(agg_fn(m.get("field", "")).alias(m.get("name", "")))
        return grouped.agg(*agg_exprs)

    def aggregate(self, df: Any, group_by: list[str], aggs: list[dict]) -> Any:
        from pyspark.sql import functions as F
        grouped = df.groupBy(*group_by)
        agg_exprs = []
        for a in aggs:
            agg_fn = getattr(F, a.get("func", "sum").lower())
            agg_exprs.append(agg_fn(a.get("col", "")).alias(a.get("alias", "")))
        return grouped.agg(*agg_exprs)

    def count(self, df: Any) -> int:
        return df.count()

    def to_pandas(self, df: Any) -> Any:
        return df.toPandas()

    def columns(self, df: Any) -> list[str]:
        return df.columns
