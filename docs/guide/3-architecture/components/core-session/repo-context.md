# Core Session - Repo Context

## Overview

**RepoContext** is the primary entry point for all de_Funk applications. It initializes the runtime environment, loads configurations, and creates appropriate database connections.

## Class Definition

```python
# File: core/context.py:21-79

@dataclass
class RepoContext:
    """
    Repository context with connection management.

    Attributes:
        repo: Repository root path
        spark: Spark session (None if using DuckDB)
        polygon_cfg: Polygon API configuration
        storage: Storage configuration
        connection: DataConnection instance (Spark or DuckDB)
        connection_type: Backend type ('spark' or 'duckdb')
    """
    repo: Path
    spark: Any  # SparkSession or None
    polygon_cfg: Dict[str, Any]
    storage: Dict[str, Any]
    connection: Optional[Any] = None
    connection_type: str = "spark"

    @classmethod
    def from_repo_root(cls, connection_type: Optional[str] = None) -> "RepoContext":
        """
        Create RepoContext from repository root.

        Args:
            connection_type: Override connection type ('spark' or 'duckdb').
                           If None, reads from storage.json config.

        Returns:
            RepoContext with appropriate connection
        """
        here = Path(__file__).resolve()
        root = _repo_root(here)

        # Load configurations
        polygon_cfg = json.loads((root / "configs" / "polygon_endpoints.json").read_text())
        storage = json.loads((root / "configs" / "storage.json").read_text())

        # Determine connection type
        if connection_type is None:
            connection_type = storage.get("connection", {}).get("type", "spark")

        # Create connection based on type
        if connection_type == "duckdb":
            from core.connection import ConnectionFactory
            duckdb_path = root / "storage" / "duckdb" / "analytics.db"
            duckdb_path.parent.mkdir(parents=True, exist_ok=True)
            connection = ConnectionFactory.create("duckdb", db_path=str(duckdb_path))
            spark = None
        else:
            from orchestration.common.spark_session import get_spark
            spark = get_spark("CompanyPipeline")
            from core.connection import ConnectionFactory
            connection = ConnectionFactory.create("spark", spark_session=spark)

        return cls(
            repo=root,
            spark=spark,
            polygon_cfg=polygon_cfg,
            storage=storage,
            connection=connection,
            connection_type=connection_type
        )
```

## Repository Root Detection

```python
# File: core/context.py:7-19

def _repo_root(start: Path) -> Path:
    """
    Walk up directory tree to find repository root.

    Looks for markers: configs/ and core/ directories.
    """
    cur = start if start.is_dir() else start.parent

    while cur != cur.parent:
        if (cur / "configs").exists() and (cur / "core").exists():
            return cur
        cur = cur.parent

    return start.parent if start.is_file() else start
```

## Configuration Loading

### Storage Configuration

```json
// configs/storage.json
{
  "connection": {
    "type": "duckdb",  // or "spark"
    "options": {
      "threads": 4,
      "memory_limit": "4GB"
    }
  },
  "roots": {
    "bronze": "storage/bronze",
    "silver": "storage/silver",
    "gold": "storage/gold"
  }
}
```

### API Configuration

```json
// configs/polygon_endpoints.json
{
  "endpoints": {
    "base": "https://api.polygon.io"
  },
  "credentials": {
    "api_keys": ["key1", "key2"]
  },
  "rate_limit": 5
}
```

## Usage Patterns

### Pattern 1: Default Initialization

```python
# Uses configuration from storage.json
ctx = RepoContext.from_repo_root()

print(f"Backend: {ctx.connection_type}")
print(f"Repo: {ctx.repo}")
```

### Pattern 2: Force Backend

```python
# Override to use DuckDB
ctx = RepoContext.from_repo_root(connection_type='duckdb')

# Override to use Spark
ctx = RepoContext.from_repo_root(connection_type='spark')
```

### Pattern 3: Script Initialization

```python
#!/usr/bin/env python
"""Data pipeline script."""

from core.context import RepoContext

def main():
    # Initialize context
    ctx = RepoContext.from_repo_root(connection_type='spark')

    # Access configurations
    bronze_root = ctx.storage['roots']['bronze']
    polygon_cfg = ctx.polygon_cfg

    # Use connection
    df = ctx.connection.read_table(f"{bronze_root}/polygon/prices_daily")

if __name__ == "__main__":
    main()
```

---

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/core-session/repo-context.md`
