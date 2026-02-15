---
type: reference
description: "Guide for measure definitions"
---

## measures Guide

Measures define pre-built calculations on model tables.

### Simple Measures

```yaml
measures:
  simple:
    # [name, aggregation, column, description, {options}]
    - [total_amount, sum, transaction_amount, "Total amount", {format: "$#,##0.00"}]
    - [entry_count, count_distinct, entry_id, "Entry count", {format: "#,##0"}]
    - [avg_amount, avg, transaction_amount, "Average", {format: "$#,##0.00"}]
```

### Aggregation Types

| Aggregation | Description |
|-------------|-------------|
| `count` | Count rows |
| `count_distinct` | Count unique |
| `sum` | Sum values |
| `avg` | Average |
| `min` | Minimum |
| `max` | Maximum |

### Computed Measures

```yaml
  computed:
    # [name, expression, SQL, description, {options}]
    - [payroll_pct, expression, "SUM(CASE WHEN entry_type = 'PAYROLL' THEN amount ELSE 0 END) / SUM(amount)", "Payroll %", {format: "0.00%"}]
```

### Python Measures

For complex calculations (NPV, Sharpe ratio, rolling windows):

```yaml
  python:
    net_present_value:
      function: "ledger.measures.calculate_npv"
      params:
        discount_rate: 0.05
```

Python measures are implemented in `src/de_funk/models/implemented/{model}/measures.py`.

### Measure Options

| Option | Description |
|--------|-------------|
| `format` | Display format (`$#,##0.00`, `0.00%`) |
| `filter` | Conditional filter (`entry_type = 'PAYROLL'`) |
