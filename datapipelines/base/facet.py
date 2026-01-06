"""
Base Facet class for data transformation pipelines.

Facets transform raw API responses into normalized Spark DataFrames.
This is the foundation for all provider-specific facets.

Features:
- Numeric type coercion (handles JSON string/int/float inconsistencies)
- Batch processing with unionByName
- Final schema enforcement via SPARK_CASTS and FINAL_COLUMNS
- Empty DataFrame generation with correct schema

Usage:
    from datapipelines.base.facet import Facet

    class MyFacet(Facet):
        NUMERIC_COERCE = {"price": "double", "volume": "long"}
        FINAL_COLUMNS = [
            ("ticker", "string"),
            ("price", "double"),
            ("volume", "long"),
        ]

        def postprocess(self, df):
            # Custom transformations
            return df

Author: de_Funk Team
Date: December 2025
Moved: January 2026 - Consolidated to datapipelines/base/
"""
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
    Lightweight base class for data transformation facets.

    Features:
      1) Pre-coerces python dicts for numeric keys to stable types (avoids Long/Double merge errors)
      2) Unions batches with unionByName
      3) Lets child facet do vectorized postprocess()
      4) Enforces final Spark casts (SPARK_CASTS) & optional final column order (FINAL_COLUMNS)

    Class Attributes:
        NUMERIC_COERCE: Dict mapping field names to target types for pre-coercion
        SPARK_CASTS: Dict mapping column names to Spark type strings for final casting
        FINAL_COLUMNS: Optional list of (name, type) tuples defining final schema

    Methods to Override:
        calls(): Generator yielding API call specifications
        postprocess(df): Transform DataFrame after initial creation
        validate(df): Validate output DataFrame (optional)
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
        """
        Main normalization pipeline.

        Args:
            raw_batches: List of lists of dicts (batches of API responses)

        Returns:
            Spark DataFrame with normalized data
        """
        dfs = []
        for rows in raw_batches:
            if not rows:
                continue
            rows = self._coerce_rows(rows)
            # Use samplingRatio=1.0 to sample all rows for schema inference
            # This prevents CANNOT_DETERMINE_TYPE errors when the first row
            # doesn't have all fields or has None/null values
            df = self.spark.createDataFrame(rows, samplingRatio=1.0)
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

    def postprocess(self, df):
        """
        Override in child class to apply custom transformations.

        Args:
            df: Input DataFrame after batch union

        Returns:
            Transformed DataFrame
        """
        return df

    def validate(self, df):
        """
        Override in child class to validate output DataFrame.

        Args:
            df: Output DataFrame to validate

        Returns:
            DataFrame (same as input, for chaining)

        Raises:
            ValueError: If validation fails
        """
        return df

    def calls(self):
        """
        Override in child class to generate API call specifications.

        Yields:
            Dict with keys like 'ep_name', 'params' for API calls
        """
        raise NotImplementedError("Child facet must implement calls()")
