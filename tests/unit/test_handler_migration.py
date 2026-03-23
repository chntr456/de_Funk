"""Tests for Handler Migration — Phase 7."""
import pytest


class TestHandlerNoQueryEngineMixin:
    def test_graphical_no_mixin(self):
        from de_funk.api.handlers.graphical import GraphicalHandler
        from de_funk.api.executor import QueryEngine
        assert QueryEngine not in GraphicalHandler.__mro__

    def test_pivot_no_mixin(self):
        from de_funk.api.handlers.pivot import PivotHandler
        from de_funk.api.executor import QueryEngine
        assert QueryEngine not in PivotHandler.__mro__

    def test_metrics_no_mixin(self):
        from de_funk.api.handlers.metrics import MetricsHandler
        from de_funk.api.executor import QueryEngine
        assert QueryEngine not in MetricsHandler.__mro__

    def test_box_no_mixin(self):
        from de_funk.api.handlers.box import BoxHandler
        from de_funk.api.executor import QueryEngine
        assert QueryEngine not in BoxHandler.__mro__

    def test_table_data_no_mixin(self):
        from de_funk.api.handlers.table_data import TableDataHandler
        from de_funk.api.executor import QueryEngine
        assert QueryEngine not in TableDataHandler.__mro__


class TestHandlerHasQe:
    def test_handler_qe_attribute(self):
        from de_funk.api.handlers.base import ExhibitHandler
        assert hasattr(ExhibitHandler, '_qe')

    def test_build_registry_sets_qe(self):
        from de_funk.api.handlers import build_registry
        from pathlib import Path
        registry = build_registry(
            storage_root=Path("storage/silver"),
            memory_limit="256MB",
            max_sql_rows=1000,
            max_dimension_values=100,
            max_response_mb=1.0,
        )
        handler = registry.get("line")
        assert handler is not None
        assert handler._qe is not None
        assert handler._qe is registry.shared_engine
