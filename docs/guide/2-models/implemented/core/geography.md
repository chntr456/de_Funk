---
title: "Geography Dimension (Planned)"
tags: [reference, component/model, concept/geography, status/planned]
aliases: ["Geography", "Geographic Dimension", "dim_geography"]
---

# Geography Dimension

---

**Status:** 🔜 Planned Enhancement

The Geography dimension will provide hierarchical geographic data for location-based analysis across all models.

---

## Purpose

---

Enable geographic analysis:
- **Location filtering** - By country, state, city, zip code
- **Hierarchical aggregation** - Roll up from zip → city → state → country
- **Geographic joins** - Connect models via location
- **Spatial analysis** - Distance calculations, proximity queries
- **Regional trends** - Compare performance across geographies

---

## Planned Schema

---

**Table:** `dim_geography` (proposed)
**Primary Key:** `geography_id`
**Grain:** One row per geographic entity

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **geography_id** | string | Unique identifier | "US-IL-CHI-60601" |
| **geography_type** | string | Type: country/state/city/zip | "zip_code" |
| **zip_code** | string | 5-digit zip code | "60601" |
| **city** | string | City name | "Chicago" |
| **state** | string | State abbreviation | "IL" |
| **state_name** | string | Full state name | "Illinois" |
| **country** | string | Country code | "US" |
| **country_name** | string | Full country name | "United States" |
| **latitude** | double | Latitude | 41.8857 |
| **longitude** | double | Longitude | -87.6186 |
| **timezone** | string | IANA timezone | "America/Chicago" |
| **utc_offset** | integer | UTC offset hours | -6 |

---

## Hierarchical Structure

---

```
Country
  └─ State
      └─ City
          └─ Zip Code
              └─ Community Area (Chicago)
```

**Example Hierarchy:**
```
United States (US)
  └─ Illinois (IL)
      └─ Chicago
          └─ 60601
              └─ Loop (Community Area 32)
```

---

## Integration with Existing Models

---

### City Finance Model

**Current:** Community areas have lat/long but no broader geography
**Enhanced:** Link community areas to geography hierarchy

```sql
-- Join community area to geography
SELECT
    ca.community_area_name,
    g.city,
    g.state,
    g.country
FROM dim_community_area ca
JOIN dim_geography g
  ON ca.city = g.city
  AND g.geography_type = 'city'
```

### Company Model

**Current:** No geographic dimension
**Enhanced:** Add company headquarters location

```sql
-- Add to dim_company
ALTER TABLE dim_company ADD COLUMN headquarters_geography_id STRING

-- Query companies by state
SELECT c.company_name, g.state_name
FROM dim_company c
JOIN dim_geography g ON c.headquarters_geography_id = g.geography_id
WHERE g.state = 'CA'
```

### Macro Model

**Current:** National-level only
**Enhanced:** Add state-level economic indicators

```sql
-- State unemployment rates
SELECT
    g.state_name,
    f.date,
    f.unemployment_rate
FROM fact_state_unemployment f
JOIN dim_geography g ON f.geography_id = g.geography_id
WHERE g.geography_type = 'state'
```

---

## Data Sources

---

### Potential Sources

1. **US Census Bureau**
   - Geographic boundaries
   - Zip code to city/state mappings
   - Population by geography

2. **GeoNames**
   - Global city/country data
   - Timezone information
   - Coordinates

3. **OpenStreetMap**
   - Detailed boundary data
   - Points of interest
   - Road networks

4. **USPS**
   - Zip code database
   - Address standardization

---

## Use Cases

---

### Regional Performance

```python
# Compare stock performance by company headquarters state
SELECT
    g.state_name,
    AVG(p.close) as avg_price,
    SUM(p.volume) as total_volume
FROM fact_prices p
JOIN dim_company c ON p.ticker = c.ticker
JOIN dim_geography g ON c.headquarters_geography_id = g.geography_id
WHERE g.geography_type = 'state'
GROUP BY g.state_name
```

### Multi-Geography Analysis

```python
# Compare Chicago community metrics to national trends
SELECT
    'National' as level,
    AVG(unemployment_rate) as avg_unemployment
FROM fact_unemployment  -- National
UNION ALL
SELECT
    'Chicago' as level,
    AVG(unemployment_rate)
FROM fact_local_unemployment  -- Community-level
```

### Distance Calculations

```python
# Find companies within 50 miles of Chicago
import math

def haversine_distance(lat1, lon1, lat2, lon2):
    # Distance calculation
    pass

# Filter by distance
chicago = geography[geography['city'] == 'Chicago'].iloc[0]
companies = dim_company.merge(geography, ...)
nearby = companies[
    companies.apply(
        lambda row: haversine_distance(
            chicago['latitude'], chicago['longitude'],
            row['latitude'], row['longitude']
        ) < 50,
        axis=1
    )
]
```

---

## Implementation Plan

---

### Phase 1: US Geography
- Country, state, city hierarchy
- Major metro areas
- Zip code coverage
- Timezone mapping

### Phase 2: Global Geography
- International countries
- Major cities worldwide
- Currency regions
- Time zones

### Phase 3: Enhanced Chicago
- Link community areas to geography
- Neighborhood to zip code mapping
- Address geocoding

### Phase 4: Spatial Features
- Polygon boundaries
- Distance calculations
- Proximity queries
- Heat mapping support

---

## Related Documentation

---

### Current Models
- [[Community Area]] - Chicago neighborhoods (will integrate)
- [[Calendar]] - Time dimension (complement)
- [[Core Model Overview]] - Parent model

### Planned Features
- Geographic time zones (with [[Calendar]])
- Multi-region support
- Spatial indexing

### Architecture
- [[Bronze Storage]] - Geographic seed data
- [[Silver Storage]] - Geography dimension
- [[Models System]] - Dimensional modeling

---

**Tags:** #reference #component/model #concept/geography #status/planned #architecture/foundation

**Last Updated:** 2024-11-08
**Status:** Planned (not yet implemented)
**Timeline:** Q1 2025 (tentative)
