"""
Line chart exhibit component with enhanced Plotly visualization.

Renders time series or categorical data as interactive line charts with:
- Proper time ordering
- Interactive hover tooltips
- Zoom, pan, and selection tools
- Theme support
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def render_line_chart(exhibit, pdf: pd.DataFrame):
    """
    Render enhanced line chart exhibit with proper ordering.

    Args:
        exhibit: Exhibit configuration with x_axis, y_axis, color_by
        pdf: Pandas DataFrame with data to plot
    """
    st.subheader(exhibit.title)

    if exhibit.description:
        st.caption(exhibit.description)

    if not exhibit.x_axis or not exhibit.y_axis:
        st.warning("Line chart requires x_axis and y_axis configuration")
        return

    if pdf.empty:
        st.info("No data available for selected filters")
        return

    x_col = exhibit.x_axis.dimension
    y_col = exhibit.y_axis.measure if hasattr(exhibit.y_axis, 'measure') else exhibit.y_axis.measures[0]

    # Sort by x-axis for proper time ordering
    pdf_sorted = pdf.sort_values(by=x_col)

    # Create Plotly figure with enhanced interactivity
    fig = px.line(
        pdf_sorted,
        x=x_col,
        y=y_col,
        color=exhibit.color_by if hasattr(exhibit, 'color_by') and exhibit.color_by else None,
        labels={
            x_col: exhibit.x_axis.label or x_col.replace('_', ' ').title(),
            y_col: exhibit.y_axis.label or y_col.replace('_', ' ').title()
        },
        hover_data={x_col: True, y_col: ':.2f'},
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
                showgrid=True,
                zeroline=False
            ),
            yaxis=dict(
                gridcolor='#3A3D45',
                showgrid=True,
                zeroline=False
            ),
            hovermode='x unified',
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
                showgrid=True,
                zeroline=False
            ),
            yaxis=dict(
                gridcolor='#E0E0E0',
                showgrid=True,
                zeroline=False
            ),
            hovermode='x unified',
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

    # Better line styling
    fig.update_traces(
        line=dict(width=2.5),
        mode='lines+markers',
        marker=dict(size=4),
        hovertemplate='<b>%{x}</b><br>%{y:.2f}<extra></extra>'
    )

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

    st.plotly_chart(fig, use_container_width=True, config=config)
