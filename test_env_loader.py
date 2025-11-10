"""
Test script to verify environment variable loading and credential injection
"""
from utils.env_loader import inject_credentials_into_config
from pathlib import Path
import json

# Load configs - CORRECT way: read file first, then parse JSON
root = Path(__file__).parent
polygon_cfg = json.loads((root / "configs" / "polygon_endpoints.json").read_text())
storage = json.loads((root / "configs" / "storage.json").read_text())

print("=" * 70)
print("BEFORE INJECTION:")
print("=" * 70)
print(f"API Keys: {polygon_cfg['credentials']['api_keys']}")
print(f"Base URL: {polygon_cfg['base_urls']['core']}")
print()

# Inject credentials from environment
polygon_cfg = inject_credentials_into_config(polygon_cfg, 'polygon')

print("=" * 70)
print("AFTER INJECTION:")
print("=" * 70)
print(f"API Keys: {polygon_cfg['credentials']['api_keys']}")
print(f"Number of keys: {len(polygon_cfg['credentials']['api_keys'])}")

if polygon_cfg['credentials']['api_keys']:
    first_key = polygon_cfg['credentials']['api_keys'][0]
    print(f"First key (partial): {first_key[:15]}...")
    print(f"✓ Credentials successfully loaded from .env file!")
else:
    print("✗ No API keys loaded - check your .env file")

print()
print("=" * 70)
print("FULL CONFIG:")
print("=" * 70)
print(json.dumps(polygon_cfg, indent=2))
