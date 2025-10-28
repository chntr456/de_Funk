"""
Professional notebook application with dual sidebars, themes, and cross-filtering.

Features:
- Independent collapsible sidebars (Explorer + Filters)
- Notebook management (Create, Delete, Rename, Duplicate)
- Day/Night themes with professional styling
- Dynamic cross-filtering across exhibits
- Clean, consulting-grade UI
"""

import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yaml
import json

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestration.context import RepoContext
from src.model.api.session import ModelSession
from src.notebook.api.notebook_session import NotebookSession
from src.notebook.schema import VariableType, ExhibitType


# Configure page - MUST be first Streamlit command
st.set_page_config(
    page_title="Notebook Platform",
    layout="wide",
    initial_sidebar_state="collapsed",  # We'll use custom sidebars
)


# Professional CSS styling with day/night themes
def load_custom_css():
    """Load custom CSS for professional styling."""
    theme = st.session_state.get('theme', 'day')

    if theme == 'day':
        colors = {
            'bg_primary': '#FFFFFF',
            'bg_secondary': '#F8F9FA',
            'bg_tertiary': '#E9ECEF',
            'text_primary': '#212529',
            'text_secondary': '#6C757D',
            'accent': '#0066CC',
            'accent_hover': '#0052A3',
            'border': '#DEE2E6',
            'success': '#28A745',
            'danger': '#DC3545',
            'warning': '#FFC107',
        }
    else:  # night theme
        colors = {
            'bg_primary': '#1A1D23',
            'bg_secondary': '#252A31',
            'bg_tertiary': '#2F3640',
            'text_primary': '#E4E7EB',
            'text_secondary': '#9CA3AF',
            'accent': '#3B82F6',
            'accent_hover': '#2563EB',
            'border': '#374151',
            'success': '#10B981',
            'danger': '#EF4444',
            'warning': '#F59E0B',
        }

    css = f"""
    <style>
    /* Global styles */
    .main {{
        background-color: {colors['bg_primary']};
        color: {colors['text_primary']};
    }}

    /* Hide default Streamlit elements */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}

    /* Custom sidebar panels */
    .sidebar-panel {{
        background-color: {colors['bg_secondary']};
        border-right: 1px solid {colors['border']};
        height: 100vh;
        overflow-y: auto;
        padding: 1rem;
        position: fixed;
        top: 0;
        transition: all 0.3s ease;
    }}

    .sidebar-panel.collapsed {{
        width: 40px !important;
    }}

    .sidebar-header {{
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: {colors['text_secondary']};
        margin-bottom: 1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}

    /* Tree item */
    .tree-item {{
        padding: 0.5rem 0.75rem;
        margin: 0.125rem 0;
        cursor: pointer;
        border-radius: 4px;
        font-size: 0.875rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        transition: background-color 0.2s;
    }}

    .tree-item:hover {{
        background-color: {colors['bg_tertiary']};
    }}

    .tree-item.active {{
        background-color: {colors['accent']};
        color: white;
        font-weight: 500;
    }}

    .tree-item.open {{
        background-color: {colors['bg_tertiary']};
    }}

    /* Folder */
    .tree-folder {{
        font-weight: 500;
        color: {colors['text_primary']};
    }}

    /* Tab bar */
    .tab-bar {{
        background-color: {colors['bg_secondary']};
        border-bottom: 1px solid {colors['border']};
        padding: 0.5rem 1rem;
        display: flex;
        gap: 0.25rem;
        overflow-x: auto;
    }}

    .tab {{
        background-color: transparent;
        border: 1px solid transparent;
        padding: 0.5rem 1rem;
        cursor: pointer;
        border-radius: 4px 4px 0 0;
        font-size: 0.875rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        white-space: nowrap;
        transition: all 0.2s;
    }}

    .tab:hover {{
        background-color: {colors['bg_tertiary']};
    }}

    .tab.active {{
        background-color: {colors['bg_primary']};
        border-color: {colors['border']};
        border-bottom-color: {colors['bg_primary']};
        font-weight: 500;
    }}

    .tab-close {{
        opacity: 0.6;
        margin-left: 0.5rem;
        cursor: pointer;
    }}

    .tab-close:hover {{
        opacity: 1;
        color: {colors['danger']};
    }}

    /* Filter section */
    .filter-section {{
        margin-bottom: 1.5rem;
    }}

    .filter-label {{
        font-size: 0.75rem;
        font-weight: 500;
        color: {colors['text_secondary']};
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    /* Metric cards */
    .metric-card {{
        background-color: {colors['bg_secondary']};
        border: 1px solid {colors['border']};
        border-radius: 8px;
        padding: 1.5rem;
        text-align: center;
    }}

    .metric-value {{
        font-size: 2rem;
        font-weight: 600;
        color: {colors['text_primary']};
        margin: 0.5rem 0;
    }}

    .metric-label {{
        font-size: 0.875rem;
        color: {colors['text_secondary']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    /* Section headers */
    .section-header {{
        font-size: 1.125rem;
        font-weight: 600;
        color: {colors['text_primary']};
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid {colors['border']};
    }}

    /* Buttons */
    .stButton > button {{
        background-color: {colors['accent']};
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: background-color 0.2s;
    }}

    .stButton > button:hover {{
        background-color: {colors['accent_hover']};
    }}

    /* Input fields */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > select,
    .stMultiselect > div > div {{
        background-color: {colors['bg_primary']};
        color: {colors['text_primary']};
        border: 1px solid {colors['border']};
        border-radius: 4px;
    }}

    /* Dataframe */
    .dataframe {{
        font-size: 0.875rem;
    }}

    /* Charts */
    .js-plotly-plot {{
        border-radius: 8px;
        background-color: {colors['bg_secondary']};
    }}

    /* Theme toggle */
    .theme-toggle {{
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 1000;
        background-color: {colors['bg_secondary']};
        border: 1px solid {colors['border']};
        border-radius: 4px;
        padding: 0.5rem;
        cursor: pointer;
        font-size: 1.25rem;
    }}

    /* Action buttons */
    .action-btn {{
        background: none;
        border: 1px solid {colors['border']};
        border-radius: 4px;
        padding: 0.25rem 0.5rem;
        cursor: pointer;
        font-size: 0.75rem;
        color: {colors['text_secondary']};
        transition: all 0.2s;
    }}

    .action-btn:hover {{
        border-color: {colors['accent']};
        color: {colors['accent']};
    }}

    .action-btn.danger:hover {{
        border-color: {colors['danger']};
        color: {colors['danger']};
    }}
    </style>
    """

    st.markdown(css, unsafe_allow_html=True)


