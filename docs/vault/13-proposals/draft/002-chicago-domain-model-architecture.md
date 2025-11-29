# Proposal: Chicago Domain Model Architecture

**Status**: Draft
**Author**: Claude
**Date**: 2025-11-29
**Updated**: 2025-11-29
**Priority**: High

---

## Summary

This proposal defines a comprehensive domain model architecture for Chicago municipal data, implementing a hierarchical inheritance structure with city finance as the base and department-specific models (Police, Fire, Infrastructure, Education) extending it. Each department model will have specialized fact tables for incidents, arrests, performance metrics, and geographic analysis.

---

## Motivation

### Current State

The existing `city_finance` model is a flat v1.x implementation with:
- 2 dimensions (community_area, permit_type)
- 5 fact tables (local_unemployment, building_permits, business_licenses, economic_indicators)
- No departmental separation
- No inheritance structure
- Limited geographic integration

### Why Change?

1. **Budget Data Requirement**: Chicago provides annual budget data per API endpoint - need structured ingestion
2. **Department Specialization**: Police arrests ≠ Fire incidents ≠ Infrastructure repairs
3. **Geographic Analysis**: Need consistent geographic dimensions across all city data
4. **Inheritance Benefits**: Share common city finance logic, specialize per department
5. **Scalability**: Easier to add new departments without modifying base

---

## Detailed Design

### Domain Model Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CORE DIMENSIONS                              │
├─────────────────────────────────────────────────────────────────────┤
│  core.dim_calendar          (time dimension)                        │
│  geography.dim_geography    (proposed - see geography proposal)     │
│  geography.dim_chicago_area (Chicago-specific: wards, districts)    │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CITY FINANCE (BASE MODEL)                       │
├─────────────────────────────────────────────────────────────────────┤
│  city_finance/                                                      │
│  ├── model.yaml           (metadata, inheritance config)            │
│  ├── schema.yaml          (shared dimensions & fact templates)      │
│  ├── graph.yaml           (base relationships)                      │
│  └── measures.yaml        (common financial measures)               │
│                                                                     │
│  Dimensions:                                                        │
│    dim_department          (city departments: Police, Fire, etc.)   │
│    dim_fiscal_year         (FY with budget cycles)                  │
│    dim_budget_category     (operating, capital, grants)             │
│    dim_fund                (general fund, special revenue, etc.)    │
│                                                                     │
│  Facts:                                                             │
│    fact_annual_budget      (appropriations by dept/fund/category)   │
│    fact_budget_execution   (actual vs. budgeted spending)           │
│    fact_revenue            (tax revenue, fees, grants)              │
└─────────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────┬──────────┼───────────┬───────────┐
         ▼           ▼          ▼           ▼           ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   POLICE    │ │    FIRE     │ │INFRASTRUCTURE│ │ EDUCATION   │
│  (inherits) │ │  (inherits) │ │  (inherits)  │ │ (inherits)  │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

### Model Inheritance Structure

#### Base: City Finance Model

**File: `configs/models/city_finance/model.yaml`**
```yaml
model: city_finance
version: 2.0
description: "Base city finance model for Chicago municipal data"

metadata:
  owner: "finance_team"
  domain: "municipal_finance"
  sla_hours: 24
  tags: [chicago, municipal, finance, budget]

components:
  schema: city_finance/schema.yaml
  graph: city_finance/graph.yaml
  measures:
    yaml: city_finance/measures.yaml
    python: city_finance/measures.py

depends_on:
  - core       # Calendar dimension
  - geography  # Geographic dimension (proposed)

storage:
  root: storage/silver/city_finance
  format: parquet

# Define what child models can inherit
exports:
  dimensions:
    - dim_department
    - dim_fiscal_year
    - dim_budget_category
    - dim_fund
  measures:
    - total_budget
    - budget_variance
    - spending_rate
```

