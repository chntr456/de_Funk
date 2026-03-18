---
id: company_financials
title: Company Financials Analysis
description: Comprehensive company financial statements analysis
tags: [company, financials, fundamentals, analysis]
models: [corporate.entity]
author: de_Funk Analytics
created: 2025-12-05
---

$filter${
  id: ticker
  label: Ticker
  type: select
  multi: true
  column: ticker
  source: {model: company, table: dim_company, column: ticker}
  default: ["AAPL", "MSFT", "GOOGL"]
  help_text: Select one or more companies to analyze
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
  id: report_type
  label: Report Type
  type: select
  multi: false
  source: {model: company, table: fact_income_statement, column: report_type}
  default: "annual"
  help_text: Annual or quarterly reports
}

$filter${
  id: date
  type: date_range
  label: Fiscal Period
  column: date
  operator: between
  default: {start: "2020-01-01", end: current_date()}
  help_text: Filter by fiscal period end date
}

# Company Financials Analysis

Analyze company financial statements including income, balance sheet, cash flows, and earnings.

## Company Overview

$exhibits${
  type: data_table
  source: corporate.entity.dim_company
  columns: [ticker, company_name, sector, industry, market_cap, pe_ratio, eps, dividend_yield]
  download: true
}

## Income Statement Analysis

### Revenue & Profitability

$exhibits${
  type: metric_cards
  source: corporate.entity.fact_income_statement
  metrics: [
    { column: total_revenue, label: "Total Revenue", aggregation: sum, format: "$,.0f" },
    { column: gross_profit, label: "Gross Profit", aggregation: sum, format: "$,.0f" },
    { column: operating_income, label: "Operating Income", aggregation: sum, format: "$,.0f" },
    { column: net_income, label: "Net Income", aggregation: sum, format: "$,.0f" }
  ]
}

### Revenue Trend

$exhibits${
  type: bar_chart
  source: corporate.entity.fact_income_statement
  x: temporal.dim_calendar.date
  y: corporate.entity.fact_income_statement.total_revenue
  color: corporate.entity.dim_corporate.entity.ticker
  title: Total Revenue by Period
  height: 400
}

### Profitability Trend

$exhibits${
  type: line_chart
  source: corporate.entity.fact_income_statement
  x: temporal.dim_calendar.date
  y: [corporate.entity.fact_income_statement.gross_profit, corporate.entity.fact_income_statement.operating_income, corporate.entity.fact_income_statement.net_income]
  color: corporate.entity.dim_corporate.entity.ticker
  title: Profitability Metrics Over Time
  height: 400
}

<details>
<summary>Income Statement Details</summary>

### Operating Expenses

$exhibits${
  type: bar_chart
  source: corporate.entity.fact_income_statement
  x: temporal.dim_calendar.date
  y: [corporate.entity.fact_income_statement.operating_income]
  color: corporate.entity.dim_corporate.entity.ticker
  title: Operating Income by Period
  height: 350
}

### EBITDA Analysis

$exhibits${
  type: line_chart
  source: corporate.entity.fact_income_statement
  x: temporal.dim_calendar.date
  y: [corporate.entity.fact_income_statement.ebitda]
  color: corporate.entity.dim_corporate.entity.ticker
  title: EBITDA Over Time
  height: 350
}

### Income Statement Data

$exhibits${
  type: data_table
  source: corporate.entity.fact_income_statement
  columns: [corporate.entity.dim_corporate.entity.ticker, corporate.entity.fact_income_statement.report_type, corporate.entity.fact_income_statement.total_revenue, corporate.entity.fact_income_statement.gross_profit, corporate.entity.fact_income_statement.operating_income, corporate.entity.fact_income_statement.net_income, corporate.entity.fact_income_statement.ebitda]
  sort_by: corporate.entity.fact_income_statement.period_end_date_id
  sort_order: desc
  page_size: 20
  download: true
}

</details>

## Balance Sheet Analysis

### Asset & Liability Summary

$exhibits${
  type: metric_cards
  source: corporate.entity.fact_balance_sheet
  metrics: [
    { column: total_assets, label: "Total Assets", aggregation: last, format: "$,.0f" },
    { column: total_liabilities, label: "Total Liabilities", aggregation: last, format: "$,.0f" },
    { column: total_shareholder_equity, label: "Shareholder Equity", aggregation: last, format: "$,.0f" },
    { column: cash_and_equivalents, label: "Cash Position", aggregation: last, format: "$,.0f" }
  ]
}

### Asset Composition

$exhibits${
  type: bar_chart
  source: corporate.entity.fact_balance_sheet
  x: temporal.dim_calendar.date
  y: [corporate.entity.fact_balance_sheet.total_current_assets, corporate.entity.fact_balance_sheet.total_non_current_assets]
  color: corporate.entity.dim_corporate.entity.ticker
  title: Current vs Non-Current Assets
  height: 400
}

<details>
<summary>Balance Sheet Details</summary>

### Debt Analysis

$exhibits${
  type: line_chart
  source: corporate.entity.fact_balance_sheet
  x: temporal.dim_calendar.date
  y: [corporate.entity.fact_balance_sheet.long_term_debt, corporate.entity.fact_balance_sheet.short_long_term_debt_total, corporate.entity.fact_balance_sheet.cash_and_equivalents]
  color: corporate.entity.dim_corporate.entity.ticker
  title: Debt vs Cash Position
  height: 350
}

