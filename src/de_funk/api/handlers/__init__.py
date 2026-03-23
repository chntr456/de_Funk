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

    Creates one QueryEngine (one DuckDB connection), then injects it
    into each handler via _qe. ExhibitHandler bridge methods proxy
    all QueryEngine operations.
    """
    from de_funk.api.executor import QueryEngine

    registry = HandlerRegistry()
    shared_engine = QueryEngine(
        storage_root=storage_root,
        memory_limit=memory_limit,
        max_sql_rows=max_sql_rows,
        max_dimension_values=max_dimension_values,
        max_response_mb=max_response_mb,
    )
    registry.shared_engine = shared_engine

    for cls in _HANDLER_CLASSES:
        handler = cls.__new__(cls)
        handler._qe = shared_engine
        registry.register(handler)
    return registry
