# Weighted Aggregate Graphics Feature (Model-Based)

## Overview

The weighted aggregate graphics feature allows you to create dynamic visualizations that aggregate stock data across multiple securities using various weighting methods. This is particularly useful for creating custom indices, portfolio views, and comparative analyses.

**Architecture:** Calculations are performed in the model/silver layer using DuckDB for optimal performance. The UI only handles rendering - no business logic.

## Quick Start

### 1. Build Weighted Aggregate Views

Before using weighted aggregate charts, you need to build the weighted aggregate views:

```bash
python scripts/build_weighted_aggregates_duckdb.py
```

This creates DuckDB views for all 6 weighting methods defined in the model configuration.

### 2. Use in Notebooks

Reference the pre-defined measures in your notebook YAML:

```yaml
exhibits:
  - id: my_aggregate_index
    type: weighted_aggregate_chart
    title: "My Index"
    aggregate_by: trade_date
    value_measures:
      - equal_weighted_index
      - volume_weighted_index
      - market_cap_weighted_index
```

### 3. Run the App

```bash
streamlit run app/ui/notebook_app_duckdb.py
```

## Features

### Supported Weighting Methods

1. **Equal Weighted** (`equal`)
   - All stocks weighted equally (simple average)
   - Best for: Unbiased sector or thematic indices
   - Formula: `Σ(value) / N`

2. **Volume Weighted** (`volume`)
   - Weighted by trading volume
   - Best for: Liquidity-focused indices
   - Formula: `Σ(value × volume) / Σ(volume)`

3. **Price Weighted** (`price`)
   - Weighted by stock price
   - Best for: Traditional indices like Dow Jones
   - Formula: `Σ(value × price) / Σ(price)`

4. **Market Cap Weighted** (`market_cap`)
   - Weighted by market capitalization (price × volume as proxy)
   - Best for: Broad market indices like S&P 500
   - Formula: `Σ(value × price × volume) / Σ(price × volume)`

5. **Volume Deviation Weighted** (`volume_deviation`)
   - Weighted by difference from average volume × price
   - Best for: Identifying unusual trading activity
   - Formula: `Σ(value × |volume - avg_volume| × price) / Σ(|volume - avg_volume| × price)`

6. **Inverse Volatility Weighted** (`volatility`)
   - Weighted by inverse of daily price range
   - Best for: Risk-adjusted indices
   - Formula: `Σ(value / daily_range) / Σ(1 / daily_range)`

### Interactive Features

- **Multi-Method Display**: Show multiple weighting methods side-by-side
- **Interactive Legend**: Click to show/hide individual methods
- **Multiple Metrics**: Display multiple aggregated indices simultaneously
- **Summary Statistics**: View detailed statistics about each aggregate
- **Export Capability**: Download charts as PNG images
- **Fast Performance**: Pre-calculated views mean instant rendering

## Configuration

### Model Configuration (configs/models/company.yaml)

Define weighted aggregate measures in your model configuration:

```yaml
measures:
  equal_weighted_index:
    description: "Equal weighted price index across stocks"
    type: weighted_aggregate
    source: fact_prices.close
    weighting_method: equal
    group_by: [trade_date]
    format: "$#,##0.00"

  volume_weighted_index:
    description: "Volume weighted price index across stocks"
    type: weighted_aggregate
    source: fact_prices.close
    weighting_method: volume
    group_by: [trade_date]
    format: "$#,##0.00"
```

### Notebook YAML Configuration

Reference the model measures in your notebook:

```yaml
exhibits:
  - id: aggregate_price_index
    type: weighted_aggregate_chart
    title: "Aggregate Price Index"
    description: "Combined price index across selected stocks"
    aggregate_by: trade_date
    value_measures:
      - equal_weighted_index
      - volume_weighted_index
      - market_cap_weighted_index
```

### Configuration Parameters

- **`id`** (required): Unique identifier for the exhibit
- **`type`** (required): Must be `weighted_aggregate_chart`
- **`title`** (required): Display title
- **`description`** (optional): Description text
- **`aggregate_by`** (required): Dimension to aggregate by (e.g., "trade_date")
- **`value_measures`** (required): List of model measure IDs to display

### Multi-Measure Example

Display price, volume, and VWAP in one chart:

```yaml
exhibits:
  - id: multi_measure_aggregate
    type: weighted_aggregate_chart
    title: "Multi-Measure Aggregate Index"
    source: "company.fact_prices"
    aggregate_by: trade_date
    value_measures: ["close", "volume", "volume_weighted"]
    weighting:
      method: market_cap
      normalize: true
```

## Use Cases

### 1. Custom Sector Index

Create an equal-weighted tech sector index:

```yaml
variables:
  ticker:
    type: multi_select
    default: ["AAPL", "GOOGL", "MSFT", "META", "NVDA"]

exhibits:
  - id: tech_sector_index
    type: weighted_aggregate_chart
    title: "Tech Sector Index (Equal Weighted)"
    source: "company.fact_prices"
    aggregate_by: trade_date
    value_measures: ["close"]
    weighting:
      method: equal
```

### 2. Market Cap Weighted Portfolio

Track a market-cap weighted portfolio:

