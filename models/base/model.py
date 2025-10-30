from pyspark.sql import functions as F

from src.model.graph_dsl import as_graph, interpolate

class BaseModel:
    def __init__(self, spark, model_cfg: dict, storage_cfg: dict, params=None):
        self.spark = spark
        self.model_cfg = model_cfg
        self.graph = as_graph(model_cfg)
        self.storage_cfg = storage_cfg
        self.params = params or {}

    def _bronze_path(self, key: str) -> str:
        # key like 'bronze.ref_ticker' or 'bronze.news'
        t = self.storage_cfg["tables"][key.replace("bronze.","")]
        root = self.storage_cfg["roots"][t["root"]]
        return f"{root}/{t['rel']}"

    def _read(self, ref: str):
        return self.spark.read.parquet(self._bronze_path(ref))

    def _build_node(self, node: dict):
        df = self._read(node["from"])
        # where
        for cond in node.get("where", []):
            df = df.where(interpolate(cond, self.params))
        # select/rename
        select_map = node.get("select", {})
        for new, old in select_map.items():
            if new != old and old in df.columns:
                df = df.withColumnRenamed(old, new)
        # derive
        for new, expr in (node.get("derive", {}) or {}).items():
            if expr == "sha1(ticker)":
                df = df.withColumn(new, F.sha1(F.col("ticker")))
        # unique
        if "unique_key" in node:
            df = df.dropDuplicates(node["unique_key"])
        return df

    def build(self):
        dims, facts = {}, {}
        for node in self.graph["nodes"]:
            df = self._build_node(node)
            tags = set(node.get("tags", []))
            if {"dim","entity","ref"} & tags:
                dims[node["id"]] = df
            else:
                facts[node["id"]] = df
        return dims, facts
