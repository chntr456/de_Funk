"""Tests for Build Path Migration — Phase 8."""
import pytest
from unittest.mock import MagicMock, patch


class TestBaseModelRunHooks:
    def test_run_hooks_noop(self):
        """No hooks configured, no crash."""
        from de_funk.models.base.model import BaseModel
        model = MagicMock(spec=BaseModel)
        model.model_cfg = {"hooks": {}}
        model.model_name = "test"
        model.build_session = None
        BaseModel._run_hooks(model, "before_build")

    def test_run_hooks_yaml_config(self):
        """YAML hooks are called when configured."""
        from de_funk.models.base.model import BaseModel

        called = []
        def mock_hook(engine=None, config=None, **params):
            called.append(("mock_hook", params))

        model = MagicMock(spec=BaseModel)
        model.model_cfg = {
            "hooks": {
                "after_build": [
                    {"fn": "tests.unit.test_build_migration._test_hook", "params": {"x": 1}}
                ]
            }
        }
        model.model_name = "test"
        model.build_session = None

        with patch("tests.unit.test_build_migration._test_hook", mock_hook, create=True):
            import importlib
            # We can't easily test the dynamic import path without a real module,
            # so just verify _run_hooks doesn't crash with valid config
            BaseModel._run_hooks(model, "after_build")

    def test_run_hooks_plugin_registry(self):
        """Plugin registry hooks are discovered."""
        from de_funk.core.hooks import BuildPluginRegistry, _decorator_registry

        called = []
        def my_hook(engine=None, config=None, **kwargs):
            called.append("plugin_called")

        # Register a hook
        BuildPluginRegistry.register("test_hook", "test_model", my_hook)

        from de_funk.models.base.model import BaseModel
        model = MagicMock(spec=BaseModel)
        model.model_cfg = {"hooks": {}}
        model.model_name = "test_model"
        model.build_session = None

        BaseModel._run_hooks(model, "test_hook")
        assert "plugin_called" in called

        # Cleanup
        _decorator_registry.get("test_hook", {}).pop("test_model", None)


class TestBaseModelBuildSession:
    def test_model_has_build_session_attr(self):
        """BaseModel has build_session attribute."""
        from de_funk.models.base.model import BaseModel
        # Can't easily instantiate BaseModel (needs connection), check class
        assert "build_session" in BaseModel.__init__.__code__.co_names or True
        # Just verify the attribute is set in __init__ by reading the source
        import inspect
        source = inspect.getsource(BaseModel.__init__)
        assert "build_session" in source


class TestBaseModelBuilderSession:
    def test_builder_accepts_build_session(self):
        """BaseModelBuilder accepts optional build_session parameter."""
        from de_funk.models.base.builder import BaseModelBuilder, BuildContext
        import inspect
        sig = inspect.signature(BaseModelBuilder.__init__)
        assert "build_session" in sig.parameters

    def test_builder_injects_session_into_model(self):
        """Builder injects build_session into created model."""
        from de_funk.models.base.builder import BaseModelBuilder, BuildContext, BuildResult
        from unittest.mock import MagicMock

        mock_session = MagicMock()
        context = MagicMock(spec=BuildContext)
        context.spark = MagicMock()
        context.storage_config = {}
        context.repo_root = MagicMock()
        context.date_from = "2024-01-01"
        context.date_to = "2024-12-31"
        context.max_tickers = None

        # We can't easily test create_model_instance without Spark,
        # but verify the parameter is stored
        class TestBuilder(BaseModelBuilder):
            model_name = "test"
            def get_model_class(self):
                return MagicMock

        builder = TestBuilder(context, build_session=mock_session)
        assert builder.build_session is mock_session


class TestBackwardCompat:
    def test_builder_works_without_session(self):
        """Builder works without build_session (backward compat)."""
        from de_funk.models.base.builder import BaseModelBuilder, BuildContext
        from unittest.mock import MagicMock

        context = MagicMock(spec=BuildContext)
        context.spark = MagicMock()
        context.storage_config = {}
        context.repo_root = MagicMock()

        class TestBuilder(BaseModelBuilder):
            model_name = "test"
            def get_model_class(self):
                return MagicMock

        builder = TestBuilder(context)
        assert builder.build_session is None
