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
    from app.notebook.schema import ColumnReference

    # Helper function to extract field name from ColumnReference or string
    def extract_field_name(col_ref):
        """Extract field name from ColumnReference object or return string as-is."""
        if isinstance(col_ref, ColumnReference):
            return col_ref.field
        return col_ref

    # Get x column - must have x_axis with dimension as ColumnReference
    if not hasattr(exhibit, 'x_axis') or not exhibit.x_axis or not exhibit.x_axis.dimension:
        return "<div>Line chart requires x_axis configuration with dimension in model.table.column format</div>"

    x_col = exhibit.x_axis.dimension
    # Extract field name from ColumnReference
    x_col_name = extract_field_name(x_col)

    if x_col_name not in pdf.columns:
        return f"<div>X column '{x_col_name}' not found in data</div>"

    # Check for measure_selector configuration
    has_measure_selector = hasattr(exhibit, 'measure_selector') and exhibit.measure_selector
    has_dimension_selector = hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector

    # Get available and default measures
    available_measures = []
    default_measures = []

    if has_measure_selector:
        ms = exhibit.measure_selector
        if hasattr(ms, 'available_measures') and ms.available_measures:
            available_measures = [extract_field_name(m) for m in ms.available_measures if extract_field_name(m) in pdf.columns]
        if hasattr(ms, 'default_measures') and ms.default_measures:
            default_measures = [extract_field_name(m) for m in ms.default_measures if extract_field_name(m) in pdf.columns]
    elif hasattr(exhibit, 'y_axis') and exhibit.y_axis:
        # Get measures from y_axis (ColumnReference objects)
        if hasattr(exhibit.y_axis, 'measure') and exhibit.y_axis.measure:
            if isinstance(exhibit.y_axis.measure, list):
                available_measures = [extract_field_name(m) for m in exhibit.y_axis.measure if extract_field_name(m) in pdf.columns]
            else:
                m_name = extract_field_name(exhibit.y_axis.measure)
                available_measures = [m_name] if m_name in pdf.columns else []
        elif hasattr(exhibit.y_axis, 'measures') and exhibit.y_axis.measures:
            available_measures = [extract_field_name(m) for m in exhibit.y_axis.measures if extract_field_name(m) in pdf.columns]
        default_measures = available_measures.copy()

    # Use passed selections if provided
    if selected_measures:
        default_measures = [m for m in selected_measures if m in pdf.columns]

    # No fallback to auto-detect numeric columns - y_axis measures MUST be configured
    if not available_measures:
        return "<div>Line chart requires y_axis configuration with measures in model.table.column format (e.g., stocks.fact_stock_prices.adjusted_close)</div>"

    if not default_measures:
        default_measures = available_measures[:1]

    # Get available and default dimensions
    available_dimensions = []
    default_dimension = None

    if has_dimension_selector:
        ds = exhibit.dimension_selector
        if hasattr(ds, 'available_dimensions') and ds.available_dimensions:
            available_dimensions = [extract_field_name(d) for d in ds.available_dimensions if extract_field_name(d) in pdf.columns]
        if hasattr(ds, 'default_dimension') and ds.default_dimension:
            d_name = extract_field_name(ds.default_dimension)
            default_dimension = d_name if d_name in pdf.columns else None
    elif hasattr(exhibit, 'color_by') and exhibit.color_by:
        # color_by is a ColumnReference object
        color_name = extract_field_name(exhibit.color_by)
        if color_name in pdf.columns:
            available_dimensions = [color_name]
            default_dimension = color_name

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
            pdf = pdf.groupby([x_col_name, default_dimension], as_index=False).agg(agg_dict)
        except Exception:
            pass  # Aggregation failed, continue with original data

    # Sort by x-axis
    pdf = pdf.sort_values(by=x_col_name)

    # Determine which measures to display
    # If selected_measures was provided (server-side selection), only show those
    # Otherwise, use default_measures but keep all available for client-side dropdown
    server_side_selection = selected_measures is not None
    measures_to_display = default_measures if server_side_selection else available_measures

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
        for measure in measures_to_display:
            for dim_val in dim_values:
                df_subset = pdf[pdf[dim_to_use] == dim_val]
                is_visible = measure in default_measures
                fig.add_trace(go.Scatter(
                    x=df_subset[x_col_name],
                    y=df_subset[measure],
                    name=f"{dim_val}" if len(measures_to_display) == 1 else f"{dim_val} - {measure.replace('_', ' ').title()}",
                    mode='lines+markers',
                    line=dict(width=2),
                    marker=dict(size=3),
                    visible=is_visible,
                    legendgroup=str(dim_val),
                ))
                trace_info.append((measure, dim_val))
    else:
        # No dimension - just plot measures
        for measure in measures_to_display:
            is_visible = measure in default_measures
            fig.add_trace(go.Scatter(
                x=pdf[x_col_name],
                y=pdf[measure],
                name=measure.replace('_', ' ').title(),
                mode='lines+markers',
                line=dict(width=2),
                marker=dict(size=3),
                visible=is_visible,
            ))
            trace_info.append((measure, None))

    # Build dropdown menus for measure selector only (dimension is handled by Streamlit)
    # Skip Plotly dropdown when using server-side selection (multiselect in Chart Controls)
    updatemenus = []
    menu_y_offset = 1.0

    # Measure selector dropdown (only if not using server-side selection and measure_selector is configured)
    if not server_side_selection and has_measure_selector and len(available_measures) > 1:
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
    chart_html = pio.to_html(
        fig,
        full_html=False,
        include_plotlyjs='cdn',
        config={'displayModeBar': True, 'responsive': True}
    )

    # Build in-chart controls if we have multiple measures and not using server-side selection
    controls_html = ""
    if has_measure_selector and len(measures_to_display) > 1 and not server_side_selection:
        # Build checkbox controls for measure multi-select
        checkbox_items = []
        for i, measure in enumerate(measures_to_display):
            checked = "checked" if measure in default_measures else ""
            label = measure.replace('_', ' ').title()
            checkbox_items.append(
                f'<label style="margin-right:12px;cursor:pointer;">'
                f'<input type="checkbox" class="measure-cb" data-measure="{measure}" {checked} '
                f'style="margin-right:4px;cursor:pointer;"> {label}</label>'
            )

        controls_html = f'''
        <div class="chart-controls" style="
            padding: 8px 12px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
            font-size: 12px;
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        ">
            <span style="font-weight:600;color:#495057;margin-right:8px;">Measures:</span>
            {''.join(checkbox_items)}
        </div>
        '''

    # Build JavaScript for checkbox interactivity
    controls_js = ""
    if controls_html:
        # Map measures to trace indices
        measure_trace_map = {}
        for idx, (measure, dim_val) in enumerate(trace_info):
            if measure not in measure_trace_map:
                measure_trace_map[measure] = []
            measure_trace_map[measure].append(idx)

        controls_js = f'''
        <script>
        (function() {{
            const measureTraceMap = {measure_trace_map};
            const container = document.currentScript.parentElement;
            const checkboxes = container.querySelectorAll('.measure-cb');
            const plotDiv = container.querySelector('.plotly-graph-div');

            checkboxes.forEach(cb => {{
                cb.addEventListener('change', function() {{
                    const measure = this.dataset.measure;
                    const visible = this.checked;
                    const traceIndices = measureTraceMap[measure] || [];

                    if (plotDiv && traceIndices.length > 0) {{
                        const update = {{}};
                        traceIndices.forEach(idx => {{
                            Plotly.restyle(plotDiv, {{'visible': visible}}, [idx]);
                        }});
                    }}
                }});
            }});
        }})();
        </script>
        '''

    return f'''
    <div style="height: {height}px; width: 100%; display: flex; flex-direction: column;">
        {controls_html}
        <div style="flex: 1; min-height: 0;">
            {chart_html}
        </div>
        {controls_js}
    </div>
    '''
