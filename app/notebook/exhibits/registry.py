"""
Exhibit type registry - maps exhibit types to renderers and presets.

This module provides a centralized registry for exhibit types, enabling:
- Dynamic exhibit type registration
- Preset configuration inheritance
- Lazy-loading of renderers
- Type aliases for convenience
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
import importlib
import yaml

from config.logging import get_logger

logger = get_logger(__name__)

# Singleton instance
_registry_instance: Optional["ExhibitTypeRegistry"] = None


@dataclass
class ExhibitTypeConfig:
    """Configuration for an exhibit type."""

    name: str
    renderer_module: str
    renderer_function: str
    preset_path: Optional[Path] = None
    requires: List[str] = field(default_factory=list)
    description: str = ""

    _renderer: Optional[Callable] = field(default=None, repr=False)
    _preset: Optional[Dict] = field(default=None, repr=False)

    @property
    def renderer(self) -> Callable:
        """Lazy-load renderer function."""
        if self._renderer is None:
            try:
                module = importlib.import_module(self.renderer_module)
                self._renderer = getattr(module, self.renderer_function)
                logger.debug(f"Loaded renderer {self.renderer_module}.{self.renderer_function}")
            except (ImportError, AttributeError) as e:
                logger.error(f"Failed to load renderer for {self.name}: {e}")
                raise
        return self._renderer

    @property
    def preset(self) -> Dict:
        """Lazy-load preset configuration."""
        if self._preset is None:
            if self.preset_path and self.preset_path.exists():
                try:
                    with open(self.preset_path) as f:
                        self._preset = yaml.safe_load(f) or {}
                    logger.debug(f"Loaded preset from {self.preset_path}")
                except Exception as e:
                    logger.warning(f"Failed to load preset for {self.name}: {e}")
                    self._preset = {}
            else:
                self._preset = {}
        return self._preset

    def get_defaults(self) -> Dict:
        """Get default parameters from preset."""
        return self.preset.get('defaults', {})


class ExhibitTypeRegistry:
    """
    Registry of exhibit types with their renderers and presets.

    Usage:
        registry = ExhibitTypeRegistry()
        registry.register(
            name="great_table",
            renderer_module="app.ui.components.exhibits.great_table",
            renderer_function="render_great_table",
            requires=["great_tables"]
        )

        # Get renderer
        renderer = registry.get_renderer("great_table")
        renderer(exhibit, dataframe)

        # Get defaults merged with user config
        config = registry.merge_with_defaults("great_table", user_config)
    """

    def __init__(self):
        self._types: Dict[str, ExhibitTypeConfig] = {}
        self._aliases: Dict[str, str] = {}
        self._initialized = False

    def register(
        self,
        name: str,
        renderer_module: str,
        renderer_function: str,
        preset_path: Optional[Path] = None,
        requires: Optional[List[str]] = None,
        description: str = "",
    ) -> None:
        """
        Register an exhibit type.

        Args:
            name: Unique type name (e.g., "great_table")
            renderer_module: Module path (e.g., "app.ui.components.exhibits.great_table")
            renderer_function: Function name in module (e.g., "render_great_table")
            preset_path: Path to preset YAML file
            requires: List of required packages
            description: Human-readable description
        """
        self._types[name] = ExhibitTypeConfig(
            name=name,
            renderer_module=renderer_module,
            renderer_function=renderer_function,
            preset_path=preset_path,
            requires=requires or [],
            description=description,
        )
        logger.debug(f"Registered exhibit type: {name}")

    def add_alias(self, alias: str, target: str) -> None:
        """
        Add an alias for an exhibit type.

        Args:
            alias: The alias name (e.g., "gt")
            target: The target type name (e.g., "great_table")
        """
        if target not in self._types:
            logger.warning(f"Alias {alias} points to unknown type {target}")
        self._aliases[alias] = target

    def resolve_type(self, type_name: str) -> str:
        """Resolve alias to actual type name."""
        return self._aliases.get(type_name, type_name)

    def has_type(self, type_name: str) -> bool:
        """Check if a type is registered."""
        resolved = self.resolve_type(type_name)
        return resolved in self._types

    def get_config(self, type_name: str) -> ExhibitTypeConfig:
        """
        Get configuration for an exhibit type.

        Args:
            type_name: Type name or alias

        Returns:
            ExhibitTypeConfig for the type

        Raises:
            ValueError: If type is not registered
        """
        resolved = self.resolve_type(type_name)
        if resolved not in self._types:
            available = list(self._types.keys())
            raise ValueError(
                f"Unknown exhibit type: {type_name}. "
                f"Available types: {available}"
            )
        return self._types[resolved]

    def get_renderer(self, type_name: str) -> Callable:
        """
        Get renderer function for an exhibit type.

        Args:
            type_name: Type name or alias

        Returns:
            Renderer function
        """
        return self.get_config(type_name).renderer

    def get_defaults(self, type_name: str) -> Dict:
        """
        Get default parameters for an exhibit type.

        Args:
            type_name: Type name or alias

        Returns:
            Dictionary of default parameters
        """
        return self.get_config(type_name).get_defaults()

    def merge_with_defaults(self, type_name: str, user_config: Dict) -> Dict:
        """
        Merge user config with type defaults (user config takes precedence).

        Args:
            type_name: Type name or alias
            user_config: User-provided configuration

        Returns:
            Merged configuration
        """
        defaults = self.get_defaults(type_name)
        return {**defaults, **user_config}

    def list_types(self) -> List[str]:
        """List all registered type names."""
        return list(self._types.keys())

    def list_aliases(self) -> Dict[str, str]:
        """List all aliases and their targets."""
        return dict(self._aliases)

    @classmethod
    def from_config(cls, config_path: Path) -> "ExhibitTypeRegistry":
        """
        Load registry from YAML config file.

        Config format:
        ```yaml
        exhibit_types:
          great_table:
            renderer: app.ui.components.exhibits.great_table.render_great_table
            preset: presets/great_table.yaml
            requires: [great_tables]
            description: Publication-quality tables

        aliases:
          gt: great_table
          table: great_table
        ```
        """
        registry = cls()

        if not config_path.exists():
            logger.warning(f"Registry config not found: {config_path}")
            return registry

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        base_path = config_path.parent

        # Register types
        for type_name, type_config in config.get('exhibit_types', {}).items():
            renderer_path = type_config.get('renderer', '')
            if '.' in renderer_path:
                # Split "module.path.function" into module and function
                parts = renderer_path.rsplit('.', 1)
                renderer_module = parts[0]
                renderer_function = parts[1] if len(parts) > 1 else 'render'
            else:
                continue

            preset_path = None
            if 'preset' in type_config:
                preset_path = base_path / type_config['preset']

            registry.register(
                name=type_name,
                renderer_module=renderer_module,
                renderer_function=renderer_function,
                preset_path=preset_path,
                requires=type_config.get('requires', []),
                description=type_config.get('description', ''),
            )

        # Register aliases
        for alias, target in config.get('aliases', {}).items():
            registry.add_alias(alias, target)

        registry._initialized = True
        return registry


def _register_builtin_types(registry: ExhibitTypeRegistry) -> None:
    """Register built-in exhibit types."""

    # Great Tables (new)
    registry.register(
        name="great_table",
        renderer_module="app.ui.components.exhibits.great_table",
        renderer_function="render_great_table",
        requires=["great_tables"],
        description="Publication-quality tables using Great Tables library",
    )

    # Line chart
    registry.register(
        name="line_chart",
        renderer_module="app.ui.components.exhibits.line_chart",
        renderer_function="render_line_chart",
        requires=["plotly"],
        description="Interactive line charts",
    )

    # Bar chart
    registry.register(
        name="bar_chart",
        renderer_module="app.ui.components.exhibits.bar_chart",
        renderer_function="render_bar_chart",
        requires=["plotly"],
        description="Interactive bar charts",
    )

    # Data table (basic)
    registry.register(
        name="data_table",
        renderer_module="app.ui.components.exhibits.data_table",
        renderer_function="render_data_table",
        requires=[],
        description="Basic interactive data table",
    )

    # Metric cards
    registry.register(
        name="metric_cards",
        renderer_module="app.ui.components.exhibits.metric_cards",
        renderer_function="render_metric_cards",
        requires=[],
        description="Summary metric cards",
    )

    # Scatter chart
    registry.register(
        name="scatter_chart",
        renderer_module="app.ui.components.exhibits.scatter_chart",
        renderer_function="render_scatter_chart",
        requires=["plotly"],
        description="Scatter plot charts",
    )

    # Weighted aggregate chart
    registry.register(
        name="weighted_aggregate_chart",
        renderer_module="app.ui.components.exhibits.weighted_aggregate_chart",
        renderer_function="render_weighted_aggregate_chart",
        requires=["plotly"],
        description="Weighted index charts",
    )

    # Forecast chart
    registry.register(
        name="forecast_chart",
        renderer_module="app.ui.components.exhibits.forecast_chart",
        renderer_function="render_forecast_chart",
        requires=["plotly"],
        description="Forecast with confidence bands",
    )

    # Aliases
    registry.add_alias("gt", "great_table")
    registry.add_alias("table", "great_table")
    registry.add_alias("chart", "line_chart")
    registry.add_alias("line", "line_chart")
    registry.add_alias("bar", "bar_chart")
    registry.add_alias("scatter", "scatter_chart")
    registry.add_alias("metrics", "metric_cards")


def get_exhibit_registry() -> ExhibitTypeRegistry:
    """
    Get the singleton exhibit type registry.

    Returns:
        ExhibitTypeRegistry with built-in types registered
    """
    global _registry_instance

    if _registry_instance is None:
        _registry_instance = ExhibitTypeRegistry()
        _register_builtin_types(_registry_instance)

    return _registry_instance
