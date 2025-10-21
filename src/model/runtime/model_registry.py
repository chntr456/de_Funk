from __future__ import annotations
from typing import Dict, Any, Optional
from pyspark.sql import SparkSession, DataFrame, functions as F
from src.common.storage_paths import StoragePaths

class DatasetRegistry:
    def __init__(self, spark: SparkSession, storage_cfg: str = "configs/storage.json"):
        self.spark = spark
        self.paths = StoragePaths(storage_cfg)

    def load_bronze(self, table: str) -> DataFrame:
        root = self.paths.table_root(table)
        return self.spark.read.parquet(str(root))

    def load_with_filters(self, table: str, filters: list[str] | None = None) -> DataFrame:
        df = self.load_bronze(table)
        for cond in (filters or []):
            if cond and cond.strip():
                df = df.where(cond)
        return df

    def load_with_snapshot(self, table: str, snapshot_dt: Optional[str]) -> DataFrame:
        df = self.load_bronze(table)
        if not snapshot_dt:
            return df
        return df.where(F.input_file_name().contains(f"snapshot_dt={snapshot_dt}"))
