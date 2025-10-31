# src/orchestration/orchestrator.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame
    from datapipelines.ingestors.company_ingestor import CompanyPolygonIngestor
    from models.company_model import CompanyModel

from core.context import RepoContext

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


class Orchestrator:
    def __init__(self, ctx: RepoContext):
        self.ctx = ctx  # holds repo Path, spark: SparkSession, polygon_cfg: dict, storage: dict

    # ---- helpers -------------------------------------------------------------

    def _load_company_model_cfg(self) -> Dict[str, Any]:
        """Load YAML model graph config."""
        cfg_path = self.ctx.repo / "configs" / "models" / "company.yaml"
        text = cfg_path.read_text()
        if yaml is not None:
            return yaml.safe_load(text)
        # fallback if PyYAML isn't installed (expects JSON-compatible YAML)
        return json.loads(text)

    # ---- public API ----------------------------------------------------------

    def run_company_pipeline(
        self,
        *,
        date_from: str,
        date_to: str,
        max_tickers: int | None = None,
    ) -> "DataFrame":
        # Lazy imports - only load when method is actually called
        from datapipelines.ingestors.company_ingestor import CompanyPolygonIngestor
        from models.company_model import CompanyModel

        # ✅ do NOT call spark like a function
        spark = self.ctx.spark

        # 1) Bronze: ingest Polygon → parquet (skip-if-exists at partition level)
        ing = CompanyPolygonIngestor(
            polygon_cfg=self.ctx.polygon_cfg,
            storage_cfg=self.ctx.storage,
            spark=spark,
        )
        tickers = ing.run_all(
            date_from=date_from,
            date_to=date_to,
            snapshot_dt=None,
            max_tickers=max_tickers,
            include_news=True,
        )

        # 2) Silver: build the model graph from bronze sources
        model_cfg = self._load_company_model_cfg()
        model = CompanyModel(
            spark,
            model_cfg=model_cfg,
            storage_cfg=self.ctx.storage,
            params={"DATE_FROM": date_from, "DATE_TO": date_to, "UNIVERSE_SIZE": len(tickers)},
        )
        dims, facts = model.build()

        # Return the canonical analytics path
        final_df = facts["prices_with_company"]
        return final_df
