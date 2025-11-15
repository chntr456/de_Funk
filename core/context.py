from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Optional
from config import ConfigLoader, AppConfig

@dataclass
class RepoContext:
    """
    Repository context with database connection and configuration.

    Now powered by the unified ConfigLoader system for consistent configuration management.
    """
    repo: Path
    spark: Any  # Kept for backward compatibility
    polygon_cfg: Dict[str, Any]
    storage: Dict[str, Any]
    connection: Optional[Any] = None  # DataConnection (DuckDB or Spark)
    connection_type: str = "spark"  # Default to spark for backward compatibility
    _config: Optional[AppConfig] = None  # Internal: full typed config

    @classmethod
    def from_repo_root(cls, connection_type: Optional[str] = None) -> "RepoContext":
        """
        Create RepoContext from repository root.

        Now uses ConfigLoader for centralized, validated configuration loading.

        Args:
            connection_type: Override connection type ('spark' or 'duckdb').
                           If None, uses precedence: env var > storage.json > default

        Returns:
            RepoContext with appropriate connection
        """
        # Use ConfigLoader for centralized config management
        loader = ConfigLoader()
        config = loader.load(connection_type=connection_type)

        # Create connection based on type
        spark = None
        connection = None

        if config.connection.type == "duckdb":
            from core.connection import ConnectionFactory
            # Get DuckDB path from config
            duckdb_path = config.connection.duckdb.database_path
            duckdb_path.parent.mkdir(parents=True, exist_ok=True)
            connection = ConnectionFactory.create("duckdb", db_path=str(duckdb_path))
            # DuckDB-only mode: No Spark needed for UI/analytics
            spark = None
        else:
            # Spark mode
            from orchestration.common.spark_session import get_spark
            # Pass SparkConfig to get_spark for proper configuration
            spark = get_spark("CompanyPipeline", spark_config=config.connection.spark)
            from core.connection import ConnectionFactory
            connection = ConnectionFactory.create("spark", spark_session=spark)

        # Build backward-compatible polygon_cfg dict
        # BaseRegistry expects specific structure: base_urls dict, rate_limit_per_sec number
        polygon_api = config.apis.get("polygon")
        if polygon_api:
            # Convert base_url string to base_urls dict format
            base_urls = {"core": polygon_api.base_url}

            # Convert rate_limit calls/period to calls per second
            rate_limit_per_sec = polygon_api.rate_limit_calls / polygon_api.rate_limit_period

            polygon_cfg = {
                "base_urls": base_urls,
                "endpoints": polygon_api.endpoints,
                "api_keys": polygon_api.api_keys,
                "rate_limit_per_sec": rate_limit_per_sec,
                "headers": polygon_api.headers,
            }
        else:
            polygon_cfg = {}

        # Build backward-compatible storage dict
        # Models expect the original storage.json structure with "roots" nested dict
        # Load raw storage.json to get all roots (including model-specific silver roots)
        storage_json_path = config.repo_root / "configs" / "storage.json"
        if storage_json_path.exists():
            import json
            with open(storage_json_path) as f:
                storage_json = json.load(f)
            roots = storage_json.get("roots", {})
        else:
            # Fallback: minimal roots if storage.json not found
            roots = {
                "bronze": str(config.storage.bronze_root),
                "silver": str(config.storage.silver_root),
            }

        storage_dict = {
            "roots": roots,
            "tables": config.storage.tables,
            "connection": {
                "type": config.connection.type,
            }
        }

        return cls(
            repo=config.repo_root,
            spark=spark,
            polygon_cfg=polygon_cfg,
            storage=storage_dict,
            connection=connection,
            connection_type=config.connection.type,
            _config=config,
        )

    @property
    def config(self) -> Optional[AppConfig]:
        """Get the full typed configuration object."""
        return self._config
