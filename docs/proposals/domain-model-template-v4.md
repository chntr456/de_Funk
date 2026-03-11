# Domain Model Template Specification v4.0

**Status**: Draft Proposal
**Created**: 2026-01-26
**Updated**: 2026-01-27
**Author**: Data Engineering

---

## Executive Summary

This specification defines a unified template for domain model configuration files. The goals are:

1. **Single source of truth** - All column info in `schema:` (no separate select/derive/from)
2. **Separate concerns** - Inputs (`data_sources:`) vs outputs (`storage:`)
3. **Foundation models** - Shared reference dimensions (temporal, accounts) as Tier 0
4. **Multi-domain reuse** - Chart of Accounts shared across corporate, municipal, funds
5. **Clarify inheritance** - `extends:` as list, build trigger via `{from:}` in schema
6. **Support all model types** - Foundation, base templates, ingested, generated, extensions

### Key Changes from v3.0

| v3.0 | v4.0 |
|------|------|
| `graph.nodes.*` separate from `tables.*` | Unified `tables:` with `{from:}` in schema |
| `storage.bronze.*` | `data_sources:` (top-level) |
| `storage.silver.root` | `storage.root` |
| `extends: string` | `extends: [list]` |
| Financial statements in company | Normalized to Chart of Accounts |
| No foundation layer concept | `accounts` + `temporal` as Tier 0 |

---

## Model Hierarchy

### Foundation, Domain, and View Tiers

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TIER 0: FOUNDATION (Seeded reference dimensions - no external sources) │
│                                                                         │
│   ┌─────────────┐          ┌─────────────┐                              │
│   │  temporal   │          │  accounts   │                              │
│   │ dim_calendar│          │ dim_account │                              │
│   │  (dates)    │          │   (CoA)     │                              │
│   └─────────────┘          └─────────────┘                              │
└─────────────────────────────────────────────────────────────────────────┘
                    │                    │
        ┌───────────┴───────────┬────────┴────────┐
        ▼                       ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  TIER 1: ENTITIES (Legal/organizational entities - from external APIs)  │
│                                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│   │   company   │    │ municipality│    │    fund     │                 │
│   │ dim_company │    │ dim_entity  │    │  dim_fund   │                 │
│   │ (corporate) │    │  (Chicago)  │    │  (invest)   │                 │
│   └─────────────┘    └─────────────┘    └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────────┘
        │                       │                 │
        │                       │                 │
        ▼                       ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  TIER 2: FACTS (Transactional data - from external APIs)                │
│                                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│   │  corporate/ │    │  municipal/ │    │   funds/    │                 │
│   │ financials  │    │ city_finance│    │ accounting  │                 │
│   │fact_balance │    │fact_balance │    │fact_balance │                 │
│   └─────────────┘    └─────────────┘    └─────────────┘                 │
│                                                                         │
│   ┌─────────────┐                                                       │
│   │  securities │  (Different pattern - prices, not accounting)         │
│   │ fact_prices │                                                       │
│   └─────────────┘                                                       │
└─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  TIER 3: VIEWS (Aggregated/derived - no external sources)               │
│                                                                         │
│   ┌─────────────────────┐    ┌─────────────────────┐                    │
│   │ financial_statements│    │  municipal_reports  │                    │
│   │ view_balance_sheet  │    │    view_budget      │                    │
│   │view_income_statement│    │     view_cafr       │                    │
│   └─────────────────────┘    └─────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Foundation Models?

Foundation models are **seeded reference dimensions** that:

| Characteristic | temporal | accounts |
|----------------|----------|----------|
| **Source** | Seeded (generated) | Seeded (predefined) |
| **Dependencies** | None | None |
| **Consumers** | ALL models | ALL financial models |
| **Change frequency** | Never (dates are dates) | Rarely (CoA is standard) |
| **Tier** | 0 | 0 |

**Key insight**: Chart of Accounts is like a calendar - it's a reference taxonomy that corporate, municipal, and fund accounting ALL use. Different entities populate balances differently, but they reference the SAME account structure.

---

## Additive Ledger Architecture (Plug-In Model)

The Chart of Accounts is designed as an **additive ledger backbone** - any financial data source can "post" to it, similar to how sub-ledgers post to a General Ledger in ERP systems.

### The General Ledger Analogy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TRADITIONAL ERP ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│     AR      │  │     AP      │  │   Payroll   │  │  Fixed      │
│ Sub-Ledger  │  │ Sub-Ledger  │  │ Sub-Ledger  │  │  Assets     │
│             │  │             │  │             │  │             │
│ Customer    │  │ Vendor      │  │ Employee    │  │ Asset       │
│ invoices    │  │ bills       │  │ wages       │  │ depreciation│
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │                │
       │    POST        │    POST        │    POST        │    POST
       ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         GENERAL LEDGER                                   │
│                                                                         │
│  Account 1100 (Accounts Receivable)    ← AR posts here                  │
│  Account 2000 (Accounts Payable)       ← AP posts here                  │
│  Account 6100 (Salaries Expense)       ← Payroll posts here             │
│  Account 1500 (Fixed Assets)           ← FA posts here                  │
│  Account 6800 (Depreciation Expense)   ← FA posts here                  │
│                                                                         │
│  ONE Chart of Accounts, MANY sources feeding it                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### de_Funk Equivalent: Plug-In Data Sources

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    de_Funk ADDITIVE ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Alpha       │  │ Chicago     │  │ Cook County │  │ Future      │
│ Vantage     │  │ Budget      │  │ Tax Revenue │  │ Source      │
│             │  │             │  │             │  │             │
│ SEC filings │  │ Municipal   │  │ Property    │  │ ???         │
│ fundamentals│  │ budget data │  │ tax data    │  │             │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │                │
       │ Transform      │ Transform      │ Transform      │ Transform
       │ + Map          │ + Map          │ + Map          │ + Map
       ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    UNIFIED FACT TABLE(S)                                 │
│                    fact_account_balance                                  │
│                                                                         │
│  ┌─────────┬───────────┬──────────┬────────┬─────────┬───────────────┐ │
│  │entity_id│account_id │period_id │ source │ balance │ source_ref    │ │
│  ├─────────┼───────────┼──────────┼────────┼─────────┼───────────────┤ │
│  │ AAPL    │ 4000      │ 2024Q4   │ av     │ 119.6B  │ av.income.123 │ │
│  │ AAPL    │ 6100      │ 2024Q4   │ av     │ 45.2B   │ av.income.123 │ │
│  │ CHI     │ 4100      │ FY2024   │ chi    │ 5.2B    │ chi.budget.x  │ │
│  │ CHI     │ 6200      │ FY2024   │ chi    │ 1.8B    │ chi.budget.x  │ │
│  │ COOK    │ 4200      │ FY2024   │ cook   │ 2.1B    │ cook.tax.y    │ │
│  └─────────┴───────────┴──────────┴────────┴─────────┴───────────────┘ │
│                           ▲                                             │
│                           │                                             │
│                    ALL reference same dim_account                       │
└─────────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FOUNDATION: dim_account                               │
│                    (Chart of Accounts)                                   │
│                                                                         │
│  4000 Revenue (Total)                                                   │
│  ├── 4100 Operating Revenue                                             │
│  │   ├── 4110 Product Sales                                             │
│  │   ├── 4120 Service Revenue                                           │
│  │   └── 4130 Tax Revenue        ← Cook County posts here               │
│  ├── 4200 Non-Operating Revenue                                         │
│  │   ├── 4210 Interest Income                                           │
│  │   └── 4220 Investment Gains                                          │
│  6000 Operating Expenses                                                │
│  ├── 6100 Salaries & Wages       ← All entities post here               │
│  ├── 6200 Contracted Services    ← All entities post here               │
│  ...                                                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Adding a New Source: Cook County Tax Revenue

Here's how you'd add Cook County property tax data:

#### Step 1: Create Entity Dimension (if needed)

```yaml
# domains/municipal/cook_county.md

type: domain-model
model: cook_county
version: 4.0
description: "Cook County government entities and tax data"

depends_on:
  - temporal
  - accounts    # Foundation CoA

data_sources:
  cook_county:
    - property_tax_levy
    - property_tax_collections
    - tax_distribution

storage:
  format: delta
  root: municipal/cook_county

tables:
  dim_taxing_district:
    type: dimension
    description: "Cook County taxing districts"
    primary_key: [district_id]

    schema:
      - [district_id, integer, false, "PK", {derive: "ABS(HASH(agency_number))"}]
      - [agency_number, _, false, "Agency ID", {from: cook_county.property_tax_levy.agency_number}]
      - [agency_name, _, false, "District name", {from: cook_county.property_tax_levy.agency_name}]
      - [district_type, _, true, "Type", {from: cook_county.property_tax_levy.agency_type}]
      - [county, string, false, "County", {default: "Cook"}]
      - [state, string, false, "State", {default: "IL"}]

  # THIS IS THE KEY: Posts to the SAME account structure
  fact_account_balance:
    type: fact
    description: "Tax revenue by district and account"
    primary_key: [balance_id]
    partition_by: [tax_year]

    schema:
      # Keys linking to foundation
      - [balance_id, integer, false, "PK", {derive: "..."}]
      - [district_id, integer, false, "FK to district", {fk: dim_taxing_district.district_id}]
      - [account_id, integer, false, "FK to CoA", {fk: accounts.dim_account.account_id}]
      - [period_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]

      # Source tracking
      - [source_system, string, false, "Source", {default: "cook_county"}]
      - [source_reference, string, true, "Source record ID"]

      # The actual balance
      - [balance, double, true, "Amount"]
      - [tax_year, integer, false, "Tax year"]

      # Tax-specific attributes (domain extensions)
      - [levy_amount, _, true, "Original levy", {from: cook_county.property_tax_levy.levy_amount}]
      - [collected_amount, _, true, "Collected", {from: cook_county.property_tax_collections.collected}]
      - [collection_rate, double, true, "Collection %", {derive: "collected_amount / NULLIF(levy_amount, 0)"}]

edges:
  - [balance_to_account, fact_account_balance, accounts.dim_account, account_id=account_id, many_to_one]
  - [balance_to_district, fact_account_balance, dim_taxing_district, district_id=district_id, many_to_one]
  - [balance_to_calendar, fact_account_balance, temporal.dim_calendar, period_date_id=date_id, many_to_one]
```

#### Step 2: Map Source Fields to Standard Accounts

```yaml
# Cook County → Standard Account Mappings

mappings:
  cook_county.property_tax_levy.levy_amount:
    canonical_term: "Property Tax Revenue"
    account_code: 4130  # Tax Revenue
    mapping_type: exact

  cook_county.property_tax_collections.collected:
    canonical_term: "Property Tax Revenue - Collected"
    account_code: 4130  # Same account, different measure
    mapping_type: exact

  cook_county.tax_distribution.school_portion:
    canonical_term: "Tax Distribution - Schools"
    account_code: 7100  # Intergovernmental transfers
    mapping_type: exact
```

#### Step 3: Query Across All Sources

Once Cook County is added, queries automatically include it:

```sql
-- Revenue by account across ALL sources
SELECT
    a.account_code,
    a.account_name,
    f.source_system,
    SUM(f.balance) as total_balance
FROM fact_account_balance f
JOIN accounts.dim_account a ON f.account_id = a.account_id
WHERE a.account_type = 'revenue'
  AND f.period_date_id BETWEEN 20240101 AND 20241231
GROUP BY a.account_code, a.account_name, f.source_system
ORDER BY a.account_code;

-- Result:
-- account_code | account_name      | source_system | total_balance
-- 4000         | Total Revenue     | alpha_vantage | 500,000,000,000
-- 4100         | Operating Revenue | chicago       | 12,000,000,000
-- 4130         | Tax Revenue       | cook_county   | 2,100,000,000   ← NEW!
-- ...
```

### Swap-Out Capability

The architecture supports swapping data sources:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SWAP SCENARIOS                                   │
└─────────────────────────────────────────────────────────────────────────┘

SCENARIO 1: Replace Alpha Vantage with SEC EDGAR Direct
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before:
  alpha_vantage.income_statement → fact_account_balance (source='av')

After:
  sec_edgar.10k_financials → fact_account_balance (source='sec')

The fact table structure is IDENTICAL. Only:
  - data_sources: changes
  - {from: ...} references change
  - source_system column value changes

Existing queries continue to work!


SCENARIO 2: Add Multiple Tax Sources
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cook_county.property_tax     → fact_account_balance (source='cook_county')
dupage_county.property_tax   → fact_account_balance (source='dupage')
lake_county.property_tax     → fact_account_balance (source='lake')
il_dept_revenue.sales_tax    → fact_account_balance (source='il_dor')

All post to same account structure (4130 Tax Revenue, etc.)
All queryable together via dim_account join


SCENARIO 3: Deprecate a Source
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Soft delete: Mark old source as inactive
UPDATE fact_account_balance
SET is_active = false
WHERE source_system = 'old_provider'
  AND period_date_id < 20240101;

-- Or partition by source for easy drop
ALTER TABLE fact_account_balance
DROP PARTITION (source_system = 'old_provider');
```

### Unified View Pattern

For cross-source analysis, create a unified view:

```yaml
# domains/reporting/unified_ledger.md

type: domain-model
model: unified_ledger
version: 4.0
description: "Unified view across all financial data sources"

depends_on:
  - temporal
  - accounts
  - corporate/financials      # Alpha Vantage corporate
  - municipal/city_finance    # Chicago budget
  - municipal/cook_county     # Cook County tax

# NO data_sources - this is a VIEW over silver tables

storage:
  format: delta
  root: reporting/unified

