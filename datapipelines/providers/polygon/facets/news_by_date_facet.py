from __future__ import annotations
from datetime import date, timedelta
from typing import Iterable
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StringType, MapType
from datapipelines.providers.polygon.facets.polygon_base_facet import PolygonFacet

def _date_iter(a: str, b: str):
    s = date.fromisoformat(a); e = date.fromisoformat(b)
    while s <= e:
        yield s.isoformat(); s += timedelta(days=1)

class NewsByDateFacet(PolygonFacet):
    SPARK_CASTS = {
        "publish_date":"date", "ticker":"string",
        "article_id":"string", "title":"string", "source":"string", "sentiment":"string"
    }
    FINAL_COLUMNS = [
        ("publish_date","date"), ("ticker","string"),
        ("article_id","string"), ("title","string"),
        ("source","string"), ("sentiment","string")
    ]

    def __init__(self, spark, *, date_from: str, date_to: str):
        super().__init__(spark, date_from=date_from, date_to=date_to)

    def calls(self) -> Iterable[dict]:
        for d in _date_iter(self.date_from, self.date_to):
            yield {
                "ep_name": "news_by_date",
                "params": {
                    "query": {
                        "published_utc.gte": f"{d}T00:00:00Z",
                        "published_utc.lte": f"{d}T23:59:59Z"
                    },
                    "publish_date": d
                }
            }

    def _source_expr(self, df):
        """
        Build a safe 'source' expression:
        - prefer existing df['source'] if present
        - else try publisher.name when publisher is a struct with 'name'
        - else cast publisher to string if it is a string
        - else NULL
        """
        if "source" in df.columns:
            return F.col("source").cast("string")

        if "publisher" in df.columns:
            pfield = df.schema["publisher"].dataType
            if isinstance(pfield, StructType):
                # check field existence on the struct
                names = [f.name for f in pfield.fields]
                if "name" in names:
                    return F.col("publisher.name").cast("string")
                # sometimes 'publisher' struct is { name: <str>, homepage_url: <str>, ... }
                # if no 'name', fallback to struct->string (will be JSON-ish) or NULL
                return F.to_json(F.col("publisher")).cast("string")
            if isinstance(pfield, StringType):
                return F.col("publisher").cast("string")
            if isinstance(pfield, MapType):
                # map<string, string>, try ["name"]
                return F.col("publisher")["name"].cast("string")

        return F.lit(None).cast("string")

    def _sentiment_expr(self, df):
        # Not all payloads include sentiment; default to NULL when missing
        return F.col("sentiment").cast("string") if "sentiment" in df.columns else F.lit(None).cast("string")

    def postprocess(self, df):
        # If payload already has a publish_date, drop it so we can standardize
        tmp = df
        if "publish_date" in tmp.columns:
            tmp = tmp.drop("publish_date")

        tmp = (
            tmp
            .withColumn("publish_ts", F.to_timestamp("published_utc"))
            .withColumn("publish_date", F.to_date("publish_ts"))
            .withColumn("ticker", F.explode_outer("tickers"))
        )

        src_expr = self._source_expr(tmp)
        sent_expr = self._sentiment_expr(tmp)

        out = (
            tmp.select(
                "publish_date",
                F.col("ticker").cast("string"),
                F.col("id").cast("string").alias("article_id"),
                F.col("title").cast("string").alias("title"),
                src_expr.alias("source"),
                sent_expr.alias("sentiment"),
            )
            .dropna(subset=["publish_date", "ticker", "article_id"])
            .dropDuplicates(["publish_date", "ticker", "article_id"])
        )

        # Enforce final casts/order if declared on the facet
        return out

