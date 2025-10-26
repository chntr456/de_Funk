# scripts/examples/use_bronze_direct.py
from pyspark.sql import functions as F
from src.orchestration.context import RepoContext
from src.model.api.session import ModelSession

DATE_FROM = "2024-01-01"
DATE_TO   = "2024-01-05"

ctx = RepoContext.from_repo_root()
ms = ModelSession(ctx.spark, ctx.repo, ctx.storage)

news_bronze = ms.bronze("news").read().where(F.col("publish_date").between(DATE_FROM, DATE_TO))
news_bronze.select("publish_date","ticker","title","source","sentiment").show(10, truncate=False)

df_filtered = news_bronze.filter(F.col("sentiment").isNotNull())
df_filtered.show(100)