from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

class StoragePaths:
    def __init__(self, cfg_path: str = "configs/storage.json"):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        self.roots: Dict[str, str] = cfg.get("roots", {})
        self.tables: Dict[str, Dict[str, Any]] = cfg.get("tables", {})

    def root(self, name: str) -> Path:
        r = self.roots.get(name)
        if not r: raise KeyError(f"Root not found: {name}")
        return Path(r)

    def table_info(self, name: str) -> Dict[str, Any]:
        t = self.tables.get(name)
        if not t: raise KeyError(f"Table not found: {name}")
        return t

    def table_root(self, name: str) -> Path:
        t = self.table_info(name)
        return self.root(t["root"]) / t["rel"]

    def partitions_for(self, name: str) -> List[str]:
        return list(self.table_info(name).get("partitions", []))

    def table_partition_path(self, name: str, partition_spec: Dict[str, str]) -> Path:
        p = self.table_root(name)
        for k in self.partitions_for(name):
            v = partition_spec.get(k)
            if v is None:
                raise ValueError(f"Missing partition key '{k}' for table '{name}'")
            p = p / f"{k}={v}"
        return p
