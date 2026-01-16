---
type: domain-model
model: company
version: 2.0
description: "Corporate legal entities with SEC registration and fundamentals"
tags: [company, corporate, legal_entity, fundamentals]


# Dependencies
depends_on: []  # Builds independently from Bronze (securities_reference)

# Storage
storage:
  root: storage/silver/company
  format: delta

# Build
build:
  partitions: []
  sort_by: [cik]
  optimize: true

# Schema
schema:
  dimensions:
    dim_company:
      description: "Corporate entity master - from securities_reference"
      primary_key: [ticker]
      columns:
        company_id: {type: string, description: "PK - Internal ID", required: true}
        cik: {type: string, description: "SEC Central Index Key (10 digits)", pattern: "^[0-9]{10}$"}
        company_name: {type: string, description: "Company name", required: true}
        legal_name: {type: string, description: "Legal entity name"}
        ticker_primary: {type: string, description: "Primary trading symbol", required: true}
        ticker: {type: string, description: "Ticker symbol", required: true}
        exchange_code: {type: string, description: "Primary exchange code"}
        is_active: {type: boolean, description: "Currently active", default: true}
        sector: {type: string, description: "GICS Sector"}
        industry: {type: string, description: "GICS Industry"}
        market_cap: {type: double, description: "Market capitalization"}
        shares_outstanding: {type: long, description: "Shares outstanding"}
        pe_ratio: {type: double, description: "Price to earnings ratio"}
        eps: {type: double, description: "Earnings per share"}
        dividend_yield: {type: double, description: "Dividend yield"}
        incorporation_country: {type: string, description: "Country of incorporation", default: "US"}
      tags: [dim, entity, corporate]

  facts:
    fact_income_statement:
      description: "Income statement data from SEC filings"
      primary_key: [ticker, fiscal_date_ending, report_type]
      partitions: [fiscal_date_ending]
      columns:
        ticker: {type: string, required: true}
        fiscal_date_ending: {type: date, required: true}
        report_type: {type: string, description: "annual or quarterly"}
        total_revenue: {type: double}
        cost_of_revenue: {type: double}
        gross_profit: {type: double}
        operating_income: {type: double}
        net_income: {type: double}
        ebit: {type: double}
        ebitda: {type: double}
        operating_expenses: {type: double}
        research_and_development: {type: double}
        interest_expense: {type: double}
        reported_currency: {type: string}
      tags: [fact, financials, income_statement]

    fact_balance_sheet:
      description: "Balance sheet data from SEC filings"
      primary_key: [ticker, fiscal_date_ending, report_type]
      partitions: [fiscal_date_ending]
      columns:
        ticker: {type: string, required: true}
        fiscal_date_ending: {type: date, required: true}
        report_type: {type: string}
        total_assets: {type: double}
        total_current_assets: {type: double}
        cash_and_equivalents: {type: double}
        total_liabilities: {type: double}
        total_current_liabilities: {type: double}
        long_term_debt: {type: double}
        total_shareholder_equity: {type: double}
        retained_earnings: {type: double}
        reported_currency: {type: string}
      tags: [fact, financials, balance_sheet]

    fact_cash_flow:
      description: "Cash flow statement data"
      primary_key: [ticker, fiscal_date_ending, report_type]
      partitions: [fiscal_date_ending]
      columns:
        ticker: {type: string, required: true}
        fiscal_date_ending: {type: date, required: true}
        report_type: {type: string}
        operating_cashflow: {type: double}
        cashflow_from_investment: {type: double}
        capital_expenditures: {type: double}
        cashflow_from_financing: {type: double}
        dividend_payout: {type: double}
        free_cash_flow: {type: double}
        reported_currency: {type: string}
      tags: [fact, financials, cash_flow]

    fact_earnings:
      description: "Earnings data (EPS actual vs estimate)"
      primary_key: [ticker, fiscal_date_ending, report_type]
      partitions: [fiscal_date_ending]
      columns:
        ticker: {type: string, required: true}
        fiscal_date_ending: {type: date, required: true}
        report_type: {type: string}
        reported_eps: {type: double}
        estimated_eps: {type: double}
        surprise: {type: double}
        surprise_percentage: {type: double}
      tags: [fact, financials, earnings]

