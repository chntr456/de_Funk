---
type: domain-model-table
table: dim_parcel
extends: _base.property.parcel._dim_parcel
table_type: dimension
primary_key: [parcel_id]
unique_key: [parcel_code]
partition_by: [property_category]

enrich:
  - {join: dim_property_class, on: [property_class=property_class_code], fields: [property_category]}

# Source-specific column derivations — overrides derived: on inherited columns
# Full schema (types, nullable, descriptions, subset metadata) inherited from base
derivations:
  # Common fields
  parcel_id: "LPAD(pin, 14, '0')"
  parcel_code: "pin"
  property_class: "class"
  neighborhood_code: "nbhd"
  # Residential (from _base.property.residential via auto-absorption)
  bedrooms: "bdrm"
  bathrooms: "COALESCE(fbath, 0) + COALESCE(hbath, 0) * 0.5"
  basement: "bsmt_desc"
  exterior_wall: "ext_wall"
  # Commercial (from _base.property.commercial via auto-absorption)
  commercial_sqft: "comm_sqft"
  commercial_units: "comm_units"
  residential_units: "res_units"
  space_type: "use_type"
  floors: "num_floors"
  # Industrial (from _base.property.industrial via auto-absorption)
  industrial_sqft: "ind_sqft"
  ceiling_height: "ceiling_ht"
  zoning_class: "zoning"

measures:
  - [residential_count, count_distinct, parcel_id, "Residential parcels", {format: "#,##0", filters: ["property_category = 'RESIDENTIAL'"]}]
  - [commercial_count, count_distinct, parcel_id, "Commercial parcels", {format: "#,##0", filters: ["property_category = 'COMMERCIAL'"]}]
  - [industrial_count, count_distinct, parcel_id, "Industrial parcels", {format: "#,##0", filters: ["property_category = 'INDUSTRIAL'"]}]
---

## Parcel Dimension (Wide Table)

All parcels in Cook County — single wide table with type-specific columns partitioned by `property_category`.

### How It Works

1. **Schema inherited** from `_base.property.parcel._dim_parcel` (common columns)
2. **Subset columns auto-absorbed** from `_base.property.{residential,commercial,industrial}` via `subset_of`
3. **`derivations:`** maps inherited column names to Cook County source expressions
4. **`enrich:`** joins `dim_property_class` post-build to resolve `property_category`

Columns not listed in `derivations:` use the inherited column name as-is (e.g., `year_built`, `land_sqft`, `building_sqft` pass through unchanged).

### Data Flow

```
bronze.cook_county_parcel_universe (all fields in one source)
  → source: parcel_universe (aliases all columns)
  → derivations: maps canonical names to Cook County column names
  → enrich: JOIN dim_property_class → property_category
  → partition_by: property_category
  → dim_parcel (wide table)
```

### Adding a Field

To add `parking_spaces` to commercial properties:
1. Add to `_base/property/commercial.md` canonical_fields
2. Add source alias in `sources/cook_county/parcel_universe.md`
3. Add derivation here if source column name differs from canonical name

PIN must be zero-padded to 14 digits for cross-dataset joins. Source field `nbhd` maps to canonical `neighborhood_code`.
