from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Optional

def _repo_root(start: Path) -> Path:
    # Walk up until we find the repo markers (adjust if you use a different layout)
    # If start is a file, get its directory first
    cur = start if start.is_dir() else start.parent

    while cur != cur.parent:
        # Check for configs directory and core directory (new structure)
        if (cur / "configs").exists() and (cur / "core").exists():
            return cur
        cur = cur.parent

    # Fallback: return parent of start if it was a file, otherwise start
    return start.parent if start.is_file() else start

@dataclass
class RepoContext:
    repo: Path
    spark: Any  # Kept for backward compatibility
    polygon_cfg: Dict[str, Any]
    storage: Dict[str, Any]
    connection: Optional[Any] = None  # DataConnection (DuckDB or Spark)
    connection_type: str = "spark"  # Default to spark for backward compatibility

    @classmethod
    def from_repo_root(cls, connection_type: Optional[str] = None) -> "RepoContext":
        """
        Create RepoContext from repository root.

        Args:
            connection_type: Override connection type ('spark' or 'duckdb').
                           If None, reads from storage.json config.

        Returns:
            RepoContext with appropriate connection
        """
        here = Path(__file__).resolve()
        root = _repo_root(here)

        # Load configs
        polygon_cfg = json.loads((root / "configs" / "polygon_endpoints.json").read_text())
        storage = json.loads((root / "configs" / "storage.json").read_text())

        # Determine connection type
        if connection_type is None:
            connection_type = storage.get("connection", {}).get("type", "spark")

        # Create connection based on type
        spark = None
        connection = None

        if connection_type == "duckdb":
            from core.connection import ConnectionFactory
            connection = ConnectionFactory.create("duckdb")
            # DuckDB-only mode: No Spark needed for UI/analytics
            spark = None
        else:
            # Default to Spark
            from orchestration.common.spark_session import get_spark
            spark = get_spark("CompanyPipeline")
            from core.connection import ConnectionFactory
            connection = ConnectionFactory.create("spark", spark_session=spark)

        return cls(
            repo=root,
            spark=spark,
            polygon_cfg=polygon_cfg,
            storage=storage,
            connection=connection,
            connection_type=connection_type
        )
