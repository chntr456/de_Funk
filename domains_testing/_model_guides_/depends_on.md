---
type: reference
description: "Guide for depends_on - model build ordering"
---

## depends_on Guide

Declares which models must be built before this one.

### Syntax

```yaml
depends_on: [temporal, company]
```

### Build Order

Models are built in dependency-resolved order:

```
Tier 0: temporal (no dependencies)
Tier 1: company, geospatial (depend on temporal)
Tier 2: chicago_ledger (depends on temporal)
Tier 3: chicago_finance (depends on temporal, chicago_ledger)
```

### Common Dependencies

| Dependency | Why |
|------------|-----|
| `temporal` | All facts FK to dim_calendar via date_id |
| `company` | Stock models need company dimension |
| `geospatial` | Crime/housing models need location dimension |

### Rules

1. No circular dependencies
2. Base templates (`_base.*`) are NOT listed - they are templates, not built models
3. Only list direct dependencies, not transitive ones
