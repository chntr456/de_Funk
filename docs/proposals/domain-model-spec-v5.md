# Domain Model Specification v5.0

**Status**: Draft - Requires Decision Review
**Date**: 2026-02-09

---

## Decisions Required

Before finalizing this specification, the following decisions need resolution:

| # | Decision | Options | Current Assumption |
|---|----------|---------|-------------------|
| 1 | Where do aliases live? | A) domain-base defines possible aliases, domain-model selects<br>B) domain-model defines all aliases (base only has canonical names) | **B** - Base is pure, model handles mapping |
| 2 | When is aliasing applied? | A) During Bronze ingestion (facets)<br>B) During Silver build (graph nodes) | **B** - Bronze is raw, Silver transforms |
| 3 | Multi-source union syntax | A) `sources:` block with `union()` in table<br>B) Multiple `from:` in single node | **A** - Explicit sources block |
| 4 | Federation materialization | A) Always views<br>B) Optional materialization<br>C) Configurable per-model | **C** - Configurable |
| 5 | Intermediate tables | A) `_int_` prefix convention<br>B) `persist: false` flag<br>C) Both | **C** - Both for clarity |
| 6 | Schema vs Graph definition | A) Schema is authoritative (graph references)<br>B) Graph is authoritative (schema validates) | **A** - Schema is single source of truth |

---

## 1. Overview

### 1.1 Two Document Types

| Type | Purpose | Creates Storage? | Location |
|------|---------|------------------|----------|
| `domain-base` | Reusable template with canonical schema | No | `domains/_base/{category}/` |
| `domain-model` | Concrete implementation from source data | Yes | `domains/{category}/` |

### 1.2 Data Flow

```
Bronze (Raw)                    Silver (Canonical)
─────────────                   ──────────────────
source fields                   canonical fields
"1. open"          ─────────►   open
"vendor_name"      aliases      payee
"fund"                          expense_category
```

---

## 2. domain-base Template

A domain-base defines **what** the canonical schema is. It does NOT know about source-specific field names.

### 2.1 Structure

```yaml
---
type: domain-base
model: {template_name}
version: {semver}
description: "{what this template provides}"

# CANONICAL FIELDS - the semantic concepts
# All domain-models extending this will output these field names
canonical_fields:
  {field_name}:
    type: {data_type}
    nullable: {true|false}
    description: "{semantic meaning of this field}"

# TEMPLATE TABLES - schema patterns (not materialized)
# Use underscore prefix to indicate template
tables:
  _{table_name}:
    type: {dimension|fact}
    primary_key: [{columns}]
    schema:
      - [{column}, {type}, {nullable}, "{description}", {options}]

# FEDERATION - enable cross-model queries (optional)
federation:
  enabled: true
  union_key: {discriminator_column}
  primary_key: {shared_pk}
---
```

### 2.2 Single Source of Truth: Schema Definitions

**Key Principle**: Table schema is the authoritative source for all column definitions. Graph nodes reference tables but do NOT duplicate column mappings.

| Definition Location | What It Contains |
|---------------------|------------------|
| **Table Schema** | Column name, type, nullable, description, derived expression, FK |
| **Graph Node** | `from:` source, `filter:` conditions, table reference |
| **Sources Block** | Source-specific `aliases:` mapping raw → canonical names |

**Why This Matters**:
- No duplication between schema `derived:` and node `select:/derive:`
- Schema validates output; sources define input mapping
- Changes to derivation happen in ONE place

### 2.3 Complete Example: Ledger Base Template

```yaml
# domains/_base/finance/ledger.md
---
type: domain-base
model: ledger
version: 1.0
description: "Template for financial ledger entries - supports multi-source unions"

# CANONICAL FIELDS - semantic concepts only, no source-specific names
# These define WHAT fields mean, not HOW to populate them
canonical_fields:
  payee:
    type: string
    nullable: false
    description: "Entity receiving payment (person, vendor, contractor)"

  transaction_amount:
    type: decimal(18,2)
    nullable: false
    description: "Monetary value of the transaction"

  transaction_date:
    type: date
    nullable: false
    description: "Date the transaction occurred"

  organizational_unit:
    type: string
    nullable: true                    # <- NULLABLE: some sources won't have this
    default: null
    description: "Department, agency, or division responsible for transaction"

  expense_category:
    type: string
    nullable: true                    # <- NULLABLE: classification may not exist
    default: null
    description: "How expense is classified (fund, account, category)"

  entry_type:
    type: string
    nullable: false
    description: "Discriminator identifying source type (PAYROLL, VENDOR_PAYMENT, CONTRACT)"

  domain_source:
    type: string
    nullable: false
    description: "Which domain/organization this entry comes from"

# TEMPLATE TABLES - schema is authoritative source of truth
# Graph nodes will reference these columns, not redefine them
tables:
  _fact_journal_entries:
    type: fact
    primary_key: [entry_id]
    partition_by: [date_id]

    schema:
      # PK - derived from entry_type + source_id for uniqueness across unions
      - [entry_id, integer, false, "Primary key",
         {derived: "ABS(HASH(CONCAT(entry_type, '_', source_id)))"}]

      # FK to calendar dimension (required for all facts)
      - [date_id, integer, false, "FK to temporal.dim_calendar",
         {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(transaction_date, 'yyyyMMdd') AS INT)"}]

      # Union discriminator
      - [entry_type, string, false, "Source type discriminator"]
      - [domain_source, string, false, "Domain/organization identifier"]

      # Canonical fields from above (type/nullable must match)
      - [payee, string, false, "Who received payment"]
      - [transaction_amount, "decimal(18,2)", false, "Amount"]
      - [transaction_date, date, false, "Transaction date"]
      - [organizational_unit, string, true, "Department (null if not available)"]
      - [expense_category, string, true, "Classification (null if not available)"]

      # Source tracking (for debugging/lineage)
      - [source_id, string, false, "Original ID from source system"]

# CHART OF ACCOUNTS - expense categorization dimension
  _dim_chart_of_accounts:
    type: dimension
    primary_key: [account_id]

    schema:
      - [account_id, integer, false, "Primary key",
         {derived: "ABS(HASH(account_code))"}]
      - [account_code, string, false, "Account code (e.g., '5000', 'SALARY')"]
      - [account_name, string, false, "Human-readable name"]
      - [account_type, string, false, "Type: EXPENSE, REVENUE, ASSET, LIABILITY",
         {enum: [EXPENSE, REVENUE, ASSET, LIABILITY]}]
      - [parent_account_id, integer, true, "Parent account (for hierarchy)",
         {fk: _dim_chart_of_accounts.account_id}]
      - [level, integer, false, "Hierarchy level (1=top)", {default: 1}]
      - [is_active, boolean, false, "Currently in use", {default: true}]

federation:
  enabled: true
  union_key: domain_source
  primary_key: entry_id
---

## Ledger Base Template

This template defines a unified financial ledger structure that supports:
- Multiple source types (payroll, vendor payments, contracts)
- Multiple domains (city, company, federal)
- Nullable fields for sources that don't provide all data

### Canonical Fields

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `payee` | string | No | Entity receiving payment |
| `transaction_amount` | decimal(18,2) | No | Monetary value |
| `transaction_date` | date | No | When transaction occurred |
| `organizational_unit` | string | **Yes** | Department/agency - null if not available |
| `expense_category` | string | **Yes** | Classification - null if not available |
| `entry_type` | string | No | Source discriminator |
| `domain_source` | string | No | Which domain provided this data |

### Nullable Field Handling

Sources that don't have a field should map to `null`:

```yaml
# In domain-model sources block:
derive:
  organizational_unit: "null"  # Explicit null when source lacks departments
