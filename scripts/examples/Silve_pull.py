# scripts/examples/use_model_news_prices.py
from src.orchestration.context import RepoContext
from src.model.api.session import ModelSession
from src.model.api.services import NewsAPI, PricesAPI

DATE_FROM = "2024-01-01"
DATE_TO   = "2024-01-05"

ctx = RepoContext.from_repo_root()
ms = ModelSession(ctx.spark, ctx.repo, ctx.storage)

news = NewsAPI(ms)
prices = PricesAPI(ms)

df_news = news.news_with_company_df(DATE_FROM, DATE_TO, only_matched=True)
df_news.show(10, truncate=False)

df_prices = prices.prices_with_company_df(DATE_FROM, DATE_TO, only_matched=False)
df_prices.show(10, truncate=False)

# grab a small python list for scripting
items = news.news_items(DATE_FROM, DATE_TO, limit=50)
print(items[:3])
