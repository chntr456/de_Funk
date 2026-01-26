# Proposal: Core Geography Dimension

**Status**: Draft
**Author**: Claude
**Date**: 2025-11-29
**Updated**: 2025-11-29
**Priority**: High

---

## Summary

This proposal defines a core geography dimension model following the calendar dimension pattern, providing hierarchical geographic data (country → state → county → city → zip code) with optional GIS capabilities and Chicago-specific administrative boundaries (community areas, wards, police districts).

---

## Motivation

### Current State

Geographic data is scattered across models with no unified dimension:

| Model | Geography Fields | Limitations |
|-------|------------------|-------------|
| `city_finance` | community_area, lat/lon | Chicago-only, flat structure |
| `company` | headquarters_state, headquarters_city | No hierarchy, no codes |
| `stocks` | (none) | Via company only |
| All models | latitude, longitude as doubles | No spatial operations |

### Problems

1. **No Unified Geography**: Each model implements geography differently
2. **No Hierarchy**: Can't roll up from zip → city → county → state
3. **No Standard Codes**: Missing FIPS, GNIS, ISO codes
4. **No GIS Operations**: Lat/lon stored as numbers, can't compute distances
5. **Chicago-Specific Only**: No US-wide geography for company/securities data

### Benefits of Change

1. **Consistent foreign keys** across all models
2. **Hierarchical drill-down** in analytics
3. **Standard identifiers** (FIPS, ZIP, Census)
4. **Optional GIS** for spatial analysis
5. **Foundation** for geographic filtering in notebooks

---

## Detailed Design

### Following the Calendar Pattern

The calendar dimension (`core/model.py` + `core/builders/calendar_builder.py`) provides an excellent pattern:

```
configs/models/core.yaml          ← YAML configuration
models/implemented/core/
├── model.py                      ← Convenience methods
└── builders/
    └── calendar_builder.py       ← Dimension generator
```

### Geography Model Structure

```
configs/models/geography/
├── model.yaml                    ← Main configuration
├── schema.yaml                   ← Dimension schemas
├── graph.yaml                    ← Relationships
└── measures.yaml                 ← Geographic measures

models/implemented/geography/
├── __init__.py
├── model.py                      ← GeographyModel class
└── builders/
    ├── __init__.py
    ├── us_geography_builder.py   ← US states/counties/cities
    └── chicago_geography_builder.py  ← Chicago-specific areas
```

### Schema Definition

**File: `configs/models/geography/schema.yaml`**