### Balance Sheet Data

$exhibits${
  type: data_table
  source: corporate.entity.fact_balance_sheet
  columns: [corporate.entity.dim_corporate.entity.ticker, corporate.entity.fact_balance_sheet.report_type, corporate.entity.fact_balance_sheet.total_assets, corporate.entity.fact_balance_sheet.total_liabilities, corporate.entity.fact_balance_sheet.total_shareholder_equity, corporate.entity.fact_balance_sheet.cash_and_equivalents, corporate.entity.fact_balance_sheet.short_long_term_debt_total]
  sort_by: corporate.entity.fact_balance_sheet.period_end_date_id
  sort_order: desc
  page_size: 20
  download: true
}

</details>

## Cash Flow Analysis

### Cash Flow Summary

$exhibits${
  type: metric_cards
  source: corporate.entity.fact_cash_flow
  metrics: [
    { column: operating_cashflow, label: "Operating Cash Flow", aggregation: sum, format: "$,.0f" },
    { column: cashflow_from_investment, label: "Investing Cash Flow", aggregation: sum, format: "$,.0f" },
    { column: cashflow_from_financing, label: "Financing Cash Flow", aggregation: sum, format: "$,.0f" },
    { column: free_cash_flow, label: "Free Cash Flow", aggregation: sum, format: "$,.0f" }
  ]
}

### Cash Flow Trend

$exhibits${
  type: line_chart
  source: corporate.entity.fact_cash_flow
  x: temporal.dim_calendar.date
  y: [corporate.entity.fact_cash_flow.operating_cashflow, corporate.entity.fact_cash_flow.cashflow_from_investment, corporate.entity.fact_cash_flow.cashflow_from_financing]
  color: corporate.entity.dim_corporate.entity.ticker
  title: Cash Flow Components Over Time
  height: 400
}

<details>
<summary>Cash Flow Details</summary>

### Free Cash Flow Trend

$exhibits${
  type: bar_chart
  source: corporate.entity.fact_cash_flow
  x: temporal.dim_calendar.date
  y: corporate.entity.fact_cash_flow.operating_cashflow
  color: corporate.entity.dim_corporate.entity.ticker
  title: Operating Cash Flow by Period
  height: 350
}

### Capital Expenditures & Dividends

$exhibits${
  type: line_chart
  source: corporate.entity.fact_cash_flow
  x: temporal.dim_calendar.date
  y: [corporate.entity.fact_cash_flow.capital_expenditures, corporate.entity.fact_cash_flow.dividend_payout]
  color: corporate.entity.dim_corporate.entity.ticker
  title: CapEx and Dividends
  height: 350
}

### Cash Flow Data

$exhibits${
  type: data_table
  source: corporate.entity.fact_cash_flow
  columns: [corporate.entity.dim_corporate.entity.ticker, corporate.entity.fact_cash_flow.report_type, corporate.entity.fact_cash_flow.operating_cashflow, corporate.entity.fact_cash_flow.cashflow_from_investment, corporate.entity.fact_cash_flow.cashflow_from_financing, corporate.entity.fact_cash_flow.capital_expenditures]
  sort_by: corporate.entity.fact_cash_flow.period_end_date_id
  sort_order: desc
  page_size: 20
  download: true
}

</details>

## Earnings Analysis

### EPS Performance

$exhibits${
  type: metric_cards
  source: corporate.entity.fact_earnings
  metrics: [
    { column: reported_eps, label: "Latest EPS", aggregation: last, format: "$,.2f" },
    { column: estimated_eps, label: "Estimated EPS", aggregation: last, format: "$,.2f" },
    { column: surprise_percentage, label: "Avg Surprise %", aggregation: avg, format: ".1f%" }
  ]
}

### EPS vs Estimates

$exhibits${
  type: bar_chart
  source: corporate.entity.fact_earnings
  x: temporal.dim_calendar.date
  y: [corporate.entity.fact_earnings.reported_eps, corporate.entity.fact_earnings.estimated_eps]
  color: corporate.entity.dim_corporate.entity.ticker
  title: Reported EPS vs Analyst Estimates
  height: 400
}

<details>
<summary>Earnings Details</summary>

### Earnings Surprise History

$exhibits${
  type: line_chart
  source: corporate.entity.fact_earnings
  x: temporal.dim_calendar.date
  y: corporate.entity.fact_earnings.surprise_percentage
  color: corporate.entity.dim_corporate.entity.ticker
  title: Earnings Surprise Percentage Over Time
  height: 350
}

### Earnings Data

$exhibits${
  type: data_table
  source: corporate.entity.fact_earnings
  columns: [corporate.entity.dim_corporate.entity.ticker, corporate.entity.fact_earnings.report_type, corporate.entity.fact_earnings.reported_date, corporate.entity.fact_earnings.reported_eps, corporate.entity.fact_earnings.estimated_eps, corporate.entity.fact_earnings.surprise, corporate.entity.fact_earnings.surprise_percentage]
  sort_by: corporate.entity.fact_earnings.period_end_date_id
  sort_order: desc
  page_size: 20
  download: true
}

</details>
