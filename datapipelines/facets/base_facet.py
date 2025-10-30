from __future__ import annotations
from typing import Dict, List, Iterable, Tuple, Optional
from pyspark.sql import DataFrame, functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, IntegerType, LongType,
    BooleanType, DateType, TimestampType
)

# ---------- Safe column helpers ----------

def coalesce_existing(df: DataFrame, candidates: Iterable[str]):
    """coalesce(...) but only over columns that actually exist."""
    cols = [F.col(c) for c in candidates if c in df.columns]
    return F.coalesce(*cols) if cols else F.lit(None)

def first_existing(df: DataFrame, candidates: Iterable[str]):
    """Return the first existing column as a Column, else NULL literal."""
    for c in candidates:
        if c in df.columns:
            return F.col(c)
    return F.lit(None)

def _type_from_str(t: str):
    t = (t or "").lower()
    return {
        "string": StringType(),
        "double": DoubleType(),
        "float": DoubleType(),
        "int": IntegerType(),
        "integer": IntegerType(),
        "long": LongType(),
        "bigint": LongType(),
        "boolean": BooleanType(),
        "date": DateType(),
        "timestamp": TimestampType(),
    }.get(t, StringType())

# ---------- Facet base ----------

class Facet:
    """
    Lightweight base:
      1) pre-coerces python dicts for numeric keys to stable types (avoids Long/Double merge errors)
      2) unions batches
      3) lets child facet do vectorized postprocess()
      4) enforces final Spark casts (SPARK_CASTS) & optional final column order (FINAL_COLUMNS)
    """

    # Example in child facet:
    # NUMERIC_COERCE = {"o":"double","h":"double","v":"double","t":"long"}
    NUMERIC_COERCE: Dict[str, str] = {}

    # Final Spark casts by column name (after postprocess, before return)
    # SPARK_CASTS = {"open":"double","trade_date":"date", ...}
    SPARK_CASTS: Dict[str, str] = {}

    # Optional final column order; if set, we will select these in order and add NULLs for missing
    FINAL_COLUMNS: Optional[List[Tuple[str, str]]] = None  # list of (name, spark_type_str)

    def __init__(self, spark, **kwargs):
        self.spark = spark
        self._extra = kwargs

    # -------- implementation helpers --------

    def _coerce_rows(self, rows: List[dict]) -> List[dict]:
        """
        Pre-coerce numeric fields in raw JSON rows so Spark sees a consistent schema.
        - doubles: allow int/str -> float
        - longs:   allow float/str -> int (truncate)
        """
        if not rows or not self.NUMERIC_COERCE:
            return rows
        out = []
        for r in rows:
            rr = dict(r)
            for k, typ in self.NUMERIC_COERCE.items():
                if k not in rr or rr[k] is None:
                    continue
                val = rr[k]
                if typ.lower() in ("double", "float", "decimal"):
                    if isinstance(val, int):
                        rr[k] = float(val)
                    elif isinstance(val, str):
                        try: rr[k] = float(val)
                        except Exception: pass
                elif typ.lower() in ("long", "bigint", "int", "integer"):
                    if isinstance(val, float):
                        rr[k] = int(val)
                    elif isinstance(val, str):
                        try: rr[k] = int(float(val))
                        except Exception: pass
            out.append(rr)
        return out

    def _apply_final_casts(self, df: DataFrame) -> DataFrame:
        if not self.SPARK_CASTS:
            return df
        for c, t in self.SPARK_CASTS.items():
            if c in df.columns:
                df = df.withColumn(c, F.col(c).cast(t))
            else:
                df = df.withColumn(c, F.lit(None).cast(t))
        return df

    def _apply_final_columns(self, df: DataFrame) -> DataFrame:
        """
        Ensure a stable column set and order. If FINAL_COLUMNS is provided,
        select those columns in order; any missing ones are created as NULL.
        """
        if not self.FINAL_COLUMNS:
            return df
        sel = []
        for name, t in self.FINAL_COLUMNS:
            if name in df.columns:
                sel.append(F.col(name).cast(t).alias(name))
            else:
                sel.append(F.lit(None).cast(t).alias(name))
        return df.select(*sel)

    # -------- main normalization pipeline --------


    def _empty_df(self) -> DataFrame:
        """
        Produce an empty DataFrame matching FINAL_COLUMNS if declared,
        otherwise a truly empty 0-column DF.
        """
        if self.FINAL_COLUMNS:
            fields = [StructField(name, _type_from_str(t), True) for name, t in self.FINAL_COLUMNS]
            schema = StructType(fields)
            return self.spark.createDataFrame([], schema)
        # return a 0-col empty DF instead of a placeholder "empty" column
        return self.spark.createDataFrame(self.spark.sparkContext.emptyRDD(), StructType([]))

    def normalize(self, raw_batches):
        dfs = []
        for rows in raw_batches:
            if not rows:
                continue
            rows = self._coerce_rows(rows)
            df = self.spark.createDataFrame(rows)
            dfs.append(df)

        if not dfs:
            return self._empty_df()

        out = dfs[0]
        for d in dfs[1:]:
            out = out.unionByName(d, allowMissingColumns=True)

        out = self.postprocess(out)
        out = self._apply_final_casts(out)
        out = self._apply_final_columns(out)
        return out

    def postprocess(self, df):  # child override
        return df
