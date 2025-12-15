# Proposal 010: Model Standardization & Chicago Actuarial Forecast

**Status**: Draft
**Created**: 2025-12-15
**Author**: Claude (AI Assistant)
**Priority**: High

---

## Executive Summary

This proposal addresses two interconnected goals:

1. **Model Standardization**: Clean up inconsistencies across the codebase - legacy v1.x files, backend branching, missing implementations, and exhibit configuration gaps
2. **Chicago Actuarial Forecast Model**: Redesign `city_finance` into a comprehensive actuarial economic forecast model with core geography dimensions and tax assessment analysis

---

## Part 1: Model Standardization - Current State Assessment

### Component Ratings

| Component | Rating | Issues | Priority |
|-----------|--------|--------|----------|
| **configs/models/** | ⚠️ 6/10 | Mixed v1.x/v2.0, duplicate files, missing Python measures | High |
| **models/implemented/** | ⚠️ 6/10 | Backend branching, inconsistent patterns, orphaned services | High |
| **models/base/** | ✅ 8/10 | Well-structured composition pattern | Low |
| **configs/exhibits/** | ⚠️ 5/10 | Only great_tables has full config, missing base configs | Medium |
| **datapipelines/** | ✅ 7/10 | Consistent facet pattern, some unused endpoints | Medium |
| **core model** | ⚠️ 5/10 | v1.x only, Spark-only code, should be shared infrastructure | High |

---

### Issue 1: Mixed v1.x and v2.0 YAML Configurations

**Current State:**
```
configs/models/
├── core.yaml           # v1.x - NOT migrated
├── company.yaml        # v1.x - DEPRECATED but still exists
├── etf.yaml            # v1.x - DEPRECATED but still exists
├── forecast.yaml       # v1.x - NOT migrated
├── company/            # v2.0 modular ✓
├── stocks/             # v2.0 modular ✓
├── options/            # v2.0 modular ✓
├── etfs/               # v2.0 modular ✓ (note: plural vs singular etf.yaml)
├── futures/            # v2.0 modular ✓
├── macro/              # v2.0 modular ✓
└── city_finance/       # v2.0 modular ✓
```

**Problems:**
- `company.yaml` and `etf.yaml` are deprecated but still present (confusing)
- `core.yaml` and `forecast.yaml` have no v2.0 modular equivalents
- Naming inconsistency: `etf.yaml` (singular) vs `etfs/` (plural)
- Code must handle both patterns - unclear which is authoritative

**Recommended Actions:**

| Action | Files | Effort |
|--------|-------|--------|
| Delete deprecated v1.x files | `company.yaml`, `etf.yaml` | 1 hour |
| Migrate `core` to v2.0 modular | Create `core/` directory | 2 hours |
| Migrate `forecast` to v2.0 modular | Create `forecast/` directory | 2 hours |
| Standardize naming (singular) | Rename `etfs/` → `etf/` OR update refs | 1 hour |

---

### Issue 2: Backend Branching in Implemented Models

**Current State:**
```python
# models/implemented/company/model.py - 6 instances
if self._backend == 'spark':
    return dim_company.filter(dim_company.cik == cik)
else:  # duckdb/pandas
    return dim_company[dim_company['cik'] == cik]

# models/implemented/stocks/model.py - 9 instances
# models/implemented/stocks/measures.py - 6 instances
```

**Problem:** 21+ backend branching statements across implemented models violates DRY and the backend abstraction layer.

**Root Cause:** Models bypass the filter abstraction in `core/session/filters.py`

**Solution - Create Backend-Agnostic Filter Helper:**

```python
# models/base/query_helpers.py (NEW)
"""Backend-agnostic query helpers for model implementations."""

from typing import Any, List, Optional, Union
from core.session.filters import FilterEngine

class QueryHelper:
    """
    Provides backend-agnostic DataFrame operations.

    Usage:
        helper = QueryHelper(self._backend, self.connection)
        result = helper.filter_eq(df, 'ticker', 'AAPL')
        result = helper.filter_in(df, 'sector', ['Tech', 'Finance'])
    """

    def __init__(self, backend: str, connection: Any):
        self.backend = backend
        self.connection = connection
        self._filter_engine = FilterEngine(backend)

    def filter_eq(self, df: Any, column: str, value: Any) -> Any:
        """Filter where column equals value."""
        return self._filter_engine.apply_filter(
            df, {'column': column, 'operator': '=', 'value': value}
        )

    def filter_in(self, df: Any, column: str, values: List[Any]) -> Any:
        """Filter where column is in values list."""
        return self._filter_engine.apply_filter(
            df, {'column': column, 'operator': 'in', 'value': values}
        )

    def filter_range(self, df: Any, column: str,
                     start: Optional[Any] = None,
                     end: Optional[Any] = None) -> Any:
        """Filter where column is between start and end."""
        if start and end:
            return self._filter_engine.apply_filter(
                df, {'column': column, 'operator': 'between', 'value': [start, end]}
            )
        elif start:
            return self._filter_engine.apply_filter(
                df, {'column': column, 'operator': '>=', 'value': start}
            )
        elif end:
            return self._filter_engine.apply_filter(
                df, {'column': column, 'operator': '<=', 'value': end}
            )
        return df

    def select_distinct(self, df: Any, column: str) -> List[Any]:
        """Get distinct values from column as list."""
        if self.backend == 'spark':
            rows = df.select(column).distinct().collect()
            return [getattr(row, column) for row in rows if getattr(row, column)]
        else:
            return df[column].dropna().unique().tolist()

    def order_by(self, df: Any, columns: Union[str, List[str]],
                 ascending: bool = True) -> Any:
        """Order DataFrame by columns."""
        if isinstance(columns, str):
            columns = [columns]

        if self.backend == 'spark':
            from pyspark.sql import functions as F
            order_cols = [F.col(c).asc() if ascending else F.col(c).desc()
                         for c in columns]
            return df.orderBy(*order_cols)
        else:
            return df.sort_values(columns, ascending=ascending)
```

**Refactored Model Example:**
```python
# models/implemented/company/model.py (AFTER)
class CompanyModel(BaseModel):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._query = QueryHelper(self._backend, self.connection)

    def get_company_by_cik(self, cik: str) -> Any:
        """Get company by SEC CIK number."""
        dim_company = self.get_table('dim_company')
        return self._query.filter_eq(dim_company, 'cik', cik)

    def get_companies_by_sector(self, sector: str) -> Any:
        """Get all companies in a sector."""
        dim_company = self.get_table('dim_company')
        return self._query.filter_eq(dim_company, 'sector', sector)

    def list_sectors(self) -> List[str]:
        """Get list of all sectors."""
        dim_company = self.get_table('dim_company')
        return self._query.select_distinct(dim_company, 'sector')
```

---

### Issue 3: Missing Python Measures Implementations

**Current State:**
```yaml
# configs/models/etfs/model.yaml
components:
  measures:
    python: etfs/measures.py  # ❌ FILE DOES NOT EXIST

# configs/models/futures/model.yaml
components:
  measures:
    python: futures/measures.py  # ❌ FILE DOES NOT EXIST
```

**Problem:** YAML references Python measure files that don't exist - will cause runtime errors.

**Solution Options:**
1. **Remove references** - If no Python measures needed, remove from model.yaml
2. **Create stub files** - Create empty measure class files
3. **Implement measures** - Add actual Python measures

**Recommended:** Option 1 for now - remove references since these are skeleton models:

```yaml
# configs/models/etfs/model.yaml (FIXED)
components:
  schema: etfs/schema.yaml
  graph: etfs/graph.yaml
  measures:
    yaml: etfs/measures.yaml
    # python: etfs/measures.py  # REMOVED - not implemented yet
```

---

### Issue 4: Core Model is Spark-Only

**Current State:**
```python
# models/implemented/core/model.py
from pyspark.sql import DataFrame  # ❌ Spark-only import

def get_calendar(self, ...) -> DataFrame:
    df = self.get_dimension_df('dim_calendar')
    df = df.filter(df.date >= date_from)  # ❌ Spark filter syntax
    return df.orderBy('date')  # ❌ Spark orderBy
```

**Problem:** Core model is the foundation for ALL other models but only works with Spark.

**Solution:** Apply QueryHelper pattern (see Issue 2) and use generic type hints:

```python
# models/implemented/core/model.py (FIXED)
from typing import Any, Optional
from models.base.query_helpers import QueryHelper

DataFrame = Any  # Backend-agnostic type

class CoreModel(BaseModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._query = QueryHelper(self._backend, self.connection)

    def get_calendar(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        df = self.get_dimension_df('dim_calendar')
        df = self._query.filter_range(df, 'date', date_from, date_to)
        return self._query.order_by(df, 'date')
```

---

### Issue 5: Company Model Has Orphaned Services

**Current State:**
```
models/implemented/company/
├── model.py
├── services/
│   ├── company_api.py
│   ├── news_api.py
│   └── prices_api.py    # ❌ Uses graph paths not in company model
└── types/
    └── ...
```

**Problem:** `prices_api.py` references `prices_with_company` table that should come from graph definition, but prices are now in `stocks` model (v2.0 redesign).

**Solution Options:**
1. **Delete services/** - These are legacy v1.x patterns
2. **Migrate to stocks model** - Move prices_api to stocks where prices live
3. **Keep as cross-model API** - Update to use session for cross-model access

**Recommended:** Option 1 - Delete and use standard model methods + session cross-model queries

---

### Issue 6: Exhibit Configuration Gaps

**Current State:**
```
configs/exhibits/
├── registry.yaml           # Maps exhibit types to renderers
├── presets/
│   └── great_table.yaml    # ✓ Full preset config
└── themes/
    └── financial.yaml      # ✓ Theme config
```

**Problem:** Only `great_table` has a preset config. Other exhibit types (line_chart, bar_chart, etc.) are registered but have no preset files.

**Solution - Create Base Exhibit Configs:**

```yaml
# configs/exhibits/presets/base.yaml (NEW)
# Base configuration inherited by all exhibit types

defaults:
  # Title/Description
  title: null
  description: null

  # Data source
  source: null  # model.table reference

  # Grid placement
  grid_cell: null

  # Scrolling
  scroll: false
  max_height: null

  # Visibility
  collapsible: false
  collapsed_by_default: false

# configs/exhibits/presets/chart_base.yaml (NEW)
# Base configuration for all chart types

extends: base.yaml

defaults:
  # Axes
  x_axis:
    column: null
    label: null
    type: auto  # auto, linear, log, date, category

  y_axis:
    column: null
    label: null
    type: linear
    format: null  # number, currency, percent

  # Styling
  color_by: null
  color_palette: default  # default, financial, categorical

  # Legend
  show_legend: true
  legend_position: right  # right, bottom, top, left

  # Interactivity
  hover_template: null
  click_action: null

# configs/exhibits/presets/line_chart.yaml (NEW)
extends: chart_base.yaml

defaults:
  # Line-specific
  line_shape: linear  # linear, spline, hv, vh, hvh, vhv
  line_width: 2
  show_markers: false
  marker_size: 6

  # Fill
  fill: none  # none, tozeroy, tonexty

  # Multiple series
  group_by: null

# configs/exhibits/presets/bar_chart.yaml (NEW)
extends: chart_base.yaml

defaults:
  # Bar-specific
  orientation: vertical  # vertical, horizontal
  bar_mode: group  # group, stack, overlay, relative
  bar_gap: 0.2

  # Text
  show_text: false
  text_position: auto  # auto, inside, outside, none
```

---

### Issue 7: No True Primary Keys - Derived Keys Pattern

**Current State:**
```yaml
# configs/models/company/graph.yaml
nodes:
  - id: dim_company
    derive:
      company_id: "CONCAT('COMPANY_', LPAD(cik, 10, '0'))"
```

**Observation:** Primary keys are derived expressions, not declared constraints.

**This is actually correct for this architecture** because:
1. Bronze layer has raw data without guaranteed keys
2. Silver layer derives business keys during transformation
3. Graph definitions specify the derivation logic

**Recommendation:** Document this pattern clearly but no code changes needed. Add to CLAUDE.md:

```markdown
### Primary Key Pattern

Models use **derived business keys** rather than database constraints:
- Bronze: Raw data, may have duplicates
- Silver: Business keys derived via `derive:` in graph.yaml
- Pattern: `CONCAT('{MODEL}_', source_key)` ensures cross-model uniqueness

Example:
- `company_id = CONCAT('COMPANY_', cik)`
- `stock_id = CONCAT('STOCK_', ticker)`
```

---

## Part 2: Chicago Actuarial Forecast Model

### Vision

Transform `city_finance` into a comprehensive **Chicago Economic Actuarial Model** that:

1. **Core Geography**: Neighborhood/community area dimension with hierarchies
2. **Tax Assessment**: Property values and tax streams by geography
3. **City Services**: Analyze service delivery by area (permits, licenses, inspections)
4. **Fiscal Health**: Revenue vs expenditure analysis with actuarial projections
5. **Economic Indicators**: Local unemployment, business activity, development trends

### Data Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BRONZE LAYER                                 │
│  (Raw Chicago Data Portal + Cook County Assessor Data)              │
├─────────────────────────────────────────────────────────────────────┤
│  chicago_community_areas     │ 77 community areas with boundaries   │
│  chicago_neighborhoods       │ Neighborhood to community mapping    │
│  chicago_census_tracts       │ Census tract geography               │
│  chicago_tax_assessments     │ Property assessments by PIN          │
│  chicago_tax_bills           │ Tax bills and payments               │
│  chicago_unemployment        │ Monthly unemployment by area         │
│  chicago_building_permits    │ Permit activity                      │
│  chicago_business_licenses   │ Business license activity            │
│  chicago_city_budget         │ Annual budget allocations            │
│  chicago_expenditures        │ Actual spending by department        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SILVER LAYER                                 │
│                    (chicago_actuarial model)                         │
├─────────────────────────────────────────────────────────────────────┤
│ DIMENSIONS:                                                          │
│  dim_geography           │ Core geography with hierarchy            │
│  dim_property_class      │ Property classification codes            │
│  dim_tax_district        │ Taxing district reference                │
│  dim_service_category    │ City service categories                  │
│  dim_budget_category     │ Budget line item categories              │
│                                                                      │
│ FACTS:                                                               │
│  fact_tax_assessment     │ Property values by geography/year        │
│  fact_tax_collection     │ Tax revenue by district/year             │
│  fact_economic_activity  │ Unemployment, permits, licenses          │
│  fact_city_budget        │ Budget allocations by category           │
│  fact_city_expenditure   │ Actual spending vs budget                │
│                                                                      │
│ ACTUARIAL:                                                           │
│  fact_fiscal_projection  │ Revenue/expense forecasts                │
│  fact_fund_status        │ Fund solvency metrics                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Geography Dimension Design

```yaml
# configs/models/chicago_actuarial/schema.yaml

dimensions:
  dim_geography:
    description: "Chicago geography hierarchy - tracts → neighborhoods → community areas"
    columns:
      # Primary key
      geography_id: string           # GEO_{community_area}_{neighborhood}_{tract}

      # Hierarchy Level 1: Community Area (77 official areas)
      community_area_number: integer  # 1-77 official numbering
      community_area_name: string     # "Loop", "Lincoln Park", "Hyde Park"
      community_area_slug: string     # "loop", "lincoln-park", "hyde-park"

      # Hierarchy Level 2: Neighborhood (informal, many-to-one with community)
      neighborhood_name: string       # "Old Town", "River North", "Streeterville"
      neighborhood_slug: string

      # Hierarchy Level 3: Census Tract
      census_tract: string            # FIPS code
      census_block_group: string

      # Geographic attributes
      ward: integer                   # Political ward (1-50)
      police_district: integer        # CPD district
      zip_code: string
      latitude: double                # Centroid
      longitude: double               # Centroid

      # Classification
      region: string                  # "North Side", "South Side", "West Side", "Central"
      area_type: string               # "residential", "commercial", "industrial", "mixed"

      # Demographics (from census)
      population_estimate: long
      median_household_income: double
      poverty_rate: double

    primary_key: [geography_id]

    # Hierarchy definitions for rollup
    hierarchies:
      location:
        levels: [community_area_name, neighborhood_name, census_tract]
      political:
        levels: [ward, community_area_name]
      service:
        levels: [police_district, community_area_name]
```

### Tax Assessment Fact Design

```yaml
# configs/models/chicago_actuarial/schema.yaml (continued)

facts:
  fact_tax_assessment:
    description: "Property tax assessments aggregated by geography and year"
    columns:
      # Keys
      assessment_id: string          # {geography_id}_{tax_year}_{property_class}
      geography_id: string           # FK to dim_geography
      tax_year: integer
      property_class_code: string    # FK to dim_property_class

      # Assessment values
      parcel_count: long             # Number of properties
      total_land_value: double       # Assessed land value
      total_building_value: double   # Assessed building value
      total_assessed_value: double   # Total assessed value (land + building)
      total_market_value: double     # Estimated market value

      # Assessment ratios
      assessment_ratio: double       # Assessed / Market
      avg_value_per_parcel: double

      # Year-over-year
      yoy_value_change: double       # Percentage change from prior year
      yoy_parcel_change: integer     # Net new/demolished parcels

      # Exemptions
      total_exemptions: double       # Homeowner, senior, etc.
      net_taxable_value: double      # Assessed - Exemptions

    primary_key: [assessment_id]

    # Grain: One row per geography × year × property class
    grain:
      - geography_id
      - tax_year
      - property_class_code

  fact_tax_collection:
    description: "Property tax collections by taxing district"
    columns:
      collection_id: string
      geography_id: string           # FK to dim_geography
      tax_district_id: string        # FK to dim_tax_district
      tax_year: integer
      collection_year: integer       # Year actually collected (may lag)

      # Levy and collection
      tax_levy: double               # Amount levied
      tax_collected: double          # Amount collected
      collection_rate: double        # Collected / Levy

      # By fund type
      education_levy: double         # School portion
      municipal_levy: double         # City portion
      county_levy: double            # Cook County portion
      special_district_levy: double  # TIF, SSA, etc.

      # Rates
      composite_tax_rate: double     # Total rate per $100 EAV
      education_rate: double
      municipal_rate: double
      county_rate: double

    primary_key: [collection_id]
```

### Python Measures for Actuarial Analysis

```python
# models/implemented/chicago_actuarial/measures.py

"""
Chicago Actuarial Model - Python Measures

Provides actuarial calculations for fiscal health analysis:
- Revenue projections
- Expenditure forecasts
- Fund solvency analysis
- Tax base growth modeling
"""

from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd
from scipy import stats

class ChicagoActuarialMeasures:
    """Python measures for Chicago actuarial analysis."""

    def __init__(self, model):
        self.model = model

    # ================================================================
    # TAX BASE ANALYSIS
    # ================================================================

    def calculate_tax_base_growth(
        self,
        geography_id: Optional[str] = None,
        years: int = 5,
        method: str = 'cagr',
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate tax base growth rate by geography.

        Args:
            geography_id: Filter to specific geography (optional)
            years: Number of years for growth calculation
            method: 'cagr' (compound annual) or 'linear' (regression)

        Returns:
            DataFrame with geography, growth_rate, confidence metrics
        """
        assessments = self.model.get_table('fact_tax_assessment')

        # Filter and aggregate
        df = assessments.groupby(['geography_id', 'tax_year']).agg({
            'total_assessed_value': 'sum'
        }).reset_index()

        if geography_id:
            df = df[df['geography_id'] == geography_id]

        # Calculate growth by geography
        results = []
        for geo_id in df['geography_id'].unique():
            geo_data = df[df['geography_id'] == geo_id].sort_values('tax_year')

            if len(geo_data) >= 2:
                values = geo_data['total_assessed_value'].values
                years_data = geo_data['tax_year'].values

                if method == 'cagr':
                    # Compound Annual Growth Rate
                    n_years = years_data[-1] - years_data[0]
                    if n_years > 0 and values[0] > 0:
                        cagr = (values[-1] / values[0]) ** (1 / n_years) - 1
                    else:
                        cagr = 0
                    growth_rate = cagr

                else:  # linear regression
                    slope, intercept, r_value, p_value, std_err = stats.linregress(
                        years_data, values
                    )
                    # Convert slope to percentage growth
                    avg_value = np.mean(values)
                    growth_rate = slope / avg_value if avg_value > 0 else 0

                results.append({
                    'geography_id': geo_id,
                    'growth_rate': growth_rate,
                    'latest_value': values[-1],
                    'earliest_value': values[0],
                    'years_analyzed': len(values)
                })

        return pd.DataFrame(results)

    def project_tax_revenue(
        self,
        geography_id: Optional[str] = None,
        projection_years: int = 10,
        growth_scenario: str = 'baseline',  # baseline, optimistic, pessimistic
        **kwargs
    ) -> pd.DataFrame:
        """
        Project future tax revenue by geography.

        Uses historical growth rates with scenario adjustments.

        Args:
            geography_id: Filter to specific geography
            projection_years: Years to project forward
            growth_scenario: Scenario for growth assumptions

        Returns:
            DataFrame with year, projected_revenue, confidence_low, confidence_high
        """
        # Get historical growth
        growth_df = self.calculate_tax_base_growth(geography_id=geography_id)

        # Get latest collection data
        collections = self.model.get_table('fact_tax_collection')
        latest = collections.groupby('geography_id').agg({
            'tax_collected': 'last',
            'tax_year': 'max'
        }).reset_index()

        # Merge and project
        projections = []

        # Scenario adjustments
        scenario_factors = {
            'optimistic': 1.2,    # 20% above baseline
            'baseline': 1.0,
            'pessimistic': 0.7    # 30% below baseline
        }
        factor = scenario_factors.get(growth_scenario, 1.0)

        for _, row in growth_df.iterrows():
            geo_id = row['geography_id']
            base_growth = row['growth_rate'] * factor

            geo_latest = latest[latest['geography_id'] == geo_id]
            if len(geo_latest) == 0:
                continue

            base_value = geo_latest['tax_collected'].values[0]
            base_year = geo_latest['tax_year'].values[0]

            for year_offset in range(1, projection_years + 1):
                projected_year = base_year + year_offset
                projected_value = base_value * ((1 + base_growth) ** year_offset)

                # Confidence bands widen with time
                uncertainty = 0.05 * year_offset  # 5% per year

                projections.append({
                    'geography_id': geo_id,
                    'projection_year': projected_year,
                    'projected_revenue': projected_value,
                    'confidence_low': projected_value * (1 - uncertainty),
                    'confidence_high': projected_value * (1 + uncertainty),
                    'scenario': growth_scenario
                })

        return pd.DataFrame(projections)

    # ================================================================
    # FISCAL HEALTH METRICS
    # ================================================================

    def calculate_fiscal_stress_index(
        self,
        geography_id: Optional[str] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate fiscal stress index combining multiple indicators.

        Components:
        - Tax base stability (volatility of assessed values)
        - Collection rate performance
        - Economic activity (unemployment, permits)
        - Dependency ratio (exemptions / gross assessed)

        Returns:
            DataFrame with geography and stress_index (0-100, higher = more stress)
        """
        results = []

        # Get required data
        assessments = self.model.get_table('fact_tax_assessment')
        collections = self.model.get_table('fact_tax_collection')
        economic = self.model.get_table('fact_economic_activity')

        geographies = assessments['geography_id'].unique()

        for geo_id in geographies:
            if geography_id and geo_id != geography_id:
                continue

            # 1. Tax base volatility (std dev of YoY changes)
            geo_assess = assessments[assessments['geography_id'] == geo_id]
            if 'yoy_value_change' in geo_assess.columns:
                volatility = geo_assess['yoy_value_change'].std()
                volatility_score = min(volatility * 100, 25)  # Cap at 25 points
            else:
                volatility_score = 12.5  # Neutral

            # 2. Collection rate (lower = more stress)
            geo_collect = collections[collections['geography_id'] == geo_id]
            if len(geo_collect) > 0:
                avg_collection_rate = geo_collect['collection_rate'].mean()
                collection_score = (1 - avg_collection_rate) * 25  # 25 points if 0%
            else:
                collection_score = 12.5

            # 3. Unemployment (higher = more stress)
            geo_econ = economic[economic['geography_id'] == geo_id]
            if 'unemployment_rate' in geo_econ.columns:
                avg_unemployment = geo_econ['unemployment_rate'].mean()
                unemployment_score = min(avg_unemployment * 2.5, 25)  # 10% = 25 pts
            else:
                unemployment_score = 12.5

            # 4. Exemption dependency (higher = more stress)
            if len(geo_assess) > 0:
                total_assessed = geo_assess['total_assessed_value'].sum()
                total_exempt = geo_assess['total_exemptions'].sum()
                exemption_ratio = total_exempt / total_assessed if total_assessed > 0 else 0
                exemption_score = exemption_ratio * 25
            else:
                exemption_score = 12.5

            stress_index = (
                volatility_score +
                collection_score +
                unemployment_score +
                exemption_score
            )

            results.append({
                'geography_id': geo_id,
                'stress_index': min(stress_index, 100),
                'volatility_component': volatility_score,
                'collection_component': collection_score,
                'unemployment_component': unemployment_score,
                'exemption_component': exemption_score,
                'risk_level': (
                    'Low' if stress_index < 25 else
                    'Moderate' if stress_index < 50 else
                    'Elevated' if stress_index < 75 else
                    'High'
                )
            })

        return pd.DataFrame(results)

    def calculate_fund_solvency(
        self,
        fund_type: str = 'general',  # general, pension, capital
        projection_years: int = 30,
        **kwargs
    ) -> pd.DataFrame:
        """
        Actuarial solvency analysis for city funds.

        Models:
        - Projected revenues
        - Projected expenditures (with inflation)
        - Fund balance trajectory
        - Years until insolvency (if applicable)

        Returns:
            DataFrame with year, fund_balance, funded_ratio, solvency_status
        """
        # This would integrate with city budget data
        # Simplified projection model

        budget = self.model.get_table('fact_city_budget')
        expenditure = self.model.get_table('fact_city_expenditure')

        # Get latest fund balance and flows
        fund_data = budget[budget['fund_type'] == fund_type]

        if len(fund_data) == 0:
            return pd.DataFrame()

        latest = fund_data.sort_values('fiscal_year').iloc[-1]
        current_balance = latest.get('fund_balance', 0)
        current_revenue = latest.get('total_revenue', 0)
        current_expense = latest.get('total_expense', 0)

        # Projection parameters
        revenue_growth = 0.02  # 2% annual
        expense_growth = 0.035  # 3.5% annual (faster than revenue)

        projections = []
        balance = current_balance

        for year_offset in range(projection_years + 1):
            projected_revenue = current_revenue * ((1 + revenue_growth) ** year_offset)
            projected_expense = current_expense * ((1 + expense_growth) ** year_offset)

            net_flow = projected_revenue - projected_expense
            balance = balance + net_flow if year_offset > 0 else balance

            # For pension funds, calculate funded ratio
            if fund_type == 'pension':
                # Simplified: assume liability grows at 4%
                liability = current_balance * 2 * ((1.04) ** year_offset)
                funded_ratio = balance / liability if liability > 0 else 0
            else:
                funded_ratio = None

            projections.append({
                'projection_year': latest['fiscal_year'] + year_offset,
                'projected_revenue': projected_revenue,
                'projected_expense': projected_expense,
                'net_flow': net_flow,
                'fund_balance': balance,
                'funded_ratio': funded_ratio,
                'solvency_status': (
                    'Solvent' if balance > 0 else 'Insolvent'
                )
            })

        result = pd.DataFrame(projections)

        # Find years until insolvency
        insolvent_years = result[result['fund_balance'] < 0]
        if len(insolvent_years) > 0:
            years_to_insolvency = (
                insolvent_years.iloc[0]['projection_year'] - latest['fiscal_year']
            )
        else:
            years_to_insolvency = None

        # Add summary metrics
        result.attrs['years_to_insolvency'] = years_to_insolvency
        result.attrs['fund_type'] = fund_type

        return result
```

### Graph Definition

```yaml
# configs/models/chicago_actuarial/graph.yaml

nodes:
  # ============================================
  # DIMENSION NODES
  # ============================================

  - id: dim_geography
    from: bronze.chicago_community_areas
    select:
      geography_id: "CONCAT('GEO_', LPAD(community_area_number, 2, '0'))"
      community_area_number: area_number
      community_area_name: community_area
      community_area_slug: "LOWER(REPLACE(community_area, ' ', '-'))"
      region: side
      ward: primary_ward
      police_district: police_district
      population_estimate: population
      median_household_income: median_income
      poverty_rate: poverty_pct
    unique_key: [geography_id]

  - id: dim_property_class
    from: bronze.chicago_property_classes
    select:
      property_class_code: class_code
      property_class_name: class_description
      property_category: category  # residential, commercial, industrial
      assessment_level: assessment_pct
    unique_key: [property_class_code]

  - id: dim_tax_district
    from: bronze.chicago_tax_districts
    select:
      tax_district_id: "CONCAT('DIST_', agency_number)"
      district_name: agency_name
      district_type: agency_type  # school, municipal, county, special
    unique_key: [tax_district_id]

  # ============================================
  # FACT NODES
  # ============================================

  - id: fact_tax_assessment
    from: bronze.chicago_tax_assessments
    derive:
      assessment_id: "CONCAT(geography_id, '_', tax_year, '_', property_class)"
      geography_id: "CONCAT('GEO_', LPAD(community_area, 2, '0'))"
    aggregate:
      group_by: [geography_id, tax_year, property_class]
      measures:
        parcel_count: "COUNT(*)"
        total_land_value: "SUM(land_assessed)"
        total_building_value: "SUM(building_assessed)"
        total_assessed_value: "SUM(land_assessed + building_assessed)"
        total_market_value: "SUM(market_value)"
        total_exemptions: "SUM(exemption_total)"
    select:
      assessment_id: assessment_id
      geography_id: geography_id
      tax_year: tax_year
      property_class_code: property_class
      parcel_count: parcel_count
      total_land_value: total_land_value
      total_building_value: total_building_value
      total_assessed_value: total_assessed_value
      total_market_value: total_market_value
      total_exemptions: total_exemptions
      net_taxable_value: "total_assessed_value - total_exemptions"
      assessment_ratio: "total_assessed_value / NULLIF(total_market_value, 0)"
      avg_value_per_parcel: "total_assessed_value / NULLIF(parcel_count, 0)"

  - id: fact_tax_collection
    from: bronze.chicago_tax_bills
    derive:
      collection_id: "CONCAT(geography_id, '_', tax_year, '_', tax_district_id)"
      geography_id: "CONCAT('GEO_', LPAD(community_area, 2, '0'))"
      tax_district_id: "CONCAT('DIST_', agency_number)"
    aggregate:
      group_by: [geography_id, tax_year, tax_district_id]
      measures:
        tax_levy: "SUM(tax_amount)"
        tax_collected: "SUM(amount_paid)"
    select:
      collection_id: collection_id
      geography_id: geography_id
      tax_district_id: tax_district_id
      tax_year: tax_year
      tax_levy: tax_levy
      tax_collected: tax_collected
      collection_rate: "tax_collected / NULLIF(tax_levy, 0)"

  - id: fact_economic_activity
    from: bronze.chicago_unemployment
    derive:
      geography_id: "CONCAT('GEO_', LPAD(community_area_number, 2, '0'))"
    select:
      geography_id: geography_id
      activity_date: date
      unemployment_rate: unemployment_rate
      labor_force: labor_force
      employed: employed
      unemployed: unemployed

edges:
  # Dimension relationships
  - from: fact_tax_assessment
    to: dim_geography
    on: geography_id

  - from: fact_tax_assessment
    to: dim_property_class
    on: property_class_code

  - from: fact_tax_collection
    to: dim_geography
    on: geography_id

  - from: fact_tax_collection
    to: dim_tax_district
    on: tax_district_id

  - from: fact_economic_activity
    to: dim_geography
    on: geography_id

  # Cross-model: calendar
  - from: fact_tax_assessment
    to: core.dim_calendar
    on:
      left: tax_year
      right: year
    type: left

  - from: fact_economic_activity
    to: core.dim_calendar
    on:
      left: activity_date
      right: date
    type: left

paths:
  # Pre-joined views for common analysis
  - id: assessments_with_geography
    description: "Tax assessments with full geography context"
    nodes: [fact_tax_assessment, dim_geography, dim_property_class]

  - id: collections_with_context
    description: "Tax collections with geography and district"
    nodes: [fact_tax_collection, dim_geography, dim_tax_district]

  - id: economic_activity_with_geography
    description: "Economic indicators with geography"
    nodes: [fact_economic_activity, dim_geography]
```

---

## Part 3: Implementation Plan

### Phase 1: Codebase Cleanup (Week 1-2)

| Step | Task | Files | Priority |
|------|------|-------|----------|
| 1.1 | Delete deprecated v1.x YAML files | `company.yaml`, `etf.yaml` | High |
| 1.2 | Create `QueryHelper` class | `models/base/query_helpers.py` | High |
| 1.3 | Refactor company model to use QueryHelper | `models/implemented/company/model.py` | High |
| 1.4 | Refactor core model for backend agnostic | `models/implemented/core/model.py` | High |
| 1.5 | Remove missing Python measure refs | `configs/models/etfs/model.yaml`, `futures/model.yaml` | Medium |
| 1.6 | Delete orphaned company services | `models/implemented/company/services/` | Medium |

### Phase 2: Migrate Core to v2.0 Modular (Week 2)

| Step | Task | Files |
|------|------|-------|
| 2.1 | Create `configs/models/core/` directory | New directory |
| 2.2 | Create `core/model.yaml` | Split from `core.yaml` |
| 2.3 | Create `core/schema.yaml` | Split from `core.yaml` |
| 2.4 | Create `core/graph.yaml` | Split from `core.yaml` |
| 2.5 | Create `core/measures.yaml` | Empty (core has no measures) |
| 2.6 | Delete `core.yaml` | After verification |

### Phase 3: Exhibit Configuration (Week 2-3)

| Step | Task | Files |
|------|------|-------|
| 3.1 | Create base exhibit preset | `configs/exhibits/presets/base.yaml` |
| 3.2 | Create chart base preset | `configs/exhibits/presets/chart_base.yaml` |
| 3.3 | Create line chart preset | `configs/exhibits/presets/line_chart.yaml` |
| 3.4 | Create bar chart preset | `configs/exhibits/presets/bar_chart.yaml` |
| 3.5 | Update registry with presets | `configs/exhibits/registry.yaml` |

### Phase 4: Chicago Actuarial Model Foundation (Week 3-4)

| Step | Task | Files |
|------|------|-------|
| 4.1 | Create new model directory | `configs/models/chicago_actuarial/` |
| 4.2 | Create model.yaml | Dependencies: core |
| 4.3 | Create schema.yaml | dim_geography, fact_tax_assessment |
| 4.4 | Create graph.yaml | Node transformations |
| 4.5 | Create measures.yaml | YAML measures |
| 4.6 | Create Python model | `models/implemented/chicago_actuarial/` |

### Phase 5: Data Ingestion (Week 4-5)

| Step | Task | Data Source |
|------|------|-------------|
| 5.1 | Add community area facet | Chicago Data Portal |
| 5.2 | Add tax assessment facet | Cook County Assessor (or Chicago API) |
| 5.3 | Add tax bill facet | Cook County Treasurer |
| 5.4 | Configure endpoints | `configs/pipelines/chicago_endpoints.json` |
| 5.5 | Update storage config | `configs/storage.json` |
| 5.6 | Run initial ingestion | Test with sample data |

### Phase 6: Actuarial Measures (Week 5-6)

| Step | Task | Measure |
|------|------|---------|
| 6.1 | Implement tax base growth | `calculate_tax_base_growth()` |
| 6.2 | Implement revenue projection | `project_tax_revenue()` |
| 6.3 | Implement stress index | `calculate_fiscal_stress_index()` |
| 6.4 | Implement fund solvency | `calculate_fund_solvency()` |
| 6.5 | Add unit tests | Test each measure |

### Phase 7: Notebooks & Visualization (Week 6-7)

| Step | Task | Notebook |
|------|------|----------|
| 7.1 | Geography overview | Community area map/table |
| 7.2 | Tax base analysis | Assessment trends by area |
| 7.3 | Fiscal health dashboard | Stress index visualization |
| 7.4 | Revenue projections | Scenario comparison charts |
| 7.5 | Fund solvency report | 30-year projection |

---

## Summary Ratings

| Area | Before | After | Improvement |
|------|--------|-------|-------------|
| Model Config Consistency | 6/10 | 9/10 | +3 |
| Backend Abstraction | 6/10 | 9/10 | +3 |
| Exhibit Configuration | 5/10 | 8/10 | +3 |
| Core Model Quality | 5/10 | 8/10 | +3 |
| City Finance Model | 5/10 | 9/10 | +4 |
| **Overall** | **5.4/10** | **8.6/10** | **+3.2** |

---

## Appendix A: Data Sources for Chicago Actuarial Model

| Dataset | Source | API/Format | Key Fields |
|---------|--------|------------|------------|
| Community Areas | Chicago Data Portal | GeoJSON | boundaries, demographics |
| Tax Assessments | Cook County Assessor | CSV/API | PIN, assessed value, class |
| Tax Bills | Cook County Treasurer | CSV | PIN, levy, payment |
| Unemployment | Chicago Data Portal | JSON | community area, rate, date |
| Building Permits | Chicago Data Portal | JSON | address, type, value |
| City Budget | Chicago Data Portal | JSON | fund, department, amount |

---

## Appendix B: Rename `city_finance` → `chicago_actuarial`

The current `city_finance` model should be renamed to `chicago_actuarial` to reflect:
1. Specific focus on Chicago (not generic "city")
2. Actuarial/forecasting purpose (not just finance data)
3. Alignment with expanded scope

**Migration steps:**
1. Create new `configs/models/chicago_actuarial/`
2. Create new `models/implemented/chicago_actuarial/`
3. Update storage paths in `storage.json`
4. Deprecate old `city_finance` with redirect
5. Update notebooks and references

---

## Appendix C: Ingestion Pipeline Architecture

### Current Architecture Rating: ✅ 7/10

The ingestion pipeline follows a clean, pluggable architecture:

```
API → Provider → Facet (normalize) → BronzeSink → Bronze Layer (Delta Lake)
```

### Component Summary

| Component | Purpose | Rating |
|-----------|---------|--------|
| **BaseFacet** | Normalizes raw JSON → Spark DataFrame | ✅ 8/10 |
| **BaseProvider** | Abstract interface for data sources | ✅ 8/10 |
| **BaseRegistry** | Config-driven endpoint rendering | ✅ 8/10 |
| **HttpClient** | Rate limiting, retries, key rotation | ✅ 8/10 |
| **BronzeSink** | Delta Lake writes (upsert/append) | ✅ 9/10 |
| **ChicagoIngestor** | Chicago-specific pagination | ⚠️ 6/10 |

### Chicago Provider Gap Analysis

**Implemented Facets (2):**
- `building_permits_facet.py` ✅
- `unemployment_rates_facet.py` ✅

**Configured but Missing Facets (4):**
- `business_licenses` (r5kz-chrr) ❌
- `per_capita_income` (qpxx-qyaw) ❌
- `economic_indicators` (nej5-8p3s) ❌
- `affordable_rental_housing` (s6ha-ppgi) ❌

### New Facets Needed for Actuarial Model

| Facet | Dataset ID | Bronze Table | Effort |
|-------|------------|--------------|--------|
| `community_areas_facet.py` | `igwz-8jzy` | `chicago_community_areas` | 2 hours |
| `tax_assessments_facet.py` | Cook County | `chicago_tax_assessments` | 4 hours |
| `tax_bills_facet.py` | Cook County | `chicago_tax_bills` | 4 hours |
| `city_budget_facet.py` | `fg6s-gzvg` | `chicago_city_budget` | 2 hours |

### Facet Implementation Pattern

```python
# datapipelines/providers/chicago/facets/tax_assessments_facet.py (NEW)

class TaxAssessmentsFacet(ChicagoFacet):
    """Transform Cook County tax assessment data."""

    SPARK_CASTS = {
        "pin": "string",
        "tax_year": "int",
        "assessed_value": "double",
        "market_value": "double",
        "property_class": "string",
        "community_area": "int",
    }

    FINAL_COLUMNS = [
        ("pin", "string"),
        ("tax_year", "int"),
        ("community_area", "int"),
        ("property_class", "string"),
        ("land_assessed", "double"),
        ("building_assessed", "double"),
        ("total_assessed", "double"),
        ("market_value", "double"),
        ("exemption_total", "double"),
    ]

    def calls(self):
        params = {}
        if self.date_from:
            params["$where"] = f"tax_year >= {self.date_from[:4]}"
        yield {"ep_name": "tax_assessments", "params": params}

    def postprocess(self, df):
        from pyspark.sql import functions as F
        return (
            df.select(
                F.col("pin").alias("pin"),
                F.col("tax_year").cast("int"),
                F.col("community_area_number").cast("int").alias("community_area"),
                F.col("class").alias("property_class"),
                F.col("land_av").cast("double").alias("land_assessed"),
                F.col("bldg_av").cast("double").alias("building_assessed"),
                (F.col("land_av") + F.col("bldg_av")).alias("total_assessed"),
                F.col("market_value").cast("double"),
                F.coalesce(F.col("exe_total"), F.lit(0)).cast("double").alias("exemption_total"),
            )
            .dropna(subset=["pin"])
            .dropDuplicates(["pin", "tax_year"])
        )
```

### Storage Configuration Updates

```json
// configs/storage.json additions
{
  "chicago_community_areas": {
    "root": "bronze",
    "rel": "chicago/community_areas",
    "partitions": [],
    "write_strategy": "upsert",
    "key_columns": ["community_area_number"]
  },
  "chicago_tax_assessments": {
    "root": "bronze",
    "rel": "chicago/tax_assessments",
    "partitions": ["tax_year"],
    "write_strategy": "upsert",
    "key_columns": ["pin", "tax_year"]
  },
  "chicago_tax_bills": {
    "root": "bronze",
    "rel": "chicago/tax_bills",
    "partitions": ["tax_year"],
    "write_strategy": "append",
    "key_columns": ["pin", "tax_year", "agency_number"]
  },
  "chicago_city_budget": {
    "root": "bronze",
    "rel": "chicago/city_budget",
    "partitions": ["fiscal_year"],
    "write_strategy": "upsert",
    "key_columns": ["fund_code", "fiscal_year"]
  }
}
```

---

## Appendix D: Model Building Process

### Current Architecture Rating: ✅ 8/10

The model building system uses a well-designed composition pattern:

```
Bronze Layer → YAML Config → GraphBuilder → In-Memory DataFrames → ModelWriter → Silver Layer
```

### Build Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ SCRIPTS                                                             │
│ scripts/build/build_all_models.py                                   │
│ scripts/build/build_silver_layer.py                                 │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ Orchestrates
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│ MODEL INSTANTIATION                                                  │
│ model = ChicagoActuarialModel(connection, storage_cfg, model_cfg)   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ Calls
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│ BaseModel.build()                                                    │
│ ├── before_build() hook                                             │
│ ├── GraphBuilder._build_nodes()                                     │
│ │   ├── For each node in graph.yaml:                               │
│ │   │   ├── _load_bronze_table()  → StorageRouter → BronzeTable    │
│ │   │   ├── _apply_filters()      → Backend-agnostic filtering     │
│ │   │   ├── _apply_joins()        → Internal table joins           │
│ │   │   ├── _apply_select()       → Column mapping/aliasing        │
│ │   │   ├── _apply_derive()       → Computed columns               │
│ │   │   └── _enforce_unique_key() → Deduplication                  │
│ │   └── Return {node_id: DataFrame}                                │
│ ├── Separate dims (dim_*) vs facts (fact_*)                        │
│ └── after_build() hook                                              │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ Returns (dims, facts)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ModelWriter.write_tables()                                           │
│ ├── For each dimension:                                             │
│ │   └── Write to storage/silver/{model}/dims/{dim_name}/           │
│ └── For each fact:                                                  │
│     └── Write to storage/silver/{model}/facts/{fact_name}/         │
│ Format: Delta Lake (default) or Parquet                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| **BaseModel** | `models/base/model.py` | 397 | Orchestrator (composition) |
| **GraphBuilder** | `models/base/graph_builder.py` | 550 | Node loading + transforms |
| **TableAccessor** | `models/base/table_accessor.py` | 269 | Table access methods |
| **MeasureCalculator** | `models/base/measure_calculator.py` | 277 | Measure computation |
| **ModelWriter** | `models/base/model_writer.py` | 341 | Silver persistence |
| **StorageRouter** | `models/api/dal.py` | 78 | Path resolution |
| **BronzeTable** | `models/api/dal.py` | 78 | Auto-detect Delta/Parquet |

### Graph Node Processing

Each node in `graph.yaml` goes through this pipeline:

```yaml
# Example node definition
- id: fact_tax_assessment
  from: bronze.chicago_tax_assessments    # 1. Load from Bronze
  filters:                                  # 2. Apply filters
    - "tax_year >= 2015"
  join:                                     # 3. Join other nodes
    table: dim_geography
    on: ["community_area=community_area_number"]
  select:                                   # 4. Map columns
    geography_id: geography_id
    tax_year: tax_year
  derive:                                   # 5. Compute columns
    assessment_id: "CONCAT(geography_id, '_', tax_year)"
  unique_key: [assessment_id]               # 6. Deduplicate
```

### city_finance Current Build Status

**Status:** ⚠️ NOT in active build pipeline

**Issue:** `city_finance` is not in `BUILDABLE_MODELS` list in `build_silver_layer.py`

**Fix Required:**
```python
# scripts/build/build_silver_layer.py
BUILDABLE_MODELS = [
    "core",
    "company",
    "stocks",
    "macro",
    "city_finance",      # ADD THIS
    "chicago_actuarial", # ADD THIS (new model)
]
```

### Build Script for Chicago Actuarial

```bash
# Step 1: Ensure Bronze data exists
python -m scripts.ingest.chicago_ingestor --datasets community_areas,tax_assessments,unemployment

# Step 2: Build Silver model
python -m scripts.build.build_silver_layer --model chicago_actuarial

# Step 3: Verify output
ls -la storage/silver/chicago_actuarial/dims/
ls -la storage/silver/chicago_actuarial/facts/
```

### Model Build Hooks

The `chicago_actuarial` model can implement custom hooks:

```python
# models/implemented/chicago_actuarial/model.py

class ChicagoActuarialModel(BaseModel):
    """Chicago actuarial forecast model."""

    def before_build(self) -> None:
        """Pre-build validation."""
        # Verify required Bronze tables exist
        required_tables = [
            'chicago_community_areas',
            'chicago_tax_assessments',
            'chicago_unemployment'
        ]
        for table in required_tables:
            path = self.storage_router.bronze_path(table)
            if not Path(path).exists():
                raise ValueError(f"Required Bronze table missing: {table}")

    def after_build(
        self,
        dims: Dict[str, DataFrame],
        facts: Dict[str, DataFrame]
    ) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """Post-build transformations."""
        # Calculate YoY changes for tax assessments
        if 'fact_tax_assessment' in facts:
            facts['fact_tax_assessment'] = self._add_yoy_changes(
                facts['fact_tax_assessment']
            )
        return dims, facts

    def _add_yoy_changes(self, df: DataFrame) -> DataFrame:
        """Add year-over-year value changes."""
        from pyspark.sql import Window
        from pyspark.sql import functions as F

        window = Window.partitionBy('geography_id').orderBy('tax_year')

        return df.withColumn(
            'prior_year_value',
            F.lag('total_assessed_value').over(window)
        ).withColumn(
            'yoy_value_change',
            (F.col('total_assessed_value') - F.col('prior_year_value')) /
            F.col('prior_year_value')
        ).drop('prior_year_value')
```

---

## Appendix E: Complete Implementation Checklist

### Phase 5 Detailed: Data Ingestion

| Step | Task | File | Est. Hours |
|------|------|------|------------|
| 5.1a | Create community areas endpoint config | `chicago_endpoints.json` | 0.5 |
| 5.1b | Create `CommunityAreasFacet` class | `community_areas_facet.py` | 2 |
| 5.1c | Add storage config | `storage.json` | 0.25 |
| 5.2a | Research Cook County Assessor API | Documentation | 2 |
| 5.2b | Create tax assessments endpoint config | `chicago_endpoints.json` | 0.5 |
| 5.2c | Create `TaxAssessmentsFacet` class | `tax_assessments_facet.py` | 4 |
| 5.2d | Add storage config | `storage.json` | 0.25 |
| 5.3a | Research Cook County Treasurer API | Documentation | 2 |
| 5.3b | Create tax bills endpoint config | `chicago_endpoints.json` | 0.5 |
| 5.3c | Create `TaxBillsFacet` class | `tax_bills_facet.py` | 4 |
| 5.3d | Add storage config | `storage.json` | 0.25 |
| 5.4 | Update `ChicagoIngestor` to use new facets | `chicago_ingestor.py` | 2 |
| 5.5 | Run test ingestion | CLI | 1 |
| 5.6 | Verify Bronze data quality | Notebook | 2 |
| **Total** | | | **~21 hours** |

### Phase 4 Detailed: Model Configuration

| Step | Task | File | Est. Hours |
|------|------|------|------------|
| 4.1 | Create model directory | `configs/models/chicago_actuarial/` | 0.25 |
| 4.2 | Create model.yaml with dependencies | `model.yaml` | 0.5 |
| 4.3a | Define dim_geography schema | `schema.yaml` | 1 |
| 4.3b | Define dim_property_class schema | `schema.yaml` | 0.5 |
| 4.3c | Define dim_tax_district schema | `schema.yaml` | 0.5 |
| 4.3d | Define fact_tax_assessment schema | `schema.yaml` | 1 |
| 4.3e | Define fact_tax_collection schema | `schema.yaml` | 1 |
| 4.3f | Define fact_economic_activity schema | `schema.yaml` | 0.5 |
| 4.4a | Define dimension nodes | `graph.yaml` | 2 |
| 4.4b | Define fact nodes with aggregations | `graph.yaml` | 3 |
| 4.4c | Define edges and paths | `graph.yaml` | 1 |
| 4.5 | Define YAML measures | `measures.yaml` | 1 |
| 4.6a | Create model.py with hooks | `model.py` | 2 |
| 4.6b | Create measures.py with Python measures | `measures.py` | 4 |
| 4.7 | Add to build pipeline | `build_silver_layer.py` | 0.5 |
| **Total** | | | **~19 hours** |

---

## Appendix F: Data Source Details

### Chicago Data Portal Datasets

| Dataset | ID | Records | Update Frequency |
|---------|----|---------|--------------------|
| Community Areas | `igwz-8jzy` | 77 | Static |
| Unemployment by Area | `ane4-dwhs` | ~50K | Monthly |
| Building Permits | `ydr8-5enu` | ~1.5M | Daily |
| Business Licenses | `r5kz-chrr` | ~200K | Daily |
| Budget - Appropriations | `fg6s-gzvg` | ~5K | Annual |

### Cook County Data Sources

| Dataset | Source | Format | Access |
|---------|--------|--------|--------|
| Property Assessments | Cook County Assessor | CSV/API | Public |
| Tax Bills | Cook County Treasurer | CSV | Public |
| Property Classes | Cook County Assessor | Reference | Static |
| Taxing Districts | Cook County Clerk | Reference | Public |

### API Rate Limits

| Provider | Rate Limit | Auth Required |
|----------|------------|---------------|
| Chicago Data Portal | 5 req/sec with token | Optional (X-App-Token) |
| Cook County Assessor | Unknown | Check terms |
| Cook County Treasurer | Unknown | Check terms |
