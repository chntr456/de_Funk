"""
Weighted aggregate chart exhibit component with dynamic weighting methods.

Renders aggregated stock metrics using various weighting schemes:
- Equal weighting (simple average)
- Market cap weighting
- Volume weighting
- Price weighting
- Custom formula weighting (e.g., volume deviation)

Features:
- Interactive weight method selector
- Real-time chart updates
- Multiple metrics display
- Detailed hover information showing weights
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from typing import Optional


def calculate_weighted_aggregate(
    df: pd.DataFrame,
    value_col: str,
    weight_method: str,
    weight_col: Optional[str] = None,
    normalize: bool = True
) -> pd.DataFrame:
    """
    Calculate weighted aggregate for a given weighting method.

    Args:
        df: DataFrame with stock data
        value_col: Column to aggregate (e.g., 'close', 'volume')
        weight_method: Weighting method ('equal', 'volume', 'price', etc.)
        weight_col: Custom weight column (for 'custom' method)
        normalize: Whether to normalize weights to sum to 1

    Returns:
        DataFrame with weighted aggregate values
    """
    result_frames = []

    # Group by date if present
    if 'trade_date' in df.columns:
        group_col = 'trade_date'
        for date, group in df.groupby(group_col):
            agg_value = _calculate_group_weighted_aggregate(
                group, value_col, weight_method, weight_col, normalize
            )
            result_frames.append({
                group_col: date,
                f'weighted_{value_col}': agg_value,
                'weight_method': weight_method
            })
    else:
        # Single aggregate
        agg_value = _calculate_group_weighted_aggregate(
            df, value_col, weight_method, weight_col, normalize
        )
        result_frames.append({
            f'weighted_{value_col}': agg_value,
            'weight_method': weight_method
        })

    return pd.DataFrame(result_frames)


def _calculate_group_weighted_aggregate(
    group: pd.DataFrame,
    value_col: str,
    weight_method: str,
    weight_col: Optional[str],
    normalize: bool
) -> float:
    """Calculate weighted aggregate for a single group."""

    if group.empty or value_col not in group.columns:
        return np.nan

    values = group[value_col].values

    # Calculate weights based on method
    if weight_method == 'equal':
        weights = np.ones(len(values))

    elif weight_method == 'volume':
        if 'volume' not in group.columns:
            return np.nan
        weights = group['volume'].values

    elif weight_method == 'price':
        if 'close' not in group.columns:
            return np.nan
        weights = group['close'].values

    elif weight_method == 'market_cap':
        # Market cap = price * shares outstanding
        # If shares not available, use price * volume as proxy
        if 'close' in group.columns and 'volume' in group.columns:
            weights = group['close'].values * group['volume'].values
        else:
            return np.nan

    elif weight_method == 'volume_deviation':
        # Weight by (volume - avg_volume) * price
        if 'volume' not in group.columns or 'close' not in group.columns:
            return np.nan

        avg_volume = group['volume'].mean()
        volume_diff = group['volume'].values - avg_volume
        weights = volume_diff * group['close'].values

        # Handle negative weights by taking absolute value
        weights = np.abs(weights)

    elif weight_method == 'volatility':
        # Inverse volatility weighting - requires historical data
        # For single group, use inverse of daily range
        if 'high' in group.columns and 'low' in group.columns:
            daily_range = group['high'].values - group['low'].values
            # Avoid division by zero
            daily_range = np.where(daily_range == 0, 0.001, daily_range)
            weights = 1.0 / daily_range
        else:
            return np.nan

    elif weight_method == 'custom' and weight_col:
        if weight_col not in group.columns:
            return np.nan
        weights = group[weight_col].values

    else:
        weights = np.ones(len(values))

    # Remove NaN values
    valid_mask = ~(np.isnan(values) | np.isnan(weights))
    values = values[valid_mask]
    weights = weights[valid_mask]

    if len(values) == 0 or weights.sum() == 0:
        return np.nan

    # Normalize weights if requested
    if normalize:
        weights = weights / weights.sum()

    # Calculate weighted average
    weighted_avg = np.sum(values * weights)

    return weighted_avg


def render_weighted_aggregate_chart(exhibit, pdf: pd.DataFrame):
    """
    Render weighted aggregate chart with dynamic weight method selection.

    Args:
        exhibit: Exhibit configuration with weighting, aggregate_by, value_measures
        pdf: Pandas DataFrame with stock data
    """
    st.subheader(exhibit.title)

    if exhibit.description:
        st.caption(exhibit.description)

    if pdf.empty:
        st.info("No data available for selected filters")
        return

    # Get configuration
    value_measures = exhibit.value_measures or ['close']
    aggregate_by = exhibit.aggregate_by or 'trade_date'

    # Default weighting config
    default_weight_method = 'equal'
    if exhibit.weighting and hasattr(exhibit.weighting, 'method'):
        if hasattr(exhibit.weighting.method, 'value'):
            default_weight_method = exhibit.weighting.method.value
        else:
            default_weight_method = exhibit.weighting.method

    # Create interactive weight method selector
    col1, col2 = st.columns([3, 1])

    with col1:
        weight_methods = {
            'Equal Weighted': 'equal',
            'Volume Weighted': 'volume',
            'Price Weighted': 'price',
            'Market Cap Weighted': 'market_cap',
            'Volume Deviation Weighted': 'volume_deviation',
            'Inverse Volatility Weighted': 'volatility'
        }

        # Find default key
        default_key = 'Equal Weighted'
        for key, val in weight_methods.items():
            if val == default_weight_method:
                default_key = key
                break

        selected_method_name = st.selectbox(
            "Weighting Method",
            options=list(weight_methods.keys()),
            index=list(weight_methods.keys()).index(default_key),
            key=f"{exhibit.id}_weight_method"
        )
        selected_method = weight_methods[selected_method_name]

    with col2:
        normalize_weights = st.checkbox(
            "Normalize",
            value=True,
            key=f"{exhibit.id}_normalize",
            help="Normalize weights to sum to 1"
        )

    # Display method description
    method_descriptions = {
        'equal': 'All stocks weighted equally (simple average)',
        'volume': 'Weighted by trading volume',
        'price': 'Weighted by stock price',
        'market_cap': 'Weighted by market capitalization (price × volume)',
        'volume_deviation': 'Weighted by (volume - avg_volume) × price',
        'volatility': 'Weighted by inverse volatility (1 / daily_range)'
    }

    st.caption(f"💡 {method_descriptions.get(selected_method, 'Custom weighting')}")

    # Calculate weighted aggregates for each value measure
    all_results = []

    for measure in value_measures:
        if measure not in pdf.columns:
            st.warning(f"Measure '{measure}' not found in data")
            continue

        weighted_df = calculate_weighted_aggregate(
            pdf,
            measure,
            selected_method,
            normalize=normalize_weights
        )

        if not weighted_df.empty:
            # Rename for clarity
            weighted_df = weighted_df.rename(
                columns={f'weighted_{measure}': f'Aggregate {measure.replace("_", " ").title()}'}
            )
            all_results.append(weighted_df)

    if not all_results:
        st.error("Unable to calculate weighted aggregates with selected method")
        return

    # Merge all results
    result_df = all_results[0]
    for df in all_results[1:]:
        result_df = result_df.merge(df, on=aggregate_by, how='outer')

    # Sort by date
    result_df = result_df.sort_values(by=aggregate_by)

    # Create visualization
    fig = go.Figure()

    # Add trace for each measure
    theme = st.session_state.get('theme', 'light')
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    for idx, measure in enumerate(value_measures):
        col_name = f'Aggregate {measure.replace("_", " ").title()}'
        if col_name in result_df.columns:
            fig.add_trace(go.Scatter(
                x=result_df[aggregate_by],
                y=result_df[col_name],
                mode='lines+markers',
                name=col_name,
                line=dict(width=2.5, color=colors[idx % len(colors)]),
                marker=dict(size=6),
                hovertemplate='<b>%{x}</b><br>%{y:.2f}<extra></extra>'
            ))

    # Apply theme
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
                title='Value'
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
                zeroline=False,
                title=aggregate_by.replace('_', ' ').title()
            ),
            yaxis=dict(
                gridcolor='#E0E0E0',
                showgrid=True,
                zeroline=False,
                title='Value'
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
        height=500,
        margin=dict(l=10, r=10, t=10, b=10),
    )

    # Interactive config
    config = {
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'toImageButtonOptions': {
            'format': 'png',
            'filename': f'{exhibit.id}_{selected_method}',
            'height': 600,
            'width': 1200,
            'scale': 2
        }
    }

    st.plotly_chart(fig, use_container_width=True, config=config)

    # Optional: Show summary statistics
    with st.expander("📊 View Summary Statistics"):
        summary_stats = result_df.describe()
        st.dataframe(summary_stats, use_container_width=True)

        # Show sample of underlying data
        if st.checkbox("Show sample data", key=f"{exhibit.id}_show_sample"):
            st.dataframe(pdf.head(20), use_container_width=True)
