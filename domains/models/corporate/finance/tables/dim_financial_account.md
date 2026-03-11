---
type: domain-model-table
table: dim_financial_account
extends: _base.accounting.chart_of_accounts._dim_chart_of_accounts
table_type: dimension
static: true
primary_key: [account_id]
unique_key: [account_code]

# [column, type, nullable, description, {options}]
schema:
  - [account_id, integer, false, "PK", {derived: "ABS(HASH(account_code))"}]
  - [account_code, string, false, "Line item code (e.g., TOTAL_REVENUE)"]
  - [account_name, string, false, "Display name"]
  - [account_type, string, false, "Classification", {enum: [ASSET, LIABILITY, REVENUE, EXPENSE, EQUITY, CASH_FLOW]}]
  - [account_subtype, string, true, "Sub-classification (current, non_current, operating)"]
  - [parent_account_id, integer, true, "Hierarchy parent", {fk: dim_financial_account.account_id}]
  - [level, integer, true, "Hierarchy depth"]
  - [statement_section, string, false, "Financial statement", {enum: [BALANCE_SHEET, INCOME_STATEMENT, CASH_FLOW]}]
  - [cash_flow_category, string, true, "Cash flow bucket", {enum: [OPERATING, INVESTING, FINANCING]}]
  - [normal_balance, string, true, "Balance direction", {enum: [DEBIT, CREDIT]}]
  - [is_contra, boolean, true, "Contra account flag", {default: false}]
  - [is_rollup, boolean, true, "Summary/rollup account", {default: false}]
  - [format_type, string, true, "Display format", {enum: [CURRENCY, PERCENTAGE, RATIO], default: "CURRENCY"}]
  - [display_order, integer, true, "Sort order within statement"]

data:
  # Income Statement accounts
  - {account_code: TOTAL_REVENUE, account_name: "Total Revenue", account_type: REVENUE, statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 1}
  - {account_code: COST_OF_REVENUE, account_name: "Cost of Revenue", account_type: EXPENSE, account_subtype: OPERATING, statement_section: INCOME_STATEMENT, normal_balance: DEBIT, format_type: CURRENCY, level: 1, display_order: 2}
  - {account_code: GROSS_PROFIT, account_name: "Gross Profit", account_type: REVENUE, statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 3}
  - {account_code: OPERATING_EXPENSES, account_name: "Operating Expenses", account_type: EXPENSE, account_subtype: OPERATING, statement_section: INCOME_STATEMENT, normal_balance: DEBIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 4}
  - {account_code: OPERATING_INCOME, account_name: "Operating Income", account_type: REVENUE, account_subtype: OPERATING, statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 5}
  - {account_code: EBITDA, account_name: "EBITDA", account_type: REVENUE, statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 6}
  - {account_code: NET_INCOME, account_name: "Net Income", account_type: REVENUE, statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 7}
  # Balance Sheet accounts
  - {account_code: TOTAL_ASSETS, account_name: "Total Assets", account_type: ASSET, statement_section: BALANCE_SHEET, normal_balance: DEBIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 10}
  - {account_code: TOTAL_CURRENT_ASSETS, account_name: "Total Current Assets", account_type: ASSET, account_subtype: CURRENT, statement_section: BALANCE_SHEET, normal_balance: DEBIT, is_rollup: true, format_type: CURRENCY, level: 2, display_order: 11}
  - {account_code: CASH_AND_EQUIVALENTS, account_name: "Cash and Equivalents", account_type: ASSET, account_subtype: CURRENT, statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 12}
  - {account_code: TOTAL_LIABILITIES, account_name: "Total Liabilities", account_type: LIABILITY, statement_section: BALANCE_SHEET, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 20}
  - {account_code: TOTAL_CURRENT_LIABILITIES, account_name: "Total Current Liabilities", account_type: LIABILITY, account_subtype: CURRENT, statement_section: BALANCE_SHEET, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 2, display_order: 21}
  - {account_code: LONG_TERM_DEBT, account_name: "Long-Term Debt", account_type: LIABILITY, account_subtype: NON_CURRENT, statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 2, display_order: 22}
  - {account_code: TOTAL_SHAREHOLDER_EQUITY, account_name: "Total Shareholder Equity", account_type: EQUITY, statement_section: BALANCE_SHEET, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 30}
  - {account_code: RETAINED_EARNINGS, account_name: "Retained Earnings", account_type: EQUITY, statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 2, display_order: 31}
  - {account_code: SHARES_OUTSTANDING, account_name: "Shares Outstanding", account_type: EQUITY, statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: INTEGER, level: 2, display_order: 32}
  # Cash Flow accounts
  - {account_code: OPERATING_CASHFLOW, account_name: "Cash from Operations", account_type: CASH_FLOW, statement_section: CASH_FLOW, cash_flow_category: OPERATING, normal_balance: DEBIT, format_type: CURRENCY, level: 1, display_order: 40}
  - {account_code: CAPITAL_EXPENDITURES, account_name: "Capital Expenditures", account_type: CASH_FLOW, statement_section: CASH_FLOW, cash_flow_category: INVESTING, normal_balance: DEBIT, format_type: CURRENCY, level: 1, display_order: 41}
  - {account_code: CASHFLOW_FROM_INVESTMENT, account_name: "Cash from Investing", account_type: CASH_FLOW, statement_section: CASH_FLOW, cash_flow_category: INVESTING, normal_balance: DEBIT, format_type: CURRENCY, level: 1, display_order: 42}
  - {account_code: CASHFLOW_FROM_FINANCING, account_name: "Cash from Financing", account_type: CASH_FLOW, statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 1, display_order: 43}
  - {account_code: DIVIDEND_PAYOUT, account_name: "Dividends Paid", account_type: CASH_FLOW, statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 1, display_order: 44}

measures:
  - [account_count, count_distinct, account_id, "Financial accounts", {format: "#,##0"}]
---

## Financial Account Dimension

Chart of accounts for SEC financial statement line items. Static dimension -- accounts are seeded from the `data:` section.

### Statement Types

| Type | Content |
|------|---------|
| INCOME_STATEMENT | Revenue, expenses, profit metrics |
| BALANCE_SHEET | Assets, liabilities, equity |
| CASH_FLOW | Operating, investing, financing flows |