```yaml
exhibits:
  - id: portfolio_index
    type: weighted_aggregate_chart
    title: "Portfolio Index (Market Cap Weighted)"
    source: "company.fact_prices"
    aggregate_by: trade_date
    value_measures: ["close"]
    weighting:
      method: market_cap
      normalize: true
```

### 3. Volume Activity Index

Monitor unusual trading volume:

```yaml
exhibits:
  - id: volume_activity_index
    type: weighted_aggregate_chart
    title: "Volume Activity Index"
    source: "company.fact_prices"
    aggregate_by: trade_date
    value_measures: ["volume"]
    weighting:
      method: volume_deviation
```

## Data Requirements

The weighted aggregate chart expects the following columns in your data source:

### Required Columns
- **`trade_date`**: Trading date (for time series aggregation)
- One or more value columns specified in `value_measures`

### Optional Columns (depending on weighting method)
- **`volume`**: Trading volume (for volume, market_cap, volume_deviation methods)
- **`close`**: Closing price (for price, market_cap methods)
- **`high`**, **`low`**: High/low prices (for volatility method)
- **`ticker`**: Stock symbol (for grouping)

## Interactive Usage

Once the exhibit is rendered in the Streamlit app:

1. **Select Weighting Method**: Use the dropdown to change weighting methods
2. **Toggle Normalization**: Check/uncheck the normalize option
3. **View Summary Statistics**: Expand the statistics section to see detailed stats
4. **Export Chart**: Use the camera icon in the chart toolbar to export as PNG
5. **Interact with Chart**: Hover for details, zoom, pan, or select regions

## Schema Extensions

The following schema elements were added to support this feature:

### New Exhibit Type

```python
class ExhibitType(Enum):
    WEIGHTED_AGGREGATE_CHART = "weighted_aggregate_chart"
```

### New Weighting Methods Enum

```python
class WeightingMethod(Enum):
    EQUAL = "equal"
    MARKET_CAP = "market_cap"
    VOLUME = "volume"
    PRICE = "price"
    CUSTOM = "custom"
    VOLUME_DEVIATION = "volume_deviation"
    VOLATILITY = "volatility"
```

### New Configuration Classes

```python
@dataclass
class WeightingConfig:
    method: WeightingMethod
    weight_column: Optional[str] = None
    expression: Optional[str] = None
    normalize: bool = True

@dataclass
class Exhibit:
    # ... existing fields ...
    weighting: Optional[WeightingConfig] = None
    aggregate_by: Optional[str] = None
    value_measures: Optional[List[str]] = None
    group_by: Optional[str] = None
```

## Technical Implementation

### Calculation Logic

The weighted aggregate is calculated as follows:

1. **Group by dimension**: Group data by `aggregate_by` (e.g., trade_date)
2. **Calculate weights**: For each group, calculate weights based on the selected method
3. **Normalize weights**: Optionally normalize weights to sum to 1
4. **Compute weighted average**: `weighted_avg = Σ(value × weight)`
5. **Handle edge cases**: Remove NaN values, handle zero weights

### Performance Considerations

- Calculations are performed in-memory using NumPy for efficiency
- Large datasets (>100k rows) may experience slight delays
- Consider filtering data to relevant date ranges for better performance

## Example Notebook

A complete example notebook is available at:
`configs/notebooks/aggregate_stock_analysis.yaml`

This notebook demonstrates:
- Single and multi-measure aggregates
- Different weighting methods
- Comparison with individual stock charts
- Export and analysis features

## Troubleshooting

### Common Issues

1. **"Measure not found in data"**
   - Ensure the measure exists in your data source
   - Check that the source table is correctly specified

2. **"Unable to calculate weighted aggregates"**
   - Verify that required columns for the weighting method exist
   - Check for sufficient non-null data

3. **NaN values in chart**
   - Some groups may not have sufficient data for the selected weighting method
   - Try a simpler method like "equal" to diagnose

### Debug Mode

Enable debug mode by adding a checkbox in your notebook:

```yaml
exhibits:
  - id: aggregate_index
    type: weighted_aggregate_chart
    # ... configuration ...
    options:
      show_debug: true
```

This will display:
- Sample of underlying data
- Weight calculations
- Summary statistics

## API Reference

### Main Function

```python
def render_weighted_aggregate_chart(exhibit, pdf: pd.DataFrame)
```

Renders the weighted aggregate chart with interactive controls.

**Parameters:**
- `exhibit`: Exhibit configuration object
- `pdf`: Pandas DataFrame with stock data

### Helper Functions

```python
def calculate_weighted_aggregate(
    df: pd.DataFrame,
    value_col: str,
    weight_method: str,
    weight_col: Optional[str] = None,
    normalize: bool = True
) -> pd.DataFrame
```

Calculates weighted aggregate for a given weighting method.

## Future Enhancements

Potential future additions:
- Custom weighting expressions
- Rolling window aggregates
- Multi-group aggregation (e.g., by sector and date)
- Benchmark comparison overlays
- Statistical significance tests
- Export to Excel with full calculations

## Support

For questions or issues:
1. Check the example notebook at `configs/notebooks/aggregate_stock_analysis.yaml`
2. Review the implementation at `app/ui/components/exhibits/weighted_aggregate_chart.py`
3. Consult the schema documentation at `app/notebook/schema.py`
