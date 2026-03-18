"""Great Tables formatter — converts pivot DataFrames into styled HTML.

Ports the `pretty_print` pattern: column kind classification, format
application, colour-coded banding, and spanner grouping via ``||`` keys.

Uses shared format codes and parsing from ``formatting.py``.
"""
from __future__ import annotations

from typing import Any

from great_tables import GT, loc, md, style

from de_funk.api.handlers.formatting import (
    parse_format_section,
    resolve_color,
    resolve_format,
)
from de_funk.api.models.requests import GreatTablesResponse, TableColumn


# ---------------------------------------------------------------------------
# GT-specific format code mapping
# ---------------------------------------------------------------------------

_GT_FMT = {
    "$":       ("fmt_currency", dict(currency="USD", decimals=0)),
    "$2":      ("fmt_currency", dict(currency="USD", decimals=2)),
    "$K":      ("fmt_number",   dict(decimals=1, scale_by=1e-3, pattern="${x}K")),
    "$M":      ("fmt_number",   dict(decimals=1, scale_by=1e-6, pattern="${x}M")),
    "$B":      ("fmt_number",   dict(decimals=2, scale_by=1e-9, pattern="${x}B")),
    "%":       ("fmt_percent",  dict(decimals=2, scale_values=True)),
    "%0":      ("fmt_percent",  dict(decimals=0, scale_values=True)),
    "number":  ("fmt_number",   dict(decimals=0, use_seps=True)),
    "decimal": ("fmt_number",   dict(decimals=4, use_seps=False)),
    "decimal2":("fmt_number",   dict(decimals=2, use_seps=False)),
}


def _apply_format(table: GT, columns: list[str], fmt_code: str | None) -> GT:
    """Apply a single format code to a list of GT columns."""
    if not fmt_code or fmt_code not in _GT_FMT or not columns:
        return table
    method_name, kwargs = _GT_FMT[fmt_code]
    return getattr(table, method_name)(columns=columns, **kwargs)


# ---------------------------------------------------------------------------
# Column kind classification (pivot-specific)
# ---------------------------------------------------------------------------

def _col_kind(
    col: str,
    measure_keys: set[str],
    window_keys: set[str],
    row_keys: list[str],
    layout: str,
) -> str:
    """Classify a column for formatting: row_dim | measure | window."""
    if col in row_keys:
        return "row_dim"
    base = _base_key(col, layout)
    if base in window_keys:
        return "window"
    if base in measure_keys:
        return "measure"
    # Flat pivot columns (dimension values like "2011") are data, not row dims
    if col not in row_keys and "||" not in col and col not in measure_keys:
        return "measure"
    return "row_dim"


def _base_key(col: str, layout: str) -> str:
    """Extract the measure/window alias from a column key."""
    if "||" in col:
        parts = col.split("||")
        return parts[0] if layout == "by_measure" else parts[1]
    return col


