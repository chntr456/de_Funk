---
id: dimension_selector_demo
title: Measure Selector and Collapsible Exhibits Demo
description: Demonstrating dynamic measure selection and collapsible exhibits with equity model
tags: [demo, measure-selector, collapsible, equity]
models: [equity]
author: analyst@company.com
created: 2025-01-01
updated: 2025-11-13
---

$filter${
  id: trade_date
  type: date_range
  label: Date Range
  operator: between
  default: {start: "2024-01-01", end: "2024-01-05"}
  help_text: Filter by trade date range
}

$filter${
  id: ticker
  label: Stock Tickers
  type: select
  multi: true
  source: {model: equity, table: fact_equity_prices, column: ticker}
  help_text: Select stocks to analyze
}

# Measure Selector and Collapsible Exhibits

This notebook demonstrates two powerful features using the new **equity model**:

1. **Measure Selector** - Dynamically select which measures to display on charts
2. **Collapsible Exhibits** - Hide/show exhibits in expandable sections to keep notebooks clean

**Note:** This uses the `equity` model, which replaces the deprecated `company` model.

---

## Measure Selector Examples

### Example 1: Line Chart with Dynamic Measure Selection

Select which price measures to display on the chart. Try switching between different metrics!

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  color: ticker
  title: Stock Price Trends - Dynamic Measure Selection
  description: Use the measure selector to choose which price metrics to display
  measure_selector: {
    available_measures: [open, close, high, low, volume_weighted],
    default_measures: [close],
    label: "Select Measures",
    selector_type: checkbox,
    help_text: "Choose which price measures to display"
  }
  interactive: true
  collapsible: true
  collapsible_title: "📈 Price Trends (Click to expand/collapse)"
  collapsible_expanded: true
}

**Available Measures from equity.fact_equity_prices:**
- `open`: Opening price
- `close`: Closing price
- `high`: Highest intraday price
- `low`: Lowest intraday price
- `volume_weighted`: Volume-weighted average price (VWAP)
- `market_cap`: Market capitalization
- `volume`: Trading volume

---

### Example 2: Bar Chart with Measure Selector

Compare different metrics across stocks. The measure selector lets you quickly switch perspectives!

$exhibits${
  type: bar_chart
  source: equity.fact_equity_prices
  x: ticker
  y: volume
  color: ticker
  title: Metric Comparison
  description: Switch measures to see different metrics from various perspectives
  measure_selector: {
    available_measures: [volume, close, high, low, open, market_cap],
    default_measures: [volume],
    label: "Select Metric",
    selector_type: selectbox,
    help_text: "Choose which metric to compare"
  }
  interactive: true
  collapsible: true
  collapsible_title: "📊 Metric Comparison"
  collapsible_expanded: false
}

**Selectbox vs Checkbox:**
- `selectbox`: Single selection (dropdown)
- `checkbox`: Multiple selections allowed

---

## Collapsible Exhibits

Keep your notebook organized by hiding detailed exhibits until needed.

### Example 3: Collapsible Metric Cards

$exhibits${
  type: metric_cards
  source: equity.fact_equity_prices
  metrics: [
    { measure: close, label: "Avg Close", aggregation: avg },
    { measure: volume, label: "Total Volume", aggregation: sum },
    { measure: high, label: "Max High", aggregation: max }
  ]
  collapsible: true
  collapsible_title: "💳 Key Metrics"
  collapsible_expanded: false
}

---

### Example 4: Multiple Measure Selector with Collapsible

This exhibit combines all features:
- Measure selector for choosing which metrics to display
- Collapsible section to keep things tidy
- Interactive charting

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  color: ticker
  title: Advanced Multi-Selector Chart
  description: Use measure selector to view multiple metrics simultaneously
  measure_selector: {
    available_measures: [open, close, high, low, volume_weighted],
    default_measures: [close, high, low],
    label: "Select Price Measures",
    selector_type: checkbox,
    help_text: "Choose which price metrics to display (multiple allowed)"
  }
  interactive: true
  collapsible: true
  collapsible_title: "🎯 Advanced Analysis (All Features Combined)"
  collapsible_expanded: true
}

---

## Technical Indicators (New!)

The equity model includes technical indicators table:

### Example 5: Technical Indicators with Measure Selector