```yaml
dimensions:
  # ========================================
  # Core US Geography Hierarchy
  # ========================================
  dim_geography:
    description: "Unified geographic hierarchy dimension"
    columns:
      # Primary Key
      geography_id: string           # Composite: {level}_{code}

      # Hierarchy Level
      level: integer                 # 1=country, 2=state, 3=county, 4=city, 5=zip
      level_name: string             # "country", "state", "county", "city", "zip"

      # Identifiers (at least one per level)
      fips_code: string              # 2-digit state, 5-digit county
      iso_code: string               # ISO 3166-1/2 (US, US-IL)
      gnis_id: string                # USGS Geographic Names ID
      zip_code: string               # 5-digit ZIP

      # Names
      name: string                   # Primary name at this level
      full_name: string              # "Chicago, Cook County, IL"

      # Parent Reference (self-referential)
      parent_geography_id: string    # FK to parent level

      # Denormalized Hierarchy (for query convenience)
      country_code: string           # "US"
      country_name: string           # "United States"
      state_code: string             # "IL"
      state_name: string             # "Illinois"
      state_fips: string             # "17"
      county_code: string            # "031"
      county_name: string            # "Cook County"
      county_fips: string            # "17031"
      city_name: string              # "Chicago"
      city_fips: string              # "1714000"

      # Point Geometry (centroid)
      latitude: double
      longitude: double

      # Demographics (optional, from Census)
      population: long
      area_sq_miles: double
      population_density: double

      # Metadata
      is_active: boolean             # For historical boundaries
      effective_date: date           # When boundary became effective

    primary_key: [geography_id]
    indexes:
      - [fips_code]
      - [zip_code]
      - [state_code]
      - [parent_geography_id]
    tags: [dim, geography, hierarchy]

  # ========================================
  # Chicago-Specific Administrative Areas
  # ========================================
  dim_chicago_area:
    description: "Chicago administrative areas (community areas, wards, police districts)"
    columns:
      # Primary Key
      area_id: string                # "{type}_{number}"

      # Area Classification
      area_type: string              # "community_area", "ward", "police_district", "beat"
      area_number: integer           # 1-77 for community areas, 1-50 for wards
      area_name: string              # "Rogers Park", "Ward 1", etc.

      # Parent References
      parent_area_id: string         # For beats → district → area hierarchy
      geography_id: string           # FK to dim_geography (Chicago city)

      # Demographics
      population: long
      area_sq_miles: double
      housing_units: long
      median_income: double

      # Centroid
      latitude: double
      longitude: double

      # GIS (optional - requires geopandas)
      # boundary_geojson: string     # GeoJSON polygon (if GIS enabled)

    primary_key: [area_id]
    indexes:
      - [area_type, area_number]
    tags: [dim, geography, chicago]

  # ========================================
  # ZIP Code to Geography Mapping
  # ========================================
  dim_zip_mapping:
    description: "ZIP code to geographic area mapping (many-to-many)"
    columns:
      zip_code: string               # 5-digit ZIP
      geography_id: string           # FK to dim_geography
      chicago_area_id: string        # FK to dim_chicago_area (if in Chicago)
      coverage_pct: double           # Percentage of ZIP in this area
      is_primary: boolean            # Primary assignment for this ZIP
    primary_key: [zip_code, geography_id]
    tags: [mapping, geography]
```

### Model Configuration

**File: `configs/models/geography/model.yaml`**

```yaml
model: geography
version: 2.0
description: "Core geography dimension with hierarchical US geography and Chicago areas"

metadata:
  owner: "platform_team"
  domain: "core"
  sla_hours: 168  # Weekly refresh acceptable
  tags: [core, geography, dimension, hierarchy]

components:
  schema: geography/schema.yaml
  graph: geography/graph.yaml
  measures:
    yaml: geography/measures.yaml

depends_on:
  - core   # For calendar joins (effective_date filtering)

storage:
  root: storage/silver/geography
  format: parquet

# Builder Configuration
geography_config:
  # US Geography Levels
  levels:
    - level: 1
      name: "country"
      identifiers: [iso_code]
      source: "static"         # Hardcoded (just US for now)

    - level: 2
      name: "state"
      identifiers: [fips_code, iso_code]
      source: "census_api"     # Census Bureau API

    - level: 3
      name: "county"
      identifiers: [fips_code, gnis_id]
      source: "census_api"

    - level: 4
      name: "city"
      identifiers: [fips_code, gnis_id]
      source: "census_api"

    - level: 5
      name: "zip"
      identifiers: [zip_code]
      source: "usps_crosswalk"

  # Chicago-Specific Areas
  chicago_areas:
    - type: "community_area"
      count: 77
      source: "chicago_portal"
      dataset_id: "igwz-8jzy"    # Community area boundaries

    - type: "ward"
      count: 50
      source: "chicago_portal"
      dataset_id: "sp34-6z76"    # Ward boundaries

    - type: "police_district"
      count: 22
      source: "chicago_portal"
      dataset_id: "fthy-xz3r"    # Police district boundaries

    - type: "police_beat"
      count: 279
      source: "chicago_portal"
      dataset_id: "aerh-rz74"    # Police beat boundaries

  # Optional GIS Settings
  gis:
    enabled: false               # Set true if geopandas installed
    coordinate_system: "EPSG:4326"  # WGS 84
    store_boundaries: false      # Store GeoJSON polygons
```

### Builder Implementation

**File: `models/implemented/geography/builders/us_geography_builder.py`**

