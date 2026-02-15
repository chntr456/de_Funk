---
type: domain-base
model: chart_of_accounts
version: 1.0
description: "Chart of accounts - hierarchical expense/revenue classification"
extends: _base._base_.entity

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [account_id, integer, nullable: false, description: "Primary key"]
  - [account_code, string, nullable: false, description: "Account code (e.g., 5000, SALARY)"]
  - [account_name, string, nullable: false, description: "Account name"]
  - [account_type, string, nullable: false, description: "ASSET, LIABILITY, REVENUE, EXPENSE, EQUITY"]
  - [parent_account_id, integer, nullable: true, description: "Parent account for hierarchy"]
  - [level, integer, nullable: false, description: "Hierarchy level (1=top)"]
  - [is_active, boolean, nullable: false, description: "Currently in use"]

tables:
  _dim_chart_of_accounts:
    type: dimension
    primary_key: [account_id]
    unique_key: [account_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [account_id, integer, false, "PK", {derived: "ABS(HASH(account_code))"}]
      - [account_code, string, false, "Natural key"]
      - [account_name, string, false, "Display name"]
      - [account_type, string, false, "Classification", {enum: [ASSET, LIABILITY, REVENUE, EXPENSE, EQUITY]}]
      - [parent_account_id, integer, true, "Self-referencing FK", {fk: _dim_chart_of_accounts.account_id}]
      - [level, integer, false, "Hierarchy depth", {default: 1}]
      - [is_active, boolean, false, "Currently used", {default: true}]

    measures:
      - [account_count, count_distinct, account_id, "Number of accounts", {format: "#,##0"}]
      - [expense_account_count, expression, "SUM(CASE WHEN account_type = 'EXPENSE' THEN 1 ELSE 0 END)", "Expense accounts", {format: "#,##0"}]
      - [revenue_account_count, expression, "SUM(CASE WHEN account_type = 'REVENUE' THEN 1 ELSE 0 END)", "Revenue accounts", {format: "#,##0"}]

domain: accounting
tags: [base, template, accounting, chart_of_accounts]
status: active
---

## Chart of Accounts Base Template

Hierarchical classification of financial accounts. Extends `_base._base_.entity` with accounting-specific fields.

### Account Types

| Type | Description | Example |
|------|-------------|---------|
| ASSET | Owned resources | Cash, Receivables |
| LIABILITY | Owed obligations | Payables, Bonds |
| REVENUE | Income sources | Taxes, Fees, Grants |
| EXPENSE | Spending categories | Salaries, Contracts, Supplies |
| EQUITY | Net position | Fund Balance |

### Hierarchy

Accounts form a tree via `parent_account_id`:

```
EXPENSE (level 1)
  PERSONNEL (level 2)
    SALARIES (level 3)
    BENEFITS (level 3)
  CONTRACTUAL (level 2)
    PROFESSIONAL_SERVICES (level 3)
    UTILITIES (level 3)
```

### Usage

```yaml
extends: _base.accounting.chart_of_accounts
```
