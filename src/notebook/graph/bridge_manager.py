"""
Bridge manager for cross-model joins.

Handles relationships between different models (subgraphs).
"""

from typing import Dict, List, Tuple
from pyspark.sql import DataFrame
import pyspark.sql.functions as F

from ..schema import Bridge, SourceReference


class BridgeManager:
    """
    Manages bridges (cross-model joins) between models.

    Bridges allow notebooks to combine data from multiple backend models
    into a unified view.
    """

    def __init__(self, bridges: List[Bridge]):
        """
        Initialize bridge manager.

        Args:
            bridges: List of bridge definitions
        """
        self.bridges = bridges
        self._bridge_index = self._build_index()

    def _build_index(self) -> Dict[Tuple[str, str], Bridge]:
        """
        Build an index of bridges for quick lookup.

        Returns:
            Dictionary mapping (from_source, to_source) to Bridge
        """
        index = {}
        for bridge in self.bridges:
            key = (bridge.from_source, bridge.to_source)
            index[key] = bridge
        return index

    def get_bridge(self, from_source: str, to_source: str) -> Bridge:
        """
        Get bridge between two sources.

        Args:
            from_source: Source identifier (model.node)
            to_source: Target identifier (model.node)

        Returns:
            Bridge definition

        Raises:
            ValueError if no bridge found
        """
        key = (from_source, to_source)
        if key not in self._bridge_index:
            raise ValueError(
                f"No bridge found from {from_source} to {to_source}. "
                f"Available bridges: {list(self._bridge_index.keys())}"
            )
        return self._bridge_index[key]

    def has_bridge(self, from_source: str, to_source: str) -> bool:
        """
        Check if a bridge exists between two sources.

        Args:
            from_source: Source identifier (model.node)
            to_source: Target identifier (model.node)

        Returns:
            True if bridge exists
        """
        return (from_source, to_source) in self._bridge_index

    def apply_bridge(
        self,
        left_df: DataFrame,
        right_df: DataFrame,
        bridge: Bridge,
    ) -> DataFrame:
        """
        Apply a bridge (join) between two dataframes.

        Args:
            left_df: Left dataframe
            right_df: Right dataframe
            bridge: Bridge definition

        Returns:
            Joined dataframe
        """
        # Parse join conditions
        join_conditions = []
        for condition in bridge.on:
            # Parse "left_col = right_col" or "left_col=right_col"
            parts = condition.replace(" ", "").split("=")
            if len(parts) != 2:
                raise ValueError(f"Invalid join condition: {condition}")

            left_col, right_col = parts
            join_conditions.append(left_df[left_col] == right_df[right_col])

        # Combine conditions with AND
        join_expr = join_conditions[0]
        for condition in join_conditions[1:]:
            join_expr = join_expr & condition

        # Perform join
        return left_df.join(right_df, join_expr, bridge.type)

    def join_path(
        self,
        dataframes: Dict[str, DataFrame],
        path: List[str],
    ) -> DataFrame:
        """
        Join multiple dataframes along a path.

        Args:
            dataframes: Dictionary of source_id -> DataFrame
            path: List of source IDs forming the join path

        Returns:
            Joined dataframe

        Example:
            path = ["company.fact_prices", "company.dim_company", "company.dim_exchange"]
            This will join prices -> company -> exchange
        """
        if len(path) < 2:
            raise ValueError("Path must contain at least 2 nodes")

        # Start with first dataframe
        result = dataframes[path[0]]

        # Join each subsequent dataframe
        for i in range(1, len(path)):
            from_source = path[i - 1]
            to_source = path[i]

            # Get bridge
            bridge = self.get_bridge(from_source, to_source)

            # Join
            right_df = dataframes[to_source]
            result = self.apply_bridge(result, right_df, bridge)

        return result

    def validate_bridges(self, available_sources: List[str]) -> List[str]:
        """
        Validate that all bridges reference valid sources.

        Args:
            available_sources: List of available source IDs

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        available_set = set(available_sources)

        for bridge in self.bridges:
            if bridge.from_source not in available_set:
                errors.append(
                    f"Bridge references unknown source: {bridge.from_source}"
                )
            if bridge.to_source not in available_set:
                errors.append(
                    f"Bridge references unknown source: {bridge.to_source}"
                )

        return errors


class JoinOptimizer:
    """
    Optimizes join order for better performance.

    Considers factors like:
    - Table sizes
    - Join types (inner vs outer)
    - Filter pushdown opportunities
    """

    @staticmethod
    def optimize_join_order(path: List[str], hints: Dict[str, int] = None) -> List[str]:
        """
        Optimize the join order.

        Args:
            path: Original join path
            hints: Optional size hints (source_id -> row count)

        Returns:
            Optimized path

        Note: For now, this is a placeholder. In production, you would
        analyze table statistics and reorder joins accordingly.
        """
        # TODO: Implement join optimization
        # For now, just return the original path
        return path

    @staticmethod
    def suggest_broadcast_joins(
        path: List[str],
        hints: Dict[str, int] = None,
        broadcast_threshold: int = 10_000_000,
    ) -> List[str]:
        """
        Suggest which tables should be broadcast for join optimization.

        Args:
            path: Join path
            hints: Optional size hints (source_id -> row count)
            broadcast_threshold: Max size for broadcast join (bytes)

        Returns:
            List of source IDs that should be broadcast
        """
        if hints is None:
            return []

        broadcast_sources = []
        for source, row_count in hints.items():
            if row_count < broadcast_threshold:
                broadcast_sources.append(source)

        return broadcast_sources
