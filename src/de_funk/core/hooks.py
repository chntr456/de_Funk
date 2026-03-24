"""
HookRunner — config-first hook dispatch.

Reads hooks from YAML config (model.md hooks: section), imports and
calls the declared Python functions. Falls back to @pipeline_hook
decorated functions for hooks that can't be expressed in YAML
(e.g. custom_node_loading which returns a DataFrame).

Config is king — YAML hooks are checked first. Python decorators
are the escape hatch for complex logic.

Usage:
    runner = HookRunner(model_cfg, model_name="securities.stocks")
    runner.run("post_build", engine=engine, model=model)

    # Or with the decorator fallback:
    @pipeline_hook("custom_node_loading", model="temporal")
    def generate_calendar(engine, config, **params):
        return calendar_df  # Can't do this in YAML
"""
from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, List

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


# ── Decorator registry (fallback for non-YAML hooks) ──────

_decorator_registry: Dict[str, Dict[str, List[Callable]]] = {}


def pipeline_hook(hook_type: str, model: str = "*"):
    """Decorator to register a hook function.

    Use for hooks that CAN'T be declared in YAML — typically because
    they return a value (like custom_node_loading returning a DataFrame).

    For hooks that are side effects (pre/post build, training, etc.),
    prefer declaring them in model.md hooks: section instead.

    Args:
        hook_type: Hook point (pre_build, before_build, after_build,
                   post_build, custom_node_loading)
        model: Model name or "*" for all models
    """
    def decorator(fn: Callable) -> Callable:
        _decorator_registry.setdefault(hook_type, {}).setdefault(model, []).append(fn)
        logger.debug(f"Registered @pipeline_hook: {hook_type}/{model} → {fn.__name__}")
        return fn
    return decorator


def discover_plugins(plugins_dir: str = "de_funk.plugins"):
    """Auto-discover plugin modules. Importing them triggers @pipeline_hook registration."""
    import pkgutil
    try:
        package = importlib.import_module(plugins_dir)
        for _, name, _ in pkgutil.iter_modules(package.__path__):
            importlib.import_module(f"{plugins_dir}.{name}")
            logger.info(f"Discovered plugin: {plugins_dir}.{name}")
    except (ModuleNotFoundError, AttributeError) as e:
        logger.debug(f"No plugins at {plugins_dir}: {e}")


# ── HookRunner — config-first dispatch ─────────────────────

class HookRunner:
    """Dispatches hooks from YAML config, with decorator fallback.

    Resolution order:
    1. Read model_cfg["hooks"][hook_name] → list of {fn, params}
    2. Import each fn by dotted path, call it
    3. If no YAML hooks, check @pipeline_hook decorator registry
    4. If neither, no-op
    """

    def __init__(self, model_cfg: dict, model_name: str = ""):
        self.model_cfg = model_cfg
        self.model_name = model_name

    def run(self, hook_name: str, **context) -> Any:
        """Run all hooks for a lifecycle event.

        Args:
            hook_name: Hook point (pre_build, before_build, after_build, post_build)
            **context: Passed to each hook fn (engine, model, dims, facts, etc.)

        Returns:
            Result from last hook, or None
        """
        result = None

        # 1. YAML config hooks (primary — config is king)
        hooks_cfg = self.model_cfg.get("hooks", {})
        hook_defs = hooks_cfg.get(hook_name, [])

        if hook_defs:
            for hook_def in hook_defs:
                fn_path = hook_def.get("fn", "") if isinstance(hook_def, dict) else getattr(hook_def, 'fn', '')
                params = hook_def.get("params", {}) if isinstance(hook_def, dict) else getattr(hook_def, 'params', {})

                if not fn_path:
                    continue

                try:
                    fn = _import_fn(fn_path)
                    result = fn(config=self.model_cfg, **context, **params)
                    logger.info(f"Hook {hook_name}: {fn_path}")
                except Exception as e:
                    logger.warning(f"Hook {hook_name}/{fn_path} failed: {e}")
            return result

        # 2. Decorator registry (fallback — Python escape hatch)
        decorator_hooks = _get_decorator_hooks(hook_name, self.model_name)
        if decorator_hooks:
            for fn in decorator_hooks:
                try:
                    result = fn(config=self.model_cfg, **context)
                    logger.info(f"Hook {hook_name}: @pipeline_hook {fn.__name__}")
                except Exception as e:
                    logger.warning(f"Hook {hook_name}/{fn.__name__} failed: {e}")
            return result

        # 3. No hooks — no-op
        return None

    def has_hooks(self, hook_name: str) -> bool:
        """Check if any hooks exist for a lifecycle event."""
        hooks_cfg = self.model_cfg.get("hooks", {})
        if hooks_cfg.get(hook_name):
            return True
        return bool(_get_decorator_hooks(hook_name, self.model_name))

    def list_hooks(self) -> dict:
        """List all available hooks for this model."""
        result = {}
        hooks_cfg = self.model_cfg.get("hooks", {})
        for hook_name, defs in hooks_cfg.items():
            result[hook_name] = [d.get("fn", "") if isinstance(d, dict) else "" for d in defs]

        # Add decorator hooks
        for hook_type, models in _decorator_registry.items():
            fns = models.get(self.model_name, []) + models.get("*", [])
            if fns:
                existing = result.get(hook_type, [])
                result[hook_type] = existing + [f"@{fn.__name__}" for fn in fns]

        return result


# ── Helpers ────────────────────────────────────────────────

def _import_fn(dotted_path: str) -> Callable:
    """Import a function by dotted path."""
    module_path, fn_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, fn_name)


def _get_decorator_hooks(hook_type: str, model_name: str) -> List[Callable]:
    """Get hooks from the decorator registry for a hook type + model."""
    hooks = _decorator_registry.get(hook_type, {})
    return hooks.get(model_name, []) + hooks.get("*", [])


# ── Backward compatibility ─────────────────────────────────
# BuildPluginRegistry is an alias for code that still references it.

class BuildPluginRegistry:
    """Deprecated: use HookRunner for config-first dispatch,
    or @pipeline_hook decorator for Python-only hooks."""

    @staticmethod
    def register(hook_type: str, model_name: str, fn: Callable):
        _decorator_registry.setdefault(hook_type, {}).setdefault(model_name, []).append(fn)

    @staticmethod
    def get(hook_type: str, model_name: str) -> List[Callable]:
        return _get_decorator_hooks(hook_type, model_name)

    @staticmethod
    def list_hooks() -> Dict[str, Dict[str, int]]:
        return {ht: {m: len(fns) for m, fns in models.items()}
                for ht, models in _decorator_registry.items()}

    @staticmethod
    def discover(plugins_dir: str = "de_funk.plugins"):
        discover_plugins(plugins_dir)