```python
"""
US Geography Builder - Generates hierarchical geography dimension.

Data Sources:
- US Census Bureau API (states, counties, cities)
- USPS ZIP Code Crosswalk (ZIP codes)
- Census TIGER/Line (boundaries, if GIS enabled)
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import pandas as pd
from pathlib import Path

@dataclass
class GeographyLevel:
    level: int
    name: str
    identifiers: List[str]
    source: str

class USGeographyBuilder:
    """Build US geography hierarchy from Census data."""

    # State FIPS codes (hardcoded for reliability)
    STATES = {
        "01": ("AL", "Alabama"),
        "02": ("AK", "Alaska"),
        "04": ("AZ", "Arizona"),
        # ... all 50 states + DC + territories
        "17": ("IL", "Illinois"),
        "36": ("NY", "New York"),
        "48": ("TX", "Texas"),
    }

    def __init__(self, config: Dict):
        self.config = config
        self.levels = [GeographyLevel(**l) for l in config.get('levels', [])]

    def build(self) -> pd.DataFrame:
        """Build complete geography dimension."""
        records = []

        # Level 1: Country
        records.append(self._build_country_record())

        # Level 2: States
        records.extend(self._build_state_records())

        # Level 3: Counties (from Census API or static file)
        records.extend(self._build_county_records())

        # Level 4: Cities (major cities from Census)
        records.extend(self._build_city_records())

        # Level 5: ZIP codes (from crosswalk)
        records.extend(self._build_zip_records())

        return pd.DataFrame(records)

    def _build_country_record(self) -> Dict:
        """Build US country record."""
        return {
            'geography_id': 'country_US',
            'level': 1,
            'level_name': 'country',
            'fips_code': None,
            'iso_code': 'US',
            'name': 'United States',
            'full_name': 'United States of America',
            'parent_geography_id': None,
            'country_code': 'US',
            'country_name': 'United States',
            'latitude': 39.8283,
            'longitude': -98.5795,
            'population': 331_000_000,
            'area_sq_miles': 3_796_742,
            'is_active': True,
        }

    def _build_state_records(self) -> List[Dict]:
        """Build state records from FIPS codes."""
        records = []
        for fips, (abbrev, name) in self.STATES.items():
            records.append({
                'geography_id': f'state_{fips}',
                'level': 2,
                'level_name': 'state',
                'fips_code': fips,
                'iso_code': f'US-{abbrev}',
                'name': name,
                'full_name': f'{name}, United States',
                'parent_geography_id': 'country_US',
                'country_code': 'US',
                'country_name': 'United States',
                'state_code': abbrev,
                'state_name': name,
                'state_fips': fips,
                'is_active': True,
            })
        return records

    def _build_county_records(self) -> List[Dict]:
        """Build county records from Census data."""
        # Load from static file or Census API
        # For now, return Illinois counties as example
        counties = self._fetch_census_counties()
        return counties

    def _fetch_census_counties(self) -> List[Dict]:
        """Fetch county data from Census Bureau API."""
        # In production, use Census API:
        # https://api.census.gov/data/2020/acs/acs5?get=NAME,B01003_001E&for=county:*

        # Example: Cook County, IL
        return [{
            'geography_id': 'county_17031',
            'level': 3,
            'level_name': 'county',
            'fips_code': '17031',
            'name': 'Cook County',
            'full_name': 'Cook County, Illinois',
            'parent_geography_id': 'state_17',
            'country_code': 'US',
            'country_name': 'United States',
            'state_code': 'IL',
            'state_name': 'Illinois',
            'state_fips': '17',
            'county_code': '031',
            'county_name': 'Cook County',
            'county_fips': '17031',
            'latitude': 41.8415,
            'longitude': -87.8170,
            'population': 5_275_541,
            'area_sq_miles': 1_635,
            'is_active': True,
        }]

    def _build_city_records(self) -> List[Dict]:
        """Build city records for major cities."""
        # Focus on cities where we have data (Chicago, company HQs)
        return [{
            'geography_id': 'city_1714000',
            'level': 4,
            'level_name': 'city',
            'fips_code': '1714000',
            'gnis_id': '428803',
            'name': 'Chicago',
            'full_name': 'Chicago, Cook County, Illinois',
            'parent_geography_id': 'county_17031',
            'country_code': 'US',
            'country_name': 'United States',
            'state_code': 'IL',
            'state_name': 'Illinois',
            'state_fips': '17',
            'county_code': '031',
            'county_name': 'Cook County',
            'county_fips': '17031',
            'city_name': 'Chicago',
            'city_fips': '1714000',
            'latitude': 41.8781,
            'longitude': -87.6298,
            'population': 2_746_388,
            'area_sq_miles': 234,
            'is_active': True,
        }]

    def _build_zip_records(self) -> List[Dict]:
        """Build ZIP code records from USPS crosswalk."""
        # In production, load from USPS or Census crosswalk
        return []
```

