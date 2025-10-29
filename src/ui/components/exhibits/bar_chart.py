"""
Bar chart exhibit component.

Renders categorical comparisons as bar charts with theme support.
"""

import streamlit as st
import pandas as pd
import plotly.express as px


def render_bar_chart(exhibit, pdf: pd.DataFrame):
    """
    Render bar chart exhibit.

    Args:
        exhibit: Exhibit configuration with x_axis, y_axis, color_by
        pdf: Pandas DataFrame with data to plot
    """
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
        if st.session_state.get('theme') == 'dark':
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
