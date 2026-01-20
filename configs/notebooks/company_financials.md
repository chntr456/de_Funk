---
id: company_financials
title: Company Financials Analysis
description: Comprehensive company financial statements analysis
tags: [company, financials, fundamentals, analysis]
models: [company]
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
  id: period_date
  type: date_range
  label: Fiscal Period
  column: period_date
  operator: between
  default: {start: "2020-01-01", end: "2025-12-31"}
  help_text: Filter by fiscal period end date
}

# Company Financials Analysis

Analyze company financial statements including income, balance sheet, cash flows, and earnings.

## Company Overview

$exhibits${
  type: data_table
  source: company.dim_company
  columns: [ticker_primary, company_name, sector, industry, market_cap, pe_ratio, eps, dividend_yield]
  download: true
}

## Income Statement Analysis

### Revenue & Profitability

$exhibits${
  type: metric_cards
  source: company.fact_income_statement
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
  source: company.fact_income_statement
  x: period_date
  y: total_revenue
  color: ticker
  title: Total Revenue by Period
  height: 400
}

### Profitability Trend

$exhibits${
  type: line_chart
  source: company.fact_income_statement
  x: period_date
  y: [gross_profit, operating_income, net_income]
  color: ticker
  title: Profitability Metrics Over Time
  height: 400
}

<details>
<summary>Income Statement Details</summary>

### Operating Expenses

$exhibits${
  type: bar_chart
  source: company.fact_income_statement
  x: period_date
  y: [operating_expenses, sg_and_a, research_and_development]
  color: ticker
  title: Operating Expense Breakdown
  height: 350
}

### EBITDA Analysis

$exhibits${
  type: line_chart
  source: company.fact_income_statement
  x: period_date
  y: [ebit, ebitda]
  color: ticker
  title: EBIT vs EBITDA
  height: 350
}

### Income Statement Data

$exhibits${
  type: data_table
  source: company.fact_income_statement
  columns: [ticker, period_date, report_type, total_revenue, gross_profit, operating_income, net_income, ebitda]
  sort_by: period_date
  sort_order: desc
  page_size: 20
  download: true
}

</details>

## Balance Sheet Analysis

### Asset & Liability Summary

$exhibits${
  type: metric_cards
  source: company.fact_balance_sheet
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
  source: company.fact_balance_sheet
  x: period_date
  y: [total_current_assets, total_non_current_assets]
  color: ticker
  title: Current vs Non-Current Assets
  height: 400
}

<details>
<summary>Balance Sheet Details</summary>

### Debt Analysis

$exhibits${
  type: line_chart
  source: company.fact_balance_sheet
  x: period_date
  y: [long_term_debt, total_debt, cash_and_equivalents]
  color: ticker
  title: Debt vs Cash Position
  height: 350
}

### Balance Sheet Data

$exhibits${
  type: data_table
  source: company.fact_balance_sheet
  columns: [ticker, period_date, report_type, total_assets, total_liabilities, total_shareholder_equity, cash_and_equivalents, total_debt]
  sort_by: period_date
  sort_order: desc
  page_size: 20
  download: true
}

</details>

## Cash Flow Analysis

### Cash Flow Summary

$exhibits${
  type: metric_cards
  source: company.fact_cash_flow
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
  source: company.fact_cash_flow
  x: period_date
  y: [operating_cashflow, cashflow_from_investment, cashflow_from_financing]
  color: ticker
  title: Cash Flow Components Over Time
  height: 400
}

<details>
<summary>Cash Flow Details</summary>

### Free Cash Flow Trend

$exhibits${
  type: bar_chart
  source: company.fact_cash_flow
  x: period_date
  y: free_cash_flow
  color: ticker
  title: Free Cash Flow by Period
  height: 350
}

### Capital Expenditures & Dividends

$exhibits${
  type: line_chart
  source: company.fact_cash_flow
  x: period_date
  y: [capital_expenditures, dividend_payout]
  color: ticker
  title: CapEx and Dividends
  height: 350
}

### Cash Flow Data

$exhibits${
  type: data_table
  source: company.fact_cash_flow
  columns: [ticker, period_date, report_type, operating_cashflow, cashflow_from_investment, cashflow_from_financing, free_cash_flow, capital_expenditures]
  sort_by: period_date
  sort_order: desc
  page_size: 20
  download: true
}

</details>

## Earnings Analysis

### EPS Performance

$exhibits${
  type: metric_cards
  source: company.fact_earnings
  metrics: [
    { column: reported_eps, label: "Latest EPS", aggregation: last, format: "$,.2f" },
    { column: estimated_eps, label: "Estimated EPS", aggregation: last, format: "$,.2f" },
    { column: surprise_percentage, label: "Avg Surprise %", aggregation: avg, format: ".1f%" }
  ]
}

### EPS vs Estimates

$exhibits${
  type: bar_chart
  source: company.fact_earnings
  x: period_date
  y: [reported_eps, estimated_eps]
  color: ticker
  title: Reported EPS vs Analyst Estimates
  height: 400
}

<details>
<summary>Earnings Details</summary>

### Earnings Surprise History

$exhibits${
  type: line_chart
  source: company.fact_earnings
  x: period_date
  y: surprise_percentage
  color: ticker
  title: Earnings Surprise Percentage Over Time
  height: 350
}

### Earnings Data

$exhibits${
  type: data_table
  source: company.fact_earnings
  columns: [ticker, period_date, report_type, reported_date, reported_eps, estimated_eps, surprise, surprise_percentage, beat_estimate]
  sort_by: period_date
  sort_order: desc
  page_size: 20
  download: true
}

</details>
