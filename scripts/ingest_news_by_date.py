from src.ingest.news_by_date_job import run_news_to_bronze
run_news_to_bronze("configs/polygon_endpoints.json", "configs/storage.json", "2024-01-01", "2024-01-03")
