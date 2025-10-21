from src.ingest.prices_ticker_job import run_ticker_prices_to_bronze
run_ticker_prices_to_bronze("configs/polygon_endpoints.json", "configs/storage.json", ["HUM","UNH"], "2024-01-01", "2024-01-05")
