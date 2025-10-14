from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Tuple, Callable, Optional
from pyspark.sql import DataFrame, SparkSession, Column, functions as F
from src.common.spark_df_utils import project_with_mapping, union_all

# Type aliases
Schema = List[Tuple[str, str]]          # [("col", "type"), ...]
RenameMap = Dict[str, str]              # {"src": "dst"}
Literals = Dict[str, Tuple[str, object]]# {"col": ("type", value)}
Derived = Dict[str, Callable[[DataFrame], Column]]  # {"col": lambda df: expr}

class Facet(ABC):
    """
    Facet contract with declarative specs:
      - RENAME_MAP:   raw->canonical column mapping
      - OUTPUT_SCHEMA: list of (name, spark_sql_type) in final order
      - LITERALS:     constant columns to inject (name -> (type, value))
      - DERIVED:      columns computed from DF (name -> function returning Column)
    Subclasses may override `postprocess()` for facet-specific fixes.
    """
    name: str

    # ---- Declarative spec (override in subclasses) ----
    RENAME_MAP: RenameMap = {}
    OUTPUT_SCHEMA: Schema = []
    LITERALS: Literals = {}
    DERIVED: Derived = {}

    def __init__(self, spark: SparkSession):
        self.spark = spark

    # ---- API calls spec must still be provided by facet ----
    @abstractmethod
    def calls(self) -> Iterable[dict]: ...

    # ---- Core normalize using the declarative spec ----
    def normalize(self, raw_batches: List[List[dict]]) -> DataFrame:
        if not self.OUTPUT_SCHEMA:
            raise ValueError(f"{self.__class__.__name__}: OUTPUT_SCHEMA must be defined")

        target_cols = [c for c, _ in self.OUTPUT_SCHEMA]
        casts = {c: t for c, t in self.OUTPUT_SCHEMA}

        dfs: List[DataFrame] = []
        for rows in raw_batches:
            if not rows:
                continue
            df = self.spark.createDataFrame(rows)

            # 1) rename + (optional) cast + inject literals (single projection)
            df = project_with_mapping(
                df,
                rename_map=self.RENAME_MAP,
                casts={},               # cast at final select for flexibility
                literals=self.LITERALS,
                keep=None               # we will finalize order later
            )

            # 2) derived columns (all-at-once, vectorized)
            for col_name, fn in self.DERIVED.items():
                df = df.withColumn(col_name, fn(df))

            # 3) facet-specific cleanup/fixes (optional)
            df = self.postprocess(df)

            # 4) final order + casts
            df = df.select(*[
                (F.col(c).cast(casts[c]) if c in df.columns else F.lit(None).cast(casts[c]).alias(c))
                for c in target_cols
            ])
            dfs.append(df)

        if not dfs:
            schema_str = ", ".join([f"{c} {t}" for c, t in self.OUTPUT_SCHEMA])
            return self.spark.createDataFrame([], schema=schema_str)

        return union_all(dfs)

    # ---- Optional hook for facets needing custom logic ----
    def postprocess(self, df: DataFrame) -> DataFrame:
        return df