tables:
  view_unified_ledger:
    type: fact
    description: "Union of all fact_account_balance tables"
    generated: true

    schema:
      # Common columns across all sources
      - [ledger_entry_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(source, '_', source_entry_id)))"}]
      - [entity_id, integer, false, "Polymorphic entity FK"]
      - [entity_type, string, false, "Entity type", {enum: [company, municipality, taxing_district]}]
      - [entity_name, string, false, "Entity name (denormalized)"]
      - [account_id, integer, false, "FK to CoA", {fk: accounts.dim_account.account_id}]
      - [period_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [balance, double, true, "Balance amount"]
      - [source_system, string, false, "Source system"]
      - [source_entry_id, string, false, "Original source PK"]

    # Built from UNION of domain fact tables
    build_sql: |
      SELECT
        ABS(HASH(CONCAT('corporate_', balance_id))) as ledger_entry_id,
        company_id as entity_id,
        'company' as entity_type,
        c.company_name as entity_name,
        account_id,
        period_end_date_id as period_date_id,
        balance,
        'alpha_vantage' as source_system,
        CAST(balance_id AS STRING) as source_entry_id
      FROM corporate.financials.fact_account_balance f
      JOIN corporate.company.dim_company c ON f.company_id = c.company_id

      UNION ALL

      SELECT
        ABS(HASH(CONCAT('chicago_', balance_id))) as ledger_entry_id,
        department_id as entity_id,
        'municipality' as entity_type,
        d.department_name as entity_name,
        account_id,
        period_date_id,
        COALESCE(expenditure, appropriation) as balance,
        'chicago' as source_system,
        CAST(balance_id AS STRING) as source_entry_id
      FROM municipal.city_finance.fact_account_balance f
      JOIN municipal.city_finance.dim_department d ON f.department_id = d.department_id

      UNION ALL

      SELECT
        ABS(HASH(CONCAT('cook_', balance_id))) as ledger_entry_id,
        district_id as entity_id,
        'taxing_district' as entity_type,
        t.agency_name as entity_name,
        account_id,
        period_date_id,
        balance,
        'cook_county' as source_system,
        CAST(balance_id AS STRING) as source_entry_id
      FROM municipal.cook_county.fact_account_balance f
      JOIN municipal.cook_county.dim_taxing_district t ON f.district_id = t.district_id

    measures:
      - [total_balance, sum, balance, "Total across all sources"]
      - [source_count, count_distinct, source_system, "Number of sources"]
      - [entity_count, count_distinct, entity_id, "Number of entities"]
```

### Adding a New Source: Checklist

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    NEW SOURCE ONBOARDING CHECKLIST                       │
└─────────────────────────────────────────────────────────────────────────┘

□ 1. BRONZE INGESTION
    □ Create provider in datapipelines/providers/{provider}/
    □ Define endpoints in configs/pipelines/{provider}_endpoints.json
    □ Test ingestion: python -m scripts.ingest.run_bronze_ingestion --provider {provider}

□ 2. ACCOUNT MAPPING
    □ Discover source fields: python -m scripts.mapping.discover_fields --provider {provider}
    □ Generate mappings: python -m scripts.mapping.generate_mappings --provider {provider}
    □ Review and approve mappings (human step)
    □ Import verified: python -m scripts.mapping.import_mappings --file mappings.csv

□ 3. DOMAIN MODEL
    □ Create entity dimension (if new entity type)
    □ Create fact_account_balance table with:
        - FK to accounts.dim_account (REQUIRED)
        - FK to temporal.dim_calendar (REQUIRED)
        - FK to entity dimension
        - source_system column
        - Domain-specific extension columns

□ 4. BUILD & VALIDATE
    □ Build model: python -m scripts.build.build_models --models {model}
    □ Validate account mappings: python -m scripts.validate.check_account_coverage
    □ Run reconciliation: python -m scripts.validate.reconcile_balances

□ 5. INTEGRATE
    □ Add to unified_ledger view (if using)
    □ Update reporting models
    □ Test cross-source queries
```

### Why This Architecture Works

| Property | Benefit |
|----------|---------|
| **Additive** | New sources add rows, don't change structure |
| **Substitutable** | Can swap Alpha Vantage for SEC EDGAR without changing downstream |
| **Composable** | Mix corporate + municipal + tax data in same queries |
| **Extensible** | Domain-specific columns live in domain tables, not foundation |
| **Auditable** | source_system + source_reference track lineage |
| **Consistent** | Same account codes everywhere, regardless of source terminology |

### Cook County Tax Example Query

```sql
-- Compare property tax revenue to corporate revenue in same region
WITH cook_county_tax AS (
    SELECT
        t.agency_name,
        a.account_name,
        SUM(f.balance) as tax_revenue
    FROM municipal.cook_county.fact_account_balance f
    JOIN municipal.cook_county.dim_taxing_district t ON f.district_id = t.district_id
    JOIN accounts.dim_account a ON f.account_id = a.account_id
    WHERE a.account_code LIKE '41%'  -- Tax revenue accounts
      AND f.tax_year = 2024
    GROUP BY t.agency_name, a.account_name
),
corporate_revenue AS (
    SELECT
        c.company_name,
        a.account_name,
        SUM(f.balance) as corporate_revenue
    FROM corporate.financials.fact_account_balance f
    JOIN corporate.company.dim_company c ON f.company_id = c.company_id
    JOIN accounts.dim_account a ON f.account_id = a.account_id
    WHERE a.account_code LIKE '4%'  -- All revenue
      AND c.address LIKE '%Chicago%'  -- Chicago-based companies
      AND f.report_type = 'annual'
    GROUP BY c.company_name, a.account_name
)
SELECT * FROM cook_county_tax
UNION ALL
SELECT * FROM corporate_revenue
ORDER BY account_name;
```

---

## Directory Structure

```
domains/
├── foundation/                    # Tier 0 - Seeded reference dimensions
│   ├── temporal.md                # Calendar dimension
│   └── accounts.md                # Chart of Accounts dimension
│
├── _base/                         # Templates (never built directly)
│   ├── entity.md                  # Legal entity patterns
│   ├── securities.md              # Security patterns (prices)
│   └── financials.md              # Account balance patterns
│
├── corporate/                     # Corporate domain
│   ├── company.md                 # Company entities (Tier 1)
│   └── financials.md              # Company financials (Tier 2)
│
├── municipal/                     # Municipal domain
│   ├── entity.md                  # City/agency entities (Tier 1)
│   └── city_finance.md            # Municipal financials (Tier 2)
│
├── securities/                    # Securities domain
│   ├── stocks.md                  # Stock securities
│   ├── options.md                 # Options contracts
│   └── etfs.md                    # Exchange-traded funds
│
└── reporting/                     # Tier 3 - Derived views
    ├── financial_statements.md    # Balance sheet, income statement
    └── municipal_reports.md       # CAFR, budget reports
```

---

## Core Concepts

### Unified Schema Definition

**Everything about a column in ONE place:**

```yaml
schema:
  # Format: [name, type, nullable, description, {options}]

  # From bronze source (type "_" = infer from bronze)
  - [ticker, _, false, "Trading symbol", {from: alpha_vantage.listing_status.ticker}]

  # Derived from other columns
  - [security_id, integer, false, "PK", {derive: "ABS(HASH(ticker))"}]

  # Foreign key to foundation model
  - [account_id, integer, false, "FK", {fk: accounts.dim_account.account_id}]

  # Static/default value
  - [is_active, boolean, true, "Active", {default: true}]

  # Definition only (no source - for inheritance)
  - [exchange_code, string, true, "Exchange"]
```

**Column options:**
- `{from: provider.table.field}` - Pulls from bronze source
- `{derive: "SQL expression"}` - Computed from other columns
- `{default: value}` - Static default value
- `{enum: [values]}` - Allowed values
- `{fk: model.table.column}` - Foreign key reference
- `{pattern: "regex"}` - Validation pattern

### Build Trigger

**A table is built based on its schema content:**

| Schema contains | Result | Example |
|-----------------|--------|---------|
| Any `{from: ...}` | Built from bronze sources | Domain models |
| Only `{derive: ...}` + seeded | Generated/seeded model | Foundation models |
| Only `{derive: ...}` from silver | View model | Statement views |
| Neither | Definition only (inheritance) | Base templates |

### Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  data_sources:  │────▶│ schema.{from:}  │────▶│    storage:     │
│  (declares      │     │ (transforms)    │     │  (Silver output)│
│   available)    │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
    WHAT EXISTS            HOW TO BUILD           WHERE TO WRITE
```

---

## Template Specification

### Complete Template

```yaml
---
# ============================================================================
# IDENTITY
# ============================================================================
type: domain-model           # domain-model | base-template | foundation
model: model_name            # Unique identifier (required)
version: 4.0                 # Semantic version (required)
description: "Brief description"
tags: [tag1, tag2]           # For discovery/filtering

# ============================================================================
# INHERITANCE (optional)
# ============================================================================
extends:                     # List of base templates to inherit from
  - _base/securities         # First = primary base
  - _base/company_linked     # Subsequent = mixins (later overrides earlier)

# ============================================================================
# DEPENDENCIES (Silver layer - build order)
# ============================================================================
depends_on:
  - temporal                 # Foundation: calendar dimension
  - accounts                 # Foundation: chart of accounts
  - company                  # Entity model (if needed)

# ============================================================================
# DATA SOURCES (Bronze layer - declares available sources)
# ============================================================================
# Declares which bronze tables this model can use.
# Columns reference these via {from: provider.table.field}
# Omit for: foundation models, base templates, view models
data_sources:
  provider_name:             # Provider key (alpha_vantage, bls, chicago)
    - endpoint_id_1          # Available: bronze/{provider}/{endpoint_id}
    - endpoint_id_2
  another_provider:
    - endpoint_id_3

# ============================================================================
# STORAGE (Silver layer output)
# ============================================================================
# Omit for: base templates
storage:
  format: delta              # delta | parquet (default: delta)
  auto_vacuum: true          # Run OPTIMIZE/VACUUM (default: true)
  root: domain/model         # Relative path → storage/silver/{root}

# ============================================================================
# BUILD
# ============================================================================
build:
  partitions: []             # Partition columns
  sort_by: [primary_key]     # Z-order columns
  optimize: true             # Run OPTIMIZE after build

# ============================================================================
# TABLES (Unified schema with source lineage)
# ============================================================================
tables:
  table_name:
    type: dimension | fact
    description: "What this table represents"
    primary_key: [key_col]
    unique_key: [natural_key]          # Optional
    partition_by: [partition_col]      # Facts only
    tags: [dim, entity, seeded]        # Optional metadata

    # ---- SCHEMA (single source of truth for columns) ----
    # Format: [name, type, nullable, description, {options}]
    schema:
      # From bronze (type inferred)
      - [natural_key, _, false, "Natural key", {from: provider.table.source_field}]

      # Derived columns
      - [surrogate_id, integer, false, "PK", {derive: "ABS(HASH(natural_key))"}]
      - [date_id, integer, false, "FK to calendar", {derive: "...", fk: temporal.dim_calendar.date_id}]
      - [account_id, integer, false, "FK to accounts", {fk: accounts.dim_account.account_id}]

      # Static/defaults
      - [status, string, true, "Status", {enum: [active, inactive], default: "active"}]

    # ---- DROP (columns to exclude from output) ----
    drop: [temp_col, intermediate_col]

    # ---- MEASURES ----
    measures:
      # Format: [name, type, source|expr, description, {options}]
      - [record_count, count_distinct, surrogate_id, "Count", {format: "#,##0"}]
      - [ratio, expression, "AVG(a / NULLIF(b, 0))", "Ratio", {format: "#,##0.00%"}]

# ============================================================================
# EDGES (Cross-table relationships for JOINs)
# ============================================================================
# Format: [name, from, to, on, type, description]
edges:
  - [edge_name, source_table, target_table, fk_col=pk_col, many_to_one, "Description"]
  - [to_calendar, fact_table, temporal.dim_calendar, date_id=date_id, many_to_one]
  - [to_account, fact_table, accounts.dim_account, account_id=account_id, many_to_one]

# ============================================================================
# METADATA
# ============================================================================
metadata:
  domain: domain_name        # Logical grouping
  owner: team_name           # Responsible team
  sla_hours: 24              # Freshness SLA

status: active | draft | deprecated
---

## Model Documentation

Human-readable documentation in markdown body.
```

---

## Foundation Models

### 1. Temporal (Calendar Dimension)

```yaml
---
type: foundation
model: temporal
version: 4.0
description: "Calendar dimension - foundation for all date-based analysis"
tags: [foundation, calendar, dates, seeded]

# NO depends_on - Tier 0
# NO data_sources - seeded

storage:
  format: delta
  root: foundation/temporal

tables:
  dim_calendar:
    type: dimension
    description: "Calendar dimension with fiscal and trading day attributes"
    primary_key: [date_id]
    unique_key: [calendar_date]
    tags: [dim, calendar, seeded, foundation]

    schema:
      # Keys
      - [date_id, integer, false, "PK (YYYYMMDD format)", {derive: "seeded"}]
      - [calendar_date, date, false, "Calendar date", {derive: "seeded"}]

      # Date parts
      - [year, integer, false, "Year", {derive: "seeded"}]
      - [quarter, integer, false, "Quarter (1-4)", {derive: "seeded"}]
      - [month, integer, false, "Month (1-12)", {derive: "seeded"}]
      - [day_of_month, integer, false, "Day (1-31)", {derive: "seeded"}]
      - [day_of_week, integer, false, "Day of week (1=Mon)", {derive: "seeded"}]
      - [week_of_year, integer, false, "ISO week", {derive: "seeded"}]

      # Labels
      - [month_name, string, false, "Month name", {derive: "seeded"}]
      - [day_name, string, false, "Day name", {derive: "seeded"}]

      # Flags
      - [is_weekend, boolean, false, "Is weekend", {derive: "seeded"}]
      - [is_trading_day, boolean, false, "Is trading day", {derive: "seeded"}]
      - [is_month_end, boolean, false, "Is month end", {derive: "seeded"}]
      - [is_quarter_end, boolean, false, "Is quarter end", {derive: "seeded"}]
      - [is_year_end, boolean, false, "Is year end", {derive: "seeded"}]

      # Fiscal (configurable)
      - [fiscal_year, integer, true, "Fiscal year", {derive: "seeded"}]
      - [fiscal_quarter, integer, true, "Fiscal quarter", {derive: "seeded"}]

    measures:
      - [trading_days, expression, "SUM(CASE WHEN is_trading_day THEN 1 ELSE 0 END)", "Trading days"]
      - [calendar_days, count_distinct, date_id, "Calendar days"]

edges: []  # No outbound edges - foundation model

metadata:
  domain: foundation
  owner: data_engineering
  sla_hours: 168  # Weekly refresh

status: active
---

## Temporal (Calendar Dimension)

Foundation model providing calendar attributes for all date-based analysis.
Seeded from 2000-01-01 to 2050-12-31.

### Seed Script

```bash
python -m scripts.seed.seed_calendar --start 2000-01-01 --end 2050-12-31
```
```

---

### 2. Accounts (Chart of Accounts)

```yaml
---
type: foundation
model: accounts
version: 4.0
description: "Chart of Accounts - foundation for all financial models"
tags: [foundation, accounts, coa, seeded]

# NO depends_on - Tier 0
# NO data_sources - seeded

storage:
  format: delta
  root: foundation/accounts

tables:
  dim_account:
    type: dimension
    description: "Standard chart of accounts with hierarchy"
    primary_key: [account_id]
    unique_key: [account_code]
    tags: [dim, coa, hierarchy, seeded, foundation]

    schema:
      # Keys
      - [account_id, integer, false, "PK", {derive: "ABS(HASH(account_code))"}]

      # Account identity
      - [account_code, string, false, "Account code (e.g., 1000)", {pattern: "^[0-9]{4,6}$"}]
      - [account_name, string, false, "Account name"]
      - [account_description, string, true, "Description"]

      # Hierarchy (self-referential)
      - [parent_account_id, integer, true, "FK to parent", {fk: dim_account.account_id}]
      - [account_level, integer, false, "Level (1=top)", {default: 1}]
      - [account_path, string, true, "Path (e.g., Assets/Current/Cash)"]

      # Classification
      - [account_type, string, false, "Type", {enum: [asset, liability, equity, revenue, expense]}]
      - [account_subtype, string, true, "Subtype (current, non_current, operating, etc.)"]
      - [statement_section, string, false, "Statement", {enum: [balance_sheet, income_statement, cash_flow]}]
      - [cash_flow_category, string, true, "CF category", {enum: [operating, investing, financing]}]

      # Behavior
      - [normal_balance, string, false, "Normal balance", {enum: [debit, credit]}]
      - [is_contra, boolean, false, "Contra account", {default: false}]
      - [is_rollup, boolean, false, "Summary account", {default: false}]

      # Government/Municipal extensions (null for corporate)
      - [fund_type, string, true, "Fund type", {enum: [general, special_revenue, capital, enterprise, fiduciary]}]
      - [gasb_category, string, true, "GASB category (municipal)"]

      # Display
      - [display_order, integer, true, "Order in statement"]
      - [format_type, string, true, "Display format", {enum: [currency, percentage, ratio]}]

    measures:
      - [account_count, count_distinct, account_id, "Total accounts"]
      - [leaf_accounts, expression, "SUM(CASE WHEN is_rollup = false THEN 1 ELSE 0 END)", "Leaf accounts"]

edges:
  - [account_to_parent, dim_account, dim_account, parent_account_id=account_id, many_to_one, "Hierarchy"]

metadata:
  domain: foundation
  owner: data_engineering
  sla_hours: 168  # Weekly refresh (seeded data)

status: active
---

## Chart of Accounts (Foundation)

Standard chart of accounts supporting corporate and municipal accounting.

### Why Foundation Level?

The Chart of Accounts is referenced by ALL financial data:
- **Corporate** (company financials from Alpha Vantage)
- **Municipal** (Chicago city finance from Socrata)
- **Funds** (investment fund accounting)

This is exactly like `temporal` - a seeded reference dimension that multiple domains depend on.

### Standard Account Ranges

| Range | Type | Corporate | Municipal |
|-------|------|-----------|-----------|
| 1000-1499 | Assets - Current | ✓ | ✓ |
| 1500-1999 | Assets - Non-Current | ✓ | ✓ |
| 2000-2499 | Liabilities - Current | ✓ | ✓ |
| 2500-2999 | Liabilities - Non-Current | ✓ | ✓ |
| 3000-3999 | Equity/Fund Balance | ✓ | ✓ |
| 4000-4999 | Revenue | ✓ | ✓ |
| 5000-6999 | Expenses | ✓ | ✓ |
| 7000-7999 | Other/Transfers | ✓ | ✓ |
| 8000-8999 | Tax/Special | ✓ | - |
| 9000-9999 | Memo/Statistical | - | ✓ |

### Seed Script

```bash
python -m scripts.seed.seed_accounts --template gaap  # Corporate GAAP
python -m scripts.seed.seed_accounts --template gasb  # Municipal GASB
python -m scripts.seed.seed_accounts --template custom --file accounts.csv
```
```

---

## Base Templates

### _base/entity.md

```yaml
---
type: base-template
template: entity
version: 4.0
description: "Base patterns for legal entities"

tables:
  _dim_entity:
    type: dimension
    schema:
      # Standard entity fields (no sources - template only)
      - [entity_id, integer, false, "PK"]
      - [entity_name, string, false, "Legal name"]
      - [entity_type, string, true, "Type", {enum: [corporation, llc, partnership, municipality, agency]}]
      - [jurisdiction, string, true, "Incorporation jurisdiction"]
      - [tax_id, string, true, "Tax identifier"]
      - [is_active, boolean, true, "Active", {default: true}]

status: active
---

## Entity Base Template

Common patterns for legal entities (companies, municipalities, funds).
```

---

### _base/financials.md

```yaml
---
type: base-template
template: financials
version: 4.0
description: "Base patterns for financial data (account balances)"

tables:
  _fact_account_balance:
    type: fact
    description: "Period-end account balances"
    schema:
      - [balance_id, integer, false, "PK"]
      - [entity_id, integer, false, "FK to entity"]
      - [account_id, integer, false, "FK to accounts", {fk: accounts.dim_account.account_id}]
      - [period_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [report_type, string, false, "Period type", {enum: [annual, quarterly, monthly]}]
      - [balance, double, true, "Period-end balance"]
      - [prior_balance, double, true, "Prior period balance"]
      - [period_change, double, true, "Change", {derive: "COALESCE(balance, 0) - COALESCE(prior_balance, 0)"}]
      - [reported_currency, string, true, "Currency", {default: "USD"}]

    measures:
      - [total_balance, sum, balance, "Total", {format: "$#,##0.00"}]
      - [avg_balance, avg, balance, "Average", {format: "$#,##0.00"}]
      - [net_change, sum, period_change, "Net change", {format: "$#,##0.00"}]

status: active
---

## Financials Base Template

Common patterns for account balance fact tables. Used by corporate, municipal, and fund accounting.
```

---

### _base/securities.md

```yaml
---
type: base-template
template: securities
version: 4.0
description: "Base template for security types"
tags: [base, securities]

# NO data_sources - templates don't specify sources
# NO storage - templates don't persist

tables:
  dim_security:
    type: dimension
    primary_key: [security_id]
    unique_key: [ticker]

    # Definitions only - no {from:} sources
    schema:
      - [security_id, integer, false, "PK"]
      - [ticker, string, false, "Trading symbol"]
      - [asset_type, string, false, "Type", {enum: [stock, option, etf, future]}]
      - [exchange_code, string, true, "Exchange"]
      - [is_active, boolean, true, "Active", {default: true}]

    measures:
      - [security_count, count_distinct, security_id, "Securities"]

  fact_prices:
    type: fact
    primary_key: [price_id]
    partition_by: [date_id]

    # Definitions only - no {from:} sources
    schema:
      - [price_id, integer, false, "PK"]
      - [security_id, integer, false, "FK", {fk: dim_security.security_id}]
      - [date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [open, double, true, "Open price"]
      - [high, double, true, "High price"]
      - [low, double, true, "Low price"]
      - [close, double, true, "Close price"]
      - [volume, long, true, "Trading volume"]

    measures:
      - [avg_close, avg, close, "Avg close", {format: "$#,##0.00"}]
      - [total_volume, sum, volume, "Total volume", {format: "#,##0"}]

edges:
  - [prices_to_security, fact_prices, dim_security, security_id=security_id, many_to_one]

status: active
---

## Securities Base Template

Common patterns for all security types (stocks, options, ETFs, futures).
Concrete models extend this and add `{from:}` sources to columns.
```

---

## Domain Models

### 1. Corporate: company.md (Entity Only)

```yaml
---
type: domain-model
model: company
version: 4.0
description: "Corporate legal entities"
tags: [company, corporate, entity]

extends:
  - _base/entity

depends_on:
  - temporal

data_sources:
  alpha_vantage:
    - company_overview

storage:
  format: delta
  root: corporate/company

build:
  partitions: []
  sort_by: [company_id]

tables:
  dim_company:
    type: dimension
    description: "Corporate entity master"
    primary_key: [company_id]
    unique_key: [ticker]
    tags: [dim, entity, corporate]

    schema:
      # ---- Derived Keys ----
      - [company_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT('COMPANY_', ticker)))"}]
      - [is_active, boolean, true, "Active", {derive: "true"}]

      # ---- Identity ----
      - [cik, _, true, "SEC CIK", {from: alpha_vantage.company_overview.cik}]
      - [ticker, _, false, "Primary ticker", {from: alpha_vantage.company_overview.ticker}]
      - [company_name, _, false, "Name", {from: alpha_vantage.company_overview.company_name}]
      - [description, _, true, "Description", {from: alpha_vantage.company_overview.description}]

      # ---- Classification ----
      - [sector, _, true, "GICS Sector", {from: alpha_vantage.company_overview.sector}]
      - [industry, _, true, "GICS Industry", {from: alpha_vantage.company_overview.industry}]
      - [exchange_code, _, true, "Exchange", {from: alpha_vantage.company_overview.exchange_code}]
      - [asset_type, _, true, "Asset type", {from: alpha_vantage.company_overview.asset_type}]

      # ---- Location ----
      - [country, _, true, "Country", {from: alpha_vantage.company_overview.country, default: "US"}]
      - [address, _, true, "Address", {from: alpha_vantage.company_overview.address}]

      # ---- Operational ----
      - [fiscal_year_end, _, true, "FY end month", {from: alpha_vantage.company_overview.fiscal_year_end}]
      - [currency, _, true, "Currency", {from: alpha_vantage.company_overview.currency, default: "USD"}]
      - [official_site, _, true, "Website", {from: alpha_vantage.company_overview.official_site}]

    measures:
      - [company_count, count_distinct, company_id, "Companies"]

edges:
  - [company_to_stock, dim_company, stocks.dim_security, company_id=company_id, one_to_one]
  - [company_to_balances, dim_company, financials.fact_account_balance, company_id=company_id, one_to_many, "Company's account balances"]

metadata:
  domain: corporate
  owner: data_engineering
  sla_hours: 24

status: active
---

## Company Model (Entity Only)

Corporate legal entities. Financial data is in `corporate/financials`.
```

---

### 2. Corporate: financials.md (Account Balances)

```yaml
---
type: domain-model
model: financials
version: 4.0
description: "Corporate financial data (account balances from statements)"
tags: [corporate, financials, accounting]

extends:
  - _base/financials

depends_on:
  - temporal
  - accounts    # Foundation CoA
  - company     # Entity

data_sources:
  alpha_vantage:
    - income_statement
    - balance_sheet
    - cash_flow
    - earnings

storage:
  format: delta
  root: corporate/financials

build:
  partitions: [period_end_date_id]
  sort_by: [company_id, account_id]

tables:
  fact_account_balance:
    type: fact
    description: "Corporate account balances (normalized from financial statements)"
    primary_key: [balance_id]
    partition_by: [period_end_date_id]
    tags: [fact, balance, period]

    schema:
      # ---- Derived Keys ----
      - [balance_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(company_id, '_', account_id, '_', period_end_date_id, '_', report_type)))"}]
      - [company_id, integer, false, "FK to company", {derive: "ABS(HASH(CONCAT('COMPANY_', ticker)))", fk: company.dim_company.company_id}]
      - [account_id, integer, false, "FK to accounts", {fk: accounts.dim_account.account_id}]
      - [period_start_date_id, integer, false, "FK - period start", {fk: temporal.dim_calendar.date_id}]
      - [period_end_date_id, integer, false, "FK - period end", {fk: temporal.dim_calendar.date_id}]

      # ---- Attributes ----
      - [report_type, string, false, "Period type", {enum: [annual, quarterly]}]
      - [reported_currency, string, true, "Currency", {default: "USD"}]
      - [source_statement, string, false, "Source", {enum: [income_statement, balance_sheet, cash_flow]}]

      # ---- Balance Values ----
      - [balance, double, true, "Period-end balance"]
      - [prior_balance, double, true, "Prior period balance"]
      - [period_change, double, true, "Change", {derive: "COALESCE(balance, 0) - COALESCE(prior_balance, 0)"}]

    measures:
      - [total_balance, sum, balance, "Total", {format: "$#,##0.00B"}]
      - [avg_balance, avg, balance, "Average", {format: "$#,##0.00M"}]
      - [net_change, sum, period_change, "Net change", {format: "$#,##0.00M"}]

edges:
  - [balance_to_account, fact_account_balance, accounts.dim_account, account_id=account_id, many_to_one]
  - [balance_to_company, fact_account_balance, company.dim_company, company_id=company_id, many_to_one]
  - [balance_to_period_start, fact_account_balance, temporal.dim_calendar, period_start_date_id=date_id, many_to_one]
  - [balance_to_period_end, fact_account_balance, temporal.dim_calendar, period_end_date_id=date_id, many_to_one]

metadata:
  domain: corporate
  owner: data_engineering
  sla_hours: 24

status: active
---

## Corporate Financials

Account balances normalized from Alpha Vantage financial statements.

### Account Mapping from Alpha Vantage

The build process unpivots statement columns into account rows:

| Alpha Vantage Field | Account Code | Account Name |
|---------------------|--------------|--------------|
| `total_revenue` | 4000 | Total Revenue |
| `cost_of_revenue` | 5000 | Cost of Revenue |
| `operating_income` | 4100 | Operating Income |
| `net_income` | 4900 | Net Income |
| `total_assets` | 1000 | Total Assets |
| `total_current_assets` | 1100 | Current Assets |
| `cash_and_equivalents` | 1110 | Cash and Equivalents |
| `total_liabilities` | 2000 | Total Liabilities |
| `total_shareholder_equity` | 3000 | Total Equity |
| `operating_cashflow` | 7100 | Operating Cash Flow |
| `capital_expenditures` | 7200 | Capital Expenditures |
```

---

### 3. Municipal: city_finance.md

```yaml
---
type: domain-model
model: city_finance
version: 4.0
description: "Chicago municipal financial data"
tags: [municipal, chicago, government]

extends:
  - _base/financials

depends_on:
  - temporal
  - accounts    # Foundation CoA

data_sources:
  chicago:
    - budget_appropriations
    - budget_revenue
    - capital_projects

storage:
  format: delta
  root: municipal/chicago

build:
  partitions: [fiscal_year]
  sort_by: [department_id, account_id]

tables:
  dim_department:
    type: dimension
    description: "City departments and agencies"
    primary_key: [department_id]
    unique_key: [department_code]
    tags: [dim, entity, municipal]

    schema:
      - [department_id, integer, false, "PK", {derive: "ABS(HASH(department_code))"}]
      - [department_code, _, false, "Dept code", {from: chicago.budget_appropriations.department_code}]
      - [department_name, _, false, "Dept name", {from: chicago.budget_appropriations.department_name}]
      - [fund_code, _, true, "Fund code", {from: chicago.budget_appropriations.fund_code}]
      - [fund_name, _, true, "Fund name", {from: chicago.budget_appropriations.fund_name}]

  fact_account_balance:
    type: fact
    description: "Municipal account balances by department and fund"
    primary_key: [balance_id]
    partition_by: [fiscal_year]
    tags: [fact, balance, budget]

    schema:
      # ---- Derived Keys ----
      - [balance_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(department_id, '_', account_id, '_', fiscal_year)))"}]
      - [department_id, integer, false, "FK to department", {derive: "ABS(HASH(department_code))", fk: dim_department.department_id}]
      - [account_id, integer, false, "FK to accounts", {fk: accounts.dim_account.account_id}]
      - [period_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [fiscal_year, integer, false, "Fiscal year"]

      # ---- Budget Values ----
      - [appropriation, _, true, "Budgeted amount", {from: chicago.budget_appropriations.appropriation}]
      - [expenditure, _, true, "Actual spent", {from: chicago.budget_appropriations.expenditure}]
      - [encumbrance, _, true, "Committed", {from: chicago.budget_appropriations.encumbrance}]
      - [available, double, true, "Available", {derive: "COALESCE(appropriation, 0) - COALESCE(expenditure, 0) - COALESCE(encumbrance, 0)"}]

    measures:
      - [total_appropriation, sum, appropriation, "Total budget", {format: "$#,##0.00M"}]
      - [total_expenditure, sum, expenditure, "Total spent", {format: "$#,##0.00M"}]
      - [budget_utilization, expression, "SUM(expenditure) / NULLIF(SUM(appropriation), 0) * 100", "Utilization %", {format: "#,##0.0%"}]

edges:
  - [balance_to_account, fact_account_balance, accounts.dim_account, account_id=account_id, many_to_one]
  - [balance_to_department, fact_account_balance, dim_department, department_id=department_id, many_to_one]
  - [balance_to_calendar, fact_account_balance, temporal.dim_calendar, period_date_id=date_id, many_to_one]

metadata:
  domain: municipal
  owner: data_engineering
  sla_hours: 24

status: active
---

## Chicago City Finance

Municipal financial data using the same Chart of Accounts foundation as corporate.

### Municipal-Specific Account Extensions

The foundation `accounts.dim_account` includes optional municipal fields:
- `fund_type` - General, special revenue, capital, enterprise, fiduciary
- `gasb_category` - GASB statement classification

These are null for corporate entities but populated for municipal.
```

---

### 4. Securities: stocks.md

```yaml
---
type: domain-model
model: stocks
version: 4.0
description: "Stock securities with price data"
tags: [securities, stocks]

extends:
  - _base/securities

depends_on:
  - temporal
  - company

data_sources:
  alpha_vantage:
    - listing_status
    - time_series_daily

storage:
  format: delta
  root: securities/stocks

build:
  partitions: [date_id]
  sort_by: [ticker]

tables:
  dim_security:
    type: dimension
    primary_key: [security_id]
    unique_key: [ticker]
    description: "Stock securities"

    schema:
      # Inherited structure, adding sources:
      - [security_id, integer, false, "PK", {derive: "ABS(HASH(ticker))"}]
      - [ticker, _, false, "Trading symbol", {from: alpha_vantage.listing_status.ticker}]
      - [asset_type, _, false, "Type", {from: alpha_vantage.listing_status.asset_type}]
      - [exchange_code, _, true, "Exchange", {from: alpha_vantage.listing_status.exchange}]
      - [is_active, boolean, true, "Active", {default: true}]

      # Stock-specific:
      - [company_id, integer, true, "FK to company", {derive: "ABS(HASH(CONCAT('COMPANY_', ticker)))", fk: company.dim_company.company_id}]
      - [security_name, _, true, "Security name", {from: alpha_vantage.listing_status.name}]

  fact_prices:
    type: fact
    primary_key: [price_id]
    partition_by: [date_id]
    description: "Daily stock prices"

    schema:
      # Inherited, adding sources:
      - [price_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(ticker, '_', CAST(trade_date AS STRING))))"}]
      - [security_id, integer, false, "FK", {derive: "ABS(HASH(ticker))", fk: dim_security.security_id}]
      - [date_id, integer, false, "FK", {derive: "CAST(DATE_FORMAT(trade_date, 'yyyyMMdd') AS INT)", fk: temporal.dim_calendar.date_id}]

      - [ticker, _, false, "Ticker", {from: alpha_vantage.time_series_daily.ticker}]
      - [trade_date, _, false, "Trade date", {from: alpha_vantage.time_series_daily.trade_date}]
      - [open, _, true, "Open", {from: alpha_vantage.time_series_daily.open}]
      - [high, _, true, "High", {from: alpha_vantage.time_series_daily.high}]
      - [low, _, true, "Low", {from: alpha_vantage.time_series_daily.low}]
      - [close, _, true, "Close", {from: alpha_vantage.time_series_daily.close}]
      - [volume, _, true, "Volume", {from: alpha_vantage.time_series_daily.volume}]

    drop: [ticker, trade_date]  # Replaced by FKs

