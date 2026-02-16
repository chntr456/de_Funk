---
type: domain-model-table
table: fact_financial_statements
table_type: fact
primary_key: [statement_entry_id]
partition_by: [period_end_date_id]

# Built by unpivoting wide source tables into row-per-line-item
# Sources: income_statement, balance_sheet, cash_flow bronze tables
transform: unpivot
unpivot_sources:
  - from: bronze.income_statement
    account_mapping:
      - [total_revenue, TOTAL_REVENUE]
      - [cost_of_revenue, COST_OF_REVENUE]
      - [gross_profit, GROSS_PROFIT]
      - [operating_expenses, OPERATING_EXPENSES]
      - [operating_income, OPERATING_INCOME]
      - [ebitda, EBITDA]
      - [net_income, NET_INCOME]
  - from: bronze.balance_sheet
    account_mapping:
      - [total_assets, TOTAL_ASSETS]
      - [total_current_assets, TOTAL_CURRENT_ASSETS]
      - [cash_and_equivalents, CASH_AND_EQUIVALENTS]
      - [total_liabilities, TOTAL_LIABILITIES]
      - [total_current_liabilities, TOTAL_CURRENT_LIABILITIES]
      - [long_term_debt, LONG_TERM_DEBT]
      - [total_shareholder_equity, TOTAL_SHAREHOLDER_EQUITY]
      - [retained_earnings, RETAINED_EARNINGS]
      - [shares_outstanding, SHARES_OUTSTANDING]
  - from: bronze.cash_flow
    account_mapping:
      - [operating_cashflow, OPERATING_CASHFLOW]
      - [capital_expenditures, CAPITAL_EXPENDITURES]
      - [cashflow_from_investment, CASHFLOW_FROM_INVESTMENT]
      - [cashflow_from_financing, CASHFLOW_FROM_FINANCING]
      - [dividend_payout, DIVIDEND_PAYOUT]

# [column, type, nullable, description, {options}]
schema:
  - [statement_entry_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(company_id, '_', account_id, '_', period_end_date_id, '_', report_type)))"}]
  - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
  - [account_id, integer, false, "FK to dim_financial_account", {fk: dim_financial_account.account_id, derived: "ABS(HASH(account_code))"}]
  - [period_start_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
  - [period_end_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
  - [report_type, string, false, "annual or quarterly"]
  - [amount, double, false, "Line item value"]
  - [reported_currency, string, true, "Reporting currency"]

measures:
  - [entry_count, count_distinct, statement_entry_id, "Statement entries", {format: "#,##0"}]
  - [total_amount, sum, amount, "Total amount", {format: "$#,##0"}]
---

## Financial Statements Fact

Normalized financial statement data. Each row is one line item for one company in one reporting period. Built by unpivoting wide source tables (income_statement, balance_sheet, cash_flow) into row-per-line-item format.

### Unpivot Transform

Source columns are mapped to account codes via `unpivot_sources`. For example, the `total_revenue` column from `bronze.income_statement` becomes a row where `account_code = 'TOTAL_REVENUE'` and `amount` = the revenue value.

### Query Pattern

```sql
-- Get all income statement items for AAPL, 2024 annual
SELECT fa.account_name, fs.amount
FROM fact_financial_statements fs
JOIN dim_financial_account fa ON fs.account_id = fa.account_id
JOIN dim_company c ON fs.company_id = c.company_id
WHERE c.ticker = 'AAPL'
  AND fa.statement_type = 'INCOME_STATEMENT'
  AND fs.report_type = 'annual'
ORDER BY fa.display_order;
```
