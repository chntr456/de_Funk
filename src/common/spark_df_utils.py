from __future__ import annotations
from typing import Dict, Iterable, Tuple
from functools import reduce
from pyspark.sql import DataFrame, functions as F, types as T

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

# NEW: build a StructType from a simple spec like [("o","double"),("t","long"),...]
def struct_from_spec(spec: Iterable[Tuple[str, str]]) -> T.StructType:
    type_map = {
        "string": T.StringType(),
        "double": T.DoubleType(),
        "float": T.FloatType(),
        "long": T.LongType(),
        "int": T.IntegerType(),
        "integer": T.IntegerType(),
        "boolean": T.BooleanType(),
        "date": T.DateType(),
        "timestamp": T.TimestampType(),
        "binary": T.BinaryType(),
        "short": T.ShortType(),
        "byte": T.ByteType(),
        "decimal": T.DecimalType(38, 18)
    }
    fields = []
    for name, tname in spec:
        t = type_map.get(tname.lower())
        if t is None:
            raise ValueError(f"Unsupported type in spec: {tname} for field {name}")
        fields.append(T.StructField(name, t, True))
    return T.StructType(fields)