```

Or use COALESCE with a default:

```yaml
derive:
  organizational_unit: "COALESCE(department, 'UNASSIGNED')"
```

### Usage

```yaml
extends: _base.finance.ledger
```
```

---

## 3. domain-model Implementation

A domain-model defines **how** source data maps to the canonical schema.

### 3.1 Structure (Single Source) - Simplified

**Key Change**: Graph nodes no longer contain `select:` or `derive:` - those are defined in the table schema. Graph nodes only specify source and filter.

```yaml
---
type: domain-model
model: {model_name}
version: {semver}
description: "{what this model provides}"

extends: _base.{category}.{template}
depends_on: [{dependencies}]

storage:
  format: delta
  bronze:
    provider: {provider_name}
    tables:
      {local_name}: {provider}/{endpoint}
  silver:
    root: storage/silver/{model}/

# ALIASES - map source fields to canonical fields (applied during build)
aliases:
  "{source_field}": {canonical_field}

tables:
  {table_name}:
    extends: _base.{category}.{template}._{base_table}
    type: {dimension|fact}
    from: bronze.{provider}.{table}     # <- Source defined here
    filter: "{optional_filter}"          # <- Filter defined here
    primary_key: [{columns}]

graph:
  edges:
    {edge_name}:
      from: {source_table}
      to: {target_table}
      on: [{join_condition}]
      type: {many_to_one|one_to_one}
---
```

**What Changed**:
- `from:` moved from graph node to table definition
- `filter:` moved from graph node to table definition
- `select:/derive:` REMOVED - derivation comes from schema `{derived:}` option
- Graph section now only contains `edges:`

### 3.2 Structure (Multi-Source Union) - Simplified

For multi-source, the `sources:` block defines aliases and derived values per source. Table schema still defines the output columns.

```yaml
---
type: domain-model
model: {model_name}
version: {semver}
description: "{what this model provides}"

extends: _base.{category}.{template}
depends_on: [{dependencies}]

storage:
  format: delta
  bronze:
    provider: {provider_name}
    tables:
      {table1}: {provider}/{endpoint1}
      {table2}: {provider}/{endpoint2}
  silver:
    root: storage/silver/{model}/

# SOURCES - each endpoint with its own aliases and nullable handling
sources:
  {source_name}:
    from: bronze.{provider}.{table}
    entry_type: {DISCRIMINATOR_VALUE}

    # Map raw source fields to canonical names
    aliases:
      "{source_field}": {canonical_field}

    # Handle missing fields with explicit null or default
    derive:
      {missing_field}: "null"
      {computed_field}: "{SQL_expression}"

tables:
  {table_name}:
    extends: _base.{category}.{template}._{base_table}
    type: fact
    source: union({source1}, {source2})    # <- Union defined in table
    primary_key: [{columns}]
    # Schema inherited from base - no need to redefine

graph:
  edges:
    # Only edges needed - no nodes (sources block handles transformation)
    {edge_name}:
      from: {source_table}
      to: {target_table}
      on: [{join_condition}]
      type: many_to_one
---
```

**Multi-Source Build Process**:
1. For each source: read Bronze, apply aliases, apply derive, add entry_type
2. Project all sources to canonical schema (from base template)
3. Union all sources
4. Write to Silver table

### 3.3 Complete Example (Single Source) - Simplified

```yaml
# domains/securities/stocks.md
---
type: domain-model
model: stocks
version: 3.0
description: "Stock equities from Alpha Vantage"

extends: _base.finance.securities
depends_on: [temporal]

storage:
  format: delta
  bronze:
    provider: alpha_vantage
    tables:
      listing: alpha_vantage/listing_status
      prices: alpha_vantage/time_series_daily_adjusted
  silver:
    root: storage/silver/stocks/

# ALIASES - single place for source → canonical mapping
aliases:
  "symbol": ticker
  "name": security_name
  "1. open": open
  "2. high": high
  "3. low": low
  "4. close": close
  "6. volume": volume

# TABLES - define source, filter, and any schema overrides
tables:
  dim_stock:
    extends: _base.finance.securities._dim_security
    type: dimension
    from: bronze.alpha_vantage.listing_status
    filter: "assetType = 'Stock'"
    primary_key: [security_id]
    # Derived columns defined in base schema - not duplicated here

  fact_stock_prices:
    extends: _base.finance.securities._fact_prices
    type: fact
    from: bronze.alpha_vantage.time_series_daily_adjusted
    primary_key: [price_id]
    partition_by: [date_id]
    # Derived columns defined in base schema - not duplicated here

# GRAPH - only edges needed (no nodes with select/derive)
graph:
  edges:
    prices_to_stock:
      from: fact_stock_prices
      to: dim_stock
      on: [security_id=security_id]
      type: many_to_one

    prices_to_calendar:
      from: fact_stock_prices
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal
---
```

**Where did select/derive go?**

They're in the base schema. For example, `_base.finance.securities._dim_security` defines:

```yaml
schema:
  - [security_id, integer, false, "PK", {derived: "ABS(HASH(ticker))"}]
  - [ticker, string, false, "Trading symbol"]  # Alias 'symbol' → 'ticker' applied
  - [asset_type, string, false, "Asset classification", {derived: "'stocks'"}]
  # etc.
```

The build process:
1. Reads `from:` source table
2. Applies `aliases:` (symbol → ticker)
3. Applies `filter:`
4. Computes `derived:` expressions from schema
5. Writes to Silver

### 3.4 Complete Example (Multi-Source Union) - Chicago Ledger

Chicago has departments for all sources, so `organizational_unit` is always populated.

