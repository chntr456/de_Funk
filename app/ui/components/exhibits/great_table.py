"""
Great Tables exhibit renderer.

Renders publication-quality tables using the great_tables library.
Supports:
- Column formatting (currency, percent, number, date)
- Spanners (grouped column headers) with model schema integration
- Row grouping and hierarchies
- Conditional formatting
- Source notes and footnotes
- Themes (default, financial, dark, striped, minimal)
- Period aggregation with subtotals
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import pandas as pd
import streamlit as st

from config.logging import get_logger

logger = get_logger(__name__)

# Try to import great_tables, provide helpful message if not installed
try:
    from great_tables import GT, loc, style, md
    from great_tables.gt import GT as GTType
    GREAT_TABLES_AVAILABLE = True
except ImportError:
    GREAT_TABLES_AVAILABLE = False
    GT = None
    GTType = None


class GreatTableRenderer:
    """
    Renderer for Great Tables exhibits.

    Supports:
    - Column formatting (currency, percent, number, date)
    - Spanners (grouped column headers)
    - Row grouping
    - Conditional formatting
    - Source notes and footnotes
    - Themes (default, financial, dark, striped, minimal)
    """

    # Format type to GT formatter mapping
    FORMAT_MAP = {
        'currency': 'fmt_currency',
        'currency_millions': 'fmt_currency',
        'currency_billions': 'fmt_currency',
        'percent': 'fmt_percent',
        'number': 'fmt_number',
        'integer': 'fmt_integer',
        'date': 'fmt_date',
        'datetime': 'fmt_datetime',
    }

    # Theme configurations
    THEME_CONFIGS = {
        'default': {'style': 1},
        'financial': {'style': 2, 'row_striping': True},
        'dark': {'style': 6},
        'striped': {'row_striping': True},
        'minimal': {'style': 1},
    }

    def __init__(self, exhibit: Any, pdf: pd.DataFrame, model_schema: Optional[Dict] = None):
        """
        Initialize the renderer.

        Args:
            exhibit: Exhibit configuration object
            pdf: Pandas DataFrame with data
            model_schema: Optional model schema for column groups (spanners)
        """
        self.exhibit = exhibit
        self.pdf = pdf
        self.model_schema = model_schema
        self.gt: Optional[GTType] = None

    def render(self) -> None:
        """Render the Great Table exhibit."""
        if not GREAT_TABLES_AVAILABLE:
            st.error(
                "Great Tables is not installed. "
                "Install with: `pip install great_tables`"
            )
            return

        if self.pdf is None or self.pdf.empty:
            st.warning("No data available for this table.")
            return

        try:
            # Build GT object
            self.gt = GT(self.pdf)

            # Apply configuration in order
            self._apply_header()
            self._apply_columns()
            self._apply_spanners()
            self._apply_formatting()
            self._apply_conditional_formatting()
            self._apply_row_config()
            self._apply_footer()
            self._apply_theme()

            # Render to Streamlit
            self._render_to_streamlit()

        except Exception as e:
            logger.error(f"Error rendering Great Table: {e}", exc_info=True)
            st.error(f"Error rendering table: {str(e)}")
            # Fallback to basic dataframe display
            st.dataframe(self.pdf)

    def _apply_header(self) -> None:
        """Apply title and subtitle."""
        title = getattr(self.exhibit, 'title', None)
        subtitle = getattr(self.exhibit, 'subtitle', None)

        if title or subtitle:
            self.gt = self.gt.tab_header(
                title=title,
                subtitle=subtitle
            )

    def _apply_columns(self) -> None:
        """Apply column labels from configuration."""
        columns_config = getattr(self.exhibit, 'columns', None)

        if not columns_config:
            return

        labels = {}

        # Handle list of column configs
        if isinstance(columns_config, list):
            for col_config in columns_config:
                if isinstance(col_config, dict):
                    col_id = col_config.get('id')
                    col_label = col_config.get('label')
                    if col_id and col_label and col_id in self.pdf.columns:
                        labels[col_id] = col_label
                elif isinstance(col_config, str):
                    # Simple column name, use as-is
                    pass

        # Handle dict of column configs
        elif isinstance(columns_config, dict):
            # Check for measures sub-config
            measures = columns_config.get('measures', [])
            for measure_config in measures:
                if isinstance(measure_config, dict):
                    col_id = measure_config.get('id')
                    col_label = measure_config.get('label')
                    if col_id and col_label and col_id in self.pdf.columns:
                        labels[col_id] = col_label

        if labels:
            self.gt = self.gt.cols_label(**labels)

    def _apply_spanners(self) -> None:
        """Apply column spanners (grouped headers)."""
        spanners_config = getattr(self.exhibit, 'spanners', None)

        if not spanners_config:
            return

        # Handle "auto" - get from model schema
        if spanners_config == 'auto' and self.model_schema:
            spanners_config = self._get_spanners_from_schema()

        if not isinstance(spanners_config, list):
            return

        for spanner in spanners_config:
            if isinstance(spanner, dict):
                # Check for from_model reference
                if 'from_model' in spanner and self.model_schema:
                    model_spanner = self._get_spanner_from_model(spanner['from_model'])
                    if model_spanner:
                        self._add_spanner(model_spanner)
                else:
                    self._add_spanner(spanner)

    def _get_spanners_from_schema(self) -> List[Dict]:
        """Extract spanners from model schema column_groups."""
        spanners = []

        if not self.model_schema:
            return spanners

        # Get column_groups from schema
        column_groups = self.model_schema.get('column_groups', {})

        for group_name, group_config in column_groups.items():
            if isinstance(group_config, dict):
                label = group_config.get('label', group_name)
                columns = group_config.get('columns', [])

                # Only include columns that exist in the dataframe
                valid_columns = [c for c in columns if c in self.pdf.columns]

                if valid_columns:
                    spanners.append({
                        'label': label,
                        'columns': valid_columns
                    })

        return spanners

    def _get_spanner_from_model(self, group_name: str) -> Optional[Dict]:
        """Get a single spanner from model schema by group name."""
        if not self.model_schema:
            return None

        column_groups = self.model_schema.get('column_groups', {})
        group_config = column_groups.get(group_name)

        if not group_config:
            return None

        label = group_config.get('label', group_name)
        columns = group_config.get('columns', [])

        # Only include columns that exist in the dataframe
        valid_columns = [c for c in columns if c in self.pdf.columns]

        if not valid_columns:
            return None

        return {
            'label': label,
            'columns': valid_columns
        }

    def _add_spanner(self, spanner: Dict) -> None:
        """Add a single spanner to the table."""
        label = spanner.get('label', '')
        columns = spanner.get('columns', [])

        # Filter to columns that exist
        valid_columns = [c for c in columns if c in self.pdf.columns]

        if valid_columns and label:
            try:
                self.gt = self.gt.tab_spanner(
                    label=label,
                    columns=valid_columns
                )
            except Exception as e:
                logger.warning(f"Failed to add spanner '{label}': {e}")

    def _apply_formatting(self) -> None:
        """Apply column number formats."""
        columns_config = getattr(self.exhibit, 'columns', None)

        if not columns_config:
            return

        # Collect columns by format type
        format_groups: Dict[str, List[str]] = {}

        # Process list of column configs
        if isinstance(columns_config, list):
            for col_config in columns_config:
                if isinstance(col_config, dict):
                    self._collect_format(col_config, format_groups)

        # Process dict with measures
        elif isinstance(columns_config, dict):
            measures = columns_config.get('measures', [])
            for measure_config in measures:
                if isinstance(measure_config, dict):
                    self._collect_format(measure_config, format_groups)

        # Apply formats
        for format_type, cols in format_groups.items():
            valid_cols = [c for c in cols if c in self.pdf.columns]
            if valid_cols:
                self._apply_format(format_type, valid_cols)

    def _collect_format(self, col_config: Dict, format_groups: Dict[str, List[str]]) -> None:
        """Collect column format info."""
        col_id = col_config.get('id')
        col_format = col_config.get('format')

        if col_id and col_format:
            if col_format not in format_groups:
                format_groups[col_format] = []
            format_groups[col_format].append(col_id)

    def _apply_format(self, format_type: str, columns: List[str]) -> None:
        """Apply a format type to columns."""
        try:
            if format_type == 'currency':
                self.gt = self.gt.fmt_currency(columns=columns)
            elif format_type == 'currency_millions':
                self.gt = self.gt.fmt_currency(columns=columns, scale_by=1e-6, pattern="{x}M")
            elif format_type == 'currency_billions':
                self.gt = self.gt.fmt_currency(columns=columns, scale_by=1e-9, pattern="{x}B")
            elif format_type == 'percent':
                self.gt = self.gt.fmt_percent(columns=columns, decimals=1)
            elif format_type == 'number':
                self.gt = self.gt.fmt_number(columns=columns, decimals=2)
            elif format_type == 'integer':
                self.gt = self.gt.fmt_integer(columns=columns)
            elif format_type == 'date':
                self.gt = self.gt.fmt_date(columns=columns)
            elif format_type == 'datetime':
                self.gt = self.gt.fmt_datetime(columns=columns)
        except Exception as e:
            logger.warning(f"Failed to apply format {format_type}: {e}")

    def _apply_conditional_formatting(self) -> None:
        """Apply conditional formatting rules."""
        columns_config = getattr(self.exhibit, 'columns', None)

        if not columns_config:
            return

        # Process list of column configs
        if isinstance(columns_config, list):
            for col_config in columns_config:
                if isinstance(col_config, dict):
                    self._apply_column_conditional(col_config)

        # Process dict with measures
        elif isinstance(columns_config, dict):
            measures = columns_config.get('measures', [])
            for measure_config in measures:
                if isinstance(measure_config, dict):
                    self._apply_column_conditional(measure_config)

    def _apply_column_conditional(self, col_config: Dict) -> None:
        """Apply conditional formatting to a single column."""
        col_id = col_config.get('id')
        conditional = col_config.get('conditional')

        if not col_id or not conditional or col_id not in self.pdf.columns:
            return

        cond_type = conditional.get('type')

        if cond_type == 'color_scale':
            try:
                palette = conditional.get('palette', ['red', 'white', 'green'])
                domain = conditional.get('domain')

                self.gt = self.gt.data_color(
                    columns=col_id,
                    palette=palette,
                    domain=domain
                )
            except Exception as e:
                logger.warning(f"Failed to apply color scale to {col_id}: {e}")

    def _apply_row_config(self) -> None:
        """Apply row configuration (grouping, striping)."""
        row_config = getattr(self.exhibit, 'rows', None)
        row_striping = getattr(self.exhibit, 'row_striping', True)

        # Handle row grouping
        if row_config and isinstance(row_config, dict):
            group_by = row_config.get('group_by')
            if group_by and group_by in self.pdf.columns:
                try:
                    self.gt = self.gt.tab_stub(rowname_col=group_by)
                except Exception as e:
                    logger.warning(f"Failed to set row stub: {e}")

        # Apply row striping if enabled
        if row_striping:
            try:
                self.gt = self.gt.opt_row_striping()
            except Exception as e:
                logger.debug(f"Row striping not applied: {e}")

    def _apply_footer(self) -> None:
        """Apply footer (source notes, footnotes)."""
        source_note = getattr(self.exhibit, 'source_note', None)
        footnotes = getattr(self.exhibit, 'footnotes', None)

        if source_note:
            try:
                self.gt = self.gt.tab_source_note(source_note=source_note)
            except Exception as e:
                logger.warning(f"Failed to add source note: {e}")

        if footnotes and isinstance(footnotes, list):
            for fn in footnotes:
                if isinstance(fn, dict):
                    try:
                        fn_text = fn.get('text', '')
                        fn_column = fn.get('column')

                        if fn_column and fn_column in self.pdf.columns:
                            self.gt = self.gt.tab_footnote(
                                footnote=fn_text,
                                locations=loc.body(columns=fn_column)
                            )
                    except Exception as e:
                        logger.warning(f"Failed to add footnote: {e}")

    def _apply_theme(self) -> None:
        """Apply visual theme."""
        theme = getattr(self.exhibit, 'theme', 'default')

        theme_config = self.THEME_CONFIGS.get(theme, self.THEME_CONFIGS['default'])

        try:
            # Apply style if specified
            if 'style' in theme_config:
                self.gt = self.gt.opt_stylize(style=theme_config['style'])

            # Apply row striping if in theme (and not already applied)
            if theme_config.get('row_striping'):
                self.gt = self.gt.opt_row_striping()

        except Exception as e:
            logger.debug(f"Theme application issue: {e}")

    def _render_to_streamlit(self) -> None:
        """Render GT to Streamlit."""
        try:
            # GT renders to HTML
            html = self.gt.as_raw_html()

            # Display in Streamlit
            st.html(html)

            # Optional: Export buttons
            self._render_export_buttons(html)

        except Exception as e:
            logger.error(f"Failed to render to Streamlit: {e}")
            st.dataframe(self.pdf)

    def _render_export_buttons(self, html: str) -> None:
        """Render export buttons if enabled."""
        export_html = getattr(self.exhibit, 'export_html', False)
        export_png = getattr(self.exhibit, 'export_png', False)

        if not (export_html or export_png):
            return

        col1, col2 = st.columns(2)

        if export_html:
            with col1:
                st.download_button(
                    label="Download HTML",
                    data=html,
                    file_name="table.html",
                    mime="text/html"
                )

        if export_png:
            with col2:
                st.info("PNG export requires browser rendering setup")


def render_great_table(
    exhibit: Any,
    pdf: pd.DataFrame,
    model_schema: Optional[Dict] = None,
    **kwargs
) -> None:
    """
    Render a Great Tables exhibit.

    Entry point for the exhibit dispatcher.

    Args:
        exhibit: Exhibit configuration object
        pdf: Pandas DataFrame with data
        model_schema: Optional model schema for column groups
        **kwargs: Additional arguments (ignored)
    """
    renderer = GreatTableRenderer(exhibit, pdf, model_schema)
    renderer.render()
