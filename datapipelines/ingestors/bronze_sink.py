from pathlib import Path

class BronzeSink:
    def __init__(self, storage_cfg):
        self.cfg = storage_cfg

    def _table_cfg(self, table):
        return self.cfg["tables"][table]

    def _path(self, table, partitions):
        base = Path(self.cfg["roots"]["bronze"]) / self._table_cfg(table)["rel"]
        for k, v in (partitions or {}).items():
            base = base / f"{k}={v}"
        return base

    def exists(self, table, partitions):
        return self._path(table, partitions).exists()

    def write_if_missing(self, table, partitions, df):
        path = self._path(table, partitions)
        if path.exists():
            return False
        path.mkdir(parents=True, exist_ok=True)
        df.write.mode("overwrite").parquet(str(path))
        return True
