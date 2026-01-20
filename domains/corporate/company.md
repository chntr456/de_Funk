---
type: domain-model
model: company
version: 3.0
description: "Corporate legal entities with SEC registration and fundamentals"
tags: [company, corporate, fundamentals]

# Dependencies
depends_on: [temporal]

# Storage - provider/endpoint_id for bronze, domain hierarchy for silver
storage:
  format: delta
  bronze:
    provider: alpha_vantage
    tables:
      # Table names match endpoint_id from API config
      company_overview: alpha_vantage/company_overview  # Company fundamentals (COMPANY_OVERVIEW)
      income_statement: alpha_vantage/income_statement  # Income statement (INCOME_STATEMENT)
      balance_sheet: alpha_vantage/balance_sheet  # Balance sheet (BALANCE_SHEET)
      cash_flow: alpha_vantage/cash_flow  # Cash flow (CASH_FLOW)
      earnings: alpha_vantage/earnings  # Earnings (EARNINGS)
  silver:
    root: storage/silver/corporate

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
      - [security_id, integer, true, "FK to stocks.dim_stock (if publicly traded)", {fk: stocks.dim_stock.security_id}]

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
      # Keys
      - [balance_sheet_id, integer, false, "PK - Integer surrogate"]
      - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      # Attributes
      - [report_type, string, true, "annual or quarterly"]
      - [reported_currency, string, true, "Reporting currency"]
      # Assets - Current
      - [total_assets, double, true, "Total assets", {coerce: double}]
      - [total_current_assets, double, true, "Current assets", {coerce: double}]
      - [cash_and_equivalents, double, true, "Cash and equivalents", {coerce: double}]
      - [cash_and_short_term_investments, double, true, "Cash + short-term investments", {coerce: double}]
      - [inventory, double, true, "Inventory", {coerce: double}]
      - [current_net_receivables, double, true, "Receivables", {coerce: double}]
      - [other_current_assets, double, true, "Other current assets", {coerce: double}]
      # Assets - Non-current
      - [total_non_current_assets, double, true, "Non-current assets", {coerce: double}]
      - [property_plant_equipment, double, true, "PP&E", {coerce: double}]
      - [accumulated_depreciation, double, true, "Accumulated depreciation", {coerce: double}]
      - [intangible_assets, double, true, "Intangible assets", {coerce: double}]
      - [intangible_assets_ex_goodwill, double, true, "Intangibles ex goodwill", {coerce: double}]
      - [goodwill, double, true, "Goodwill", {coerce: double}]
      - [investments, double, true, "Total investments", {coerce: double}]
      - [long_term_investments, double, true, "Long-term investments", {coerce: double}]
      - [short_term_investments, double, true, "Short-term investments", {coerce: double}]
      - [other_non_current_assets, double, true, "Other non-current assets", {coerce: double}]
      # Liabilities - Current
      - [total_liabilities, double, true, "Total liabilities", {coerce: double}]
      - [total_current_liabilities, double, true, "Current liabilities", {coerce: double}]
      - [accounts_payable, double, true, "Accounts payable", {coerce: double}]
      - [deferred_revenue, double, true, "Deferred revenue", {coerce: double}]
      - [current_debt, double, true, "Current portion of debt", {coerce: double}]
      - [short_term_debt, double, true, "Short-term debt", {coerce: double}]
      - [other_current_liabilities, double, true, "Other current liabilities", {coerce: double}]
      # Liabilities - Non-current
      - [total_non_current_liabilities, double, true, "Non-current liabilities", {coerce: double}]
      - [capital_lease_obligations, double, true, "Capital lease obligations", {coerce: double}]
      - [long_term_debt, double, true, "Long-term debt", {coerce: double}]
      - [current_long_term_debt, double, true, "Current portion of LT debt", {coerce: double}]
      - [long_term_debt_noncurrent, double, true, "Non-current LT debt", {coerce: double}]
      - [short_long_term_debt_total, double, true, "Total debt", {coerce: double}]
      - [other_non_current_liabilities, double, true, "Other non-current liabilities", {coerce: double}]
      # Equity
      - [total_shareholder_equity, double, true, "Shareholder equity", {coerce: double}]
      - [treasury_stock, double, true, "Treasury stock", {coerce: double}]
      - [retained_earnings, double, true, "Retained earnings", {coerce: double}]
      - [common_stock, double, true, "Common stock", {coerce: double}]
      - [shares_outstanding, double, true, "Shares outstanding", {coerce: double}]

    measures:
      - [avg_total_assets, avg, total_assets, "Average total assets", {format: "$#,##0.00B"}]
      - [avg_equity, avg, total_shareholder_equity, "Average equity", {format: "$#,##0.00B"}]
      - [debt_to_equity, expression, "AVG(long_term_debt / NULLIF(total_shareholder_equity, 0))", "Debt to equity ratio", {format: "#,##0.00"}]
      - [current_ratio, expression, "AVG(total_current_assets / NULLIF(total_current_liabilities, 0))", "Current ratio", {format: "#,##0.00"}]
      - [quick_ratio, expression, "AVG((cash_and_equivalents + current_net_receivables) / NULLIF(total_current_liabilities, 0))", "Quick ratio", {format: "#,##0.00"}]

  fact_cash_flow:
    type: fact
    description: "Cash flow statement data"
    primary_key: [cash_flow_id]
    partition_by: [date_id]

    schema:
      # Keys
      - [cash_flow_id, integer, false, "PK - Integer surrogate"]
      - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      # Attributes
      - [report_type, string, true, "annual or quarterly"]
      - [reported_currency, string, true, "Reporting currency"]
      # Operating activities
      - [operating_cashflow, double, true, "Cash from operations", {coerce: double}]
      - [payments_for_operating_activities, double, true, "Operating payments", {coerce: double}]
      - [proceeds_from_operating_activities, double, true, "Operating proceeds", {coerce: double}]
      - [change_in_operating_liabilities, double, true, "Change in op liabilities", {coerce: double}]
      - [change_in_operating_assets, double, true, "Change in op assets", {coerce: double}]
      - [depreciation_depletion_amortization, double, true, "D&A", {coerce: double}]
      - [capital_expenditures, double, true, "CapEx", {coerce: double}]
      - [change_in_receivables, double, true, "Change in receivables", {coerce: double}]
      - [change_in_inventory, double, true, "Change in inventory", {coerce: double}]
      - [profit_loss, double, true, "Net profit/loss", {coerce: double}]
      # Investing activities
      - [cashflow_from_investment, double, true, "Cash from investing", {coerce: double}]
      # Financing activities
      - [cashflow_from_financing, double, true, "Cash from financing", {coerce: double}]
      - [proceeds_from_short_term_debt, double, true, "Short-term debt proceeds", {coerce: double}]
      - [payments_for_repurchase_common, double, true, "Buyback payments", {coerce: double}]
      - [payments_for_repurchase_equity, double, true, "Equity repurchase", {coerce: double}]
      - [payments_for_repurchase_preferred, double, true, "Preferred repurchase", {coerce: double}]
      - [dividend_payout, double, true, "Dividends paid", {coerce: double}]
      - [dividend_payout_common, double, true, "Common dividends", {coerce: double}]
      - [dividend_payout_preferred, double, true, "Preferred dividends", {coerce: double}]
      - [proceeds_from_common_stock, double, true, "Stock issuance proceeds", {coerce: double}]
      - [proceeds_from_long_term_debt, double, true, "LT debt proceeds", {coerce: double}]
      - [proceeds_from_preferred_stock, double, true, "Preferred stock proceeds", {coerce: double}]
      - [proceeds_from_repurchase_equity, double, true, "Equity repurchase proceeds", {coerce: double}]
      - [proceeds_from_treasury_stock, double, true, "Treasury stock proceeds", {coerce: double}]
      # Net change
      - [net_change_in_cash, double, true, "Net change in cash", {coerce: double}]
      - [change_in_exchange_rate, double, true, "FX impact", {coerce: double}]
      - [net_income, double, true, "Net income", {coerce: double}]
      # Computed
      - [free_cash_flow, double, true, "Free cash flow (operating - capex)", {coerce: double, derived: "operating_cashflow - ABS(COALESCE(capital_expenditures, 0))"}]

    measures:
      - [avg_fcf, avg, free_cash_flow, "Average free cash flow", {format: "$#,##0.00M"}]
      - [total_operating_cf, sum, operating_cashflow, "Total operating cash flow", {format: "$#,##0.00B"}]
      - [total_dividends, sum, dividend_payout, "Total dividends paid", {format: "$#,##0.00M"}]
      - [total_capex, sum, capital_expenditures, "Total CapEx", {format: "$#,##0.00M"}]

  fact_earnings:
    type: fact
    description: "Earnings data (EPS actual vs estimate)"
    primary_key: [earnings_id]
    partition_by: [date_id]

    schema:
      # Keys
      - [earnings_id, integer, false, "PK - Integer surrogate"]
      - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      # Attributes
      - [report_type, string, true, "annual or quarterly"]
      - [reported_date, date, true, "Actual earnings announcement date"]
      # EPS metrics
      - [reported_eps, double, true, "Reported EPS", {coerce: double}]
      - [estimated_eps, double, true, "Estimated EPS", {coerce: double}]
      - [surprise, double, true, "EPS surprise (actual - estimate)", {coerce: double}]
      - [surprise_percentage, double, true, "Surprise as percentage", {coerce: double}]
      # Computed
      - [beat_estimate, boolean, true, "Did actual beat estimate?", {derived: "reported_eps > estimated_eps"}]

    measures:
      - [avg_eps, avg, reported_eps, "Average EPS", {format: "$#,##0.00"}]
      - [avg_surprise_pct, avg, surprise_percentage, "Average surprise %", {format: "#,##0.00%"}]
      - [beat_count, expression, "SUM(CASE WHEN surprise > 0 THEN 1 ELSE 0 END)", "Earnings beats", {format: "#,##0"}]
      - [beat_rate, expression, "AVG(CASE WHEN beat_estimate THEN 1.0 ELSE 0.0 END) * 100", "Beat rate %", {format: "#,##0.0%"}]

