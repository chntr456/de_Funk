from src.ingest.exchanges_job import run_exchanges_to_bronze
run_exchanges_to_bronze("configs/polygon_endpoints.json", "configs/storage.json")