@st.cache_resource
def get_repo_context():
    """Get repository context (cached)."""
    return RepoContext.from_repo_root()


@st.cache_resource
def get_model_session(_ctx):
    """Get model session (cached)."""
    return ModelSession(_ctx.spark, _ctx.repo, _ctx.storage)


@st.cache_resource
def get_notebook_session(_model_session, _ctx):
    """Get notebook session (cached)."""
    return NotebookSession(_ctx.spark, _model_session, _ctx.repo)


# Session state initialization
def init_session_state():
    """Initialize session state variables."""
    defaults = {
        'open_tabs': [],  # List of (notebook_id, notebook_path, notebook_config)
        'active_tab': None,
        'edit_mode': {},  # Dict of notebook_id -> bool
        'yaml_content': {},  # Dict of notebook_id -> yaml string
        'explorer_collapsed': False,
        'filters_collapsed': False,
        'theme': 'day',  # 'day' or 'night'
        'cross_filter': {},  # Dict of filter_column -> [values]
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


class NotebookPlatform:
    """Professional notebook platform with advanced features."""

    def __init__(self):
        """Initialize application."""
        init_session_state()
        load_custom_css()

        self.ctx = get_repo_context()
        self.model_session = get_model_session(self.ctx)
        self.notebook_session = get_notebook_session(
            self.model_session,
            self.ctx,
        )
        self.notebooks_root = self.ctx.repo / "configs" / "notebooks"
        self.notebooks_root.mkdir(parents=True, exist_ok=True)

    def run(self):
        """Run the application."""
        # Theme toggle button
        self._render_theme_toggle()

        # Three-column layout: Explorer | Main Content | Filters
        left_col, main_col, right_col = st.columns([2, 7, 2])

        with left_col:
            self._render_explorer_panel()

        with main_col:
            self._render_main_content()

        with right_col:
            self._render_filters_panel()

    def _render_theme_toggle(self):
        """Render theme toggle button."""
        theme = st.session_state.theme
        icon = "☀️" if theme == 'night' else "🌙"

        if st.button(icon, key="theme_toggle", help="Toggle theme"):
            st.session_state.theme = 'night' if theme == 'day' else 'day'
            st.rerun()

    def _render_explorer_panel(self):
        """Render explorer sidebar panel."""
        # Header
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### Explorer")
        with col2:
            if st.button("⚙️", key="explorer_settings", help="Settings"):
                pass  # TODO: Settings menu

        # Collapse button
        if st.button("⮜" if not st.session_state.explorer_collapsed else "⮞",
                     key="toggle_explorer"):
            st.session_state.explorer_collapsed = not st.session_state.explorer_collapsed
            st.rerun()

        if st.session_state.explorer_collapsed:
            return

        st.divider()

        # Notebook management actions
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("➕", key="new_notebook", help="New notebook"):
                self._create_new_notebook()
        with col2:
            if st.button("📁", key="new_folder", help="New folder"):
                self._create_new_folder()
        with col3:
            if st.button("🔄", key="refresh", help="Refresh"):
                st.rerun()

        st.divider()

        # Directory tree
        notebooks = self._scan_notebooks()
        grouped = self._group_by_directory(notebooks)

        for folder, files in sorted(grouped.items()):
            if folder == ".":
                for file_path in sorted(files):
                    self._render_tree_item(file_path, indent=0)
            else:
                if st.expander(f"📂 {folder}", expanded=True):
                    for file_path in sorted(files):
                        self._render_tree_item(file_path, indent=1)

    def _render_tree_item(self, notebook_path: Path, indent: int = 0):
        """Render a tree item with actions."""
        notebook_id = str(notebook_path.relative_to(self.notebooks_root))
        notebook_name = notebook_path.stem

        is_open = any(tab[0] == notebook_id for tab in st.session_state.open_tabs)
        is_active = st.session_state.active_tab == notebook_id

        # Indent
        indent_str = "　" * indent

        # Item row
        col1, col2, col3 = st.columns([6, 1, 1])

        with col1:
            label = f"{indent_str}{notebook_name}"
            if st.button(label, key=f"tree_{notebook_id}",
                        type="primary" if is_active else "secondary",
                        use_container_width=True):
                self._open_notebook(notebook_id, notebook_path)

        with col2:
            if st.button("✏️", key=f"rename_{notebook_id}", help="Rename"):
                self._rename_notebook(notebook_path)

        with col3:
            if st.button("🗑️", key=f"delete_{notebook_id}", help="Delete"):
                self._delete_notebook(notebook_path)

    def _render_filters_panel(self):
        """Render filters sidebar panel."""
        # Header
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### Filters")
        with col2:
            if st.button("⮞" if not st.session_state.filters_collapsed else "⮜",
                        key="toggle_filters"):
                st.session_state.filters_collapsed = not st.session_state.filters_collapsed
                st.rerun()

        if st.session_state.filters_collapsed or not st.session_state.active_tab:
            return

        st.divider()

        # Get active notebook
        active_notebook = next(
            (tab for tab in st.session_state.open_tabs if tab[0] == st.session_state.active_tab),
            None
        )

        if not active_notebook:
            st.info("Open a notebook to see filters")
            return

        notebook_id, notebook_path, notebook_config = active_notebook

        # Cross-filters (from clicking charts)
        if st.session_state.cross_filter:
            st.markdown("#### Active Filters")
            for col, values in st.session_state.cross_filter.items():
                st.caption(f"{col}: {', '.join(map(str, values))}")
            if st.button("Clear", key="clear_cross_filter"):
                st.session_state.cross_filter = {}
                st.rerun()
            st.divider()

        # Regular filters
        st.markdown("#### Notebook Filters")

        filter_context = self.notebook_session.get_filter_context()
        filter_values = {}

        for var_id, variable in notebook_config.variables.items():
            if variable.type == VariableType.DATE_RANGE:
                filter_values[var_id] = self._render_date_range_filter(var_id, variable)
            elif variable.type == VariableType.MULTI_SELECT:
                filter_values[var_id] = self._render_multi_select_filter(var_id, variable)
            elif variable.type == VariableType.NUMBER:
                filter_values[var_id] = self._render_number_filter(var_id, variable)

        if filter_values:
            self.notebook_session.update_filters(filter_values)

    def _render_date_range_filter(self, var_id: str, variable) -> Dict[str, datetime]:
        """Render compact date range filter."""
        filter_context = self.notebook_session.get_filter_context()
        current_value = filter_context.get(var_id)

        if current_value and isinstance(current_value, dict):
            default_start = current_value['start']
            default_end = current_value['end']
            if isinstance(default_start, datetime):
                default_start = default_start.date()
            if isinstance(default_end, datetime):
                default_end = default_end.date()
        else:
            default_start = datetime.now().date() - timedelta(days=30)
            default_end = datetime.now().date()

        st.caption(variable.display_name)
        start_date = st.date_input(
            "From",
            value=default_start,
            key=f"filter_{var_id}_start",
            label_visibility="collapsed",
        )
        end_date = st.date_input(
            "To",
            value=default_end,
            key=f"filter_{var_id}_end",
            label_visibility="collapsed",
        )

        return {
            'start': datetime.combine(start_date, datetime.min.time()),
            'end': datetime.combine(end_date, datetime.min.time()),
        }

    def _render_multi_select_filter(self, var_id: str, variable) -> List[Any]:
        """Render compact multi-select filter."""
        options = variable.default if variable.default else []
        default = variable.default if variable.default else []

        return st.multiselect(
            variable.display_name,
            options=options,
            default=default,
            key=f"filter_{var_id}",
        )

    def _render_number_filter(self, var_id: str, variable) -> float:
        """Render compact number filter."""
        default = variable.default if variable.default is not None else 0.0

        return st.number_input(
            variable.display_name,
            value=float(default),
            key=f"filter_{var_id}",
        )

    def _render_main_content(self):
        """Render main content area."""
        if not st.session_state.open_tabs:
            self._render_welcome()
            return

        # Tab bar
        st.markdown('<div class="tab-bar">', unsafe_allow_html=True)
        tabs_html = ""
        for notebook_id, notebook_path, notebook_config in st.session_state.open_tabs:
            is_active = st.session_state.active_tab == notebook_id
            active_class = "active" if is_active else ""
            tabs_html += f'<div class="tab {active_class}">{notebook_config.notebook.title}</div>'
        st.markdown(tabs_html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Render active notebook
        active_notebook = next(
            (tab for tab in st.session_state.open_tabs if tab[0] == st.session_state.active_tab),
            None
        )

        if active_notebook:
            self._render_notebook_content(active_notebook)

    def _render_notebook_content(self, notebook_tuple):
        """Render notebook content."""
        notebook_id, notebook_path, notebook_config = notebook_tuple

        # Header with actions
        col1, col2, col3 = st.columns([6, 1, 1])
        with col1:
            st.title(notebook_config.notebook.title)
            if notebook_config.notebook.description:
                st.caption(notebook_config.notebook.description)
        with col2:
            if st.button("Edit" if not st.session_state.edit_mode.get(notebook_id) else "View",
                        key=f"toggle_mode_{notebook_id}"):
                st.session_state.edit_mode[notebook_id] = not st.session_state.edit_mode.get(notebook_id, False)
                st.rerun()
        with col3:
            if st.button("✕", key=f"close_main_{notebook_id}"):
                self._close_tab(notebook_id)

        st.divider()

        # Content
        if st.session_state.edit_mode.get(notebook_id, False):
            self._render_yaml_editor(notebook_id, notebook_path)
        else:
            self._render_notebook_exhibits(notebook_id, notebook_config)

    def _render_yaml_editor(self, notebook_id: str, notebook_path: Path):
        """Render YAML editor."""
        yaml_content = st.session_state.yaml_content.get(notebook_id, "")

        edited_content = st.text_area(
            "YAML Content",
            value=yaml_content,
            height=600,
            key=f"yaml_{notebook_id}",
        )

        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("Save", key=f"save_{notebook_id}"):
                self._save_notebook(notebook_id, notebook_path, edited_content)
        with col2:
            if st.button("Reload", key=f"reload_{notebook_id}"):
                with open(notebook_path, 'r') as f:
                    st.session_state.yaml_content[notebook_id] = f.read()
                st.rerun()

    def _render_notebook_exhibits(self, notebook_id: str, notebook_config):
        """Render notebook exhibits with cross-filtering support."""
        # Apply cross-filters to the notebook session's filter context
        if st.session_state.cross_filter:
            self._apply_cross_filters()

        for section in notebook_config.layout:
            st.markdown(f'<div class="section-header">{section.title}</div>', unsafe_allow_html=True)

            if section.columns > 1:
                cols = st.columns(section.columns)
                for i, exhibit_id in enumerate(section.exhibits):
                    with cols[i % section.columns]:
                        self._render_exhibit(exhibit_id, enable_cross_filter=True)
            else:
                for exhibit_id in section.exhibits:
                    self._render_exhibit(exhibit_id, enable_cross_filter=True)

    def _apply_cross_filters(self):
        """Apply cross-filters to the notebook session's filter context."""
        # Map cross-filter columns to variable names
        column_to_var_mapping = {
            'ticker': 'tickers',
            'trade_date': 'time',
            # Add more mappings as needed
        }

        filter_updates = {}
        for col, values in st.session_state.cross_filter.items():
            # Find corresponding variable
            var_name = column_to_var_mapping.get(col, col)

            # Update filter value
            if var_name in self.notebook_session.notebook_config.variables:
                filter_updates[var_name] = values

        if filter_updates:
            self.notebook_session.update_filters(filter_updates)

    def _render_exhibit(self, exhibit_id: str, enable_cross_filter: bool = False):
        """Render an exhibit with optional cross-filtering."""
        try:
            notebook_config = self.notebook_session.notebook_config
            exhibit = next((e for e in notebook_config.exhibits if e.id == exhibit_id), None)

            if not exhibit:
                st.error(f"Exhibit {exhibit_id} not found")
                return

            # Execute the exhibit
            result_df = self.notebook_session.execute_exhibit(exhibit_id)

            if result_df is None or result_df.count() == 0:
                st.warning(f"{exhibit.title}: No data")
                return

            # Convert to Pandas
            pandas_df = result_df.toPandas()

            # Get dimensions and measures
            dimensions = [d for d in notebook_config.dimensions if d.id in exhibit.dimensions]
            measures = [m for m in notebook_config.measures if m.id in exhibit.measures]

            # Render based on exhibit type
            if exhibit.type == ExhibitType.METRIC_CARD:
                self._render_metric_card(exhibit, pandas_df, measures)
            elif exhibit.type == ExhibitType.BAR_CHART:
                self._render_bar_chart(exhibit, pandas_df, dimensions, measures, enable_cross_filter)
            elif exhibit.type == ExhibitType.LINE_CHART:
                self._render_line_chart(exhibit, pandas_df, dimensions, measures, enable_cross_filter)
            elif exhibit.type == ExhibitType.TABLE:
                self._render_data_table(exhibit, pandas_df, dimensions, measures, enable_cross_filter)
            else:
                st.warning(f"Unsupported exhibit type: {exhibit.type}")

        except Exception as e:
            st.error(f"Error rendering {exhibit_id}: {e}")

    def _render_metric_card(self, exhibit, pandas_df, measures):
        """Render a metric card."""
        for measure in measures:
            value = pandas_df[measure.id].iloc[0] if len(pandas_df) > 0 else 0

            # Format value
            if measure.format:
                if measure.format.startswith('$'):
                    formatted = f"${value:,.2f}"
                elif measure.format == 'percent':
                    formatted = f"{value:.2%}"
                else:
                    formatted = f"{value:,.2f}"
            else:
                formatted = f"{value:,.2f}"

            # Render metric card with custom styling
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{measure.display_name}</div>
                <div class="metric-value">{formatted}</div>
            </div>
            """, unsafe_allow_html=True)

    def _render_bar_chart(self, exhibit, pandas_df, dimensions, measures, enable_cross_filter):
        """Render a bar chart."""
        st.markdown(f"#### {exhibit.title}")

        if len(dimensions) == 0:
            st.warning("Bar chart requires at least one dimension")
            return

        x_col = dimensions[0].source.column
        y_col = measures[0].id

        # Create Plotly chart
        fig = px.bar(
            pandas_df,
            x=x_col,
            y=y_col,
            title=None,
            labels={y_col: measures[0].display_name, x_col: dimensions[0].display_name},
        )

        # Apply theme styling
        theme = st.session_state.theme
        if theme == 'night':
            fig.update_layout(
                plot_bgcolor='#252A31',
                paper_bgcolor='#252A31',
                font=dict(color='#E4E7EB'),
            )
        else:
            fig.update_layout(
                plot_bgcolor='#F8F9FA',
                paper_bgcolor='#F8F9FA',
            )

        # Display chart
        if enable_cross_filter:
            # Add click event handling via session state
            event = st.plotly_chart(fig, use_container_width=True, key=f"chart_{exhibit.id}", on_select="rerun")

            # Handle click events for cross-filtering
            if event and hasattr(event, 'selection') and event.selection:
                selected_points = event.selection.get('points', [])
                if selected_points:
                    selected_values = [point.get('x') for point in selected_points]
                    if selected_values:
                        # Update cross-filter state
                        st.session_state.cross_filter[x_col] = selected_values
                        st.rerun()
        else:
            st.plotly_chart(fig, use_container_width=True)

    def _render_line_chart(self, exhibit, pandas_df, dimensions, measures, enable_cross_filter):
        """Render a line chart."""
        st.markdown(f"#### {exhibit.title}")

        if len(dimensions) == 0:
            st.warning("Line chart requires at least one dimension")
            return

        x_col = dimensions[0].source.column
        y_col = measures[0].id

        # Sort by x axis
        pandas_df = pandas_df.sort_values(x_col)

        # Create Plotly chart
        fig = px.line(
            pandas_df,
            x=x_col,
            y=y_col,
            title=None,
            labels={y_col: measures[0].display_name, x_col: dimensions[0].display_name},
            markers=True,
        )

        # Apply theme styling
        theme = st.session_state.theme
        if theme == 'night':
            fig.update_layout(
                plot_bgcolor='#252A31',
                paper_bgcolor='#252A31',
                font=dict(color='#E4E7EB'),
            )
        else:
            fig.update_layout(
                plot_bgcolor='#F8F9FA',
                paper_bgcolor='#F8F9FA',
            )

        st.plotly_chart(fig, use_container_width=True)

    def _render_data_table(self, exhibit, pandas_df, dimensions, measures, enable_cross_filter):
        """Render a data table."""
        st.markdown(f"#### {exhibit.title}")

        # Prepare display columns
        display_cols = {}
        for dim in dimensions:
            display_cols[dim.source.column] = dim.display_name
        for measure in measures:
            display_cols[measure.id] = measure.display_name

        # Rename columns for display
        display_df = pandas_df.copy()
        display_df = display_df.rename(columns=display_cols)

        # Format numbers
        for measure in measures:
            if measure.id in pandas_df.columns:
                col_name = display_cols[measure.id]
                if measure.format:
                    if measure.format.startswith('$'):
                        display_df[col_name] = display_df[col_name].apply(lambda x: f"${x:,.2f}")
                    elif measure.format == 'percent':
                        display_df[col_name] = display_df[col_name].apply(lambda x: f"{x:.2%}")

        # Display with selection if cross-filter enabled
        if enable_cross_filter and len(dimensions) > 0:
            selected_rows = st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                selection_mode="multi-row",
                on_select="rerun",
                key=f"table_{exhibit.id}",
            )

            # Handle row selection for cross-filtering
            if selected_rows and hasattr(selected_rows, 'selection') and selected_rows.selection:
                selected_indices = selected_rows.selection.get('rows', [])
                if selected_indices:
                    # Get dimension column to filter on
                    filter_col = dimensions[0].source.column
                    selected_values = pandas_df.iloc[selected_indices][filter_col].tolist()
                    if selected_values:
                        st.session_state.cross_filter[filter_col] = selected_values
                        st.rerun()
        else:
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    def _render_welcome(self):
        """Render professional welcome screen."""
        st.markdown("""
        # Notebook Platform

        ### Professional Financial Modeling Environment

        **Get Started:**
        - Click **➕** in the Explorer to create a new notebook
        - Click any notebook name to open it
        - Use the theme toggle (☀️/🌙) for your preferred appearance

        **Features:**
        - Dynamic cross-filtering across all exhibits
        - Professional day/night themes
        - Inline YAML editing
        - Organized folder structure
        """)

    # Helper methods
    def _scan_notebooks(self) -> List[Path]:
        return list(self.notebooks_root.rglob("*.yaml"))

    def _group_by_directory(self, notebooks: List[Path]) -> Dict[str, List[Path]]:
        grouped = {}
        for notebook_path in notebooks:
            rel_path = notebook_path.relative_to(self.notebooks_root)
            folder = "." if len(rel_path.parts) == 1 else rel_path.parts[0]
            if folder not in grouped:
                grouped[folder] = []
            grouped[folder].append(notebook_path)
        return grouped

    def _open_notebook(self, notebook_id: str, notebook_path: Path):
        existing = next((t for t in st.session_state.open_tabs if t[0] == notebook_id), None)
        if existing:
            st.session_state.active_tab = notebook_id
        else:
            try:
                config = self.notebook_session.load_notebook(str(notebook_path))
                st.session_state.open_tabs.append((notebook_id, notebook_path, config))
                st.session_state.active_tab = notebook_id
                with open(notebook_path, 'r') as f:
                    st.session_state.yaml_content[notebook_id] = f.read()
            except Exception as e:
                st.error(f"Error: {e}")
        st.rerun()

    def _close_tab(self, notebook_id: str):
        st.session_state.open_tabs = [t for t in st.session_state.open_tabs if t[0] != notebook_id]
        if st.session_state.active_tab == notebook_id:
            st.session_state.active_tab = st.session_state.open_tabs[-1][0] if st.session_state.open_tabs else None
        st.rerun()

    def _create_new_notebook(self):
        """Create a new notebook."""
        # Use a dialog or form for creation
        if 'show_create_dialog' not in st.session_state:
            st.session_state.show_create_dialog = True

        if st.session_state.show_create_dialog:
            with st.form("create_notebook_form"):
                st.subheader("Create New Notebook")
                notebook_name = st.text_input("Notebook Name", placeholder="my_analysis")
                folder = st.text_input("Folder (optional)", placeholder="Leave empty for root")

                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("Create")
                with col2:
                    cancel = st.form_submit_button("Cancel")

                if submit and notebook_name:
                    # Create template notebook
                    template = """notebook:
  title: "{title}"
  description: "Description"

variables:
  time:
    type: date_range
    display_name: "Time Period"
    default:
      start: "2024-01-01"
      end: "2024-01-31"

dimensions: []
measures: []
exhibits: []

layout:
  - title: "Section 1"
    columns: 1
    exhibits: []
"""
                    content = template.format(title=notebook_name.replace('_', ' ').title())

                    # Determine path
                    if folder:
                        target_dir = self.notebooks_root / folder
                        target_dir.mkdir(parents=True, exist_ok=True)
                    else:
                        target_dir = self.notebooks_root

                    target_path = target_dir / f"{notebook_name}.yaml"

                    # Check if exists
                    if target_path.exists():
                        st.error(f"Notebook {notebook_name} already exists")
                    else:
                        target_path.write_text(content)
                        st.success(f"Created {notebook_name}")
                        st.session_state.show_create_dialog = False
                        st.rerun()

                if cancel:
                    st.session_state.show_create_dialog = False
                    st.rerun()

    def _create_new_folder(self):
        """Create a new folder."""
        if 'show_folder_dialog' not in st.session_state:
            st.session_state.show_folder_dialog = True

        if st.session_state.show_folder_dialog:
            with st.form("create_folder_form"):
                st.subheader("Create New Folder")
                folder_name = st.text_input("Folder Name", placeholder="my_folder")

                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("Create")
                with col2:
                    cancel = st.form_submit_button("Cancel")

                if submit and folder_name:
                    folder_path = self.notebooks_root / folder_name
                    if folder_path.exists():
                        st.error(f"Folder {folder_name} already exists")
                    else:
                        folder_path.mkdir(parents=True, exist_ok=True)
                        st.success(f"Created folder {folder_name}")
                        st.session_state.show_folder_dialog = False
                        st.rerun()

                if cancel:
                    st.session_state.show_folder_dialog = False
                    st.rerun()

    def _rename_notebook(self, path: Path):
        """Rename a notebook."""
        notebook_id = str(path.relative_to(self.notebooks_root))

        if f'show_rename_dialog_{notebook_id}' not in st.session_state:
            st.session_state[f'show_rename_dialog_{notebook_id}'] = True

        if st.session_state.get(f'show_rename_dialog_{notebook_id}'):
            with st.form(f"rename_form_{notebook_id}"):
                st.subheader(f"Rename {path.stem}")
                new_name = st.text_input("New Name", value=path.stem)

                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("Rename")
                with col2:
                    cancel = st.form_submit_button("Cancel")

                if submit and new_name and new_name != path.stem:
                    new_path = path.parent / f"{new_name}.yaml"
                    if new_path.exists():
                        st.error(f"Notebook {new_name} already exists")
                    else:
                        path.rename(new_path)

                        # Update open tabs
                        for i, tab in enumerate(st.session_state.open_tabs):
                            if tab[1] == path:
                                st.session_state.open_tabs[i] = (
                                    str(new_path.relative_to(self.notebooks_root)),
                                    new_path,
                                    tab[2]
                                )

                        st.success(f"Renamed to {new_name}")
                        st.session_state[f'show_rename_dialog_{notebook_id}'] = False
                        st.rerun()

                if cancel:
                    st.session_state[f'show_rename_dialog_{notebook_id}'] = False
                    st.rerun()

    def _delete_notebook(self, path: Path):
        """Delete a notebook with confirmation."""
        notebook_id = str(path.relative_to(self.notebooks_root))

        if f'show_delete_dialog_{notebook_id}' not in st.session_state:
            st.session_state[f'show_delete_dialog_{notebook_id}'] = True

        if st.session_state.get(f'show_delete_dialog_{notebook_id}'):
            with st.form(f"delete_form_{notebook_id}"):
                st.subheader(f"Delete {path.stem}?")
                st.warning("This action cannot be undone.")

                col1, col2 = st.columns(2)
                with col1:
                    confirm = st.form_submit_button("Delete", type="primary")
                with col2:
                    cancel = st.form_submit_button("Cancel")

                if confirm:
                    # Close tab if open
                    st.session_state.open_tabs = [
                        tab for tab in st.session_state.open_tabs if tab[1] != path
                    ]

                    # Update active tab
                    if st.session_state.active_tab == notebook_id:
                        st.session_state.active_tab = (
                            st.session_state.open_tabs[-1][0] if st.session_state.open_tabs else None
                        )

                    # Delete file
                    path.unlink()
                    st.success(f"Deleted {path.stem}")
                    st.session_state[f'show_delete_dialog_{notebook_id}'] = False
                    st.rerun()

                if cancel:
                    st.session_state[f'show_delete_dialog_{notebook_id}'] = False
                    st.rerun()

    def _save_notebook(self, notebook_id: str, path: Path, content: str):
        try:
            yaml.safe_load(content)
            with open(path, 'w') as f:
                f.write(content)
            st.success("Saved!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")


def main():
    """Main entry point."""
    app = NotebookPlatform()
    app.run()


if __name__ == "__main__":
    main()
