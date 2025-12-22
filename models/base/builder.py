"""
BaseModelBuilder - Abstract base class for model builders.

Each domain model should have a corresponding builder that inherits from this class.
Builders handle:
- Model instantiation with proper configuration
- Spark session management
- Build execution and validation
- Dependency declaration

Usage:
    class StocksBuilder(BaseModelBuilder):
        model_name = "stocks"
        depends_on = ["company"]

        def get_model_class(self):
            from models.domain.stocks.model import StocksModel
            return StocksModel

The build orchestrator discovers all builders and executes them in dependency order.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, Type, TYPE_CHECKING
from pathlib import Path
import logging
from datetime import datetime

if TYPE_CHECKING:
    from pyspark.sql import SparkSession, DataFrame

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Result of a model build operation."""
    model_name: str
    success: bool
    dimensions: int = 0
    facts: int = 0
    rows_written: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.success:
            return (f"✓ {self.model_name}: {self.dimensions} dims, "
                    f"{self.facts} facts ({self.duration_seconds:.1f}s)")
        return f"✗ {self.model_name}: {self.error}"


@dataclass
class BuildContext:
    """Context passed to builders containing shared resources."""
    spark: Any  # SparkSession
    storage_config: Dict[str, Any]
    repo_root: Path
    date_from: str
    date_to: str
    max_tickers: Optional[int] = None
    dry_run: bool = False
    verbose: bool = False


class BaseModelBuilder(ABC):
    """
    Abstract base class for model builders.

    Subclasses must implement:
    - model_name: str - Name of the model (e.g., "stocks")
    - get_model_class(): Return the model class to instantiate

    Optional overrides:
    - depends_on: List[str] - Models that must be built first
    - validate(): Custom validation logic
    - pre_build(): Actions before build
    - post_build(): Actions after build
    """

    # Class attributes - override in subclasses
    model_name: str = ""
    depends_on: List[str] = []

    def __init__(self, context: BuildContext):
        """
        Initialize builder with build context.

        Args:
            context: BuildContext with spark session, config, etc.
        """
        self.context = context
        self.spark = context.spark
        self.storage_config = context.storage_config
        self.repo_root = context.repo_root
        self._model_instance = None
        self._model_config = None

    @abstractmethod
    def get_model_class(self) -> Type:
        """
        Return the model class to instantiate.

        Returns:
            Model class (e.g., StocksModel)
        """
        pass

    def get_model_config(self) -> Dict[str, Any]:
        """
        Load and return model configuration.

        Returns:
            Model configuration dict from YAML
        """
        if self._model_config is None:
            from config.model_loader import ModelConfigLoader
            config_dir = self.repo_root / "configs" / "models"
            loader = ModelConfigLoader(config_dir)
            self._model_config = loader.load_model_config(self.model_name)
        return self._model_config

    def create_model_instance(self) -> Any:
        """
        Create and return model instance.

        Returns:
            Instantiated model object
        """
        if self._model_instance is not None:
            return self._model_instance

        model_class = self.get_model_class()
        model_config = self.get_model_config()

        # Create connection wrapper for Spark
        from core.connection import ConnectionFactory
        connection = ConnectionFactory.create_spark(self.spark)

        # Build params dict
        params = {
            "DATE_FROM": self.context.date_from,
            "DATE_TO": self.context.date_to,
        }
        if self.context.max_tickers:
            params["UNIVERSE_SIZE"] = self.context.max_tickers

        # Instantiate model
        self._model_instance = model_class(
            connection=connection,
            storage_cfg=self.storage_config,
            model_cfg=model_config,
            params=params,
            repo_root=str(self.repo_root)
        )

        return self._model_instance

    def pre_build(self) -> None:
        """
        Hook called before build. Override for custom pre-build logic.
        """
        pass

    def post_build(self, result: BuildResult) -> None:
        """
        Hook called after build. Override for custom post-build logic.

        Args:
            result: BuildResult from the build operation
        """
        pass

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate build prerequisites.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Check model config exists
        try:
            self.get_model_config()
        except Exception as e:
            errors.append(f"Failed to load model config: {e}")

        # Check model class can be imported
        try:
            self.get_model_class()
        except Exception as e:
            errors.append(f"Failed to import model class: {e}")

        return len(errors) == 0, errors

    def build(self) -> BuildResult:
        """
        Execute the model build.

        Returns:
            BuildResult with build outcome
        """
        start_time = datetime.now()

        # Validate first
        is_valid, errors = self.validate()
        if not is_valid:
            return BuildResult(
                model_name=self.model_name,
                success=False,
                error="; ".join(errors)
            )

        try:
            # Pre-build hook
            self.pre_build()

            if self.context.dry_run:
                logger.info(f"[DRY RUN] Would build {self.model_name}")
                return BuildResult(
                    model_name=self.model_name,
                    success=True,
                    duration_seconds=0.0
                )

            # Create model instance
            model = self.create_model_instance()

            # Execute build
            if self.context.verbose:
                logger.info(f"Building {self.model_name}...")

            dims, facts = model.build()

            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()

            # Create result
            result = BuildResult(
                model_name=self.model_name,
                success=True,
                dimensions=len(dims) if dims else 0,
                facts=len(facts) if facts else 0,
                duration_seconds=duration
            )

            # Post-build hook
            self.post_build(result)

            if self.context.verbose:
                logger.info(f"  {result}")

            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Build failed for {self.model_name}: {e}")
            return BuildResult(
                model_name=self.model_name,
                success=False,
                error=str(e),
                duration_seconds=duration
            )

    @classmethod
    def get_dependencies(cls) -> List[str]:
        """
        Return list of model names this builder depends on.

        Returns:
            List of model names that must be built first
        """
        return cls.depends_on.copy()

    def __repr__(self) -> str:
        deps = ", ".join(self.depends_on) if self.depends_on else "none"
        return f"<{self.__class__.__name__}(model={self.model_name}, depends_on=[{deps}])>"


