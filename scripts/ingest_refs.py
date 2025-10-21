from src.ingest.ref_ticker_job import run_ref_ticker_to_bronze
run_ref_ticker_to_bronze("configs/polygon_endpoints.json", "configs/storage.json", ["HUM","UNH"])
