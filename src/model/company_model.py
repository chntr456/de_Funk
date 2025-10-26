from typing import Dict, List, Tuple
from pyspark.sql import DataFrame, functions as F

def _join_pairs_from_strings(specs: List[str]) -> List[Tuple[str, str]]:
    pairs = []
    for s in specs:
        l, r = s.split("=", 1)
        pairs.append((l.strip(), r.strip()))
    return pairs

def _infer_pairs(left: DataFrame, right: DataFrame) -> List[Tuple[str, str]]:
    if "ticker" in left.columns and "ticker" in right.columns:
        return [("ticker", "ticker")]
    commons = [c for c in left.columns if c in right.columns]
    if commons:
        return [(commons[0], commons[0])]
    raise ValueError(f"Cannot infer join keys: left={left.columns} right={right.columns}")

def _join_with_dedupe(left: DataFrame, right: DataFrame, pairs: List[Tuple[str, str]], right_prefix: str, how: str="left") -> DataFrame:
    # build condition
    cond = None
    for l, r in pairs:
        c = (left[l] == right[r])
        cond = c if cond is None else (cond & c)

    # columns to carry from right (avoid duplicating join-right keys and any name that already exists on left)
    right_keep = []
    right_cols = set(right.columns)
    right_join_keys = set(r for _, r in pairs)
    for c in right.columns:
        if c in right_join_keys:
            continue
        alias = c if c not in left.columns else f"{right_prefix}{c}"
        right_keep.append(F.col(c).alias(alias))

    return left.join(right, cond, how=how).select(left["*"], *right_keep)

class CompanyModel:
    def __init__(self, spark, model_cfg: dict, storage_cfg: dict, params: dict | None = None):
        self.spark = spark
        self.model_cfg = model_cfg
        self.storage_cfg = storage_cfg
        self.params = params or {}

    def _bronze_path(self, rel: str) -> str:
        root = self.storage_cfg["roots"]["bronze"]
        return f"{root.rstrip('/')}/{rel}"

    def _load_bronze(self, rel: str) -> DataFrame:
        return self.spark.read.parquet(self._bronze_path(rel))

    def _build_nodes(self) -> Dict[str, DataFrame]:
        nodes = {}
        for n in self.model_cfg["graph"]["nodes"]:
            node_id = n["id"]
            layer, table = n["from"].split(".", 1)
            assert layer == "bronze"

            rel = self.storage_cfg["tables"][table]["rel"]
            df = self._load_bronze(rel)

            if "select" in n and n["select"]:
                cols = [F.col(expr).alias(out_name) for out_name, expr in n["select"].items()]
                df = df.select(*cols)

            if "derive" in n and n["derive"]:
                for out_name, expr in n["derive"].items():
                    if expr == "sha1(ticker)":
                        df = df.withColumn(out_name, F.sha1(F.col("ticker")))
                    elif expr in df.columns:
                        df = df.withColumn(out_name, F.col(expr))
                    else:
                        raise ValueError(f"Unsupported derive expression '{expr}' in node '{node_id}'")

            nodes[node_id] = df
        return nodes

    def _apply_edges(self, nodes: Dict[str, DataFrame]) -> None:
        # Dry-validate edge columns (limit(1) to keep this cheap)
        for e in self.model_cfg["graph"].get("edges", []):
            left = nodes[e["from"]]
            right = nodes[e["to"]]
            pairs = _join_pairs_from_strings(e["on"]) if e.get("on") else _infer_pairs(left, right)
            # plan-only validation
            _ = left.limit(1).join(right.limit(1), on=[left[l] == right[r] for l, r in pairs], how="left")

    def _materialize_paths(self, nodes: Dict[str, DataFrame]) -> Dict[str, DataFrame]:
        facts = {}
        for p in self.model_cfg["graph"].get("paths", []):
            path_id = p["id"]
            hops = p["hops"]
            chain = [h.strip() for h in (hops.split("->") if isinstance(hops, str) else (hops[0].split("->") if len(hops)==1 and "->" in hops[0] else hops))]

            df = nodes[chain[0]]
            for i in range(len(chain) - 1):
                l_id, r_id = chain[i], chain[i + 1]
                left, right = df, nodes[r_id]
                edge = next((e for e in self.model_cfg["graph"].get("edges", []) if e["from"] == l_id and e["to"] == r_id), None)
                pairs = _join_pairs_from_strings(edge["on"]) if edge and edge.get("on") else _infer_pairs(left, right)

                # right_prefix keeps columns distinct; e.g., "dim_exchange__"
                right_prefix = f"{r_id}__"
                df = _join_with_dedupe(left, right, pairs, right_prefix, how="left")

            facts[path_id] = df
        return facts

    def build(self):
        nodes = self._build_nodes()
        self._apply_edges(nodes)
        facts = self._materialize_paths(nodes)
        dims = {k: v for k, v in nodes.items() if k.startswith("dim_")}
        return dims, facts
