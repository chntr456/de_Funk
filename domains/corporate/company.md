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
      primary_key: [company_id]
      columns:
        company_id: {type: string, description: "PK - Surrogate key (COMPANY_cik or COMPANY_ticker)", required: true}
        security_id: {type: string, description: "FK to dim_security.security_id (for publicly traded)"}
        cik: {type: string, description: "SEC Central Index Key (10 digits)", pattern: "^[0-9]{10}$"}
        company_name: {type: string, description: "Company name", required: true}
        ticker: {type: string, description: "Ticker symbol (denormalized)", unique: true}
        exchange_code: {type: string, description: "Primary exchange code"}
        is_active: {type: boolean, description: "Currently active", default: true}
        sector: {type: string, description: "GICS Sector"}
        industry: {type: string, description: "GICS Industry"}
        market_cap: {type: double, description: "Market capitalization"}
        incorporation_country: {type: string, description: "Country of incorporation", default: "US"}
      tags: [dim, entity, corporate]

  facts:
    fact_income_statement:
      description: "Income statement data from SEC filings"
      primary_key: [income_statement_id]
      partitions: [fiscal_date_ending]
      columns:
        income_statement_id: {type: string, description: "PK - Surrogate key", required: true}
        company_id: {type: string, description: "FK to dim_company.company_id", required: true}
        fiscal_date_ending: {type: date, required: true}
        report_type: {type: string, description: "annual or quarterly"}
        total_revenue: {type: double}
        gross_profit: {type: double}
        operating_income: {type: double}
        net_income: {type: double}
        ebitda: {type: double}
        reported_currency: {type: string}
      tags: [fact, financials, income_statement]

    fact_balance_sheet:
      description: "Balance sheet data from SEC filings"
      primary_key: [balance_sheet_id]
      partitions: [fiscal_date_ending]
      columns:
        balance_sheet_id: {type: string, description: "PK - Surrogate key", required: true}
        company_id: {type: string, description: "FK to dim_company.company_id", required: true}
        fiscal_date_ending: {type: date, required: true}
        report_type: {type: string}
        total_assets: {type: double}
        total_liabilities: {type: double}
        total_shareholder_equity: {type: double}
        cash_and_equivalents: {type: double}
        long_term_debt: {type: double}
        reported_currency: {type: string}
      tags: [fact, financials, balance_sheet]

    fact_cash_flow:
      description: "Cash flow statement data"
      primary_key: [cash_flow_id]
      partitions: [fiscal_date_ending]
      columns:
        cash_flow_id: {type: string, description: "PK - Surrogate key", required: true}
        company_id: {type: string, description: "FK to dim_company.company_id", required: true}
        fiscal_date_ending: {type: date, required: true}
        report_type: {type: string}
        operating_cashflow: {type: double}
        cashflow_from_investment: {type: double}
        cashflow_from_financing: {type: double}
        free_cash_flow: {type: double}
        reported_currency: {type: string}
      tags: [fact, financials, cash_flow]

    fact_earnings:
      description: "Earnings data (EPS actual vs estimate)"
      primary_key: [earnings_id]
      partitions: [fiscal_date_ending]
      columns:
        earnings_id: {type: string, description: "PK - Surrogate key", required: true}
        company_id: {type: string, description: "FK to dim_company.company_id", required: true}
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
        - "AssetType IN ('Stock', 'Common Stock', 'Preferred Stock')"
      select:
        cik: cik
        company_name: company_name
        ticker: ticker
        exchange_code: exchange_code
        sector: sector
        industry: industry
        market_cap: market_cap
      derive:
        company_id: "CONCAT('COMPANY_', COALESCE(cik, ticker))"
        security_id: "CONCAT('Stock_', ticker)"
        incorporation_country: "'US'"
        is_active: "true"
      primary_key: [company_id]
      unique_key: [ticker]
      foreign_keys:
        - {column: security_id, references: securities.dim_security.security_id}
      tags: [dim, entity, corporate]

    fact_income_statement:
      from: bronze.company_income_statements
      select:
        ticker: ticker
        fiscal_date_ending: fiscal_date_ending
        report_type: report_type
        total_revenue: total_revenue
        gross_profit: gross_profit
        operating_income: operating_income
        net_income: net_income
        ebitda: ebitda
      derive:
        company_id: "CONCAT('COMPANY_', ticker)"
        report_date: "fiscal_date_ending"
        income_statement_id: "CONCAT(ticker, '_', fiscal_date_ending, '_', report_type)"
      primary_key: [income_statement_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: report_date, references: temporal.dim_calendar.date}

    fact_balance_sheet:
      from: bronze.company_balance_sheets
      select:
        ticker: ticker
        fiscal_date_ending: fiscal_date_ending
        report_type: report_type
        total_assets: total_assets
        total_liabilities: total_liabilities
        total_shareholder_equity: total_shareholder_equity
        cash_and_equivalents: cash_and_equivalents
        long_term_debt: long_term_debt
      derive:
        company_id: "CONCAT('COMPANY_', ticker)"
        report_date: "fiscal_date_ending"
        balance_sheet_id: "CONCAT(ticker, '_', fiscal_date_ending, '_', report_type)"
      primary_key: [balance_sheet_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: report_date, references: temporal.dim_calendar.date}

    fact_cash_flow:
      from: bronze.company_cash_flows
      select:
        ticker: ticker
        fiscal_date_ending: fiscal_date_ending
        report_type: report_type
        operating_cashflow: operating_cashflow
        cashflow_from_investment: cashflow_from_investment
        cashflow_from_financing: cashflow_from_financing
        free_cash_flow: free_cash_flow
      derive:
        company_id: "CONCAT('COMPANY_', ticker)"
        report_date: "fiscal_date_ending"
        cash_flow_id: "CONCAT(ticker, '_', fiscal_date_ending, '_', report_type)"
      primary_key: [cash_flow_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: report_date, references: temporal.dim_calendar.date}

    fact_earnings:
      from: bronze.company_earnings
      select:
        ticker: ticker
        fiscal_date_ending: fiscal_date_ending
        report_type: report_type
        reported_eps: reported_eps
        estimated_eps: estimated_eps
        surprise: surprise
        surprise_percentage: surprise_percentage
      derive:
        company_id: "CONCAT('COMPANY_', ticker)"
        report_date: "fiscal_date_ending"
        earnings_id: "CONCAT(ticker, '_', fiscal_date_ending, '_', report_type)"
      primary_key: [earnings_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: report_date, references: temporal.dim_calendar.date}

  edges:
    company_to_security:
      from: dim_company
      to: securities.dim_security
      on: [security_id=security_id]
      type: one_to_one
      description: "Company's primary security (for publicly traded)"

    company_to_stock:
      from: dim_company
      to: stocks.dim_stock
      on: [company_id=company_id]
      type: one_to_one
      description: "Company's primary stock listing"

    income_statement_to_company:
      from: fact_income_statement
      to: dim_company
      on: [company_id=company_id]
      type: many_to_one

    balance_sheet_to_company:
      from: fact_balance_sheet
      to: dim_company
      on: [company_id=company_id]
      type: many_to_one

    cash_flow_to_company:
      from: fact_cash_flow
      to: dim_company
      on: [company_id=company_id]
      type: many_to_one

    earnings_to_company:
      from: fact_earnings
      to: dim_company
      on: [company_id=company_id]
      type: many_to_one

    # Calendar joins for time-series
    income_statement_to_calendar:
      from: fact_income_statement
      to: temporal.dim_calendar
      on: [fiscal_date_ending=date]
      type: left

    balance_sheet_to_calendar:
      from: fact_balance_sheet
      to: temporal.dim_calendar
      on: [fiscal_date_ending=date]
      type: left

    cash_flow_to_calendar:
      from: fact_cash_flow
      to: temporal.dim_calendar
      on: [fiscal_date_ending=date]
      type: left

    earnings_to_calendar:
      from: fact_earnings
      to: temporal.dim_calendar
      on: [fiscal_date_ending=date]
      type: left

# Measures
measures:
  simple:
    company_count:
      description: "Number of companies"
      source: dim_company.company_id
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
