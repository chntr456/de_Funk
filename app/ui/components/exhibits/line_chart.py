"""
Line chart exhibit component with Plotly visualization.

Renders time series or categorical data as interactive line charts with:
- Proper time ordering
- Interactive hover tooltips
- Zoom, pan, and selection tools
- Dynamic measure and dimension selection via Plotly dropdowns
"""

import pandas as pd
import plotly.graph_objects as go


def get_line_chart_html(
    exhibit,
    pdf: pd.DataFrame,
    selected_measures: list = None,
    selected_dimension: str = None,
) -> str:
    """
    Get line chart as embeddable HTML for CSS grid rendering.

    Includes Plotly dropdown menus for measure and dimension selection
    when measure_selector or dimension_selector are configured in YAML.

    Args:
        exhibit: Exhibit configuration
        pdf: Pandas DataFrame with data
        selected_measures: Optional list of measures (overrides defaults)
        selected_dimension: Optional dimension (overrides default)

    Returns:
        HTML string with embedded Plotly chart and interactive dropdowns
    """
    import plotly.io as pio
    from config.logging import get_logger
    logger = get_logger(__name__)

    # Get x column
    if not hasattr(exhibit, 'x_axis') or not exhibit.x_axis:
        x_col = getattr(exhibit, 'x', None)
        if not x_col:
            return "<div>Line chart requires x_axis configuration</div>"
    else:
        x_col = exhibit.x_axis.dimension

    if x_col not in pdf.columns:
        return f"<div>X column '{x_col}' not found in data</div>"

    # Check for measure_selector configuration
    has_measure_selector = hasattr(exhibit, 'measure_selector') and exhibit.measure_selector
    has_dimension_selector = hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector

    # Get available and default measures
    available_measures = []
    default_measures = []

    if has_measure_selector:
        ms = exhibit.measure_selector
        if hasattr(ms, 'available_measures') and ms.available_measures:
            available_measures = [m for m in ms.available_measures if m in pdf.columns]
        if hasattr(ms, 'default_measures') and ms.default_measures:
            default_measures = [m for m in ms.default_measures if m in pdf.columns]
    elif hasattr(exhibit, 'y_axis') and exhibit.y_axis:
        if hasattr(exhibit.y_axis, 'measure') and exhibit.y_axis.measure:
            if isinstance(exhibit.y_axis.measure, list):
                available_measures = [m for m in exhibit.y_axis.measure if m in pdf.columns]
            else:
                available_measures = [exhibit.y_axis.measure] if exhibit.y_axis.measure in pdf.columns else []
        elif hasattr(exhibit.y_axis, 'measures') and exhibit.y_axis.measures:
            available_measures = [m for m in exhibit.y_axis.measures if m in pdf.columns]
        default_measures = available_measures.copy()
    elif hasattr(exhibit, 'y') and exhibit.y:
        if isinstance(exhibit.y, list):
            available_measures = [m for m in exhibit.y if m in pdf.columns]
        else:
            available_measures = [exhibit.y] if exhibit.y in pdf.columns else []
        default_measures = available_measures.copy()

    # Use passed selections if provided
    if selected_measures:
        default_measures = [m for m in selected_measures if m in pdf.columns]

    if not available_measures:
        available_measures = [c for c in pdf.columns if pd.api.types.is_numeric_dtype(pdf[c]) and c != x_col][:5]

    if not available_measures:
        return "<div>No numeric measures found for line chart</div>"

    if not default_measures:
        default_measures = available_measures[:1]

    # Get available and default dimensions
    available_dimensions = []
    default_dimension = None

    if has_dimension_selector:
        ds = exhibit.dimension_selector
        if hasattr(ds, 'available_dimensions') and ds.available_dimensions:
            available_dimensions = [d for d in ds.available_dimensions if d in pdf.columns]
        if hasattr(ds, 'default_dimension') and ds.default_dimension:
            default_dimension = ds.default_dimension if ds.default_dimension in pdf.columns else None
    elif hasattr(exhibit, 'color_by') and exhibit.color_by and exhibit.color_by in pdf.columns:
        available_dimensions = [exhibit.color_by]
        default_dimension = exhibit.color_by
    elif hasattr(exhibit, 'color') and exhibit.color and exhibit.color in pdf.columns:
        available_dimensions = [exhibit.color]
        default_dimension = exhibit.color

    # Use passed dimension if provided
    if selected_dimension and selected_dimension in pdf.columns:
        default_dimension = selected_dimension

    # Limit data size for browser performance
    MAX_POINTS_PER_LINE = 500
    MAX_DIMENSION_VALUES = 10

    # Get aggregation method from dimension_selector config
    agg_method = 'mean'
    if has_dimension_selector:
        ds = exhibit.dimension_selector
        agg_method = getattr(ds, 'aggregation', 'avg')
        if agg_method == 'avg':
            agg_method = 'mean'

    # Determine if we need to aggregate (when using a non-primary dimension)
    primary_dim = available_dimensions[0] if available_dimensions else None
    needs_aggregation = default_dimension and default_dimension != primary_dim and default_dimension in pdf.columns

    # Aggregate if needed (e.g., switching from ticker to sector)
    if needs_aggregation:
        agg_dict = {m: agg_method for m in available_measures if m in pdf.columns}
        try:
            pdf = pdf.groupby([x_col, default_dimension], as_index=False).agg(agg_dict)
            logger.debug(f"Aggregated by {default_dimension}: {len(pdf)} rows")
        except Exception as e:
            logger.warning(f"Aggregation for {default_dimension} failed: {e}")

    # Sort by x-axis
    pdf = pdf.sort_values(by=x_col)

    logger.debug(f"Line chart HTML: {len(pdf)} points, measures={available_measures}, dim={default_dimension}")

    # Build figure with traces for the selected dimension
    fig = go.Figure()
    trace_info = []  # [(measure, dimension_value or None)]

    dim_to_use = default_dimension
    if dim_to_use and dim_to_use in pdf.columns:
        # Filter to top dimension values by frequency
        unique_vals = pdf[dim_to_use].nunique()
        if unique_vals > MAX_DIMENSION_VALUES:
            top_dims = pdf[dim_to_use].value_counts().head(MAX_DIMENSION_VALUES).index.tolist()
            pdf = pdf[pdf[dim_to_use].isin(top_dims)]

        dim_values = pdf[dim_to_use].unique().tolist()
        for measure in available_measures:
            for dim_val in dim_values:
                df_subset = pdf[pdf[dim_to_use] == dim_val]
                is_visible = measure in default_measures
                fig.add_trace(go.Scatter(
                    x=df_subset[x_col],
                    y=df_subset[measure],
                    name=f"{dim_val}" if len(available_measures) == 1 else f"{dim_val} - {measure.replace('_', ' ').title()}",
                    mode='lines+markers',
                    line=dict(width=2),
                    marker=dict(size=3),
                    visible=is_visible,
                    legendgroup=str(dim_val),
                ))
                trace_info.append((measure, dim_val))
    else:
        # No dimension - just plot measures
        for measure in available_measures:
            is_visible = measure in default_measures
            fig.add_trace(go.Scatter(
                x=pdf[x_col],
                y=pdf[measure],
                name=measure.replace('_', ' ').title(),
                mode='lines+markers',
                line=dict(width=2),
                marker=dict(size=3),
                visible=is_visible,
            ))
            trace_info.append((measure, None))

    # Build dropdown menus for measure selector only (dimension is handled by Streamlit)
    updatemenus = []
    menu_y_offset = 1.0

    # Measure selector dropdown (if measure_selector is configured and has multiple measures)
    if has_measure_selector and len(available_measures) > 1:
        measure_buttons = []
        for measure in available_measures:
            visibility = [info[0] == measure for info in trace_info]
            measure_buttons.append(dict(
                label=measure.replace('_', ' ').title(),
                method='update',
                args=[{'visible': visibility}]
            ))
        # Add "All" option
        measure_buttons.insert(0, dict(
            label='All Measures',
            method='update',
            args=[{'visible': [True] * len(trace_info)}]
        ))

        updatemenus.append(dict(
            active=0,
            buttons=measure_buttons,
            direction='down',
            showactive=True,
            x=0,
            xanchor='left',
            y=menu_y_offset,
            yanchor='bottom',
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='#ddd',
            font=dict(size=10),
            pad=dict(r=2, t=2, b=2, l=2),
        ))

    # Style the figure with proper spacing for dropdowns and title
    has_title = hasattr(exhibit, 'title') and exhibit.title
    top_margin = 30
    if has_title:
        top_margin += 25
    if updatemenus:
        top_margin += 30

    fig.update_layout(
        title=dict(
            text=exhibit.title if has_title else None,
            y=0.98,
            x=0.5,
            xanchor='center',
            yanchor='top',
            font=dict(size=14)
        ) if has_title else None,
        hovermode='x unified',
        margin=dict(l=40, r=40, t=top_margin, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white',
        updatemenus=updatemenus if updatemenus else [],
    )

    # Get height from exhibit config
    height = 400
    if hasattr(exhibit, 'height') and exhibit.height:
        height = exhibit.height
    elif hasattr(exhibit, 'options') and exhibit.options and exhibit.options.get('height'):
        height = exhibit.options['height']

    # Convert to HTML
    html = pio.to_html(
        fig,
        full_html=False,
        include_plotlyjs='cdn',
        config={'displayModeBar': True, 'responsive': True}
    )

    return f'<div style="height: {height}px; width: 100%;">{html}</div>'
