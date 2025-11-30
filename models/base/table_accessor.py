"""
Table Accessor for BaseModel.

Provides table access, schema inspection, and metadata extraction:
- get_table, get_dimension_df, get_fact_df
- has_table, list_tables
- get_table_schema, get_relations, get_metadata

This module is used by BaseModel via composition.
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class TableAccessor:
    """
    Provides table access and schema inspection for a model.

    Handles lazy building, table lookup, and metadata extraction.
    """

    def __init__(self, model):
        """
        Initialize table accessor.

        Args:
            model: BaseModel instance
        """
        self.model = model

    @property
    def model_cfg(self) -> Dict:
        return self.model.model_cfg

    @property
    def model_name(self) -> str:
        return self.model.model_name

    def ensure_built(self):
        """Lazy build pattern - delegates to model's ensure_built."""
        self.model.ensure_built()

    def get_table(self, table_name: str) -> DataFrame:
        """
        Get a table by name (searches dims and facts).

        Args:
            table_name: Table identifier

        Returns:
            DataFrame

        Raises:
            KeyError: If table not found
        """
        self.ensure_built()

        if table_name in self.model._dims:
            return self.model._dims[table_name]
        elif table_name in self.model._facts:
            return self.model._facts[table_name]
        else:
            available = list(self.model._dims.keys()) + list(self.model._facts.keys())
            raise KeyError(
                f"Table '{table_name}' not found in {self.model_name} model. "
                f"Available tables: {available}"
            )

    def get_table_enriched(
        self,
        table_name: str,
        enrich_with: Optional[List[str]] = None,
        columns: Optional[List[str]] = None
    ) -> DataFrame:
        """
        Get table with optional enrichment via dynamic joins.

        Uses graph edges to join related tables at runtime. Falls back to
        materialized views when available for performance.

        Args:
            table_name: Base table name (e.g., 'fact_equity_prices')
            enrich_with: List of tables to join (e.g., ['dim_equity', 'dim_exchange'])
            columns: Columns to select (default: all columns)

        Returns:
            DataFrame with enrichment applied

        Raises:
            ValueError: If no join path exists

        Example:
            # Get prices with company info (dynamic join)
            df = equity_model.get_table_enriched(
                'fact_equity_prices',
                enrich_with=['dim_equity', 'dim_exchange'],
                columns=['ticker', 'trade_date', 'close', 'company_name', 'exchange_name']
            )

            # System:
            # 1. Checks for materialized view (equity_prices_with_company)
            # 2. If not found, builds join from graph edges
            # 3. Returns enriched DataFrame
        """
        return self.model.query_planner.get_table_enriched(table_name, enrich_with, columns)

    def get_dimension_df(self, dim_id: str) -> DataFrame:
        """Get a dimension table by ID."""
        self.ensure_built()
        if dim_id not in self.model._dims:
            raise KeyError(f"Dimension '{dim_id}' not found in {self.model_name}")
        return self.model._dims[dim_id]

    def get_fact_df(self, fact_id: str) -> DataFrame:
        """Get a fact table by ID."""
        self.ensure_built()
        if fact_id not in self.model._facts:
            raise KeyError(f"Fact '{fact_id}' not found in {self.model_name}")
        return self.model._facts[fact_id]

    def has_table(self, table_name: str) -> bool:
        """
        Check if a table exists in this model.

        Args:
            table_name: Table identifier

        Returns:
            True if table exists (in dimensions or facts), False otherwise
        """
        self.ensure_built()
        return table_name in self.model._dims or table_name in self.model._facts

    def list_tables(self) -> Dict[str, List[str]]:
        """
        List all available tables.

        Returns:
            Dictionary with 'dimensions' and 'facts' keys
        """
        self.ensure_built()
        return {
            'dimensions': list(self.model._dims.keys()),
            'facts': list(self.model._facts.keys())
        }

    def get_table_schema(self, table_name: str) -> Dict[str, str]:
        """
        Get schema (column definitions) for a table.

        Args:
            table_name: Name of the table

        Returns:
            Dictionary mapping column_name -> data_type

        Raises:
            KeyError: If table not found
        """
        schema_config = self.model_cfg.get('schema', {})

        # Check dimensions
        if table_name in schema_config.get('dimensions', {}):
            return schema_config['dimensions'][table_name].get('columns', {})

        # Check facts
        if table_name in schema_config.get('facts', {}):
            return schema_config['facts'][table_name].get('columns', {})

        # If not found in schema, try to get columns from actual DataFrame
        try:
            self.ensure_built()
            if table_name in self.model._dims:
                df = self.model._dims[table_name]
                return {col: 'unknown' for col in df.columns}
            elif table_name in self.model._facts:
                df = self.model._facts[table_name]
                return {col: 'unknown' for col in df.columns}
        except Exception:
            pass

        raise KeyError(f"Table '{table_name}' not found in model schema")

    def get_relations(self) -> Dict[str, List[str]]:
        """
        Return relationship graph from edges config.

        Returns:
            Dictionary mapping table -> [related_tables]
        """
        graph = self.model_cfg.get('graph', {})
        relations = {}

        # Handle both v1.x (list) and v2.0 (dict) edge formats
        edges_config = graph.get('edges', [])
        if isinstance(edges_config, dict):
            # v2.0 format: {edge_id: {from: ..., to: ...}}
            edges_list = list(edges_config.values())
        else:
            # v1.x format: [{id: edge_id, from: ..., to: ...}]
            edges_list = edges_config

        for edge in edges_list:
            from_table = edge['from']
            to_table = edge['to']

            if from_table not in relations:
                relations[from_table] = []
            relations[from_table].append(to_table)

        return relations

    def get_metadata(self) -> Dict[str, Any]:
        """
        Return model metadata.

        Returns:
            Dictionary with model info
        """
        graph = self.model_cfg.get('graph', {})

        # Handle nodes - could be dict (v2.0) or list (v1.x)
        nodes_config = graph.get('nodes', [])
        if isinstance(nodes_config, dict):
            node_ids = list(nodes_config.keys())
        else:
            node_ids = [n['id'] for n in nodes_config]

        # Handle paths - could be dict (v2.0) or list (v1.x)
        paths_config = graph.get('paths', [])
        if isinstance(paths_config, dict):
            path_ids = list(paths_config.keys())
        else:
            path_ids = [p['id'] for p in paths_config]

        return {
            'name': self.model_name,
            'version': self.model_cfg.get('version', '1.0.0'),
            'description': self.model_cfg.get('description', ''),
            'tags': self.model_cfg.get('tags', []),
            'nodes': node_ids,
            'paths': path_ids,
            'measures': list(self.model_cfg.get('measures', {}).keys()),
            'dependencies': self.model_cfg.get('depends_on', []),
        }
