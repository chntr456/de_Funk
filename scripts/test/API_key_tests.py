from utils.env_loader import inject_credentials_into_config
from pathlib import Path
import json


# Load configs
polygon_cfg = json.loads(Path("configs/polygon_endpoints.json").read_text())


polygon_cfg = inject_credentials_into_config(polygon_cfg, 'polygon')

print(polygon_cfg)