```yaml
# domains/municipal/chicago/finance.md
---
type: domain-model
model: chicago_ledger
version: 1.0
description: "Chicago municipal ledger from multiple endpoints"

extends: _base.finance.ledger
depends_on: [temporal]

storage:
  format: delta
  bronze:
    provider: chicago
    tables:
      payments: chicago/chicago_payments
      salaries: chicago/chicago_salaries
      contracts: chicago/chicago_contracts
  silver:
    root: storage/silver/chicago/finance/

sources:
  vendor_payments:
    from: bronze.chicago.chicago_payments
    entry_type: VENDOR_PAYMENT

    aliases:
      "vendor_name": payee
      "amount": transaction_amount
      "check_date": transaction_date
      "department_name": organizational_unit    # <- Has department
      "fund": expense_category

    derive:
      domain_source: "'chicago'"
      source_id: "voucher_number"               # For entry_id hash

  employee_salaries:
    from: bronze.chicago.chicago_salaries
    entry_type: PAYROLL

    aliases:
      "name": payee
      "effective_date": transaction_date
      "department": organizational_unit          # <- Has department
      "job_titles": expense_category

    derive:
      domain_source: "'chicago'"
      transaction_amount: "annual_salary / 12"   # Monthly from annual
      source_id: "CONCAT(name, '_', effective_date)"

  contract_payments:
    from: bronze.chicago.chicago_contracts
    entry_type: CONTRACT

    aliases:
      "vendor": payee
      "award_amount": transaction_amount
      "start_date": transaction_date
      "awarding_department": organizational_unit # <- Has department
      "contract_type": expense_category

    derive:
      domain_source: "'chicago'"
      source_id: "contract_number"

tables:
  fact_journal_entries:
    extends: _base.finance.ledger._fact_journal_entries
    type: fact
    source: union(vendor_payments, employee_salaries, contract_payments)
    primary_key: [entry_id]
    partition_by: [date_id]

  dim_chart_of_accounts:
    extends: _base.finance.ledger._dim_chart_of_accounts
    type: dimension
    from: bronze.chicago.chart_of_accounts
    primary_key: [account_id]

graph:
  edges:
    entry_to_calendar:
      from: fact_journal_entries
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal

    entry_to_chart:
      from: fact_journal_entries
      to: dim_chart_of_accounts
      on: [expense_category=account_code]
      type: many_to_one
      optional: true                              # May not match
---
```

### 3.5 Complete Example (Nullable Fields) - Company Ledger

Company data does NOT have department information. Show how to handle nullable fields.

```yaml
# domains/corporate/company_ledger.md
---
type: domain-model
model: company_ledger
version: 1.0
description: "Corporate financial ledger - NO department data available"

extends: _base.finance.ledger
depends_on: [temporal, company]

storage:
  format: delta
  bronze:
    provider: sec
    tables:
      expenses: sec/company_expenses
      payroll: sec/company_payroll
  silver:
    root: storage/silver/company/ledger/

sources:
  expenses:
    from: bronze.sec.company_expenses
    entry_type: EXPENSE

    aliases:
      "vendor": payee
      "expense_amount": transaction_amount
      "expense_date": transaction_date
      "account_code": expense_category

    derive:
      domain_source: "'company'"
      source_id: "expense_id"
      # NO DEPARTMENT DATA - explicitly null
      organizational_unit: "null"                 # <- Explicit null

  payroll:
    from: bronze.sec.company_payroll
    entry_type: PAYROLL

    aliases:
      "employee_name": payee
      "pay_date": transaction_date
      "gross_pay": transaction_amount

    derive:
      domain_source: "'company'"
      source_id: "CONCAT(employee_id, '_', pay_date)"
      # NO DEPARTMENT DATA - use company name as fallback
      organizational_unit: "company_name"         # <- Fallback value
      expense_category: "'SALARY'"                # <- Static value

tables:
  fact_journal_entries:
    extends: _base.finance.ledger._fact_journal_entries
    type: fact
    source: union(expenses, payroll)
    primary_key: [entry_id]
    partition_by: [date_id]

graph:
  edges:
    entry_to_calendar:
      from: fact_journal_entries
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal

    entry_to_company:
      from: fact_journal_entries
      to: company.dim_company
      on: [domain_source=company_id]
      type: many_to_one
      cross_model: company
      optional: true
---
```

### 3.6 Nullable Field Patterns

| Pattern | When to Use | Example |
|---------|-------------|---------|
| `"null"` | Field truly doesn't exist | `organizational_unit: "null"` |
| `"'{static}'"` | Use constant value | `expense_category: "'GENERAL'"` |
| `"source_column"` | Use another column as fallback | `organizational_unit: "company_name"` |
| `"COALESCE(...)"` | Try multiple sources | `"COALESCE(dept, division, 'UNKNOWN')"` |

**Federation Query Result**:

When querying `finance.v_all_ledger_entries` (federation view):

```sql
SELECT domain_source, entry_type, organizational_unit
FROM finance.v_all_ledger_entries
LIMIT 5;
```

| domain_source | entry_type | organizational_unit |
|--------------|------------|---------------------|
| chicago | VENDOR_PAYMENT | Streets & Sanitation |
| chicago | PAYROLL | Police Department |
| company | EXPENSE | null |
| company | PAYROLL | Acme Corp |

---

## 4. Build Process

### 4.1 Single Source Build (v5.0 Simplified)

```
1. Read domain-model config
2. Load base template (if extends: specified)
3. Merge schemas (child overrides parent)
4. For each table:
   a. Read from table.from (Bronze source)
   b. Apply model-level aliases (source field → canonical field)
   c. Apply table.filter if specified
   d. For each schema column with {derived:}:
      - Evaluate SQL expression
   e. Project to schema columns only (implicit drop of unlisted)
5. For each edge:
   a. Validate FK relationships exist
6. Write to Silver tables (Delta format)
```

**Key v5.0 Changes:**
- `from:` and `filter:` read from table definition (not graph node)
- Column derivation comes from schema `{derived:}` option
- No separate `select:` or `derive:` in graph nodes

### 4.2 Multi-Source Union Build (v5.0 Simplified)

```
1. Read domain-model config
2. Load base template
3. For each source in sources:
   a. Read from source.from (Bronze table)
   b. Apply source-specific aliases
   c. Apply source-specific derive (including nullable handling)
   d. Add entry_type discriminator column
   e. Project to canonical schema (from base template)
4. Union all source DataFrames
5. Apply table-level schema derivations (e.g., entry_id hash)
6. Write to Silver table (Delta format)
```

**Nullable Field Handling in Step 3c:**
- Fields not in source → derive with `"null"` or fallback value
- Example: `organizational_unit: "null"` when source lacks departments

---

## 5. Federation

### 5.1 How It Works

When multiple domain-models extend the same domain-base with `federation.enabled: true`:

1. All children output the same canonical schema
2. Query engine can UNION across children
3. `union_key` column identifies which child each row came from

