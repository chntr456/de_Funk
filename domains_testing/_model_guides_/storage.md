---
type: reference
description: "Guide for storage configuration"
---

## storage Guide

Storage defines where data comes from (bronze) and where it goes (silver).

### Format

```yaml
storage:
  format: delta
  bronze:
    provider: {provider_name}
    tables:
      # [local_name, provider/endpoint]
      - [payments, chicago/chicago_payments]
      - [contracts, chicago/chicago_contracts]
  silver:
    root: storage/silver/{model_name}/
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `format` | Yes | Always `delta` |
| `bronze.provider` | Yes | Data provider identifier |
| `bronze.tables` | Yes | List of `[local_name, provider/endpoint]` |
| `silver.root` | Yes | Output directory path |

### Bronze Table Naming

The `local_name` is how tables are referenced in the model config. The `provider/endpoint` maps to the physical path:

```
storage/bronze/{provider}/{endpoint}/
```

Example: `chicago/chicago_payments` → `storage/bronze/chicago/chicago_payments/`

### Multi-Provider Models

Models can pull from multiple providers:

```yaml
bronze:
  provider: multi
  tables:
    - [payments, chicago/chicago_payments]
    - [sec_filings, sec/company_expenses]
```
