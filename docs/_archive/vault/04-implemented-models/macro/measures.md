# Macro Measures

**Economic indicator calculations**

---

## Overview

The macro model provides 4 measures for economic analysis.

---

## Simple Measures

### avg_unemployment_rate

**Average unemployment rate**

| Property | Value |
|----------|-------|
| Source | `fact_unemployment.value` |
| Aggregation | `avg` |
| Data Type | double |
| Format | `#,##0.00%` |

**Usage**:
```python
model.calculate_measure("avg_unemployment_rate")
```

---

### latest_cpi

**Latest CPI value**

| Property | Value |
|----------|-------|
| Source | `fact_cpi.value` |
| Aggregation | `max` |
| Data Type | double |
| Format | `#,##0.00` |

**Usage**:
```python
model.calculate_measure("latest_cpi")
```

---

### employment_growth

**Total employment growth**

| Property | Value |
|----------|-------|
| Source | `fact_employment.value` |
| Aggregation | `sum` |
| Data Type | double |
| Format | `#,##0` |

**Usage**:
```python
model.calculate_measure("employment_growth")
```

---

### wage_trend

**Average wage trend**

| Property | Value |
|----------|-------|
| Source | `fact_wages.value` |
| Aggregation | `avg` |
| Data Type | double |
| Format | `$#,##0.00` |

**Usage**:
```python
model.calculate_measure("wage_trend")
```

---

## Usage Examples

```python
from models.api.registry import get_model_registry

registry = get_model_registry()
model = registry.get_model("macro")

# Average unemployment rate
unemployment = model.calculate_measure("avg_unemployment_rate")

# Latest CPI
cpi = model.calculate_measure("latest_cpi")

# Filter by year
unemployment_2024 = model.calculate_measure(
    "avg_unemployment_rate",
    filters=[{"column": "year", "value": 2024}]
)
```

---

## Related Documentation

- [Overview](overview.md) - Model overview
- [Dimensions](dimensions.md) - Schema details