### 5.2 Query Pattern

```sql
-- Federation view auto-generated from base template
SELECT * FROM finance.v_all_ledger_entries
-- Unions: corporate_ledger, chicago_ledger, federal_ledger
-- All have same canonical columns: payee, transaction_amount, etc.
```

---

## 6. Templates for Implementation

### Template A: domain-base

Copy and fill in:

```yaml
# domains/_base/{CATEGORY}/{TEMPLATE_NAME}.md
---
type: domain-base
model: {TEMPLATE_NAME}
version: 1.0
description: "{DESCRIPTION}"

# TODO: Define canonical fields - these are SEMANTIC CONCEPTS
# All domain-models extending this will output these exact field names
canonical_fields:
  {FIELD_1}:
    type: {TYPE}
    nullable: {true|false}
    description: "{WHAT THIS FIELD MEANS}"

  {FIELD_2}:
    type: {TYPE}
    nullable: {true|false}
    description: "{WHAT THIS FIELD MEANS}"

# TODO: Define template tables
tables:
  _{TABLE_NAME}:
    type: {dimension|fact}
    primary_key: [{PK_COLUMNS}]
    partition_by: [{PARTITION_COLUMNS}]  # for facts

    schema:
      # Use canonical field names in schema
      - [{COLUMN}, {TYPE}, {NULLABLE}, "{DESCRIPTION}", {OPTIONS}]

# TODO: Enable federation if cross-model queries needed
federation:
  enabled: {true|false}
  union_key: {DISCRIMINATOR_COLUMN}
  primary_key: {SHARED_PK}
---

## {TEMPLATE_NAME} Template

{DOCUMENTATION}

### Canonical Fields

| Field | Type | Description |
|-------|------|-------------|
| `{FIELD_1}` | {TYPE} | {MEANING} |

### Usage

```yaml
extends: _base.{CATEGORY}.{TEMPLATE_NAME}
```
```

### Template B: domain-model (Single Source) - v5.0 Simplified

```yaml
# domains/{CATEGORY}/{MODEL_NAME}.md
---
type: domain-model
model: {MODEL_NAME}
version: 1.0
description: "{DESCRIPTION}"

extends: _base.{CATEGORY}.{TEMPLATE_NAME}
depends_on: [{DEPENDENCIES}]

storage:
  format: delta
  bronze:
    provider: {PROVIDER}
    tables:
      {LOCAL_NAME}: {PROVIDER}/{ENDPOINT}
  silver:
    root: storage/silver/{MODEL_NAME}/

# TODO: Map source fields to canonical fields
aliases:
  "{SOURCE_FIELD_1}": {CANONICAL_FIELD_1}
  "{SOURCE_FIELD_2}": {CANONICAL_FIELD_2}

# TODO: Define tables with source and filter
tables:
  {TABLE_NAME}:
    extends: _base.{CATEGORY}.{TEMPLATE_NAME}._{BASE_TABLE}
    type: {dimension|fact}
    from: bronze.{PROVIDER}.{ENDPOINT}     # Source defined here
    filter: "{OPTIONAL_SQL_FILTER}"        # Filter defined here
    primary_key: [{PK}]
    # Schema inherited from base - derived expressions defined there

# TODO: Define edges only (no nodes needed)
graph:
  edges:
    {EDGE_NAME}:
      from: {SOURCE_TABLE}
      to: {TARGET_TABLE}
      on: [{JOIN_COLUMN}={JOIN_COLUMN}]
      type: many_to_one

    # Cross-model edge example
    {TABLE}_to_calendar:
      from: {TABLE_NAME}
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal
---
```

### Template C: domain-model (Multi-Source Union) - v5.0 Simplified

```yaml
# domains/{CATEGORY}/{MODEL_NAME}.md
---
type: domain-model
model: {MODEL_NAME}
version: 1.0
description: "{DESCRIPTION}"

extends: _base.{CATEGORY}.{TEMPLATE_NAME}
depends_on: [{DEPENDENCIES}]

storage:
  format: delta
  bronze:
    provider: {PROVIDER}
    tables:
      {TABLE_1}: {PROVIDER}/{ENDPOINT_1}
      {TABLE_2}: {PROVIDER}/{ENDPOINT_2}
  silver:
    root: storage/silver/{MODEL_NAME}/

# TODO: Define each source with its own aliases and nullable handling
sources:
  {SOURCE_1_NAME}:
    from: bronze.{PROVIDER}.{TABLE_1}
    entry_type: {DISCRIMINATOR_VALUE_1}

    aliases:
      "{SOURCE_FIELD}": {CANONICAL_FIELD}

    derive:
      domain_source: "'{DOMAIN}'"
      source_id: "{SOURCE_ID_EXPR}"
      # Handle nullable fields:
      {NULLABLE_FIELD}: "null"              # If source lacks this field
      {NULLABLE_FIELD}: "{FALLBACK_COL}"    # Or use another column

  {SOURCE_2_NAME}:
    from: bronze.{PROVIDER}.{TABLE_2}
    entry_type: {DISCRIMINATOR_VALUE_2}

    aliases:
      "{SOURCE_FIELD}": {CANONICAL_FIELD}

    derive:
      domain_source: "'{DOMAIN}'"
      source_id: "{SOURCE_ID_EXPR}"
      {NULLABLE_FIELD}: "{VALUE_OR_NULL}"

# TODO: Define union table
tables:
  {TABLE_NAME}:
    extends: _base.{CATEGORY}.{TEMPLATE_NAME}._{BASE_TABLE}
    type: fact
    source: union({SOURCE_1_NAME}, {SOURCE_2_NAME})
    primary_key: [{PK}]
    partition_by: [{PARTITION}]
    # Schema inherited from base

# TODO: Define edges only (sources block handles transformation)
graph:
  edges:
    {TABLE}_to_calendar:
      from: {TABLE_NAME}
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal
---
```

---

## 7. Migration TODO Checklist

### Phase 1: Create Base Templates

- [ ] Identify distinct semantic domains (securities, ledger, crime, etc.)
- [ ] For each domain, define canonical fields (semantic concepts)
- [ ] Create `domains/_base/{category}/{template}.md` files
- [ ] Define template tables with underscore prefix
- [ ] Configure federation if cross-model queries needed

### Phase 2: Convert Existing Models

For each existing model:

- [ ] Identify which base template it should extend
- [ ] Add `extends:` reference
- [ ] Create `aliases:` section mapping source → canonical
- [ ] Update table definitions to use `extends:`
- [ ] Update graph nodes to output canonical field names
- [ ] Test that output schema matches canonical schema

### Phase 3: Multi-Source Models

For models with multiple Bronze endpoints:

