"""
Professional notebook application with vault-style navigation and themes.

Features:
- Directory tree navigation
- Multiple notebook tabs
- Toggle between YAML edit and rendered view
- Nested scrollable filters
- Day/night professional themes
"""

import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import plotly.express as px
import yaml

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestration.context import RepoContext
from src.core import ModelRegistry
from src.notebook.api.notebook_session import NotebookSession
from src.notebook.schema import VariableType, ExhibitType


# Configure page
st.set_page_config(
    page_title="Notebook Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_professional_theme():
    """Apply professional theme styling."""
    theme = st.session_state.get('theme', 'light')

    if theme == 'dark':
        colors = {
            'bg': '#0E1117',
            'sidebar_bg': '#262730',
            'card_bg': '#1E2130',
            'text': '#FAFAFA',
            'text_muted': '#9CA3AF',
            'border': '#3A3D45',
            'accent': '#4D9EF6',
            'accent_hover': '#3B82F6',
        }
    else:
        colors = {
            'bg': '#FFFFFF',
            'sidebar_bg': '#F0F2F6',
            'card_bg': '#F8F9FA',
            'text': '#262730',
            'text_muted': '#6C757D',
            'border': '#E0E0E0',
            'accent': '#0068C9',
            'accent_hover': '#0056A3',
        }

    st.markdown(f"""
    <style>
        /* Main background */
        .main {{
            background-color: {colors['bg']};
        }}

        /* Sidebar styling */
        section[data-testid="stSidebar"] {{
            background-color: {colors['sidebar_bg']};
        }}

        section[data-testid="stSidebar"] .block-container {{
            padding-top: 2rem;
        }}

        /* Headers */
        .main h1, .main h2, .main h3 {{
            color: {colors['text']};
        }}

        /* Section dividers */
        hr {{
            border-color: {colors['border']};
        }}

        /* Metric cards */
        div[data-testid="stMetricValue"] {{
            font-size: 2.5rem;
            font-weight: 700;
            color: {colors['accent']};
        }}

        div[data-testid="stMetricLabel"] {{
            font-size: 0.9rem;
            color: {colors['text_muted']};
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        /* Buttons */
        .stButton > button {{
            border-radius: 0.375rem;
            font-weight: 500;
            transition: all 0.2s;
        }}

        .stButton > button[kind="primary"] {{
            background-color: {colors['accent']};
            border-color: {colors['accent']};
        }}

        .stButton > button[kind="primary"]:hover {{
            background-color: {colors['accent_hover']};
            border-color: {colors['accent_hover']};
        }}

        /* Tab bar styling */
        .tab-container {{
            background-color: {colors['card_bg']};
            padding: 0.5rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
        }}

        /* Code editor */
        .stCodeBlock {{
            background-color: {colors['card_bg']};
        }}

        /* Hide Streamlit branding */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}

        /* Plotly charts background */
        .js-plotly-plot .plotly {{
            background-color: {colors['card_bg']} !important;
        }}
    </style>
    """, unsafe_allow_html=True)


@st.cache_resource
def get_repo_context():
    """
    Get repository context configured for notebook UI.

    Uses DuckDB for 10-100x faster queries compared to Spark.
    Perfect for interactive notebook rendering.
    """
    return RepoContext.from_repo_root(connection_type="duckdb")


@st.cache_resource
def get_model_registry(_ctx):
    """Get model registry (cached)."""
    models_dir = _ctx.repo / "configs" / "models"
    return ModelRegistry(models_dir)


@st.cache_resource
def get_notebook_session(_ctx, _model_registry):
    """
    Get notebook session with DuckDB backend (cached).

    This session uses StorageService with DuckDB for instant queries.
    """
    return NotebookSession(_ctx.connection, _model_registry, _ctx.repo)


# Session state initialization
if 'open_tabs' not in st.session_state:
    st.session_state.open_tabs = []  # List of (notebook_id, notebook_path, notebook_config)

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = None

if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = {}  # Dict of notebook_id -> bool

if 'yaml_content' not in st.session_state:
    st.session_state.yaml_content = {}  # Dict of notebook_id -> yaml string

if 'theme' not in st.session_state:
    st.session_state.theme = 'light'  # 'light' or 'dark'

# Apply theme
apply_professional_theme()


class NotebookVaultApp:
    """Enhanced notebook application with vault-style navigation."""

    def __init__(self):
        """Initialize application with DuckDB backend."""
        self.ctx = get_repo_context()
        self.model_registry = get_model_registry(self.ctx)
        self.notebook_session = get_notebook_session(self.ctx, self.model_registry)
        self.notebooks_root = self.ctx.repo / "configs" / "notebooks"
        self.notebooks_root.mkdir(parents=True, exist_ok=True)

    def run(self):
        """Run the application."""
        # Theme toggle in top-right
        col1, col2 = st.columns([0.95, 0.05])
        with col2:
            theme_icon = "🌙" if st.session_state.theme == 'light' else "☀️"
            if st.button(theme_icon, help="Toggle theme", key="theme_toggle"):
                st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
                st.rerun()

        # Sidebar: Directory tree + filters
        with st.sidebar:
            self._render_directory_tree()

            # Show filters if a notebook is active
            if st.session_state.active_tab:
                st.divider()
                self._render_filters_section()

        # Main content: Tabs
        self._render_main_content()

    def _render_directory_tree(self):
        """Render directory tree navigation."""
        st.header("📚 Notebooks")

        # Scan for notebooks
        notebooks = self._scan_notebooks()

        if not notebooks:
            st.info("No notebooks found. Create a `.yaml` file in `configs/notebooks/`")
            return

        # Group by directory
        grouped = self._group_by_directory(notebooks)

        # Render tree
        for folder, files in sorted(grouped.items()):
            if folder == ".":
                # Root level files
                for file_path in sorted(files):
                    self._render_notebook_item(file_path)
            else:
                # Folder with files
                with st.expander(f"📁 {folder}", expanded=True):
                    for file_path in sorted(files):
                        self._render_notebook_item(file_path)

    def _scan_notebooks(self) -> List[Path]:
        """Scan for notebook YAML files."""
        return list(self.notebooks_root.rglob("*.yaml"))

    def _group_by_directory(self, notebooks: List[Path]) -> Dict[str, List[Path]]:
        """Group notebooks by their parent directory."""
        grouped = {}
        for notebook_path in notebooks:
            # Get relative path from notebooks root
            rel_path = notebook_path.relative_to(self.notebooks_root)

            if len(rel_path.parts) == 1:
                # Root level
                folder = "."
            else:
                # In a subfolder
                folder = rel_path.parts[0]

            if folder not in grouped:
                grouped[folder] = []
            grouped[folder].append(notebook_path)

        return grouped

    def _render_notebook_item(self, notebook_path: Path):
        """Render a single notebook item in the tree."""
        notebook_id = str(notebook_path.relative_to(self.notebooks_root))
        notebook_name = notebook_path.stem

        # Check if already open
        is_open = any(tab[0] == notebook_id for tab in st.session_state.open_tabs)
        is_active = st.session_state.active_tab == notebook_id

        # Style based on state
        if is_active:
            icon = "📖"
            label = f"**{notebook_name}**"
        elif is_open:
            icon = "📄"
            label = f"*{notebook_name}*"
        else:
            icon = "📄"
            label = notebook_name

        # Click to open/activate
        if st.button(f"{icon} {label}", key=f"nav_{notebook_id}", use_container_width=True):
            self._open_notebook(notebook_id, notebook_path)

    def _open_notebook(self, notebook_id: str, notebook_path: Path):
        """Open a notebook (or switch to it if already open)."""
        # Check if already open
        existing_tab = next((tab for tab in st.session_state.open_tabs if tab[0] == notebook_id), None)

        if existing_tab:
            # Just switch to it
            st.session_state.active_tab = notebook_id
        else:
            # Load the notebook
            try:
                notebook_config = self.notebook_session.load_notebook(str(notebook_path))
                st.session_state.open_tabs.append((notebook_id, notebook_path, notebook_config))
                st.session_state.active_tab = notebook_id
                st.session_state.edit_mode[notebook_id] = False

                # Load YAML content for editing
                with open(notebook_path, 'r') as f:
                    st.session_state.yaml_content[notebook_id] = f.read()

            except Exception as e:
                st.error(f"Error loading notebook: {str(e)}")

        st.rerun()

    def _close_tab(self, notebook_id: str):
        """Close a notebook tab."""
        # Remove from open tabs
        st.session_state.open_tabs = [
            tab for tab in st.session_state.open_tabs if tab[0] != notebook_id
        ]

        # Clear edit mode
        if notebook_id in st.session_state.edit_mode:
            del st.session_state.edit_mode[notebook_id]

        # Clear YAML content
        if notebook_id in st.session_state.yaml_content:
            del st.session_state.yaml_content[notebook_id]

        # Switch active tab
        if st.session_state.active_tab == notebook_id:
            if st.session_state.open_tabs:
                st.session_state.active_tab = st.session_state.open_tabs[-1][0]
            else:
                st.session_state.active_tab = None

        st.rerun()

    def _render_filters_section(self):
        """Render the filters section in sidebar."""
        st.subheader("🎛️ Filters")

        # Get active notebook
        active_notebook = next(
            (tab for tab in st.session_state.open_tabs if tab[0] == st.session_state.active_tab),
            None
        )

        if not active_notebook:
            return

        notebook_id, notebook_path, notebook_config = active_notebook

        # Create a scrollable container for filters
        with st.container():
            filter_context = self.notebook_session.get_filter_context()
            filter_values = {}

            # Render each variable as a filter control
            for var_id, variable in notebook_config.variables.items():
                if variable.type == VariableType.DATE_RANGE:
                    filter_values[var_id] = self._render_date_range_filter(var_id, variable)

                elif variable.type == VariableType.MULTI_SELECT:
                    filter_values[var_id] = self._render_multi_select_filter(var_id, variable)

                elif variable.type == VariableType.SINGLE_SELECT:
                    filter_values[var_id] = self._render_single_select_filter(var_id, variable)

                elif variable.type == VariableType.NUMBER:
                    filter_values[var_id] = self._render_number_filter(var_id, variable)

                elif variable.type == VariableType.BOOLEAN:
                    filter_values[var_id] = self._render_boolean_filter(var_id, variable)

            # Update filter context
            if filter_values:
                self.notebook_session.update_filters(filter_values)

    def _render_date_range_filter(self, var_id: str, variable) -> Dict[str, datetime]:
        """Render date range filter."""
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

        start_date = st.date_input(
            f"{variable.display_name} (Start)",
            value=default_start,
            key=f"filter_{var_id}_start",
        )

        end_date = st.date_input(
            f"{variable.display_name} (End)",
            value=default_end,
            key=f"filter_{var_id}_end",
        )

        return {
            'start': datetime.combine(start_date, datetime.min.time()),
            'end': datetime.combine(end_date, datetime.min.time()),
        }

    def _render_multi_select_filter(self, var_id: str, variable) -> List[Any]:
        """Render multi-select filter."""
        if variable.options:
            options = variable.options
        elif not variable.source:
            options = variable.default if variable.default else []
        else:
            options = variable.default if variable.default else []

        default = variable.default if variable.default else []

        return st.multiselect(
            variable.display_name,
            options=options,
            default=default,
            key=f"filter_{var_id}",
            help=variable.description,
        )

    def _render_single_select_filter(self, var_id: str, variable) -> Any:
        """Render single-select filter."""
        options = variable.options if variable.options else []
        default = variable.default

        return st.selectbox(
            variable.display_name,
            options=options,
            index=options.index(default) if default in options else 0,
            key=f"filter_{var_id}",
            help=variable.description,
        )

    def _render_number_filter(self, var_id: str, variable) -> float:
        """Render number filter."""
        default = variable.default if variable.default is not None else 0.0

        return st.number_input(
            variable.display_name,
            value=float(default),
            key=f"filter_{var_id}",
            help=variable.description,
        )

    def _render_boolean_filter(self, var_id: str, variable) -> bool:
        """Render boolean filter."""
        default = variable.default if variable.default is not None else False

        return st.checkbox(
            variable.display_name,
            value=default,
            key=f"filter_{var_id}",
            help=variable.description,
        )

    def _render_main_content(self):
        """Render main content area with tabs."""
        if not st.session_state.open_tabs:
            self._render_welcome()
            return

        # Render tabs
        tab_names = [f"{tab[2].notebook.title}" for tab in st.session_state.open_tabs]

        # Create tabs with close buttons
        cols = st.columns([0.9, 0.1] * len(st.session_state.open_tabs))

        for i, (notebook_id, notebook_path, notebook_config) in enumerate(st.session_state.open_tabs):
            with cols[i * 2]:
                is_active = st.session_state.active_tab == notebook_id
                if st.button(
                    notebook_config.notebook.title,
                    key=f"tab_{notebook_id}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.active_tab = notebook_id
                    st.rerun()

            with cols[i * 2 + 1]:
                if st.button("✕", key=f"close_{notebook_id}"):
                    self._close_tab(notebook_id)

        st.divider()

        # Render active notebook
        active_notebook = next(
            (tab for tab in st.session_state.open_tabs if tab[0] == st.session_state.active_tab),
            None
        )

        if active_notebook:
            self._render_notebook_content(active_notebook)

    def _render_notebook_content(self, notebook_tuple):
        """Render the content of a notebook."""
        notebook_id, notebook_path, notebook_config = notebook_tuple

        # Toggle between edit and view mode
        col1, col2 = st.columns([0.1, 0.9])

        with col1:
            edit_mode = st.session_state.edit_mode.get(notebook_id, False)

            if st.button("📝 Edit" if not edit_mode else "📊 View", key=f"toggle_{notebook_id}"):
                st.session_state.edit_mode[notebook_id] = not edit_mode
                st.rerun()

        with col2:
            st.title(notebook_config.notebook.title)
            if notebook_config.notebook.description:
                st.caption(notebook_config.notebook.description)

        st.divider()

        # Render based on mode
        if st.session_state.edit_mode.get(notebook_id, False):
            self._render_yaml_editor(notebook_id, notebook_path)
        else:
            self._render_notebook_exhibits(notebook_id, notebook_config)

    def _render_yaml_editor(self, notebook_id: str, notebook_path: Path):
        """Render YAML editor."""
        st.subheader("📝 Edit Notebook YAML")

        # Get current YAML content
        yaml_content = st.session_state.yaml_content.get(notebook_id, "")

        # Text area for editing
        edited_content = st.text_area(
            "YAML Content",
            value=yaml_content,
            height=600,
            key=f"yaml_editor_{notebook_id}",
        )

        # Save button
        col1, col2, col3 = st.columns([0.2, 0.2, 0.6])

        with col1:
            if st.button("💾 Save", key=f"save_{notebook_id}"):
                try:
                    # Validate YAML
                    yaml.safe_load(edited_content)

                    # Save to file
                    with open(notebook_path, 'w') as f:
                        f.write(edited_content)

                    # Update session state
                    st.session_state.yaml_content[notebook_id] = edited_content

                    # Reload notebook
                    notebook_config = self.notebook_session.load_notebook(str(notebook_path))

                    # Update open tab
                    for i, tab in enumerate(st.session_state.open_tabs):
                        if tab[0] == notebook_id:
                            st.session_state.open_tabs[i] = (notebook_id, notebook_path, notebook_config)
                            break

                    st.success("✅ Notebook saved and reloaded!")

                except yaml.YAMLError as e:
                    st.error(f"❌ Invalid YAML: {str(e)}")
                except Exception as e:
                    st.error(f"❌ Error saving: {str(e)}")

        with col2:
            if st.button("🔄 Reload", key=f"reload_{notebook_id}"):
                with open(notebook_path, 'r') as f:
                    st.session_state.yaml_content[notebook_id] = f.read()
                st.rerun()

        # Preview
        st.subheader("📋 YAML Preview")
        st.code(edited_content, language="yaml")

    def _render_notebook_exhibits(self, notebook_id: str, notebook_config):
        """Render notebook exhibits."""
        # Render layout sections
        for section in notebook_config.layout:
            self._render_section(section)

    def _render_section(self, section):
        """Render a layout section."""
        if section.title:
            st.subheader(section.title)
        if section.description:
            st.markdown(section.description)

        # Create columns if specified
        if section.columns > 1:
            cols = st.columns(section.columns)
            for i, exhibit_id in enumerate(section.exhibits):
                with cols[i % section.columns]:
                    self._render_exhibit(exhibit_id)
        else:
            for exhibit_id in section.exhibits:
                self._render_exhibit(exhibit_id)

    def _render_exhibit(self, exhibit_id: str):
        """Render an exhibit."""
        active_notebook = next(
            (tab for tab in st.session_state.open_tabs if tab[0] == st.session_state.active_tab),
            None
        )

        if not active_notebook:
            return

        notebook_id, notebook_path, notebook_config = active_notebook

        # Find exhibit
        exhibit = None
        for ex in notebook_config.exhibits:
            if ex.id == exhibit_id:
                exhibit = ex
                break

        if not exhibit:
            st.error(f"Exhibit not found: {exhibit_id}")
            return

        # Get data for exhibit
        try:
            with st.spinner(f"Loading {exhibit.title}..."):
                df = self.notebook_session.get_exhibit_data(exhibit_id)
                # Convert to pandas (works with both Spark DF and DuckDB relation)
                pdf = self.ctx.connection.to_pandas(df)

            # Render based on type
            if exhibit.type == ExhibitType.METRIC_CARDS:
                self._render_metric_cards(exhibit, pdf)
            elif exhibit.type == ExhibitType.LINE_CHART:
                self._render_line_chart(exhibit, pdf)
            elif exhibit.type == ExhibitType.BAR_CHART:
                self._render_bar_chart(exhibit, pdf)
            elif exhibit.type == ExhibitType.DATA_TABLE:
                self._render_data_table(exhibit, pdf)
            else:
                st.warning(f"Exhibit type not yet implemented: {exhibit.type}")

        except Exception as e:
            st.error(f"Error rendering exhibit: {str(e)}")
            with st.expander("Show details"):
                st.exception(e)

    def _render_metric_cards(self, exhibit, pdf: pd.DataFrame):
        """Render metric cards exhibit."""
        st.subheader(exhibit.title)

        if exhibit.metrics:
            cols = st.columns(len(exhibit.metrics))
            for i, metric_config in enumerate(exhibit.metrics):
                with cols[i]:
                    measure_id = metric_config.measure
                    if measure_id in pdf.columns:
                        value = pdf[measure_id].iloc[0] if len(pdf) > 0 else 0

                        # Format value based on magnitude
                        if pd.isna(value):
                            formatted = "N/A"
                        elif abs(value) >= 1e9:
                            formatted = f"${value/1e9:.2f}B"
                        elif abs(value) >= 1e6:
                            formatted = f"${value/1e6:.2f}M"
                        elif abs(value) >= 1e3:
                            formatted = f"${value/1e3:.2f}K"
                        else:
                            formatted = f"${value:,.2f}"

                        # Use Streamlit metric with delta styling
                        display_name = measure_id.replace('_', ' ').title()
                        st.metric(label=display_name, value=formatted)
                    else:
                        st.metric(label=measure_id.replace('_', ' ').title(), value="N/A")

    def _render_line_chart(self, exhibit, pdf: pd.DataFrame):
        """Render line chart exhibit."""
        st.subheader(exhibit.title)

        if exhibit.x_axis and exhibit.y_axis:
            x_col = exhibit.x_axis.dimension
            y_cols = exhibit.y_axis.measures or [exhibit.y_axis.measure]

            fig = px.line(
                pdf,
                x=x_col,
                y=y_cols,
                color=exhibit.color_by if exhibit.color_by else None,
                title=exhibit.title,
                labels={x_col: exhibit.x_axis.label or x_col},
            )

            # Apply theme to chart
            if st.session_state.theme == 'dark':
                fig.update_layout(
                    plot_bgcolor='#1E2130',
                    paper_bgcolor='#1E2130',
                    font_color='#FAFAFA',
                    xaxis=dict(gridcolor='#3A3D45'),
                    yaxis=dict(gridcolor='#3A3D45'),
                )
            else:
                fig.update_layout(
                    plot_bgcolor='#F8F9FA',
                    paper_bgcolor='#F8F9FA',
                )

            st.plotly_chart(fig, use_container_width=True)

    def _render_bar_chart(self, exhibit, pdf: pd.DataFrame):
        """Render bar chart exhibit."""
        st.subheader(exhibit.title)

        if exhibit.x_axis and exhibit.y_axis:
            x_col = exhibit.x_axis.dimension
            y_cols = exhibit.y_axis.measures or [exhibit.y_axis.measure]

            fig = px.bar(
                pdf,
                x=x_col,
                y=y_cols[0] if y_cols else None,
                color=exhibit.color_by if exhibit.color_by else None,
                title=exhibit.title,
            )

            # Apply theme to chart
            if st.session_state.theme == 'dark':
                fig.update_layout(
                    plot_bgcolor='#1E2130',
                    paper_bgcolor='#1E2130',
                    font_color='#FAFAFA',
                    xaxis=dict(gridcolor='#3A3D45'),
                    yaxis=dict(gridcolor='#3A3D45'),
                )
            else:
                fig.update_layout(
                    plot_bgcolor='#F8F9FA',
                    paper_bgcolor='#F8F9FA',
                )

            st.plotly_chart(fig, use_container_width=True)

    def _render_data_table(self, exhibit, pdf: pd.DataFrame):
        """Render data table exhibit."""
        st.subheader(exhibit.title)

        if exhibit.description:
            st.caption(exhibit.description)

        # Display dataframe
        st.dataframe(
            pdf,
            use_container_width=True,
            hide_index=True,
        )

        # Download button if enabled
        if exhibit.download:
            csv = pdf.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"{exhibit.id}.csv",
                mime="text/csv",
            )

    def _render_welcome(self):
        """Render welcome screen."""
        st.title("📊 Notebook Platform")

        st.markdown("""
        ## Professional Financial Modeling Environment

        ### Features

        **📁 Notebook Library**
        - Organized directory structure
        - Multi-tab interface
        - Quick navigation

        **📝 YAML Configuration**
        - Inline YAML editor
        - Real-time validation
        - Hot reload

        **🎛️ Dynamic Filtering**
        - Time-based filters
        - Multi-select dimensions
        - Context-aware filtering

        **📊 Interactive Exhibits**
        - Metric cards with smart formatting
        - Line and bar charts
        - Data tables with export
        - Theme-aware visualizations

        **🎨 Professional Design**
        - Light/dark themes
        - Clean, minimal interface
        - Consulting-grade appearance

        ---

        **Get Started:** Select a notebook from the sidebar →
        """)


def main():
    """Main entry point."""
    app = NotebookVaultApp()
    app.run()


if __name__ == "__main__":
    main()
