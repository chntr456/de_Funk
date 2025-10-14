from __future__ import annotations
from typing import Dict, Iterable, Tuple, Optional
from functools import reduce
from pyspark.sql import DataFrame, functions as F

def project_with_mapping(
    df: DataFrame,
    rename_map: Dict[str, str] | None = None,
    casts: Dict[str, str] | None = None,
    literals: Dict[str, tuple[str, object]] | None = None,
    keep: Iterable[str] | None = None
) -> DataFrame:
    rename_map = rename_map or {}
    casts = casts or {}
    literals = literals or {}
    keep = list(keep) if keep else None

    exprs = {}
    for c in df.columns:
        out = rename_map.get(c, c)
        exprs[out] = F.col(c)

    for col, spark_type in casts.items():
        if col in exprs:
            exprs[col] = exprs[col].cast(spark_type)

    for col, (spark_type, value) in literals.items():
        exprs[col] = F.lit(value).cast(spark_type) if spark_type else F.lit(value)

    if keep:
        final = []
        for k in keep:
            if k in exprs:
                final.append(exprs[k].alias(k))
            else:
                t = casts.get(k, None)
                final.append((F.lit(None).cast(t) if t else F.lit(None)).alias(k))
    else:
        final = [exprs[k].alias(k) for k in exprs.keys()]

    return df.select(*final)

def epoch_ms_to_date(col):
    return F.to_date(F.from_unixtime((F.col(col) / 1000).cast("long")))

def union_all(dfs: Iterable[DataFrame]) -> DataFrame:
    dfs = [d for d in dfs if d is not None]
    if not dfs:
        raise ValueError("union_all: no DataFrames provided")
    return reduce(lambda a, b: a.unionByName(b, allowMissingColumns=True), dfs)
