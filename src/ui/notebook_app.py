"""
Streamlit notebook viewer application.

Renders YAML-based financial modeling notebooks with interactive filters and exhibits.
"""

import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestration.context import RepoContext
from src.model.api.session import ModelSession
from src.notebook.api.notebook_session import NotebookSession
from src.notebook.schema import VariableType, ExhibitType


# Configure page
st.set_page_config(
    page_title="Financial Notebook",
    layout="wide",
    initial_sidebar_state="expanded",
)


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
    """Streamlit notebook viewer application."""

    def __init__(self):
        """Initialize application."""
        self.ctx = get_repo_context()
        self.model_session = get_model_session(self.ctx)
        self.notebook_session = get_notebook_session(
            self.model_session,
            self.ctx,
        )

    def run(self):
        """Run the application."""
        st.title("📊 Financial Modeling Notebook")

        # Sidebar: Notebook selector
        with st.sidebar:
            self._render_notebook_selector()

            st.divider()

            # Render filters if notebook is loaded
            if 'notebook_loaded' in st.session_state:
                self._render_filters()

        # Main content
        if 'notebook_loaded' in st.session_state:
            self._render_notebook()
        else:
            self._render_welcome()

    def _render_notebook_selector(self):
        """Render notebook selector."""
        st.header("Select Notebook")

        # Find available notebooks
        notebooks_dir = self.ctx.repo / "configs" / "notebooks"
        notebooks_dir.mkdir(parents=True, exist_ok=True)

        notebook_files = list(notebooks_dir.glob("*.yaml"))

        if not notebook_files:
            st.warning("No notebooks found in configs/notebooks/")
            st.info("Create a YAML notebook file to get started.")
            return

        # Notebook selector
        notebook_names = [f.stem for f in notebook_files]
        selected = st.selectbox(
            "Notebook",
            notebook_names,
            key="selected_notebook",
        )

        if st.button("Load Notebook", type="primary"):
            self._load_notebook(notebooks_dir / f"{selected}.yaml")

    def _load_notebook(self, notebook_path: Path):
        """Load a notebook."""
        try:
            with st.spinner("Loading notebook..."):
                notebook_config = self.notebook_session.load_notebook(str(notebook_path))

                st.session_state['notebook_loaded'] = True
                st.session_state['notebook_config'] = notebook_config

                st.success(f"Loaded: {notebook_config.notebook.title}")
                st.rerun()

        except Exception as e:
            st.error(f"Error loading notebook: {str(e)}")
            st.exception(e)

    def _render_filters(self):
        """Render filter controls."""
        st.header("Filters")

        notebook_config = st.session_state.get('notebook_config')
        if not notebook_config:
            return

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
        # Get current filter value from context (already resolved)
        filter_context = self.notebook_session.get_filter_context()
        current_value = filter_context.get(var_id)

        if current_value and isinstance(current_value, dict):
            default_start = current_value['start']
            default_end = current_value['end']
            # Convert to date if datetime
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
        # Get options
        options = variable.options if variable.options else variable.default

        if not options:
            # Try to load from dimension
            try:
                options = self.notebook_session.get_dimension_values(var_id)
            except:
                options = []

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

    def _render_notebook(self):
        """Render the notebook content."""
        notebook_config = st.session_state.get('notebook_config')
        if not notebook_config:
            return

        # Notebook header
        st.header(notebook_config.notebook.title)
        if notebook_config.notebook.description:
            st.markdown(notebook_config.notebook.description)

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
        notebook_config = st.session_state['notebook_config']

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
                        st.metric(label=measure_id, value=f"{value:,.2f}")
                    else:
                        st.metric(label=measure_id, value="N/A")

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
        st.info("👈 Select a notebook from the sidebar to get started")

        st.markdown("""
        ## Financial Modeling Notebooks

        This application renders YAML-based financial modeling notebooks with:

        - **📊 Dynamic Exhibits**: Interactive charts, tables, and metrics
        - **🎛️ Flexible Filters**: Notebook-level and exhibit-specific filtering
        - **📈 Complex Measures**: Weighted averages, window functions, custom calculations
        - **🔗 Graph-based Data**: Query backend models and create relational frameworks

        ### Getting Started

        1. Create a YAML notebook file in `configs/notebooks/`
        2. Define your models, dimensions, measures, and exhibits
        3. Select the notebook from the sidebar

        See the documentation for notebook schema details.
        """)


def main():
    """Main entry point."""
    app = NotebookApp()
    app.run()


if __name__ == "__main__":
    main()
