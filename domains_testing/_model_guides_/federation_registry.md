---
type: reference
description: "Registry of federation implementations - which models extend each federated base"
---

## Federation Registry

Maps each federated base template to its known model implementations. This file is the single source of truth for federation membership — base templates remain pure structural definitions.

### How to Update

When adding a new model that extends a federated base, add it to the appropriate section below.

---

### Accounting — Ledger Entry

**Base**: `_base.accounting.ledger_entry`
**Union key**: `domain_source`
**Primary key**: `entry_id`

| Model | domain_source | Fact Table |
|-------|--------------|------------|
| `municipal/finance` | chicago | fact_ledger_entries |
| `corporate/finance` | — | (uses financial_statement instead) |

---

### Accounting — Financial Event

**Base**: `_base.accounting.financial_event`
**Union key**: `domain_source`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/finance` | chicago | fact_budget_events, fact_property_tax |
| `corporate/finance` | alpha_vantage | fact_financial_statements, fact_earnings |

---

### Public Safety — Crime

**Base**: `_base.public_safety.crime`
**Union key**: `domain_source`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/public_safety` | chicago | fact_crimes, fact_arrests |

---

### Operations — Service Request

**Base**: `_base.operations.service_request`
**Union key**: `domain_source`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/operations` | chicago | fact_service_requests |

---

### Regulatory — Inspection

**Base**: `_base.regulatory.inspection`
**Union key**: `domain_source`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/regulatory` | chicago | fact_food_inspections, fact_building_violations, fact_business_licenses |

---

### Housing — Permit

**Base**: `_base.housing.permit`
**Union key**: `domain_source`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/housing` | chicago | fact_building_permits |

---

### Transportation — Transit

**Base**: `_base.transportation.transit`
**Union key**: `domain_source`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/transportation` | chicago | fact_ridership |

---

### Transportation — Traffic

**Base**: `_base.transportation.traffic`
**Union key**: `domain_source`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `municipal/transportation` | chicago | fact_traffic_observations |

---

### Corporate — Earnings

**Base**: `_base.corporate.earnings`
**Union key**: `domain_source`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `corporate/finance` | alpha_vantage | fact_earnings |

---

### Finance — Corporate Action

**Base**: `_base.finance.corporate_action`
**Union key**: `domain_source`

| Model | domain_source | Fact Table(s) |
|-------|--------------|---------------|
| `securities/stocks` | alpha_vantage | fact_dividends, fact_splits |
