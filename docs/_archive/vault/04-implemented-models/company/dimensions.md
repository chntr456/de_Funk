# Company Dimensions

**Corporate entity reference schema**

---

## dim_company

**Purpose**: Master corporate entity reference

**Primary Key**: `cik`

**Secondary Key**: `company_id` (derived: `CONCAT('COMPANY_', cik)`)

---

## Schema

### Identification

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `cik` | string | SEC Central Index Key (10 digits) | `0000320193` |
| `company_id` | string | Unique ID (FK target) | `COMPANY_0000320193` |
| `company_name` | string | Official company name | `Apple Inc` |
| `legal_name` | string | Full legal name | `Apple Inc.` |
| `ticker_primary` | string | Primary trading ticker | `AAPL` |

### Incorporation

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `incorporation_state` | string | State of incorporation | `CA` |
| `incorporation_country` | string | Country of incorporation | `US` |
| `incorporation_date` | date | Date incorporated | `1977-01-03` |

### Classification (GICS)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `sector` | string | GICS Sector | `Technology` |
| `industry_group` | string | GICS Industry Group | `Technology Hardware & Equipment` |
| `industry` | string | GICS Industry | `Technology Hardware, Storage & Peripherals` |
| `sub_industry` | string | GICS Sub-Industry | `Technology Hardware, Storage & Peripherals` |
| `sic_code` | string | SIC Code (SEC) | `3571` |
| `naics_code` | string | NAICS Code | `334111` |

### Location

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `headquarters_city` | string | HQ city | `Cupertino` |
| `headquarters_state` | string | HQ state | `CA` |
| `headquarters_country` | string | HQ country | `US` |
| `headquarters_address` | string | Full address | `One Apple Park Way` |

### Contact

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `website` | string | Company website | `https://www.apple.com` |
| `phone` | string | Main phone | `408-996-1010` |
| `email` | string | Investor relations email | `ir@apple.com` |

### Status

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `is_active` | boolean | Active company | `true` |
| `fiscal_year_end` | string | FY end month | `September` |
| `employee_count` | long | Employee count | `164000` |

### Metadata

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `description` | string | Company description | `Apple Inc. designs...` |
| `last_updated` | timestamp | Last data update | `2024-01-15T10:00:00` |

---

## Source Mapping

| Column | Bronze Source | Transformation |
|--------|---------------|----------------|
| `cik` | securities_reference.cik | Padded to 10 digits |
| `company_id` | Derived | `CONCAT('COMPANY_', cik)` |
| `company_name` | securities_reference.security_name | Direct |
| `sector` | securities_reference.sector | Direct |
| `industry` | securities_reference.industry | Direct |

---

## Usage Examples

### Get Company by CIK

```sql
SELECT company_name, sector, industry
FROM company.dim_company
WHERE cik = '0000320193'  -- Apple
```

### Companies by Sector

```sql
SELECT company_name, industry, employee_count
FROM company.dim_company
WHERE sector = 'Technology'
ORDER BY employee_count DESC
```

### Join with Stocks

```sql
SELECT
    c.company_name,
    s.ticker,
    s.market_cap
FROM company.dim_company c
JOIN stocks.dim_stock s ON c.company_id = s.company_id
WHERE c.sector = 'Technology'
ORDER BY s.market_cap DESC
```

---

## Related Documentation

- [Company Overview](overview.md)
- [Measures](measures.md)
- [Stocks Dimensions](../stocks/dimensions.md) - company_id linkage
