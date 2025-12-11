---
id: financial_statements_gt
title: Company Financial Statements
description: Publication-quality financial tables using Great Tables with grid layouts
author: de_Funk
version: 2.0
models: [company, core]
tags: [financials, great_tables, example, grid_layout]
---

# Financial Statement Analysis

This notebook demonstrates publication-quality financial tables using **Great Tables** with **grid layouts**.
Select a company to view their financial statements in a dashboard view.

$filter${
  id: ticker
  type: select
  multi: false
  label: Company
  source: {model: company, table: dim_company, column: ticker}
  default: AAPL
}

$filter${
  id: report_type
  type: select
  label: Report Type
  options: [annual, quarterly]
  default: annual
}

---

## Financial Dashboard

View all four financial statements at a glance in a 2x2 grid layout.

$grid${
  template: 2x2
}

$exhibits${
  type: great_table
  source: company.fact_income_statement
  title: Income Statement
  theme: financial
  scroll: true
  max_height: 300
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: total_revenue, label: Revenue, format: currency_millions}
    - {id: gross_profit, label: Gross Profit, format: currency_millions, style: {bold: true}}
    - {id: operating_income, label: Op. Income, format: currency_millions}
    - {id: net_income, label: Net Income, format: currency_millions, style: {bold: true}, conditional: {type: color_scale, palette: ['#ffcccc', '#ffffff', '#ccffcc'], domain: [-1000000000, 0, 10000000000]}}
  spanners:
    - {label: Revenue, columns: [total_revenue, gross_profit]}
    - {label: Bottom Line, columns: [operating_income, net_income]}
  source_note: "Amounts in millions USD"
  row_striping: true
}

$exhibits${
  type: great_table
  source: company.fact_balance_sheet
  title: Balance Sheet
  theme: financial
  scroll: true
  max_height: 300
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: total_assets, label: Total Assets, format: currency_millions, style: {bold: true}}
    - {id: total_liabilities, label: Total Liabilities, format: currency_millions}
    - {id: total_shareholder_equity, label: Equity, format: currency_millions, style: {bold: true}}
  source_note: "Amounts in millions USD"
  row_striping: true
}

$exhibits${
  type: great_table
  source: company.fact_cash_flow
  title: Cash Flow
  theme: financial
  scroll: true
  max_height: 300
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: operating_cashflow, label: Operating, format: currency_millions, style: {bold: true}}
    - {id: cashflow_from_investment, label: Investing, format: currency_millions}
    - {id: cashflow_from_financing, label: Financing, format: currency_millions}
    - {id: free_cash_flow, label: FCF, format: currency_millions, style: {bold: true}, conditional: {type: color_scale, palette: ['#ef4444', '#ffffff', '#22c55e'], domain: [-5000000000, 0, 20000000000]}}
  source_note: "Amounts in millions USD"
  row_striping: true
}

$exhibits${
  type: great_table
  source: company.fact_earnings
  title: Earnings
  theme: financial
  scroll: true
  max_height: 300
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: reported_eps, label: EPS, format: currency}
    - {id: estimated_eps, label: Est. EPS, format: currency}
    - {id: surprise_percentage, label: Surprise %, format: percent, conditional: {type: color_scale, palette: ['#ef4444', '#fbbf24', '#22c55e'], domain: [-0.1, 0, 0.1]}}
  spanners:
    - {label: EPS, columns: [reported_eps, estimated_eps]}
    - {label: Beat/Miss, columns: [surprise_percentage]}
  source_note: "EPS data from Alpha Vantage"
  row_striping: true
}

$/grid$

---

## Detailed Statements

<details>
<summary>Full Income Statement</summary>

### Consolidated Statement of Operations

$exhibits${
  type: great_table
  source: company.fact_income_statement
  title: Consolidated Statement of Operations
  theme: financial
  scroll: true
  max_height: 400
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: total_revenue, label: Total Revenue, format: currency_millions}
    - {id: cost_of_revenue, label: Cost of Revenue, format: currency_millions}
    - {id: gross_profit, label: Gross Profit, format: currency_millions, style: {bold: true}}
    - {id: operating_expenses, label: Operating Expenses, format: currency_millions}
    - {id: operating_income, label: Operating Income, format: currency_millions, style: {bold: true}}
    - {id: net_income, label: Net Income, format: currency_millions, style: {bold: true}, conditional: {type: color_scale, palette: ['#ffcccc', '#ffffff', '#ccffcc'], domain: [-1000000000, 0, 10000000000]}}
  spanners:
    - {label: Revenue, columns: [total_revenue, cost_of_revenue, gross_profit]}
    - {label: Operating, columns: [operating_expenses, operating_income]}
    - {label: Bottom Line, columns: [net_income]}
  source_note: "Source: SEC Filings via Alpha Vantage | Amounts in millions USD"
  row_striping: true
}

</details>

<details>
<summary>Full Balance Sheet</summary>

### Consolidated Balance Sheet

