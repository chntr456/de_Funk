

# Dynamic Filter System

## Overview

The new dynamic filter system provides database-driven, session-aware filtering with automatic option loading and fuzzy search support. Filters are defined inline using `$filter${...}` syntax and render in the sidebar.

## Key Features

- **Database-Driven**: Options pulled directly from your data
- **No Static Lists**: Never hardcode values - they update automatically
- **Fuzzy Search**: Find values quickly with fuzzy matching
- **Session State**: Filters persist across interactions
- **SQL Generation**: Automatic WHERE clause generation
- **Type Inference**: Smart detection of filter types
- **Clean UI**: Filters appear only in sidebar, not in notebook view

## Syntax

```markdown
$filter${
  id: column_name
  label: Display Label
  type: select|date_range|number_range|text_search|boolean|slider
  operator: in|between|gte|lte|equals|contains|fuzzy
  source: model.table.column
  multi: true
  default: value
  help_text: Helper text
}
```

## Filter Types

### 1. Select Filter (Single or Multi)

**Multi-Select** (default):
```markdown
$filter${
  id: ticker
  label: Stock Tickers
  type: select
  multi: true
  source: company.dim_company.ticker
}
```

**Single-Select**:
```markdown
$filter${
  id: exchange
  label: Exchange
  type: select
  multi: false
  source: company.dim_exchange.exchange_code
}
```

**Simple source format**:
```markdown
source: company.dim_company.ticker
# Is shorthand for:
source: {model: company, table: dim_company, column: ticker}
```

### 2. Date Range Filter

```markdown
$filter${
  id: trade_date
  type: date_range
  label: Date Range
  operator: between
  default: {start: "2024-01-01", end: "2024-12-31"}
  help_text: Select date range for analysis
}
```

**Relative dates** (coming soon):
```markdown
default: {start: "-30d", end: "today"}
```

### 3. Number Range Filter

```markdown
$filter${
  id: price
  type: number_range
  label: Price Range
  operator: between
  min_value: 0
  max_value: 1000
  step: 10
  default: {min: 0, max: 500}
}
```

### 4. Slider Filter

For single numeric values:
```markdown
$filter${
  id: volume
  type: slider
  label: Minimum Volume
  min_value: 0
  max_value: 100000000
  step: 1000000
  default: 0
  operator: gte
}
```

### 5. Text Search Filter

```markdown
$filter${
  id: company_name
  type: text_search
  label: Search Company
  operator: contains
  placeholder: Enter company name...
  fuzzy_enabled: true
  fuzzy_threshold: 0.6
}
```

### 6. Boolean Filter

```markdown
$filter${
  id: is_active
  type: boolean
  label: Active Only
  default: true
}
```

## Source Configuration

### Simple Format

```markdown
source: model.table.column
```

### Advanced Format

```markdown
source: {
  model: company,
  table: dim_company,
  column: ticker,
  distinct: true,
  sort: true,
  limit: 100
}
```

**Options**:
- `model`: Model name (required)
- `table`: Table name (required)
- `column`: Column name (required)
- `distinct`: Get distinct values only (default: true)
- `sort`: Sort values alphabetically (default: true)
- `limit`: Maximum number of options (optional)

## Operators

### Comparison Operators

- `equals`: Exact match (`=`)
- `not_equals`: Not equal (`!=`)
- `gt`: Greater than (`>`)
- `gte`: Greater than or equal (`>=`)
- `lt`: Less than (`<`)
- `lte`: Less than or equal (`<=`)
- `between`: Range (`BETWEEN`)
- `in`: In list (`IN`)
- `not_in`: Not in list (`NOT IN`)

### Text Operators

- `contains`: Contains substring (`LIKE '%value%'`)
- `starts_with`: Starts with (`LIKE 'value%'`)
- `ends_with`: Ends with (`LIKE '%value'`)
- `fuzzy`: Fuzzy matching with threshold

## Type Inference

If you don't specify a `type`, the system auto-detects:

```markdown
$filter${
  id: trade_date
  # type is inferred as date_range from operator
  operator: between
  default: {start: "2024-01-01", end: "2024-12-31"}
}
```

```markdown
$filter${
  id: ticker
  # type is inferred as select from source
  source: company.dim_company.ticker
}
```

## Static Options

Instead of database source, provide static list:

```markdown
$filter${
  id: category
  label: Category
  options: [Technology, Finance, Healthcare, Energy]
  default: [Technology]
}
```

## Examples

### Complete Stock Analysis Filters

```markdown
---
id: stock_analysis
title: Stock Analysis
models: [company]
---

$filter${
  id: trade_date
  type: date_range
  label: Date Range
  operator: between
  default: {start: "2024-01-01", end: "2024-12-31"}
  help_text: Select the date range for analysis
}

$filter${
  id: ticker
  label: Stock Tickers
  type: select
  multi: true
  source: company.dim_company.ticker
  help_text: Select stocks (loaded from database)
}

$filter${
  id: volume
  label: Minimum Volume
  type: slider
  min_value: 0
  max_value: 100000000
  step: 1000000
  default: 0
  operator: gte
  help_text: Filter by minimum trading volume
}

$filter${
  id: market_cap
  label: Market Cap Range
  type: number_range
  min_value: 0
  max_value: 5000000000000
  operator: between
  help_text: Filter by market capitalization
}

# Analysis Content...
```

