"""
V4 Builder Factory - Dynamic builder registration for v4 domain models.

Creates builder classes on-the-fly for each v4 model config,
registering them with BuilderRegistry so build_models.py can
discover and build them alongside v3 models.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Type

logger = logging.getLogger(__name__)


class V4BuilderFactory:
    """
    Factory that scans v4 domain configs and creates builder classes.

    Each generated builder:
    - Has model_name and depends_on from the v4 config
    - Uses DomainConfigLoaderV4 + translate_v4_config() for config loading
    - Returns V4Model as the model class
    - Registers with BuilderRegistry
    """

    @classmethod
    def create_builders(
        cls,
        domains_dir: Path,
        skip_existing: bool = True,
    ) -> Dict[str, Any]:
        """
        Scan v4 domain configs and create/register builder classes.

        Args:
            domains_dir: Path to domains/ directory (v4 structure)
            skip_existing: If True, don't register builders for models
                          that already have a v3 builder registered

        Returns:
            Dict of model_name → builder_class for all created builders
        """
        from de_funk.config.domain import DomainConfigLoaderV4, get_domain_loader
        from de_funk.models.base.builder import BuilderRegistry, BaseModelBuilder

        # Check if this is actually a v4 directory
        loader = get_domain_loader(domains_dir)
        if not isinstance(loader, DomainConfigLoaderV4):
            logger.debug(f"{domains_dir} is not a v4 domain directory")
            return {}

        existing = BuilderRegistry.all()
        created = {}

        for model_name in loader.list_models():
            # Skip models that already have v3 builders
            if skip_existing and model_name in existing:
                logger.debug(
                    f"Skipping v4 builder for '{model_name}' — "
                    f"v3 builder already registered"
                )
                continue

            try:
                # Load minimal config to get depends_on
                config = loader.load_model_config(model_name)
                depends = config.get("depends_on", [])
                if isinstance(depends, str):
                    depends = [depends]

                # Create a dynamic builder class
                builder_class = cls._create_builder_class(
                    model_name, depends, domains_dir
                )

                # Register with the registry
                BuilderRegistry.register(builder_class)
                created[model_name] = builder_class

                logger.debug(f"Registered v4 builder: {model_name}")

            except Exception as e:
                logger.warning(
                    f"Failed to create v4 builder for '{model_name}': {e}"
                )

        if created:
            logger.info(
                f"Registered {len(created)} v4 builders: "
                f"{', '.join(sorted(created.keys()))}"
            )

        return created

    @classmethod
    def _create_builder_class(
        cls,
        model_name: str,
        depends_on: List[str],
        domains_dir: Path,
    ) -> type:
        """
        Create a dynamic builder class for a v4 model.

        Uses type() to create a new class with the correct model_name
        and depends_on attributes.
        """
        from de_funk.models.base.builder import BaseModelBuilder

        class_name = f"V4Builder_{model_name.replace('-', '_')}"

        def get_model_class(self) -> type:
            from de_funk.models.base.v4_model import V4Model
            return V4Model

        def get_model_config(self) -> Dict[str, Any]:
            if self._model_config is None:
                from de_funk.config.domain import DomainConfigLoaderV4
                from de_funk.config.domain.v4_to_nodes import translate_v4_config

                loader = DomainConfigLoaderV4(self._v4_domains_dir)
                v4_config = loader.load_model_config(self.model_name)
                self._model_config = translate_v4_config(v4_config)

            return self._model_config

        def pre_build(self) -> None:
            """Skip bronze validation — v4 sources are more complex."""
            logger.info(f"Pre-build for v4 model: {self.model_name}")

        # Build the class with type()
        attrs = {
            "model_name": model_name,
            "depends_on": depends_on,
            "_v4_domains_dir": domains_dir,
            "get_model_class": get_model_class,
            "get_model_config": get_model_config,
            "pre_build": pre_build,
        }

        builder_class = type(class_name, (BaseModelBuilder,), attrs)
        return builder_class


def discover_v4_builders(repo_root: Path) -> Dict[str, Any]:
    """
    Convenience function to discover v4 builders from the domains/ directory.

    Args:
        repo_root: Repository root path

    Returns:
        Dict of created builder classes
    """
    domains_dir = repo_root / "domains"
    if not domains_dir.exists():
        return {}

    return V4BuilderFactory.create_builders(domains_dir)