**File: `configs/models/city_finance/schema.yaml`**
```yaml
dimensions:
  dim_department:
    description: "City of Chicago departments"
    columns:
      department_id: string          # Primary key
      department_name: string        # Full name
      department_code: string        # Abbreviation (CPD, CFD, etc.)
      department_type: string        # public_safety, infrastructure, services
      parent_department_id: string   # For sub-departments
      budget_unit_code: string       # Budget system identifier
      active: boolean
    primary_key: [department_id]

  dim_fiscal_year:
    description: "Chicago fiscal year (Jan 1 - Dec 31)"
    columns:
      fiscal_year_id: string         # e.g., "FY2024"
      fiscal_year: integer           # 2024
      start_date: date               # 2024-01-01
      end_date: date                 # 2024-12-31
      budget_status: string          # proposed, adopted, amended, closed
      is_current: boolean
    primary_key: [fiscal_year_id]

  dim_budget_category:
    description: "Budget appropriation categories"
    columns:
      category_id: string
      category_name: string          # Personnel, Contractual, Commodities, etc.
      category_type: string          # operating, capital
      is_discretionary: boolean
    primary_key: [category_id]

  dim_fund:
    description: "Municipal funds"
    columns:
      fund_id: string
      fund_name: string              # General Fund, Enterprise Fund, etc.
      fund_type: string              # governmental, proprietary, fiduciary
      is_restricted: boolean
    primary_key: [fund_id]

facts:
  fact_annual_budget:
    description: "Annual budget appropriations by department"
    columns:
      budget_line_id: string
      fiscal_year_id: string         # FK to dim_fiscal_year
      department_id: string          # FK to dim_department
      fund_id: string                # FK to dim_fund
      category_id: string            # FK to dim_budget_category
      appropriation_amount: double   # Budgeted amount
      revised_amount: double         # After amendments
      description: string
    primary_key: [budget_line_id]
    partitions: [fiscal_year_id]

  fact_budget_execution:
    description: "Actual spending vs budget"
    columns:
      execution_id: string
      fiscal_year_id: string
      department_id: string
      fund_id: string
      category_id: string
      period_date: date              # Monthly or quarterly
      budgeted_amount: double
      actual_amount: double
      encumbered_amount: double
      available_amount: double
    primary_key: [execution_id]
    partitions: [period_date]

  fact_revenue:
    description: "City revenue by source"
    columns:
      revenue_id: string
      fiscal_year_id: string
      revenue_source: string         # Property Tax, Sales Tax, Fees, etc.
      fund_id: string
      period_date: date
      budgeted_amount: double
      collected_amount: double
    primary_key: [revenue_id]
    partitions: [period_date]
```

#### Child: Police Department Model

**File: `configs/models/chicago_police/model.yaml`**
```yaml
model: chicago_police
version: 2.0
description: "Chicago Police Department - Crime, arrests, and public safety"

inherits_from: city_finance    # Inherit base city finance

metadata:
  owner: "public_safety_team"
  domain: "public_safety"
  department_filter: "department_code = 'CPD'"
  sla_hours: 12
  tags: [chicago, police, crime, public_safety]

components:
  schema: chicago_police/schema.yaml      # Extends city_finance schema
  graph: chicago_police/graph.yaml
  measures:
    yaml: chicago_police/measures.yaml
    python: chicago_police/measures.py

depends_on:
  - core
  - geography
  - city_finance    # Explicit dependency on base

storage:
  root: storage/silver/chicago_police
  format: parquet
```

**File: `configs/models/chicago_police/schema.yaml`**
```yaml
extends: city_finance.schema   # Inherit all base dimensions

dimensions:
  dim_crime_type:
    description: "IUCR crime classification"
    columns:
      crime_type_id: string
      iucr_code: string              # Illinois Uniform Crime Reporting code
      primary_type: string           # THEFT, BATTERY, etc.
      secondary_type: string         # More specific description
      fbi_code: string               # FBI classification
      is_index_crime: boolean        # Part 1 crimes
      is_domestic: boolean
    primary_key: [crime_type_id]

  dim_beat:
    description: "Police beats (patrol areas)"
    columns:
      beat_id: string
      beat_number: string            # 4-digit beat number
      district_id: string            # FK to dim_police_district
      community_area_id: string      # FK to geography.dim_chicago_area
      area_sq_miles: double
    primary_key: [beat_id]

  dim_police_district:
    description: "Police districts"
    columns:
      district_id: string
      district_number: integer       # 1-25
      district_name: string
      station_address: string
      commander: string
      latitude: double
      longitude: double
    primary_key: [district_id]

facts:
  fact_crime_incidents:
    description: "Reported crime incidents"
    columns:
      case_number: string            # Chicago PD case number
      incident_date: date
      incident_datetime: timestamp
      crime_type_id: string          # FK to dim_crime_type
      beat_id: string                # FK to dim_beat
      block: string                  # Redacted street address
      location_description: string   # APARTMENT, STREET, etc.
      latitude: double
      longitude: double
      arrest_made: boolean
      domestic: boolean
      year: integer
      updated_on: timestamp
    primary_key: [case_number]
    partitions: [year]

  fact_arrests:
    description: "Arrest records"
    columns:
      arrest_id: string
      arrest_date: date
      arrest_datetime: timestamp
      crime_type_id: string
      beat_id: string
      charge_1_iucr: string
      charge_1_description: string
      charge_2_iucr: string
      charge_2_description: string
      latitude: double
      longitude: double
      year: integer
    primary_key: [arrest_id]
    partitions: [year]

  fact_use_of_force:
    description: "Use of force incidents"
    columns:
      incident_id: string
      incident_date: date
      district_id: string
      beat_id: string
      force_type: string             # Firearm, Taser, OC Spray, etc.
      subject_injured: boolean
      officer_injured: boolean
      subject_armed: boolean
      year: integer
    primary_key: [incident_id]
    partitions: [year]

  # Inherited from city_finance (filtered to CPD):
  # fact_department_budget (auto-filtered by department_code = 'CPD')
```