def _effective_override_key(
    col: str,
    layout: str,
    measure_keys: set[str],
    window_keys: set[str],
    row_keys: list[str],
    fmt_overrides: dict[str, dict],
) -> str:
    """Resolve the format-override lookup key for a column.

    In flat 2D pivots (single measure), column keys are dimension values
    like "2011" — not the measure key. Fall back to the sole measure key
    so that format/color specified for the measure applies to all columns.
    """
    base = _base_key(col, layout)
    if base in fmt_overrides or base in measure_keys or base in window_keys:
        return base
    # Flat pivot column — use the single measure key if exactly one exists
    if col not in row_keys and len(measure_keys) == 1:
        return next(iter(measure_keys))
    return base


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_gt(
    rows: list[list[Any]],
    columns: list[TableColumn],
    formatting: dict[str, Any] | None = None,
    layout: str = "by_measure",
    measure_keys: set[str] | None = None,
    window_keys: set[str] | None = None,
) -> GreatTablesResponse:
    """Build a complete Great Tables HTML response from pivot data."""
    import pandas as pd

    formatting = formatting or {}
    measure_keys = measure_keys or set()
    window_keys = window_keys or set()

    title = formatting.get("title", "")
    subtitle = formatting.get("subtitle", "")
    defaults = formatting.get("defaults", {})
    fmt_overrides = parse_format_section(formatting.get("format"))
    totals_cfg = formatting.get("totals", {})

    font_size = defaults.get("font_size", "10px")
    label_size = defaults.get("label_font_size", "9px")

    col_keys = [c.key for c in columns]
    all_data_keys = measure_keys | window_keys
    row_dims = [
        c.key for c in columns
        if not c.group and "||" not in c.key and c.key not in all_data_keys
        and c.format is None
    ]

    df = pd.DataFrame(rows, columns=col_keys)
    table = GT(df)

    # ── Title ────────────────────────────────────────────────────────────
    if title or subtitle:
        table = table.tab_header(
            title=md(f"**{title}**") if title else None,
            subtitle=md(subtitle) if subtitle else None,
        )

    # ── Column labels from || separator ──────────────────────────────────
    col_labels = {}
    for c in columns:
        if "||" in c.key:
            col_labels[c.key] = c.key.split("||")[1].replace("_", " ")
        elif c.label != c.key:
            col_labels[c.key] = c.label
    if col_labels:
        table = table.cols_label(**col_labels)

    # ── Spanners from group metadata ─────────────────────────────────────
    spanners: dict[str, list[str]] = {}
    for c in columns:
        if c.group:
            spanners.setdefault(c.group, []).append(c.key)
    for spanner_label, spanner_cols in spanners.items():
        table = table.tab_spanner(
            label=md(f"**{spanner_label}**"),
            columns=spanner_cols,
        )

    # ── Formatting by format code ────────────────────────────────────────
    fmt_groups: dict[str, list[str]] = {}
    for c in columns:
        if c.key in row_dims:
            continue
        lookup = _effective_override_key(
            c.key, layout, measure_keys, window_keys, row_dims, fmt_overrides,
        )
        effective_fmt = resolve_format(lookup, c.format, fmt_overrides)
        if effective_fmt:
            fmt_groups.setdefault(effective_fmt, []).append(c.key)

    for fmt_code, fmt_cols in fmt_groups.items():
        table = _apply_format(table, fmt_cols, fmt_code)

    # ── Window columns: default percent formatting if no format set ──────
    win_cols = [
        c.key for c in columns
        if _col_kind(c.key, measure_keys, window_keys, row_dims, layout) == "window"
        and c.format is None
        and _base_key(c.key, layout) not in fmt_overrides
    ]
    if win_cols:
        table = table.fmt_percent(columns=win_cols, decimals=2, scale_values=True)

    # ── Colour banding — batch by color to reduce tab_style calls ────────
    color_groups: dict[str, list[str]] = {}
    for c in columns:
        if c.key in row_dims:
            continue
        lookup = _effective_override_key(
            c.key, layout, measure_keys, window_keys, row_dims, fmt_overrides,
        )
        kind = _col_kind(c.key, measure_keys, window_keys, row_dims, layout)
        color = resolve_color(lookup, kind, fmt_overrides, defaults)
        if color:
            color_groups.setdefault(color, []).append(c.key)
    for color, color_cols in color_groups.items():
        table = table.tab_style(
            style=style.fill(color=color),
            locations=loc.body(columns=color_cols),
        )

    # ── Totals row styling ───────────────────────────────────────────────
    totals_color = totals_cfg.get("color")
    if totals_color and rows:
        totals_indices = [i for i, row in enumerate(rows) if row[0] is None]
        if totals_indices:
            table = table.tab_style(
                style=[style.fill(color=totals_color), style.text(weight="bold")],
                locations=loc.body(rows=totals_indices),
            )

    # ── Row dimension styling ────────────────────────────────────────────
    max_row_width = defaults.get("max_row_width", "320px")
    if row_dims:
        table = table.tab_style(
            style=style.css(f"max-width: {max_row_width}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"),
            locations=loc.body(columns=row_dims),
        )

    # ── Data column width constraints ─────────────────────────────────
    max_col_width = defaults.get("max_col_width", "110px")
    data_cols = [c.key for c in columns if c.key not in row_dims]
    if data_cols:
        table = table.tab_style(
            style=style.css(f"max-width: {max_col_width}; overflow: hidden; text-overflow: ellipsis;"),
            locations=loc.body(columns=data_cols),
        )

    # ── Header styling ───────────────────────────────────────────────────
    table = (
        table
        .tab_style(style=style.text(weight="bold"), locations=loc.column_labels())
        .tab_options(
            table_font_size=font_size,
            column_labels_font_size=label_size,
            heading_align="left",
        )
    )

    html = table.as_raw_html()
    return GreatTablesResponse(html=html)
