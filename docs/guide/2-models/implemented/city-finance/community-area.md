---
title: "Community Area Dimension"
tags: [municipal, component/model, concept/dimensional-modeling, concept/geography]
aliases: ["Community Areas", "Chicago Neighborhoods", "dim_community_area"]
---

# Community Area Dimension

---

The Community Area dimension defines Chicago's 77 official community areas with geographic boundaries, demographics, and identifiers.

**Table:** `dim_community_area`
**Primary Key:** `community_area_id`
**Storage:** `storage/silver/city-finance/dims/dim_community_area`

---

## Purpose

---

Chicago community areas are geographic subdivisions used for planning and statistical purposes. They provide consistent boundaries for analyzing local economic and social trends.

**Use Cases:**
- Geographic filtering and aggregation
- Community-level analysis
- Mapping and visualization
- Correlation with local unemployment
- Building permit analysis by neighborhood

---

## Schema

---

**Grain:** One row per community area (77 total)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **community_area_id** | integer | Community area number (1-77) | 32 |
| **community_area_name** | string | Official neighborhood name | "Loop" |
| **area_number** | string | Two-digit area code | "32" |
| **latitude** | double | Geographic center latitude | 41.8819 |
| **longitude** | double | Geographic center longitude | -87.6278 |
| **population** | integer | Population estimate | 29,283 |
| **median_income** | double | Median household income | 92,154 |
| **area_sq_miles** | double | Area in square miles | 1.58 |

---

## Sample Data

---

```
+--------------------+-----------------------+-------------+----------+-----------+------------+---------------+--------------+
| community_area_id  | community_area_name   | area_number | latitude | longitude | population | median_income | area_sq_miles|
+--------------------+-----------------------+-------------+----------+-----------+------------+---------------+--------------+
| 32                 | Loop                  | 32          | 41.8819  | -87.6278  | 29,283     | 92,154        | 1.58         |
| 8                  | Near North Side       | 08          | 41.9029  | -87.6315  | 105,481    | 88,632        | 1.91         |
| 28                 | Near West Side        | 28          | 41.8820  | -87.6476  | 67,881     | 45,223        | 4.69         |
| 43                 | South Shore           | 43          | 41.7661  | -87.5794  | 49,767     | 34,562        | 3.96         |
+--------------------+-----------------------+-------------+----------+-----------+------------+---------------+--------------+
```

---

## Community Area Map

---

Chicago's 77 community areas are organized geographically:

**North Side Areas:** 1-23
**West Side Areas:** 24-31
**Central Areas:** 32-33
**South Side Areas:** 34-77

**Notable Communities:**
- **Loop (32):** Downtown business district
- **Near North Side (8):** Gold Coast, Streeterville
- **Hyde Park (41):** University of Chicago
- **South Shore (43):** Lakefront community
- **Englewood (68):** South side neighborhood

---

## Geographic Boundaries

---

Community areas have fixed boundaries defined by streets and natural features. These boundaries are used for:

- **Census data aggregation**
- **City planning and zoning**
- **Statistical reporting**
- **Community organization**

**Coordinate System:** WGS84 (lat/long)
**Boundary Format:** Polygon geometries (stored in Bronze)

---

## Data Source

---

**Provider:** Chicago Data Portal
**API Endpoint:** `/resource/igwz-8jzy.json`
**Update Frequency:** Annual (boundaries fixed, demographics updated)

**Bronze Table:** `bronze.chicago_community_areas`
**Transformation:** Direct mapping with geographic enrichment

---

## Usage Examples

---

### Filter by Community

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get specific communities
areas = session.get_table('city_finance', 'dim_community_area')
downtown = areas.filter(
    areas['community_area_name'].isin(['Loop', 'Near North Side'])
).to_pandas()

print(downtown[['community_area_name', 'population', 'median_income']])
```

### Geographic Analysis

```python
# Get all lakefront communities (by longitude)
lakefront = areas.filter(areas['longitude'] > -87.60).to_pandas()

# Communities by population density
areas_df = areas.to_pandas()
areas_df['density'] = areas_df['population'] / areas_df['area_sq_miles']
high_density = areas_df.nlargest(10, 'density')

print(high_density[['community_area_name', 'density']])
```

### Join with Facts

```python
# Get unemployment by community
city_finance = session.load_model('city_finance')
unemployment = city_finance.get_fact_df('fact_local_unemployment').to_pandas()

# Join with community details
merged = unemployment.merge(
    areas_df,
    on='community_area_id'
)

# Average unemployment by income bracket
merged['income_bracket'] = pd.cut(
    merged['median_income'],
    bins=[0, 40000, 60000, 100000],
    labels=['Low', 'Medium', 'High']
)
avg_by_income = merged.groupby('income_bracket')['unemployment_rate'].mean()
print(avg_by_income)
```

### Mapping Visualization

```python
import folium

# Create Chicago map
chicago_map = folium.Map(
    location=[41.8781, -87.6298],
    zoom_start=11
)

# Add community markers
for _, area in areas_df.iterrows():
    folium.CircleMarker(
        location=[area['latitude'], area['longitude']],
        radius=5,
        popup=f"{area['community_area_name']}<br>Pop: {area['population']:,}",
        color='blue',
        fill=True
    ).add_to(chicago_map)

chicago_map.save('community_areas.html')
```

---

## Relationships

---

### Used By (Foreign Key References)

- **[[Local Unemployment]]** - `fact_local_unemployment.community_area_id`
- **[[Building Permits]]** - `fact_building_permits.community_area_id`
- **[[Business Licenses]]** - `fact_business_licenses.community_area_id`
- **[[Economic Indicators]]** - `fact_economic_indicators.community_area_id`

### Dependencies

- **[[Core Model]]** - Can join to calendar via date fields
- **[[Macro Model]]** - Compare local vs national trends

---

## Design Decisions

---

### Why Community Areas vs Zip Codes?

**Decision:** Use official community areas

**Rationale:**
- Fixed boundaries (zip codes change)
- Official city planning divisions
- Consistent with Chicago Data Portal
- Better for historical analysis
- Align with census tracts

### Why Include Demographics?

**Decision:** Include population and median income

**Rationale:**
- Enable normalization (per capita calculations)
- Understand economic context
- Identify correlations
- Support equity analysis

---

## Future Enhancements

---

### Planned Additions

- **Polygon boundaries** - Full geographic shapes for mapping
- **Adjacent areas** - Neighboring community relationships
- **Historical demographics** - Time series population/income
- **Crime statistics** - Safety metrics by area
- **School districts** - Education zone mapping

### Integration Opportunities

Chicago Data Portal has additional datasets:
- **Crime data** - Incidents by community area
- **311 requests** - Service requests by area
- **Health indicators** - Community health metrics
- **Transportation** - Transit access and usage

---

## Related Documentation

---

### Model Documentation
- [[City Finance Overview]] - Overall model
- [[Local Unemployment]] - Community unemployment fact
- [[Building Permits]] - Permits by area
- [[Chicago Data Portal Integration]] - Data source

### Architecture Documentation
- [[Data Pipeline/Chicago]] - Ingestion process
- [[Facets/Municipal]] - Data normalization
- [[Storage/Silver]] - Dimensional storage

### External Resources
- [Chicago Community Areas (Wikipedia)](https://en.wikipedia.org/wiki/Community_areas_in_Chicago)
- [Chicago Data Portal](https://data.cityofchicago.org/)

---

**Tags:** #municipal #component/model #concept/dimensional-modeling #concept/geography #pattern/geographic

**Last Updated:** 2024-11-08
**Table:** dim_community_area
**Grain:** One row per community area (77 total)