# Graph
graph:
  nodes:
    dim_company:
      from: bronze.alpha_vantage.company_overview
      # Note: company_overview facet normalizes columns to snake_case
      # No filter needed - company_reference only contains companies with CIK
      select:
        # Identity
        cik: cik
        ticker: ticker
        company_name: company_name
        description: description
        # Classification
        asset_type: asset_type
        exchange_code: exchange_code
        sector: sector
        industry: industry
        country: country
        currency: currency
        # Contact/Info
        address: address
        official_site: official_site
        fiscal_year_end: fiscal_year_end
        # Valuation metrics
        market_cap: market_cap
        ebitda: ebitda
        pe_ratio: pe_ratio
        peg_ratio: peg_ratio
        book_value: book_value
        eps: eps
        trailing_pe: trailing_pe
        forward_pe: forward_pe
        price_to_sales: price_to_sales
        price_to_book: price_to_book
        ev_to_revenue: ev_to_revenue
        ev_to_ebitda: ev_to_ebitda
        # Profitability
        profit_margin: profit_margin
        operating_margin: operating_margin
        return_on_assets: return_on_assets
        return_on_equity: return_on_equity
        revenue_ttm: revenue_ttm
        gross_profit_ttm: gross_profit_ttm
        # Growth
        quarterly_earnings_growth: quarterly_earnings_growth
        quarterly_revenue_growth: quarterly_revenue_growth
        # Risk & Volatility
        beta: beta
        week_52_high: week_52_high
        week_52_low: week_52_low
        # Shares
        shares_outstanding: shares_outstanding
        shares_float: shares_float
        percent_insiders: percent_insiders
        percent_institutions: percent_institutions
        # Dividends
        dividend_per_share: dividend_per_share
        dividend_yield: dividend_yield
        dividend_date: dividend_date
        ex_dividend_date: ex_dividend_date
        # Analyst
        analyst_target_price: analyst_target_price
        analyst_rating_strong_buy: analyst_rating_strong_buy
        analyst_rating_buy: analyst_rating_buy
        analyst_rating_hold: analyst_rating_hold
        analyst_rating_sell: analyst_rating_sell
        analyst_rating_strong_sell: analyst_rating_strong_sell
      derive:
        company_id: "ABS(HASH(CONCAT('COMPANY_', COALESCE(cik, ticker))))"
        security_id: "ABS(HASH(ticker))"
        is_active: "true"
      primary_key: [company_id]
      unique_key: [ticker]
      foreign_keys:
        - {column: security_id, references: stocks.dim_stock.security_id}
      tags: [dim, entity, corporate]

    fact_income_statement:
      from: bronze.alpha_vantage.income_statement
      # Bronze columns are now snake_case and properly typed (via endpoint markdown coerce rules)
      select:
        # Identifiers
        ticker: ticker
        fiscal_date_ending: fiscal_date_ending
        report_type: report_type
        reported_currency: reported_currency
        # Revenue and gross profit
        total_revenue: total_revenue
        gross_profit: gross_profit
        cost_of_revenue: cost_of_revenue
        cost_of_goods_sold: cost_of_goods_sold
        # Operating income and expenses
        operating_income: operating_income
        operating_expenses: operating_expenses
        sg_and_a: sg_and_a
        research_and_development: research_and_development
        depreciation: depreciation
        depreciation_and_amortization: depreciation_and_amortization
        # Interest and investment income
        investment_income_net: investment_income_net
        net_interest_income: net_interest_income
        interest_income: interest_income
        interest_expense: interest_expense
        non_interest_income: non_interest_income
        other_non_operating_income: other_non_operating_income
        interest_and_debt_expense: interest_and_debt_expense
        # Net income
        income_before_tax: income_before_tax
        income_tax_expense: income_tax_expense
        net_income_from_continuing_ops: net_income_from_continuing_ops
        comprehensive_income: comprehensive_income
        net_income: net_income
        # EBIT/EBITDA
        ebit: ebit
        ebitda: ebitda
      derive:
        income_statement_id: "ABS(HASH(CONCAT(ticker, '_', CAST(fiscal_date_ending AS STRING), '_', report_type)))"
        company_id: "ABS(HASH(CONCAT('COMPANY_', ticker)))"
        date_id: "CAST(DATE_FORMAT(fiscal_date_ending, 'yyyyMMdd') AS INT)"
      # Drop natural keys - use FKs only (company_id → dim_company, date_id → temporal.dim_calendar)
      drop: [ticker, fiscal_date_ending]
      primary_key: [income_statement_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}

    fact_balance_sheet:
      from: bronze.alpha_vantage.balance_sheet
      # Bronze columns are now snake_case and properly typed (via endpoint markdown coerce rules)
      select:
        # Identifiers
        ticker: ticker
        fiscal_date_ending: fiscal_date_ending
        report_type: report_type
        reported_currency: reported_currency
        # Assets - Current
        total_assets: total_assets
        total_current_assets: total_current_assets
        cash_and_equivalents: cash_and_equivalents
        cash_and_short_term_investments: cash_and_short_term_investments
        inventory: inventory
        current_net_receivables: current_net_receivables
        other_current_assets: other_current_assets
        # Assets - Non-current
        total_non_current_assets: total_non_current_assets
        property_plant_equipment: property_plant_equipment
        accumulated_depreciation: accumulated_depreciation
        intangible_assets: intangible_assets
        intangible_assets_ex_goodwill: intangible_assets_ex_goodwill
        goodwill: goodwill
        investments: investments
        long_term_investments: long_term_investments
        short_term_investments: short_term_investments
        other_non_current_assets: other_non_current_assets
        # Liabilities - Current
        total_liabilities: total_liabilities
        total_current_liabilities: total_current_liabilities
        accounts_payable: accounts_payable
        deferred_revenue: deferred_revenue
        current_debt: current_debt
        short_term_debt: short_term_debt
        other_current_liabilities: other_current_liabilities
        # Liabilities - Non-current
        total_non_current_liabilities: total_non_current_liabilities
        capital_lease_obligations: capital_lease_obligations
        long_term_debt: long_term_debt
        current_long_term_debt: current_long_term_debt
        long_term_debt_noncurrent: long_term_debt_noncurrent
        short_long_term_debt_total: short_long_term_debt_total
        other_non_current_liabilities: other_non_current_liabilities
        # Equity
        total_shareholder_equity: total_shareholder_equity
        treasury_stock: treasury_stock
        retained_earnings: retained_earnings
        common_stock: common_stock
        shares_outstanding: shares_outstanding
      derive:
        balance_sheet_id: "ABS(HASH(CONCAT(ticker, '_', CAST(fiscal_date_ending AS STRING), '_', report_type)))"
        company_id: "ABS(HASH(CONCAT('COMPANY_', ticker)))"
        date_id: "CAST(DATE_FORMAT(fiscal_date_ending, 'yyyyMMdd') AS INT)"
      # Drop natural keys - use FKs only (company_id → dim_company, date_id → temporal.dim_calendar)
      drop: [ticker, fiscal_date_ending]
      primary_key: [balance_sheet_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}

    fact_cash_flow:
      from: bronze.alpha_vantage.cash_flow
      # Bronze columns are now snake_case and properly typed (via endpoint markdown coerce rules)
      # free_cash_flow is computed as derived column (not in Bronze)
      select:
        # Identifiers
        ticker: ticker
        fiscal_date_ending: fiscal_date_ending
        report_type: report_type
        reported_currency: reported_currency
        # Operating activities
        operating_cashflow: operating_cashflow
        payments_for_operating_activities: payments_for_operating_activities
        proceeds_from_operating_activities: proceeds_from_operating_activities
        change_in_operating_liabilities: change_in_operating_liabilities
        change_in_operating_assets: change_in_operating_assets
        depreciation_depletion_amortization: depreciation_depletion_amortization
        capital_expenditures: capital_expenditures
        change_in_receivables: change_in_receivables
        change_in_inventory: change_in_inventory
        profit_loss: profit_loss
        # Investing activities
        cashflow_from_investment: cashflow_from_investment
        # Financing activities
        cashflow_from_financing: cashflow_from_financing
        proceeds_from_short_term_debt: proceeds_from_short_term_debt
        payments_for_repurchase_common: payments_for_repurchase_common
        payments_for_repurchase_equity: payments_for_repurchase_equity
        payments_for_repurchase_preferred: payments_for_repurchase_preferred
        dividend_payout: dividend_payout
        dividend_payout_common: dividend_payout_common
        dividend_payout_preferred: dividend_payout_preferred
        proceeds_from_common_stock: proceeds_from_common_stock
        proceeds_from_long_term_debt: proceeds_from_long_term_debt
        proceeds_from_preferred_stock: proceeds_from_preferred_stock
        proceeds_from_repurchase_equity: proceeds_from_repurchase_equity
        proceeds_from_treasury_stock: proceeds_from_treasury_stock
        # Net change in cash
        net_change_in_cash: net_change_in_cash
        change_in_exchange_rate: change_in_exchange_rate
        net_income: net_income
      derive:
        cash_flow_id: "ABS(HASH(CONCAT(ticker, '_', CAST(fiscal_date_ending AS STRING), '_', report_type)))"
        company_id: "ABS(HASH(CONCAT('COMPANY_', ticker)))"
        date_id: "CAST(DATE_FORMAT(fiscal_date_ending, 'yyyyMMdd') AS INT)"
        free_cash_flow: "COALESCE(operating_cashflow, 0) - COALESCE(capital_expenditures, 0)"
      # Drop natural keys - use FKs only (company_id → dim_company, date_id → temporal.dim_calendar)
      drop: [ticker, fiscal_date_ending]
      primary_key: [cash_flow_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}

    fact_earnings:
      from: bronze.alpha_vantage.earnings
      optional: true  # Skip if bronze table doesn't exist yet
      # Bronze columns are now snake_case and properly typed (via endpoint markdown coerce rules)
      select:
        # Identifiers
        ticker: ticker
        fiscal_date_ending: fiscal_date_ending
        report_type: report_type
        reported_date: reported_date  # Actual announcement date
        # EPS metrics
        reported_eps: reported_eps
        estimated_eps: estimated_eps
        surprise: surprise
        surprise_percentage: surprise_percentage
      derive:
        earnings_id: "ABS(HASH(CONCAT(ticker, '_', CAST(fiscal_date_ending AS STRING), '_', report_type)))"
        company_id: "ABS(HASH(CONCAT('COMPANY_', ticker)))"
        date_id: "CAST(DATE_FORMAT(fiscal_date_ending, 'yyyyMMdd') AS INT)"
        beat_estimate: "CASE WHEN reported_eps > estimated_eps THEN true ELSE false END"
      # Drop natural keys - use FKs only (company_id → dim_company, date_id → temporal.dim_calendar)
      drop: [ticker, fiscal_date_ending]
      primary_key: [earnings_id]
      unique_key: [ticker, fiscal_date_ending, report_type]
      foreign_keys:
        - {column: company_id, references: dim_company.company_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}

  edges:
    # Primary join path: company → stock via company_id (recommended)
    # Both tables derive company_id from HASH('COMPANY_' + ticker/cik)
    company_to_stock:
      from: dim_company
      to: stocks.dim_stock
      on: [company_id=company_id]
      type: one_to_one
      description: "Link company to its stock dimension via company_id"

    # Alternative join path: company → stock via security_id
    # Both tables derive security_id from HASH(ticker)
    company_to_stock_by_security:
      from: dim_company
      to: stocks.dim_stock
      on: [security_id=security_id]
      type: one_to_one
      description: "Alternative link via security_id (ticker hash)"

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

