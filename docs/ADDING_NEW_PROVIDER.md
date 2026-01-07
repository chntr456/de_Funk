# Adding a New Data Provider - Planning Guide

**Purpose**: Planning checklist and considerations for adding a new data provider

---

## Files to Touch (Complete Map)

When adding a new provider, these are ALL the files that need to be created or modified:

```
Files to CREATE:
─────────────────────────────────────────────────────────────────────
datapipelines/providers/{provider}/
├── __init__.py                    # Exports
├── provider.py                    # Provider class (API client)
├── {provider}_registry.py         # Endpoint → Facet mapping
└── facets/
    ├── __init__.py
    ├── {provider}_base_facet.py   # Shared transformation logic
    └── {endpoint}_facet.py        # One per endpoint type

configs/pipelines/
└── {provider}_endpoints.json      # API endpoint definitions

scripts/ingest/
└── run_{provider}_ingestion.py    # Test/run script


Files to MODIFY:
─────────────────────────────────────────────────────────────────────
configs/storage.json               # Add Bronze table definitions
datapipelines/base/ingestor_engine.py  # Register provider in create_engine()
.env                               # Add {PROVIDER}_API_KEYS
```

---

## Key Considerations

### 1. API Structure Considerations

| Question | Options | Impact |
|----------|---------|--------|
| **Authentication method?** | API key, OAuth, None | Affects key_pool setup |
| **Rate limiting?** | Calls/sec, Calls/day, None | Sets `rate_limit_per_sec` |
| **Pagination method?** | Offset, Cursor, Page number, None | Affects fetch loop |
| **Response format?** | JSON array, Nested JSON, CSV | Affects facet parsing |
| **Batch support?** | Multiple items per call, Single item | Affects efficiency |

### 2. Data Architecture Considerations

| Question | Options | Impact |
|----------|---------|--------|
| **One table or many?** | Single table (partitioned), Multiple tables | Storage config structure |
| **Partition column?** | Date, Year, Asset type, None | Query performance |
| **Write strategy?** | `upsert` (mutable), `append` (immutable) | Dedup vs time-series |
| **Key columns?** | Natural keys for upsert | Required for upsert strategy |
| **Date column?** | For append strategy | Required for append strategy |

### 3. Multi-Endpoint → Single Table Pattern

**When to use**: Same data type across multiple endpoints (e.g., budget by fiscal year)

```
Example: Chicago Budget Data
────────────────────────────────────────────────────────────
Endpoints:                         Single Table:
├── budget_fy2024    ──┐
├── budget_fy2023    ──┼──→  bronze/chicago/budget/
└── budget_fy2022    ──┘           ├── fiscal_year=2024/
                                   ├── fiscal_year=2023/
                                   └── fiscal_year=2022/
```

**Key pattern**:
- Endpoint config has `metadata.fiscal_year` field
- All endpoints map to same Facet class
- Facet extracts metadata and adds as partition column
- Storage config defines single table with `partitions: ["fiscal_year"]`

---

## Directory Structure Examples

### Minimal Provider (1 endpoint → 1 table)

```
datapipelines/providers/simple_api/
├── __init__.py
├── provider.py
└── facets/
    ├── __init__.py
    └── data_facet.py
```

### Standard Provider (N endpoints → N tables)

```
datapipelines/providers/alpha_vantage/
├── __init__.py
├── provider.py
├── alpha_vantage_registry.py       # Endpoint → Facet mapping
└── facets/
    ├── __init__.py
    ├── alpha_vantage_base_facet.py
    ├── securities_reference_facet.py   # → securities_reference table
    ├── securities_prices_facet.py      # → securities_prices_daily table
    ├── income_statement_facet.py       # → income_statements table
    └── balance_sheet_facet.py          # → balance_sheets table
```

### Multi-Endpoint Provider (N endpoints → M tables, where N > M)

