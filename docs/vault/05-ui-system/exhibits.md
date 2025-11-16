# Exhibits

**Visualization system for notebook displays**

Files: `app/notebook/exhibits/`
Related: [Notebook System](notebook-system.md)

---

## Overview

**Exhibits** are declarative visualizations embedded in markdown notebooks using the `$exhibits${}` syntax. They render charts, tables, and metrics using Plotly and Streamlit.

**Design**: Declarative YAML configuration → Python rendering logic → Interactive viz

---

## Exhibit Types

### Charts

| Type | Purpose | Library |
|------|---------|---------|
| `line_chart` | Time series trends | Plotly |
| `bar_chart` | Category comparisons | Plotly |
| `scatter_plot` | Correlations | Plotly |
| `area_chart` | Stacked trends | Plotly |
| `histogram` | Distributions | Plotly |
| `heatmap` | 2D correlations | Plotly |

### Data Displays

| Type | Purpose | Library |
|------|---------|---------|
| `table` | Tabular data | Streamlit |
| `metric_cards` | KPI displays | Streamlit |

---

## Chart Examples

### Line Chart

```yaml
$exhibits${
type: line_chart
title: Stock Price Trends
source: equity.fact_equity_prices
x: trade_date
y: close
color: ticker
}
```

**Rendered As**: Interactive Plotly line chart with date on x-axis, price on y-axis, colored by ticker

---

### Bar Chart

```yaml
$exhibits${
type: bar_chart
title: Volume by Exchange
source: equity.fact_equity_prices
x: exchange_id
y: volume
}
```

---

### Scatter Plot

```yaml
$exhibits${
type: scatter_plot
title: Price vs Volume
x: volume
y: close
size: market_cap
color: sector
}
```

**Features**: Size and color encoding for multidimensional analysis

---

### Dual-Axis Chart

```yaml
$exhibits${
type: line_chart
title: Price and Volume
x: trade_date
y: close
y_label: Price
y2: volume
y2_label: Volume
}
```

**Rendered As**: Two y-axes (left and right) for different scales

---

## Data Display Examples

### Table

```yaml
$exhibits${
type: table
title: Recent Prices
source: equity.fact_equity_prices
columns: [ticker, trade_date, open, high, low, close, volume]
sortable: true
pagination: true
page_size: 50
download: true
searchable: true
}
```

**Features**:
- Sortable columns
- Pagination
- CSV download
- Search/filter

---

### Metric Cards

```yaml
$exhibits${
type: metric_cards
title: Key Metrics
metrics:
  - measure: avg_close_price
    label: Average Price
    aggregation: avg
  - measure: total_volume
    label: Total Volume
    aggregation: sum
  - measure: price_change
    label: Price Change
    aggregation: change
}
```

**Rendered As**: Grid of metric cards showing values and trends

---

## Exhibit Configuration

### Common Fields

```yaml
$exhibits${
type: chart_type              # Required
title: Display Title          # Optional
description: Subtitle         # Optional
source: model.table           # Optional (can query multiple)
x: x_column                   # X-axis column
y: y_column                   # Y-axis column or list
color: color_by_column        # Color grouping
size: size_by_column          # Size encoding (scatter only)
legend: true                  # Show legend (default: true)
interactive: true             # Interactive features (default: true)
}
```

---

## Advanced Features

### Measure Selector

```yaml
$exhibits${
type: line_chart
x: trade_date
measure_selector:
  available_measures: [close, open, high, low]
  default_measures: [close]
  label: Select Metrics
  allow_multiple: true
}
```

**Rendered As**: Dropdown to select which measures to display

---

### Dimension Selector

```yaml
$exhibits${
type: bar_chart
y: volume
dimension_selector:
  available_dimensions: [ticker, exchange_id, sector]
  default_dimension: ticker
  label: Group By
  applies_to: color
}
```

**Rendered As**: Radio buttons to change grouping dimension

---

### Collapsible Exhibits

```yaml
$exhibits${
type: table
collapsible: true
collapsible_title: Click to expand data table
collapsible_expanded: false
columns: [ticker, date, close]
}
```

**Rendered As**: Expandable section containing the exhibit

---

## Exhibit Rendering

**File**: `app/notebook/exhibits/renderer.py`

```python
class ExhibitRenderer:
    def render_exhibit(self, exhibit):
        """Route to appropriate renderer based on type."""
        if exhibit.type == ExhibitType.LINE_CHART:
            return self.render_line_chart(exhibit)
        elif exhibit.type == ExhibitType.TABLE:
            return self.render_table(exhibit)
        # ...

    def render_line_chart(self, exhibit):
        """Render Plotly line chart."""
        import plotly.express as px

        # Get data
        df = self.get_exhibit_data(exhibit)

        # Create figure
        fig = px.line(
            df,
            x=exhibit.x_axis.dimension,
            y=exhibit.y_axis.measure,
            color=exhibit.color_by,
            title=exhibit.title
        )

        # Render in Streamlit
        st.plotly_chart(fig, use_container_width=True)
```

---

## Data Loading

Exhibits load data via UniversalSession:

```python
def get_exhibit_data(self, exhibit):
    """Load data for exhibit with filters."""
    # Apply current filter state
    filters = st.session_state.get('filters', {})

    # Query data
    df = self.session.query(f"""
        SELECT {', '.join(exhibit.columns)}
        FROM {exhibit.source}
    """, filters=filters)

    return df
```

---

## Plotly Configuration

**Features**:
- Interactive hover tooltips
- Zoom and pan
- Legend toggle
- Download as PNG
- Responsive sizing

**Example Configuration**:
```python
fig.update_layout(
    template='plotly_white',
    hovermode='x unified',
    showlegend=True,
    height=500
)
```

---

## Related Documentation

- [Notebook System](notebook-system.md) - Exhibit embedding in notebooks
- [NotebookParser](notebook-parser.md) - Parsing exhibit syntax
- [Filter Engine](filter-engine-ui.md) - Filtering exhibit data
- [Streamlit App](streamlit-app.md) - UI rendering
