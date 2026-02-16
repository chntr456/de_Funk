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
  - [statement_type, string, false, "Source statement", {enum: [INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW]}]
  - [parent_account_id, integer, true, "Hierarchy parent", {fk: dim_financial_account.account_id}]
  - [level, integer, true, "Hierarchy depth"]
  - [display_order, integer, true, "Sort order within statement"]
  - [is_subtotal, boolean, false, "Subtotal/total line", {default: false}]

data:
  # Income Statement accounts
  - {account_code: TOTAL_REVENUE, account_name: "Total Revenue", account_type: REVENUE, statement_type: INCOME_STATEMENT, level: 1, display_order: 1}
  - {account_code: COST_OF_REVENUE, account_name: "Cost of Revenue", account_type: EXPENSE, statement_type: INCOME_STATEMENT, level: 1, display_order: 2}
  - {account_code: GROSS_PROFIT, account_name: "Gross Profit", account_type: REVENUE, statement_type: INCOME_STATEMENT, level: 1, display_order: 3, is_subtotal: true}
  - {account_code: OPERATING_EXPENSES, account_name: "Operating Expenses", account_type: EXPENSE, statement_type: INCOME_STATEMENT, level: 1, display_order: 4}
  - {account_code: OPERATING_INCOME, account_name: "Operating Income", account_type: REVENUE, statement_type: INCOME_STATEMENT, level: 1, display_order: 5, is_subtotal: true}
  - {account_code: EBITDA, account_name: "EBITDA", account_type: REVENUE, statement_type: INCOME_STATEMENT, level: 1, display_order: 6, is_subtotal: true}
  - {account_code: NET_INCOME, account_name: "Net Income", account_type: REVENUE, statement_type: INCOME_STATEMENT, level: 1, display_order: 7, is_subtotal: true}
  # Balance Sheet accounts
  - {account_code: TOTAL_ASSETS, account_name: "Total Assets", account_type: ASSET, statement_type: BALANCE_SHEET, level: 1, display_order: 10, is_subtotal: true}
  - {account_code: TOTAL_CURRENT_ASSETS, account_name: "Total Current Assets", account_type: ASSET, statement_type: BALANCE_SHEET, level: 2, display_order: 11, is_subtotal: true}
  - {account_code: CASH_AND_EQUIVALENTS, account_name: "Cash and Equivalents", account_type: ASSET, statement_type: BALANCE_SHEET, level: 3, display_order: 12}
  - {account_code: TOTAL_LIABILITIES, account_name: "Total Liabilities", account_type: LIABILITY, statement_type: BALANCE_SHEET, level: 1, display_order: 20, is_subtotal: true}
  - {account_code: TOTAL_CURRENT_LIABILITIES, account_name: "Total Current Liabilities", account_type: LIABILITY, statement_type: BALANCE_SHEET, level: 2, display_order: 21, is_subtotal: true}
  - {account_code: LONG_TERM_DEBT, account_name: "Long-Term Debt", account_type: LIABILITY, statement_type: BALANCE_SHEET, level: 2, display_order: 22}
  - {account_code: TOTAL_SHAREHOLDER_EQUITY, account_name: "Total Shareholder Equity", account_type: EQUITY, statement_type: BALANCE_SHEET, level: 1, display_order: 30, is_subtotal: true}
  - {account_code: RETAINED_EARNINGS, account_name: "Retained Earnings", account_type: EQUITY, statement_type: BALANCE_SHEET, level: 2, display_order: 31}
  - {account_code: SHARES_OUTSTANDING, account_name: "Shares Outstanding", account_type: EQUITY, statement_type: BALANCE_SHEET, level: 2, display_order: 32}
  # Cash Flow accounts
  - {account_code: OPERATING_CASHFLOW, account_name: "Cash from Operations", account_type: CASH_FLOW, statement_type: CASH_FLOW, level: 1, display_order: 40}
  - {account_code: CAPITAL_EXPENDITURES, account_name: "Capital Expenditures", account_type: CASH_FLOW, statement_type: CASH_FLOW, level: 1, display_order: 41}
  - {account_code: CASHFLOW_FROM_INVESTMENT, account_name: "Cash from Investing", account_type: CASH_FLOW, statement_type: CASH_FLOW, level: 1, display_order: 42}
  - {account_code: CASHFLOW_FROM_FINANCING, account_name: "Cash from Financing", account_type: CASH_FLOW, statement_type: CASH_FLOW, level: 1, display_order: 43}
  - {account_code: DIVIDEND_PAYOUT, account_name: "Dividends Paid", account_type: CASH_FLOW, statement_type: CASH_FLOW, level: 1, display_order: 44}

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
