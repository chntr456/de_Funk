from __future__ import annotations
from abc import ABC
from typing import Dict, Iterable, List, Tuple, Callable, Optional, Set
from pyspark.sql import DataFrame, SparkSession, Column, functions as F

# --- PySpark error shim ---
try:
    from pyspark.errors import PySparkError  # PySpark 3.3+
except Exception:
    try:
        from pyspark.sql.utils import AnalysisException as PySparkError
    except Exception:
        class PySparkError(Exception):
            pass

from src.common.spark_df_utils import project_with_mapping, union_all, struct_from_spec

Schema   = List[Tuple[str, str]]
RenameMap= Dict[str, str]
Literals = Dict[str, Tuple[str, object]]
Derived  = Dict[str, Callable[[DataFrame], Column]]

_NUMERIC_RAW_TYPES: Set[str] = {"double", "float", "decimal"}

def _coerce_python_values(rows: List[dict], spec: Schema) -> List[dict]:
    if not rows or not spec:
        return rows
    numeric_cols = {name for name, t in spec if t.lower() in _NUMERIC_RAW_TYPES}
    if not numeric_cols:
        return rows

    out = []
    for r in rows:
        if not isinstance(r, dict):
            out.append(r); continue
        rr = dict(r)
        for k in numeric_cols:
            if k in rr and rr[k] is not None:
                v = rr[k]
                if isinstance(v, int):
                    rr[k] = float(v)
        out.append(rr)
    return out

class Facet(ABC):
    name: str
    RENAME_MAP: RenameMap = {}
    OUTPUT_SCHEMA: Schema = []
    LITERALS: Literals = {}
    DERIVED: Derived = {}
    RAW_SCHEMA_SPEC: Schema = []

    def __init__(self, spark: SparkSession, **kwargs):
        self.spark = spark
        self._extra = kwargs

    def normalize(self, raw_batches: List[List[dict]]) -> DataFrame:
        if not self.OUTPUT_SCHEMA:
            raise ValueError(f"{self.__class__.__name__}: OUTPUT_SCHEMA must be defined")

        target_cols = [c for c, _ in self.OUTPUT_SCHEMA]
        casts = {c: t for c, t in self.OUTPUT_SCHEMA}
        dfs: List[DataFrame] = []

        for rows in raw_batches:
            if not rows:
                continue

            df: Optional[DataFrame] = None

            if self.RAW_SCHEMA_SPEC:
                safe_rows = _coerce_python_values(rows, self.RAW_SCHEMA_SPEC)
                try:
                    df = self.spark.createDataFrame(safe_rows, schema=struct_from_spec(self.RAW_SCHEMA_SPEC))
                except PySparkError:
                    df = self.spark.createDataFrame(rows)
                except Exception:
                    df = self.spark.createDataFrame(rows)
            else:
                df = self.spark.createDataFrame(rows)

            df = project_with_mapping(df, rename_map=self.RENAME_MAP, casts={}, literals=self.LITERALS, keep=None)

            for col_name, fn in self.DERIVED.items():
                df = df.withColumn(col_name, fn(df))

            df = self.postprocess(df)

            df = df.select(*[
                (F.col(c).cast(casts[c]) if c in df.columns else F.lit(None).cast(casts[c]).alias(c))
                for c in target_cols
            ])

            dfs.append(df)

        if not dfs:
            schema_str = ", ".join([f"{c} {t}" for c, t in self.OUTPUT_SCHEMA])
            return self.spark.createDataFrame([], schema=schema_str)

        return union_all(dfs)

    def postprocess(self, df: DataFrame) -> DataFrame: return df
    def finalize(self, df: DataFrame) -> DataFrame: return df

    @property
    def extra(self) -> dict:
        return self._extra
