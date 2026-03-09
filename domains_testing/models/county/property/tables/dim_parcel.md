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

schema:
  # Common fields (all parcels)
  - [parcel_id, string, false, "PK - 14-digit PIN", {derived: "LPAD(pin, 14, '0')"}]
  - [parcel_code, string, false, "Natural key (standardized PIN)", {derived: "pin"}]
  - [property_class, string, true, "Property class code", {derived: "class"}]
  - [property_category, string, true, "Category (from dim_property_class)", {enriched: true}]
  - [township_code, string, true, "Township code"]
  - [neighborhood_code, string, true, "Neighborhood code", {derived: "nbhd"}]
  - [year_built, integer, true, "Year built"]
  - [land_sqft, double, true, "Land area in square feet"]
  - [building_sqft, double, true, "Building area in square feet"]
  - [latitude, double, true, "Parcel centroid latitude"]
  - [longitude, double, true, "Parcel centroid longitude"]
  - [tax_code, string, true, "Tax district code"]

  # Residential fields (null when property_category != RESIDENTIAL)
  - [bedrooms, integer, true, "Number of bedrooms", {subset: RESIDENTIAL, derived: "bdrm"}]
  - [bathrooms, double, true, "Number of bathrooms", {subset: RESIDENTIAL, derived: "COALESCE(fbath, 0) + COALESCE(hbath, 0) * 0.5"}]
  - [stories, double, true, "Number of stories", {subset: RESIDENTIAL, derived: "stories"}]
  - [garage_spaces, integer, true, "Garage/parking spaces", {subset: RESIDENTIAL, derived: "garage_spaces"}]
  - [basement, string, true, "Basement type", {subset: RESIDENTIAL, derived: "bsmt_desc", enum: [FULL, PARTIAL, CRAWL, NONE]}]
  - [exterior_wall, string, true, "Exterior wall material", {subset: RESIDENTIAL, derived: "ext_wall"}]

  # Commercial fields (null when property_category != COMMERCIAL)
  - [commercial_sqft, double, true, "Commercial floor area sq ft", {subset: COMMERCIAL, derived: "comm_sqft"}]
  - [commercial_units, integer, true, "Number of commercial units", {subset: COMMERCIAL, derived: "comm_units"}]
  - [residential_units, integer, true, "Residential units (mixed-use)", {subset: COMMERCIAL, derived: "res_units"}]
  - [space_type, string, true, "Space classification", {subset: COMMERCIAL, derived: "use_type", enum: [OFFICE, RETAIL, MIXED_USE, WAREHOUSE]}]
  - [floors, integer, true, "Number of floors", {subset: COMMERCIAL, derived: "num_floors"}]

  # Industrial fields (null when property_category != INDUSTRIAL)
  - [industrial_sqft, double, true, "Industrial floor area sq ft", {subset: INDUSTRIAL, derived: "ind_sqft"}]
  - [loading_docks, integer, true, "Number of loading docks", {subset: INDUSTRIAL, derived: "loading_docks"}]
  - [ceiling_height, double, true, "Ceiling height in feet", {subset: INDUSTRIAL, derived: "ceiling_ht"}]
  - [zoning_class, string, true, "Industrial zoning classification", {subset: INDUSTRIAL, derived: "zoning"}]

measures:
  - [parcel_count, count_distinct, parcel_id, "Number of parcels", {format: "#,##0"}]
  - [residential_count, count_distinct, parcel_id, "Residential parcels", {format: "#,##0", filters: ["property_category = 'RESIDENTIAL'"]}]
  - [commercial_count, count_distinct, parcel_id, "Commercial parcels", {format: "#,##0", filters: ["property_category = 'COMMERCIAL'"]}]
  - [industrial_count, count_distinct, parcel_id, "Industrial parcels", {format: "#,##0", filters: ["property_category = 'INDUSTRIAL'"]}]
  - [avg_bedrooms, avg, bedrooms, "Average bedrooms", {format: "#,##0.0", subset: RESIDENTIAL}]
  - [avg_bathrooms, avg, bathrooms, "Average bathrooms", {format: "#,##0.0", subset: RESIDENTIAL}]
  - [avg_commercial_sqft, avg, commercial_sqft, "Average commercial sq ft", {format: "#,##0", subset: COMMERCIAL}]
  - [total_commercial_units, sum, commercial_units, "Total commercial units", {format: "#,##0", subset: COMMERCIAL}]
  - [avg_industrial_sqft, avg, industrial_sqft, "Average industrial sq ft", {format: "#,##0", subset: INDUSTRIAL}]
  - [total_loading_docks, sum, loading_docks, "Total loading docks", {format: "#,##0", subset: INDUSTRIAL}]
---

## Parcel Dimension (Wide Table)

All parcels in Cook County — single wide table with type-specific columns partitioned by `property_category`.

### Data Flow

```
bronze.cook_county_parcel_universe (all fields in one source)
  → source: parcel_universe (aliases all columns — common + residential + commercial + industrial)
  → enrich: JOIN dim_property_class ON property_class = property_class_code → property_category
  → partition_by: property_category
  → dim_parcel (wide table)
```

### Column Layout

| Category | Columns | Null When |
|----------|---------|-----------|
| Common | parcel_id through tax_code (12 fields) | Never |
| Residential | bedrooms, bathrooms, stories, garage_spaces, basement, exterior_wall | Not RESIDENTIAL |
| Commercial | commercial_sqft, commercial_units, residential_units, space_type, floors | Not COMMERCIAL |
| Industrial | industrial_sqft, loading_docks, ceiling_height, zoning_class | Not INDUSTRIAL |

PIN must be zero-padded to 14 digits for cross-dataset joins. Source field `nbhd` maps to canonical `neighborhood_code`.
