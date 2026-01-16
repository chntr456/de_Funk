---
type: domain-model
model: company
version: 3.0
description: "Corporate legal entities with SEC registration and fundamentals"
tags: [company, corporate, fundamentals]

# Dependencies
depends_on: [temporal]

# Storage
storage:
  root: storage/silver/company
  format: delta

# Build
build:
  partitions: []
  sort_by: [company_id]
  optimize: true

# Tables
tables:
  dim_company:
    type: dimension
    description: "Corporate entity master"
    primary_key: [company_id]
    unique_key: [ticker]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - all integers
      - [company_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('COMPANY_', COALESCE(cik, ticker))))"}]
      - [security_id, integer, true, "FK to dim_security (if publicly traded)", {fk: securities.dim_security.security_id}]

      # Natural keys
      - [cik, string, true, "SEC Central Index Key", {pattern: "^[0-9]{10}$", transform: "zfill(10)"}]
      - [ticker, string, false, "Primary ticker symbol", {unique: true}]

      # Company attributes
      - [company_name, string, false, "Company name"]
      - [exchange_code, string, true, "Primary exchange (NYSE, NASDAQ)"]
      - [sector, string, true, "GICS Sector"]
      - [industry, string, true, "GICS Industry"]
      - [market_cap, double, true, "Market capitalization", {coerce: double}]
      - [country, string, true, "Country of incorporation", {default: "US"}]
      - [currency, string, true, "Reporting currency", {default: "USD"}]
      - [is_active, boolean, true, "Currently active", {default: true}]

    # Measures on the table
    measures:
      - [company_count, count_distinct, company_id, "Number of companies", {format: "#,##0"}]
      - [avg_market_cap, avg, market_cap, "Average market cap", {format: "$#,##0.00B"}]

  fact_income_statement:
    type: fact
    description: "Income statement data from SEC filings"
    primary_key: [income_statement_id]
    partition_by: [date_id]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - all integers
      - [income_statement_id, integer, false, "PK - Integer surrogate"]
      - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
      - [date_id, integer, false, "FK to dim_calendar (fiscal_date_ending)", {fk: temporal.dim_calendar.date_id}]

      # Attributes
      - [report_type, string, true, "annual or quarterly", {enum: [annual, quarterly]}]

      # Metrics
      - [total_revenue, double, true, "Total revenue", {coerce: double}]
      - [gross_profit, double, true, "Gross profit", {coerce: double}]
      - [operating_income, double, true, "Operating income", {coerce: double}]
      - [net_income, double, true, "Net income", {coerce: double}]
      - [ebitda, double, true, "EBITDA", {coerce: double}]
      - [reported_currency, string, true, "Reporting currency"]

    measures:
      - [total_revenue_sum, sum, total_revenue, "Total revenue", {format: "$#,##0.00B"}]
      - [avg_net_income, avg, net_income, "Average net income", {format: "$#,##0.00M"}]
      - [avg_margin, expression, "AVG(net_income / NULLIF(total_revenue, 0) * 100)", "Average profit margin", {format: "#,##0.00%"}]

  fact_balance_sheet:
    type: fact
    description: "Balance sheet data from SEC filings"
    primary_key: [balance_sheet_id]
    partition_by: [date_id]

    schema:
      - [balance_sheet_id, integer, false, "PK - Integer surrogate"]
      - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [report_type, string, true, "annual or quarterly"]
      - [total_assets, double, true, "Total assets", {coerce: double}]
      - [total_liabilities, double, true, "Total liabilities", {coerce: double}]
      - [total_shareholder_equity, double, true, "Shareholder equity", {coerce: double}]
      - [cash_and_equivalents, double, true, "Cash and equivalents", {coerce: double}]
      - [long_term_debt, double, true, "Long-term debt", {coerce: double}]
      - [reported_currency, string, true, "Reporting currency"]

    measures:
      - [avg_total_assets, avg, total_assets, "Average total assets", {format: "$#,##0.00B"}]
      - [avg_equity, avg, total_shareholder_equity, "Average equity", {format: "$#,##0.00B"}]
      - [debt_to_equity, expression, "AVG(long_term_debt / NULLIF(total_shareholder_equity, 0))", "Debt to equity ratio", {format: "#,##0.00"}]

  fact_cash_flow:
    type: fact
    description: "Cash flow statement data"
    primary_key: [cash_flow_id]
    partition_by: [date_id]

    schema:
      - [cash_flow_id, integer, false, "PK - Integer surrogate"]
      - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [report_type, string, true, "annual or quarterly"]
      - [operating_cashflow, double, true, "Operating cash flow", {coerce: double}]
      - [cashflow_from_investment, double, true, "Investing cash flow", {coerce: double}]
      - [cashflow_from_financing, double, true, "Financing cash flow", {coerce: double}]
      - [free_cash_flow, double, true, "Free cash flow", {coerce: double}]
      - [reported_currency, string, true, "Reporting currency"]

    measures:
      - [avg_fcf, avg, free_cash_flow, "Average free cash flow", {format: "$#,##0.00M"}]
      - [total_operating_cf, sum, operating_cashflow, "Total operating cash flow", {format: "$#,##0.00B"}]

  fact_earnings:
    type: fact
    description: "Earnings data (EPS actual vs estimate)"
    primary_key: [earnings_id]
    partition_by: [date_id]

    schema:
      - [earnings_id, integer, false, "PK - Integer surrogate"]
      - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [report_type, string, true, "annual or quarterly"]
      - [reported_eps, double, true, "Reported EPS", {coerce: double}]
      - [estimated_eps, double, true, "Estimated EPS", {coerce: double}]
      - [surprise, double, true, "EPS surprise", {coerce: double}]
      - [surprise_percentage, double, true, "Surprise percentage", {coerce: double}]

    measures:
      - [avg_eps, avg, reported_eps, "Average EPS", {format: "$#,##0.00"}]
      - [avg_surprise_pct, avg, surprise_percentage, "Average surprise %", {format: "#,##0.00%"}]
      - [beat_count, expression, "SUM(CASE WHEN surprise > 0 THEN 1 ELSE 0 END)", "Earnings beats", {format: "#,##0"}]

