from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict
from src.common.spark_session import get_spark

def _repo_root(start: Path) -> Path:
    # Walk up until we find the repo markers (adjust if you use a different layout)
    cur = start
    while cur != cur.parent:
        if (cur / "configs").exists() and (cur / "src").exists():
            return cur
        cur = cur.parent
    return start  # fallback

@dataclass
class RepoContext:
    repo: Path
    spark: Any
    polygon_cfg: Dict[str, Any]
    storage: Dict[str, Any]

    @classmethod
    def from_repo_root(cls) -> "RepoContext":
        here = Path(__file__).resolve()
        root = _repo_root(here)
        # load configs
        polygon_cfg = json.loads((root / "configs" / "polygon_endpoints.json").read_text())
        storage = json.loads((root / "configs" / "storage.json").read_text())
        spark = get_spark("CompanyPipeline")

        return cls(repo=root, spark=spark, polygon_cfg=polygon_cfg, storage=storage)
