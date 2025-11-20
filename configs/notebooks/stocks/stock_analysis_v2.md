---
title: "Stock Analysis Dashboard (v2.0)"
description: "Comprehensive stock analysis with company fundamentals, price trends, and technical indicators"
model: stocks
version: 2.0
tags:
  - stocks
  - company
  - technical-analysis
  - cross-model
author: "de_Funk v2.0"
created: "2025-11-20"
---

# Stock Analysis Dashboard (v2.0)

This notebook demonstrates the v2.0 model architecture with cross-model joins between **stocks**, **company**, and **core** dimensions.

## Interactive Filters

Select stocks and date ranges to explore:

$filter${
  "type": "multi_select",
  "label": "Select Tickers",
  "column": "stocks.dim_stock.ticker",
  "default": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
}

$filter${
  "type": "date_range",
  "label": "Date Range",
  "column": "stocks.fact_stock_prices.trade_date",
  "default_days": 90
}

---

## Stock Overview

### Key Metrics by Company

Get high-level metrics for selected stocks with company information.

```sql
SELECT
    s.ticker,
    s.security_name,
    c.company_name,
    c.sector,
    c.industry,
    s.market_cap / 1e9 as market_cap_billions,
    s.shares_outstanding / 1e6 as shares_outstanding_millions,
    COUNT(DISTINCT p.trade_date) as trading_days,
    AVG(p.close) as avg_price,
    MIN(p.close) as min_price,
    MAX(p.close) as max_price,
    (MAX(p.close) - MIN(p.close)) / MIN(p.close) * 100 as price_range_pct
FROM stocks.dim_stock s
LEFT JOIN company.dim_company c ON s.company_id = c.company_id
LEFT JOIN stocks.fact_stock_prices p ON s.ticker = p.ticker
WHERE s.ticker IN ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META')
  AND p.trade_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY
    s.ticker,
    s.security_name,
    c.company_name,
    c.sector,
    c.industry,
    s.market_cap,
    s.shares_outstanding
ORDER BY market_cap_billions DESC
```

$exhibits${
  "type": "table",
  "title": "Stock Overview Metrics",
  "data": "stock_overview",
  "columns": [
    {"name": "ticker", "label": "Ticker"},
    {"name": "security_name", "label": "Security"},
    {"name": "company_name", "label": "Company"},
    {"name": "sector", "label": "Sector"},
    {"name": "market_cap_billions", "label": "Market Cap ($B)", "format": "#,##0.00"},
    {"name": "avg_price", "label": "Avg Price", "format": "$#,##0.00"},
    {"name": "price_range_pct", "label": "Price Range %", "format": "#,##0.0"}
  ]
}

---

## Price Trends

### Historical Closing Prices

Track price movements over time with cross-model context.

```sql
SELECT
    p.trade_date,
    p.ticker,
    s.security_name,
    c.sector,
    p.close,
    p.volume / 1e6 as volume_millions,
    cal.day_of_week_name,
    cal.is_weekend
FROM stocks.fact_stock_prices p
JOIN stocks.dim_stock s ON p.ticker = s.ticker
LEFT JOIN company.dim_company c ON s.company_id = c.company_id
JOIN core.dim_calendar cal ON p.trade_date = cal.date
WHERE p.ticker IN ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META')
  AND p.trade_date >= CURRENT_DATE - INTERVAL '90 days'
  AND cal.is_weekend = FALSE
ORDER BY p.trade_date, p.ticker
```

$exhibits${
  "type": "line_chart",
  "title": "Stock Price Trends (90 Days)",
  "data": "price_trends",
  "x": "trade_date",
  "y": "close",
  "group_by": "ticker",
  "y_axis_title": "Closing Price ($)",
  "x_axis_title": "Date",
  "show_legend": true
}

---

## Technical Indicators

### RSI (Relative Strength Index)

Identify overbought (>70) and oversold (<30) conditions.

```sql
SELECT
    t.trade_date,
    t.ticker,
    s.security_name,
    t.close,
    t.rsi_14,
    CASE
        WHEN t.rsi_14 > 70 THEN 'Overbought'
        WHEN t.rsi_14 < 30 THEN 'Oversold'
        ELSE 'Neutral'
    END as rsi_signal
FROM stocks.fact_stock_technicals t
JOIN stocks.dim_stock s ON t.ticker = s.ticker
WHERE t.ticker IN ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META')
  AND t.trade_date >= CURRENT_DATE - INTERVAL '90 days'
  AND t.rsi_14 IS NOT NULL
ORDER BY t.trade_date, t.ticker
```

