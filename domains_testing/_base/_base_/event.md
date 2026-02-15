---
type: domain-base
model: event
version: 1.0
description: "Root template for any timestamped occurrence - transaction, incident, measurement"

# CANONICAL FIELDS - the most fundamental attributes of any event
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [event_id, integer, nullable: false, description: "Surrogate primary key"]
  - [event_date, date, nullable: false, description: "When the event occurred"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar (YYYYMMDD)"]
  - [event_type, string, nullable: false, description: "Discriminator for what kind of event"]
  - [domain_source, string, nullable: false, description: "Which domain/organization produced this event"]
  - [source_id, string, nullable: false, description: "Original identifier from source system"]

tables:
  _fact_event:
    type: fact
    primary_key: [event_id]
    partition_by: [date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [event_id, integer, false, "PK - surrogate", {derived: "ABS(HASH(CONCAT(event_type, '_', source_id)))"}]
      - [date_id, integer, false, "FK to temporal.dim_calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(event_date, 'yyyyMMdd') AS INT)"}]
      - [event_type, string, false, "Discriminator"]
      - [domain_source, string, false, "Origin domain"]
      - [source_id, string, false, "Original ID from source"]
      - [event_date, date, false, "Event date"]

    measures:
      - [event_count, count_distinct, event_id, "Number of events", {format: "#,##0"}]

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [event_to_calendar, _fact_event, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]

domain: _base
tags: [base, template, event, root]
status: active
---

## Event Base Template

The most fundamental fact template. Every timestamped occurrence in the system is an event.

### What Extends This

| Template | event_type | Example source_id |
|----------|------------|-------------------|
| `_base.accounting.ledger_entry` | VENDOR_PAYMENT, PAYROLL, CONTRACT | voucher_number |
| `_base.accounting.financial_event` | BUDGET_APPROPRIATION, BUDGET_REVENUE | composite key |

### Key Design

All event PKs are integers: `ABS(HASH(CONCAT(event_type, '_', source_id)))`

The `event_type` prefix in the hash ensures uniqueness across unions of different source types.

### date_id Pattern

All facts FK to `temporal.dim_calendar` via integer `date_id` (YYYYMMDD format). Facts store `date_id`, not raw date columns, for join efficiency. The raw `event_date` is kept for derivation but should not be used for joins.