$exhibits${
  type: line_chart
  source: equity.fact_equity_technicals
  x: trade_date
  y: rsi_14
  color: ticker
  title: Technical Indicators
  description: View RSI, MACD, Bollinger Bands, and more
  measure_selector: {
    available_measures: [rsi_14, macd, macd_signal, bollinger_upper, bollinger_lower, sma_20, sma_50],
    default_measures: [rsi_14],
    label: "Select Technical Indicator",
    selector_type: selectbox,
    help_text: "Choose which technical indicator to display"
  }
  interactive: true
  collapsible: true
  collapsible_title: "🔧 Technical Indicators"
  collapsible_expanded: false
}

**Technical Indicators Available:**
- `rsi_14`: 14-day Relative Strength Index
- `macd`: MACD line
- `macd_signal`: MACD signal line
- `bollinger_upper/lower`: Bollinger Bands
- `sma_20/50/200`: Simple Moving Averages
- `ema_12/26`: Exponential Moving Averages
- `volatility_20d/60d`: Rolling volatility
- `beta`: Beta vs. market

---

## How to Use

### Measure Selector

Add a `measure_selector` to any chart exhibit:

```markdown
measure_selector: {
  available_measures: [open, close, high, low],
  default_measures: [close],
  label: "Select Measures",
  selector_type: checkbox,
  help_text: "Choose which measures to display"
}
```

**Properties:**
- `available_measures`: List of measure columns users can choose from
- `default_measures`: Which measures to display initially
- `label`: Label shown above the selector
- `selector_type`: `checkbox` (multi-select) or `selectbox` (single select)
- `help_text`: Help text shown to users

---

### Collapsible Exhibits

Make any exhibit collapsible:

```markdown
collapsible: true
collapsible_title: "📊 My Chart Title"
collapsible_expanded: false
```

**Properties:**
- `collapsible`: Set to `true` to make exhibit collapsible
- `collapsible_title`: Title for the collapsible section (defaults to exhibit title)
- `collapsible_expanded`: Whether section starts expanded (`true`) or collapsed (`false`)

---

## Benefits

**Measure Selector:**
- Quickly explore different metrics without creating multiple exhibits
- Users control which data they want to view
- Common use cases: switching between price measures (open, close, high, low), volume metrics, technical indicators, or calculated fields

**Collapsible Exhibits:**
- Keep notebooks clean and organized
- Hide detailed analysis until needed
- Better user experience for long notebooks
- Focus on key insights, details available on demand

---

## Example Use Cases

1. **Price Analysis**: Switch between viewing open, close, high, low prices
2. **Technical Analysis**: Toggle between RSI, MACD, Bollinger Bands, moving averages
3. **Volume Analysis**: Compare total volume vs. average volume vs. volume-weighted prices
4. **Multi-Metric Comparison**: Display multiple measures simultaneously on the same chart
5. **Progressive Disclosure**: Start with summary metrics, expand to detailed tables

---

## Data Tables with Measure Flexibility

### Example 6: Data Table with All Metrics

View detailed data in table format:

$exhibits${
  type: data_table
  source: equity.fact_equity_prices
  download: true
  collapsible: true
  collapsible_title: "📋 View Full Data Table (Exportable)"
  collapsible_expanded: false
}

---

## Important Notes

**Equity Model Tables:**
- `fact_equity_prices`: ticker, trade_date, open, high, low, close, volume_weighted, volume, market_cap, transactions
- `fact_equity_technicals`: ticker, trade_date, rsi_14, macd, sma_20, sma_50, sma_200, bollinger_upper, bollinger_lower, volatility_20d, beta, etc.
- `fact_equity_news`: News sentiment data
- `dim_equity`: Equity instrument master
- `dim_exchange`: Exchange reference

**Building the Equity Model:**

If you see errors about missing tables, you need to build the equity model from bronze data:

```bash
# Build equity model from existing bronze data
python scripts/build_all_models.py --models equity --skip-ingestion

# Or build all models
python scripts/build_all_models.py --skip-ingestion
```

**Performance:**
- Measure selectors are client-side UI controls (fast)
- Data filtering happens server-side (optimized)
- Collapsible sections improve page load performance by deferring rendering

---

## Migration from Company Model

This notebook has been updated from the deprecated `company` model to the new `equity` model:

**Old (Deprecated):**
- `company.fact_prices` → **NEW:** `equity.fact_equity_prices`
- `company.fact_news` → **NEW:** `equity.fact_equity_news`
- `company.dim_company` → **NEW:** `equity.dim_equity` + `corporate.dim_corporate`

**New Features in Equity Model:**
- Technical indicators table (`fact_equity_technicals`)
- Market cap column included in prices
- Better separation: equity (trading) vs. corporate (fundamentals)
- Cross-model relationships to corporate model

---

*This notebook demonstrates the new equity model with interactive measure selectors and collapsible exhibits for a modern analytical experience.*
