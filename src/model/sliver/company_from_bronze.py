from __future__ import annotations
from pyspark.sql import SparkSession, DataFrame, functions as F

def load_bronze_prices(spark: SparkSession, root="storage", date_from=None, date_to=None) -> DataFrame:
    df = spark.read.parquet(f"{root}/bronze/prices_daily")
    if date_from: df = df.where(F.col("trade_date") >= F.lit(date_from))
    if date_to:   df = df.where(F.col("trade_date") <= F.lit(date_to))
    return df

def load_bronze_news(spark: SparkSession, root="storage", date_from=None, date_to=None) -> DataFrame:
    df = spark.read.parquet(f"{root}/bronze/news")
    if date_from: df = df.where(F.col("publish_date") >= F.lit(date_from))
    if date_to:   df = df.where(F.col("publish_date") <= F.lit(date_to))
    return df

def load_bronze_ref(spark: SparkSession, root="storage", snap: str | None = None) -> DataFrame:
    df = spark.read.parquet(f"{root}/bronze/ref_ticker")
    if snap: df = df.where(F.input_file_name().contains(f"snapshot_dt={snap}"))
    return df

def load_bronze_exchanges(spark: SparkSession, root="storage", snap: str | None = None) -> DataFrame:
    df = spark.read.parquet(f"{root}/bronze/exchanges")
    if snap: df = df.where(F.input_file_name().contains(f"snapshot_dt={snap}"))
    return df

def build_company_dims_and_facts(spark: SparkSession, root="storage", snapshot_dt=None, date_from=None, date_to=None):
    prices = load_bronze_prices(spark, root, date_from, date_to)
    news   = load_bronze_news(spark, root, date_from, date_to)
    ref    = load_bronze_ref(spark, root, snapshot_dt)
    ex     = load_bronze_exchanges(spark, root, snapshot_dt)
    dim_exchange = ex.select("exchange_id","code","name").dropDuplicates()
    dim_company  = (ref.withColumn("company_id", F.abs(F.hash("ticker")).cast("bigint"))
                       .select("company_id","ticker","name","exchange_code"))
    fact_prices = prices.select("trade_date","ticker","open","high","low","close","volume_weighted","volume")
    fact_news   = news.select("publish_dt","ticker","source","id","title","description")
    return {"dim_company": dim_company, "dim_exchange": dim_exchange}, {"fact_prices": fact_prices, "fact_news_sentiment": fact_news}
