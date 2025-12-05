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
  source: {model: company, table: dim_company, column: ticker_primary}
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
  source: {model: company, table: fact_income_statement, column: report_type}
  default: "annual"
  help_text: Annual or quarterly reports
}

$filter${
  id: fiscal_date_ending
  type: date_range
  label: Fiscal Period
  column: fiscal_date_ending
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
  source: company.fact_income_statement
  x: fiscal_date_ending
  y: [total_revenue, gross_profit, operating_income, net_income]
  title: Revenue & Profitability Trend
  height: 400
}

### Income Statement Metrics

$exhibits${
  type: metric_cards
  source: company.fact_income_statement
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
  source: company.fact_income_statement
  columns: [ticker, fiscal_date_ending, report_type, total_revenue, gross_profit, operating_income, net_income, ebitda]
  sort_by: fiscal_date_ending
  sort_order: desc
  download: true
}

</details>

## Balance Sheet Analysis

Assets, liabilities, and shareholder equity position.

### Asset vs Liability Trend

$exhibits${
  type: bar_chart
  source: company.fact_balance_sheet
  x: fiscal_date_ending
  y: [total_assets, total_liabilities, total_shareholder_equity]
  title: Balance Sheet Composition
  height: 350
}

### Balance Sheet Metrics

$exhibits${
  type: metric_cards
  source: company.fact_balance_sheet
  metrics: [
    { column: total_assets, label: "Total Assets", aggregation: last, format: "$,.0f" },
    { column: total_liabilities, label: "Total Liabilities", aggregation: last, format: "$,.0f" },
    { column: total_shareholder_equity, label: "Shareholder Equity", aggregation: last, format: "$,.0f" },
    { column: cash_and_equivalents, label: "Cash & Equivalents", aggregation: last, format: "$,.0f" },
    { column: total_debt, label: "Total Debt", aggregation: last, format: "$,.0f" }
  ]
}

<details>
<summary>Balance Sheet Details</summary>

$exhibits${
  type: data_table
  source: company.fact_balance_sheet
  columns: [ticker, fiscal_date_ending, report_type, total_assets, total_liabilities, total_shareholder_equity, cash_and_equivalents, long_term_debt]
  sort_by: fiscal_date_ending
  sort_order: desc
  download: true
}

</details>

## Cash Flow Analysis

Operating, investing, and financing cash flows.

### Cash Flow Trends

$exhibits${
  type: line_chart
  source: company.fact_cash_flow
  x: fiscal_date_ending
  y: [operating_cashflow, cashflow_from_investment, cashflow_from_financing, free_cash_flow]
  title: Cash Flow Components
  height: 400
}

### Cash Flow Metrics

$exhibits${
  type: metric_cards
  source: company.fact_cash_flow
  metrics: [
    { column: operating_cashflow, label: "Operating Cash Flow", aggregation: last, format: "$,.0f" },
    { column: free_cash_flow, label: "Free Cash Flow", aggregation: last, format: "$,.0f" },
    { column: cashflow_from_investment, label: "Investing Cash Flow", aggregation: last, format: "$,.0f" },
    { column: cashflow_from_financing, label: "Financing Cash Flow", aggregation: last, format: "$,.0f" }
  ]
}

<details>
<summary>Cash Flow Details</summary>

$exhibits${
  type: data_table
  source: company.fact_cash_flow
  columns: [ticker, fiscal_date_ending, report_type, operating_cashflow, cashflow_from_investment, cashflow_from_financing, free_cash_flow, capital_expenditures]
  sort_by: fiscal_date_ending
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
  x: fiscal_date_ending
  y: [reported_eps, estimated_eps]
  title: Earnings Per Share - Reported vs Estimated
  height: 350
}

### Earnings Surprise

$exhibits${
  type: bar_chart
  source: company.fact_earnings
  x: fiscal_date_ending
  y: surprise_percentage
  title: Earnings Surprise %
  height: 300
}

<details>
<summary>Earnings Details</summary>

$exhibits${
  type: data_table
  source: company.fact_earnings
  columns: [ticker, fiscal_date_ending, report_type, reported_eps, estimated_eps, surprise, surprise_percentage, beat_estimate]
  sort_by: fiscal_date_ending
  sort_order: desc
  download: true
}

</details>