edges:
  - [prices_to_calendar, fact_prices, temporal.dim_calendar, date_id=date_id, many_to_one]
  - [security_to_company, dim_security, company.dim_company, company_id=company_id, many_to_one]

metadata:
  domain: securities
  owner: data_engineering

status: active
---

## Stocks Model

Stock securities with daily prices. Note: Stocks use the securities pattern (prices), not the financials pattern (account balances).
```

---

## View Models (Tier 3)

### financial_statements.md

```yaml
---
type: domain-model
model: financial_statements
version: 4.0
description: "Financial statements derived from account balances"
tags: [statements, generated, views]

depends_on:
  - temporal
  - accounts
  - company
  - financials

# NO data_sources - derived from silver

storage:
  format: delta
  root: reporting/statements

tables:
  view_balance_sheet:
    type: fact
    description: "Balance sheet aggregated from account balances"
    generated: true
    primary_key: [balance_sheet_id]
    partition_by: [period_end_date_id]

    schema:
      - [balance_sheet_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(company_id, '_', period_end_date_id)))"}]
      - [company_id, integer, false, "FK", {fk: company.dim_company.company_id}]
      - [period_end_date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [report_type, string, false, "Period type"]

      # Assets (aggregated from account_type = 'asset')
      - [total_assets, double, true, "Total assets", {derive: "SUM(balance) FILTER (WHERE account_type = 'asset')"}]
      - [total_current_assets, double, true, "Current assets", {derive: "SUM(balance) FILTER (WHERE account_type = 'asset' AND account_subtype = 'current')"}]
      - [total_non_current_assets, double, true, "Non-current assets", {derive: "SUM(balance) FILTER (WHERE account_type = 'asset' AND account_subtype = 'non_current')"}]

      # Liabilities
      - [total_liabilities, double, true, "Total liabilities", {derive: "SUM(balance) FILTER (WHERE account_type = 'liability')"}]
      - [total_current_liabilities, double, true, "Current liabilities", {derive: "SUM(balance) FILTER (WHERE account_type = 'liability' AND account_subtype = 'current')"}]

      # Equity
      - [total_equity, double, true, "Shareholder equity", {derive: "SUM(balance) FILTER (WHERE account_type = 'equity')"}]

    measures:
      - [avg_assets, avg, total_assets, "Avg assets", {format: "$#,##0.00B"}]
      - [current_ratio, expression, "AVG(total_current_assets / NULLIF(total_current_liabilities, 0))", "Current ratio"]

  view_income_statement:
    type: fact
    description: "Income statement aggregated from account balances"
    generated: true
    primary_key: [income_statement_id]
    partition_by: [period_end_date_id]

    schema:
      - [income_statement_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(company_id, '_', period_end_date_id)))"}]
      - [company_id, integer, false, "FK", {fk: company.dim_company.company_id}]
      - [period_end_date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [report_type, string, false, "Period type"]

      # Revenue & Expenses
      - [total_revenue, double, true, "Revenue", {derive: "SUM(balance) FILTER (WHERE account_type = 'revenue')"}]
      - [total_expenses, double, true, "Expenses", {derive: "SUM(balance) FILTER (WHERE account_type = 'expense')"}]
      - [net_income, double, true, "Net income", {derive: "total_revenue - total_expenses"}]

    measures:
      - [avg_revenue, avg, total_revenue, "Avg revenue", {format: "$#,##0.00B"}]
      - [profit_margin, expression, "AVG(net_income / NULLIF(total_revenue, 0))", "Profit margin", {format: "#,##0.0%"}]

edges:
  - [bs_to_company, view_balance_sheet, company.dim_company, company_id=company_id, many_to_one]
  - [is_to_company, view_income_statement, company.dim_company, company_id=company_id, many_to_one]

metadata:
  domain: reporting
  owner: data_engineering

status: active
---

## Financial Statements (Generated Views)

Traditional statement formats derived from the normalized Chart of Accounts.
```

---

## Inheritance Rules

### Multiple Inheritance via `extends` List

```yaml
extends:
  - _base/securities         # Primary base (applied first)
  - _base/company_linked     # Mixin (merged on top)
```

**Merge order:** Left to right, later overrides earlier.

### What Gets Inherited

| Section | Inherited? | Behavior |
|---------|------------|----------|
| `tables:` | ✅ Yes | Deep merged (child overrides parent) |
| `tables.*.schema:` | ✅ Yes | Columns merged by name |
| `tables.*.measures:` | ✅ Yes | Measures merged by name |
| `edges:` | ✅ Yes | Merged by name |
| `data_sources:` | ❌ No | Child defines own sources |
| `storage:` | ❌ No | Child defines own output |
| `depends_on:` | ✅ Yes | Combined (parent + child) |

### The Materialization Pattern

Base templates define columns WITHOUT `{from:}`. Child models ADD sources:

```yaml
# _base/securities.md (template)
tables:
  dim_security:
    schema:
      - [ticker, string, false, "Trading symbol"]  # No source

# stocks.md (concrete model)
tables:
  dim_security:
    schema:
      - [ticker, _, false, "Trading symbol", {from: alpha_vantage.listing_status.ticker}]
```

---

## Type Inference

### Using `_` for Type

When a column has `{from: ...}`, use `_` to infer type from bronze:

```yaml
schema:
  # Type inferred from bronze schema
  - [ticker, _, false, "Symbol", {from: alpha_vantage.listing_status.ticker}]
  #         ^ will be "string" based on bronze

  # Explicit type (derived column - must specify)
  - [security_id, integer, false, "PK", {derive: "ABS(HASH(ticker))"}]
```

---

## Migration from v3.0

### Breaking Changes

| v3.0 Section | v4.0 Location | Change |
|--------------|---------------|--------|
| `storage.bronze.provider` | `data_sources:` | Provider at top of section |
| `storage.bronze.tables` | `data_sources.{provider}: [list]` | Simple endpoint list |
| `storage.silver.root` | `storage.root` | Simplified |
| `graph.nodes.*.from` | *Removed* | Implicit from `{from: ...}` in columns |
| `graph.nodes.*.select` | `schema: [{from: ...}]` | Per-column source |
| `graph.nodes.*.derive` | `schema: [{derive: ...}]` | Per-column derive |
| `graph.edges:` | `edges:` (top-level, flattened) | Array format |
| Separate schema/select/derive | Unified in `schema:` | Single source of truth |
| Financial statements in company | Separate `financials` model | Normalized to CoA |

### Dependency Graph Changes

```
v3.0:
  temporal → company (with all financials) → stocks

v4.0:
  temporal ─┬─→ accounts (foundation)
            │        │
            └────────┼──→ company (entity only)
                     │        │
                     └────────┴──→ financials (fact_account_balance)
                                        │
                                        └──→ financial_statements (views)
```

---

## Account Mapping: Handling Non-Uniform Budget Fields

This section covers the architecture for integrating financial data from multiple sources with different terminologies into a unified Chart of Accounts.

---

### Industry Standard Approaches

Before diving into implementation, let's review how this problem is solved in enterprise systems:

#### 1. Master Data Management (MDM)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      MASTER DATA MANAGEMENT PATTERN                      │
└─────────────────────────────────────────────────────────────────────────┘

     Source Systems                    MDM Hub                    Consumers
    ┌─────────────┐              ┌─────────────────┐            ┌─────────┐
    │ Alpha       │─────────────▶│  GOLDEN RECORD  │◀───────────│ Reports │
    │ Vantage     │   crosswalk  │                 │            └─────────┘
    └─────────────┘              │  • Canonical ID │            ┌─────────┐
    ┌─────────────┐              │  • Attributes   │◀───────────│ Analytics│
    │ Chicago     │─────────────▶│  • Confidence   │            └─────────┘
    │ Budget      │   crosswalk  │  • Source refs  │            ┌─────────┐
    └─────────────┘              │                 │◀───────────│ ML      │
    ┌─────────────┐              └─────────────────┘            └─────────┘
    │ Future      │─────────────▶        ▲
    │ Sources     │   crosswalk          │
    └─────────────┘                      │
                                   Stewardship
                                   (human review)
```

**Key principle**: The "golden record" is the authoritative version. Source records link TO it, not to each other.

#### 2. Data Vault 2.0 (Hub-Satellite Pattern)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA VAULT PATTERN                               │
└─────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │      HUB        │
                              │  Account Term   │
                              │                 │
                              │ • term_hash_key │
                              │ • load_date     │
                              │ • record_source │
                              └────────┬────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           │                           │                           │
           ▼                           ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│     SATELLITE       │    │     SATELLITE       │    │     SATELLITE       │
│  Alpha Vantage Attrs│    │  Chicago Attrs      │    │  Standard Attrs     │
│                     │    │                     │    │                     │
│ • term_hash_key(FK) │    │ • term_hash_key(FK) │    │ • term_hash_key(FK) │
│ • field_name        │    │ • field_name        │    │ • account_code      │
│ • description       │    │ • description       │    │ • account_name      │
│ • api_endpoint      │    │ • dataset_id        │    │ • gaap_mapping      │
│ • data_type         │    │ • data_type         │    │ • gasb_mapping      │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘

                              ┌─────────────────┐
                              │      LINK       │
                              │  Term Mapping   │
                              │                 │
                              │ • source_term_hk│
                              │ • target_term_hk│
                              │ • confidence    │
                              │ • mapping_type  │
                              └─────────────────┘
```

**Key principle**: Separate the business key (Hub) from descriptive attributes (Satellites) from relationships (Links).

#### 3. Semantic Layer / Business Glossary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      SEMANTIC LAYER PATTERN                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  BUSINESS GLOSSARY (What business users see)                            │
│                                                                         │
│  "Revenue"                                                              │
│    Definition: "Total income from sales of goods and services"          │
│    Formula: "SUM of all account_type='revenue' balances"                │
│    Synonyms: ["Sales", "Income", "Top Line", "Turnover"]                │
│    Related: ["Net Revenue", "Gross Revenue", "Operating Revenue"]       │
└─────────────────────────────────────────────────────────────────────────┘
           │
           │ implements
           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  TECHNICAL MAPPING (How it maps to sources)                             │
│                                                                         │
│  Alpha Vantage: income_statement.total_revenue                          │
│  Chicago:       budget_revenue.TOTAL_REVENUE_COLLECTED                  │
│  SEC XBRL:      us-gaap:Revenues                                        │
│  Custom:        fact_account_balance WHERE account_type='revenue'       │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key principle**: Define business concepts independently from their technical implementations.

#### 4. XBRL Taxonomy (Financial Reporting Standard)

XBRL (eXtensible Business Reporting Language) is the SEC standard for financial reporting:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         XBRL TAXONOMY                                    │
└─────────────────────────────────────────────────────────────────────────┘

us-gaap:Revenues
├── us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax
├── us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax
├── us-gaap:InterestAndDividendIncomeOperating
└── us-gaap:OtherOperatingIncome

us-gaap:Assets
├── us-gaap:AssetsCurrent
│   ├── us-gaap:CashAndCashEquivalentsAtCarryingValue
│   ├── us-gaap:AccountsReceivableNetCurrent
│   └── us-gaap:InventoryNet
└── us-gaap:AssetsNoncurrent
    ├── us-gaap:PropertyPlantAndEquipmentNet
    └── us-gaap:Goodwill
```

**Key principle**: Use established taxonomies (GAAP, GASB, IFRS) as your canonical reference.

---

### Recommended Architecture: Three-Layer Semantic Model

Based on industry patterns, here's the recommended architecture for de_Funk:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    THREE-LAYER SEMANTIC MODEL                            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: SOURCE TERMS (Raw, as-is from each provider)                  │
│                                                                         │
│  dim_source_term                                                        │
│  ├── source_term_id (PK)                                                │
│  ├── provider                     "alpha_vantage" | "chicago" | ...     │
│  ├── endpoint                     "income_statement" | "budget" | ...   │
│  ├── field_name                   "total_revenue" | "APPROPRIATION"     │
│  ├── field_description            From API docs or metadata             │
│  ├── data_type                    "double" | "string" | ...             │
│  ├── sample_values                ["1000000", "2500000", ...]           │
│  ├── embedding_vector             [0.12, -0.34, ...]                    │
│  └── discovered_at                First seen timestamp                  │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              │ N:M mapping
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: CANONICAL TERMS (Our business glossary)                       │
│                                                                         │
│  dim_canonical_term                                                     │
│  ├── canonical_term_id (PK)                                             │
│  ├── term_name                    "Total Revenue"                       │
│  ├── term_definition              "Sum of all revenue..."               │
│  ├── term_category                "revenue" | "expense" | "asset" | ... │
│  ├── synonyms                     ["Sales", "Income", "Top Line"]       │
│  ├── related_terms                [other canonical_term_ids]            │
│  ├── embedding_vector             [0.15, -0.32, ...]                    │
│  ├── owner                        "finance_team"                        │
│  └── status                       "approved" | "draft" | "deprecated"   │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              │ N:M mapping
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: STANDARD ACCOUNTS (Chart of Accounts / XBRL)                  │
│                                                                         │
│  dim_account (existing foundation model)                                │
│  ├── account_id (PK)                                                    │
│  ├── account_code                 "4000"                                │
│  ├── account_name                 "Revenue"                             │
│  ├── xbrl_element                 "us-gaap:Revenues"                    │
│  ├── gaap_reference               "ASC 606"                             │
│  ├── gasb_reference               "GASB 34" (for municipal)             │
│  └── ...                                                                │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Why Three Layers?

| Layer | Purpose | Changes | Owner |
|-------|---------|---------|-------|
| **Source Terms** | Capture raw terminology exactly as received | Every new source/field | Automated discovery |
| **Canonical Terms** | Business-friendly definitions | When business needs change | Business analysts |
| **Standard Accounts** | Regulatory-compliant structure | Rarely (standards updates) | Finance/Compliance |

**Key insight**: Source terms are MANY, canonical terms are FEWER (grouped concepts), accounts are FEWEST (standard structure).

---

### Data Model: Foundation Layer Extension

```yaml
# domains/foundation/accounts.md (extended)

tables:
  # ============================================================================
  # LAYER 3: Standard Chart of Accounts (existing)
  # ============================================================================
  dim_account:
    # ... existing schema from earlier ...

  # ============================================================================
  # LAYER 2: Canonical Business Terms (NEW)
  # ============================================================================
  dim_canonical_term:
    type: dimension
    description: "Business glossary - canonical term definitions"
    primary_key: [canonical_term_id]
    unique_key: [term_name]
    tags: [dim, glossary, semantic]

    schema:
      # Identity
      - [canonical_term_id, integer, false, "PK", {derive: "ABS(HASH(term_name))"}]
      - [term_name, string, false, "Business term name"]
      - [term_definition, string, false, "Clear definition"]
      - [term_category, string, false, "Category", {enum: [revenue, expense, asset, liability, equity, metric, other]}]

      # Semantic enrichment
      - [synonyms, array<string>, true, "Alternative names"]
      - [related_terms, array<integer>, true, "Related canonical_term_ids"]
      - [anti_patterns, array<string>, true, "Terms this is NOT (disambiguation)"]
      - [examples, array<string>, true, "Example usages"]
      - [embedding_vector, array<float>, true, "Semantic embedding"]

      # Governance
      - [owner, string, true, "Responsible team/person"]
      - [status, string, false, "Status", {enum: [draft, approved, deprecated], default: "draft"}]
      - [approved_by, string, true, "Who approved"]
      - [approved_at, timestamp, true, "When approved"]

      # Lineage
      - [created_at, timestamp, false, "Created"]
      - [updated_at, timestamp, false, "Last updated"]
      - [version, integer, false, "Version number", {default: 1}]

    measures:
      - [term_count, count_distinct, canonical_term_id, "Total terms"]
      - [approved_pct, expression, "AVG(CASE WHEN status='approved' THEN 1.0 ELSE 0.0 END)*100", "% Approved"]

  # ============================================================================
  # LAYER 1: Source Terms (NEW)
  # ============================================================================
  dim_source_term:
    type: dimension
    description: "Raw terms from source systems - auto-discovered"
    primary_key: [source_term_id]
    unique_key: [provider, endpoint, field_name]
    tags: [dim, source, discovery]

    schema:
      # Identity
      - [source_term_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(provider, '.', endpoint, '.', field_name)))"}]
      - [provider, string, false, "Data provider"]
      - [endpoint, string, false, "API endpoint or table"]
      - [field_name, string, false, "Original field name"]

      # Metadata from source
      - [field_description, string, true, "Description from API/docs"]
      - [data_type, string, true, "Data type"]
      - [sample_values, array<string>, true, "Sample values (for context)"]
      - [value_distribution, string, true, "JSON stats: min, max, nulls, etc."]

      # Semantic
      - [embedding_vector, array<float>, true, "Semantic embedding"]
      - [normalized_name, string, true, "Cleaned/normalized version"]

      # Discovery metadata
      - [discovered_at, timestamp, false, "First seen"]
      - [last_seen_at, timestamp, false, "Most recent observation"]
      - [occurrence_count, integer, false, "Times seen", {default: 1}]
      - [is_active, boolean, false, "Still in source", {default: true}]

    measures:
      - [source_term_count, count_distinct, source_term_id, "Total source terms"]
      - [provider_count, count_distinct, provider, "Providers"]

  # ============================================================================
  # LINK: Source Term → Canonical Term (NEW)
  # ============================================================================
  link_source_to_canonical:
    type: fact
    description: "Maps source terms to canonical business terms"
    primary_key: [link_id]
    tags: [link, mapping, probabilistic]

    schema:
      # Keys
      - [link_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(source_term_id, '_', canonical_term_id)))"}]
      - [source_term_id, integer, false, "FK", {fk: dim_source_term.source_term_id}]
      - [canonical_term_id, integer, false, "FK", {fk: dim_canonical_term.canonical_term_id}]

      # Confidence scores (from different methods)
      - [confidence_rule, double, true, "Rule-based confidence"]
      - [confidence_embedding, double, true, "Embedding similarity"]
      - [confidence_llm, double, true, "LLM classification confidence"]
      - [confidence_combined, double, false, "Final combined confidence"]

      # Provenance
      - [mapping_method, string, false, "Primary method", {enum: [manual, rule, embedding, llm, ensemble]}]
      - [rule_matched, string, true, "Which rule matched (if any)"]
      - [llm_reasoning, string, true, "LLM explanation (if used)"]

      # Verification
      - [verified, boolean, false, "Human verified", {default: false}]
      - [verified_by, string, true, "Who verified"]
      - [verified_at, timestamp, true, "When verified"]
      - [verification_notes, string, true, "Notes from review"]

      # History
      - [created_at, timestamp, false, "Created"]
      - [updated_at, timestamp, false, "Last updated"]
      - [superseded_by, integer, true, "Newer link_id if updated"]

    measures:
      - [link_count, count_distinct, link_id, "Total mappings"]
      - [avg_confidence, avg, confidence_combined, "Avg confidence"]
      - [verified_pct, expression, "AVG(CASE WHEN verified THEN 1.0 ELSE 0.0 END)*100", "% Verified"]
      - [high_confidence_pct, expression, "AVG(CASE WHEN confidence_combined >= 0.8 THEN 1.0 ELSE 0.0 END)*100", "% High Conf"]

  # ============================================================================
  # LINK: Canonical Term → Standard Account (NEW)
  # ============================================================================
  link_canonical_to_account:
    type: fact
    description: "Maps canonical terms to standard accounts"
    primary_key: [link_id]
    tags: [link, mapping]

    schema:
      # Keys
      - [link_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(canonical_term_id, '_', account_id)))"}]
      - [canonical_term_id, integer, false, "FK", {fk: dim_canonical_term.canonical_term_id}]
      - [account_id, integer, false, "FK", {fk: dim_account.account_id}]

      # Mapping type
      - [mapping_type, string, false, "Type", {enum: [exact, partial, aggregates_to, component_of]}]
      - [contribution_weight, double, true, "Weight if partial (0-1)"]
      - [aggregation_rule, string, true, "How to aggregate if multiple"]

      # Governance
      - [approved, boolean, false, "Approved mapping", {default: false}]
      - [approved_by, string, true, "Who approved"]
      - [effective_from, date, true, "Effective date"]
      - [effective_to, date, true, "End date (if deprecated)"]

    measures:
      - [mapping_count, count_distinct, link_id, "Total mappings"]

edges:
  # Existing
  - [account_to_parent, dim_account, dim_account, parent_account_id=account_id, many_to_one, "Hierarchy"]

  # New: Layer linkages
  - [source_to_canonical, link_source_to_canonical, dim_source_term, source_term_id=source_term_id, many_to_one]
  - [canonical_from_source, link_source_to_canonical, dim_canonical_term, canonical_term_id=canonical_term_id, many_to_one]
  - [canonical_to_account, link_canonical_to_account, dim_canonical_term, canonical_term_id=canonical_term_id, many_to_one]
  - [account_from_canonical, link_canonical_to_account, dim_account, account_id=account_id, many_to_one]
```

---

### Entity Resolution Pipeline

The mapping process follows an entity resolution pattern:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ENTITY RESOLUTION PIPELINE                          │
└─────────────────────────────────────────────────────────────────────────┘

PHASE 1: DISCOVERY (Automated)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌─────────────────┐
│  New Source     │
│  (Bronze Table) │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Extract unique fields → Create dim_source_term records                 │
│                                                                         │
│  SELECT DISTINCT                                                        │
│    'chicago' as provider,                                               │
│    'budget_appropriations' as endpoint,                                 │
│    column_name as field_name,                                           │
│    column_comment as field_description,                                 │
│    data_type                                                            │
│  FROM information_schema.columns                                        │
│  WHERE table_name = 'budget_appropriations'                             │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Generate embeddings for new source terms                               │
│                                                                         │
│  text = f"{field_name}: {field_description or ''}"                      │
│  embedding = model.encode(text)                                         │
└─────────────────────────────────────────────────────────────────────────┘


PHASE 2: BLOCKING (Reduce comparison space)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌─────────────────────────────────────────────────────────────────────────┐
│  Instead of comparing every source term to every canonical term,        │
│  use blocking to reduce candidates:                                     │
│                                                                         │
│  Block 1: Same category (revenue terms only compare to revenue)         │
│  Block 2: First letter / prefix                                         │
│  Block 3: Embedding cluster (approximate nearest neighbors)             │
└─────────────────────────────────────────────────────────────────────────┘


PHASE 3: MATCHING (Multi-method)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  Source Term: "PERSONNEL SERVICES" (Chicago)                            │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ METHOD 1: Exact/Fuzzy String Match                              │    │
│  │                                                                 │    │
│  │ Levenshtein("PERSONNEL SERVICES", "Personnel Costs") = 0.65    │    │
│  │ Jaro-Winkler("PERSONNEL SERVICES", "Salaries") = 0.42          │    │
│  │ Token overlap: {"PERSONNEL"} ∩ {"Personnel"} = 1               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ METHOD 2: Embedding Similarity                                  │    │
│  │                                                                 │    │
│  │ cosine(embed("PERSONNEL SERVICES"), embed("Salaries")) = 0.89  │    │
│  │ cosine(embed("PERSONNEL SERVICES"), embed("Wages")) = 0.85     │    │
│  │ cosine(embed("PERSONNEL SERVICES"), embed("Contracted")) = 0.45│    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ METHOD 3: Rule-Based Patterns                                   │    │
│  │                                                                 │    │
│  │ MATCH: "(?i)personnel|salary|wage|payroll" → "Compensation"     │    │
│  │ Result: MATCHED with confidence 0.95                            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ METHOD 4: LLM Classification (if needed)                        │    │
│  │                                                                 │    │
│  │ Prompt: "Classify 'PERSONNEL SERVICES' from Chicago budget..."  │    │
│  │ Response: {"term": "Employee Compensation", "confidence": 0.92} │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘


PHASE 4: SCORING & COMBINATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  Candidate Canonical Terms for "PERSONNEL SERVICES":                    │
│                                                                         │
│  ┌────────────────────┬────────┬────────┬────────┬────────┬──────────┐ │
│  │ Canonical Term     │ String │ Embed  │ Rule   │ LLM    │ Combined │ │
│  ├────────────────────┼────────┼────────┼────────┼────────┼──────────┤ │
│  │ Employee Salaries  │ 0.45   │ 0.89   │ 0.95   │ 0.92   │ 0.94     │ │
│  │ Contracted Services│ 0.72   │ 0.45   │ 0.00   │ 0.05   │ 0.18     │ │
│  │ Personnel Training │ 0.68   │ 0.62   │ 0.30   │ 0.15   │ 0.35     │ │
│  └────────────────────┴────────┴────────┴────────┴────────┴──────────┘ │
│                                                                         │
│  Combined score using calibrated Bayesian combination (see earlier)     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘


PHASE 5: CLUSTERING (Optional - Group source terms)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  If no existing canonical term matches well, cluster similar source     │
│  terms to suggest NEW canonical terms:                                  │
│                                                                         │
│  Cluster 1 (suggested: "Employee Compensation"):                        │
│    - alpha_vantage.income_statement.total_operating_expense             │
│    - chicago.budget.PERSONNEL_SERVICES                                  │
│    - seattle.budget.SALARIES_AND_WAGES                                  │
│    - nyc.budget.PS_PERSONAL_SERVICES                                    │
│                                                                         │
│  Cluster 2 (suggested: "Professional Services"):                        │
│    - alpha_vantage.income_statement.sg_and_a                            │
│    - chicago.budget.CONTRACTUAL_SERVICES                                │
│    - seattle.budget.CONTRACTED_SVCS                                     │
│                                                                         │
│  → Present clusters to human for canonical term creation                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘


PHASE 6: DECISION & HUMAN REVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  Based on combined confidence:                                          │
│                                                                         │
│  ┌─────────────────────┬─────────────────────────────────────────────┐ │
│  │ Confidence Range    │ Action                                      │ │
│  ├─────────────────────┼─────────────────────────────────────────────┤ │
│  │ ≥ 0.95              │ AUTO-LINK (no review needed)                │ │
│  │ 0.85 - 0.95         │ AUTO-LINK + flag for spot-check             │ │
│  │ 0.70 - 0.85         │ SUGGEST + require human approval            │ │
│  │ 0.50 - 0.70         │ SUGGEST multiple options + human picks      │ │
│  │ < 0.50              │ CLUSTER + suggest new canonical term        │ │
│  └─────────────────────┴─────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Confidence Scoring Deep Dive

#### Prior Probability Model

Instead of uniform priors, use informative priors based on domain knowledge:

```python
class InformedPriorModel:
    """
    Prior probabilities based on:
    1. Provider patterns (Alpha Vantage tends to use GAAP terms)
    2. Category co-occurrence (revenue terms rarely map to expense accounts)
    3. Historical mapping frequencies
    """

    def __init__(self):
        # Provider-specific priors: P(canonical_term | provider)
        self.provider_priors = {
            'alpha_vantage': {
                # Alpha Vantage uses standard GAAP terminology
                'total_revenue': {'Revenue': 0.95, 'Net Sales': 0.04, 'Other': 0.01},
                'net_income': {'Net Income': 0.98, 'Other': 0.02},
            },
            'chicago': {
                # Chicago uses government/GASB terminology
                'PERSONNEL SERVICES': {'Employee Compensation': 0.85, 'Contracted Services': 0.10, 'Other': 0.05},
                'CONTRACTUAL SERVICES': {'Professional Services': 0.80, 'Employee Compensation': 0.05, 'Other': 0.15},
            }
        }

        # Category compatibility matrix: P(source_category | canonical_category)
        # Prevents revenue source terms from mapping to expense canonical terms
        self.category_compatibility = {
            #                    rev    exp    asset  liab   equity
            'revenue':         [0.90,  0.02,  0.03,  0.02,  0.03],
            'expense':         [0.02,  0.90,  0.03,  0.02,  0.03],
            'asset':           [0.02,  0.02,  0.90,  0.03,  0.03],
            'liability':       [0.02,  0.02,  0.03,  0.90,  0.03],
            'equity':          [0.03,  0.03,  0.03,  0.03,  0.88],
        }

    def get_prior(self, source_term: str, canonical_term: str,
                  provider: str, source_category: str, canonical_category: str) -> float:
        """
        Compute prior probability P(canonical_term | source_term, provider, categories)
        """
        # Start with base rate (uniform over canonical terms)
        n_canonical = 100  # approximate number of canonical terms
        base_prior = 1.0 / n_canonical

        # Adjust for provider-specific patterns
        if provider in self.provider_priors:
            provider_dist = self.provider_priors[provider].get(source_term, {})
            if canonical_term in provider_dist:
                base_prior = provider_dist[canonical_term]

        # Adjust for category compatibility
        if source_category and canonical_category:
            cat_idx = {'revenue': 0, 'expense': 1, 'asset': 2, 'liability': 3, 'equity': 4}
            if source_category in cat_idx and canonical_category in cat_idx:
                compat = self.category_compatibility[source_category][cat_idx[canonical_category]]
                base_prior *= compat

        return base_prior
```

#### Calibrated Likelihood Model

```python
class CalibratedLikelihoodModel:
    """
    Calibrate raw scores to P(score | match) and P(score | no_match)
    using labeled training data.
    """

    def __init__(self, training_data: pd.DataFrame):
        """
        training_data columns:
          - source_term, canonical_term
          - is_match (ground truth: 0 or 1)
          - embedding_similarity
          - string_similarity
          - rule_score
          - llm_confidence
        """
        self.calibrators = {}

        for method in ['embedding', 'string', 'rule', 'llm']:
            score_col = f'{method}_similarity' if method != 'llm' else 'llm_confidence'

            # Separate scores by match/no-match
            match_scores = training_data[training_data['is_match'] == 1][score_col]
            no_match_scores = training_data[training_data['is_match'] == 0][score_col]

            # Fit kernel density estimators
            from sklearn.neighbors import KernelDensity

            self.calibrators[method] = {
                'match_kde': KernelDensity(bandwidth=0.05).fit(match_scores.values.reshape(-1, 1)),
                'no_match_kde': KernelDensity(bandwidth=0.05).fit(no_match_scores.values.reshape(-1, 1)),
                'match_prior': len(match_scores) / len(training_data),
            }

    def likelihood_ratio(self, method: str, score: float) -> float:
        """
        Compute likelihood ratio: P(score | match) / P(score | no_match)
        """
        cal = self.calibrators[method]

        # Log-likelihoods from KDE
        log_p_match = cal['match_kde'].score_samples([[score]])[0]
        log_p_no_match = cal['no_match_kde'].score_samples([[score]])[0]

        # Convert to likelihood ratio
        import numpy as np
        lr = np.exp(log_p_match - log_p_no_match)

        # Clip to avoid numerical issues
        return np.clip(lr, 0.01, 100)

    def calibrated_probability(self, method: str, score: float) -> float:
        """
        Convert raw score to P(match | score) using Bayes' rule.
        """
        cal = self.calibrators[method]
        prior = cal['match_prior']

        lr = self.likelihood_ratio(method, score)

        # Bayes: P(match|score) = P(score|match) * P(match) / P(score)
        #                       = lr * prior / (lr * prior + 1 * (1-prior))
        posterior = (lr * prior) / (lr * prior + (1 - prior))

        return posterior
```

#### Full Bayesian Combination with Priors

```python
def bayesian_entity_resolution(
    source_term: dict,
    canonical_candidates: list,
    method_scores: dict,
    prior_model: InformedPriorModel,
    likelihood_model: CalibratedLikelihoodModel
) -> dict:
    """
    Full Bayesian entity resolution combining:
    - Informative priors (provider patterns, category compatibility)
    - Calibrated likelihoods from multiple methods
    - Proper uncertainty propagation

    Args:
        source_term: {provider, field_name, category, ...}
        canonical_candidates: List of candidate canonical terms
        method_scores: {method: {canonical_term: raw_score}}
        prior_model: Provides P(canonical | source context)
        likelihood_model: Converts raw scores to calibrated likelihoods

    Returns:
        {canonical_term: {
            'posterior': P(match | all evidence),
            'prior': prior probability,
            'likelihood_components': {method: contribution},
            'uncertainty': confidence interval
        }}
    """
    results = {}

    for canonical in canonical_candidates:
        # 1. Get prior
        prior = prior_model.get_prior(
            source_term=source_term['field_name'],
            canonical_term=canonical['term_name'],
            provider=source_term['provider'],
            source_category=source_term.get('category'),
            canonical_category=canonical.get('category')
        )

        # 2. Compute likelihood ratios for each method
        log_likelihood_ratio = 0
        likelihood_components = {}

        for method, scores in method_scores.items():
            if canonical['term_name'] in scores:
                raw_score = scores[canonical['term_name']]
                lr = likelihood_model.likelihood_ratio(method, raw_score)
                log_likelihood_ratio += np.log(lr)
                likelihood_components[method] = {
                    'raw_score': raw_score,
                    'likelihood_ratio': lr,
                    'contribution': np.log(lr)
                }

        # 3. Compute posterior odds
        prior_odds = prior / (1 - prior) if prior < 1 else 1e6
        posterior_odds = prior_odds * np.exp(log_likelihood_ratio)
        posterior = posterior_odds / (1 + posterior_odds)

        # 4. Compute uncertainty (using method agreement as proxy)
        # High agreement = low uncertainty
        method_posteriors = [
            likelihood_model.calibrated_probability(m, method_scores[m].get(canonical['term_name'], 0))
            for m in method_scores if canonical['term_name'] in method_scores.get(m, {})
        ]
        if method_posteriors:
            uncertainty = np.std(method_posteriors)
        else:
            uncertainty = 0.5  # Maximum uncertainty

        results[canonical['term_name']] = {
            'posterior': posterior,
            'prior': prior,
            'log_likelihood_ratio': log_likelihood_ratio,
            'likelihood_components': likelihood_components,
            'uncertainty': uncertainty,
            'confidence_interval': (
                max(0, posterior - 1.96 * uncertainty),
                min(1, posterior + 1.96 * uncertainty)
            )
        }

    # Normalize posteriors to sum to 1
    total = sum(r['posterior'] for r in results.values())
    if total > 0:
        for term in results:
            results[term]['posterior_normalized'] = results[term]['posterior'] / total

    return results
```

---

### The Problem

Different data sources use different terminology for the same accounting concepts:

```
Alpha Vantage API          Chicago Budget Portal       Generic Municipality
─────────────────          ─────────────────────       ────────────────────
total_revenue              APPROPRIATION               BUDGET_AMT
cost_of_revenue            EXPENDITURE                 ACTUAL_SPENDING
operating_income           PERSONNEL SERVICES          SALARY_EXPENSE
net_income                 CONTRACTUAL SERVICES        CONTRACTED_SVCS
```

These need to map to standard account codes in `accounts.dim_account`.

### Mapping Strategies (Layered Approach)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: Deterministic Lookup (Fast, 100% confidence)                  │
│                                                                         │
│  Known mappings in mapping table → Direct assignment                    │
│  "total_revenue" → 4000, "net_income" → 4900                           │
└─────────────────────────────────────────────────────────────────────────┘
                    │ No match
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: Rule-Based Patterns (Fast, High confidence)                   │
│                                                                         │
│  Regex/keyword patterns → Candidate accounts                            │
│  *revenue* → 4xxx, *expense*|*cost* → 5xxx-6xxx                        │
└─────────────────────────────────────────────────────────────────────────┘
                    │ No match or ambiguous
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: Embedding Similarity (Moderate speed, Good confidence)        │
│                                                                         │
│  Vector similarity between source field and account descriptions        │
│  "PERSONNEL SERVICES" ≈ "Salaries and Wages" (cosine: 0.87)            │
└─────────────────────────────────────────────────────────────────────────┘
                    │ Low confidence (< threshold)
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: LLM Classification (Slow, High accuracy for edge cases)       │
│                                                                         │
│  Claude/GPT classifies ambiguous items with context                     │
│  "Given these account categories, classify 'CONTRACTUAL SERVICES'..."   │
└─────────────────────────────────────────────────────────────────────────┘
                    │ Still uncertain
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 5: Human Review Queue                                            │
│                                                                         │
│  Flag for manual review, learn from corrections                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Implementation: Account Mapping Table

New table in the `accounts` foundation model:

```yaml
# In domains/foundation/accounts.md

tables:
  dim_account:
    # ... existing schema ...

  dim_account_mapping:
    type: dimension
    description: "Maps source field names to standard accounts"
    primary_key: [mapping_id]
    unique_key: [source_provider, source_field]
    tags: [dim, mapping, crosswalk]

    schema:
      - [mapping_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(source_provider, '_', source_field)))"}]
      - [source_provider, string, false, "Provider (alpha_vantage, chicago, etc.)"]
      - [source_field, string, false, "Original field name from source"]
      - [source_description, string, true, "Description from source (if available)"]
      - [account_id, integer, false, "FK to standard account", {fk: dim_account.account_id}]
      - [confidence, double, false, "Mapping confidence (0-1)", {default: 1.0}]
      - [mapping_method, string, false, "How mapped", {enum: [manual, rule, embedding, llm, human_review]}]
      - [embedding_vector, binary, true, "Cached embedding for source field"]
      - [verified, boolean, false, "Human verified", {default: false}]
      - [created_at, timestamp, false, "When mapping created"]
      - [verified_at, timestamp, true, "When verified"]
      - [verified_by, string, true, "Who verified"]

    measures:
      - [mapping_count, count_distinct, mapping_id, "Total mappings"]
      - [verified_pct, expression, "AVG(CASE WHEN verified THEN 1.0 ELSE 0.0 END) * 100", "Verified %"]
      - [low_confidence, expression, "SUM(CASE WHEN confidence < 0.8 THEN 1 ELSE 0 END)", "Low confidence"]

edges:
  - [mapping_to_account, dim_account_mapping, dim_account, account_id=account_id, many_to_one]
```

### Embedding-Based Matching

#### 1. Pre-compute Account Embeddings

```python
# scripts/seed/seed_account_embeddings.py

from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')  # Fast, good for short text

def embed_accounts(accounts_df):
    """Generate embeddings for standard account descriptions."""
    # Combine name + description for richer embedding
    texts = accounts_df.apply(
        lambda r: f"{r['account_name']}: {r['account_description'] or ''}",
        axis=1
    )
    embeddings = model.encode(texts.tolist())
    return embeddings

# Store in dim_account.embedding_vector or separate table
```

#### 2. Match Incoming Fields

```python
# de_funk/pipelines/mapping/account_matcher.py

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

class AccountMatcher:
    def __init__(self, account_embeddings, account_ids):
        self.account_embeddings = account_embeddings  # (N, 384)
        self.account_ids = account_ids
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def match(self, source_field: str, source_description: str = None) -> dict:
        """Find best matching account for a source field."""

        # Combine field name and description
        text = source_field
        if source_description:
            text = f"{source_field}: {source_description}"

        # Embed the source field
        source_embedding = self.model.encode([text])[0]

        # Compute similarity to all accounts
        similarities = cosine_similarity(
            [source_embedding],
            self.account_embeddings
        )[0]

        # Get top matches
        top_indices = np.argsort(similarities)[::-1][:5]

        return {
            'best_match': {
                'account_id': self.account_ids[top_indices[0]],
                'confidence': float(similarities[top_indices[0]]),
            },
            'alternatives': [
                {
                    'account_id': self.account_ids[i],
                    'confidence': float(similarities[i]),
                }
                for i in top_indices[1:]
            ]
        }
```

#### 3. Example Matches

```
Source Field                    Best Match                      Confidence
────────────────────────────────────────────────────────────────────────────
"PERSONNEL SERVICES"         → 6100 (Salaries and Wages)         0.89
"CONTRACTUAL SERVICES"       → 6200 (Contracted Services)        0.85
"TRAVEL"                     → 6310 (Travel Expense)             0.92
"COMMODITIES"                → 6400 (Supplies and Materials)     0.71  ⚠️
"EQUIPMENT"                  → 1520 (Equipment - Fixed Asset)    0.83
"SPECIFIC ITEM/CONTINGENCY"  → 6900 (Other Operating Expense)    0.45  ⚠️ → Human review
```

### LLM Classification (Layer 4)

For low-confidence matches, use Claude to classify:

```python
# de_funk/pipelines/mapping/llm_classifier.py

from anthropic import Anthropic

CLASSIFICATION_PROMPT = """
You are classifying budget line items into a standard chart of accounts.

Standard Account Categories:
1000-1999: Assets
2000-2999: Liabilities
3000-3999: Equity/Fund Balance
4000-4999: Revenue
5000-5999: Cost of Goods/Services
6000-6999: Operating Expenses
  - 6100: Salaries and Wages
  - 6200: Contracted Services
  - 6300: Travel and Training
  - 6400: Supplies and Materials
  - 6500: Utilities
  - 6600: Rent and Occupancy
  - 6700: Insurance
  - 6800: Depreciation
  - 6900: Other Operating
7000-7999: Other Income/Expense
8000-8999: Taxes

Source: {provider}
Field Name: {field_name}
Description: {description}
Sample Values: {sample_values}

Which account code (4-digit) best matches this field?
Respond with JSON: {{"account_code": "XXXX", "confidence": 0.X, "reasoning": "..."}}
"""

def classify_with_llm(field_name, description=None, sample_values=None, provider=None):
    client = Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": CLASSIFICATION_PROMPT.format(
                provider=provider or "unknown",
                field_name=field_name,
                description=description or "N/A",
                sample_values=sample_values or "N/A"
            )
        }]
    )
    return json.loads(response.content[0].text)
```

### Pipeline Integration

The account mapping happens in the Bronze → Silver transform:

```yaml
# domains/municipal/city_finance.md

tables:
  fact_account_balance:
    schema:
      # account_id is DERIVED via mapping lookup, not direct from source
      - [account_id, integer, false, "FK to accounts", {
          derive: "lookup_account_id(source_provider, source_field_name)",
          fk: accounts.dim_account.account_id
        }]
```

**Build-time resolution:**

```python
# de_funk/pipelines/transforms/account_resolver.py

def resolve_account_ids(df, provider: str, field_mapping: dict):
    """
    Transform wide source data into normalized account balances.

    Args:
        df: Source DataFrame with columns like PERSONNEL_SERVICES, TRAVEL, etc.
        provider: Source provider name
        field_mapping: Dict of {source_field: account_id}

    Returns:
        Normalized DataFrame with [entity_id, account_id, period, balance]
    """
    # Unpivot wide to long
    value_cols = [c for c in df.columns if c in field_mapping]

    melted = df.melt(
        id_vars=['department_code', 'fiscal_year'],
        value_vars=value_cols,
        var_name='source_field',
        value_name='balance'
    )

    # Map to account_id
    melted['account_id'] = melted['source_field'].map(field_mapping)

    return melted
```

### Mapping Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         NEW DATA SOURCE ONBOARDING                       │
└─────────────────────────────────────────────────────────────────────────┘

1. DISCOVER: List all unique field names from source
   └─→ SELECT DISTINCT column_name FROM bronze.{provider}.{table}

2. MATCH: Run through mapping layers
   └─→ python -m scripts.mapping.generate_mappings --provider chicago

3. REVIEW: Human reviews low-confidence mappings
   └─→ Generates review CSV with suggested mappings
   └─→ Analyst approves/corrects in UI or spreadsheet

4. IMPORT: Load verified mappings
   └─→ python -m scripts.mapping.import_mappings --file mappings.csv

5. BUILD: Normal Silver build uses mappings
   └─→ python -m scripts.build.build_models --models city_finance
```

### Seed Script for Mappings

```bash
# Generate initial mappings for a new provider
python -m scripts.mapping.generate_mappings \
  --provider chicago \
  --confidence-threshold 0.8 \
  --use-llm-fallback \
  --output mappings/chicago_draft.csv

# After human review, import verified mappings
python -m scripts.mapping.import_mappings \
  --file mappings/chicago_verified.csv \
  --mark-verified
```

### Confidence Combination: Multi-Method Fusion

When multiple methods produce candidate matches, we need to combine their confidence scores intelligently.

#### The Problem

Each method produces different types of "confidence":

| Method | Score Type | Range | Meaning |
|--------|-----------|-------|---------|
| Rule-based | Binary match | 0 or 1 | Pattern matched or not |
| Embedding | Cosine similarity | [-1, 1] | Semantic similarity |
| LLM | Self-reported | 0-1 | Model's stated confidence |

These aren't directly comparable - cosine similarity of 0.8 ≠ LLM confidence of 0.8.

#### Calibration: Converting to Probabilities

First, calibrate each method's raw scores to true probabilities P(correct | score).

**Embedding Calibration** (via held-out validation set):

```python
# Empirical calibration from labeled data
# "Given cosine similarity X, what fraction are actually correct?"

def calibrate_embedding_scores(similarity_scores, ground_truth_correct):
    """
    Build calibration curve from labeled examples.

    Returns function: raw_similarity → P(correct)
    """
    from sklearn.isotonic import IsotonicRegression

    # Isotonic regression ensures monotonicity
    calibrator = IsotonicRegression(out_of_bounds='clip')
    calibrator.fit(similarity_scores, ground_truth_correct)

    return calibrator.predict

# Example calibration curve:
# similarity 0.5 → P(correct) = 0.20
# similarity 0.7 → P(correct) = 0.55
# similarity 0.8 → P(correct) = 0.75
# similarity 0.9 → P(correct) = 0.92
```

**LLM Calibration** (LLMs are often overconfident):

```python
# Platt scaling for LLM confidence
def calibrate_llm_confidence(llm_confidences, ground_truth_correct):
    """
    LLMs tend to be overconfident. Apply Platt scaling.

    P(correct) = 1 / (1 + exp(A * llm_conf + B))
    """
    from sklearn.linear_model import LogisticRegression

    calibrator = LogisticRegression()
    calibrator.fit(llm_confidences.reshape(-1, 1), ground_truth_correct)

    def calibrated_prob(raw_conf):
        return calibrator.predict_proba([[raw_conf]])[0, 1]

    return calibrated_prob

# Example: LLM says 0.9 → actual P(correct) = 0.78
```

#### Method 1: Bayesian Combination

Treat each method as an independent "expert" and combine using Bayes' rule.

```python
def bayesian_combine(method_probs: dict, prior: float = 0.5) -> dict:
    """
    Combine calibrated probabilities from multiple methods.

    Args:
        method_probs: {method_name: {account_id: P(correct)}}
        prior: Prior probability of any account being correct

    Returns:
        {account_id: P(correct | all evidence)}
    """
    from collections import defaultdict

    # Collect all candidate accounts
    all_accounts = set()
    for probs in method_probs.values():
        all_accounts.update(probs.keys())

    posteriors = {}

    for account_id in all_accounts:
        # Start with prior odds
        odds = prior / (1 - prior)

        # Multiply by likelihood ratio from each method
        for method_name, probs in method_probs.items():
            if account_id in probs:
                p = probs[account_id]
                # Likelihood ratio: P(score | correct) / P(score | incorrect)
                # Approximated as p / (1 - p) when calibrated
                if p > 0 and p < 1:
                    odds *= (p / (1 - p))

        # Convert back to probability
        posteriors[account_id] = odds / (1 + odds)

    # Normalize to sum to 1 (accounts are mutually exclusive)
    total = sum(posteriors.values())
    if total > 0:
        posteriors = {k: v / total for k, v in posteriors.items()}

    return posteriors
```

**Example:**

```
Source field: "PERSONNEL SERVICES"

Method Outputs (raw):
  Embedding: {6100: 0.89, 6200: 0.72, 6900: 0.45}
  Rule:      {6100: 1.0}  # Pattern matched "personnel"
  LLM:       {6100: 0.85, 6200: 0.10}

Calibrated Probabilities:
  Embedding: {6100: 0.75, 6200: 0.52, 6900: 0.22}
  Rule:      {6100: 0.95}  # Rule matches are very reliable
  LLM:       {6100: 0.70, 6200: 0.08}

Bayesian Posterior:
  6100: 0.97  ← Strong agreement across methods
  6200: 0.02
  6900: 0.01
```

#### Method 2: Weighted Ensemble

Simpler approach - weighted average of calibrated scores.

```python
def weighted_ensemble(method_probs: dict, weights: dict) -> dict:
    """
    Weighted average of calibrated probabilities.

    Args:
        method_probs: {method_name: {account_id: P(correct)}}
        weights: {method_name: weight} (should sum to 1)

    Returns:
        {account_id: combined_score}
    """
    combined = defaultdict(float)

    for method_name, probs in method_probs.items():
        w = weights.get(method_name, 0)
        for account_id, p in probs.items():
            combined[account_id] += w * p

    return dict(combined)

# Weights based on method reliability
WEIGHTS = {
    'rule': 0.40,      # High precision when matches
    'embedding': 0.35, # Good general coverage
    'llm': 0.25,       # Good for edge cases
}
```

#### Method 3: Dempster-Shafer Theory

Handles uncertainty better than pure Bayesian when methods may be unreliable.

```python
def dempster_shafer_combine(mass_functions: list) -> dict:
    """
    Combine evidence using Dempster-Shafer theory.

    Each mass function assigns belief to subsets of accounts.
    Handles "I don't know" better than Bayesian.

    Args:
        mass_functions: List of {frozenset(account_ids): mass}

    Returns:
        Combined belief for each account
    """
    from itertools import combinations

    def combine_two(m1, m2):
        """Dempster's rule of combination."""
        combined = defaultdict(float)
        conflict = 0

        for a1, mass1 in m1.items():
            for a2, mass2 in m2.items():
                intersection = a1 & a2
                if intersection:
                    combined[intersection] += mass1 * mass2
                else:
                    conflict += mass1 * mass2

        # Normalize by (1 - conflict)
        if conflict < 1:
            normalization = 1 / (1 - conflict)
            combined = {k: v * normalization for k, v in combined.items()}

        return dict(combined)

    # Combine all mass functions pairwise
    result = mass_functions[0]
    for mf in mass_functions[1:]:
        result = combine_two(result, mf)

    return result
```

**When to use Dempster-Shafer:**
- Methods have different "frames of discernment" (know about different accounts)
- Want to explicitly model "uncertain" vs "conflicting"
- High conflict between methods should reduce overall confidence

#### Method 4: Learned Combination (Meta-Model)

Train a model to combine signals optimally.

```python
def train_meta_combiner(training_data):
    """
    Train a model to predict correct account from method outputs.

    Features:
      - embedding_similarity_top1
      - embedding_similarity_top2
      - embedding_gap (top1 - top2)
      - rule_matched (binary)
      - llm_confidence
      - llm_top2_gap
      - source_field_length
      - has_description (binary)

    Target: correct_account_id
    """
    from sklearn.ensemble import GradientBoostingClassifier

    X = []  # Feature vectors
    y = []  # Correct account IDs

    for sample in training_data:
        features = [
            sample['embedding_top1_sim'],
            sample['embedding_top2_sim'],
            sample['embedding_top1_sim'] - sample['embedding_top2_sim'],
            1 if sample['rule_matched'] else 0,
            sample['llm_confidence'],
            sample['llm_top1_conf'] - sample['llm_top2_conf'],
            len(sample['source_field']),
            1 if sample['has_description'] else 0,
        ]
        X.append(features)
        y.append(sample['correct_account_id'])

    model = GradientBoostingClassifier(n_estimators=100)
    model.fit(X, y)

    return model

# At inference time:
def predict_with_meta_model(model, method_outputs):
    features = extract_features(method_outputs)
    probs = model.predict_proba([features])[0]
    account_ids = model.classes_

    return {aid: p for aid, p in zip(account_ids, probs)}
```

#### Confidence Thresholds and Actions

After combining, decide action based on final confidence:

```python
def decide_action(combined_probs: dict) -> tuple:
    """
    Decide what to do based on combined confidence.

    Returns:
        (action, account_id, confidence)
    """
    sorted_probs = sorted(combined_probs.items(), key=lambda x: -x[1])
    top_account, top_conf = sorted_probs[0]
    second_conf = sorted_probs[1][1] if len(sorted_probs) > 1 else 0

    gap = top_conf - second_conf

    # Decision rules
    if top_conf >= 0.90:
        return ('auto_assign', top_account, top_conf)

    elif top_conf >= 0.75 and gap >= 0.20:
        # High confidence AND clear winner
        return ('auto_assign', top_account, top_conf)

    elif top_conf >= 0.60:
        # Moderate confidence - assign but flag for review
        return ('assign_flag_review', top_account, top_conf)

    elif top_conf >= 0.40:
        # Low confidence - escalate to LLM if not already used
        return ('escalate_llm', top_account, top_conf)

    else:
        # Very low confidence - human review required
        return ('human_review', top_account, top_conf)
```

#### Full Pipeline with Confidence Tracking

```python
class AccountMappingPipeline:
    def __init__(self, config):
        self.rule_matcher = RuleMatcher(config['rules'])
        self.embedding_matcher = EmbeddingMatcher(config['embedding'])
        self.llm_classifier = LLMClassifier(config['llm'])
        self.calibrators = load_calibrators(config['calibration'])
        self.combiner = config.get('combiner', 'bayesian')

    def map_field(self, source_field: str, source_description: str = None,
                  provider: str = None) -> MappingResult:
        """
        Map a source field to standard account with confidence.
        """
        method_outputs = {}

        # Layer 1: Exact lookup
        exact = self.lookup_exact(provider, source_field)
        if exact:
            return MappingResult(
                account_id=exact['account_id'],
                confidence=1.0,
                method='lookup',
                alternatives=[]
            )

        # Layer 2: Rules
        rule_result = self.rule_matcher.match(source_field)
        if rule_result:
            method_outputs['rule'] = self.calibrators['rule'](rule_result)

        # Layer 3: Embedding
        emb_result = self.embedding_matcher.match(source_field, source_description)
        method_outputs['embedding'] = self.calibrators['embedding'](emb_result)

        # Combine and decide
        if self.combiner == 'bayesian':
            combined = bayesian_combine(method_outputs)
        elif self.combiner == 'weighted':
            combined = weighted_ensemble(method_outputs, WEIGHTS)

        action, account_id, confidence = decide_action(combined)

        # Layer 4: LLM if needed
        if action == 'escalate_llm':
            llm_result = self.llm_classifier.classify(
                source_field, source_description, provider
            )
            method_outputs['llm'] = self.calibrators['llm'](llm_result)

            # Recombine with LLM evidence
            combined = bayesian_combine(method_outputs)
            action, account_id, confidence = decide_action(combined)

        return MappingResult(
            account_id=account_id,
            confidence=confidence,
            method=action,
            method_scores=method_outputs,
            combined_probs=combined,
            alternatives=get_alternatives(combined, top_n=3)
        )
```

#### Monitoring and Feedback Loop

Track confidence distributions to detect drift:

```sql
-- Daily confidence distribution
SELECT
    DATE(created_at) as date,
    mapping_method,
    COUNT(*) as total_mappings,
    AVG(confidence) as avg_confidence,
    SUM(CASE WHEN confidence < 0.6 THEN 1 ELSE 0 END) as low_confidence_count,
    SUM(CASE WHEN verified THEN 1 ELSE 0 END) as verified_count,
    AVG(CASE WHEN verified THEN
        CASE WHEN verified_account_id = account_id THEN 1.0 ELSE 0.0 END
    END) as accuracy_when_verified
FROM dim_account_mapping
GROUP BY DATE(created_at), mapping_method
ORDER BY date DESC;
```

**Alerts:**
- Average confidence drops below threshold → New terminology in source?
- Verified accuracy drops → Calibration may need refresh
- High conflict rate (Dempster-Shafer) → Methods disagreeing, needs investigation

### Learning Loop

Over time, the mapping system improves:

```
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│  Human Correction │────▶│  Update Mapping   │────▶│  Retrain/Fine-tune│
│  "6200 not 6100"  │     │  Table + Verify   │     │  Embedding Model  │
└───────────────────┘     └───────────────────┘     └───────────────────┘
                                                            │
                                                            ▼
                                                    ┌───────────────────┐
                                                    │  Better Future    │
                                                    │  Matches          │
                                                    └───────────────────┘
```

**Fine-tuning options:**
1. **Contrastive learning**: Pull correct pairs closer, push incorrect apart
2. **Few-shot examples**: Add verified mappings to LLM prompt
3. **Custom embedding model**: Fine-tune on accounting terminology

### Configuration

```yaml
# configs/mapping.yaml

account_mapping:
  # Layer 1: Lookup table
  lookup_table: accounts.dim_account_mapping

  # Layer 2: Rule patterns
  rules:
    - pattern: "(?i).*revenue.*"
      account_range: [4000, 4999]
    - pattern: "(?i).*salary.*|.*wage.*|.*personnel.*"
      account_code: 6100
    - pattern: "(?i).*contract.*|.*professional.*"
      account_code: 6200
    - pattern: "(?i).*travel.*"
      account_code: 6310
    - pattern: "(?i).*supply.*|.*material.*|.*commodit.*"
      account_code: 6400

  # Layer 3: Embedding
  embedding:
    model: "all-MiniLM-L6-v2"
    threshold: 0.75
    cache_embeddings: true

  # Layer 4: LLM
  llm:
    enabled: true
    model: "claude-sonnet-4-20250514"
    threshold: 0.6  # Use LLM if embedding confidence below this

  # Layer 5: Human review
  review:
    queue_table: accounts.mapping_review_queue
    notify_email: data-team@company.com
```

---

## Summary

### Key Architectural Decisions

1. **Foundation models** (`temporal`, `accounts`) are Tier 0 - seeded, no external dependencies
2. **Chart of Accounts is shared** across corporate, municipal, and fund accounting
3. **Entity models** (company, municipality) contain only entity attributes
4. **Financial data** is normalized to account balances, not denormalized statements
5. **Statement views** (balance sheet, income statement) are derived from account balances
6. **Securities** use a different pattern (prices, not account balances)

### Benefits

| Benefit | How Achieved |
|---------|--------------|
| No column duplication | Unified `schema:` with `{from:}` |
| Clear data lineage | `{from: provider.table.field}` in schema |
| Multi-domain reuse | Foundation `accounts` shared by all |
| Flexible financial analysis | Account-level granularity |
| Easier extensibility | Add accounts without schema changes |
| Simpler inheritance | `extends: [list]` with clear merge rules |

---

## ML/Generated Models (Tier 4)

Generated models are produced by algorithms (ML, statistical) rather than ingested from external APIs. They consume Silver layer data and produce new fact tables.

### Model Type Classification

| Type | Tier | Data Source | Build Trigger | Examples |
|------|------|-------------|---------------|----------|
| **foundation** | 0 | Seeded/Generated | `{derive: "seeded"}` | temporal, accounts |
| **entity** | 1 | External API | `{from: ...}` | company, municipality |
| **fact** | 2 | External API | `{from: ...}` | financials, stocks, city_finance |
| **view** | 3 | Silver tables | `build_sql:` or `{derive: "SELECT..."}` | financial_statements |
| **ml/generated** | 4 | Silver + ML | `generated: true` + `ml_models:` | forecast, account_matcher |

### Key Characteristics of Generated Models

```yaml
# Generated model indicators:
type: domain-model
generated: true              # NOT from bronze

depends_on:
  - source_model             # Consumes Silver data

# NO data_sources section
# data_sources: ❌           # Does not read from Bronze

# Has ML configuration
ml_models:
  model_name:
    type: algorithm_type
    params: {...}

tables:
  fact_output:
    type: fact
    generated: true          # Produced by ML
```

### Example: Balance Forecast Model

Forecasting account balances using the same ML patterns as securities forecasting:

```yaml
---
type: domain-model
model: balance_forecast
version: 4.0
description: "Account balance forecasting for financial planning"
tags: [forecast, ml, financials]
generated: true

depends_on:
  - temporal
  - accounts
  - financials    # Source: fact_account_balance

# NO data_sources - generated from Silver

storage:
  format: delta
  root: ml/balance_forecast

build:
  partitions: [forecast_date_id]
  sort_by: [account_id, company_id]

# ML Model Configuration
ml_models:
  arima_quarterly:
    type: arima
    target: [balance]
    lookback_periods: 12      # 12 quarters
    forecast_horizon: 4       # 4 quarters ahead
    seasonality: 4            # Quarterly seasonality

  prophet_annual:
    type: prophet
    target: [balance]
    lookback_periods: 20      # 20 quarters (5 years)
    forecast_horizon: 8       # 2 years ahead
    seasonality_mode: multiplicative

  linear_trend:
    type: linear_regression
    target: [balance]
    features: [period_index, is_q4, is_fiscal_year_end]
    lookback_periods: 8

tables:
  fact_forecast_balance:
    type: fact
    description: "Forecasted account balances"
    generated: true
    primary_key: [forecast_balance_id]
    partition_by: [forecast_date_id]

    schema:
      # Keys
      - [forecast_balance_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(...)))"}]
      - [company_id, integer, false, "FK to company", {fk: company.dim_company.company_id}]
      - [account_id, integer, false, "FK to accounts", {fk: accounts.dim_account.account_id}]
      - [forecast_date_id, integer, false, "When forecast made", {fk: temporal.dim_calendar.date_id}]
      - [prediction_date_id, integer, false, "Period being predicted", {fk: temporal.dim_calendar.date_id}]

      # Forecast attributes
      - [model_name, string, false, "Model (arima_quarterly, prophet_annual, etc.)"]
      - [horizon_periods, integer, false, "Periods ahead"]
      - [report_type, string, false, "Period type", {enum: [quarterly, annual]}]

      # Predictions
      - [predicted_balance, double, false, "Predicted balance"]
      - [lower_bound, double, true, "Lower confidence interval"]
      - [upper_bound, double, true, "Upper confidence interval"]
      - [confidence_level, double, true, "Confidence level", {default: 0.95}]

      # Actuals (populated after period ends)
      - [actual_balance, double, true, "Actual balance (for accuracy tracking)"]
      - [forecast_error, double, true, "Predicted - Actual", {derive: "predicted_balance - actual_balance"}]
      - [error_pct, double, true, "Error %", {derive: "ABS(forecast_error) / NULLIF(ABS(actual_balance), 0)"}]

    measures:
      - [forecast_count, count_distinct, forecast_balance_id, "Total forecasts"]
      - [avg_predicted, avg, predicted_balance, "Avg predicted", {format: "$#,##0.00M"}]
      - [mape, expression, "AVG(ABS(error_pct)) * 100", "MAPE %", {format: "#,##0.0%"}]

  fact_forecast_statement:
    type: fact
    description: "Forecasted financial statement line items (aggregated from account forecasts)"
    generated: true
    primary_key: [forecast_statement_id]

    schema:
      - [forecast_statement_id, integer, false, "PK"]
      - [company_id, integer, false, "FK", {fk: company.dim_company.company_id}]
      - [prediction_date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [model_name, string, false, "Model used"]

      # Aggregated predictions (from account-level forecasts)
      - [predicted_revenue, double, true, "Total revenue", {derive: "SUM WHERE account_type='revenue'"}]
      - [predicted_expenses, double, true, "Total expenses", {derive: "SUM WHERE account_type='expense'"}]
      - [predicted_net_income, double, true, "Net income", {derive: "predicted_revenue - predicted_expenses"}]
      - [predicted_total_assets, double, true, "Total assets", {derive: "SUM WHERE account_type='asset'"}]
      - [predicted_total_liabilities, double, true, "Total liabilities", {derive: "SUM WHERE account_type='liability'"}]

edges:
  - [forecast_to_account, fact_forecast_balance, accounts.dim_account, account_id=account_id, many_to_one]
  - [forecast_to_company, fact_forecast_balance, company.dim_company, company_id=company_id, many_to_one]

metadata:
  domain: ml
  owner: data_science
  sla_hours: 24

status: active
---

## Balance Forecast Model

ML-powered forecasting of account balances for financial planning and analysis.

### Use Cases

1. **Revenue forecasting** - Predict future revenue by account
2. **Expense planning** - Project operating costs
3. **Cash flow projection** - Forecast cash account balances
4. **Budget variance** - Compare forecasts to budgets

### Query: Projected Income Statement

```sql
SELECT
    c.company_name,
    cal.fiscal_quarter,
    cal.fiscal_year,
    f.model_name,
    f.predicted_revenue,
    f.predicted_expenses,
    f.predicted_net_income,
    f.predicted_net_income / NULLIF(f.predicted_revenue, 0) as predicted_margin
FROM fact_forecast_statement f
JOIN company.dim_company c ON f.company_id = c.company_id
JOIN temporal.dim_calendar cal ON f.prediction_date_id = cal.date_id
WHERE f.forecast_date_id = (SELECT MAX(date_id) FROM temporal.dim_calendar WHERE calendar_date <= CURRENT_DATE)
  AND c.ticker IN ('AAPL', 'MSFT', 'GOOGL')
ORDER BY c.ticker, cal.fiscal_year, cal.fiscal_quarter
```
```

### Example: Account Matcher Model

The semantic layer account mapping is itself an ML/generated model:

```yaml
---
type: domain-model
model: account_matcher
version: 4.0
description: "ML-assisted mapping of source terms to canonical accounts"
tags: [ml, mapping, semantic]
generated: true

depends_on:
  - accounts    # Consumes dim_source_term, dim_canonical_term

# NO data_sources - generated from semantic layer

storage:
  format: delta
  root: ml/account_matcher

ml_models:
  embedding_matcher:
    type: sentence_transformer
    model_name: all-MiniLM-L6-v2
    similarity_threshold: 0.75

  llm_classifier:
    type: llm
    model_name: claude-sonnet-4-20250514
    confidence_threshold: 0.85
    use_for: low_confidence_only

tables:
  # Output: Probabilistic mappings written to link_source_to_canonical
  # This model UPDATES the accounts foundation model's link table

metadata:
  domain: ml
  owner: data_engineering

status: active
---

## Account Matcher

ML-powered mapping of source terminology to standard Chart of Accounts.

### Pipeline

1. New source fields discovered → dim_source_term
2. Embeddings generated for source terms
3. Similarity matching against dim_canonical_term
4. Low confidence → LLM classification
5. Results → link_source_to_canonical with confidence scores
6. High confidence auto-approved, low confidence → human review
```

---

## Complete Model Hierarchy Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE v4.0 MODEL PARADIGM                             │
└─────────────────────────────────────────────────────────────────────────────────┘

TIER 0: FOUNDATION ─────────────────────────────────────────────────────────────────
│
│   temporal ──────────────────┬─────────────────── accounts
│   (calendar)                 │                    (CoA + semantic layer)
│                              │                    ├── dim_account
│                              │                    ├── dim_canonical_term
│                              │                    ├── dim_source_term
│                              │                    └── link tables
│
TIER 1: ENTITIES ───────────────────────────────────────────────────────────────────
│
│   company ───────────────────┬─────────────────── municipality ──── fund
│   (corporate entities)       │                    (gov entities)    (investment)
│   {from: alpha_vantage}      │                    {from: chicago}
│
TIER 2: FACTS ──────────────────────────────────────────────────────────────────────
│
│   ┌─── ACCOUNTING PATTERN ───────────────────────────────────────────────────┐
│   │                                                                          │
│   │   financials ────────────┬─── city_finance ────┬─── cook_county ── ...  │
│   │   (corporate)            │    (Chicago)        │    (tax data)          │
│   │   fact_account_balance   │    fact_account_bal │    fact_account_bal    │
│   │   source='av'            │    source='chi'     │    source='cook'       │
│   │                          │                     │                        │
│   │                          └─────────────────────┴────────────────────────│
│   │                                    ALL → accounts.dim_account            │
│   └──────────────────────────────────────────────────────────────────────────┘
│
│   ┌─── SECURITIES PATTERN ───────────────────────────────────────────────────┐
│   │                                                                          │
│   │   stocks ────────────────┬─── options ─────────┬─── etfs ─── futures    │
│   │   dim_security           │    dim_security     │    dim_security        │
│   │   fact_prices            │    fact_prices      │    fact_prices         │
│   │                          │    + greeks         │    + holdings          │
│   └──────────────────────────────────────────────────────────────────────────┘
│
TIER 3: VIEWS (Derived from Silver) ────────────────────────────────────────────────
│
│   financial_statements ──────┬─── municipal_reports ─── unified_ledger
│   view_balance_sheet         │    view_budget           (UNION of all
│   view_income_statement      │    view_cafr              fact_account_balance)
│   view_cash_flow             │
│
TIER 4: ML/GENERATED (Produced by algorithms) ──────────────────────────────────────
│
│   ┌─── SECURITIES FORECASTING ───────────────────────────────────────────────┐
│   │   forecast                                                               │
│   │   fact_forecast_price, fact_forecast_volume, fact_forecast_metrics       │
│   │   ml_models: arima, prophet, random_forest                               │
│   └──────────────────────────────────────────────────────────────────────────┘
│
│   ┌─── FINANCIAL FORECASTING ────────────────────────────────────────────────┐
│   │   balance_forecast                                                       │
│   │   fact_forecast_balance, fact_forecast_statement                         │
│   │   ml_models: arima_quarterly, prophet_annual, linear_trend               │
│   └──────────────────────────────────────────────────────────────────────────┘
│
│   ┌─── SEMANTIC MAPPING ─────────────────────────────────────────────────────┐
│   │   account_matcher                                                        │
│   │   → link_source_to_canonical (probabilistic mappings)                    │
│   │   ml_models: embedding_matcher, llm_classifier                           │
│   └──────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

```
External APIs ──→ Bronze ──→ TIER 2 Facts ──→ TIER 3 Views
                              ↓                    ↓
                         TIER 4 ML ←───────────────┘
                              ↓
                    Predictions/Mappings
```

### Model Build Order

```
1. temporal, accounts         (Tier 0 - seeded, no dependencies)
2. company, municipality      (Tier 1 - from Bronze, depends on T0)
3. financials, stocks, etc    (Tier 2 - from Bronze, depends on T0+T1)
4. financial_statements       (Tier 3 - from Silver, depends on T2)
5. forecast, balance_forecast (Tier 4 - ML on Silver, depends on T2/T3)
6. account_matcher            (Tier 4 - ML, can run anytime after T0)
```
