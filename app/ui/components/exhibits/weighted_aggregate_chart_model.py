"""
Weighted aggregate chart exhibit component (Model-based version).

This is a simplified renderer that displays weighted aggregate indices
that are pre-calculated in the model/silver layer. All calculation logic
has been moved to the model layer for better separation of concerns.

Features:
- Multiple weighting methods displayed side-by-side
- Interactive legend for showing/hiding methods
- Professional theming
- No business logic - pure rendering
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np


def render_weighted_aggregate_chart(exhibit, pdf: pd.DataFrame):
    """
    Render weighted aggregate chart with model-calculated data.

    The data comes pre-calculated from weighted aggregate views in the silver layer.
    This component only handles rendering - no calculation logic.

    Args:
        exhibit: Exhibit configuration
        pdf: Pandas DataFrame with columns:
            - aggregate_by (e.g., 'trade_date'): Grouping dimension
            - weighted_value: Pre-calculated weighted aggregate value
            - measure_id: Identifier for the weighting method

    Data structure:
        trade_date | weighted_value | measure_id
        2024-01-01 | 150.25        | equal_weighted_index
        2024-01-01 | 155.75        | volume_weighted_index
        2024-01-02 | 151.00        | equal_weighted_index
        2024-01-02 | 156.25        | volume_weighted_index
    """
    st.subheader(exhibit.title)

    if exhibit.description:
        st.caption(exhibit.description)

    if pdf.empty:
        st.info("No data available for selected filters")
        st.caption("💡 Make sure to run: python scripts/build_weighted_aggregates_duckdb.py")
        return

    # Get configuration
    aggregate_by = exhibit.aggregate_by or 'trade_date'

    # Check required columns
    required_cols = [aggregate_by, 'weighted_value', 'measure_id']
    missing_cols = [col for col in required_cols if col not in pdf.columns]
    if missing_cols:
        st.error(f"Missing required columns: {missing_cols}")
        st.caption("Expected columns: aggregate_by, weighted_value, measure_id")
        return

    # Get unique measures (weighting methods)
    measures = pdf['measure_id'].unique()

    if len(measures) == 0:
        st.warning("No weighted aggregate measures found in data")
        return

    # Create visualization
    fig = go.Figure()

    # Define colors for different methods
    colors = {
        'equal_weighted_index': '#1f77b4',
        'volume_weighted_index': '#ff7f0e',
        'market_cap_weighted_index': '#2ca02c',
        'price_weighted_index': '#d62728',
        'volume_deviation_weighted_index': '#9467bd',
        'volatility_weighted_index': '#8c564b',
    }

    # Add trace for each measure
    for measure_id in sorted(measures):
        measure_data = pdf[pdf['measure_id'] == measure_id].sort_values(aggregate_by)

        # Format measure name for display
        display_name = measure_id.replace('_', ' ').replace(' index', '').title()

        fig.add_trace(go.Scatter(
            x=measure_data[aggregate_by],
            y=measure_data['weighted_value'],
            mode='lines+markers',
            name=display_name,
            line=dict(
                width=2.5,
                color=colors.get(measure_id, '#666666')
            ),
            marker=dict(size=5),
            hovertemplate='<b>%{x}</b><br>$%{y:.2f}<extra></extra>'
        ))

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
                zeroline=False,
                title=aggregate_by.replace('_', ' ').title()
            ),
            yaxis=dict(
                gridcolor='#3A3D45',
                showgrid=True,
                zeroline=False,
                title='Value ($)'
            ),
            hovermode='x unified',
            legend=dict(
                bgcolor='#262730',
                bordercolor='#3A3D45',
                borderwidth=1,
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
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
                zeroline=False,
                title=aggregate_by.replace('_', ' ').title()
            ),
            yaxis=dict(
                gridcolor='#E0E0E0',
                showgrid=True,
                zeroline=False,
                title='Value ($)'
            ),
            hovermode='x unified',
            legend=dict(
                bgcolor='#FFFFFF',
                bordercolor='#E0E0E0',
                borderwidth=1,
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
        )

    # Enhanced layout
    fig.update_layout(
        title=None,  # Already have st.subheader
        showlegend=True,
        height=500,
        margin=dict(l=10, r=10, t=50, b=10),
    )

    # Interactive config
    config = {
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'toImageButtonOptions': {
            'format': 'png',
            'filename': f'{exhibit.id}_weighted_aggregates',
            'height': 600,
            'width': 1200,
            'scale': 2
        }
    }

    st.plotly_chart(fig, use_container_width=True, config=config)

    # Show information about the measures (only use expander if not already collapsible)
    # Check if exhibit is collapsible to avoid nested expanders
    use_expander = not getattr(exhibit, 'collapsible', False)

    if use_expander:
        with st.expander("📊 Measure Information"):
            _render_measure_info(exhibit, pdf, measures)
    else:
        # Just show the info directly without expander
        st.markdown("---")
        st.markdown("**📊 Measure Information**")
        _render_measure_info(exhibit, pdf, measures)

    # Optional: Show sample data
    if st.checkbox("Show sample data", key=f"{exhibit.id}_show_data"):
        st.dataframe(pdf.head(20), use_container_width=True)


def _render_measure_info(exhibit, pdf, measures):
    """Render measure information section."""
    st.markdown(f"""
    **Displaying {len(measures)} weighted aggregate measure(s):**
    """)

    for measure_id in sorted(measures):
        measure_data = pdf[pdf['measure_id'] == measure_id]
        avg_value = measure_data['weighted_value'].mean()
        min_value = measure_data['weighted_value'].min()
        max_value = measure_data['weighted_value'].max()
        data_points = len(measure_data)

        display_name = measure_id.replace('_', ' ').replace(' index', '').title()
        st.markdown(f"""
        **{display_name}**
        - Data points: {data_points}
        - Range: ${min_value:.2f} - ${max_value:.2f}
        - Average: ${avg_value:.2f}
        """)

    st.caption("""
    💡 **Tip:** Click on legend items to show/hide specific weighting methods.

    These values are pre-calculated in the silver layer for optimal performance.
    """)
