from __future__ import annotations
from pathlib import Path
from typing import Any
import json, datetime as dt

class ParquetLoader:
    def __init__(self, root="storage"):
        self.root = Path(root)
        (self.root / "silver" / "_meta" / "manifests").mkdir(parents=True, exist_ok=True)

    def _manifest(self, name: str, out_path: Path, rows: int):
        ts = dt.datetime.utcnow().strftime("%Y-%m-%dT%H%MZ")
        mf = {"dataset": name, "path": str(out_path), "rows": rows, "written_at": ts}
        (self.root / "silver" / "_meta" / "manifests" / f"{ts}__{name.replace('/','_')}.json").write_text(json.dumps(mf, indent=2))

    def _write(self, rel_path: str, df: Any):
        out = self.root / "silver" / rel_path
        out.mkdir(parents=True, exist_ok=True)
        df.write.mode("overwrite").parquet(str(out))
        self._manifest(rel_path, out, df.count())

    def write_dim(self, name: str, df: Any, snapshot_dt: str):
        rel = f"company/dims/{name}/version=v1/snapshot_dt={snapshot_dt}"
        self._write(rel, df)

    def write_fact(self, name: str, df: Any, snapshot_dt: str):
        rel = f"company/facts/{name}/version=v1/snapshot_dt={snapshot_dt}"
        self._write(rel, df)
