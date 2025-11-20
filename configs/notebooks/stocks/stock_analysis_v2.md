---
title: "Stock Analysis Dashboard (v2.0)"
description: "Stock analysis with company fundamentals and technical indicators"
model: stocks
version: 2.0
tags:
  - stocks
  - company
  - technical-analysis
author: "de_Funk v2.0"
created: "2025-11-20"
---

# Stock Analysis Dashboard (v2.0)

Explore v2.0 models with cross-model joins between **stocks**, **company**, and **core**.

---

## Stock Overview with Company Info

Latest stock prices with linked company information via CIK.

```sql
SELECT
    s.ticker,
    s.security_name,
    c.company_name,
    c.sector,
    c.industry,
    s.market_cap / 1e9 as market_cap_billions,
    p.close as latest_price,
    p.volume / 1e6 as volume_millions,
    p.trade_date as latest_date
FROM stocks.dim_stock s
LEFT JOIN company.dim_company c ON s.company_id = c.company_id
LEFT JOIN stocks.fact_stock_prices p ON s.ticker = p.ticker
WHERE p.trade_date = (SELECT MAX(trade_date) FROM stocks.fact_stock_prices)
  AND s.ticker IN ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META')
ORDER BY s.market_cap DESC
```

---

## Price Trends

Historical closing prices for tech stocks.

```sql
SELECT
    p.trade_date,
    p.ticker,
    s.security_name,
    p.close,
    p.volume / 1e6 as volume_millions
FROM stocks.fact_stock_prices p
JOIN stocks.dim_stock s ON p.ticker = s.ticker
WHERE p.ticker IN ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META')
  AND p.trade_date >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY p.trade_date, p.ticker
```

---

## Technical Indicators - RSI

Relative Strength Index showing overbought/oversold conditions.

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

---

## Moving Averages

20, 50, and 200-day moving averages for AAPL.

```sql
SELECT
    t.trade_date,
    t.ticker,
    t.close,
    t.sma_20,
    t.sma_50,
    t.sma_200
FROM stocks.fact_stock_technicals t
WHERE t.ticker = 'AAPL'
  AND t.trade_date >= CURRENT_DATE - INTERVAL '180 days'
  AND t.sma_20 IS NOT NULL
ORDER BY t.trade_date
```

---

## Bollinger Bands

Price volatility bands for AAPL.

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

---

## Volume Analysis

Trading volume with volume ratio (vs 20-day average).

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

---

## Sector Performance

Average daily returns by sector over 30 days.

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

---

## Cross-Model Join Demo

Demonstrating CIK-based linkage between stocks and company dimensions.

```sql
SELECT
    s.ticker,
    s.security_name,
    s.exchange_code,
    c.company_name,
    c.cik,
    c.sector,
    c.industry,
    s.market_cap / 1e9 as market_cap_billions,
    s.shares_outstanding / 1e6 as shares_millions
FROM stocks.dim_stock s
LEFT JOIN company.dim_company c ON s.company_id = c.company_id
WHERE s.ticker IN ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'A', 'AA', 'AAL')
ORDER BY s.market_cap DESC
```

---

## Key Features

**v2.0 Architecture:**
- ✅ Cross-model joins via CIK-based company_id
- ✅ Technical indicators (RSI, SMA, Bollinger Bands)
- ✅ Calendar dimension integration
- ✅ Sector-based aggregations

**Current Data:**
- 386 stocks with fundamentals
- 285 companies with CIK
- 107,860 price records
- Full technical indicator suite

**Models Used:**
- `stocks` - Stock securities with prices
- `company` - Corporate entities with CIK
- `core` - Calendar dimension

---

*Generated by de_Funk v2.0 - November 2025*
