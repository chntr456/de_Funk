"""Tests for Handler Migration — handlers use Engine directly."""
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


class TestHandlerHasEngine:
    def test_handler_engine_attribute(self):
        from de_funk.api.handlers.base import ExhibitHandler
        assert hasattr(ExhibitHandler, '_engine')

    def test_build_registry_sets_engine(self):
        from de_funk.api.handlers import build_registry
        from de_funk.core.engine import Engine

        engine = Engine.for_duckdb(memory_limit="256MB")
        registry = build_registry(engine=engine, max_sql_rows=100,
                                  max_dimension_values=50, max_response_mb=1.0)
        handler = registry.get("line")
        assert handler is not None
        assert handler._engine is engine

    def test_no_qe_on_handlers(self):
        from de_funk.api.handlers import build_registry
        from de_funk.core.engine import Engine

        engine = Engine.for_duckdb(memory_limit="256MB")
        registry = build_registry(engine=engine)
        handler = registry.get("line")
        # _qe should not exist — handlers use _engine directly
        assert not hasattr(handler, '_qe') or handler._qe is None