**File: `configs/models/chicago_police/measures.yaml`**
```yaml
extends: city_finance.measures   # Inherit base financial measures

simple_measures:
  total_crimes:
    type: simple
    source: fact_crime_incidents.case_number
    aggregation: count_distinct
    format: "#,##0"

  total_arrests:
    type: simple
    source: fact_arrests.arrest_id
    aggregation: count_distinct
    format: "#,##0"

  arrest_rate:
    type: computed
    formula: "(total_arrests / total_crimes) * 100"
    format: "#,##0.0%"

  crimes_per_capita:
    type: computed
    formula: "total_crimes / population"  # population from geography
    format: "#,##0.00"

python_measures:
  crime_trend:
    function: "chicago_police.measures.calculate_crime_trend"
    params:
      window_days: 30

  hotspot_score:
    function: "chicago_police.measures.calculate_hotspot_score"
    params:
      radius_miles: 0.5
```

#### Child: Fire Department Model

**File: `configs/models/chicago_fire/model.yaml`**
```yaml
model: chicago_fire
version: 2.0
description: "Chicago Fire Department - Fire incidents and EMS responses"

inherits_from: city_finance

metadata:
  owner: "public_safety_team"
  domain: "public_safety"
  department_filter: "department_code = 'CFD'"
  tags: [chicago, fire, ems, public_safety]

components:
  schema: chicago_fire/schema.yaml
  graph: chicago_fire/graph.yaml
  measures:
    yaml: chicago_fire/measures.yaml
```

**File: `configs/models/chicago_fire/schema.yaml`**
```yaml
extends: city_finance.schema

dimensions:
  dim_incident_type:
    description: "Fire/EMS incident types"
    columns:
      incident_type_id: string
      incident_type_code: string     # NFIRS code
      incident_type_name: string     # Structure Fire, EMS, etc.
      category: string               # fire, ems, hazmat, rescue
      severity_level: integer        # 1-5
    primary_key: [incident_type_id]

  dim_fire_station:
    description: "Fire stations and battalions"
    columns:
      station_id: string
      station_number: integer
      battalion_id: string
      address: string
      latitude: double
      longitude: double
      apparatus_count: integer
    primary_key: [station_id]

facts:
  fact_fire_incidents:
    description: "Fire incident reports"
    columns:
      incident_id: string
      incident_date: date
      incident_datetime: timestamp
      incident_type_id: string
      station_id: string             # First responding station
      community_area_id: string
      address: string
      latitude: double
      longitude: double
      property_loss: double
      contents_loss: double
      civilian_injuries: integer
      civilian_fatalities: integer
      firefighter_injuries: integer
      response_time_seconds: integer
      year: integer
    primary_key: [incident_id]
    partitions: [year]

  fact_ems_calls:
    description: "Emergency medical service calls"
    columns:
      call_id: string
      call_date: date
      call_datetime: timestamp
      call_type: string              # ALS, BLS, etc.
      station_id: string
      community_area_id: string
      dispatch_time_seconds: integer
      response_time_seconds: integer
      transport_destination: string
      patient_outcome: string
      year: integer
    primary_key: [call_id]
    partitions: [year]
```

#### Child: Infrastructure Model

**File: `configs/models/chicago_infrastructure/model.yaml`**
```yaml
model: chicago_infrastructure
version: 2.0
description: "Chicago infrastructure - Streets, water, buildings, 311 requests"

inherits_from: city_finance

metadata:
  owner: "infrastructure_team"
  domain: "infrastructure"
  department_filter: "department_code IN ('CDOT', 'DWM', 'DOB')"
  tags: [chicago, infrastructure, 311, streets, water]

components:
  schema: chicago_infrastructure/schema.yaml
  graph: chicago_infrastructure/graph.yaml
  measures:
    yaml: chicago_infrastructure/measures.yaml
```

