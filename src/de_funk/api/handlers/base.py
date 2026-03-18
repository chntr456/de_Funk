"""
ExhibitHandler — abstract base class for all exhibit execution families.

Each handler subclass declares a `handles` set of type strings it owns
and implements `execute()` to process the request and return a response.
Handlers inherit shared DuckDB infrastructure from QueryEngine via mixin.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ExhibitHandler(ABC):
    """Base class for exhibit handlers.

    Subclasses must define:
        handles: set[str]  — block type strings this handler owns
                              (e.g. {"plotly.line", "line", "line_chart"})

    Subclasses inherit QueryEngine as a mixin for shared infra:
        Planning layer (backend-agnostic):
            self._collect_tables(resolved_fields)
            self._resolve_filter_tables(filters, resolver)

        Execution layer (DuckDB):
            self._build_from(tables, resolver)
            self._build_where(filters, resolver)
            self._execute(sql)
    """

    handles: set[str]

    @abstractmethod
    def execute(self, payload: dict[str, Any], resolver: Any) -> Any:
        """Execute the exhibit query and return a response model."""
        ...
