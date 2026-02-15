---
type: reference
description: "Guide for domain-model configuration"
---

## domain-model Guide

A `domain-model` is a concrete implementation that maps source data to a canonical schema defined by a `domain-base`.

### Single-File vs Directory-as-Model

Models can be defined as a single markdown file or as a directory:

| Format | When to Use |
|--------|------------|
| **Single file** (`model.md`) | Simple models with 1-2 sources, <300 lines |
| **Directory** (`model/`) | Complex models with multiple sources, tables, and enrichments |

### Directory-as-Model Structure

```
models/{domain}/{entity}/{model}/
├── model.md            # type: domain-model — metadata, graph, build, measures
├── sources/
│   ├── source_a.md     # type: domain-model-source — aliases for one bronze endpoint
│   └── source_b.md
└── tables/
    ├── fact_*.md        # type: domain-model-table — fact table definitions
    └── dim_*.md         # type: domain-model-table — dimension definitions
```

**Auto-discovery:** The loader reads `model.md` first, then discovers all `sources/*.md` and `tables/*.md`. Sources declare `maps_to:` to indicate which fact table they feed; the loader groups and unions them automatically.

---

### model.md — Required Top-Level Keys

| Key | Type | Description |
|-----|------|-------------|
| `type` | string | Always `domain-model` |
| `model` | string | Model identifier (e.g., `chicago_finance`) |
| `version` | string | Semantic version |
| `description` | string | What this model provides |
| `extends` | string or list | Parent base template(s) |

### model.md — Optional Top-Level Keys

| Key | Type | Description |
|-----|------|-------------|
| `depends_on` | list | Build dependencies `[temporal, company]` |
| `storage` | object | Bronze/Silver path config |
| `graph` | object | Edge definitions (cross-cutting, lives here) |
| `build` | object | Build phases and ordering |
| `measures` | object | Model-level measure definitions |
| `federation` | object | Federation config |
| `metadata` | object | Ownership, SLA |
| `status` | string | `active`, `deprecated`, `draft` |

---

### domain-model-source

Each source file maps one bronze endpoint to a fact table's canonical schema.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `type` | string | Yes | Always `domain-model-source` |
| `source` | string | Yes | Source identifier (e.g., `payments`) |
| `maps_to` | string | Yes | Target fact table (e.g., `fact_ledger_entries`) |
| `from` | string | Yes | Bronze table reference |
| `entry_type` | string | If ledger | Discriminator value (e.g., `VENDOR_PAYMENT`) |
| `event_type` | string | If budget | Discriminator value (e.g., `APPROPRIATION`) |
| `domain_source` | string | Yes | Domain origin (e.g., `"'chicago'"`) |
| `aliases` | list | Yes | `[canonical_field, source_expression]` pairs |

```yaml
---
type: domain-model-source
source: payments
maps_to: fact_ledger_entries
from: bronze.payments
entry_type: VENDOR_PAYMENT
domain_source: "'chicago'"

# [canonical_field, source_expression]
aliases:
  - [source_id, voucher_number]
  - [payee, vendor_name]
  - [transaction_amount, amount]
---
```

**Adding a new source = dropping a new file in `sources/`.** No edits to model.md needed.

---

### domain-model-table

Each table file defines one fact or dimension table.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `type` | string | Yes | Always `domain-model-table` |
| `table` | string | Yes | Table name (e.g., `dim_vendor`) |
| `table_type` | string | Yes | `dimension` or `fact` |
| `extends` | string | No | Base template table (e.g., `_fact_ledger_entries`) |
| `from` | string | Yes* | Source: fact table name, bronze ref, or list |
| `transform` | string | No | `aggregate`, `distinct`, or omit |
| `group_by` | list | If aggregate | Columns to group by |
| `primary_key` | list | Yes | Primary key columns |
| `schema` | list | Yes* | `[column, type, nullable, description, {options}]` |
| `additional_schema` | list | No | Extra columns beyond inherited base |
| `enrich` | list | No | Enrichment from related fact tables |
| `measures` | list | No | Table-level measures |

*Facts that extend a base inherit schema; dimensions need explicit schema.

---

### Dimensions Derive from Facts (Design Principle)

Dimensions should aggregate from **canonicalized fact tables**, not from raw bronze:

```yaml
# CORRECT — uses canonical column names, gets richer data
from: fact_ledger_entries
group_by: [payee]              # canonical name
schema:
  - [total_payments, ..., {derived: "SUM(transaction_amount)"}]  # canonical name

# EXCEPTION — only when dimension needs source-specific columns
# not present in the canonical schema
from: bronze.contracts         # needs specification_number, procurement_type, etc.
```

**Why:** Alias mapping happens once (in the source). Dimensions use canonical names. Richer data (e.g., dim_vendor gets VENDOR_PAYMENT + CONTRACT entries).

**Build order:** Facts first (phase 1), dimensions second (phase 2). Hash-based surrogate keys are deterministic, so FK integrity works regardless of build order.

---

### The `enrich:` Section

Materialized columns added to a dimension at build time by joining to fact tables. These are **pre-computed and persisted** — not query-time measures.

```yaml
enrich:
  - from: fact_ledger_entries
    join: [department_id = org_unit_id]
    filter: "optional WHERE clause"        # optional
    # [column, type, nullable, description, {options}]
    columns:
      - [total_paid, "decimal(18,2)", true, "Actual spending", {derived: "SUM(transaction_amount)"}]

  - from: fact_budget_events
    join: [department_id = org_unit_id]
    filter: "event_type = 'APPROPRIATION'"
    columns:
      - [total_appropriated, "decimal(18,2)", true, "Budgeted amount", {derived: "SUM(amount)"}]

  - derived:    # computed from enriched columns (no additional join)
      - [budget_variance, "decimal(18,2)", true, "Budget minus actual", {derived: "total_appropriated - total_paid"}]
```

**Build phases with enrichment:**
```
Phase 1: Facts (union sources → canonical schema)
Phase 2: Base dimensions (aggregate from facts / load from bronze)
Phase 3: Enrichment (LEFT JOIN facts → dims, compute aggregates)
```

---

### Minimal Single-File Example

```yaml
---
type: domain-model
model: chicago_ledger
version: 1.0
description: "Chicago municipal ledger entries"
extends: _base.accounting.ledger_entry
depends_on: [temporal]

storage:
  format: delta
  bronze:
    provider: chicago
    tables:
      - [payments, chicago/chicago_payments]
  silver:
    root: storage/silver/chicago/ledger/
---
```