**File: `configs/models/chicago_infrastructure/schema.yaml`**
```yaml
extends: city_finance.schema

dimensions:
  dim_service_request_type:
    description: "311 service request types"
    columns:
      request_type_id: string
      request_type_code: string
      request_type_name: string      # Pothole, Graffiti, Tree Trim, etc.
      department_id: string          # Responsible department
      sla_days: integer              # Expected resolution time
    primary_key: [request_type_id]

  dim_asset_type:
    description: "Infrastructure asset types"
    columns:
      asset_type_id: string
      asset_type_name: string        # Street, Water Main, Bridge, etc.
      category: string               # transportation, water, buildings
      expected_lifespan_years: integer
    primary_key: [asset_type_id]

facts:
  fact_311_requests:
    description: "311 service requests"
    columns:
      request_id: string
      created_date: date
      created_datetime: timestamp
      closed_date: date
      request_type_id: string
      community_area_id: string
      ward: integer
      latitude: double
      longitude: double
      status: string                 # Open, Completed, Duplicate
      days_to_close: integer
      year: integer
    primary_key: [request_id]
    partitions: [year]

  fact_street_repairs:
    description: "Street repair and maintenance"
    columns:
      repair_id: string
      repair_date: date
      repair_type: string            # Pothole, Resurfacing, etc.
      street_segment_id: string
      community_area_id: string
      cost: double
      area_sq_feet: double
      contractor: string
      year: integer
    primary_key: [repair_id]
    partitions: [year]

  fact_building_violations:
    description: "Building code violations"
    columns:
      violation_id: string
      violation_date: date
      violation_type: string
      property_address: string
      community_area_id: string
      latitude: double
      longitude: double
      disposition: string
      fine_amount: double
      year: integer
    primary_key: [violation_id]
    partitions: [year]
```

#### Child: Education Model

**File: `configs/models/chicago_education/model.yaml`**
```yaml
model: chicago_education
version: 2.0
description: "Chicago Public Schools - Performance, demographics, facilities"

inherits_from: city_finance

metadata:
  owner: "education_team"
  domain: "education"
  department_filter: "department_code = 'CPS'"
  tags: [chicago, education, schools, cps]

components:
  schema: chicago_education/schema.yaml
  graph: chicago_education/graph.yaml
  measures:
    yaml: chicago_education/measures.yaml
```

**File: `configs/models/chicago_education/schema.yaml`**
```yaml
extends: city_finance.schema

dimensions:
  dim_school:
    description: "CPS schools"
    columns:
      school_id: string              # CPS school ID
      school_name: string
      school_type: string            # Elementary, High School, Charter
      network: string                # CPS network
      community_area_id: string
      ward: integer
      address: string
      latitude: double
      longitude: double
      enrollment: integer
      grades_served: string          # K-8, 9-12, etc.
      is_title_i: boolean
      is_magnet: boolean
    primary_key: [school_id]

  dim_grade_level:
    columns:
      grade_level_id: string
      grade_level: integer           # K=0, 1-12
      grade_name: string             # Kindergarten, 1st Grade, etc.
      level: string                  # elementary, middle, high
    primary_key: [grade_level_id]

facts:
  fact_school_performance:
    description: "Annual school performance metrics"
    columns:
      performance_id: string
      school_id: string
      school_year: string            # 2023-2024
      graduation_rate: double
      attendance_rate: double
      college_enrollment_rate: double
      sqrp_rating: string            # 1+, 1, 2+, 2, 3
      growth_reading: double
      growth_math: double
    primary_key: [performance_id]
    partitions: [school_year]

  fact_test_scores:
    description: "Standardized test results"
    columns:
      score_id: string
      school_id: string
      school_year: string
      grade_level_id: string
      test_name: string              # IAR, SAT, PSAT
      subject: string                # Reading, Math
      proficiency_rate: double
      students_tested: integer
    primary_key: [score_id]
    partitions: [school_year]

  fact_school_demographics:
    description: "Student demographics by school"
    columns:
      demographics_id: string
      school_id: string
      school_year: string
      total_students: integer
      pct_low_income: double
      pct_english_learners: double
      pct_special_ed: double
      pct_african_american: double
      pct_hispanic: double
      pct_white: double
      pct_asian: double
    primary_key: [demographics_id]
    partitions: [school_year]
```

### Data Ingestion for Budget Data

**Chicago Budget API Endpoints (Annual):**

| Fiscal Year | Dataset ID | API Endpoint |
|-------------|-----------|--------------|
| FY2024 | `hbz4-24jd` | `/resource/hbz4-24jd.json` |
| FY2023 | `gf8t-xt9j` | `/resource/gf8t-xt9j.json` |
| FY2022 | `mpxx-yq9h` | `/resource/mpxx-yq9h.json` |
| ... | ... | ... |