$exhibits${
  type: great_table
  source: company.fact_balance_sheet
  title: Consolidated Balance Sheet
  theme: financial
  scroll: true
  max_height: 400
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: cash_and_equivalents, label: Cash & Equivalents, format: currency_millions}
    - {id: total_current_assets, label: Current Assets, format: currency_millions, style: {bold: true}}
    - {id: total_assets, label: Total Assets, format: currency_millions, style: {bold: true}}
    - {id: total_current_liabilities, label: Current Liabilities, format: currency_millions}
    - {id: long_term_debt, label: Long-Term Debt, format: currency_millions}
    - {id: total_liabilities, label: Total Liabilities, format: currency_millions, style: {bold: true}}
    - {id: total_shareholder_equity, label: Shareholders' Equity, format: currency_millions, style: {bold: true}}
  spanners:
    - {label: Assets, columns: [cash_and_equivalents, total_current_assets, total_assets]}
    - {label: Liabilities, columns: [total_current_liabilities, long_term_debt, total_liabilities]}
    - {label: Equity, columns: [total_shareholder_equity]}
  source_note: "Source: SEC Filings | Amounts in millions USD"
  row_striping: true
}

</details>

<details>
<summary>Full Cash Flow Statement</summary>

### Consolidated Statement of Cash Flows

$exhibits${
  type: great_table
  source: company.fact_cash_flow
  title: Consolidated Statement of Cash Flows
  theme: financial
  scroll: true
  max_height: 400
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: operating_cashflow, label: Cash from Operations, format: currency_millions, style: {bold: true}}
    - {id: capital_expenditures, label: Capital Expenditures, format: currency_millions}
    - {id: cashflow_from_investment, label: Cash from Investing, format: currency_millions, style: {bold: true}}
    - {id: dividend_payout, label: Dividends Paid, format: currency_millions}
    - {id: cashflow_from_financing, label: Cash from Financing, format: currency_millions, style: {bold: true}}
    - {id: free_cash_flow, label: Free Cash Flow, format: currency_millions, style: {bold: true}, conditional: {type: color_scale, palette: ['#ef4444', '#ffffff', '#22c55e'], domain: [-5000000000, 0, 20000000000]}}
  spanners:
    - {label: Operating, columns: [operating_cashflow]}
    - {label: Investing, columns: [capital_expenditures, cashflow_from_investment]}
    - {label: Financing, columns: [dividend_payout, cashflow_from_financing]}
    - {label: Summary, columns: [free_cash_flow]}
  source_note: "Source: SEC Filings | Amounts in millions USD"
  footnotes:
    - {column: free_cash_flow, text: "Free Cash Flow = Operating Cash Flow - Capital Expenditures"}
  row_striping: true
}

</details>

<details>
<summary>Full Earnings History</summary>

### Earnings Per Share Analysis

$exhibits${
  type: great_table
  source: company.fact_earnings
  title: Earnings History
  theme: financial
  scroll: true
  max_height: 400
  sort: {by: fiscal_date_ending, order: desc}
  columns:
    - {id: fiscal_date_ending, label: Period, format: date}
    - {id: reported_eps, label: Reported EPS, format: currency}
    - {id: estimated_eps, label: Estimated EPS, format: currency}
    - {id: surprise, label: Surprise, format: currency, conditional: {type: color_scale, palette: ['#ef4444', '#ffffff', '#22c55e'], domain: [-0.5, 0, 0.5]}}
    - {id: surprise_percentage, label: Surprise %, format: percent, conditional: {type: color_scale, palette: ['#ef4444', '#fbbf24', '#22c55e'], domain: [-0.1, 0, 0.1]}}
  spanners:
    - {label: EPS, columns: [reported_eps, estimated_eps]}
    - {label: Beat/Miss, columns: [surprise, surprise_percentage]}
  source_note: "Source: Alpha Vantage Earnings Data"
  row_striping: true
}

</details>

---

## Notes

### About Grid Layouts

This notebook demonstrates the **grid layout** feature, which arranges multiple exhibits in a configurable grid pattern:

- **2x2 Template**: Displays 4 exhibits in a 2-column, 2-row grid
- **Condensed Views**: Grid exhibits use fewer columns for compact display
- **Full Details**: Detailed views available in collapsible sections below

### About Great Tables

This notebook uses the **Great Tables** library for publication-quality table rendering.
Key features demonstrated:

- **Spanners**: Grouped column headers (Revenue, Operating, etc.)
- **Conditional Formatting**: Color scales for profit/loss indicators
- **Number Formatting**: Currency in millions, percentages
- **Themes**: Financial theme with professional styling
- **Source Notes**: Data attribution at table footer
- **Footnotes**: Explanatory notes for specific columns

### Data Sources

All financial data is sourced from SEC filings via the Alpha Vantage API:

- **Income Statement**: Revenue, expenses, profitability
- **Balance Sheet**: Assets, liabilities, equity
- **Cash Flow**: Operating, investing, financing activities
- **Earnings**: Quarterly EPS vs analyst estimates
