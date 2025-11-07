"""
Bar chart exhibit component with enhanced Plotly visualization.

Renders categorical comparisons as interactive bar charts with:
- Proper ordering by value or category
- Interactive hover tooltips
- Zoom and selection tools
- Theme support
- Dynamic measure selection with grouped bars
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from .measure_selector import render_measure_selector
from .dimension_selector import render_dimension_selector
from .click_events import enable_chart_selection


def render_bar_chart(exhibit, pdf: pd.DataFrame):
    """
    Render enhanced bar chart exhibit with proper ordering.

    Supports both single and multiple measures via:
    - Static y_axis.measure configuration
    - Static y_axis.measures list configuration
    - Dynamic measure_selector configuration

    Args:
        exhibit: Exhibit configuration with x_axis, y_axis, color_by, measure_selector
        pdf: Pandas DataFrame with data to plot
    """
    st.subheader(exhibit.title)

    if exhibit.description:
        st.caption(exhibit.description)

    if not exhibit.x_axis or not exhibit.y_axis:
        st.warning("Bar chart requires x_axis and y_axis configuration")
        return

    if pdf.empty:
        st.info("No data available for selected filters")
        return

    x_col = exhibit.x_axis.dimension

    # Determine which measures to plot
    y_measures = []

    # Check if dynamic measure selector is configured
    if hasattr(exhibit, 'measure_selector') and exhibit.measure_selector:
        # Render measure selector and get selected measures
        selected_measures = render_measure_selector(
            exhibit_id=exhibit.id,
            measure_selector_config=exhibit.measure_selector,
            available_columns=pdf.columns.tolist()
        )
        y_measures = selected_measures

        # Add a divider
        st.markdown("---")

    # Otherwise use y_axis configuration
    elif hasattr(exhibit.y_axis, 'measures') and exhibit.y_axis.measures:
        y_measures = exhibit.y_axis.measures
    elif hasattr(exhibit.y_axis, 'measure') and exhibit.y_axis.measure:
        y_measures = [exhibit.y_axis.measure]
    else:
        st.warning("No measures configured for bar chart")
        return

    # Filter measures to only those present in the dataframe
    y_measures = [m for m in y_measures if m in pdf.columns]

    if not y_measures:
        st.warning("No valid measures found in data")
        return

    # Check if dynamic dimension selector is configured
    color_dimension = None
    if hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector:
        # Render dimension selector and get selected dimension
        selected_dimension = render_dimension_selector(
            exhibit_id=exhibit.id,
            dimension_selector_config=exhibit.dimension_selector,
            available_columns=pdf.columns.tolist()
        )

        # Apply selected dimension based on applies_to setting
        if exhibit.dimension_selector.applies_to == "color":
            color_dimension = selected_dimension
        # Can extend to support "x" or "group_by" in the future

        # Add a divider
        st.markdown("---")
    else:
        # Use static color_by if no dimension selector
        color_dimension = exhibit.color_by if hasattr(exhibit, 'color_by') else None

    # Auto-detect color dimension if not specified
    # This fixes cross-sectional grouping - if ticker is in columns, use it by default
    if not color_dimension:
        # Check for common grouping dimensions in order of preference
        auto_detect_dimensions = ['ticker', 'symbol', 'stock', 'exchange', 'sector', 'category']
        for dim in auto_detect_dimensions:
            if dim in pdf.columns:
                color_dimension = dim
                break

    # Sort by first y-measure for better visualization (descending)
    pdf_sorted = pdf.sort_values(by=y_measures[0], ascending=False)

    # Create figure based on number of measures
    if len(y_measures) == 1:
        # Single measure - use standard plotting
        y_col = y_measures[0]
        fig = px.bar(
            pdf_sorted,
            x=x_col,
            y=y_col,
            color=color_dimension if color_dimension and color_dimension in pdf.columns else None,
            labels={
                x_col: exhibit.x_axis.label or x_col.replace('_', ' ').title(),
                y_col: exhibit.y_axis.label or y_col.replace('_', ' ').title()
            },
            hover_data={x_col: True, y_col: ':.2f'},
        )
    else:
        # Multiple measures - create grouped bars
        fig = go.Figure()

        for measure in y_measures:
            fig.add_trace(go.Bar(
                x=pdf_sorted[x_col],
                y=pdf_sorted[measure],
                name=measure.replace('_', ' ').title(),
                hovertemplate='<b>%{x}</b><br>%{y:.2f}<extra></extra>'
            ))

        # Update layout for grouped bars
        fig.update_layout(
            barmode='group',
            xaxis_title=exhibit.x_axis.label or x_col.replace('_', ' ').title(),
            yaxis_title=exhibit.y_axis.label or "Value"
        )

    # Apply theme
    theme = st.session_state.get('theme', 'light')
    if theme == 'dark':
        fig.update_layout(
            plot_bgcolor='#1E2130',
            paper_bgcolor='#1E2130',
            font=dict(color='#FAFAFA', size=12),
            xaxis=dict(
                gridcolor='#3A3D45',
                showgrid=False,
                zeroline=False
            ),
            yaxis=dict(
                gridcolor='#3A3D45',
                showgrid=True,
                zeroline=False
            ),
            hovermode='closest',
            legend=dict(
                bgcolor='#262730',
                bordercolor='#3A3D45',
                borderwidth=1
            )
        )
    else:
        fig.update_layout(
            plot_bgcolor='#FFFFFF',
            paper_bgcolor='#F8F9FA',
            font=dict(size=12),
            xaxis=dict(
                gridcolor='#E0E0E0',
                showgrid=False,
                zeroline=False
            ),
            yaxis=dict(
                gridcolor='#E0E0E0',
                showgrid=True,
                zeroline=False
            ),
            hovermode='closest',
            legend=dict(
                bgcolor='#FFFFFF',
                bordercolor='#E0E0E0',
                borderwidth=1
            )
        )

    # Enhanced layout
    fig.update_layout(
        title=None,  # Already have st.subheader
        showlegend=True,
        height=400,
        margin=dict(l=10, r=10, t=10, b=10),
    )

    # Better bar styling
    fig.update_traces(
        marker=dict(line=dict(width=0)),
        hovertemplate='<b>%{x}</b><br>%{y:.2f}<extra></extra>'
    )

    # Enable click/selection events if interactive is enabled
    if exhibit.interactive:
        fig = enable_chart_selection(fig, exhibit.id)

    # Interactive config
    config = {
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'toImageButtonOptions': {
            'format': 'png',
            'filename': f'{exhibit.id}',
            'height': 600,
            'width': 1200,
            'scale': 2
        }
    }

    st.plotly_chart(fig, use_container_width=True, config=config, key=f"chart_{exhibit.id}")
