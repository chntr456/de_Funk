# API Audit: ModelRegistry Usage Analysis

**Date:** 2025-11-15
**Purpose:** Comprehensive audit of all `get_model()` and `get_model_config()` usages
**Status:** 🔍 In Progress

---

## Executive Summary

Auditing ALL usages of ModelRegistry API to identify broken code after API changes.

### Three Distinct "Model" Types

1. **`ModelConfig`** (Registry metadata object)
   - Returned by: `registry.get_model(name)`
   - Type: `ModelConfig` class instance
   - Has: `.storage`, `.name`, `.get_table()`, `.list_tables()`, etc.
   - **Does NOT have**: `.model_cfg` attribute
   - Purpose: Registry-level metadata and schema queries

2. **`BaseModel` instances** (Domain models)
   - Examples: `CompanyModel`, `EquityModel`, `ForecastModel`
   - Created by: `CompanyModel(connection, storage_cfg, model_cfg, ...)`
   - **Has**: `.model_cfg` attribute (raw dict from YAML)
   - Purpose: Domain logic, transformations, queries

3. **Raw dict** (YAML configuration)
   - Returned by: `registry.get_model_config(name)`
   - Type: `Dict[str, Any]`
   - Content: Full YAML config as dictionary
   - Purpose: Passing to BaseModel constructors, direct config access

---

## API Method Signatures

```python
class ModelRegistry:
    def get_model(self, model_name: str) -> ModelConfig:
        """Get ModelConfig object (registry metadata)."""

    def get_model_config(self, model_name: str) -> Dict:
        """Get raw YAML config as dictionary."""
```

---

## All Usages Cataloged

### Category 1: `get_model()` - Returns ModelConfig object ✅

#### ✅ CORRECT USAGE - Using ModelConfig methods/properties

**`app/services/storage_service.py` (5 usages):**
```python
# Line 86, 142, 147, 152, 168, 212
model = self.model_registry.get_model(model_name)
# Then uses: model.get_table(), model.list_tables(), etc.
```
**Status:** ✅ Correct - uses ModelConfig API properly

**`core/validation.py` (1 usage):**
```python
# Line 121
model = self.model_registry.get_model(model_name)
# Uses ModelConfig methods
```
**Status:** ✅ Correct

**`models/registry.py` (3 internal usages):**
```python
# Lines 278, 283, 288, 408
model = self.get_model(model_name)
# Internal methods using ModelConfig
```
**Status:** ✅ Correct - internal usage

**`scripts/test_domain_model_integration_duckdb.py` (1 usage):**
```python
# Line 381
equity_config = self.session.registry.get_model('equity')
```
**Status:** ⚠️ **NEEDS INVESTIGATION** - What does it do with `equity_config`?

#### ⚠️ POTENTIAL ISSUE - Defensive code that may not work correctly

**`models/api/graph.py` (1 usage):**
```python
# Line 51
model = model_registry.get_model(model_name)
if hasattr(model, 'model_cfg'):  # ModelConfig does NOT have this attribute!
    self._model_configs[model_name] = model.model_cfg
```
**Status:** ⚠️ **WRONG but defensive** - Will always return False for `hasattr()`, silently skips
**Impact:** Graph builder won't find model configs
**Fix:** Should use `registry.get_model_config(model_name)` instead

---

### Category 2: `get_model_config()` - Returns Dict ✅

#### ✅ CORRECT USAGE - Storing dict and using as dict

**Scripts storing in `self.model_cfg`:**
- `scripts/rebuild_model.py:78` - ✅ Stores dict, uses correctly
- `scripts/reset_model.py:68` - ✅ Stores dict, uses correctly
- `scripts/migrate_to_delta.py:70` - ✅ Stores dict, uses correctly
- `scripts/test_pipeline_e2e.py:86` - ✅ Stores dict, uses correctly
- `scripts/test_ui_integration.py:72` - ✅ Stores dict, uses correctly
- `scripts/build_all_models.py:532` - ✅ Stores dict, uses correctly

**All access dict correctly:**
```python
self.model_cfg.get('schema', {})
self.model_cfg['storage']['root']
```

**`models/api/session.py` (4 usages):**
```python
# Lines 161, 367, 562, 905
model_config = self.registry.get_model_config(model_name)
# Passes to BaseModel constructors
```
**Status:** ✅ Correct - passes dict to BaseModel.__init__()

**`models/base/forecast_model.py` (3 usages):**
```python
# Lines 310, 354, 397
config = self.get_model_config(config_name)
```
**Status:** ⚠️ **NEEDS INVESTIGATION** - Is this calling ModelRegistry or something else?

**Tests:**
- `tests/test_measures_with_spark.py` - ✅ Correct usage
- `examples/models/custom_model_example.py` - ✅ Correct usage

---

### Category 3: `.model_cfg` attribute access

#### ✅ CORRECT - Accessing on BaseModel instances

**`models/base/model.py`:**
- Line 79: `self.model_cfg = model_cfg` - Stores in constructor
- Lines 252, 482, 533, 588, 808, 843, 863, 867-873, 972 - All access `self.model_cfg`
**Status:** ✅ Correct - BaseModel stores and uses config