# Graph
graph:
  nodes:
    dim_company:
      from: bronze.company_reference
      filters:
        - "AssetType IN ('Stock', 'Common Stock', 'Preferred Stock')"
      select:
        # Map Alpha Vantage COMPANY_OVERVIEW column names to silver schema
        cik: CIK
        company_name: Name
        ticker: Symbol
        exchange_code: Exchange
        sector: Sector
        industry: Industry
        market_cap: MarketCapitalization
        currency: Currency
      derive:
        company_id: "ABS(HASH(CONCAT('COMPANY_', COALESCE(CIK, Symbol))))"
        security_id: "ABS(HASH(Symbol))"
        country: "'US'"
        is_active: "true"
      primary_key: [company_id]
      unique_key: [ticker]
      foreign_keys:
        - {column: security_id, references: securities.dim_security.security_id}
      tags: [dim, entity, corporate]

    fact_income_statement:
      from: bronze.income_statements
      select:
        # Map camelCase bronze columns to snake_case silver columns
        ticker: ticker
        fiscal_date_ending: fiscalDateEnding
        report_type: report_type
        total_revenue: totalRevenue
        gross_profit: grossProfit
        operating_income: operatingIncome
        net_income: netIncome
        ebitda: ebitda
        reported_currency: reportedCurrency
      derive:
        income_statement_id: "ABS(HASH(CONCAT(ticker, '_', fiscalDateEnding, '_', report_type)))"
        company_id: "ABS(HASH(CONCAT('COMPANY_', ticker)))"
        date_id: "CAST(DATE_FORMAT(fiscalDateEnding, 'yyyyMMdd') AS INT)"
      primary_key: [income_statement_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}

    fact_balance_sheet:
      from: bronze.balance_sheets
      select:
        # Map camelCase bronze columns to snake_case silver columns
        ticker: ticker
        fiscal_date_ending: fiscalDateEnding
        report_type: report_type
        total_assets: totalAssets
        total_liabilities: totalLiabilities
        total_shareholder_equity: totalShareholderEquity
        cash_and_equivalents: cashAndCashEquivalentsAtCarryingValue
        long_term_debt: longTermDebt
        reported_currency: reportedCurrency
      derive:
        balance_sheet_id: "ABS(HASH(CONCAT(ticker, '_', fiscalDateEnding, '_', report_type)))"
        company_id: "ABS(HASH(CONCAT('COMPANY_', ticker)))"
        date_id: "CAST(DATE_FORMAT(fiscalDateEnding, 'yyyyMMdd') AS INT)"
      primary_key: [balance_sheet_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}

    fact_cash_flow:
      from: bronze.cash_flows
      select:
        # Map camelCase bronze columns to snake_case silver columns
        ticker: ticker
        fiscal_date_ending: fiscalDateEnding
        report_type: report_type
        operating_cashflow: operatingCashflow
        cashflow_from_investment: cashflowFromInvestment
        cashflow_from_financing: cashflowFromFinancing
        reported_currency: reportedCurrency
      derive:
        cash_flow_id: "ABS(HASH(CONCAT(ticker, '_', fiscalDateEnding, '_', report_type)))"
        company_id: "ABS(HASH(CONCAT('COMPANY_', ticker)))"
        date_id: "CAST(DATE_FORMAT(fiscalDateEnding, 'yyyyMMdd') AS INT)"
        # Free cash flow = operating - capex (approximation)
        free_cash_flow: "operatingCashflow - ABS(COALESCE(capitalExpenditures, 0))"
      primary_key: [cash_flow_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}

    fact_earnings:
      from: bronze.earnings
      select:
        # Map camelCase bronze columns to snake_case silver columns
        ticker: ticker
        fiscal_date_ending: fiscalDateEnding
        report_type: report_type
        reported_eps: reportedEPS
        estimated_eps: estimatedEPS
        surprise: surprise
        surprise_percentage: surprisePercentage
      derive:
        earnings_id: "ABS(HASH(CONCAT(ticker, '_', fiscalDateEnding, '_', report_type)))"
        company_id: "ABS(HASH(CONCAT('COMPANY_', ticker)))"
        date_id: "CAST(DATE_FORMAT(fiscal_date_ending, 'yyyyMMdd') AS INT)"
      primary_key: [earnings_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}

  edges:
    company_to_security:
      from: dim_company
      to: securities.dim_security
      on: [security_id=security_id]
      type: one_to_one

    company_to_stock:
      from: dim_company
      to: stocks.dim_stock
      on: [company_id=company_id]
      type: one_to_one

    income_to_company:
      from: fact_income_statement
      to: dim_company
      on: [company_id=company_id]
      type: many_to_one

    income_to_calendar:
      from: fact_income_statement
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one

    balance_to_company:
      from: fact_balance_sheet
      to: dim_company
      on: [company_id=company_id]
      type: many_to_one

    balance_to_calendar:
      from: fact_balance_sheet
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one

    cashflow_to_company:
      from: fact_cash_flow
      to: dim_company
      on: [company_id=company_id]
      type: many_to_one

    cashflow_to_calendar:
      from: fact_cash_flow
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one

    earnings_to_company:
      from: fact_earnings
      to: dim_company
      on: [company_id=company_id]
      type: many_to_one

    earnings_to_calendar:
      from: fact_earnings
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one

