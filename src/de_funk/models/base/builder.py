"""
BaseModelBuilder — builds Silver tables from domain configs.

Used by DomainBuilderFactory to create dynamic builders for each model.
Each builder declares model_name, depends_on, and get_model_class().

BuildResult captures the outcome of a build (success, rows, duration).
BuildContext holds shared resources (Spark session, storage config).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, Type
from pathlib import Path
import logging
import time

if True:  # TYPE_CHECKING workaround
    try:
        from pyspark.sql import SparkSession, DataFrame
    except ImportError:
        pass

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
    """Shared resources for builders."""
    spark: Any  # SparkSession
    storage_config: Dict[str, Any]
    repo_root: Path
    date_from: str
    date_to: str
    max_tickers: Optional[int] = None
    dry_run: bool = False
    verbose: bool = False


class BaseModelBuilder(ABC):
    """Abstract builder for domain models."""

    model_name: str = ""
    depends_on: List[str] = []

    def __init__(self, context: BuildContext, build_session=None):
        self.context = context
        self.spark = context.spark
        self.storage_config = context.storage_config
        self.repo_root = context.repo_root
        self.build_session = build_session
        self._model_instance = None
        self._model_config = None

    @abstractmethod
    def get_model_class(self) -> Type:
        """Return the model class to instantiate."""
        pass

    def get_model_config(self) -> Dict[str, Any]:
        """Load model config from domain markdown."""
        if self._model_config is None:
            from de_funk.config.domain import get_domain_loader
            from de_funk.config.domain.config_translator import translate_domain_config
            domains_dir = self.repo_root / "domains"
            loader = get_domain_loader(domains_dir)
            raw_config = loader.load_model_config(self.model_name)
            self._model_config = translate_domain_config(raw_config)
        return self._model_config

    def build(self) -> BuildResult:
        """Build the model: instantiate → build → write."""
        start = time.time()
        try:
            model_config = self.get_model_config()
            model_class = self.get_model_class()

            # Create connection
            from de_funk.core.connection import get_spark_connection
            connection = get_spark_connection(self.spark)

            params = {
                "DATE_FROM": self.context.date_from,
                "DATE_TO": self.context.date_to,
            }
            if self.context.max_tickers:
                params["UNIVERSE_SIZE"] = self.context.max_tickers

            model = model_class(
                connection=connection,
                storage_cfg=self.storage_config,
                model_cfg=model_config,
                params=params,
                repo_root=self.repo_root,
            )

            if self.build_session is not None:
                model.build_session = self.build_session

            dims, facts = model.build()
            model.write_tables()

            duration = time.time() - start
            return BuildResult(
                model_name=self.model_name,
                success=True,
                dimensions=len(dims),
                facts=len(facts),
                duration_seconds=duration,
            )
        except Exception as e:
            duration = time.time() - start
            logger.error(f"Build failed for {self.model_name}: {e}", exc_info=True)
            return BuildResult(
                model_name=self.model_name,
                success=False,
                error=str(e),
                duration_seconds=duration,
            )

    @classmethod
    def get_dependencies(cls) -> List[str]:
        return cls.depends_on if cls.depends_on else []


class BuilderRegistry:
    """Registry of discovered model builders."""

    _builders: Dict[str, Type[BaseModelBuilder]] = {}

    @classmethod
    def register(cls, builder_class: Type[BaseModelBuilder]) -> Type[BaseModelBuilder]:
        cls._builders[builder_class.model_name] = builder_class
        return builder_class

    @classmethod
    def all(cls) -> Dict[str, Type[BaseModelBuilder]]:
        return dict(cls._builders)

    @classmethod
    def discover(cls, models_path: Path) -> None:
        """Discover builders from Python modules in models/domains/."""
        import importlib
        if not models_path.exists():
            return
        for builder_file in models_path.rglob("builder.py"):
            rel = builder_file.relative_to(models_path.parent.parent)
            module_name = "de_funk." + str(rel).replace("/", ".").replace(".py", "")
            try:
                mod = importlib.import_module(module_name)
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (isinstance(attr, type) and issubclass(attr, BaseModelBuilder)
                            and attr is not BaseModelBuilder and hasattr(attr, 'model_name')
                            and attr.model_name):
                        cls.register(attr)
            except Exception as e:
                logger.debug(f"Could not load {module_name}: {e}")

    @classmethod
    def clear(cls):
        cls._builders.clear()