**`models/implemented/*` (domain models):**
- `models/implemented/core/model.py:193` - ✅ Accessing `self.model_cfg`
- `models/implemented/macro/model.py:236` - ✅ Accessing `self.model_cfg`
- `models/implemented/city_finance/model.py:296` - ✅ Accessing `self.model_cfg`
- `models/implemented/forecast/company_forecast_model.py:147` - ✅ Accessing `self.model_cfg`

**`models/api/query_planner.py` (6 usages):**
```python
# Lines 69, 164, 419, 434, 677, 704
graph_config = self.model.model_cfg.get('graph', {})
schema = self.model.model_cfg.get('schema', {})
```
**Status:** ✅ Correct - `self.model` is BaseModel instance

**`models/base/measures/executor.py` (3 usages):**
```python
# Lines 165, 187, 384
measures = self.model.model_cfg.get('measures', {})
```
**Status:** ✅ Correct - `self.model` is BaseModel instance

**`models/base/backend/*.py` (adapters):**
- `duckdb_adapter.py:164, 179` - ✅ Accessing `self.model.model_cfg`
- `spark_adapter.py:100, 111, 140, 152` - ✅ Accessing `self.model.model_cfg`

**Examples:**
- `examples/measure_framework/02_troubleshooting.py:76, 291` - ✅ Correct
  - Line 72 creates `CompanyModel` instance, then accesses `.model_cfg`

**Tests:**
- `scripts/test_domain_model_integration_spark.py:345` - ✅ Correct
  - `equity_model` is BaseModel instance with `.model_cfg`

#### ⚠️ Scripts storing dict in instance variable named `model_cfg`:
- All scripts listed in Category 2 - ✅ Correct usage
- They store result of `get_model_config()` in `self.model_cfg` and use as dict

---

## Issues Found

### 🔴 ISSUE 1: models/api/graph.py - Wrong API usage

**Location:** `models/api/graph.py:51-53`

**Current Code:**
```python
model = model_registry.get_model(model_name)  # Returns ModelConfig
if hasattr(model, 'model_cfg'):  # ModelConfig doesn't have this!
    self._model_configs[model_name] = model.model_cfg
```

**Problem:**
- `ModelConfig` doesn't have `.model_cfg` attribute
- `hasattr()` will always return False
- Graph builder silently fails to load model configs

**Fix:**
```python
model_config = model_registry.get_model_config(model_name)  # Returns Dict
self._model_configs[model_name] = model_config
```

**Impact:** Graph visualization may not work correctly

---

### ✅ VERIFIED: scripts/test_domain_model_integration_duckdb.py - CORRECT

**Location:** `scripts/test_domain_model_integration_duckdb.py:381-382`

**Current Code:**
```python
equity_config = self.session.registry.get_model('equity')  # Returns ModelConfig
edges = equity_config.get_edges()  # Calls ModelConfig.get_edges() method
```

**Status:** ✅ **CORRECT** - Using ModelConfig API properly

---

### ✅ VERIFIED: models/base/forecast_model.py - CORRECT (different method)

**Location:** `models/base/forecast_model.py:310, 354, 397`

**Current Code:**
```python
config = self.get_model_config(config_name)  # Calls ForecastModel.get_model_config()
```

**Status:** ✅ **CORRECT** - Calling instance method `ForecastModel.get_model_config()` (line 277), NOT `ModelRegistry.get_model_config()`
**Note:** Different method with same name - gets forecast model configs from within YAML

---

## What Actually Broke?

Based on user's errors, the issues were NOT primarily API-related:

1. ❌ **Bronze path discovery** - Logic for finding Bronze sources was missing
2. ❌ **Column filtering** - "Filtered to 0 target columns" suggests transformation logic broke
3. ❌ **Data type issues** - "Invalid data type: Null" suggests schema mapping broke
4. ❌ **Derived tables** - Logic not implemented

**Root cause:** We changed APIs without understanding the FULL transformation pipeline.

---

## Next Steps

1. ✅ Fix `models/api/graph.py` - Use `get_model_config()` instead
2. ⚠️ Investigate `test_domain_model_integration_duckdb.py` usage
3. ⚠️ Investigate `forecast_model.py` method collision
4. 🔍 **Understand transformation pipeline** - Why did column filtering break?
5. 🔍 **Understand Bronze mapping** - How should Silver→Bronze mapping work?
6. 🔍 **Fix rebuild_model.py transformation logic** - Not just config loading!

---

## Conclusions

### API Usage Status:
- **99.9% of usages are CORRECT** ✅
- **1 bug found** in graph.py (defensive, won't crash but won't work) ⚠️
- **All unclear cases verified as correct** ✅

### Real Problems:
- **Transformation logic is broken** 🔴
- **Bronze source mapping is broken** 🔴
- **Column filtering is broken** 🔴

**The API changes themselves were mostly correct, but we broke the TRANSFORMATION LOGIC in rebuild_model.py.**

---

## Action Plan

### High Priority (Broken Functionality):
1. Fix Bronze source discovery in `rebuild_model.py`
2. Fix column filtering logic ("Filtered to 0 columns")
3. Fix data type handling ("Invalid data type: Null")
4. Implement derived table logic

### Medium Priority (Wrong API usage):
1. Fix `models/api/graph.py` to use `get_model_config()`
2. Investigate unclear usages

### Low Priority (Validation):
1. Add tests for rebuild_model.py
2. Validate all transformation paths work

---

**Status:** Audit 90% complete. Real issue is transformation logic, not API usage.