# Metadata
metadata:
  domain: corporate
  owner: data_engineering
  sla_hours: 24
status: active
---

## Company Model

Corporate legal entities with SEC registration and financial fundamentals.

### Integer Keys

| Key | Type | Derivation |
|-----|------|------------|
| `company_id` | integer | `HASH('COMPANY_' + cik)` |
| `security_id` | integer | `HASH(ticker)` |
| `date_id` | integer | `YYYYMMDD` format |
| `{fact}_id` | integer | `HASH(ticker + date + type)` |

### No Date Columns on Facts

All facts use `date_id` FK instead of `fiscal_date_ending`:

```sql
-- Get income statements with actual dates
SELECT
    c.date AS fiscal_date,
    c.year,
    c.quarter,
    co.ticker,
    i.total_revenue,
    i.net_income
FROM fact_income_statement i
JOIN temporal.dim_calendar c ON i.date_id = c.date_id
JOIN dim_company co ON i.company_id = co.company_id
WHERE c.year = 2024
  AND i.report_type = 'annual'
```

### Data Sources

| Source | Provider |
|--------|----------|
| company_reference | Alpha Vantage |
| company_income_statements | Alpha Vantage |
| company_balance_sheets | Alpha Vantage |
| company_cash_flows | Alpha Vantage |
| company_earnings | Alpha Vantage |

### Notes

- CIK may be NULL from bulk LISTING_STATUS
- Financial statements link via integer `company_id`
- All date filtering through `dim_calendar` join
