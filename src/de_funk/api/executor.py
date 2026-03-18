"""
QueryEngine — shared DuckDB infrastructure mixin for exhibit handlers.

Provides two layers:
  Planning (backend-agnostic): _collect_tables, _resolve_filter_tables
  Execution (DuckDB): _execute, _safe_scan, _build_from, _build_where, _build_order

Handlers inherit this mixin alongside ExhibitHandler to get SQL generation
and query execution without duplicating infrastructure.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb

from de_funk.api.resolver import ResolvedField
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Module-level helpers (used by handlers directly)
# ---------------------------------------------------------------------------

def _eval_date_expr(expr: object) -> str | None:
    """Evaluate frontmatter date expressions to ISO date strings.

    Handles: current_date, current_date ± N, year_start, literal dates.
    """
    if expr is None:
        return None
    s = str(expr).strip()
    today = date.today()
    if s == "current_date":
        return str(today)
    m = re.match(r"current_date\s*-\s*(\d+)", s)
    if m:
        return str(today - timedelta(days=int(m.group(1))))
    m = re.match(r"current_date\s*\+\s*(\d+)", s)
    if m:
        return str(today + timedelta(days=int(m.group(1))))
    if s == "year_start":
        return str(today.replace(month=1, day=1))
    return s


def truncate_to_mb(rows: list[list], columns, max_mb: float) -> tuple[list[list], bool]:
    """Truncate row list so the JSON-serialised response stays under max_mb.

    Returns (rows, truncated).  Uses a fast byte estimate from a 50-row sample.
    """
    import json
    max_bytes = int(max_mb * 1024 * 1024)
    if not rows:
        return rows, False
    sample = rows[:min(50, len(rows))]
    sample_bytes = len(json.dumps(sample, default=str).encode())
    bytes_per_row = sample_bytes / len(sample)
    estimated_total = bytes_per_row * len(rows)
    if estimated_total <= max_bytes:
        return rows, False
    max_rows = max(1, int(max_bytes / bytes_per_row))
    return rows[:max_rows], True


# ---------------------------------------------------------------------------
# QueryEngine mixin
# ---------------------------------------------------------------------------

class QueryEngine:
    """Shared DuckDB infrastructure for exhibit handlers.

    Initialised once at app startup and shared across all handler instances
    via multiple inheritance.
    """

    def __init__(
        self,
        storage_root: Path,
        memory_limit: str,
        max_sql_rows: int,
        max_dimension_values: int,
        max_response_mb: float,
    ) -> None:
        self.max_response_mb = max_response_mb
        self._max_sql_rows = max_sql_rows
        self._max_dimension_values = max_dimension_values
        self.storage_root = storage_root
        self._conn = duckdb.connect()
        self._conn.execute(f"SET memory_limit='{memory_limit}'")
        self._scan_cache: dict[str, str] = {}
        try:
            self._conn.execute("INSTALL delta; LOAD delta;")
            self._delta_available = True
        except Exception:
            self._delta_available = False
        logger.info(
            f"QueryEngine ready — storage_root={storage_root}, "
            f"delta={self._delta_available}, memory_limit={memory_limit}, "
            f"max_sql_rows={max_sql_rows}, max_dim_values={max_dimension_values}, "
            f"max_response={max_response_mb}MB"
        )

    # -------------------------------------------------------------------
    # Execution layer (DuckDB-specific)
    # -------------------------------------------------------------------

    def _execute(self, sql: str, max_rows: int | None = None) -> list:
        """Central query execution — streams at most max_rows rows."""
        import time
        limit = max_rows if max_rows is not None else self._max_sql_rows
        t0 = time.perf_counter()
        result = self._conn.execute(sql).fetchmany(limit)
        elapsed = (time.perf_counter() - t0) * 1000
        logger.debug(f"SQL execute: {len(result)} rows in {elapsed:.0f}ms")
        return result

    def _scan(self, path: str) -> str:
        """Return a DuckDB scan expression (delta_scan or read_parquet)."""
        if self._delta_available:
            return f"delta_scan('{path}')"
        return f"read_parquet('{path}/*.parquet')"

    def _safe_scan(self, path: str) -> str:
        """Return a cached DuckDB scan expression, probing delta_scan on first use."""
        if path in self._scan_cache:
            return self._scan_cache[path]
        if not self._delta_available:
            expr = f"read_parquet('{path}/*.parquet')"
        else:
            try:
                self._conn.execute(f"SELECT 1 FROM delta_scan('{path}') LIMIT 0")
                expr = f"delta_scan('{path}')"
            except Exception:
                logger.debug(f"delta_scan failed for {path}, falling back to read_parquet")
                expr = f"read_parquet('{path}/*.parquet')"
        self._scan_cache[path] = expr
        return expr

    # -------------------------------------------------------------------
    # Planning layer (backend-agnostic metadata)
    # -------------------------------------------------------------------

    @staticmethod
    def _collect_tables(resolved_fields: list[ResolvedField | None]) -> dict[str, str]:
        """Collect unique table_name → Silver path mappings from resolved fields."""
        tables: dict[str, str] = {}
        for r in resolved_fields:
            if r is None:
                continue
            tables[r.table_name] = str(r.silver_path)
        return tables

    @staticmethod
    def _collect_tables_with_domains(
        resolved_fields: list[ResolvedField | None],
    ) -> tuple[dict[str, str], set[str]]:
        """Collect tables AND their canonical domains from resolved fields."""
        tables: dict[str, str] = {}
        domains: set[str] = set()
        for r in resolved_fields:
            if r is None:
                continue
            tables[r.table_name] = str(r.silver_path)
            domains.add(r.domain)
        return tables, domains

    @staticmethod
    def _resolve_filter_tables(
        filters,
        resolver: Any,
        *,
        allowed_domains: set[str] | None = None,
        **_kw,
    ) -> list[ResolvedField]:
        """Resolve filter fields so their tables enter the FROM clause.

        When *allowed_domains* is provided, filters whose domain is not
        in the allowed set are excluded.  This prevents cross-domain page
        filters (e.g. ``corporate.entity.sector`` on a municipal exhibit)
        from pulling unrelated tables into the FROM clause.
        """
        resolved = []
        for f in (filters or []):
            try:
                r = resolver.resolve(f.field)
            except ValueError:
                continue
            if allowed_domains is not None and r.domain not in allowed_domains:
                logger.info(
                    f"Skipping out-of-scope filter '{f.field}' — "
                    f"domain '{r.domain}' not in {allowed_domains}"
                )
                continue
            resolved.append(r)
        return resolved

    @staticmethod
    def _extra_filter_fields(
        extra_filters: list[tuple[ResolvedField | str, Any]] | None,
    ) -> list[ResolvedField]:
        """Extract ResolvedField objects from extra_filters for table collection."""
        if not extra_filters:
            return []
        return [f for f, _ in extra_filters if isinstance(f, ResolvedField)]

    # -------------------------------------------------------------------
    # SQL generation (DuckDB-specific)
    # -------------------------------------------------------------------

    def _build_from(
        self,
        tables: dict[str, str],
        resolver: Any = None,
        allowed_domains: set[str] | None = None,
    ) -> str:
        """Build a FROM clause with automatic join resolution.

        Strategy:
        1. Single table → plain scan.
        2. Use resolver.find_join_path() BFS for multi-hop join chains.
           All tables (including dim_calendar) are joined via graph edges
           so the correct join columns are used (e.g. period_end_date_id).
        3. Fallback: CROSS JOIN if no graph path exists.

        Sets ``self._from_tables`` to the set of table names actually
        included in the FROM clause.  Callers (e.g. ``_build_where``) can
        use this to skip WHERE references to tables that were requested
        but couldn't be joined.
        """
        if not tables:
            raise ValueError("No tables to query")
        if len(tables) == 1:
            name, path = next(iter(tables.items()))
            self._from_tables = {name}
            return f'{self._safe_scan(path)} AS "{name}"'

        # Put dimension tables last so facts are the base for joins.
        # This gives BFS better starting points for finding join paths.
        names = sorted(
            tables.keys(),
            key=lambda n: (n.startswith("dim_"), n),
        )

        base = names[0]
        included: dict[str, str] = {base: tables[base]}
        parts = [f'{self._safe_scan(tables[base])} AS "{base}"']

        for target_name in names[1:]:
            if target_name in included:
                continue

            path_steps = None
            path_start = None
            for already_in in included:
                steps = resolver.find_join_path(already_in, target_name, allowed_domains=allowed_domains) if resolver else None
                if steps is not None:
                    path_steps = steps
                    path_start = already_in
                    break

            if path_steps is None:
                logger.warning(
                    f"No graph path from included tables to '{target_name}' — "
                    "using CROSS JOIN. Check graph.edges in model.md."
                )
                parts.append(f'CROSS JOIN {self._safe_scan(tables[target_name])} AS "{target_name}"')
                included[target_name] = tables[target_name]
                continue

            current = path_start
            for (next_table, col_on_current, col_on_next) in path_steps:
                if next_table in included:
                    current = next_table
                    continue
                next_path = tables.get(next_table) or self._resolve_intermediate_path(next_table, resolver)
                if next_path is None:
                    logger.warning(f"Cannot find Silver path for intermediate table '{next_table}' — skipping")
                    break
                parts.append(
                    f'JOIN {self._safe_scan(next_path)} AS "{next_table}"'
                    f' ON "{current}"."{col_on_current}" = "{next_table}"."{col_on_next}"'
                )
                included[next_table] = next_path
                current = next_table

        self._from_tables = set(included)
        return " ".join(parts)

    def _resolve_intermediate_path(self, table_name: str, resolver: Any = None) -> str | None:
        """Find Silver path for an intermediate table needed to complete a join chain."""
        if resolver is None:
            return None
        for domain, fields in resolver._index.items():
            for tbl, _, subdir in fields.values():
                if tbl == table_name:
                    domain_path = domain.replace(".", "/")
                    domain_root = resolver._domain_overrides.get(
                        domain, resolver.storage_root / domain_path
                    )
                    return str(domain_root / subdir / table_name) if subdir else str(domain_root / table_name)
        return None

    def _build_where(self, filters, resolver: Any, *, from_tables: dict[str, str] | set[str] | None = None) -> list[str]:
        """Build WHERE clause fragments from filter specs.

        Filters referencing tables not in the FROM clause are silently
        skipped.  This prevents cross-domain page filters from injecting
        unreachable table references (e.g. a ``corporate.finance.reported_currency``
        filter on a municipal-only exhibit).

        Table membership is checked against (in priority order):
        1. Explicit *from_tables* parameter (dict keys or set)
        2. ``self._from_tables`` set populated by ``_build_from``
        """
        # Determine which tables are actually in the FROM clause
        joined: set[str] | None = None
        if from_tables is not None:
            joined = set(from_tables) if isinstance(from_tables, dict) else from_tables
        elif hasattr(self, "_from_tables"):
            joined = self._from_tables

        clauses = []
        for f in (filters or []):
            try:
                resolved = resolver.resolve(f.field)
            except ValueError:
                continue
            # Skip filters whose table isn't in the FROM clause
            if joined is not None and resolved.table_name not in joined:
                logger.warning(
                    f"Skipping filter {f.field} — table '{resolved.table_name}' "
                    f"not in query tables {list(joined)}"
                )
                continue
            col = f'"{resolved.table_name}"."{resolved.column}"'
            op = f.operator
            val = f.value

            if op == "in":
                # If a single string was passed, treat as equality (not char iteration)
                if isinstance(val, str):
                    clauses.append(f"{col} = '{val}'")
                    continue
                values = list(val) if not isinstance(val, list) else val
                if not values:
                    continue
                placeholders = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in values)
                clauses.append(f"{col} IN ({placeholders})")
            elif op == "eq":
                v = f"'{val}'" if isinstance(val, str) else str(val)
                clauses.append(f"{col} = {v}")
            elif op == "gte":
                v = f"'{val}'" if isinstance(val, str) else str(val)
                clauses.append(f"{col} >= {v}")
            elif op == "lte":
                v = f"'{val}'" if isinstance(val, str) else str(val)
                clauses.append(f"{col} <= {v}")
            elif op == "like" and isinstance(val, str):
                clauses.append(f"{col} LIKE '{val}'")
            elif op == "between" and isinstance(val, dict):
                lo_raw = val.get("from")
                hi_raw = val.get("to")
                lo = lo_raw if isinstance(lo_raw, (int, float)) else _eval_date_expr(lo_raw)
                hi = hi_raw if isinstance(hi_raw, (int, float)) else _eval_date_expr(hi_raw)
                def _q(v):
                    return str(v) if isinstance(v, (int, float)) else f"'{v}'"
                if lo and hi:
                    clauses.append(f"{col} BETWEEN {_q(lo)} AND {_q(hi)}")
                elif lo:
                    clauses.append(f"{col} >= {_q(lo)}")
                elif hi:
                    clauses.append(f"{col} <= {_q(hi)}")

        return clauses

    @staticmethod
    def _build_extra_where(extra_filters: list[tuple[ResolvedField | str, Any]] | None) -> str:
        """Build AND-joined WHERE fragments from context filter pairs."""
        if not extra_filters:
            return ""
        parts: list[str] = []
        for field_or_col, val in extra_filters:
            if isinstance(field_or_col, ResolvedField):
                col_ref = f'"{field_or_col.table_name}"."{field_or_col.column}"'
            else:
                col_ref = f'"{field_or_col}"'
            if isinstance(val, list):
                if not val:
                    continue
                placeholders = ", ".join(
                    f"'{v}'" if isinstance(v, str) else str(v) for v in val
                )
                parts.append(f'{col_ref} IN ({placeholders})')
            else:
                quoted = f"'{val}'" if isinstance(val, str) else str(val)
                parts.append(f'{col_ref} = {quoted}')
        return (" AND " + " AND ".join(parts)) if parts else ""

    def _build_order(self, sort, x_resolved) -> str:
        """Build ORDER BY clause from sort spec or default to x axis."""
        if sort:
            direction = sort.order.upper() if sort.order else "ASC"
            if sort.by:
                return f"ORDER BY {sort.by} {direction}"
        if x_resolved:
            return f'ORDER BY "{x_resolved.table_name}"."{x_resolved.column}" ASC'
        return ""

    # -------------------------------------------------------------------
    # Dimension value queries (used by /api/dimensions endpoint)
    # -------------------------------------------------------------------

    def distinct_values(
        self,
        resolved: ResolvedField,
        extra_filters: list[tuple[ResolvedField | str, Any]] | None = None,
        resolver: Any = None,
    ) -> list[Any]:
        """Return sorted distinct values for a dimension field."""
        col = f'"{resolved.table_name}"."{resolved.column}"'
        tables = self._collect_tables([resolved] + self._extra_filter_fields(extra_filters))
        extra = self._build_extra_where(extra_filters)

        if len(tables) == 1:
            from_clause = f'{self._safe_scan(str(resolved.silver_path))} AS "{resolved.table_name}"'
        else:
            from_clause = self._build_from(tables, resolver)

        sql = f"""
            SELECT DISTINCT {col}
            FROM {from_clause}
            WHERE {col} IS NOT NULL{extra}
            ORDER BY {col}
        """
        logger.debug(f"distinct_values SQL: {sql}")
        result = self._execute(sql, max_rows=self._max_dimension_values)
        return [row[0] for row in result]

    def distinct_values_by_measure(
        self,
        resolved: ResolvedField,
        order_by: ResolvedField,
        order_dir: str = "desc",
        extra_filters: list[tuple[ResolvedField | str, Any]] | None = None,
        resolver: Any = None,
    ) -> list[Any]:
        """Return distinct values for a dimension, ordered by aggregated measure."""
        dim_col = f'"{resolved.table_name}"."{resolved.column}"'
        measure_col = f'"{order_by.table_name}"."{order_by.column}"'
        dir_sql = "DESC" if order_dir.lower() == "desc" else "ASC"
        extra = self._build_extra_where(extra_filters)

        tables = self._collect_tables(
            [resolved, order_by] + self._extra_filter_fields(extra_filters)
        )

        if len(tables) == 1:
            name, path = next(iter(tables.items()))
            from_clause = f'{self._safe_scan(path)} AS "{name}"'
        else:
            from_clause = self._build_from(tables, resolver)

        sql = f"""
            SELECT {dim_col}, AVG({measure_col}) AS _sort_val
            FROM {from_clause}
            WHERE {dim_col} IS NOT NULL{extra}
            GROUP BY {dim_col}
            ORDER BY _sort_val {dir_sql}
        """
        logger.debug(f"distinct_values_by_measure SQL: {sql}")
        result = self._execute(sql, max_rows=self._max_dimension_values)
        return [row[0] for row in result]