### Date Handling - Calendar as Source of Truth

Facts use `date_id` FK pointing to the calendar dimension (`temporal.dim_calendar`). All date-related attributes (date, year, quarter, fiscal_year, etc.) come from the calendar join. The UI reconciles these joins through defined edge pathways.

```sql
-- Query with calendar join (auto-resolved by UI edge pathways)
SELECT
    c.date AS fiscal_date,
    c.year,
    c.quarter,
    c.fiscal_year,
    co.ticker,
    i.total_revenue,
    i.net_income
FROM fact_income_statement i
JOIN temporal.dim_calendar c ON i.date_id = c.date_id
JOIN dim_company co ON i.company_id = co.company_id
WHERE c.year = 2024
  AND i.report_type = 'annual'
```

**Edge pathways defined:**
- `income_to_calendar`: fact_income_statement → temporal.dim_calendar (via date_id)
- `balance_to_calendar`: fact_balance_sheet → temporal.dim_calendar (via date_id)
- `cashflow_to_calendar`: fact_cash_flow → temporal.dim_calendar (via date_id)
- `earnings_to_calendar`: fact_earnings → temporal.dim_calendar (via date_id)

### Data Sources

| Source | Provider | Endpoint |
|--------|----------|----------|
| company_overview | Alpha Vantage | COMPANY_OVERVIEW |
| income_statement | Alpha Vantage | INCOME_STATEMENT |
| balance_sheet | Alpha Vantage | BALANCE_SHEET |
| cash_flow | Alpha Vantage | CASH_FLOW |
| earnings | Alpha Vantage | EARNINGS |

### Notes

- CIK may be NULL from bulk LISTING_STATUS
- Financial statements link via integer `company_id`
- All date filtering through `dim_calendar` join
