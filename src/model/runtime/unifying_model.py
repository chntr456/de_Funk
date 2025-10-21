from __future__ import annotations
from typing import Dict, Any, List, Tuple
from pyspark.sql import SparkSession, DataFrame, functions as F
from src.model.runtime.model_registry import DatasetRegistry
import yaml, os, re

class UnifyingModel:
    def __init__(self, spark: SparkSession, model_cfg_path: str, storage_cfg_path: str = "configs/storage.json", params: Dict[str, str] | None = None):
        self.spark = spark
        self.registry = DatasetRegistry(spark, storage_cfg_path)
        self.params = {**{k: v for k, v in os.environ.items()}, **(params or {})}
        with open(model_cfg_path, "r", encoding="utf-8") as f:
            self.spec = yaml.safe_load(f)

    def _expand(self, s: str | None) -> str | None:
        if s is None: return None
        out = s
        for k, v in self.params.items():
            out = out.replace("${" + k + "}", v)
        # ${KEY:-default}
        def repl(m):
            key, default = m.group(1), m.group(2)
            return self.params.get(key, default)
        out = re.sub(r"\$\{([A-Z0-9_]+):-([^}]+)\}", repl, out)
        return out

    def _expand_list(self, items: List[str] | None) -> List[str]:
        return [self._expand(x) for x in (items or []) if self._expand(x)]

    def _load_dataset(self, name: str) -> DataFrame:
        ds = self.spec["datasets"][name]
        table = ds["table"]
        snap = self._expand(ds.get("snapshot_dt"))
        filters = self._expand_list(ds.get("filters"))
        if snap:
            return self.registry.load_with_snapshot(table, snapshot_dt=snap)
        return self.registry.load_with_filters(table, filters)

    def _build_dimension(self, name: str) -> DataFrame:
        cfg = self.spec["dimensions"][name]
        if "source" in cfg:
            df = self._load_dataset(cfg["source"]).alias("src")
        else:
            # two-source join (simple case)
            srcs = {alias: self._load_dataset(real).alias(alias) for alias, real in cfg["sources"].items()}
            aliases = list(srcs.keys())
            df = srcs[aliases[0]]
            for j in cfg.get("joins", []):
                left, right = [side.strip() for side in j.split("=")]
                # detect which alias is not yet joined; assume second alias in expression is the right source
                alias_right = right.split(".")[0]
                df = df.join(srcs[alias_right], on=F.expr(f"{left} = {right}"), how="left")
        selects = [self._expand(expr) for expr in cfg.get("select", [])]
        df = df.selectExpr(*selects)
        if "dedupe_by" in cfg:
            df = df.dropDuplicates(cfg["dedupe_by"])
        return df

    def _build_fact(self, name: str) -> DataFrame:
        cfg = self.spec["facts"][name]
        df = self._load_dataset(cfg["source"]).alias("src")
        selects = [self._expand(expr) for expr in cfg.get("select", [])]
        return df.selectExpr(*selects)

    def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        dims = {name: self._build_dimension(name) for name in self.spec.get("dimensions", {}).keys()}
        facts = {name: self._build_fact(name) for name in self.spec.get("facts", {}).keys()}
        return dims, facts
