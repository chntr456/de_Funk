from src.ingest.fundamentals_job import run_fundamentals_to_bronze
run_fundamentals_to_bronze("configs/polygon_endpoints.json", "configs/storage.json", ["HUM","UNH"])