- [ ] Convert to `sources:` block pattern
- [ ] Each source gets its own `aliases:` and `derive:`
- [ ] Update table to use `source: union(...)`
- [ ] Add `entry_type` discriminator to each source
- [ ] Test union output

### Phase 4: Federation

- [ ] Identify models that should be queryable together
- [ ] Ensure they extend same base template
- [ ] Verify base has `federation.enabled: true`
- [ ] Test federated queries

---

## 8. Key Rules Summary

| Rule | Description |
|------|-------------|
| **Base is pure** | domain-base only defines canonical fields, never source-specific names |
| **Model maps** | domain-model aliases map source fields to canonical fields |
| **Underscore = template** | `_table_name` means template, not materialized |
| **Sources for unions** | Multiple endpoints → `sources:` block with `union()` |
| **entry_type discriminates** | Each source in union gets unique entry_type value |
| **Federation from base** | Cross-model queries enabled in domain-base, inherited by children |
| **date_id everywhere** | All facts FK to temporal.dim_calendar via integer date_id |
| **Integer PKs** | All PKs are integers via `ABS(HASH(...))` |

---

## 9. Complete Reference

Legend: ✅ = Implemented | 🔶 = Partial | 📋 = Proposed

### 9.1 Top-Level Keys

| Key | Required | Type | Status | Description |
|-----|----------|------|--------|-------------|
| `type` | Yes | string | ✅ | `domain-base` or `domain-model` |
| `model` | Yes | string | ✅ | Model identifier |
| `version` | Yes | string | ✅ | Semantic version (e.g., "3.0") |
| `description` | Yes | string | ✅ | Human-readable description |
| `tags` | No | list | ✅ | Classification tags `[securities, stocks]` |
| `extends` | No | string | ✅ | Parent template `_base.finance.securities` |
| `depends_on` | No | list | ✅ | Build dependencies `[temporal, company]` |
| `storage` | Conditional | object | ✅ | Required for domain-model |
| `canonical_fields` | Conditional | object | 📋 | Required for domain-base |
| `aliases` | No | object | 📋 | Source → canonical field mapping |
| `sources` | No | object | 📋 | Multi-source union configuration |
| `tables` | Yes | object | ✅ | Table definitions |
| `graph` | No | object | ✅ | Nodes, edges, paths |
| `measures` | No | object | ✅ | Measure definitions |
| `federation` | No | object | 📋 | Cross-model query config |
| `metadata` | No | object | ✅ | Ownership, SLA |
| `status` | No | string | ✅ | `active`, `deprecated`, `draft` |

---

### 9.2 Data Types

| Type | Status | Description | Example |
|------|--------|-------------|---------|
| `integer` | ✅ | 32-bit signed integer | `security_id` |
| `long` | ✅ | 64-bit signed integer | `volume` |
| `decimal(p,s)` | ✅ | Fixed-point decimal | `decimal(18,4)` for prices |
| `string` | ✅ | Variable-length string | `ticker` |
| `boolean` | ✅ | True/false | `is_active` |
| `date` | ✅ | Calendar date (no time) | `trade_date` |
| `timestamp` | ✅ | Date + time | `updated_at` |
| `array<T>` | 🔶 | Array of type T | `array<string>` |
| `map<K,V>` | 🔶 | Key-value map | `map<string,decimal>` |

---

### 9.3 Schema Column Definition

Format: `[column_name, type, nullable, description, {options}]`

**Options Object:**

| Option | Status | Type | Description | Example |
|--------|--------|------|-------------|---------|
| `derived` | ✅ | string | SQL expression to compute | `{derived: "ABS(HASH(ticker))"}` |
| `fk` | ✅ | string | Foreign key reference | `{fk: temporal.dim_calendar.date_id}` |
| `optional` | 📋 | boolean | Nullable FK (left join) | `{fk: company.dim_company.company_id, optional: true}` |
| `enum` | 🔶 | list | Allowed values | `{enum: [stocks, etf, option, future]}` |
| `default` | ✅ | any | Default value | `{default: "USD"}` |
| `format` | ✅ | string | Display format | `{format: "$#,##0.00"}` |
| `primary_key` | 📋 | boolean | Part of PK | `{primary_key: true}` |
| `unique` | 📋 | boolean | Unique constraint | `{unique: true}` |

**Derived Expression Examples:**

```yaml
# Integer surrogate key from hash
{derived: "ABS(HASH(ticker))"}

# Prefixed hash for namespacing
{derived: "ABS(HASH(CONCAT('STOCK_', ticker)))"}

# Date to integer date_id
{derived: "CAST(DATE_FORMAT(trade_date, 'yyyyMMdd') AS INT)"}

# Composite hash
{derived: "ABS(HASH(CONCAT(ticker, '_', trade_date)))"}

# Conditional logic
{derived: "CASE WHEN status = 'Active' THEN true ELSE false END"}

# String manipulation
{derived: "UPPER(TRIM(ticker))"}

# Date extraction
{derived: "YEAR(trade_date)"}
```

---

### 9.4 Storage Configuration

```yaml
storage:
  format: {format}           # Storage format
  auto_vacuum: {boolean}     # Remove old Delta versions

  bronze:                    # Source data
    provider: {provider}     # Provider name
    tables:                  # Table mappings
      {local}: {provider}/{endpoint}

  silver:                    # Output location
    root: {path}             # Output directory
```

| Field | Status | Required | Description |
|-------|--------|----------|-------------|
| `format` | ✅ | Yes | Always `delta` |
| `auto_vacuum` | ✅ | No | Default `true` |
| `bronze.provider` | ✅ | Yes | Provider identifier |
| `bronze.tables` | ✅ | Yes | Local name → path mapping |
| `silver.root` | ✅ | Yes | Output directory path |

---

### 9.5 Canonical Fields (domain-base)

```yaml
canonical_fields:
  {field_name}:
    type: {data_type}
    nullable: {boolean}
    description: "{semantic meaning}"
    enum: [{values}]         # Optional: allowed values
    default: {value}         # Optional: default value
```

| Field | Status | Required | Description |
|-------|--------|----------|-------------|
| `type` | 📋 | Yes | Data type |
| `nullable` | 📋 | Yes | Can be null |
| `description` | 📋 | Yes | Semantic meaning |
| `enum` | 📋 | No | Allowed values |
| `default` | 📋 | No | Default value |

---

### 9.6 Aliases (domain-model)

**Single Source Pattern:**

```yaml
aliases:
  "{source_field}": {canonical_field}
```

**Multi-Source Pattern:**

```yaml
sources:
  {source_name}:
    from: bronze.{provider}.{table}
    entry_type: {DISCRIMINATOR}

    aliases:
      "{source_field}": {canonical_field}

    derive:
      {field}: "{SQL_expression}"
```

