from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, Tuple
from pyspark.sql import DataFrame, SparkSession, functions as F

from src.model.company_model import CompanyModel
from models.api.dal import StorageRouter, BronzeTable, SilverPath

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

class ModelSession:
    """
    Thin wrapper around your CompanyModel with convenience to access bronze and silver.
    - builds the graph lazily
    - lets services get at named silver 'paths' without re-implementing joins
    """
    def __init__(self, spark: SparkSession, repo_root: Path, storage_cfg: Dict[str, Any]):
        self.spark = spark
        self.repo_root = repo_root
        self.storage_cfg = storage_cfg
        self.router = StorageRouter(storage_cfg)
        self._dims: Dict[str, DataFrame] | None = None
        self._facts: Dict[str, DataFrame] | None = None

    # ------------- bronze -------------
    def bronze(self, logical_table: str) -> BronzeTable:
        return BronzeTable(self.spark, self.router, logical_table)

    # ------------- silver -------------
    def _load_model_yaml(self) -> Dict[str, Any]:
        p = self.repo_root / "configs" / "models" / "company.yaml"
        txt = p.read_text()
        if yaml is not None:
            return yaml.safe_load(txt)
        return json.loads(txt)

    def ensure_built(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        if self._facts is None or self._dims is None:
            model_cfg = self._load_model_yaml()
            model = CompanyModel(
                self.spark, model_cfg=model_cfg, storage_cfg=self.storage_cfg, params={}
            )
            self._dims, self._facts = model.build()
        return self._dims, self._facts

    def silver_path_df(self, path_id: str) -> DataFrame:
        _, facts = self.ensure_built()
        if path_id not in facts:
            raise KeyError(f"Silver path '{path_id}' not built.")
        return facts[path_id]

    def get_dimension_df(self, model_name: str, node_name: str) -> DataFrame:
        """
        Get a dimension dataframe.

        Args:
            model_name: Model name (e.g., 'company')
            node_name: Node name (e.g., 'dim_company')

        Returns:
            Dimension dataframe
        """
        dims, _ = self.ensure_built()
        if node_name not in dims:
            raise KeyError(f"Dimension '{node_name}' not found in model '{model_name}'. Available dims: {list(dims.keys())}")
        return dims[node_name]

    def get_fact_df(self, model_name: str, node_name: str) -> DataFrame:
        """
        Get a fact dataframe.

        Args:
            model_name: Model name (e.g., 'company')
            node_name: Node name (e.g., 'fact_prices')

        Returns:
            Fact dataframe
        """
        _, facts = self.ensure_built()
        if node_name not in facts:
            raise KeyError(f"Fact '{node_name}' not found in model '{model_name}'. Available facts: {list(facts.keys())}")
        return facts[node_name]

    # Optional: writer if you decide to persist silver later
    def persist_silver(self, outputs: Dict[str, str]):
        """
        outputs: mapping of path_id -> silver relative path (e.g. 'company/paths/news_with_company')
        """
        _, facts = self.ensure_built()
        for pid, rel in outputs.items():
            if pid not in facts:
                raise KeyError(f"Path '{pid}' not found.")
            facts[pid].write.mode("overwrite").parquet(self.router.silver_path(rel))
