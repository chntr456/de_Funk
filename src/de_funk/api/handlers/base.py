"""
ExhibitHandler — abstract base class for all exhibit execution families.

Each handler subclass declares a `handles` set of type strings it owns
and implements `execute()` to process the request and return a response.

Handlers access shared DuckDB infrastructure via composition:
    self._qe  — QueryEngine instance (set by HandlerRegistry)

Bridge methods proxy all QueryEngine operations so handler code
can use self._execute(), self._build_from(), etc. unchanged.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ExhibitHandler(ABC):
    """Base class for exhibit handlers.

    Subclasses must define:
        handles: set[str]  — block type strings this handler owns

    Infrastructure is injected via _qe (QueryEngine) by the registry.
    All QueryEngine methods are proxied here for backward compat.
    """

    handles: set[str]

    # Infrastructure — set by HandlerRegistry
    _qe: Any = None  # QueryEngine instance
    session: Any = None  # QuerySession (future)

    @abstractmethod
    def execute(self, payload: dict[str, Any], resolver: Any) -> Any:
        """Execute the exhibit query and return a response model."""
        ...

    # ── QueryEngine bridge methods ────────────────────────
    # These proxy to self._qe so handler code can use self._method()
    # unchanged after removing the QueryEngine mixin.

    def _execute(self, sql: str, max_rows: int | None = None) -> list:
        return self._qe._execute(sql, max_rows)

    def _scan(self, path: str) -> str:
        return self._qe._scan(path)

    def _safe_scan(self, path: str) -> str:
        return self._qe._safe_scan(path)

    @staticmethod
    def _collect_tables(resolved_fields) -> dict[str, str]:
        from de_funk.api.executor import QueryEngine
        return QueryEngine._collect_tables(resolved_fields)

    @staticmethod
    def _collect_tables_with_domains(resolved_fields):
        from de_funk.api.executor import QueryEngine
        return QueryEngine._collect_tables_with_domains(resolved_fields)

    @staticmethod
    def _resolve_filter_tables(filters, resolver, *, allowed_domains=None, **kw):
        from de_funk.api.executor import QueryEngine
        return QueryEngine._resolve_filter_tables(filters, resolver, allowed_domains=allowed_domains, **kw)

    @staticmethod
    def _extra_filter_fields(extra_filters):
        from de_funk.api.executor import QueryEngine
        return QueryEngine._extra_filter_fields(extra_filters)

    def _build_from(self, tables, resolver=None, allowed_domains=None):
        return self._qe._build_from(tables, resolver, allowed_domains)

    def _build_where(self, filters, resolver, *, from_tables=None):
        return self._qe._build_where(filters, resolver, from_tables=from_tables)

    @staticmethod
    def _build_extra_where(extra_filters):
        from de_funk.api.executor import QueryEngine
        return QueryEngine._build_extra_where(extra_filters)

    def _build_order(self, sort, x_resolved):
        return self._qe._build_order(sort, x_resolved)

    def _resolve_intermediate_path(self, table_name, resolver=None):
        return self._qe._resolve_intermediate_path(table_name, resolver)

    def distinct_values(self, resolved, extra_filters=None, resolver=None):
        return self._qe.distinct_values(resolved, extra_filters, resolver)

    def distinct_values_by_measure(self, resolved, order_by, order_dir="desc",
                                   extra_filters=None, resolver=None):
        return self._qe.distinct_values_by_measure(
            resolved, order_by, order_dir, extra_filters, resolver)

    # ── Proxied properties ────────────────────────────────

    @property
    def max_response_mb(self):
        return getattr(self._qe, 'max_response_mb', 4.0) if self._qe else 4.0

    @max_response_mb.setter
    def max_response_mb(self, value):
        if self._qe:
            self._qe.max_response_mb = value
        self._max_response_mb_override = value

    @property
    def storage_root(self):
        return getattr(self._qe, 'storage_root', None) if self._qe else None

    @storage_root.setter
    def storage_root(self, value):
        if self._qe:
            self._qe.storage_root = value
        self._storage_root_override = value

    @property
    def _max_sql_rows(self):
        return getattr(self._qe, '_max_sql_rows', 30000) if self._qe else 30000

    @_max_sql_rows.setter
    def _max_sql_rows(self, value):
        if self._qe:
            self._qe._max_sql_rows = value

    @property
    def _max_dimension_values(self):
        return getattr(self._qe, '_max_dimension_values', 10000) if self._qe else 10000

    @_max_dimension_values.setter
    def _max_dimension_values(self, value):
        if self._qe:
            self._qe._max_dimension_values = value

    @property
    def _from_tables(self):
        return getattr(self._qe, '_from_tables', set()) if self._qe else set()