| Field | Status | Required | Description |
|-------|--------|----------|-------------|
| `aliases` (top-level) | 📋 | No | Global source → canonical mapping |
| `sources` | 📋 | No | Multi-source configuration |
| `sources.*.from` | 📋 | Yes | Bronze table path |
| `sources.*.entry_type` | 📋 | Yes | Union discriminator value |
| `sources.*.aliases` | 📋 | No | Source-specific field mapping |
| `sources.*.derive` | 📋 | No | Source-specific computed fields |

---

### 9.7 Table Definition

```yaml
tables:
  {table_name}:
    type: {dimension|fact|intermediate}
    extends: {base_table_ref}
    description: "{description}"

    # SOURCE DEFINITION (v5.0 - moved from graph nodes)
    from: {bronze.provider.table}    # Source table
    filter: "{SQL_condition}"        # Optional filter
    source: union({sources})         # For multi-source unions

    # KEYS AND PARTITIONING
    primary_key: [{columns}]
    unique_key: [{columns}]
    partition_by: [{columns}]
    sort_by: [{columns}]

    # BUILD OPTIONS
    persist: {boolean}

    # SCHEMA (authoritative source for columns)
    schema:
      - [{column}, {type}, {nullable}, "{desc}", {options}]

    # TABLE-LEVEL ALIASES (optional override)
    aliases:
      "{source}": {canonical}
```

| Field | Status | Required | Description |
|-------|--------|----------|-------------|
| `type` | ✅ | Yes | `dimension`, `fact`, or `intermediate` |
| `extends` | 📋 | No | Inherit from base template table |
| `description` | ✅ | No | Table description |
| `from` | ✅ | Conditional | Source table (required unless `source:` is used) |
| `filter` | ✅ | No | SQL WHERE condition applied to source |
| `source` | 📋 | Conditional | `union(source1, source2)` for multi-source |
| `primary_key` | ✅ | Yes | PK column(s) |
| `unique_key` | ✅ | No | Natural key column(s) |
| `partition_by` | ✅ | No | Delta partition columns |
| `sort_by` | 🔶 | No | Z-order columns |
| `persist` | 📋 | No | For intermediate tables (default true) |
| `schema` | ✅ | Yes | Column definitions (includes derived expressions) |
| `aliases` | 📋 | No | Table-specific field mapping |

**Table Definition Examples:**

```yaml
# Single source table
tables:
  dim_stock:
    extends: _base.finance.securities._dim_security
    type: dimension
    from: bronze.alpha_vantage.listing_status
    filter: "assetType = 'Stock'"
    primary_key: [security_id]

# Multi-source union table
tables:
  fact_journal_entries:
    extends: _base.finance.ledger._fact_journal_entries
    type: fact
    source: union(vendor_payments, employee_salaries, contracts)
    primary_key: [entry_id]
    partition_by: [date_id]
```

---

### 9.8 Graph Nodes (DEPRECATED in v5.0)

**v5.0 Change**: Graph nodes with `select:` and `derive:` are deprecated. Use table-level `from:` and `filter:` instead, with derivations in schema.

**Old Pattern (Deprecated):**

```yaml
graph:
  nodes:
    {node_name}:
      from: {source}               # MOVED to table definition
      type: {dimension|fact}       # MOVED to table definition
      filter: "{SQL_condition}"    # MOVED to table definition
      select:                      # REMOVED - use schema derived
        {target}: {source_or_expr}
      derive:                      # REMOVED - use schema derived
        {column}: "{SQL}"
```

**New Pattern (v5.0):**

```yaml
tables:
  {table_name}:
    extends: {base_template}
    type: {dimension|fact}
    from: {source}                 # <- Source defined here
    filter: "{SQL_condition}"      # <- Filter defined here
    primary_key: [{columns}]
    # Schema (with derived) inherited from base or defined here

graph:
  edges:                           # <- Only edges remain
    {edge_name}:
      from: {table}
      to: {table}
      on: [{conditions}]
```

**Migration from old to new:**

| Old Location | New Location |
|--------------|--------------|
| `graph.nodes.{name}.from` | `tables.{name}.from` |
| `graph.nodes.{name}.type` | `tables.{name}.type` |
| `graph.nodes.{name}.filter` | `tables.{name}.filter` |
| `graph.nodes.{name}.select` | `tables.{name}.schema[].derived` |
| `graph.nodes.{name}.derive` | `tables.{name}.schema[].derived` |
| `graph.nodes.{name}.drop` | Omit column from schema |

**Why This Change:**
- Single source of truth for column definitions
- No duplication between select/derive and schema
- Schema is authoritative for types, nullability, and derivation
- Graph section focuses purely on relationships (edges)

---

### 9.9 Graph Edges

```yaml
graph:
  edges:
    {edge_name}:
      from: {source_table}
      to: {target_table}
      on: [{join_conditions}]
      type: {cardinality}
      cross_model: {model_name}
      optional: {boolean}
      description: "{description}"
```

| Field | Status | Required | Description |
|-------|--------|----------|-------------|
| `from` | ✅ | Yes | Source table in current model |
| `to` | ✅ | Yes | Target table (can be `model.table`) |
| `on` | ✅ | Yes | Join conditions `[col1=col2]` |
| `type` | ✅ | Yes | `many_to_one`, `one_to_one`, `one_to_many` |
| `cross_model` | ✅ | No | Target model name for cross-model joins |
| `optional` | 🔶 | No | Left join (nullable FK) |
| `description` | 🔶 | No | Edge description |

**Edge Examples:**

```yaml
edges:
  # Same-model join
  prices_to_stock:
    from: fact_stock_prices
    to: dim_stock
    on: [security_id=security_id]
    type: many_to_one

  # Cross-model join
  stock_to_company:
    from: dim_stock
    to: company.dim_company
    on: [company_id=company_id]
    type: many_to_one
    cross_model: company
    optional: true

  # Composite key join
  technicals_to_prices:
    from: fact_technicals
    to: fact_prices
    on: [security_id=security_id, date_id=date_id]
    type: one_to_one
```

---

### 9.10 Graph Paths

```yaml
graph:
  paths:
    {path_name}:
      description: "{description}"
      steps:
        - {from: table1, to: table2, via: column}
        - {from: table2, to: table3, via: column}
```

| Field | Status | Required | Description |
|-------|--------|----------|-------------|
| `description` | 🔶 | No | Path description |
| `steps` | 🔶 | Yes | Ordered join steps |
| `steps.*.from` | 🔶 | Yes | Source table |
| `steps.*.to` | 🔶 | Yes | Target table |
| `steps.*.via` | 🔶 | Yes | Join column |

**Path Example:**

```yaml
paths:
  prices_to_sector:
    description: "Navigate from prices to company sector"
    steps:
      - {from: fact_stock_prices, to: dim_stock, via: security_id}
      - {from: dim_stock, to: company.dim_company, via: company_id}
```