$exhibits${
  "type": "line_chart",
  "title": "Relative Strength Index (RSI-14)",
  "data": "rsi_trends",
  "x": "trade_date",
  "y": "rsi_14",
  "group_by": "ticker",
  "y_axis_title": "RSI",
  "x_axis_title": "Date",
  "show_legend": true,
  "annotations": [
    {"y": 70, "label": "Overbought", "color": "red"},
    {"y": 30, "label": "Oversold", "color": "green"}
  ]
}

---

### Moving Averages (SMA)

Track trend strength with 20, 50, and 200-day moving averages.

```sql
SELECT
    t.trade_date,
    t.ticker,
    t.close,
    t.sma_20,
    t.sma_50,
    t.sma_200,
    CASE
        WHEN t.close > t.sma_20 AND t.sma_20 > t.sma_50 THEN 'Bullish'
        WHEN t.close < t.sma_20 AND t.sma_20 < t.sma_50 THEN 'Bearish'
        ELSE 'Neutral'
    END as trend_signal
FROM stocks.fact_stock_technicals t
WHERE t.ticker = 'AAPL'
  AND t.trade_date >= CURRENT_DATE - INTERVAL '180 days'
  AND t.sma_20 IS NOT NULL
ORDER BY t.trade_date
```

$exhibits${
  "type": "line_chart",
  "title": "Moving Averages (AAPL)",
  "data": "moving_averages",
  "x": "trade_date",
  "y": ["close", "sma_20", "sma_50", "sma_200"],
  "y_axis_title": "Price ($)",
  "x_axis_title": "Date",
  "show_legend": true,
  "line_styles": {
    "close": {"width": 2, "color": "blue"},
    "sma_20": {"width": 1, "dash": "dash", "color": "green"},
    "sma_50": {"width": 1, "dash": "dash", "color": "orange"},
    "sma_200": {"width": 1, "dash": "dash", "color": "red"}
  }
}

---

### Bollinger Bands

Visualize price volatility and potential breakouts.

```sql
SELECT
    t.trade_date,
    t.ticker,
    t.close,
    t.bollinger_middle,
    t.bollinger_upper,
    t.bollinger_lower,
    t.volatility_20d * 100 as volatility_pct
FROM stocks.fact_stock_technicals t
WHERE t.ticker = 'AAPL'
  AND t.trade_date >= CURRENT_DATE - INTERVAL '90 days'
  AND t.bollinger_middle IS NOT NULL
ORDER BY t.trade_date
```

$exhibits${
  "type": "line_chart",
  "title": "Bollinger Bands (AAPL)",
  "data": "bollinger_bands",
  "x": "trade_date",
  "y": ["close", "bollinger_upper", "bollinger_middle", "bollinger_lower"],
  "y_axis_title": "Price ($)",
  "x_axis_title": "Date",
  "show_legend": true,
  "fill_between": {
    "y1": "bollinger_upper",
    "y2": "bollinger_lower",
    "alpha": 0.2,
    "color": "gray"
  }
}

---

## Volume Analysis

### Trading Volume Trends

Identify unusual trading activity with volume ratio analysis.

```sql
SELECT
    t.trade_date,
    t.ticker,
    s.security_name,
    t.volume / 1e6 as volume_millions,
    t.volume_sma_20 / 1e6 as avg_volume_20d_millions,
    t.volume_ratio,
    CASE
        WHEN t.volume_ratio > 2.0 THEN 'High Volume'
        WHEN t.volume_ratio < 0.5 THEN 'Low Volume'
        ELSE 'Normal'
    END as volume_signal
FROM stocks.fact_stock_technicals t
JOIN stocks.dim_stock s ON t.ticker = s.ticker
WHERE t.ticker IN ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META')
  AND t.trade_date >= CURRENT_DATE - INTERVAL '90 days'
  AND t.volume_ratio IS NOT NULL
ORDER BY t.trade_date, t.ticker
```