**New Facet: `budget_facet.py`**
```python
from datapipelines.facets.base_facet import BaseFacet
from typing import Dict, List

class ChicagoBudgetFacet(BaseFacet):
    """Normalize Chicago annual budget data."""

    # Mapping of fiscal years to dataset IDs
    BUDGET_DATASETS = {
        2024: "hbz4-24jd",
        2023: "gf8t-xt9j",
        2022: "mpxx-yq9h",
        2021: "vekc-2kxv",
        2020: "fg6s-gzvg",
    }

    SPARK_CASTS = {
        "appropriation": "double",
        "revised_appropriation": "double",
        "expenditure": "double",
    }

    COLUMN_MAPPING = {
        "fund_type": "fund_type",
        "fund_code": "fund_id",
        "fund_description": "fund_name",
        "department_code": "department_id",
        "department_description": "department_name",
        "appropriation_account": "category_id",
        "appropriation_account_description": "category_name",
        "appropriation": "appropriation_amount",
        "revised_appropriation": "revised_amount",
        "expenditure": "actual_amount",
    }

    def __init__(self, fiscal_year: int):
        self.fiscal_year = fiscal_year
        self.dataset_id = self.BUDGET_DATASETS.get(fiscal_year)
        if not self.dataset_id:
            raise ValueError(f"No budget dataset for FY{fiscal_year}")

    def calls(self) -> List[Dict]:
        """Generate API calls for budget data."""
        return [{
            "endpoint": f"/resource/{self.dataset_id}.json",
            "params": {"$limit": 50000}  # Budget data is small
        }]

    def postprocess(self, df):
        """Normalize budget data."""
        # Rename columns
        for old, new in self.COLUMN_MAPPING.items():
            if old in df.columns:
                df = df.withColumnRenamed(old, new)

        # Add fiscal year
        df = df.withColumn("fiscal_year", lit(self.fiscal_year))
        df = df.withColumn("fiscal_year_id", lit(f"FY{self.fiscal_year}"))

        # Cast numeric columns
        for col_name, dtype in self.SPARK_CASTS.items():
            if col_name in df.columns:
                df = df.withColumn(col_name, col(col_name).cast(dtype))

        return df
```

---

## Implementation Plan

### Phase 1: Base City Finance Model (Week 1-2)
1. Create modular YAML structure for `city_finance`
2. Implement `ChicagoBudgetFacet` for annual budget ingestion
3. Ingest FY2020-2024 budget data
4. Build base dimensions (department, fiscal_year, fund, category)
5. Create base financial measures

### Phase 2: Police Department Model (Week 3-4)
1. Create `chicago_police` model with inheritance
2. Implement crime and arrest facets
3. Ingest crime incidents (2020-present)
4. Build police-specific dimensions (beats, districts, crime types)
5. Create crime analysis measures

### Phase 3: Fire Department Model (Week 5)
1. Create `chicago_fire` model with inheritance
2. Implement fire incident and EMS facets
3. Ingest fire/EMS data
4. Build fire-specific dimensions

### Phase 4: Infrastructure Model (Week 6)
1. Create `chicago_infrastructure` model
2. Implement 311 and building violation facets
3. Ingest 311 requests and violations
4. Build infrastructure dimensions

### Phase 5: Education Model (Week 7-8)
1. Create `chicago_education` model
2. Implement school performance facets
3. Ingest CPS data
4. Build education dimensions and measures

---

## Chicago Data Portal API Endpoints

| Model | Dataset | Dataset ID | Update Frequency |
|-------|---------|-----------|------------------|
| **Base Finance** | Annual Budget | varies by year | Annual |
| **Police** | Crimes | `ijzp-q8t2` | Daily |
| **Police** | Arrests | `dpt3-jri9` | Daily |
| **Fire** | Fire Incidents | `4srt-4asg` | Daily |
| **Infrastructure** | 311 Requests | `v6vf-nfxy` | Daily |
| **Infrastructure** | Building Violations | `22u3-xenr` | Daily |
| **Education** | School Progress | `dw27-rash` | Annual |

---

## Open Questions

1. Should we include historical budget data (pre-2020)?
2. How far back should we ingest crime data (5 years? 10 years?)?
3. Should ward boundaries be versioned (they change every 10 years)?
4. How to handle data quality issues in older Chicago datasets?

---

## References

- Chicago Data Portal: https://data.cityofchicago.org/
- Existing city_finance model: `/configs/models/city_finance.yaml`
- Chicago Budget API: https://data.cityofchicago.org/browse?tags=budget
