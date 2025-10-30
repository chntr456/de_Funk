from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional
from pyspark.sql import DataFrame, SparkSession

@dataclass(frozen=True)
class StorageRouter:
    storage_cfg: Dict[str, Any]

    def bronze_path(self, logical_table: str) -> str:
        root = self.storage_cfg["roots"]["bronze"].rstrip("/")
        rel = self.storage_cfg["tables"][logical_table]["rel"]
        return f"{root}/{rel}"

    def silver_path(self, logical_rel: str) -> str:
        root = self.storage_cfg["roots"]["silver"].rstrip("/")
        return f"{root}/{logical_rel}"

class BronzeTable:
    def __init__(self, spark: SparkSession, router: StorageRouter, logical_table: str):
        self.spark = spark
        self.router = router
        self.logical_table = logical_table

    @property
    def path(self) -> str:
        return self.router.bronze_path(self.logical_table)

    def read(self) -> DataFrame:
        return self.spark.read.parquet(self.path)

class SilverPath:
    """
    Represents a materialized silver 'path' (fact/view) built by the model builder.
    If you write silver outputs to Parquet, this reads them by path; if you keep them in-memory,
    you can inject a DataFrame via `override_df`.
    """
    def __init__(self, spark: SparkSession, router: StorageRouter, logical_rel: str):
        self.spark = spark
        self.router = router
        self.logical_rel = logical_rel
        self._override_df: Optional[DataFrame] = None

    @property
    def path(self) -> str:
        return self.router.silver_path(self.logical_rel)

    def read(self) -> DataFrame:
        if self._override_df is not None:
            return self._override_df
        return self.spark.read.parquet(self.path)

    def set_df(self, df: DataFrame):
        self._override_df = df
