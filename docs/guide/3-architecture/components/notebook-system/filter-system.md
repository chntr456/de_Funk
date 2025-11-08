# Notebook System - Filter System

## Overview

The **Filter System** provides dynamic filter UI generation, hierarchical filter merging, and persistent filter contexts across notebooks in the same folder.

## Architecture

```
┌────────────────────────────────────────────┐
│         Filter Hierarchy                   │
└────────────────────────────────────────────┘

Global Filters (UI-level)
    │
    └─► Folder Context (shared within folder)
            │
            └─► Exhibit Filters (exhibit-specific)
                    │
                    └─► Final Query
```

## Filter Context

```python
# File: app/notebook/filters/context.py:15-80

class FilterContext:
    """Manages filter state for a notebook."""

    def __init__(self):
        self.dimensions: Dict[str, List[str]] = {}  # dimension -> values
        self.date_ranges: Dict[str, Dict] = {}      # date dimension -> {start, end}
        self.measure_filters: Dict[str, Dict] = {}  # measure -> {min, max}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to filter dict for FilterEngine."""
        filters = {}
        
        # Add dimension filters
        filters.update(self.dimensions)
        
        # Add date range filters
        filters.update(self.date_ranges)
        
        # Add measure filters
        filters.update(self.measure_filters)
        
        return filters

    def merge(self, other: 'FilterContext') -> 'FilterContext':
        """
        Merge two filter contexts.

        Rules:
        - Dimensions: intersection (all must match)
        - Date ranges: intersection (narrowest range)
        - Measures: union (all constraints applied)
        """
        merged = FilterContext()
        
        # Merge dimensions (intersection)
        for dim, values in self.dimensions.items():
            if dim in other.dimensions:
                # Intersection of values
                merged_values = list(set(values) & set(other.dimensions[dim]))
                if merged_values:
                    merged.dimensions[dim] = merged_values
            else:
                merged.dimensions[dim] = values
        
        # Add dimensions from other
        for dim, values in other.dimensions.items():
            if dim not in merged.dimensions:
                merged.dimensions[dim] = values
        
        # Merge date ranges (intersection - narrowest)
        for dim, range_spec in self.date_ranges.items():
            if dim in other.date_ranges:
                other_range = other.date_ranges[dim]
                
                # Take latest start
                start = max(range_spec.get('start'), other_range.get('start'))
                
                # Take earliest end
                end = min(range_spec.get('end'), other_range.get('end'))
                
                if start <= end:
                    merged.date_ranges[dim] = {'start': start, 'end': end}
            else:
                merged.date_ranges[dim] = range_spec
        
        # Merge measure filters (union)
        merged.measure_filters.update(self.measure_filters)
        merged.measure_filters.update(other.measure_filters)
        
        return merged

    def clear(self):
        """Clear all filters."""
        self.dimensions.clear()
        self.date_ranges.clear()
        self.measure_filters.clear()
```

## Dynamic Filter Types

### Dimension Selector

```json
{
  "type": "dimension_selector",
  "dimension": "ticker",
  "model": "company",
  "label": "Select Tickers",
  "multi_select": true,
  "default": ["AAPL"]
}
```

### Date Range

```json
{
  "type": "date_range",
  "dimension": "date",
  "label": "Date Range",
  "default_start": "2024-01-01",
  "default_end": "2024-12-31"
}
```

### Measure Range

```json
{
  "type": "measure_range",
  "measure": "volume",
  "label": "Volume Range",
  "min": 0,
  "max": 100000000
}
```

## Dynamic Filter Generation

```python
# File: app/notebook/filters/dynamic.py:20-120

class DynamicFilterGenerator:
    """Generates filter UI components dynamically."""

    def __init__(self, session: UniversalSession):
        self.session = session

    def generate_dimension_selector(self, config: Dict) -> Any:
        """
        Generate dimension selector widget.

        Fetches distinct values from model for selection.
        """
        dimension = config['dimension']
        model_name = config.get('model', 'company')
        table_name = config.get('table', f'dim_{dimension}s')
        
        # Get distinct values
        df = self.session.get_table(model_name, table_name)
        
        if self.session.backend == 'spark':
            values = [row[dimension] for row in df.select(dimension).distinct().collect()]
        else:
            values = df.select(dimension).unique().fetchall()
            values = [v[0] for v in values]
        
        # Return widget config
        return {
            'type': 'multiselect' if config.get('multi_select') else 'selectbox',
            'label': config.get('label', dimension),
            'options': sorted(values),
            'default': config.get('default')
        }

    def generate_date_range(self, config: Dict) -> Any:
        """Generate date range selector."""
        return {
            'type': 'date_range',
            'label': config.get('label', 'Date Range'),
            'start_default': config.get('default_start'),
            'end_default': config.get('default_end')
        }

    def generate_measure_range(self, config: Dict) -> Any:
        """Generate numeric range slider."""
        measure = config['measure']
        
        # Get min/max from data
        model_name = config.get('model', 'company')
        table_name = config.get('table')
        
        df = self.session.get_table(model_name, table_name)
        
        if self.session.backend == 'spark':
            from pyspark.sql import functions as F
            stats = df.agg(
                F.min(measure).alias('min'),
                F.max(measure).alias('max')
            ).collect()[0]
        else:
            stats = df.aggregate(f"min({measure}) as min, max({measure}) as max").fetchone()
        
        return {
            'type': 'slider',
            'label': config.get('label', measure),
            'min': config.get('min', stats['min']),
            'max': config.get('max', stats['max'])
        }
```

## Usage Examples

### Example 1: Notebook with Filters

```markdown
# Stock Analysis

$filter${
  "type": "dimension_selector",
  "dimension": "ticker",
  "model": "company",
  "multi_select": true
}

$filter${
  "type": "date_range",
  "dimension": "date"
}

$exhibit${
  "type": "line_chart",
  "title": "Stock Prices",
  "query": {
    "model": "company",
    "table": "fact_prices"
  }
}
```

### Example 2: Hierarchical Filters

```python
# Global filter (all notebooks)
global_context = FilterContext()
global_context.dimensions['ticker'] = ['AAPL', 'GOOGL']

# Folder filter (notebooks in this folder)
folder_context = FilterContext()
folder_context.date_ranges['date'] = {'start': '2024-01-01', 'end': '2024-12-31'}

# Exhibit filter (this exhibit only)
exhibit_filters = {'volume': {'min': 1000000}}

# Merge for final query
final_context = global_context.merge(folder_context)
final_filters = final_context.to_dict()
final_filters.update(exhibit_filters)
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/notebook-system/filter-system.md`