# Graph
graph:
  nodes:
    dim_company:
      from: bronze.company_reference
      filters:
        - "type IN ('Stock', 'Common Stock', 'Preferred Stock')"
        - "is_active = true"
      select:
        cik: cik
        company_name: security_name
        ticker: ticker
        exchange_code: exchange_code
        is_active: is_active
        sector: sector
        industry: industry
        market_cap: market_cap
      derive:
        company_id: "CONCAT('COMPANY_', COALESCE(cik, ticker))"
        incorporation_country: "'US'"
      unique_key: [ticker]
      tags: [dim, entity, corporate]

    fact_income_statement:
      from: bronze.company_income_statements
      derive:
        company_id: "CONCAT('COMPANY_', ticker)"
        report_date: "fiscal_date_ending"
      unique_key: [ticker, fiscal_date_ending, report_type]

    fact_balance_sheet:
      from: bronze.company_balance_sheets
      derive:
        company_id: "CONCAT('COMPANY_', ticker)"
        report_date: "fiscal_date_ending"
      unique_key: [ticker, fiscal_date_ending, report_type]

    fact_cash_flow:
      from: bronze.company_cash_flows
      derive:
        company_id: "CONCAT('COMPANY_', ticker)"
        report_date: "fiscal_date_ending"
      unique_key: [ticker, fiscal_date_ending, report_type]

    fact_earnings:
      from: bronze.company_earnings
      derive:
        company_id: "CONCAT('COMPANY_', ticker)"
        report_date: "fiscal_date_ending"
      unique_key: [ticker, fiscal_date_ending, report_type]

  edges:
    company_to_stock:
      from: dim_company
      to: stocks.dim_stock
      on: [ticker=ticker]
      type: one_to_one
      description: "Company's primary stock listing"

    income_statement_to_company:
      from: fact_income_statement
      to: dim_company
      on: [ticker=ticker]
      type: left

    balance_sheet_to_company:
      from: fact_balance_sheet
      to: dim_company
      on: [ticker=ticker]
      type: left

    cash_flow_to_company:
      from: fact_cash_flow
      to: dim_company
      on: [ticker=ticker]
      type: left

    earnings_to_company:
      from: fact_earnings
      to: dim_company
      on: [ticker=ticker]
      type: left

    # Calendar joins for time-series
    income_statement_to_calendar:
      from: fact_income_statement
      to: temporal.dim_calendar
      on: [report_date=date]
      type: left

# Measures
measures:
  simple:
    company_count:
      description: "Number of companies"
      source: dim_company.ticker
      aggregation: count_distinct
      format: "#,##0"

    avg_market_cap:
      description: "Average market cap"
      source: dim_company.market_cap
      aggregation: avg
      format: "$#,##0.00B"

    total_revenue:
      description: "Total revenue"
      source: fact_income_statement.total_revenue
      aggregation: sum
      format: "$#,##0.00B"

    avg_net_income:
      description: "Average net income"
      source: fact_income_statement.net_income
      aggregation: avg
      format: "$#,##0.00M"

# Metadata
metadata:
  domain: corporate
  owner: data_engineering
  sla_hours: 24
  data_quality_checks:
    - no_null_ticker
    - valid_cik_format
    - unique_ticker
status: active
---

## Company Model

Corporate legal entities with SEC registration and financial fundamentals.

### Data Sources

| Source | Provider | Update Frequency |
|--------|----------|------------------|
| securities_reference | Alpha Vantage | Daily |
| income_statements | Alpha Vantage | Quarterly |
| balance_sheets | Alpha Vantage | Quarterly |
| cash_flows | Alpha Vantage | Quarterly |
| earnings | Alpha Vantage | Quarterly |

### Key Features

- **Dimension**: `dim_company` - Corporate entity master
- **Facts**: Income statement, balance sheet, cash flow, earnings
- **Cross-model**: Links to `stocks.dim_stock` via ticker

### Usage

```python
from models.domains.corporate.company import CompanyModel

model = session.load_model("company")
companies = model.get_table("dim_company")
income = model.get_table("fact_income_statement", filters={"ticker": "AAPL"})
```

### Notes

- CIK may be NULL from bulk LISTING_STATUS (populated by OVERVIEW calls)
- Financial statements link via ticker (CIK-based linking optional)
- Ticker used as primary key for filter compatibility
