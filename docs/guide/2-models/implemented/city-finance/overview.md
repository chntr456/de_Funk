---
title: "City Finance Model Overview"
tags: [municipal, economics, component/model, source/chicago, status/stable]
aliases: ["City Finance Overview", "Chicago Model Overview"]
---

# City Finance Model - Overview

---

The City Finance Model provides municipal finance and economic data for Chicago, enabling geographic and community-level analysis.

**Data Source:** Chicago Data Portal (Socrata API)
**Dependencies:** [[Core Model]], [[Macro Model]]
**Storage:** `storage/silver/city-finance`

---

## Model Components

---

### Dimensions
- **[[Community Area]]** - 77 Chicago community areas with geographic boundaries
- **[[Permit Types]]** - Building permit classifications

### Facts
- **[[Local Unemployment]]** - Community-level unemployment rates
- **[[Building Permits]]** - Construction permits by area and type
- **[[Business Licenses]]** - Commercial activity tracking
- **[[Economic Indicators]]** - Community economic metrics

### Data Sources
- **[[Chicago Data Portal Integration]]** - API endpoints and ingestion

### Architecture
- **[[City Finance Architecture]]** - Data pipeline and storage

---

## Quick Stats

| Metric | Value |
|--------|-------|
| **Community Areas** | 77 neighborhoods |
| **Time Range** | 2010-present |
| **Update Frequency** | Monthly |
| **Geographic Coverage** | City of Chicago |
| **Fact Tables** | 4 |
| **Dimension Tables** | 2 |

---

## Related Documentation

- [[Core Model]] - Calendar dimension
- [[Macro Model]] - National economic context
- [[Data Pipeline/Chicago]] - Ingestion architecture
- [[Facets/Municipal]] - Data normalization

---

**Tags:** #municipal #economics #component/model #source/chicago #architecture/ingestion-to-analytics

**Last Updated:** 2024-11-08
