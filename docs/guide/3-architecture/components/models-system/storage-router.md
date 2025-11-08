# Models System - Storage Router

## Overview

**StorageRouter** resolves logical table names to physical storage paths. It provides layer-aware path resolution for Bronze, Silver, and Gold data.

## Class Definition

```python
# File: models/api/dal.py:25-120

class StorageRouter:
    """Resolves logical names to physical storage paths."""

    def __init__(self, storage_cfg: Dict):
        self.storage_cfg = storage_cfg
        self.bronze_root = Path(storage_cfg['roots']['bronze'])
        self.silver_root = Path(storage_cfg['roots']['silver'])
        self.gold_root = Path(storage_cfg.get('roots', {}).get('gold', 'storage/gold'))

    def resolve(self, spec: str) -> str:
        """
        Resolve logical spec to physical path.

        Args:
            spec: Logical spec (e.g., "bronze.polygon.prices_daily")

        Returns:
            Physical path (e.g., "storage/bronze/polygon/prices_daily")

        Examples:
            "bronze.polygon.prices_daily" -> "storage/bronze/polygon/prices_daily"
            "silver.companies" -> "storage/silver/companies"
            "gold.aggregated_metrics" -> "storage/gold/aggregated_metrics"
        """
        parts = spec.split('.')
        
        if len(parts) < 2:
            raise ValueError(f"Invalid spec format: {spec}")
        
        layer = parts[0]  # bronze, silver, gold
        
        if layer == 'bronze':
            return self.resolve_bronze(parts[1:])
        elif layer == 'silver':
            return self.resolve_silver(parts[1:])
        elif layer == 'gold':
            return self.resolve_gold(parts[1:])
        else:
            raise ValueError(f"Unknown layer: {layer}")

    def resolve_bronze(self, parts: List[str]) -> str:
        """
        Resolve Bronze path.

        Args:
            parts: [provider, dataset]

        Example:
            ["polygon", "prices_daily"] -> "storage/bronze/polygon/prices_daily"
        """
        if len(parts) != 2:
            raise ValueError(f"Bronze spec requires [provider, dataset]: {parts}")
        
        provider, dataset = parts
        return str(self.bronze_root / provider / dataset)

    def resolve_silver(self, parts: List[str]) -> str:
        """
        Resolve Silver path.

        Args:
            parts: [table_name]

        Example:
            ["companies"] -> "storage/silver/companies"
        """
        if len(parts) != 1:
            raise ValueError(f"Silver spec requires [table_name]: {parts}")
        
        table_name = parts[0]
        return str(self.silver_root / table_name)

    def resolve_gold(self, parts: List[str]) -> str:
        """
        Resolve Gold path.

        Args:
            parts: [table_name]

        Example:
            ["aggregated_metrics"] -> "storage/gold/aggregated_metrics"
        """
        if len(parts) != 1:
            raise ValueError(f"Gold spec requires [table_name]: {parts}")
        
        table_name = parts[0]
        return str(self.gold_root / table_name)

    def get_bronze_path(self, provider: str, dataset: str) -> Path:
        """Convenience method for Bronze paths."""
        return self.bronze_root / provider / dataset

    def get_silver_path(self, table_name: str) -> Path:
        """Convenience method for Silver paths."""
        return self.silver_root / table_name

    def get_gold_path(self, table_name: str) -> Path:
        """Convenience method for Gold paths."""
        return self.gold_root / table_name
```

## Usage Examples

### Example 1: Basic Resolution

```python
from models.api.dal import StorageRouter

router = StorageRouter(storage_cfg)

# Bronze resolution
path = router.resolve("bronze.polygon.prices_daily")
# Result: "storage/bronze/polygon/prices_daily"

# Silver resolution
path = router.resolve("silver.companies")
# Result: "storage/silver/companies"

# Gold resolution
path = router.resolve("gold.metrics")
# Result: "storage/gold/metrics"
```

### Example 2: In Model Definitions

```yaml
# configs/models/company.yaml
graph:
  nodes:
    - id: fact_prices
      from: bronze.polygon.prices_daily  # Router resolves this
    
    - id: dim_companies
      from: silver.companies  # Router resolves this
```

### Example 3: Direct Path Methods

```python
router = StorageRouter(storage_cfg)

# Bronze path
bronze_path = router.get_bronze_path('polygon', 'prices_daily')

# Silver path
silver_path = router.get_silver_path('companies')

# Gold path
gold_path = router.get_gold_path('metrics')
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/models-system/storage-router.md`