---

### 9.11 Measures

```yaml
measures:
  simple:
    - [{name}, {aggregation}, {column}, "{description}", {options}]

  computed:
    - [{name}, expression, "{SQL}", "{description}", {options}]

  python:
    {measure_name}:
      function: "{module.function}"
      params:
        {param}: {value}
```

**Simple Measure Aggregations:**

| Aggregation | Status | Description | Example |
|-------------|--------|-------------|---------|
| `count` | ✅ | Count rows | `[trade_count, count, price_id, "Number of trades"]` |
| `count_distinct` | ✅ | Count unique | `[ticker_count, count_distinct, ticker, "Unique tickers"]` |
| `sum` | ✅ | Sum values | `[total_volume, sum, volume, "Total volume"]` |
| `avg` | ✅ | Average | `[avg_close, avg, close, "Average close"]` |
| `min` | ✅ | Minimum | `[min_low, min, low, "Minimum low"]` |
| `max` | ✅ | Maximum | `[max_high, max, high, "Maximum high"]` |
| `first` | 🔶 | First value | `[first_open, first, open, "Opening price"]` |
| `last` | 🔶 | Last value | `[last_close, last, close, "Closing price"]` |

**Measure Options:**

| Option | Status | Description | Example |
|--------|--------|-------------|---------|
| `format` | ✅ | Display format | `{format: "$#,##0.00"}` |
| `filter` | 🔶 | Conditional filter | `{filter: "entry_type = 'PAYROLL'"}` |
| `window` | 📋 | Window function | `{window: {partition: ticker, order: date_id}}` |

**Computed Measure Examples:**

```yaml
computed:
  # Simple expression
  - [price_range, expression, "AVG(high - low)", "Average daily range", {format: "$#,##0.00"}]

  # Percentage
  - [return_pct, expression, "AVG((close - open) / open) * 100", "Avg return %", {format: "0.00%"}]

  # Conditional aggregation
  - [payroll_total, expression, "SUM(CASE WHEN entry_type = 'PAYROLL' THEN amount ELSE 0 END)", "Payroll total"]

  # Ratio
  - [payroll_ratio, expression, "SUM(CASE WHEN entry_type = 'PAYROLL' THEN amount ELSE 0 END) / SUM(amount)", "Payroll %"]
```

**Python Measure Definition:**

```yaml
python:
  sharpe_ratio:
    function: "stocks.measures.calculate_sharpe_ratio"
    params:
      risk_free_rate: 0.045
      window_days: 252

  beta:
    function: "stocks.measures.calculate_beta"
    params:
      benchmark: "SPY"
      window_days: 252
```

| Field | Status | Required | Description |
|-------|--------|----------|-------------|
| `function` | ✅ | Yes | Python function path `module.function` |
| `params` | ✅ | No | Default parameters passed to function |

**Python Measure Implementation:**

```python
# src/de_funk/models/implemented/stocks/measures.py

class StocksMeasures:
    def __init__(self, model):
        self.model = model

    def calculate_sharpe_ratio(
        self,
        ticker: str = None,
        risk_free_rate: float = 0.045,
        window_days: int = 252,
        **kwargs  # Accept additional runtime params
    ) -> float:
        """
        Calculate annualized Sharpe ratio.

        Called via: model.calculate_measure("sharpe_ratio", ticker="AAPL")
        YAML params provide defaults, kwargs override at runtime.
        """
        import numpy as np

        df = self.model.get_prices(ticker=ticker)
        df['return'] = df['close'].pct_change()

        mean_return = df['return'].mean() * 252
        std_return = df['return'].std() * np.sqrt(252)

        return (mean_return - risk_free_rate) / std_return
```

**Calling Python Measures:**

```python
# In application code
model = registry.get_model("stocks")

# Uses YAML default params
sharpe = model.calculate_measure("sharpe_ratio", ticker="AAPL")

# Override YAML params at runtime
sharpe_60d = model.calculate_measure(
    "sharpe_ratio",
    ticker="AAPL",
    window_days=60  # Override default 252
)
```

### 9.11.1 NPV Calculation Proposal (📋 Proposed)

**Net Present Value (NPV)** is a financial measure that calculates the present value of future cash flows discounted at a given rate. This is useful for:
- Valuing contracts with future payments
- Comparing investment alternatives
- Budgeting future expenses

**Where it belongs**: Python measure on `ledger` model (or any model with future-dated transactions).

**YAML Definition:**

```yaml
# In domain-model measures section
measures:
  python:
    net_present_value:
      function: "ledger.measures.calculate_npv"
      params:
        discount_rate: 0.05          # 5% annual discount rate
        as_of_date: null             # null = today, or specify date
        include_past: false          # Include transactions before as_of_date?

    npv_by_category:
      function: "ledger.measures.calculate_npv_by_category"
      params:
        discount_rate: 0.05
        group_by: expense_category
```

**Python Implementation:**

```python
# src/de_funk/models/implemented/ledger/measures.py

from datetime import date, timedelta
from typing import Optional
import numpy as np


class LedgerMeasures:
    """Financial measures for ledger models."""

    def __init__(self, model):
        self.model = model

    def calculate_npv(
        self,
        discount_rate: float = 0.05,
        as_of_date: Optional[date] = None,
        include_past: bool = False,
        entry_type: Optional[str] = None,
        **kwargs
    ) -> float:
        """
        Calculate Net Present Value of ledger entries.

        NPV = Σ (cash_flow_t / (1 + r)^t)

        where:
          - cash_flow_t = transaction amount at time t
          - r = discount rate (annual)
          - t = years from as_of_date

        Args:
            discount_rate: Annual discount rate (default 5%)
            as_of_date: Reference date for discounting (default: today)
            include_past: Include transactions before as_of_date
            entry_type: Filter to specific entry type (PAYROLL, CONTRACT, etc.)

        Returns:
            Net Present Value as float

        Example:
            >>> model.calculate_measure("net_present_value",
            ...     discount_rate=0.08,
            ...     entry_type="CONTRACT"
            ... )
            1234567.89
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Get journal entries
        filters = []
        if not include_past:
            filters.append(f"transaction_date >= '{as_of_date}'")
        if entry_type:
            filters.append(f"entry_type = '{entry_type}'")

        df = self.model.query_table(
            "fact_journal_entries",
            columns=["transaction_date", "transaction_amount"],
            filters=filters
        )

        if df.empty:
            return 0.0

        # Calculate years from as_of_date
        df["days_from_ref"] = (df["transaction_date"] - as_of_date).dt.days
        df["years_from_ref"] = df["days_from_ref"] / 365.25

        # Calculate discount factor
        df["discount_factor"] = 1 / (1 + discount_rate) ** df["years_from_ref"]

        # Calculate present value
        df["present_value"] = df["transaction_amount"] * df["discount_factor"]

        return float(df["present_value"].sum())

    def calculate_npv_by_category(
        self,
        discount_rate: float = 0.05,
        group_by: str = "expense_category",
        as_of_date: Optional[date] = None,
        **kwargs
    ) -> dict:
        """
        Calculate NPV grouped by a category column.

        Args:
            discount_rate: Annual discount rate
            group_by: Column to group by (expense_category, entry_type, etc.)
            as_of_date: Reference date for discounting

        Returns:
            Dict of {category: npv_value}

        Example:
            >>> model.calculate_measure("npv_by_category",
            ...     group_by="entry_type"
            ... )
            {'PAYROLL': 5000000.00, 'CONTRACT': 2500000.00, 'VENDOR_PAYMENT': 750000.00}
        """
        if as_of_date is None:
            as_of_date = date.today()

        df = self.model.query_table(
            "fact_journal_entries",
            columns=[group_by, "transaction_date", "transaction_amount"],
            filters=[f"transaction_date >= '{as_of_date}'"]
        )

        if df.empty:
            return {}

        df["years_from_ref"] = (df["transaction_date"] - as_of_date).dt.days / 365.25
        df["present_value"] = df["transaction_amount"] / (1 + discount_rate) ** df["years_from_ref"]

        return df.groupby(group_by)["present_value"].sum().to_dict()
```

