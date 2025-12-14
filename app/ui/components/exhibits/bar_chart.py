"""
Bar chart exhibit component with Plotly visualization.

Renders categorical comparisons as interactive bar charts with:
- Proper ordering by value or category
- Interactive hover tooltips
- Zoom and selection tools
- Dynamic measure and dimension selection via Plotly dropdowns
"""

import pandas as pd
import plotly.graph_objects as go


def get_bar_chart_html(
    exhibit,
    pdf: pd.DataFrame,
    selected_measures: list = None,
    selected_dimension: str = None,
) -> str:
    """
    Get bar chart as embeddable HTML for CSS grid rendering.

    Includes Plotly dropdown menus for measure selection when
    measure_selector is configured in YAML.

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
            return "<div>Bar chart requires x_axis configuration</div>"
    else:
        x_col = exhibit.x_axis.dimension

    if x_col not in pdf.columns:
        return f"<div>X column '{x_col}' not found in data</div>"

    # Check for measure_selector configuration
    has_measure_selector = hasattr(exhibit, 'measure_selector') and exhibit.measure_selector

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
        return "<div>No numeric measures found for bar chart</div>"

    if not default_measures:
        default_measures = available_measures[:1]

    # Check for dimension_selector configuration
    has_dimension_selector = hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector

    # Get available dimensions and default dimension
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

    # Use passed dimension if provided (from Streamlit selectbox)
    if selected_dimension and selected_dimension in pdf.columns:
        default_dimension = selected_dimension

    # If no default but have available, use first
    if not default_dimension and available_dimensions:
        default_dimension = available_dimensions[0]

    # Check for aggregation config
    agg_method = 'sum'
    if hasattr(exhibit, 'options') and exhibit.options:
        agg_method = exhibit.options.get('aggregation', 'sum')
    if has_dimension_selector:
        ds = exhibit.dimension_selector
        dim_agg = getattr(ds, 'aggregation', None)
        if dim_agg:
            agg_method = dim_agg

    agg_map = {
        'avg': 'mean', 'mean': 'mean', 'sum': 'sum',
        'min': 'min', 'max': 'max', 'count': 'count'
    }
    pandas_agg = agg_map.get(agg_method, 'sum')

    # Limit data size
    MAX_BARS = 50
    MAX_DIMENSION_VALUES = 10

    logger.debug(f"Bar chart HTML: measures={available_measures}, dim={default_dimension}")

    # Aggregate data by x_col and selected dimension
    group_cols = [x_col]
    if default_dimension and default_dimension in pdf.columns:
        # Filter to top dimension values first
        top_dims = pdf[default_dimension].value_counts().head(MAX_DIMENSION_VALUES).index.tolist()
        pdf = pdf[pdf[default_dimension].isin(top_dims)]
        group_cols.append(default_dimension)

    agg_dict = {m: pandas_agg for m in available_measures if m in pdf.columns}
    try:
        pdf = pdf.groupby(group_cols, as_index=False).agg(agg_dict)
    except Exception as e:
        logger.warning(f"Bar chart aggregation failed: {e}")

    # Limit bars and sort
    if len(pdf) > MAX_BARS:
        pdf = pdf.nlargest(MAX_BARS, default_measures[0])
    pdf = pdf.sort_values(by=default_measures[0], ascending=False)

    # Determine which measures to display
    # If selected_measures was provided (server-side selection), only show those
    # Otherwise, use default_measures but keep all available for client-side dropdown
    server_side_selection = selected_measures is not None
    measures_to_display = default_measures if server_side_selection else available_measures

    # Build figure with traces for the selected dimension
    fig = go.Figure()
    trace_info = []  # [(measure, dimension_value or None)]

    if default_dimension and default_dimension in pdf.columns:
        for measure in measures_to_display:
            is_visible = measure in default_measures
            for dim_val in pdf[default_dimension].unique():
                df_subset = pdf[pdf[default_dimension] == dim_val]
                name = f"{dim_val}" if len(measures_to_display) == 1 else f"{dim_val} - {measure.replace('_', ' ').title()}"
                fig.add_trace(go.Bar(
                    x=df_subset[x_col],
                    y=df_subset[measure],
                    name=name,
                    visible=is_visible,
                    legendgroup=str(dim_val),
                ))
                trace_info.append((measure, dim_val))
    else:
        for measure in measures_to_display:
            is_visible = measure in default_measures
            fig.add_trace(go.Bar(
                x=pdf[x_col],
                y=pdf[measure],
                name=measure.replace('_', ' ').title(),
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
        barmode='group' if default_dimension or len(measures_to_display) > 1 else 'relative',
        hovermode='closest',
        margin=dict(l=40, r=40, t=top_margin, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white',
        updatemenus=updatemenus if updatemenus else [],
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True)

    # Get height from exhibit config
    height = 350
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
