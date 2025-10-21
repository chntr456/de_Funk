from __future__ import annotations
from typing import Dict
from pyspark.sql import DataFrame
from src.common.storage_paths import StoragePaths

class BronzeSink:
    def __init__(self, storage_cfg: str = "configs/storage.json"):
        self.paths = StoragePaths(storage_cfg)

    def partition_exists(self, table: str, part: Dict[str, str]) -> bool:
        p = self.paths.table_partition_path(table, part)
        return p.exists() and any(p.glob("*.parquet"))

    def write_partition(self, table: str, part: Dict[str, str], df: DataFrame, overwrite: bool = True) -> None:
        p = self.paths.table_partition_path(table, part)
        p.mkdir(parents=True, exist_ok=True)
        if overwrite:
            for f in p.glob("*.parquet"): f.unlink()
        df.write.mode("overwrite").parquet(str(p))

    def write_if_missing(self, table: str, part: Dict[str, str], df: DataFrame) -> bool:
        if self.partition_exists(table, part):
            return False
        self.write_partition(table, part, df, overwrite=True)
        return True