$exhibits${
  "type": "bar_chart",
  "title": "Trading Volume (Millions)",
  "data": "volume_trends",
  "x": "trade_date",
  "y": "volume_millions",
  "group_by": "ticker",
  "y_axis_title": "Volume (M)",
  "x_axis_title": "Date",
  "show_legend": true
}

---

## Sector Analysis

### Performance by Sector

Compare stock performance grouped by company sector.

```sql
SELECT
    c.sector,
    COUNT(DISTINCT s.ticker) as num_stocks,
    AVG(p.close) as avg_price,
    AVG(t.daily_return) * 100 as avg_daily_return_pct,
    AVG(t.volatility_20d) * 100 as avg_volatility_pct,
    SUM(p.volume) / 1e9 as total_volume_billions
FROM stocks.dim_stock s
JOIN company.dim_company c ON s.company_id = c.company_id
LEFT JOIN stocks.fact_stock_prices p ON s.ticker = p.ticker
LEFT JOIN stocks.fact_stock_technicals t ON s.ticker = t.ticker AND p.trade_date = t.trade_date
WHERE p.trade_date >= CURRENT_DATE - INTERVAL '30 days'
  AND c.sector IS NOT NULL
GROUP BY c.sector
ORDER BY avg_daily_return_pct DESC
```

$exhibits${
  "type": "bar_chart",
  "title": "Average Daily Return by Sector (30 Days)",
  "data": "sector_performance",
  "x": "sector",
  "y": "avg_daily_return_pct",
  "y_axis_title": "Avg Daily Return (%)",
  "x_axis_title": "Sector",
  "orientation": "horizontal"
}

---

## Cross-Model Relationships

### Stocks with Company Context

Demonstrate the power of CIK-based cross-model joins.

```sql
SELECT
    s.ticker,
    s.security_name,
    s.asset_type,
    s.exchange_code,
    c.company_name,
    c.cik,
    c.sector,
    c.industry,
    c.sic_code,
    c.sic_description,
    s.market_cap / 1e9 as market_cap_billions,
    s.shares_outstanding / 1e6 as shares_outstanding_millions,
    p.close as latest_price,
    p.trade_date as latest_date
FROM stocks.dim_stock s
LEFT JOIN company.dim_company c ON s.company_id = c.company_id
LEFT JOIN stocks.fact_stock_prices p ON s.ticker = p.ticker
WHERE p.trade_date = (SELECT MAX(trade_date) FROM stocks.fact_stock_prices)
  AND s.ticker IN ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META')
ORDER BY s.market_cap DESC
```

$exhibits${
  "type": "table",
  "title": "Stocks with Company Information (via CIK)",
  "data": "cross_model",
  "columns": [
    {"name": "ticker", "label": "Ticker"},
    {"name": "security_name", "label": "Security"},
    {"name": "company_name", "label": "Company"},
    {"name": "cik", "label": "CIK"},
    {"name": "sector", "label": "Sector"},
    {"name": "industry", "label": "Industry"},
    {"name": "market_cap_billions", "label": "Market Cap ($B)", "format": "#,##0.00"},
    {"name": "latest_price", "label": "Latest Price", "format": "$#,##0.00"},
    {"name": "latest_date", "label": "Date"}
  ]
}

---

## Key Insights

This notebook demonstrates:

- ✅ **Cross-Model Joins**: Stocks ↔ Company via CIK-based `company_id`
- ✅ **Technical Indicators**: RSI, SMA, Bollinger Bands, Volume Ratio
- ✅ **Calendar Integration**: Business day filtering with `core.dim_calendar`
- ✅ **Sector Analysis**: Company sector aggregations
- ✅ **v2.0 Architecture**: Modular YAML models with inheritance

### Data Quality Notes

- **Companies**: 285 companies with CIK identifiers
- **Stocks**: 386 securities with fundamentals
- **Prices**: 107,860 daily price records
- **Technicals**: Full technical indicator suite (RSI, SMA, Bollinger, volatility)
- **Date Range**: 2024-11-19 to 2025-11-19 (1 year)

### Next Steps

1. **Add more tickers** - Expand beyond top 5 tech stocks
2. **Compare sectors** - Analyze sector rotation patterns
3. **Backtest strategies** - Use technical indicators for signals
4. **Add company fundamentals** - PE ratio, EPS, dividend yield (when available)

---

*Generated by de_Funk v2.0 - November 2025*
