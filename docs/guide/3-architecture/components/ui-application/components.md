# UI Application - Components

## Overview

Reusable UI components for charts, tables, filters, and other visualizations.

## Chart Components

### Line Chart

```python
# File: app/ui/components/exhibits/line_chart.py

import plotly.express as px
import streamlit as st

def render_line_chart(exhibit, data):
    """Render line chart exhibit."""
    
    config = exhibit.config
    x_axis = config.get('x_axis', 'date')
    y_axis = config.get('y_axis', 'value')
    color_by = config.get('color_by')
    
    fig = px.line(
        data,
        x=x_axis,
        y=y_axis,
        color=color_by,
        title=exhibit.title,
        labels={
            x_axis: x_axis.replace('_', ' ').title(),
            y_axis: y_axis.replace('_', ' ').title()
        }
    )
    
    fig.update_layout(
        hovermode='x unified',
        height=config.get('height', 500)
    )
    
    st.plotly_chart(fig, use_container_width=True)
```

### Bar Chart

```python
# File: app/ui/components/exhibits/bar_chart.py

def render_bar_chart(exhibit, data):
    """Render bar chart exhibit."""
    
    config = exhibit.config
    x_axis = config.get('x_axis')
    y_axis = config.get('y_axis')
    orientation = config.get('orientation', 'vertical')
    
    fig = px.bar(
        data,
        x=x_axis,
        y=y_axis,
        title=exhibit.title,
        orientation='v' if orientation == 'vertical' else 'h'
    )
    
    st.plotly_chart(fig, use_container_width=True)
```

## Table Components

```python
# File: app/ui/components/exhibits/data_table.py

def render_data_table(exhibit, data):
    """Render data table exhibit."""
    
    config = exhibit.config
    
    # Apply column formatting
    formatters = config.get('formatters', {})
    for col, fmt in formatters.items():
        if col in data.columns:
            if fmt == 'currency':
                data[col] = data[col].apply(lambda x: f"${x:,.2f}")
            elif fmt == 'percent':
                data[col] = data[col].apply(lambda x: f"{x:.2%}")
    
    # Display table
    st.dataframe(
        data,
        use_container_width=True,
        height=config.get('height', 400)
    )
    
    # Download button
    if config.get('downloadable', True):
        csv = data.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"{exhibit.title}.csv",
            mime="text/csv"
        )
```

## Filter Components

```python
# File: app/ui/components/dynamic_filters.py

def render_dimension_filter(filter_def, manager):
    """Render dimension selector filter."""
    
    config = filter_def.config
    dimension = config['dimension']
    model_name = config.get('model', 'company')
    
    # Get distinct values
    values = get_dimension_values(manager.session, model_name, dimension)
    
    # Render widget
    selected = st.multiselect(
        label=config.get('label', dimension),
        options=values,
        default=config.get('default')
    )
    
    # Update filter
    if selected:
        manager.update_filter(dimension, selected)

def render_date_range_filter(filter_def, manager):
    """Render date range filter."""
    
    config = filter_def.config
    
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start Date", value=config.get('default_start'))
    with col2:
        end = st.date_input("End Date", value=config.get('default_end'))
    
    if start and end:
        manager.update_filter('date', {'start': str(start), 'end': str(end)})
```

## Metric Components

```python
# File: app/ui/components/exhibits/metric_cards.py

def render_metric_cards(exhibit, metrics_data):
    """Render metric cards exhibit."""
    
    cols = st.columns(len(metrics_data))
    
    for idx, metric in enumerate(metrics_data):
        with cols[idx]:
            name = metric['name']
            value = metric['value']
            delta = metric.get('delta')
            format_type = metric.get('format', 'number')
            
            # Format value
            if format_type == 'currency':
                value_str = f"${value:,.2f}"
            elif format_type == 'percent':
                value_str = f"{value:.2%}"
            else:
                value_str = f"{value:,.0f}"
            
            # Display metric
            st.metric(
                label=name,
                value=value_str,
                delta=delta
            )
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/ui-application/components.md`