```
datapipelines/providers/chicago/
├── __init__.py
├── provider.py
├── chicago_registry.py
└── facets/
    ├── __init__.py
    ├── chicago_base_facet.py
    ├── budget_facet.py             # budget_fy2024, budget_fy2023, etc. → chicago_budget
    ├── unemployment_facet.py       # → chicago_unemployment
    └── building_permits_facet.py   # → chicago_building_permits
```

### Complex Provider (with parsers/transformers)

```
datapipelines/providers/sec_edgar/
├── __init__.py
├── provider.py
├── sec_registry.py
├── parsers/                        # Complex XML/XBRL parsing
│   ├── __init__.py
│   ├── xbrl_parser.py
│   └── filing_parser.py
└── facets/
    ├── __init__.py
    ├── sec_base_facet.py
    └── form_10k_facet.py
```

---

## Configuration Templates

### Endpoint Config (`configs/pipelines/{provider}_endpoints.json`)

```json
{
  "credentials": {
    "api_keys": [],
    "comment": "Set {PROVIDER}_API_KEYS env var"
  },
  "base_urls": {
    "core": "https://api.example.com"
  },
  "headers": {
    "Content-Type": "application/json"
  },
  "rate_limit_per_sec": 1.0,

  "endpoints": {
    "endpoint_name": {
      "base": "core",
      "method": "GET",
      "path_template": "/resource/{id}",
      "default_query": { "$limit": 50000 },
      "metadata": {
        "table_name": "target_table",
        "custom_field": "value"
      }
    }
  }
}
```

### Storage Config (`configs/storage.json` - add to tables section)

```json
{
  "table_name": {
    "root": "bronze",
    "rel": "{provider}/{table_path}",
    "partitions": ["partition_column"],
    "write_strategy": "upsert",
    "key_columns": ["unique_id"],
    "comment": "Description"
  }
}
```

---

## Implementation Checklist

```
[ ] 1. Analyze API documentation
      - Auth method, rate limits, pagination
      - Response structure
      - Available endpoints

[ ] 2. Design data architecture
      - How many tables?
      - Partition strategy?
      - Upsert vs append?

[ ] 3. Create endpoint config
      configs/pipelines/{provider}_endpoints.json

[ ] 4. Add storage config
      configs/storage.json - tables section

[ ] 5. Create provider directory
      datapipelines/providers/{provider}/

[ ] 6. Implement provider class
      - Extends BaseProvider
      - Implements fetch_ticker_data()

[ ] 7. Implement registry
      - Endpoint rendering with params
      - Metadata extraction

[ ] 8. Implement facets
      - One per data type
      - OUTPUT_SCHEMA defined
      - normalize() method

[ ] 9. Register in engine
      datapipelines/base/ingestor_engine.py - create_engine()

[ ] 10. Create test script
       scripts/ingest/run_{provider}_ingestion.py

[ ] 11. Set environment variable
       .env: {PROVIDER}_API_KEYS=...

[ ] 12. Test ingestion
       python -m scripts.ingest.run_{provider}_ingestion
```

---

## Reference Implementations

| Component | Example File |
|-----------|-------------|
| Provider class | `datapipelines/providers/alpha_vantage/provider.py` |
| Registry | `datapipelines/providers/alpha_vantage/alpha_vantage_registry.py` |
| Base facet | `datapipelines/providers/alpha_vantage/facets/alpha_vantage_base_facet.py` |
| Endpoint facet | `datapipelines/providers/alpha_vantage/facets/securities_prices_facet.py` |
| Engine factory | `datapipelines/base/ingestor_engine.py` |
| Storage config | `configs/storage.json` |
| Endpoint config | `configs/pipelines/alpha_vantage_endpoints.json` |

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `KeyError: 'endpoint_name'` | Endpoint not in config | Check `{provider}_endpoints.json` |
| `Table not found` | Missing storage config | Add to `configs/storage.json` |
| `Schema mismatch` | Facet schema wrong | Update `OUTPUT_SCHEMA` |
| `Missing partition column` | Facet not adding it | Add `withColumn()` |
| `Rate limit exceeded` | Too many calls | Reduce `rate_limit_per_sec` |