**File: `models/implemented/geography/builders/chicago_geography_builder.py`**

```python
"""
Chicago Geography Builder - Builds Chicago-specific administrative areas.

Data Sources:
- Chicago Data Portal (community areas, wards, police districts)
"""

from typing import List, Dict
import pandas as pd

class ChicagoGeographyBuilder:
    """Build Chicago administrative area dimension."""

    # 77 Community Areas (official)
    COMMUNITY_AREAS = {
        1: "Rogers Park",
        2: "West Ridge",
        3: "Uptown",
        4: "Lincoln Square",
        5: "North Center",
        6: "Lake View",
        7: "Lincoln Park",
        8: "Near North Side",
        9: "Edison Park",
        10: "Norwood Park",
        # ... all 77
        32: "Loop",
        76: "O'Hare",
        77: "Edgewater",
    }

    def __init__(self, config: Dict):
        self.config = config
        self.chicago_areas_config = config.get('chicago_areas', [])

    def build(self) -> pd.DataFrame:
        """Build Chicago area dimension."""
        records = []

        # Community Areas
        records.extend(self._build_community_areas())

        # Wards (1-50)
        records.extend(self._build_wards())

        # Police Districts (1-25, some inactive)
        records.extend(self._build_police_districts())

        # Police Beats (279 active)
        records.extend(self._build_police_beats())

        return pd.DataFrame(records)

    def _build_community_areas(self) -> List[Dict]:
        """Build 77 community area records."""
        records = []
        for num, name in self.COMMUNITY_AREAS.items():
            records.append({
                'area_id': f'community_area_{num}',
                'area_type': 'community_area',
                'area_number': num,
                'area_name': name,
                'parent_area_id': None,
                'geography_id': 'city_1714000',  # Chicago
            })
        return records

    def _build_wards(self) -> List[Dict]:
        """Build 50 ward records."""
        return [
            {
                'area_id': f'ward_{i}',
                'area_type': 'ward',
                'area_number': i,
                'area_name': f'Ward {i}',
                'parent_area_id': None,
                'geography_id': 'city_1714000',
            }
            for i in range(1, 51)
        ]

    def _build_police_districts(self) -> List[Dict]:
        """Build police district records."""
        # Active districts (some numbers are retired)
        active_districts = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
                          14, 15, 16, 17, 18, 19, 20, 22, 24, 25]
        return [
            {
                'area_id': f'police_district_{d}',
                'area_type': 'police_district',
                'area_number': d,
                'area_name': f'District {d}',
                'parent_area_id': None,
                'geography_id': 'city_1714000',
            }
            for d in active_districts
        ]

    def _build_police_beats(self) -> List[Dict]:
        """Build police beat records."""
        # Beats are 4-digit: first 2 = district, last 2 = beat within district
        # Would be loaded from Chicago Data Portal in production
        return []
```

### Model Class

**File: `models/implemented/geography/model.py`**

