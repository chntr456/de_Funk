---
type: reference
description: "Guide for the subsets convention — declarative data slicing by dimension discriminator"
---

## subsets Guide

A `subsets:` block on a base template declares that data can be filtered by a dimension discriminator into semantically meaningful subsets. Each subset value optionally links to a child template that adds type-specific fields.

### Syntax (Base Template)

```yaml
subsets:
  discriminator: _dim_property_class.property_category
  description: "Property parcels can be subset by classification category"
  values:
    RESIDENTIAL:
      extends: _base.property.residential
      description: "Single-family, multi-family, condos"
      filter: "property_category = 'RESIDENTIAL'"
    COMMERCIAL:
      extends: _base.property.commercial
      description: "Office, retail, mixed-use"
      filter: "property_category = 'COMMERCIAL'"
    EXEMPT:
      description: "Government, religious, educational"
      filter: "property_category = 'EXEMPT'"
```

### Key Properties

| Property | Required | Description |
|----------|----------|-------------|
| `discriminator` | Yes | `dimension_table.column` — where the enum lives |
| `description` | Yes | Human-readable description of the subsetting concept |
| `values` | Yes | Map of enum values to subset definitions |
| `values.*.extends` | No | Child base template that adds type-specific schema |
| `values.*.model` | No | Child domain-model (for securities pattern) |
| `values.*.description` | Yes | What this subset represents |
| `values.*.filter` | Yes | SQL predicate for the subset |

### Two Patterns

**Pattern 1: `extends:` — child base templates** (property)

The child template adds schema columns to the parent's dimension. The child template declares `subset_of:` and `subset_value:` as back-references:

```yaml
# _base/property/residential.md
type: domain-base
extends: _base.property.parcel
subset_of: _base.property.parcel
subset_value: RESIDENTIAL
```

**Pattern 2: `model:` — child domain-models** (securities)

The child models are full `domain-model` implementations (not `domain-base` extensions). The subset points to a concrete model name:

```yaml
# _base/finance/securities.md
subsets:
  discriminator: _dim_security.asset_type
  values:
    Stock:
      model: stocks
      description: "Common and preferred stock equities"
      filter: "asset_type = 'Stock'"
```

### Filter-Only Subsets

Values without `extends:` or `model:` are filter-only — valid analytical slices but no additional schema:

```yaml
EXEMPT:
  description: "Government, religious, educational"
  filter: "property_category = 'EXEMPT'"
```

### Current Subset Assignments

| Base Template | Discriminator | Values | Child Templates? |
|--------------|---------------|--------|-----------------|
| `_base.property.parcel` | `_dim_property_class.property_category` | RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER | Yes (3 of 5) |
| `_base.finance.securities` | `_dim_security.asset_type` | Stock, ETF, Option, Future | Yes (model: references) |
| `_base.public_safety.crime` | `_dim_crime_type.crime_category` | VIOLENT, PROPERTY, OTHER | No |
| `_base.operations.service_request` | `_dim_request_type.request_category` | INFRASTRUCTURE, SANITATION, VEGETATION, BUILDINGS, ANIMALS, OTHER | No |
| `_base.housing.permit` | `_dim_permit_type.permit_category` | NEW_CONSTRUCTION, ALTERATION, DEMOLITION, OTHER | No |
| `_base.transportation.transit` | `_dim_transit_station.transit_mode` | RAIL, BUS, SUBWAY, LIGHT_RAIL, FERRY | No |

### Relationship to Federation

Subsets and federation are complementary:
- **Federation** slices data horizontally by `domain_source` (which city/county produced it)
- **Subsets** slice data vertically by a dimension attribute (what category it belongs to)

A template can have both:
```yaml
federation:
  enabled: true
  union_key: domain_source

subsets:
  discriminator: _dim_crime_type.crime_category
  ...
```

This enables queries like: "Show violent crimes across all federated cities" (subset + federation).

### Loader Behavior

The `subsets:` block is declarative. The loader uses it for:
1. **Validation**: Verify that `discriminator` column exists in the named dimension
2. **Filter generation**: Automatically produce filter predicates for downstream queries
3. **Schema resolution**: When `extends:` is present, merge child template's `additional_schema` into parent dimension
4. **Documentation**: Discoverable via `behaviors: [subsettable]`
