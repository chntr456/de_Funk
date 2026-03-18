---
title: Bar Chart Tests
models: [securities.stocks, corporate.entity]
filters:
  sector: {source: corporate.entity.sector, type: select, multi: false}
  date:   {source: temporal.date, type: date_range, default: {from: current_date - 365}}
---

# Bar Chart Tests

Tests for `plotly.bar` — grouped, stacked, horizontal, implied aggregation.

---

## Companies by Sector (count_distinct, ignores all filters)

```de_funk
type: plotly.bar
data:
  x: corporate.entity.sector
  y: securities.stocks.ticker
  aggregation: count_distinct
formatting:
  title: Companies by Sector
  height: 350
config:
  page_filters:
    ignore: ["*"]
```

---

## Volume by Ticker (sum, horizontal, sorted)

```de_funk
type: plotly.bar
data:
  x: securities.stocks.ticker
  y: securities.stocks.volume
  aggregation: sum
  sort: {by: securities.stocks.volume, order: desc}
formatting:
  title: Total Volume by Ticker
  orientation: h
  height: 400
```

---

## Grouped Bars — Volume by Ticker × Year

```de_funk
type: plotly.bar
data:
  x: temporal.year
  y: securities.stocks.volume
  group_by: securities.stocks.ticker
  aggregation: sum
formatting:
  title: Volume by Ticker × Year (Grouped)
  barmode: group
  height: 420
```

---

## Stacked Bars — Spend by Department × Year

```de_funk
type: plotly.bar
data:
  x: temporal.year
  y: securities.stocks.adjusted_close
  group_by: corporate.entity.sector
  aggregation: avg
formatting:
  title: Avg Close by Sector × Year (Stacked)
  barmode: stack
  height: 420
```