```python
"""
GeographyModel - Core geography dimension with hierarchy support.

Follows the calendar dimension pattern for consistency.
"""

from models.base.model import BaseModel
from typing import Optional, List, Dict, Any
import pandas as pd

class GeographyModel(BaseModel):
    """
    Geography dimension model with hierarchical US geography
    and Chicago administrative areas.

    Usage:
        model = GeographyModel(connection, storage_cfg, model_cfg)

        # Get all states
        states = model.get_states()

        # Get Illinois counties
        counties = model.get_counties(state='IL')

        # Get Chicago community areas
        areas = model.get_chicago_areas(area_type='community_area')

        # Get geography hierarchy for a location
        hierarchy = model.get_hierarchy(geography_id='city_1714000')
    """

    def get_geography(
        self,
        level: Optional[int] = None,
        level_name: Optional[str] = None,
        state: Optional[str] = None,
        filters: Optional[Dict] = None
    ) -> pd.DataFrame:
        """Get geography records with optional filtering."""
        df = self.get_table('dim_geography')

        if level is not None:
            df = df[df['level'] == level]
        if level_name is not None:
            df = df[df['level_name'] == level_name]
        if state is not None:
            df = df[df['state_code'] == state]
        if filters:
            for col, val in filters.items():
                if isinstance(val, list):
                    df = df[df[col].isin(val)]
                else:
                    df = df[df[col] == val]

        return df.sort_values(['level', 'name'])

    def get_states(self) -> pd.DataFrame:
        """Get all US states."""
        return self.get_geography(level=2)

    def get_counties(self, state: Optional[str] = None) -> pd.DataFrame:
        """Get counties, optionally filtered by state."""
        return self.get_geography(level=3, state=state)

    def get_cities(
        self,
        state: Optional[str] = None,
        min_population: Optional[int] = None
    ) -> pd.DataFrame:
        """Get cities, optionally filtered by state and population."""
        df = self.get_geography(level=4, state=state)
        if min_population:
            df = df[df['population'] >= min_population]
        return df

    def get_zip_codes(
        self,
        state: Optional[str] = None,
        city: Optional[str] = None
    ) -> pd.DataFrame:
        """Get ZIP codes, optionally filtered by state/city."""
        filters = {}
        if state:
            filters['state_code'] = state
        if city:
            filters['city_name'] = city
        return self.get_geography(level=5, filters=filters)

    def get_hierarchy(self, geography_id: str) -> pd.DataFrame:
        """
        Get full hierarchy for a geography (from country down to this level).

        Returns ancestors from country → state → county → city → zip
        """
        df = self.get_table('dim_geography')

        # Find the record
        record = df[df['geography_id'] == geography_id]
        if record.empty:
            return pd.DataFrame()

        # Walk up the hierarchy
        hierarchy = [record.iloc[0].to_dict()]
        parent_id = record.iloc[0]['parent_geography_id']

        while parent_id:
            parent = df[df['geography_id'] == parent_id]
            if parent.empty:
                break
            hierarchy.append(parent.iloc[0].to_dict())
            parent_id = parent.iloc[0]['parent_geography_id']

        return pd.DataFrame(hierarchy[::-1])  # Reverse for top-down

    def get_children(self, geography_id: str) -> pd.DataFrame:
        """Get immediate children of a geography."""
        df = self.get_table('dim_geography')
        return df[df['parent_geography_id'] == geography_id]

    # ========================================
    # Chicago-Specific Methods
    # ========================================

    def get_chicago_areas(
        self,
        area_type: Optional[str] = None,
        area_numbers: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Get Chicago administrative areas.

        Args:
            area_type: Filter by type (community_area, ward, police_district, beat)
            area_numbers: Filter by area numbers
        """
        df = self.get_table('dim_chicago_area')

        if area_type:
            df = df[df['area_type'] == area_type]
        if area_numbers:
            df = df[df['area_number'].isin(area_numbers)]

        return df.sort_values(['area_type', 'area_number'])

    def get_community_areas(self) -> pd.DataFrame:
        """Get all 77 Chicago community areas."""
        return self.get_chicago_areas(area_type='community_area')

    def get_wards(self) -> pd.DataFrame:
        """Get all 50 Chicago wards."""
        return self.get_chicago_areas(area_type='ward')

    def get_police_districts(self) -> pd.DataFrame:
        """Get Chicago police districts."""
        return self.get_chicago_areas(area_type='police_district')

    def get_police_beats(self, district: Optional[int] = None) -> pd.DataFrame:
        """Get police beats, optionally filtered by district."""
        df = self.get_chicago_areas(area_type='beat')
        if district:
            parent_id = f'police_district_{district}'
            df = df[df['parent_area_id'] == parent_id]
        return df

    # ========================================
    # Lookup Methods
    # ========================================

    def lookup_by_zip(self, zip_code: str) -> Dict[str, Any]:
        """
        Look up geographic info for a ZIP code.

        Returns dict with city, county, state info.
        """
        df = self.get_table('dim_geography')
        record = df[df['zip_code'] == zip_code]

        if record.empty:
            return {}

        row = record.iloc[0]
        return {
            'zip_code': zip_code,
            'city': row['city_name'],
            'county': row['county_name'],
            'state': row['state_code'],
            'state_name': row['state_name'],
            'latitude': row['latitude'],
            'longitude': row['longitude'],
        }

    def lookup_by_fips(self, fips_code: str) -> Dict[str, Any]:
        """Look up geographic info by FIPS code."""
        df = self.get_table('dim_geography')
        record = df[df['fips_code'] == fips_code]

        if record.empty:
            return {}

        return record.iloc[0].to_dict()
```

