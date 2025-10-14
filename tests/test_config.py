import json
from pathlib import Path
from src.common.config_loader import ConfigLoader

def main():

    # go up one directory from /tests/
    root = Path(__file__).resolve().parents[1]
    cfg_path = root / "configs" / "polygon_endpoints.json"

    loader = ConfigLoader(str(cfg_path))
    cfg = loader.injected()



    print("✅ Config successfully loaded.")
    print("Keys:", list(cfg.keys()))
    print("Base URLs:", cfg.get("base_urls"))
    print("Rate limit:", cfg.get("rate_limit_per_sec"))

    headers = cfg.get("headers", {})
    print("\nAuthorization Header:")
    print(headers.get("Authorization"))

    creds = cfg.get("credentials", {})
    print("\nAPI Key from credentials:")
    print(creds.get("api_key"))

    if "${API_KEY}" in headers.get("Authorization", ""):
        print("❌ Key not injected.")
    else:
        print("✅ Key properly injected into headers.")

if __name__ == "__main__":
    main()


