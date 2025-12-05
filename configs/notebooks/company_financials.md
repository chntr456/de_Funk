---
id: company_financials
title: Company Financial Analysis
description: Deep dive into company fundamentals - income, balance sheet, cash flows, earnings
tags: [company, financials, fundamentals, analysis]
models: [company]
author: de_Funk Analytics
created: 2025-12-05
---

$filter${
  id: ticker
  label: Company Ticker
  type: select
  multi: false
  source: {model: company, table: dim_company, column: ticker}
  default: "AAPL"
  help_text: Select a company to analyze
}

$filter${
  id: sector
  label: Sector
  type: select
  multi: true
  source: {model: company, table: dim_company, column: sector}
  help_text: Filter companies by sector
}

$filter${
  id: industry
  label: Industry
  type: select
  multi: true
  source: {model: company, table: dim_company, column: industry}
  help_text: Filter companies by industry
}

$filter${
  id: report_type
  label: Report Type
  type: select
  multi: false
  source: {model: company, table: fact_income_statements, column: report_type}
  default: "annual"
  help_text: Annual or quarterly reports
}

$filter${
  id: fiscal_date
  type: date_range
  label: Fiscal Period
  column: fiscal_date
  operator: between
  default: {start: "2020-01-01", end: "2025-12-31"}
  help_text: Filter by fiscal date range
}

# Company Financial Analysis

Comprehensive financial analysis including income statements, balance sheets, cash flows, and earnings performance.

## Company Overview

$exhibits${
  type: metric_cards
  source: company.dim_company
  metrics: [
    { column: company_name, label: "Company", aggregation: first },
    { column: sector, label: "Sector", aggregation: first },
    { column: industry, label: "Industry", aggregation: first },
    { column: market_cap, label: "Market Cap", aggregation: first, format: "$,.0f" }
  ]
}

## Income Statement Analysis

Revenue, profitability, and operational efficiency metrics.

### Revenue & Profit Trends

$exhibits${
  type: line_chart
  source: company.fact_income_statements
  x: fiscal_date
  y: [total_revenue, gross_profit, operating_income, net_income]
  title: Revenue & Profitability Trend
  height: 400
}

### Income Statement Metrics

$exhibits${
  type: metric_cards
  source: company.fact_income_statements
  metrics: [
    { column: total_revenue, label: "Total Revenue", aggregation: last, format: "$,.0f" },
    { column: gross_profit, label: "Gross Profit", aggregation: last, format: "$,.0f" },
    { column: operating_income, label: "Operating Income", aggregation: last, format: "$,.0f" },
    { column: net_income, label: "Net Income", aggregation: last, format: "$,.0f" },
    { column: ebitda, label: "EBITDA", aggregation: last, format: "$,.0f" }
  ]
}

<details>
<summary>Income Statement Details</summary>

$exhibits${
  type: data_table
  source: company.fact_income_statements
  columns: [fiscal_date, report_type, total_revenue, gross_profit, operating_income, net_income, ebitda]
  sort_by: fiscal_date
  sort_order: desc
  download: true
}

</details>

## Balance Sheet Analysis

Assets, liabilities, and shareholder equity position.

### Asset vs Liability Trend

$exhibits${
  type: bar_chart
  source: company.fact_balance_sheets
  x: fiscal_date
  y: [total_assets, total_liabilities, total_equity]
  title: Balance Sheet Composition
  height: 350
}

### Balance Sheet Metrics

$exhibits${
  type: metric_cards
  source: company.fact_balance_sheets
  metrics: [
    { column: total_assets, label: "Total Assets", aggregation: last, format: "$,.0f" },
    { column: total_liabilities, label: "Total Liabilities", aggregation: last, format: "$,.0f" },
    { column: total_equity, label: "Shareholder Equity", aggregation: last, format: "$,.0f" },
    { column: cash, label: "Cash & Equivalents", aggregation: last, format: "$,.0f" },
    { column: debt, label: "Total Debt", aggregation: last, format: "$,.0f" }
  ]
}

<details>
<summary>Balance Sheet Details</summary>

$exhibits${
  type: data_table
  source: company.fact_balance_sheets
  columns: [fiscal_date, report_type, total_assets, total_liabilities, total_equity, cash, debt]
  sort_by: fiscal_date
  sort_order: desc
  download: true
}

</details>

## Cash Flow Analysis

Operating, investing, and financing cash flows.

### Cash Flow Trends

$exhibits${
  type: line_chart
  source: company.fact_cash_flows
  x: fiscal_date
  y: [operating_cashflow, investing_cashflow, financing_cashflow, free_cashflow]
  title: Cash Flow Components
  height: 400
}

### Cash Flow Metrics

$exhibits${
  type: metric_cards
  source: company.fact_cash_flows
  metrics: [
    { column: operating_cashflow, label: "Operating Cash Flow", aggregation: last, format: "$,.0f" },
    { column: free_cashflow, label: "Free Cash Flow", aggregation: last, format: "$,.0f" },
    { column: investing_cashflow, label: "Investing Cash Flow", aggregation: last, format: "$,.0f" },
    { column: financing_cashflow, label: "Financing Cash Flow", aggregation: last, format: "$,.0f" }
  ]
}

<details>
<summary>Cash Flow Details</summary>

$exhibits${
  type: data_table
  source: company.fact_cash_flows
  columns: [fiscal_date, report_type, operating_cashflow, investing_cashflow, financing_cashflow, free_cashflow]
  sort_by: fiscal_date
  sort_order: desc
  download: true
}

</details>

## Earnings Analysis

EPS performance and earnings surprises.

### EPS Trend - Reported vs Estimated

$exhibits${
  type: line_chart
  source: company.fact_earnings
  x: fiscal_date
  y: [reported_eps, estimated_eps]
  title: Earnings Per Share - Reported vs Estimated
  height: 350
}

### Earnings Surprise

$exhibits${
  type: bar_chart
  source: company.fact_earnings
  x: fiscal_date
  y: surprise_percentage
  title: Earnings Surprise %
  height: 300
}

<details>
<summary>Earnings Details</summary>

$exhibits${
  type: data_table
  source: company.fact_earnings
  columns: [fiscal_date, report_type, reported_eps, estimated_eps, surprise, surprise_percentage]
  sort_by: fiscal_date
  sort_order: desc
  download: true
}

</details>