---

## Optional GIS Extension

If `geopandas` is installed, enable spatial operations:

**File: `models/implemented/geography/gis_extension.py`**

```python
"""
GIS Extension for Geography Model.

Requires: pip install geopandas shapely rtree

Provides:
- Distance calculations
- Point-in-polygon tests
- Spatial joins
- Boundary visualization
"""

try:
    import geopandas as gpd
    from shapely.geometry import Point, Polygon
    from shapely.ops import nearest_points
    HAS_GIS = True
except ImportError:
    HAS_GIS = False


class GISExtension:
    """GIS operations for geography model."""

    def __init__(self, model):
        if not HAS_GIS:
            raise ImportError("GIS features require geopandas. Install with: pip install geopandas")
        self.model = model

    def calculate_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
        unit: str = 'miles'
    ) -> float:
        """Calculate great-circle distance between two points."""
        from math import radians, sin, cos, sqrt, atan2

        R = 3959 if unit == 'miles' else 6371  # Earth radius

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    def find_nearest_geography(
        self,
        latitude: float,
        longitude: float,
        level: int = 4,  # Default to city
        limit: int = 5
    ) -> gpd.GeoDataFrame:
        """Find nearest geographies to a point."""
        df = self.model.get_geography(level=level)

        # Create GeoDataFrame with points
        geometry = [Point(row['longitude'], row['latitude'])
                   for _, row in df.iterrows()]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')

        # Calculate distances
        point = Point(longitude, latitude)
        gdf['distance'] = gdf.geometry.distance(point)

        return gdf.nsmallest(limit, 'distance')

    def point_in_chicago_area(
        self,
        latitude: float,
        longitude: float
    ) -> Dict:
        """
        Determine which Chicago areas contain a point.

        Requires boundary polygons to be loaded.
        """
        # Would load GeoJSON boundaries from Chicago Data Portal
        # Return community area, ward, police district for the point
        pass
```

---

## Implementation Plan

### Phase 1: Core Structure (Week 1)
1. Create `geography` model directory structure
2. Implement `USGeographyBuilder` with static US states
3. Create `GeographyModel` class with basic methods
4. Register in model registry

### Phase 2: Census Integration (Week 2)
1. Add Census Bureau API client
2. Populate counties (3,000+) from Census
3. Populate major cities from Census
4. Add ZIP code crosswalk data

### Phase 3: Chicago Areas (Week 3)
1. Implement `ChicagoGeographyBuilder`
2. Ingest community areas from Chicago Data Portal
3. Ingest wards and police districts
4. Link to main geography dimension

### Phase 4: Model Integration (Week 4)
1. Add foreign keys from `city_finance` → `geography`
2. Add foreign keys from `company` → `geography`
3. Update notebook filters for geographic drill-down
4. Add GIS extension (optional)

---

## Open Questions

1. Should we include Puerto Rico and territories as states?
2. How often should Census demographics be refreshed (annually)?
3. Should we store boundary polygons for all counties, or just load on demand?
4. How to handle ZIP codes that cross county/state lines?

---

## References

- US Census Bureau API: https://api.census.gov/
- Chicago Data Portal: https://data.cityofchicago.org/
- FIPS Code Reference: https://www.census.gov/library/reference/code-lists/ansi.html
- Calendar dimension pattern: `/models/implemented/core/`
