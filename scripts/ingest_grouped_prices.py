from src.ingest.prices_grouped_job import run_grouped_prices_to_bronze
run_grouped_prices_to_bronze("configs/polygon_endpoints.json", "configs/storage.json", "2024-01-01", "2024-01-05")
