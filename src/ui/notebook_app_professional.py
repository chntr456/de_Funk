"""
Professional notebook application with improved UX.

Features:
- Clean, minimalist design
- Dual-panel layout (Explorer + Filters)
- Directory tree navigation
- Day/night theme
- Notebook management
"""

import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yaml

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestration.context import RepoContext
from src.model.api.session import ModelSession
from src.notebook.api.notebook_session import NotebookSession
from src.notebook.schema import VariableType, ExhibitType


# Configure page
st.set_page_config(
    page_title="Notebook Platform",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def apply_theme():
    """Apply professional theme styling."""
    theme = st.session_state.get('theme', 'light')

    if theme == 'dark':
        bg_color = '#0e1117'
        secondary_bg = '#262730'
        text_color = '#fafafa'
        border_color = '#3a3d45'
        accent_color = '#4d9ef6'
    else:
        bg_color = '#ffffff'
        secondary_bg = '#f0f2f6'
        text_color = '#31333F'
        border_color = '#e0e0e0'
        accent_color = '#0068c9'

    st.markdown(f"""
    <style>
        /* Clean, minimal professional styling */
        .main {{
            background-color: {bg_color};
        }}

        /* Remove default padding */
        .block-container {{
            padding-top: 2rem;
            padding-bottom: 0rem;
        }}

        /* Sidebar styling */
        .sidebar-panel {{
            background-color: {secondary_bg};
            padding: 1rem;
            border-radius: 0.5rem;
            height: 85vh;
            overflow-y: auto;
        }}

        /* Tree item */
        .tree-item {{
            padding: 0.5rem;
            margin: 0.25rem 0;
            border-radius: 0.25rem;
            cursor: pointer;
            transition: background-color 0.2s;
        }}

        .tree-item:hover {{
            background-color: {border_color};
        }}

        /* Section headers */
        .section-header {{
            font-size: 1.2rem;
            font-weight: 600;
            margin: 2rem 0 1rem 0;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid {accent_color};
        }}

        /* Metric card */
        .metric-card {{
            background-color: {secondary_bg};
            padding: 1.5rem;
            border-radius: 0.5rem;
            text-align: center;
            border-left: 4px solid {accent_color};
        }}

        .metric-value {{
            font-size: 2rem;
            font-weight: 700;
            color: {accent_color};
        }}

        .metric-label {{
            font-size: 0.9rem;
            color: {text_color};
            opacity: 0.7;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        /* Hide Streamlit branding */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)


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


class NotebookApp:
    """Professional notebook application."""

    def __init__(self):
        """Initialize application."""
        if 'theme' not in st.session_state:
            st.session_state.theme = 'light'

        apply_theme()

        self.ctx = get_repo_context()
        self.model_session = get_model_session(self.ctx)
        self.notebook_session = get_notebook_session(
            self.model_session,
            self.ctx,
        )
        self.notebooks_root = self.ctx.repo / "configs" / "notebooks"

    def run(self):
        """Run the application."""
        # Header with theme toggle
        col1, col2 = st.columns([6, 1])
        with col1:
            st.title("📊 Notebook Platform")
        with col2:
            icon = "🌙" if st.session_state.theme == 'light' else "☀️"
            if st.button(icon, help="Toggle theme"):
                st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
                st.rerun()

        st.divider()

        # Three-column layout
        left_col, main_col, right_col = st.columns([2, 6, 2])

        with left_col:
            self._render_explorer()

        with main_col:
            self._render_main_content()

        with right_col:
            self._render_filters()

    def _render_explorer(self):
        """Render notebook explorer."""
        st.markdown('<div class="sidebar-panel">', unsafe_allow_html=True)
        st.markdown("### 📁 Notebooks")

        # Scan notebooks
        if not self.notebooks_root.exists():
            self.notebooks_root.mkdir(parents=True, exist_ok=True)

        notebooks = sorted(self.notebooks_root.rglob("*.yaml"))

        if not notebooks:
            st.info("No notebooks found")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        # Group by folder
        by_folder = {}
        for nb_path in notebooks:
            rel_path = nb_path.relative_to(self.notebooks_root)
            folder = str(rel_path.parent) if rel_path.parent != Path('.') else "📄 Root"
            if folder not in by_folder:
                by_folder[folder] = []
            by_folder[folder].append(nb_path)

        # Render tree
        for folder, files in sorted(by_folder.items()):
            if folder != "📄 Root":
                st.markdown(f"**📂 {folder}**")

            for nb_path in sorted(files):
                if st.button(
                    f"  📄 {nb_path.stem}",
                    key=f"nb_{nb_path}",
                    use_container_width=True
                ):
                    self._load_notebook(nb_path)

        st.markdown('</div>', unsafe_allow_html=True)

    def _render_filters(self):
        """Render filter controls."""
        st.markdown('<div class="sidebar-panel">', unsafe_allow_html=True)
        st.markdown("### 🎛️ Filters")

        if 'notebook_loaded' not in st.session_state:
            st.info("Load a notebook to see filters")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        notebook_config = st.session_state.get('notebook_config')
        if not notebook_config:
            st.markdown('</div>', unsafe_allow_html=True)
            return

        filter_context = self.notebook_session.get_filter_context()
        filter_values = {}

        # Render each variable
        for var_id, variable in notebook_config.variables.items():
            st.markdown(f"**{variable.display_name}**")

            if variable.type == VariableType.DATE_RANGE:
                filter_values[var_id] = self._render_date_filter(var_id, variable)

            elif variable.type == VariableType.MULTI_SELECT:
                filter_values[var_id] = self._render_multi_select(var_id, variable)

            elif variable.type == VariableType.NUMBER:
                filter_values[var_id] = self._render_number_filter(var_id, variable)

        if filter_values:
            self.notebook_session.update_filters(filter_values)

        st.markdown('</div>', unsafe_allow_html=True)

    def _render_date_filter(self, var_id: str, variable) -> Dict[str, datetime]:
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

        start = st.date_input(
            "From",
            value=default_start,
            key=f"filter_{var_id}_start",
            label_visibility="collapsed"
        )
        end = st.date_input(
            "To",
            value=default_end,
            key=f"filter_{var_id}_end",
            label_visibility="collapsed"
        )

        return {
            'start': datetime.combine(start, datetime.min.time()),
            'end': datetime.combine(end, datetime.min.time()),
        }

    def _render_multi_select(self, var_id: str, variable) -> List[Any]:
        """Render multi-select filter."""
        options = variable.default if variable.default else []
        default = variable.default if variable.default else []

        return st.multiselect(
            "Select",
            options=options,
            default=default,
            key=f"filter_{var_id}",
            label_visibility="collapsed"
        )

    def _render_number_filter(self, var_id: str, variable) -> float:
        """Render number filter."""
        default = variable.default if variable.default is not None else 0.0

        return st.number_input(
            "Value",
            value=float(default),
            key=f"filter_{var_id}",
            label_visibility="collapsed"
        )

    def _render_main_content(self):
        """Render main content area."""
        if 'notebook_loaded' not in st.session_state:
            self._render_welcome()
            return

        notebook_config = st.session_state.get('notebook_config')
        if not notebook_config:
            return

        # Notebook title
        st.header(notebook_config.notebook.title)
        if notebook_config.notebook.description:
            st.caption(notebook_config.notebook.description)

        st.divider()

        # Render sections
        for layout_item in notebook_config.layout:
            if hasattr(layout_item, 'section'):
                section = layout_item.section
                self._render_section(section)

    def _render_section(self, section):
        """Render a layout section."""
        if section.title:
            st.markdown(f'<div class="section-header">{section.title}</div>', unsafe_allow_html=True)

        # Create columns if specified
        if hasattr(section, 'columns') and section.columns > 1:
            cols = st.columns(section.columns)
            for i, exhibit_id in enumerate(section.exhibits):
                with cols[i % section.columns]:
                    self._render_exhibit(exhibit_id)
        else:
            for exhibit_id in section.exhibits:
                self._render_exhibit(exhibit_id)

    def _render_exhibit(self, exhibit_id: str):
        """Render an exhibit."""
        notebook_config = st.session_state['notebook_config']

        # Find exhibit
        exhibit = next((ex for ex in notebook_config.exhibits if ex.id == exhibit_id), None)

        if not exhibit:
            st.error(f"Exhibit not found: {exhibit_id}")
            return

        # Get data
        try:
            with st.spinner(f"Loading {exhibit.title}..."):
                df = self.notebook_session.get_exhibit_data(exhibit_id)
                pdf = df.toPandas()

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
                st.warning(f"Unsupported exhibit type: {exhibit.type}")

        except Exception as e:
            st.error(f"Error rendering {exhibit_id}: {str(e)}")
            with st.expander("Show details"):
                st.exception(e)

    def _render_metric_cards(self, exhibit, pdf: pd.DataFrame):
        """Render metric cards."""
        st.subheader(exhibit.title)
        if exhibit.description:
            st.caption(exhibit.description)

        if not hasattr(exhibit, 'metrics') or not exhibit.metrics:
            st.warning("No metrics defined")
            return

        # Calculate columns based on number of metrics
        num_metrics = len(exhibit.metrics)
        cols = st.columns(num_metrics)

        for i, metric_config in enumerate(exhibit.metrics):
            with cols[i]:
                measure_id = metric_config.measure
                if measure_id in pdf.columns and len(pdf) > 0:
                    value = pdf[measure_id].iloc[0]

                    # Format value
                    if pd.isna(value):
                        formatted = "N/A"
                    elif value >= 1e9:
                        formatted = f"${value/1e9:.2f}B"
                    elif value >= 1e6:
                        formatted = f"${value/1e6:.2f}M"
                    elif value >= 1e3:
                        formatted = f"${value/1e3:.2f}K"
                    else:
                        formatted = f"${value:,.2f}"

                    # Use custom card HTML
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">{measure_id.replace('_', ' ').title()}</div>
                        <div class="metric-value">{formatted}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.metric(label=measure_id, value="N/A")

    def _render_line_chart(self, exhibit, pdf: pd.DataFrame):
        """Render line chart."""
        st.subheader(exhibit.title)
        if exhibit.description:
            st.caption(exhibit.description)

        if not hasattr(exhibit, 'x_axis') or not hasattr(exhibit, 'y_axis'):
            st.warning("Chart configuration incomplete")
            return

        x_col = exhibit.x_axis.dimension
        y_cols = exhibit.y_axis.measures if hasattr(exhibit.y_axis, 'measures') else [exhibit.y_axis.measure]

        fig = px.line(
            pdf,
            x=x_col,
            y=y_cols,
            color=exhibit.color_by if hasattr(exhibit, 'color_by') and exhibit.color_by else None,
            labels={x_col: exhibit.x_axis.label if hasattr(exhibit.x_axis, 'label') else x_col},
        )

        # Theme-aware styling
        if st.session_state.theme == 'dark':
            fig.update_layout(
                plot_bgcolor='#262730',
                paper_bgcolor='#262730',
                font_color='#fafafa'
            )

        st.plotly_chart(fig, use_container_width=True)

    def _render_bar_chart(self, exhibit, pdf: pd.DataFrame):
        """Render bar chart."""
        st.subheader(exhibit.title)
        if exhibit.description:
            st.caption(exhibit.description)

        if not hasattr(exhibit, 'x_axis') or not hasattr(exhibit, 'y_axis'):
            st.warning("Chart configuration incomplete")
            return

        x_col = exhibit.x_axis.dimension
        y_cols = exhibit.y_axis.measures if hasattr(exhibit.y_axis, 'measures') else [exhibit.y_axis.measure]

        fig = px.bar(
            pdf,
            x=x_col,
            y=y_cols[0] if y_cols else None,
            color=exhibit.color_by if hasattr(exhibit, 'color_by') and exhibit.color_by else None,
        )

        # Theme-aware styling
        if st.session_state.theme == 'dark':
            fig.update_layout(
                plot_bgcolor='#262730',
                paper_bgcolor='#262730',
                font_color='#fafafa'
            )

        st.plotly_chart(fig, use_container_width=True)

    def _render_data_table(self, exhibit, pdf: pd.DataFrame):
        """Render data table."""
        st.subheader(exhibit.title)
        if exhibit.description:
            st.caption(exhibit.description)

        st.dataframe(
            pdf,
            use_container_width=True,
            hide_index=True,
        )

        # Download button
        if hasattr(exhibit, 'download') and exhibit.download:
            csv = pdf.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"{exhibit.id}.csv",
                mime="text/csv",
            )

    def _render_welcome(self):
        """Render welcome screen."""
        st.markdown("""
        ## Welcome to the Notebook Platform

        ### Professional Financial Modeling Environment

        **Get Started:**
        1. Select a notebook from the left sidebar
        2. Adjust filters in the right sidebar
        3. Explore your data with interactive exhibits

        **Features:**
        - 📊 Dynamic exhibits with real-time filtering
        - 🎨 Clean, professional design with dark/light themes
        - 📁 Organized notebook library
        - 🚀 High-performance data processing

        ---

        *Select a notebook from the Explorer to begin*
        """)

    def _load_notebook(self, notebook_path: Path):
        """Load a notebook."""
        try:
            with st.spinner("Loading notebook..."):
                notebook_config = self.notebook_session.load_notebook(str(notebook_path))

                st.session_state['notebook_loaded'] = True
                st.session_state['notebook_config'] = notebook_config

                st.success(f"✓ Loaded: {notebook_config.notebook.title}")
                st.rerun()

        except Exception as e:
            st.error(f"Error loading notebook: {str(e)}")
            st.exception(e)


def main():
    """Main entry point."""
    app = NotebookApp()
    app.run()


if __name__ == "__main__":
    main()
