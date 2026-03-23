"""
BaseModel — Generic model class with YAML-driven graph building.

Build-only: handles node loading from Bronze, graph building,
table separation (dims/facts), and persistence to Silver.

Query methods have been removed — FieldResolver + Engine handle all queries.

Composition:
    GraphBuilder: Graph building and node loading (delegates to NodeExecutor)
    ModelWriter: Persistence to storage (delegates to Engine.write)
"""
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Try to import PySpark (may not be available when using DuckDB)
try:
    from pyspark.sql import DataFrame as SparkDataFrame, functions as F
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    SparkDataFrame = None
    F = None

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class BaseModel:
    """
    Build-only model class. Reads YAML config and builds Silver tables.

    Lifecycle:
        1. __init__: connection + config + params
        2. build(): GraphBuilder → NodeExecutor → dims/facts
        3. write_tables(): Engine.write or ModelWriter → Delta Lake
        4. Hooks: _run_hooks() dispatches YAML → plugins → class overrides
    """

    def __init__(self, connection, storage_cfg: Dict, model_cfg: Dict,
                 params: Dict = None, repo_root: Optional[Path] = None):
        self.connection = connection
        self.storage_cfg = storage_cfg
        self.model_cfg = model_cfg
        self.params = params or {}
        self.model_name = model_cfg.get('model', 'unknown')
        self.repo_root = repo_root

        # Session references
        self.session = None
        self.build_session = None

        # Build output caches
        self._dims: Optional[Dict[str, DataFrame]] = None
        self._facts: Optional[Dict[str, DataFrame]] = None
        self._is_built = False

        # Storage router for path resolution
        from de_funk.core.storage import StorageRouter as CoreStorageRouter
        self.storage_router = CoreStorageRouter(self.storage_cfg)

        # Detect backend type
        self._backend = self._detect_backend()

        # Graph builder (lazy-loaded)
        self._graph_builder = None

    # ── Properties ────────────────────────────────────────

    @property
    def backend(self) -> str:
        return self._backend

    def _detect_backend(self) -> str:
        connection_type = str(type(self.connection))
        if 'spark' in connection_type.lower() or hasattr(self.connection, 'sql'):
            return 'spark'
        if 'duckdb' in connection_type.lower() or (
            hasattr(self.connection, '_conn') and 'duckdb' in str(type(self.connection._conn)).lower()
        ):
            return 'duckdb'
        raise ValueError(f"Unknown connection type: {connection_type}")

    def _ensure_active_spark_session(self) -> bool:
        """Ensure Spark session is registered as active for Delta Lake 4.x."""
        if self.backend != 'spark':
            return True
        try:
            spark = getattr(self.connection, 'spark', None) or self.connection
            if spark is None:
                return False
            if not hasattr(spark, '_jvm') or not hasattr(spark, '_jsparkSession'):
                return True
            spark._jvm.SparkSession.setActiveSession(spark._jsparkSession)
            return True
        except Exception as e:
            logger.warning(f"Could not register active Spark session: {e}")
            return False

    # ── Session injection ─────────────────────────────────

    def set_session(self, session):
        """Set session reference for cross-model access."""
        self.session = session

    # ── Build lifecycle ───────────────────────────────────

    def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """Build model tables from Bronze layer via GraphBuilder."""
        self._ensure_active_spark_session()

        if self._graph_builder is None:
            from de_funk.models.base.graph_builder import GraphBuilder
            self._graph_builder = GraphBuilder(self)

        self._dims, self._facts = self._graph_builder.build()
        self._is_built = True
        return self._dims, self._facts

    def ensure_built(self):
        """Build if not already built."""
        if not self._is_built:
            self.build()

    def write_tables(self, output_root: str = None, fmt: str = "delta",
                     mode: str = "overwrite", **kwargs):
        """Write built tables to Silver storage."""
        self.ensure_built()

        # Use Engine.write if build_session is available
        if self.build_session and hasattr(self.build_session, 'engine'):
            engine = self.build_session.engine
            silver_root = output_root or self.storage_router.silver_path(self.model_name)
            for table_type, tables in [("dims", self._dims), ("facts", self._facts)]:
                for name, df in (tables or {}).items():
                    path = f"{silver_root}/{table_type}/{name}"
                    try:
                        engine.write(df, path, format=fmt, mode=mode)
                        logger.info(f"Wrote {name} to {path}")
                    except Exception as e:
                        logger.error(f"Failed to write {name}: {e}")
            return

        # Legacy path: use ModelWriter
        from de_funk.models.base.model_writer import ModelWriter
        writer = ModelWriter(self)
        writer.write_tables(output_root, fmt, mode)

    # ── Table access (for build hooks) ────────────────────

    def get_table(self, name: str) -> Optional[DataFrame]:
        """Get a built table by name."""
        self.ensure_built()
        if self._dims and name in self._dims:
            return self._dims[name]
        if self._facts and name in self._facts:
            return self._facts[name]
        return None

    def has_table(self, name: str) -> bool:
        self.ensure_built()
        return (self._dims and name in self._dims) or (self._facts and name in self._facts)

    def list_tables(self) -> List[str]:
        self.ensure_built()
        tables = []
        if self._dims:
            tables.extend(self._dims.keys())
        if self._facts:
            tables.extend(self._facts.keys())
        return tables

    # ── DataFrame operations (used by GraphBuilder) ────────

    def _apply_filters(self, df, filters):
        """Apply filter conditions to a DataFrame."""
        if not filters:
            return df
        if self.backend == 'spark' and PYSPARK_AVAILABLE:
            for f in filters:
                df = df.filter(f)
        else:
            import pandas as pd
            if isinstance(df, pd.DataFrame):
                for f in filters:
                    df = df.query(f)
        return df

    def _select_columns(self, df, select_spec):
        """Apply column selection/aliasing to a DataFrame."""
        if not select_spec:
            return df
        if isinstance(select_spec, dict):
            # {target: source_expr} aliasing
            if self.backend == 'spark' and PYSPARK_AVAILABLE:
                exprs = [F.expr(f"{src_expr} AS {target}") for target, src_expr in select_spec.items()]
                return df.selectExpr(*[f"{v} AS {k}" for k, v in select_spec.items()])
            else:
                import pandas as pd
                if isinstance(df, pd.DataFrame):
                    rename_map = {}
                    for target, src in select_spec.items():
                        if src in df.columns:
                            rename_map[src] = target
                    return df.rename(columns=rename_map)[list(select_spec.keys())]
        elif isinstance(select_spec, list):
            # Simple column list
            if self.backend == 'spark' and PYSPARK_AVAILABLE:
                available = set(df.columns)
                cols = [c for c in select_spec if c in available]
                return df.select(*cols) if cols else df
            else:
                import pandas as pd
                if isinstance(df, pd.DataFrame):
                    available = set(df.columns)
                    cols = [c for c in select_spec if c in available]
                    return df[cols] if cols else df
        return df

    # ── Extension points (override in subclasses) ─────────

    def before_build(self):
        """Hook called before build(). Override for custom pre-processing."""
        pass

    def after_build(self, dims: Dict[str, DataFrame],
                    facts: Dict[str, DataFrame]) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """Hook called after build(). Override for custom post-processing."""
        return dims, facts

    def custom_node_loading(self, node_id: str, node_config: Dict) -> Optional[DataFrame]:
        """Handle built-in transform markers. Override to add model-specific loaders."""
        transform = node_config.get("_transform")
        if transform == "window":
            return self._build_window_node(node_id, node_config)
        return None

    # ── Hook dispatch ─────────────────────────────────────

    def _run_hooks(self, hook_name: str, **context) -> None:
        """Run hooks for a lifecycle event.

        Resolution order:
        1. Check model_cfg.hooks.{hook_name} for YAML-declared hook fns
        2. Check BuildPluginRegistry for @pipeline_hook decorated fns
        3. If neither, no-op (class overrides called separately by GraphBuilder)
        """
        # 1. YAML config hooks
        hooks_cfg = self.model_cfg.get("hooks", {})
        hook_defs = hooks_cfg.get(hook_name, [])
        if hook_defs:
            for hook_def in hook_defs:
                fn_path = hook_def.get("fn", "") if isinstance(hook_def, dict) else getattr(hook_def, 'fn', '')
                params = hook_def.get("params", {}) if isinstance(hook_def, dict) else getattr(hook_def, 'params', {})
                if fn_path:
                    try:
                        module_path, fn_name = fn_path.rsplit(".", 1)
                        import importlib
                        module = importlib.import_module(module_path)
                        fn = getattr(module, fn_name)
                        engine = self.build_session.engine if self.build_session and hasattr(self.build_session, 'engine') else None
                        fn(engine=engine, config=self.model_cfg, model=self, **context, **params)
                        logger.info(f"Hook {hook_name}: ran {fn_path}")
                    except Exception as e:
                        logger.warning(f"Hook {hook_name}/{fn_path} failed: {e}")
            return

        # 2. Plugin registry hooks
        try:
            from de_funk.core.plugins import BuildPluginRegistry
            plugin_hooks = BuildPluginRegistry.get(hook_name, self.model_name)
            if plugin_hooks:
                for fn in plugin_hooks:
                    try:
                        engine = self.build_session.engine if self.build_session and hasattr(self.build_session, 'engine') else None
                        fn(engine=engine, config=self.model_cfg, model=self, **context)
                        logger.info(f"Hook {hook_name}: ran plugin {fn.__name__}")
                    except Exception as e:
                        logger.warning(f"Hook {hook_name}/plugin {fn.__name__} failed: {e}")
                return
        except ImportError:
            pass

    # ── Window node building ──────────────────────────────

    def _build_window_node(self, node_id: str, node_config: Dict) -> Optional[DataFrame]:
        """Build a window table from a sibling node."""
        from de_funk.models.base.indicators import apply_indicator

        source = node_config.get("_window_source", "")
        schema = node_config.get("_schema", [])

        if not source:
            logger.warning(f"Window node '{node_id}': no _window_source — skipping")
            return None

        building = getattr(self, "_building_nodes", {})
        if source not in building:
            logger.warning(f"Window node '{node_id}': source '{source}' not yet built")
            return None

        df = building[source]
        cols = set(df.columns) if hasattr(df, 'columns') else set()

        if "security_id" in cols and "date_id" in cols:
            partition_col, order_col = "security_id", "date_id"
        elif "ticker" in cols and "trade_date" in cols:
            partition_col, order_col = "ticker", "trade_date"
        else:
            partition_col = next((c for c in cols if c.endswith("_id") and c != "date_id"), None)
            order_col = next((c for c in cols if "date" in c.lower()), None)

        if not partition_col or not order_col:
            logger.warning(f"Window node '{node_id}': cannot detect partition/order columns")
            return None

        logger.info(f"Building window table '{node_id}' from '{source}' "
                     f"(partition={partition_col}, order={order_col})")

        for col_def in schema:
            col_name = col_def[0] if isinstance(col_def, (list, tuple)) else col_def.get("name", "")
            opts = col_def[4] if isinstance(col_def, (list, tuple)) and len(col_def) > 4 else {}
            if isinstance(opts, dict) and "indicator" in opts:
                indicator_cfg = opts["indicator"]
                try:
                    df = apply_indicator(df, col_name, indicator_cfg,
                                         partition_col=partition_col,
                                         order_col=order_col,
                                         backend=self.backend)
                except Exception as e:
                    logger.warning(f"Indicator '{col_name}' failed: {e}")

        return df
