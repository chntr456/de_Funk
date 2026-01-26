# Company Model Overview

**Corporate entities with SEC identifiers**

---

## Summary

| Property | Value |
|----------|-------|
| **Model** | company |
| **Version** | 2.0 |
| **Status** | Production |
| **Tier** | 1 (Independent) |
| **Dependencies** | core |
| **Data Source** | Alpha Vantage |

---

## Purpose

The company model represents **legal corporate entities** (not tradable securities). It provides:

- **Entity Reference**: Company name, incorporation details
- **SEC Identification**: CIK (Central Index Key) as permanent identifier
- **Classification**: Sector, industry, SIC/NAICS codes
- **Location**: Headquarters address and contact info

### Key Design Decision

**Company is NOT a security** - it's a legal entity. Multiple securities (stocks, bonds, preferred shares) can belong to one company. The company model is linked to securities via CIK.

---

## Tables

| Table | Type | Status | Description |
|-------|------|--------|-------------|
| [dim_company](dimensions.md) | Dimension | Production | Company reference data |
| fact_company_financials | Fact | Future | SEC filing financials |
| fact_company_filings | Fact | Future | SEC filing metadata |

---

## CIK (Central Index Key)

The **CIK** is SEC's permanent identifier for companies:

- **Format**: 10-digit, zero-padded (e.g., `0000320193`)
- **Permanent**: Never changes, even if ticker changes
- **Unique**: One CIK per legal entity
- **Example**: Apple Inc = `0000320193`

### Why CIK?

| Identifier | Problem | CIK Solution |
|------------|---------|--------------|
| Ticker | Changes (FB→META, GOOGL/GOOG) | Permanent |
| Name | Varies (Apple Inc., Apple Computer) | Standardized |
| CUSIP | Different per security | One per company |

---

## Cross-Model Linkage

```
company.dim_company (PK: cik)
         │
         │ company_id = CONCAT('COMPANY_', cik)
         │
         ▼
stocks.dim_stock (FK: company_id)
```

**Query Example**:
```sql
SELECT
    s.ticker,
    s.close_price,
    c.company_name,
    c.sector
FROM stocks.dim_stock s
JOIN company.dim_company c ON s.company_id = c.company_id
WHERE s.ticker = 'AAPL'
```

---

## Configuration Files

| File | Purpose |
|------|---------|
| `configs/models/company/model.yaml` | Metadata, dependencies |
| `configs/models/company/schema.yaml` | dim_company schema |
| `configs/models/company/graph.yaml` | Nodes, edges |
| `configs/models/company/measures.yaml` | Company measures |

---

## Related Documentation

- [Dimensions](dimensions.md) - dim_company schema
- [Measures](measures.md) - Company measures
- [Stocks Model](../stocks/) - Linked via company_id
