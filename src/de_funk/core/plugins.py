"""
Build plugin registry — extensible hook system.

Hooks can be registered via:
    1. @pipeline_hook decorator on plugin functions
    2. BuildPluginRegistry.register() programmatically
    3. YAML config hooks: section in domain model frontmatter

Hook fn signature:
    def my_hook(df, engine, config, **params) -> Any
"""
from __future__ import annotations
from typing import Callable, Dict, List

from de_funk.config.logging import get_logger

logger = get_logger(__name__)

_registry: Dict[str, Dict[str, List[Callable]]] = {}


def pipeline_hook(hook_type: str, model: str = "*"):
    """Decorator to register a pipeline hook.

    Args:
        hook_type: Hook point name (pre_build, before_build, after_build,
                   post_build, custom_node_loading)
        model: Model name to attach to, or "*" for all models

    Usage:
        @pipeline_hook("after_build", model="corporate.entity")
        def fix_cik(df, engine, config, dims=None, facts=None, **params):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        _registry.setdefault(hook_type, {}).setdefault(model, []).append(fn)
        logger.debug(f"Registered hook: {hook_type}/{model} → {fn.__name__}")
        return fn
    return decorator


class BuildPluginRegistry:
    """Registry for build-time hooks."""

    @staticmethod
    def register(hook_type: str, model_name: str, fn: Callable):
        """Register a hook function."""
        _registry.setdefault(hook_type, {}).setdefault(model_name, []).append(fn)

    @staticmethod
    def get(hook_type: str, model_name: str) -> List[Callable]:
        """Get all hooks for a hook type + model name.

        Returns hooks registered for the specific model + wildcard hooks.
        """
        hooks = _registry.get(hook_type, {})
        return hooks.get(model_name, []) + hooks.get("*", [])

    @staticmethod
    def list_hooks() -> Dict[str, Dict[str, int]]:
        """List all registered hooks with counts."""
        return {
            hook_type: {model: len(fns) for model, fns in models.items()}
            for hook_type, models in _registry.items()
        }

    @staticmethod
    def discover(plugins_dir: str = "de_funk.plugins"):
        """Auto-discover and import all plugin modules.

        Importing a module that uses @pipeline_hook will automatically
        register its hooks in the global registry.
        """
        import importlib
        import pkgutil

        try:
            package = importlib.import_module(plugins_dir)
            for _, name, _ in pkgutil.iter_modules(package.__path__):
                importlib.import_module(f"{plugins_dir}.{name}")
                logger.info(f"Discovered plugin: {plugins_dir}.{name}")
        except (ModuleNotFoundError, AttributeError) as e:
            logger.debug(f"No plugins found at {plugins_dir}: {e}")
