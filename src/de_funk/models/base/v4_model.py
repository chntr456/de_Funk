"""
V4Model - BaseModel subclass for v4 domain configs.

Handles v4-specific build behaviors that can't be expressed in
standard graph.nodes:
- Seed/static tables (inline data blocks)
- Multi-source UNION tables
- Transform-based sources (unpivot, aggregate)

Works with translated configs from v4_to_nodes.translate_v4_config(),
which synthesizes graph.nodes from v4 tables + sources.
"""

from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class V4Model:
    """
    BaseModel subclass that handles v4 domain config specifics.

    This class is used by V4Builder to build models defined in
    the v4 multi-file domain config format.

    Usage:
        from de_funk.config.domain.v4_to_nodes import translate_v4_config
        translated = translate_v4_config(v4_config)
        model = V4Model(connection, storage_cfg, translated, params, repo_root)
        model.build()
    """

    # Import BaseModel lazily to avoid circular imports
    _base_class = None

    @classmethod
    def _get_base_class(cls):
        if cls._base_class is None:
            from de_funk.models.base.model import BaseModel
            cls._base_class = BaseModel
        return cls._base_class

    def __new__(cls, *args, **kwargs):
        """Dynamically inherit from BaseModel to avoid import-time issues."""
        base = cls._get_base_class()
        # Create a new class that inherits from both V4Model and BaseModel
        if not issubclass(cls, base):
            # Rebuild the class with BaseModel as parent
            cls = type('V4Model', (cls, base), dict(cls.__dict__))
            cls._base_class = base
        return base.__new__(cls)

    def __init__(
        self,
        connection,
        storage_cfg: Dict,
        model_cfg: Dict,
        params: Dict = None,
        repo_root: Optional[Path] = None,
    ):
        base = self._get_base_class()
        base.__init__(self, connection, storage_cfg, model_cfg, params, repo_root)

        # V4-specific state
        self._v4_build = model_cfg.get("_v4_build", {})
        self._v4_sources_by_target = model_cfg.get("_v4_sources_by_target", {})

    def custom_node_loading(
        self,
        node_id: str,
        node_config: Dict,
    ) -> Optional[DataFrame]:
        """
        Handle v4-specific node types that GraphBuilder can't process.

        Intercepts:
        - __seed__ nodes: create DataFrame from inline data
        - __union__ nodes: load and UNION multiple sources
        - __generated__ nodes: post-build computation (returns None to skip)
        """
        from_spec = node_config.get("from", "")

        if from_spec == "__seed__":
            return self._build_seed_node(node_id, node_config)

        if from_spec == "__union__":
            return self._build_union_node(node_id, node_config)

        if from_spec == "__generated__":
            # Generated tables are built in after_build, skip here
            logger.info(f"Deferring generated table '{node_id}' to after_build")
            return self._create_empty_df(node_config)

        # Check for transform-based sources
        if node_config.get("_v4_transform") == "unpivot":
            return self._build_unpivot_node(node_id, node_config)

        # Default: let GraphBuilder handle it
        return None

    def _build_seed_node(
        self,
        node_id: str,
        node_config: Dict,
    ) -> DataFrame:
        """Create a DataFrame from inline seed data."""
        seed_data = node_config.get("_v4_seed_data", [])
        schema = node_config.get("_v4_schema", [])

        if not seed_data:
            logger.warning(f"Seed table '{node_id}' has no data rows")
            return self._create_empty_df(node_config)

        logger.info(f"Building seed table '{node_id}' with {len(seed_data)} rows")

        if self.backend == "spark":
            return self._seed_to_spark_df(seed_data, schema)
        else:
            return self._seed_to_duckdb_df(seed_data, schema)

    def _build_union_node(
        self,
        node_id: str,
        node_config: Dict,
    ) -> DataFrame:
        """Load multiple sources and UNION them."""
        sources = node_config.get("_v4_union_sources", [])
        if not sources:
            logger.warning(f"Union table '{node_id}' has no sources")
            return self._create_empty_df(node_config)

        logger.info(
            f"Building UNION table '{node_id}' from {len(sources)} sources"
        )

        dfs = []
        for source in sources:
            from_spec = source.get("from", "")
            if not from_spec:
                continue

            # Load the source table
            normalized_from = from_spec
            if "." in from_spec:
                layer, table = from_spec.split(".", 1)
                if layer == "bronze":
                    try:
                        df = self.graph_builder._load_bronze_table(table)
                    except Exception as e:
                        logger.warning(
                            f"Skipping source '{source.get('_source_name', '?')}' "
                            f"for union '{node_id}': {e}"
                        )
                        continue
                else:
                    try:
                        df = self.graph_builder._load_silver_table(layer, table)
                    except Exception as e:
                        logger.warning(
                            f"Skipping source for union '{node_id}': {e}"
                        )
                        continue
            else:
                logger.warning(
                    f"Union source has no dot notation: '{from_spec}'"
                )
                continue

            # Apply aliases as select
            aliases = source.get("aliases", [])
            if aliases:
                select_dict = {}
                for alias in aliases:
                    if isinstance(alias, list) and len(alias) >= 2:
                        select_dict[alias[0]] = str(alias[1])
                if select_dict:
                    df = self._select_columns(df, select_dict)

            # Inject discriminators
            if source.get("domain_source"):
                df = self._apply_derive(
                    df, "domain_source", source["domain_source"], node_id
                )
            if source.get("entry_type"):
                df = self._apply_derive(
                    df, "entry_type", f"'{source['entry_type']}'", node_id
                )

            dfs.append(df)

        if not dfs:
            return self._create_empty_df(node_config)

        # UNION all DataFrames
        result = dfs[0]
        for df in dfs[1:]:
            if self.backend == "spark":
                result = result.unionByName(df, allowMissingColumns=True)
            else:
                # DuckDB: use SQL UNION ALL
                import pandas as pd
                if hasattr(result, 'df'):
                    result = result.df()
                if hasattr(df, 'df'):
                    df = df.df()
                result = pd.concat([result, df], ignore_index=True)
                result = self.connection.conn.from_df(result)

        return result

    def _build_unpivot_node(
        self,
        node_id: str,
        node_config: Dict,
    ) -> Optional[DataFrame]:
        """Handle unpivot transform on a source."""
        unpivot_plan = node_config.get("_v4_unpivot_plan", {})
        if not unpivot_plan:
            return None

        # Load the base table normally first
        from_spec = node_config.get("from", "")
        if not from_spec or from_spec.startswith("__"):
            return None

        # Let GraphBuilder load the raw table, then apply unpivot in after_build
        # For now, return None to let normal loading proceed
        return None

    def _create_empty_df(self, node_config: Dict) -> DataFrame:
        """Create an empty DataFrame with schema from node config."""
        schema = node_config.get("_v4_schema", [])
        col_names = [col[0] for col in schema if isinstance(col, list)]

        if self.backend == "spark":
            from pyspark.sql.types import StructType, StructField, StringType
            spark_schema = StructType([
                StructField(name, StringType(), True) for name in col_names
            ])
            return self.connection.spark.createDataFrame([], spark_schema)
        else:
            import pandas as pd
            empty = pd.DataFrame(columns=col_names)
            return self.connection.conn.from_df(empty)

    def _seed_to_spark_df(
        self,
        seed_data: List[Dict],
        schema: List,
    ) -> DataFrame:
        """Convert seed data to a Spark DataFrame."""
        from pyspark.sql.types import (
            StructType, StructField, StringType, IntegerType,
            LongType, DoubleType, BooleanType,
        )

        type_map = {
            "string": StringType(),
            "int": IntegerType(),
            "integer": IntegerType(),
            "long": LongType(),
            "double": DoubleType(),
            "float": DoubleType(),
            "boolean": BooleanType(),
            "bool": BooleanType(),
        }

        fields = []
        for col in schema:
            if isinstance(col, list) and len(col) >= 2:
                col_name = col[0]
                col_type = str(col[1]).lower()
                nullable = col[2] if len(col) > 2 and isinstance(col[2], bool) else True
                spark_type = type_map.get(col_type, StringType())
                fields.append(StructField(col_name, spark_type, nullable))

        spark_schema = StructType(fields) if fields else None
        return self.connection.spark.createDataFrame(seed_data, spark_schema)

    def _seed_to_duckdb_df(
        self,
        seed_data: List[Dict],
        schema: List,
    ) -> DataFrame:
        """Convert seed data to a DuckDB relation."""
        import pandas as pd
        df = pd.DataFrame(seed_data)
        return self.connection.conn.from_df(df)

    @property
    def graph_builder(self):
        """Access the graph builder (lazy-loaded by BaseModel)."""
        if self._graph_builder is None:
            from de_funk.models.base.graph_builder import GraphBuilder
            self._graph_builder = GraphBuilder(self)
        return self._graph_builder

    def _apply_derive(self, df, out_name, expr, node_id):
        """Delegate to graph_builder's derive logic."""
        return self.graph_builder._apply_derive(df, out_name, expr, node_id)