**Usage Examples:**

```python
# Get model
model = registry.get_model("chicago_ledger")

# Total NPV of all future transactions
total_npv = model.calculate_measure("net_present_value")

# NPV of contracts only, with 8% discount rate
contract_npv = model.calculate_measure(
    "net_present_value",
    discount_rate=0.08,
    entry_type="CONTRACT"
)

# NPV breakdown by expense category
npv_by_cat = model.calculate_measure("npv_by_category")
# Returns: {'SALARY': 50M, 'INFRASTRUCTURE': 25M, 'SERVICES': 10M}

# NPV breakdown by entry type
npv_by_type = model.calculate_measure(
    "npv_by_category",
    group_by="entry_type"
)
# Returns: {'PAYROLL': 50M, 'CONTRACT': 30M, 'VENDOR_PAYMENT': 5M}
```

**Integration with Federation:**

When federation is enabled, NPV can be calculated across all child models:

```python
# Get federation model
federation = registry.get_federation("ledger")

# NPV across all domains (chicago + company + federal)
total_npv = federation.calculate_measure(
    "net_present_value",
    discount_rate=0.05
)

# NPV by domain_source
npv_by_domain = federation.calculate_measure(
    "npv_by_category",
    group_by="domain_source"
)
# Returns: {'chicago': 85M, 'company': 120M, 'federal': 500M}
```

---

### 9.12 Federation Configuration

```yaml
federation:
  enabled: {boolean}
  union_key: {column}
  primary_key: {column}
  children: [{models}]
  materialize: {boolean}
  refresh: {schedule}
```

| Field | Status | Required | Description |
|-------|--------|----------|-------------|
| `enabled` | 📋 | Yes | Enable federation |
| `union_key` | 📋 | Yes | Column identifying source model |
| `primary_key` | 📋 | Yes | Shared PK across children |
| `children` | 📋 | No | Auto-populated list of child models |
| `materialize` | 📋 | No | Create physical union table |
| `refresh` | 📋 | No | Refresh schedule: `daily`, `hourly` |

---

### 9.13 Build Configuration

```yaml
build:
  partitions: [{columns}]
  sort_by: [{columns}]
  optimize: {boolean}

  phases:
    1:
      tables: [{tables}]
      persist: {boolean}
    2:
      tables: [{tables}]
      persist: {boolean}
```

| Field | Status | Required | Description |
|-------|--------|----------|-------------|
| `partitions` | ✅ | No | Delta partition columns |
| `sort_by` | 🔶 | No | Z-order columns |
| `optimize` | ✅ | No | Run OPTIMIZE after build |
| `phases` | 📋 | No | Multi-phase build order |
| `phases.*.tables` | 📋 | Yes | Tables to build in phase |
| `phases.*.persist` | 📋 | No | Keep tables after build |

---

### 9.14 Metadata

```yaml
metadata:
  domain: {domain_name}
  owner: {team_or_person}
  sla_hours: {number}
  tags: [{tags}]
  documentation: {url}
```

| Field | Status | Required | Description |
|-------|--------|----------|-------------|
| `domain` | ✅ | No | Domain classification |
| `owner` | ✅ | No | Owning team/person |
| `sla_hours` | ✅ | No | Build SLA in hours |
| `tags` | ✅ | No | Additional tags |
| `documentation` | 🔶 | No | Link to docs |

---

### 9.15 Format Strings

| Format | Output | Use For |
|--------|--------|---------|
| `$#,##0.00` | $1,234.56 | Currency |
| `$#,##0` | $1,235 | Currency (no decimals) |
| `#,##0` | 1,235 | Integers with thousands |
| `#,##0.00` | 1,234.56 | Decimals |
| `0.00%` | 12.34% | Percentages |
| `0.0000` | 0.1234 | High precision |
| `yyyy-MM-dd` | 2025-01-27 | Dates |

---

## 10. Implementation Status Summary

| Category | Implemented | Partial | Proposed |
|----------|-------------|---------|----------|
| Core Structure | type, model, version, storage, tables | - | canonical_fields, aliases, sources |
| Schema | derived, fk, default, format | enum | optional, primary_key |
| Tables | type, from, filter, primary_key, extends | - | source (union) |
| Graph | edges | - | paths (nodes deprecated in v5.0) |
| Measures | simple, computed, python | window measures | filtered measures, NPV |
| Federation | - | - | All federation features |
| Build | partitions, optimize | sort_by | phases, persist |

### v5.0 Key Changes

| Change | Before | After |
|--------|--------|-------|
| Source definition | `graph.nodes.{name}.from` | `tables.{name}.from` |
| Filter definition | `graph.nodes.{name}.filter` | `tables.{name}.filter` |
| Column derivation | `graph.nodes.{name}.select/derive` | `tables.{name}.schema[].{derived:}` |
| Graph purpose | Nodes + Edges | Edges only |
| Nullable handling | Implicit | Explicit in sources.derive |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 5.0 | 2026-02-09 | Unified specification with consistent patterns |
| 5.1 | 2026-02-09 | Removed graph node duplication (select/derive → schema derived) |
| | | Added complete ledger/chart of accounts templates |
| | | Added nullable field handling patterns (city vs company example) |
| | | Added NPV Python measure proposal with implementation |
| | | Simplified templates B and C for v5.0 structure |