class BuilderRegistry:
    """
    Registry for discovering and managing model builders.
    """

    _builders: Dict[str, Type[BaseModelBuilder]] = {}

    @classmethod
    def register(cls, builder_class: Type[BaseModelBuilder]) -> Type[BaseModelBuilder]:
        """
        Register a builder class.

        Can be used as a decorator:
            @BuilderRegistry.register
            class StocksBuilder(BaseModelBuilder):
                ...
        """
        if not builder_class.model_name:
            raise ValueError(f"Builder {builder_class.__name__} must define model_name")
        cls._builders[builder_class.model_name] = builder_class
        return builder_class

    @classmethod
    def get(cls, model_name: str) -> Optional[Type[BaseModelBuilder]]:
        """Get builder class for a model name."""
        return cls._builders.get(model_name)

    @classmethod
    def all(cls) -> Dict[str, Type[BaseModelBuilder]]:
        """Get all registered builders."""
        return cls._builders.copy()

    @classmethod
    def discover(cls, models_path: Path) -> None:
        """
        Discover and register builders from model directories.

        Args:
            models_path: Path to models/domain directory
        """
        import importlib

        for model_dir in models_path.iterdir():
            if not model_dir.is_dir() or model_dir.name.startswith('_'):
                continue

            builder_file = model_dir / "builder.py"
            if builder_file.exists():
                try:
                    module_name = f"models.domain.{model_dir.name}.builder"
                    module = importlib.import_module(module_name)

                    # Find builder classes in the module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and
                            issubclass(attr, BaseModelBuilder) and
                            attr is not BaseModelBuilder and
                            attr.model_name):
                            cls.register(attr)
                            logger.debug(f"Discovered builder: {attr.model_name}")

                except Exception as e:
                    logger.warning(f"Failed to load builder from {model_dir.name}: {e}")

    @classmethod
    def get_build_order(cls, models: Optional[List[str]] = None) -> List[str]:
        """
        Get models in dependency order (topological sort).

        Args:
            models: Optional list of models to build (None = all)

        Returns:
            List of model names in build order
        """
        if models is None:
            models = list(cls._builders.keys())

        # Build dependency graph
        graph = {}
        for model_name in models:
            builder_cls = cls._builders.get(model_name)
            if builder_cls:
                # Only include dependencies that are in our build set
                deps = [d for d in builder_cls.depends_on if d in models]
                graph[model_name] = deps
            else:
                graph[model_name] = []

        # Topological sort (Kahn's algorithm)
        in_degree = {node: 0 for node in graph}
        for node in graph:
            for dep in graph[node]:
                if dep in in_degree:
                    in_degree[node] += 1

        queue = [node for node in in_degree if in_degree[node] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for other in graph:
                if node in graph[other]:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        if len(result) != len(graph):
            # Cycle detected - return original order
            logger.warning("Dependency cycle detected, using original order")
            return models

        return result

    @classmethod
    def clear(cls) -> None:
        """Clear all registered builders."""
        cls._builders.clear()
