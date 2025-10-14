from __future__ import annotations
from typing import Iterable, List, Tuple
from pyspark.sql import DataFrame, functions as F
from pyspark.sql import SparkSession
from src.data_pipelines.facets.base_facet import Facet
from src.common.spark_df_utils import project_with_mapping

class ExchangesFacet(Facet):
    name = "exchanges"

    RENAME_MAP = {"exchange": "code"}

    OUTPUT_SCHEMA: List[Tuple[str, str]] = [
        ("exchange_id", "bigint"),
        ("code",        "string"),
        ("name",        "string"),
    ]

    LITERALS = {}
    DERIVED = {}  # exchange_id derived in postprocess (needs a function)

    def __init__(self, spark: SparkSession):
        super().__init__(spark)

    def calls(self) -> Iterable[dict]:
        yield {"ep_name": "exchanges", "params": {}}

    def postprocess(self, df: DataFrame) -> DataFrame:
        # Guarantee presence of code/name, then derive id
        df = project_with_mapping(df, casts={"code": "string", "name": "string"}, keep=["code", "name"])
        df = df.withColumn("exchange_id", F.monotonically_increasing_id().cast("bigint"))
        return df.select("exchange_id", "code", "name")
