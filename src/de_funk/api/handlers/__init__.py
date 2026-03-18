"""
Handler registry — auto-discovers handlers and maps type strings to instances.

Usage:
    registry = build_registry(storage_root, memory_limit, ...)
    handler = registry.get("plotly.line")
    result = handler.execute(payload, resolver)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from de_funk.api.handlers.base import ExhibitHandler
from de_funk.api.handlers.graphical import GraphicalHandler
from de_funk.api.handlers.box import BoxHandler
from de_funk.api.handlers.table_data import TableDataHandler
from de_funk.api.handlers.pivot import PivotHandler
from de_funk.api.handlers.metrics import MetricsHandler

_HANDLER_CLASSES: list[type[ExhibitHandler]] = [
    GraphicalHandler,
    BoxHandler,
    TableDataHandler,
    PivotHandler,
    MetricsHandler,
]


class HandlerRegistry:
    """Maps block type strings to handler instances."""

    def __init__(self) -> None:
        self._handlers: dict[str, ExhibitHandler] = {}

    def register(self, handler: ExhibitHandler) -> None:
        for type_str in handler.handles:
            self._handlers[type_str] = handler

    def get(self, type_str: str) -> ExhibitHandler | None:
        return self._handlers.get(type_str)

    @property
    def supported_types(self) -> set[str]:
        return set(self._handlers.keys())


def build_registry(
    storage_root: Path,
    memory_limit: str,
    max_sql_rows: int,
    max_dimension_values: int,
    max_response_mb: float,
) -> HandlerRegistry:
    """Build the handler registry with a shared DuckDB connection.

    Creates one QueryEngine (one DuckDB connection), then injects its
    connection state into each handler. This prevents 5+ separate
    connections each holding their own buffer cache — the main cause
    of progressive memory bloat.
    """
    from de_funk.api.executor import QueryEngine

    registry = HandlerRegistry()
    init_kwargs: dict[str, Any] = dict(
        storage_root=storage_root,
        memory_limit=memory_limit,
        max_sql_rows=max_sql_rows,
        max_dimension_values=max_dimension_values,
        max_response_mb=max_response_mb,
    )

    # Create a single shared QueryEngine with one DuckDB connection
    shared_engine = QueryEngine(**init_kwargs)
    registry.shared_engine = shared_engine

    for cls in _HANDLER_CLASSES:
        handler = cls.__new__(cls)
        # Copy shared engine state into the handler instance
        handler._conn = shared_engine._conn
        handler._delta_available = shared_engine._delta_available
        handler._scan_cache = shared_engine._scan_cache
        handler._max_sql_rows = shared_engine._max_sql_rows
        handler._max_dimension_values = shared_engine._max_dimension_values
        handler.max_response_mb = shared_engine.max_response_mb
        handler.storage_root = shared_engine.storage_root
        registry.register(handler)
    return registry