### City Finance Analysis

```markdown
$filter${
  id: permit_date
  type: date_range
  label: Permit Date Range
  operator: between
  default: {start: "-90d", end: "today"}
}

$filter${
  id: permit_type
  label: Permit Type
  source: city_finance.dim_permits.permit_type
  multi: true
}

$filter${
  id: amount
  label: Minimum Amount
  type: slider
  min_value: 0
  max_value: 10000000
  default: 100000
  operator: gte
}
```

### Macro Economic Filters

```markdown
$filter${
  id: indicator
  label: Economic Indicator
  source: macro.dim_indicators.indicator_name
  multi: false
}

$filter${
  id: date
  type: date_range
  label: Date Range
  operator: between
}

$filter${
  id: geography
  label: Geography
  source: macro.dim_geography.region
  multi: true
}
```

## Migration from Old System

### Before (Old System)

```markdown
# Filters

- **Date Range**: trade_date (2024-01-01 to 2024-01-05) [date_range]
- **Stock Tickers**: ticker (AAPL, GOOGL, MSFT) [multi_select]
- **Min Volume**: volume (0) [number]
```

**Problems**:
- Static options hardcoded
- Rendered in notebook view
- Limited functionality
- Hard to maintain

### After (New System)

```markdown
$filter${
  id: trade_date
  type: date_range
  label: Date Range
  default: {start: "2024-01-01", end: "2024-01-05"}
}

$filter${
  id: ticker
  label: Stock Tickers
  source: company.dim_company.ticker
}

$filter${
  id: volume
  label: Minimum Volume
  type: slider
  min_value: 0
  default: 0
}
```

**Benefits**:
- Dynamic database-driven options
- Only in sidebar (clean UI)
- More filter types
- Better UX

## Backend Integration

### SQL Generation

Filters automatically generate SQL WHERE clauses:

```python
filter_collection.build_sql_conditions()
# Returns: ["trade_date BETWEEN '2024-01-01' AND '2024-12-31'",
#           "ticker IN ('AAPL', 'GOOGL')",
#           "volume >= 1000000"]
```

### Session State

Filters persist in Streamlit session state:

```python
# Access current filter values
filter_values = filter_collection.get_active_filters()
# {'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'},
#  'ticker': ['AAPL', 'GOOGL'],
#  'volume': 1000000}
```

### Data Queries

Filters integrate seamlessly with exhibits:

```python
# Filters are automatically applied to all exhibits
# No manual filter application needed!
```

## Advanced Features

### Fuzzy Search (Coming Soon)

```markdown
$filter${
  id: company_name
  type: text_search
  label: Company Search
  operator: fuzzy
  fuzzy_enabled: true
  fuzzy_threshold: 0.6
  help_text: Type company name (fuzzy matching)
}
```

Fuzzy matching allows:
- Typo tolerance: "Googl" matches "Google"
- Partial matching: "micro" matches "Microsoft"
- Phonetic matching: "fase" matches "phase"

### Cascading Filters (Coming Soon)

```markdown
$filter${
  id: country
  source: company.dim_geography.country
}

$filter${
  id: state
  source: company.dim_geography.state
  depends_on: country  # Only show states for selected countries
}
```

### Dynamic Min/Max (Coming Soon)

```markdown
$filter${
  id: price
  type: slider
  min_value: auto  # Automatically get from data
  max_value: auto
  source: company.fact_prices.close
}
```

## Best Practices

1. **Use Database Sources**: Always prefer `source` over static `options`
2. **Descriptive Labels**: Use clear, user-friendly labels
3. **Help Text**: Add `help_text` to explain filters
4. **Sensible Defaults**: Provide good default values
5. **Appropriate Types**: Choose the right filter type for your data
6. **Limit Options**: Use `limit` for very large option lists
7. **Operators**: Use appropriate operators (e.g., `gte` for minimum thresholds)

## Troubleshooting

### Filter Options Not Loading

**Problem**: No options appear in select filter

**Solutions**:
1. Check source format: `model.table.column`
2. Verify model is in front matter `models:` list
3. Ensure table and column exist
4. Check data is available in database

### Filter Not Applying

**Problem**: Filter doesn't affect exhibits

**Solutions**:
1. Verify filter `id` matches column name in data
2. Use `apply_to` if column name is different
3. Check operator is appropriate for data type
4. Ensure filter has a value selected

### Performance Issues

**Problem**: Filters slow to load

**Solutions**:
1. Add `limit` to source configuration
2. Use caching (enabled by default)
3. Pre-aggregate if possible
4. Consider indexed columns

## Future Enhancements

- [ ] Fuzzy search with Levenshtein distance
- [ ] Cascading/dependent filters
- [ ] Dynamic min/max from data
- [ ] Filter presets (save/load filter combinations)
- [ ] Filter groups (collapsible sections)
- [ ] Multi-column sources (e.g., "ticker - company_name")
- [ ] Date shortcuts ("Last 7 days", "Month to date")
- [ ] Export filter state (share URLs with filters)
- [ ] Filter history (recently used values)
- [ ] Smart suggestions (frequently used combinations)

## See Also

- [Markdown Notebook Specification](/docs/markdown_notebook_spec.md)
- [Filter Schema](/app/notebook/filters/dynamic.py)
- [Examples](/configs/notebooks/stock_analysis_dynamic.md)
