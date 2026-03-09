---
type: reference
description: "Guide for the subsets convention — declarative data slicing by dimension discriminator"
---

## subsets Guide

A `subsets:` block on a base template declares that data can be filtered by a dimension discriminator into semantically meaningful subsets. Each subset value optionally defines type-specific fields.

### Three Implementation Patterns

#### Pattern 1: Wide Table (Recommended for typed entities)

When subsets have **different columns per type**, absorb all fields into one wide dimension table. Use `{subset: VALUE}` metadata on columns and partition by the discriminator.

```yaml
subsets:
  discriminator: _dim_property_class.property_category
  pattern: wide_table
  values:
    RESIDENTIAL:
      description: "Single-family, multi-family, condos"
      filter: "property_category = 'RESIDENTIAL'"
      fields: [bedrooms, bathrooms, stories, garage_spaces, basement, exterior_wall]
    COMMERCIAL:
      description: "Office, retail, mixed-use"
      filter: "property_category = 'COMMERCIAL'"
      fields: [commercial_sqft, commercial_units, residential_units, space_type, floors]
```

The dimension table includes all fields as nullable columns:

```yaml
_dim_parcel:
  partition_by: [property_category]
  schema:
    # Common fields (all rows)
    - [parcel_id, string, false, "PK"]
    - [property_category, string, true, "Denormalized from dim_property_class"]

    # Residential fields (null when not RESIDENTIAL)
    - [bedrooms, integer, true, "Number of bedrooms", {subset: RESIDENTIAL}]
    - [bathrooms, double, true, "Number of bathrooms", {subset: RESIDENTIAL}]

    # Commercial fields (null when not COMMERCIAL)
    - [commercial_sqft, double, true, "Floor area", {subset: COMMERCIAL}]
```

**When to use**: Entity has different attributes per type but shares the same fact tables. Examples: property parcels (residential vs commercial vs industrial).

**Advantages**:
- Delta Lake partition pruning makes filtered queries fast
- Columnar null compression makes sparse columns essentially free
- No join overhead — all fields available in one table
- Schema evolution handles new types by adding columns
- Simpler build pipeline (no separate tables, sources, or phases)

**Field dictionary**: The discriminator dimension (e.g., `_dim_property_class`) should include an `applicable_fields` column listing which subset columns are populated for each code.

#### Pattern 2: Separate Models (For independent domain models)

When subsets have **completely different fact tables and build pipelines**, use separate domain models that independently extend the base.

```yaml
subsets:
  discriminator: _dim_security.asset_type
  values:
    Stock:
      model: stocks
      description: "Common and preferred stock equities"
      filter: "asset_type = 'Stock'"
    ETF:
      model: etfs
      description: "Exchange-traded funds"
      filter: "asset_type = 'ETF'"
```

**When to use**: Each subset is a full domain model with its own fact tables, build pipeline, and graph. Examples: securities (stocks vs options vs ETFs — each has different fact tables).

#### Pattern 3: Filter-Only (No type-specific fields)

When subsets share the **exact same schema** and differ only as analytical slices.

```yaml
subsets:
  discriminator: _dim_crime_type.crime_category
  values:
    VIOLENT:
      description: "Homicide, assault, battery, robbery"
      filter: "crime_category = 'VIOLENT'"
    PROPERTY:
      description: "Theft, burglary, motor vehicle theft"
      filter: "crime_category = 'PROPERTY'"
```

**When to use**: All rows have the same columns. The discriminator is just for analytical filtering. No `fields:`, `extends:`, or `model:` needed.

### Pattern Selection Guide

| Question | Wide Table | Separate Models | Filter-Only |
|----------|-----------|-----------------|-------------|
| Different columns per type? | Yes | Yes | No |
| Different fact tables per type? | No | Yes | No |
| Same build pipeline? | Yes | No | Yes |
| Same source data? | Yes | No | Yes |

### Key Properties

| Property | Required | Description |
|----------|----------|-------------|
| `discriminator` | Yes | `dimension_table.column` — where the enum lives |
| `pattern` | No | `wide_table` or omit (inferred from context) |
| `description` | Yes | Human-readable description |
| `values` | Yes | Map of enum values to subset definitions |
| `values.*.fields` | No | Columns on the wide table for this subset |
| `values.*.model` | No | Child domain-model (separate models pattern) |
| `values.*.description` | Yes | What this subset represents |
| `values.*.filter` | Yes | SQL predicate for the subset |

### Current Subset Assignments

| Base Template | Discriminator | Pattern | Values |
|--------------|---------------|---------|--------|
| `_base.property.parcel` | `_dim_property_class.property_category` | **Wide table** | RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER |
| `_base.finance.securities` | `_dim_security.asset_type` | **Separate models** | Stock, ETF, Option, Future |
| `_base.public_safety.crime` | `_dim_crime_type.crime_category` | Filter-only | VIOLENT, PROPERTY, OTHER |
| `_base.operations.service_request` | `_dim_request_type.request_category` | Filter-only | INFRASTRUCTURE, SANITATION, VEGETATION, BUILDINGS, ANIMALS, OTHER |
| `_base.housing.permit` | `_dim_permit_type.permit_category` | Filter-only | NEW_CONSTRUCTION, ALTERATION, DEMOLITION, OTHER |
| `_base.transportation.transit` | `_dim_transit_station.transit_mode` | Filter-only | RAIL, BUS, SUBWAY, LIGHT_RAIL, FERRY |

### Relationship to Federation

Subsets and federation are complementary:
- **Federation** slices data horizontally by `domain_source` (which city/county produced it)
- **Subsets** slice data vertically by a dimension attribute (what category it belongs to)

This enables queries like: "Show residential parcels across all federated counties" (subset + federation).

### Loader Behavior

The `subsets:` block is declarative. The loader uses it for:
1. **Validation**: Verify that `discriminator` column exists in the named dimension
2. **Filter generation**: Automatically produce filter predicates for downstream queries
3. **Column metadata**: `{subset: VALUE}` marks which columns belong to which subset
4. **Field dictionary**: Populate `applicable_fields` on the discriminator dimension
5. **Documentation**: Discoverable via `behaviors: [subsettable]`
