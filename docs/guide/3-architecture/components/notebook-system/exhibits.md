# Notebook System - Exhibits

## Overview

**Exhibits** are visualization specifications that define how data should be queried and rendered. Each exhibit type has specific rendering logic.

## Exhibit Types

### Line Chart

```json
{
  "type": "line_chart",
  "title": "Stock Prices Over Time",
  "query": {
    "model": "company",
    "table": "fact_prices",
    "measures": ["close", "volume"]
  },
  "x_axis": "date",
  "y_axis": "close",
  "group_by": "ticker",
  "color_by": "ticker"
}
```

### Bar Chart

```json
{
  "type": "bar_chart",
  "title": "Volume by Ticker",
  "query": {
    "model": "company",
    "table": "fact_prices",
    "measures": ["volume"],
    "aggregation": "sum(volume)",
    "group_by": ["ticker"]
  },
  "x_axis": "ticker",
  "y_axis": "volume",
  "orientation": "vertical"
}
```

### Data Table

```json
{
  "type": "data_table",
  "title": "Price Data",
  "query": {
    "model": "company",
    "table": "fact_prices",
    "measures": ["date", "ticker", "close", "volume"]
  },
  "sortable": true,
  "filterable": true,
  "page_size": 50
}
```

### Metric Cards

```json
{
  "type": "metric_cards",
  "metrics": [
    {
      "name": "Average Price",
      "query": {
        "model": "company",
        "table": "fact_prices",
        "aggregation": "avg(close)"
      },
      "format": "currency",
      "icon": "dollar"
    },
    {
      "name": "Total Volume",
      "query": {
        "model": "company",
        "table": "fact_prices",
        "aggregation": "sum(volume)"
      },
      "format": "number",
      "icon": "activity"
    }
  ]
}
```

### Forecast Chart

```json
{
  "type": "forecast_chart",
  "title": "Price Forecast",
  "query": {
    "model": "forecast",
    "table": "fact_forecasts"
  },
  "historical_query": {
    "model": "company",
    "table": "fact_prices"
  },
  "x_axis": "date",
  "y_axis": "forecast",
  "confidence_interval": true
}
```

## Exhibit Base Class

```python
# File: app/notebook/exhibits/base.py:15-80

class BaseExhibit(ABC):
    """Abstract base for all exhibits."""

    exhibit_type: str = "base"

    def __init__(self, config: Dict):
        self.config = config
        self.title = config.get('title', '')
        self.query = config.get('query', {})

    @abstractmethod
    def render(self, data: pd.DataFrame) -> Any:
        """
        Render exhibit with data.

        Args:
            data: Pandas DataFrame with query results

        Returns:
            Rendered visualization (Plotly figure, HTML, etc.)
        """
        pass

    def validate_config(self):
        """Validate exhibit configuration."""
        required_fields = ['query']
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required field: {field}")

    def validate_data(self, data: pd.DataFrame):
        """Validate data meets exhibit requirements."""
        if data.empty:
            raise ValueError(f"No data returned for exhibit: {self.title}")
```

## Chart Exhibit Implementation

```python
# File: app/notebook/exhibits/charts.py:30-150

class LineChartExhibit(BaseExhibit):
    """Line chart exhibit."""

    exhibit_type = "line_chart"

    def render(self, data: pd.DataFrame):
        """Render line chart using Plotly."""
        import plotly.express as px

        x_axis = self.config.get('x_axis', 'date')
        y_axis = self.config.get('y_axis', 'value')
        color_by = self.config.get('color_by')
        group_by = self.config.get('group_by')

        # Create line chart
        fig = px.line(
            data,
            x=x_axis,
            y=y_axis,
            color=color_by or group_by,
            title=self.title,
            labels={
                x_axis: x_axis.replace('_', ' ').title(),
                y_axis: y_axis.replace('_', ' ').title()
            }
        )

        # Apply styling
        fig.update_layout(
            hovermode='x unified',
            showlegend=True,
            height=self.config.get('height', 400)
        )

        return fig

class BarChartExhibit(BaseExhibit):
    """Bar chart exhibit."""

    exhibit_type = "bar_chart"

    def render(self, data: pd.DataFrame):
        """Render bar chart using Plotly."""
        import plotly.express as px

        x_axis = self.config.get('x_axis')
        y_axis = self.config.get('y_axis')
        orientation = self.config.get('orientation', 'vertical')

        fig = px.bar(
            data,
            x=x_axis,
            y=y_axis,
            title=self.title,
            orientation='v' if orientation == 'vertical' else 'h'
        )

        return fig
```

## Table Exhibit Implementation

```python
# File: app/notebook/exhibits/tables.py:20-100

class DataTableExhibit(BaseExhibit):
    """Data table exhibit."""

    exhibit_type = "data_table"

    def render(self, data: pd.DataFrame):
        """Render data table."""
        import streamlit as st

        # Apply formatting
        formatters = self.config.get('formatters', {})
        if formatters:
            for col, fmt in formatters.items():
                if col in data.columns:
                    if fmt == 'currency':
                        data[col] = data[col].apply(lambda x: f"${x:,.2f}")
                    elif fmt == 'percent':
                        data[col] = data[col].apply(lambda x: f"{x:.2%}")
                    elif fmt == 'number':
                        data[col] = data[col].apply(lambda x: f"{x:,.0f}")

        # Display table
        st.dataframe(
            data,
            use_container_width=True,
            height=self.config.get('height', 400)
        )
```

## Metric Cards Implementation

```python
# File: app/notebook/exhibits/metrics.py:20-120

class MetricCardsExhibit(BaseExhibit):
    """Metric cards exhibit."""

    exhibit_type = "metric_cards"

    def render(self, metrics_data: List[Dict]):
        """
        Render metric cards.

        Args:
            metrics_data: List of {name, value, delta} dicts
        """
        import streamlit as st

        # Create columns
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

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/notebook-system/exhibits.md`
